"""Experiment E2: detect first, correlate afterwards (alert-workload PROXY).

Counts alerts an analyst would have to open under three designs, from saved
event-level predictions on the same 1,692,332 Run B test events. Nothing is
retrained. No analyst was involved: alert counts are a proxy for workload.

  A  fragmented baseline     every predicted-attack event is one alert
  B  integrated incident     every predicted-attack incident is one alert
  C  detect then correlate   A's predicted-attack events grouped with the
                             pipeline's correlation key (60 / 300 / 900 s);
                             each group is one alert

Ground truth: an attack incident is a Run B incident (incident_id) with at
least one attack event. It is detected when at least one of its attack events
is inside an alert.

Delay (retrospective, offline) from the first attack event of a true incident
to its first alert:
  A        timestamp of the first alerted attack event
  B        incident close = timestamp of the incident's last event (the
           incident summary needs the completed group)
  C open   the group alert is opened by its first member; the first alert
           holding an attack event of the incident is at that event's time,
           so C open = A by construction
  C closed close = timestamp of the alert group's last member event
All groups here are built after the fact from complete records; "closed"
delays use later records and are not online latencies.

    PYTHONPATH=code code/.venv/Scripts/python.exe -B \
        experiments/v4_extension/run_alert_workload.py
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
sys.path.insert(0, str(HERE.parent / "ablation"))
import run_ablation as R  # noqa: E402  (unchanged)

C = R.C
SUB = HERE.parents[1]
PRED = SUB / "predictions"
E1 = HERE / "results" / "e1" / "preds"
OUT = HERE / "results" / "e2"
WINDOWS = (60, 300, 900)
BENIGN = "benign"
log = R.log


def load_test_events() -> pd.DataFrame:
    """Run B test events with timestamps and correlation fields (no features)."""
    files = sorted((C.DATA_OUT / "stage3_events").glob("*.parquet"))
    cols = ["ts", "src_ip", "dst_ip", "proto", "source", "split", "incident_id", "label"]
    df = pd.concat([pd.read_parquet(f, columns=cols) for f in files], ignore_index=True)
    df["event_id"] = np.arange(len(df), dtype="int64")      # stream position (Stage 4)
    return df[df["split"].astype(str) == "test"].reset_index(drop=True)


def attach(ev: pd.DataFrame, path: Path) -> np.ndarray:
    """Predictions from a saved Run B CSV, aligned to ``ev`` and checked."""
    pr = pd.read_csv(path, dtype={"incident_id": str, "source": str, "label": str,
                                  "split": str, "pred": str})
    if len(pr) != len(ev) or not (pr["event_id"].to_numpy() == ev["event_id"].to_numpy()).all():
        pr = pr.set_index("event_id").reindex(ev["event_id"]).reset_index()
    for c in ("source", "incident_id", "label"):
        if not (pr[c].astype(str).to_numpy() == ev[c].astype(str).to_numpy()).all():
            raise ValueError(f"{path.name}: column {c} does not match the event table")
    return pr["pred"].astype(str).to_numpy()


def attach_e1(ev: pd.DataFrame, name: str) -> np.ndarray | None:
    f = E1 / f"runb_w300_{name}_s42.parquet"
    rows = E1 / "runb_test_rows.parquet"
    if not f.exists() or not rows.exists():
        return None
    r = pd.read_parquet(rows)
    if not (r["event_id"].to_numpy() == ev["event_id"].to_numpy()).all():
        raise ValueError("E1 prediction rows are not in event order")
    return pd.read_parquet(f)["pred"].astype(str).to_numpy()


def groups(ev: pd.DataFrame, mask: np.ndarray, window: int) -> np.ndarray:
    """Alert-group id for the masked events (correlation key; singletons alone)."""
    sub = ev.loc[mask]
    key, _, _ = R.correlation_key(sub, window_s=window)
    codes, uniq = pd.factorize(key)
    codes = codes.astype("int64")
    lonely = codes < 0
    codes[lonely] = len(uniq) + np.arange(lonely.sum())
    return codes


def truth(ev: pd.DataFrame) -> pd.DataFrame:
    """Per true incident: attack flag and first attack timestamp."""
    att = ev["label"].astype(str).to_numpy() != BENIGN
    t = pd.DataFrame({"inc": ev["incident_id"].astype(str), "ts": ev["ts"].astype(float),
                      "att": att})
    g = t.groupby("inc", sort=False)
    out = pd.DataFrame({"is_attack": g["att"].any(), "n_events": g.size(),
                        "last_ts": g["ts"].max()})
    out["first_attack_ts"] = t[t.att].groupby("inc")["ts"].min()
    return out


def delays(d: pd.Series) -> dict:
    d = d.dropna().to_numpy(dtype="float64")
    return {"delay_n": int(len(d)),
            "delay_median_s": float(np.median(d)) if len(d) else None,
            "delay_p90_s": float(np.percentile(d, 90)) if len(d) else None,
            "delay_max_s": float(d.max()) if len(d) else None}


def summarise(name: str, design: str, window, ev, pred, alert_groups, inc_truth,
              first_alert: pd.Series, pred_source: str) -> dict:
    y = ev["label"].astype(str).to_numpy()
    r = R.evaluate_split(pd.Series(y), pd.Series(pred))
    alerted = pred != BENIGN
    lab_alerted = y[alerted] != BENIGN
    g = pd.Series(lab_alerted).groupby(alert_groups).any()
    n_alerts = int(len(g))
    false_alerts = int((~g).sum())
    inc = ev["incident_id"].astype(str).to_numpy()
    hit = pd.Series(alerted & (y != BENIGN)).groupby(inc).any()
    att = inc_truth["is_attack"]
    det = int(hit.reindex(att.index).fillna(False)[att].sum())
    n_att = int(att.sum())
    lag = first_alert.reindex(att.index[att]) - inc_truth.loc[att, "first_attack_ts"]
    return {"name": name, "design": design, "window_s": window, "predictions": pred_source,
            "n_alerts": n_alerts, "false_alarm_alerts": false_alerts,
            "false_alarm_share": false_alerts / n_alerts if n_alerts else None,
            "alerted_events": int(alerted.sum()),
            "attack_incidents": n_att, "attack_incidents_detected": det,
            "attack_incidents_missed": n_att - det,
            "accuracy": r["accuracy"], "f1_macro": r["f1_macro"], "fpr": r["fpr"], "fnr": r["fnr"],
            **delays(lag)}


def first_alert_event(ev, pred) -> pd.Series:
    """Per true incident: time of its first alerted attack event (A, C open)."""
    m = (pred != BENIGN) & (ev["label"].astype(str).to_numpy() != BENIGN)
    return ev.loc[m].groupby(ev.loc[m, "incident_id"].astype(str))["ts"].min().astype(float)


def first_alert_closed(ev, pred, gid) -> pd.Series:
    """Per true incident: earliest close time of an alert group holding one of its attack events."""
    m = pred != BENIGN
    sub = ev.loc[m, ["ts", "incident_id", "label"]].assign(g=gid)
    close = sub.groupby("g")["ts"].transform("max").astype(float)
    a = sub["label"].astype(str).to_numpy() != BENIGN
    return close[a].groupby(sub.loc[a, "incident_id"].astype(str)).min()


def event_designs(ev, pred, label, source, inc_truth, rows, keep) -> None:
    alerted = pred != BENIGN
    a_groups = np.arange(int(alerted.sum()))
    first = first_alert_event(ev, pred)
    rows.append(summarise(f"A_{label}", "A event alerts", None, ev, pred, a_groups,
                          inc_truth, first, source))
    for w in WINDOWS:
        gid = groups(ev, alerted, w)
        keep[f"C_{label}_w{w}"] = gid
        rows.append(summarise(f"C_{label}_w{w}_open", "C detect then correlate (open)", w, ev,
                              pred, gid, inc_truth, first, source))
        rows.append(summarise(f"C_{label}_w{w}_closed", "C detect then correlate (closed)", w,
                              ev, pred, gid, inc_truth, first_alert_closed(ev, pred, gid), source))


def main(argv=None) -> int:
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    log("loading Run B test events")
    ev = load_test_events()
    log(f"{len(ev):,} test events")
    inc_truth = truth(ev)
    frag = attach(ev, PRED / "fragmented_event_predictions.csv")
    integ = attach(ev, PRED / "integrated_event_predictions.csv")
    rows, keep = [], {}
    event_designs(ev, frag, "fragmented", "predictions/fragmented_event_predictions.csv",
                  inc_truth, rows, keep)
    # B: one alert per predicted-attack incident; incident prediction is propagated
    inc = ev["incident_id"].astype(str).to_numpy()
    inc_pred = pd.Series(integ).groupby(inc).agg(lambda s: s.iloc[0])
    consistent = bool((pd.Series(integ).groupby(inc).nunique() == 1).all())
    alerted = integ != BENIGN
    b_groups = pd.factorize(inc[alerted])[0]
    closed = inc_truth["last_ts"].where(inc_pred.reindex(inc_truth.index) != BENIGN)
    rows.append(summarise("B_integrated", "B incident alerts (closed)", 300, ev, integ, b_groups,
                          inc_truth, closed[closed.notna()], "predictions/integrated_event_predictions.csv"))
    extra = {}
    for name in ("event_only", "event_plus_thin"):
        p = attach_e1(ev, name)
        if p is not None:
            extra[name] = p
            event_designs(ev, p, f"ablation_{name}",
                          f"experiments/v4_extension/results/e1/preds/runb_w300_{name}_s42.parquet",
                          inc_truth, rows, keep)
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "alert_workload.csv", index=False)

    # checks: C uses A's event decisions, so event metrics must be equal
    chk = {"n_test": len(ev), "integrated_prediction_constant_within_incident": consistent,
           "true_incidents": int(len(inc_truth)), "attack_incidents": int(inc_truth["is_attack"].sum())}
    for lab in ["fragmented"] + [f"ablation_{n}" for n in extra]:
        a = res[res.name == f"A_{lab}"].iloc[0]
        c = res[res.name.str.startswith(f"C_{lab}_")]
        chk[f"C_equals_A_event_metrics_{lab}"] = bool(all(
            (c[m] == a[m]).all() for m in ("accuracy", "f1_macro", "fpr", "fnr")))
        chk[f"C_open_delay_equals_A_{lab}"] = bool(
            (c[c.name.str.endswith("_open")]["delay_median_s"] == a["delay_median_s"]).all())
    y = ev["label"].astype(str).to_numpy()
    sizes = ev.groupby("incident_id")["label"].transform("size").to_numpy()
    mb = (y == BENIGN) & (sizes > 1)
    chk["multi_event_benign_fpr"] = {
        "n_benign_in_multi_event_groups": int(mb.sum()),
        "integrated": float((integ[mb] != BENIGN).mean()),
        "fragmented": float((frag[mb] != BENIGN).mean())}
    chk["minutes"] = round((time.perf_counter() - t0) / 60, 1)
    (OUT / "checks.json").write_text(json.dumps(chk, indent=2), encoding="utf-8")
    # alert-group ids for every C variant, to recompute counts
    ids = pd.DataFrame({"event_id": ev["event_id"], "incident_id": ev["incident_id"].astype(str),
                        "label": y, "ts": ev["ts"].astype(float), "pred_fragmented": frag,
                        "pred_integrated": integ, **{f"pred_{k}": v for k, v in extra.items()}})
    ids.to_parquet(OUT / "e2_events.parquet")
    for k, gid in keep.items():
        lab = k.split("_w")[0][2:]
        pcol = "pred_fragmented" if lab == "fragmented" else f"pred_{lab.replace('ablation_', '')}"
        pd.DataFrame({"event_id": ev["event_id"].to_numpy()[ids[pcol].to_numpy() != BENIGN],
                      "group": gid}).to_parquet(OUT / f"groups_{k}.parquet")
    print(res[["name", "n_alerts", "false_alarm_alerts", "false_alarm_share",
               "attack_incidents_detected", "attack_incidents_missed", "f1_macro", "fpr",
               "delay_median_s", "delay_p90_s"]].to_string(index=False))
    print(json.dumps(chk, indent=2))
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
