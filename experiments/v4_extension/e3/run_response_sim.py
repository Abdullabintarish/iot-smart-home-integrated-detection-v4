"""Experiment E3: SIMULATED response (offline mitigation replay).

Replays the 1,692,332 Run B test events in time order and asks what an
automatic blocking response would have achieved had it acted on each
detector's alerts. Nothing is retrained and no network device is touched:
this is an offline, simulated mitigation measurement on recorded traffic.

Order      within each source capture by (ts, event_id); keys contain the
           source, so captures never interact.
Triggers   (labels are never used to decide a block, except by the oracle)
  A/C              pred_fragmented: an alert at every predicted-attack event.
                   C groups the same alerts (E2); every member opens or
                   updates its group alert, so C triggers = A triggers.
  B                pred_integrated: an incident's alert is raised at its last
                   event (the incident summary needs the finished group, E2).
  event_only, event_plus_thin   E1/E2b seed-42 ablation predictions, as A.
  oracle           ground-truth label as trigger. NOT ACHIEVABLE: upper bound.
  none             no response: lower bound.
Policies   P1 flow  = (source, src_ip, dst_ip, proto)
           P2 host  = (source, src_ip)
Blocks     an alert at event position p, time t, on key k blocks every later
           event (position > p) with key k and time in [t, t + D),
           D in {60, 300, 900 s, end of capture}. A later alert on k sets the
           end to its own time + D (start if no block was active, otherwise
           extension). Alerts keep coming from blocked traffic: the sensor is
           assumed to see traffic before the block point, and the saved
           predictions cover every event. The alerting event itself is not
           prevented by its own alert.
Scoring    (labels only here)
  prevented        blocked attack events / attack test events
  wrongly blocked  blocked benign events / benign test events
  benign hosts     distinct (source, src_ip) with >= 1 benign event blocked
  contained        attack incident (Run B incident_id with an attack event)
                   with >= 2 attack events and >= 90% of the attack events
                   after its first one blocked; none_blocked: 0 of them
  time to block    0 if the incident's first attack event is already blocked,
                   otherwise time of the next alert on its key at or after
                   that event (own alert included) minus its time. Incidents
                   never covered are counted, not given a value.

    PYTHONPATH=code code/.venv/Scripts/python.exe -B -u \
        experiments/v4_extension/e3/run_response_sim.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
V4 = HERE.parent
sys.path.insert(0, str(V4))
sys.path.insert(0, str(V4.parent / "ablation"))
import run_alert_workload as W  # noqa: E402  (unchanged; brings run_ablation)

R = W.R
C = R.C
OUT = HERE / "results"
E2_EVENTS = V4 / "results" / "e2" / "e2_events.parquet"
BENIGN = "benign"
ATTACKS = ("c2", "dos", "malware", "recon")
DURATIONS = (60.0, 300.0, 900.0, np.inf)
POLICIES = {"P1_flow": ["source", "src_ip", "dst_ip", "proto"], "P2_host": ["source", "src_ip"]}
N_TEST = 1_692_332
log = R.log


def dur_name(d: float) -> str:
    return "end" if np.isinf(d) else str(int(d))


# ---------------------------------------------------------------- loading
def load() -> pd.DataFrame:
    """Run B test events joined with the E2 predictions by event_id, in replay order."""
    ev = W.load_test_events()                 # event_id = Stage-4 stream position
    pr = pd.read_parquet(E2_EVENTS)
    chk = {"test_events": len(ev), "e2_rows": len(pr),
           "e2_event_id_unique": bool(pr["event_id"].is_unique),
           "test_event_id_unique": bool(ev["event_id"].is_unique)}
    m = ev.merge(pr, on="event_id", how="inner", suffixes=("", "_e2"), validate="one_to_one")
    chk["joined"] = len(m)
    for c in ("incident_id", "label"):
        chk[f"{c}_matches"] = bool((m[c].astype(str) == m[f"{c}_e2"].astype(str)).all())
    chk["ts_matches"] = bool(np.array_equal(m["ts"].astype(float), m["ts_e2"].astype(float)))
    ok = (len(ev) == len(pr) == len(m) == N_TEST and chk["e2_event_id_unique"]
          and chk["test_event_id_unique"] and all(v for k, v in chk.items() if k.endswith("matches")))
    if not ok:
        raise SystemExit(f"join check failed: {chk}")
    m = m.drop(columns=[c for c in m.columns if c.endswith("_e2")])
    for c in ("source", "src_ip", "dst_ip", "incident_id", "label"):
        m[c] = m[c].astype(str)
    m["ts"] = m["ts"].astype("float64")
    m = m.sort_values(["source", "ts", "event_id"], kind="mergesort").reset_index(drop=True)
    m.attrs["join_checks"] = chk
    return m


def key_codes(ev: pd.DataFrame, cols: list[str]) -> np.ndarray:
    return ev.groupby(cols, sort=False, observed=True).ngroup().to_numpy("int64")


# ---------------------------------------------------------------- triggers (label-free)
def event_trigger(pred: np.ndarray) -> np.ndarray:
    """Alert positions: every predicted-attack event."""
    return np.flatnonzero(np.asarray(pred) != BENIGN)


def incident_trigger(incident: np.ndarray, pred: np.ndarray) -> np.ndarray:
    """Alert positions for B: the last event (in replay order) of each predicted-attack incident."""
    s = pd.DataFrame({"inc": incident, "att": np.asarray(pred) != BENIGN,
                      "pos": np.arange(len(incident))})
    g = s.groupby("inc", sort=False)
    last = g["pos"].max()
    att = g["att"].any()
    return np.sort(last[att].to_numpy("int64"))


def grouped_trigger(ev: pd.DataFrame, pred: np.ndarray, window: int = 300) -> np.ndarray:
    """C: A's alerts grouped as in E2; each member opens or updates its group alert."""
    mask = np.asarray(pred) != BENIGN
    gid = W.groups(ev, mask, window)
    members = pd.DataFrame({"g": gid, "pos": np.flatnonzero(mask)})
    return np.sort(members["pos"].to_numpy("int64"))   # every member is an alert update


# ---------------------------------------------------------------- replay
def simulate(key: np.ndarray, ts: np.ndarray, alert_pos: np.ndarray, duration: float) -> dict:
    """Causal block replay. ``key``/``ts`` are in replay order; alerts sit at event positions.

    For each event: blocked iff an alert on its key at an earlier position has
    ts_event - ts_alert < duration (the latest such alert, since each alert
    restarts or extends the block). Also returns the time of the next alert on
    the event's key at or after it (own alert included), for time-to-block.
    """
    n, a = len(key), np.asarray(alert_pos, dtype="int64")
    k = np.concatenate([key, key[a]])
    p = np.concatenate([np.arange(n), a])
    kind = np.concatenate([np.zeros(n, "int8"), np.ones(len(a), "int8")])
    t = np.concatenate([ts, ts[a]])
    o = np.lexsort((kind, p, k))                     # alert after its own event
    ks, ts_o, is_a = k[o], t[o], kind[o] == 1
    m = len(o)
    i = np.arange(m)
    last = np.maximum.accumulate(np.where(is_a, i, -1))
    ok = (last >= 0) & (ks[np.clip(last, 0, None)] == ks)
    last_ts = np.where(ok, ts_o[np.clip(last, 0, None)], np.nan)
    nxt = np.minimum.accumulate(np.where(is_a, i, m)[::-1])[::-1]
    okn = (nxt < m) & (ks[np.clip(nxt, None, m - 1)] == ks)
    next_ts = np.where(okn, ts_o[np.clip(nxt, None, m - 1)], np.nan)
    ev_rows = ~is_a
    pos = p[o][ev_rows]
    out_last = np.empty(n); out_last[pos] = last_ts[ev_rows]
    out_next = np.empty(n); out_next[pos] = next_ts[ev_rows]
    with np.errstate(invalid="ignore"):
        blocked = (ts - out_last) < duration
    blocked &= ~np.isnan(out_last)
    # block actions: alert while a block on its key is active -> extension
    ao = np.lexsort((a, key[a]))
    ak, at = key[a][ao], ts[a][ao]
    same = np.r_[False, ak[1:] == ak[:-1]]
    ext = same & ((at - np.r_[np.nan, at[:-1]]) < duration)
    return {"blocked": blocked, "next_alert_ts": out_next,
            "starts": int(len(a) - ext.sum()), "extensions": int(ext.sum()), "alerts": int(len(a))}


# ---------------------------------------------------------------- scoring (labels used here only)
class Truth:
    def __init__(self, ev: pd.DataFrame):
        self.y = ev["label"].to_numpy()
        self.att = self.y != BENIGN
        self.ts = ev["ts"].to_numpy()
        self.bot = ev["source"].str.startswith("data_").to_numpy()
        self.host = key_codes(ev, ["source", "src_ip"])
        self.inc, inc_names = pd.factorize(ev["incident_id"])
        pos = np.arange(len(ev))
        first = pd.Series(np.where(self.att, pos, np.iinfo("int64").max)).groupby(self.inc).min()
        self.att_inc = first.index[first < np.iinfo("int64").max].to_numpy()
        self.first_pos = first.loc[self.att_inc].to_numpy("int64")
        self.is_first = np.zeros(len(ev), bool); self.is_first[self.first_pos] = True
        self.n_inc = len(inc_names)
        self.n_att_inc = int(len(self.att_inc))
        last_att = pd.Series(np.where(self.att, self.ts, -np.inf)).groupby(self.inc).max()
        self.last_att_ts = last_att.loc[self.att_inc].to_numpy()
        self.later_att = self.att & ~self.is_first            # attack events after each incident's first
        self.n_later = np.bincount(self.inc[self.later_att], minlength=self.n_inc)[self.att_inc]


def share(num, den):
    return float(num / den) if den else None


def score(tr: Truth, sim: dict, subset: np.ndarray | None = None) -> dict:
    b = sim["blocked"]
    m = np.ones(len(b), bool) if subset is None else subset
    att, ben = tr.att & m, ~tr.att & m
    nodos = att & (tr.y != "dos")
    r = {"attack_events": int(att.sum()), "attack_prevented": int((b & att).sum()),
         "benign_events": int(ben.sum()), "benign_blocked": int((b & ben).sum()),
         "attack_events_excl_dos": int(nodos.sum()),
         "attack_prevented_excl_dos": int((b & nodos).sum())}
    r["attack_prevented_share"] = share(r["attack_prevented"], r["attack_events"])
    r["benign_blocked_share"] = share(r["benign_blocked"], r["benign_events"])
    r["attack_prevented_share_excl_dos"] = share(r["attack_prevented_excl_dos"],
                                                 r["attack_events_excl_dos"])
    r["benign_hosts_affected"] = int(len(np.unique(tr.host[b & ben])))
    if subset is not None:
        return r
    # incidents
    blk_later = np.bincount(tr.inc[tr.later_att & b], minlength=tr.n_inc)[tr.att_inc]
    elig = tr.n_later > 0
    frac = np.divide(blk_later, tr.n_later, out=np.zeros(len(blk_later)), where=elig)
    r.update({"attack_incidents": tr.n_att_inc, "incidents_single_attack_event": int((~elig).sum()),
              "incidents_eligible": int(elig.sum()), "incidents_contained_90": int((elig & (frac >= 0.9)).sum()),
              "incidents_none_blocked": int((elig & (blk_later == 0)).sum())})
    f = tr.first_pos
    t0 = tr.ts[f]
    ttb = np.where(b[f], 0.0, sim["next_alert_ts"][f] - t0)
    cov = ~np.isnan(ttb)
    r.update({"incidents_with_block": int(cov.sum()), "incidents_never_blocked": int((~cov).sum()),
              "incidents_block_before_last_attack": int((cov & (t0 + np.nan_to_num(ttb, nan=np.inf)
                                                                 <= tr.last_att_ts)).sum()),
              "time_to_block_median_s": float(np.median(ttb[cov])) if cov.any() else None,
              "time_to_block_p90_s": float(np.percentile(ttb[cov], 90)) if cov.any() else None,
              "block_actions": sim["starts"] + sim["extensions"], "block_starts": sim["starts"],
              "block_extensions": sim["extensions"], "alerts": sim["alerts"]})
    return r


def breakdown(tr: Truth, sim: dict) -> list[dict]:
    b, rows = sim["blocked"], []
    for c in ATTACKS:
        m = tr.y == c
        rows.append({"group": "class", "value": c, "events": int(m.sum()),
                     "blocked": int((b & m).sum()), "share": share((b & m).sum(), m.sum())})
    for name, d in (("IoT-23", ~tr.bot), ("Bot-IoT", tr.bot)):
        for kind, m in (("attack", tr.att & d), ("benign", ~tr.att & d),
                        ("attack_excl_dos", tr.att & d & (tr.y != "dos"))):
            rows.append({"group": f"dataset_{kind}", "value": name, "events": int(m.sum()),
                         "blocked": int((b & m).sum()), "share": share((b & m).sum(), m.sum())})
    return rows


def bootstrap(tr: Truth, ba: np.ndarray, bb: np.ndarray, reps=1000, seed=42) -> dict:
    """Incident-clustered interval for share(A/C) - share(B); block outcomes held fixed."""
    k = tr.n_inc
    def s(m): return np.bincount(tr.inc[m], minlength=k).astype("float64")
    att, ben, nd = s(tr.att), s(~tr.att), s(tr.att & (tr.y != "dos"))
    pa, pb = s(tr.att & ba), s(tr.att & bb)
    wa, wb = s(~tr.att & ba), s(~tr.att & bb)
    na, nb = s(tr.att & (tr.y != "dos") & ba), s(tr.att & (tr.y != "dos") & bb)
    rng = np.random.default_rng(seed)
    d = np.empty((reps, 3))
    for r in range(reps):
        w = np.bincount(rng.integers(0, k, k), minlength=k)
        d[r] = ((w @ pa - w @ pb) / (w @ att), (w @ wa - w @ wb) / (w @ ben),
                (w @ na - w @ nb) / (w @ nd))
    pt = ((pa.sum() - pb.sum()) / att.sum(), (wa.sum() - wb.sum()) / ben.sum(),
          (na.sum() - nb.sum()) / nd.sum())
    ci = lambda c: [float(np.percentile(d[:, c], 2.5)), float(np.percentile(d[:, c], 97.5))]
    return {"prevented_diff": float(pt[0]), "prevented_diff_ci": ci(0),
            "wrongly_blocked_diff": float(pt[1]), "wrongly_blocked_diff_ci": ci(1),
            "prevented_excl_dos_diff": float(pt[2]), "prevented_excl_dos_diff_ci": ci(2),
            "n_boot": reps, "seed": seed, "clusters": int(k)}


# ---------------------------------------------------------------- main
def triggers(ev: pd.DataFrame) -> dict[str, np.ndarray | None]:
    inc = ev["incident_id"].to_numpy()
    return {"A/C": event_trigger(ev["pred_fragmented"].to_numpy()),
            "B": incident_trigger(inc, ev["pred_integrated"].to_numpy()),
            "event_only": event_trigger(ev["pred_event_only"].to_numpy()),
            "event_plus_thin": event_trigger(ev["pred_event_plus_thin"].to_numpy()),
            "oracle": event_trigger(ev["label"].to_numpy()),      # NOT ACHIEVABLE
            "none": np.empty(0, "int64")}


def main() -> int:
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    log("loading and joining")
    ev = load()
    chk = {"join": ev.attrs["join_checks"], "replay_events": len(ev)}
    keys = {p: key_codes(ev, cols) for p, cols in POLICIES.items()}
    for p, k in keys.items():
        chk[f"{p}_keys"] = int(k.max() + 1)
        chk[f"{p}_one_key_per_incident"] = bool(
            (pd.Series(k).groupby(ev["incident_id"].to_numpy()).nunique() == 1).all())
    chk["integrated_constant_within_incident"] = bool(
        (ev.groupby("incident_id")["pred_integrated"].nunique() == 1).all())
    tr = Truth(ev)
    chk["attack_incidents"] = tr.n_att_inc
    chk["true_incidents"] = tr.n_inc
    trig = triggers(ev)
    c_trig = grouped_trigger(ev, ev["pred_fragmented"].to_numpy(), 300)
    chk["C_triggers_equal_A"] = bool(np.array_equal(c_trig, trig["A/C"]))
    ts = ev["ts"].to_numpy()
    rows, brk, per_cap, keep, boots = [], [], [], {}, {}
    src = ev["source"].to_numpy()
    sources = sorted(np.unique(src))
    for pol, k in keys.items():
        for d in DURATIONS:
            sims = {}
            for name, a in trig.items():
                sim = simulate(k, ts, a, d)
                sims[name] = sim
                rows.append({"trigger": name, "policy": pol, "duration": dur_name(d), **score(tr, sim)})
                brk += [{"trigger": name, "policy": pol, "duration": dur_name(d), **x}
                        for x in breakdown(tr, sim)]
                if d == 300.0:
                    keep[f"{name}|{pol}"] = sim["blocked"]
                    per_cap += [{"trigger": name, "policy": pol, "duration": "300", "source": s,
                                 **score(tr, sim, src == s)} for s in sources]
            c_sim = simulate(k, ts, c_trig, d)
            chk[f"C_blocking_equals_A_{pol}_{dur_name(d)}"] = bool(
                np.array_equal(c_sim["blocked"], sims["A/C"]["blocked"]))
            if d == 300.0:
                boots[pol] = bootstrap(tr, sims["A/C"]["blocked"], sims["B"]["blocked"])
            log(f"{pol} D={dur_name(d)} done")
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "response_all.csv", index=False)
    pd.DataFrame(brk).to_csv(OUT / "response_breakdown.csv", index=False)
    pc = pd.DataFrame(per_cap)
    pc.to_csv(OUT / "response_per_capture.csv", index=False)
    # per-capture wins of A/C over B (300 s)
    wins = {}
    for pol in POLICIES:
        a = pc[(pc.trigger == "A/C") & (pc.policy == pol)].set_index("source")
        b = pc[(pc.trigger == "B") & (pc.policy == pol)].set_index("source")
        pa, pb = a["attack_prevented_share"], b["attack_prevented_share"]
        wa, wb = a["benign_blocked_share"], b["benign_blocked_share"]
        hp, hw = pa.notna() & pb.notna(), wa.notna() & wb.notna()
        wins[pol] = {"captures_with_attacks": int(hp.sum()),
                     "AC_more_prevented": int((pa[hp] > pb[hp]).sum()),
                     "AC_less_prevented": int((pa[hp] < pb[hp]).sum()),
                     "prevented_ties": int((pa[hp] == pb[hp]).sum()),
                     "captures_with_benign": int(hw.sum()),
                     "AC_fewer_wrongly_blocked": int((wa[hw] < wb[hw]).sum()),
                     "AC_more_wrongly_blocked": int((wa[hw] > wb[hw]).sum()),
                     "wrongly_blocked_ties": int((wa[hw] == wb[hw]).sum())}
    (OUT / "per_capture_wins.json").write_text(json.dumps(wins, indent=2), encoding="utf-8")
    (OUT / "bootstrap.json").write_text(json.dumps(boots, indent=2), encoding="utf-8")
    pd.DataFrame({"event_id": ev["event_id"].to_numpy(),
                  **{f"blocked_{k.replace('/', '').replace('|', '__')}": v for k, v in keep.items()}}
                 ).to_parquet(OUT / "blocked_300s.parquet")
    chk["minutes"] = round((time.perf_counter() - t0) / 60, 1)
    (OUT / "checks.json").write_text(json.dumps(chk, indent=2), encoding="utf-8")
    print(json.dumps(chk, indent=2))
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
