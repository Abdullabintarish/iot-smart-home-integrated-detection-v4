"""E3 explanatory diagnostics (written after the main run; changes no result).

Describes the data structure behind three E3 results: why B rarely prevents
under P1, why host quarantine blocks most benign events even for the oracle,
and how much of B's P2 shortfall is DoS volume inside the first incident.
Labels are used here only to describe the data.

    PYTHONPATH=code code/.venv/Scripts/python.exe -B experiments/v4_extension/e3/diagnostics.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_response_sim as S  # noqa: E402


def main() -> int:
    ev = S.load()
    att = ev["label"].to_numpy() != S.BENIGN
    flow = S.key_codes(ev, S.POLICIES["P1_flow"])
    host = S.key_codes(ev, S.POLICIES["P2_host"])
    inc = ev["incident_id"].to_numpy()
    out = {}
    inc_per_flow = pd.Series(inc).groupby(flow).nunique()
    out["flows"] = int(len(inc_per_flow))
    out["flows_with_one_incident"] = int((inc_per_flow == 1).sum())
    one = inc_per_flow.reindex(flow).to_numpy() == 1
    out["attack_events_in_single_incident_flows_share"] = float(one[att].mean())
    host_att = pd.Series(att).groupby(host).any()
    ben_host_has_att = host_att.reindex(host).to_numpy()[~att]
    out["benign_events"] = int((~att).sum())
    out["benign_events_from_hosts_with_attacks_share"] = float(ben_host_has_att.mean())
    out["hosts"] = int(host.max() + 1)
    out["hosts_with_attacks"] = int(host_att.sum())
    out["benign_events_per_source"] = ev.loc[~att, "source"].value_counts().to_dict()
    # B under P2: attack events before the first B alert on their host
    b = S.incident_trigger(inc, ev["pred_integrated"].to_numpy())
    first_b = pd.Series(ev["ts"].to_numpy()[b]).groupby(host[b]).min()
    fb = first_b.reindex(host).to_numpy()
    y = ev["label"].to_numpy()
    pos = np.arange(len(ev))
    first_b_pos = pd.Series(b).groupby(host[b]).min().reindex(host).to_numpy()
    before = np.isnan(first_b_pos) | (pos <= np.nan_to_num(first_b_pos, nan=np.inf))
    out["B_P2_attack_events_at_or_before_first_B_alert_on_host_share"] = float(before[att].mean())
    out["B_P2_dos_events_at_or_before_first_B_alert_on_host_share"] = float(before[y == "dos"].mean())
    sizes = pd.Series(inc).groupby(inc).size()
    dos_inc = pd.Series(y == "dos").groupby(inc).any()
    s = sizes[dos_inc]
    out["dos_incidents"] = int(len(s))
    out["dos_incident_size_median"] = float(s.median())
    out["dos_incident_size_max"] = int(s.max())
    out["dos_events_in_incidents_over_1000_events_share"] = float(s[s > 1000].sum() / s.sum())
    span = ev.groupby("incident_id")["ts"].agg(lambda t: t.max() - t.min())
    out["dos_incident_span_median_s"] = float(span[dos_inc[dos_inc].index].median())
    del fb
    p = Path(__file__).resolve().parent / "results" / "diagnostics.json"
    p.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
