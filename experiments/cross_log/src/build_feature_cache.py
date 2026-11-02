"""Precompute per-capture feature tables for the robustness analyses.

For every capture with Stage 3 output, writes results/robust_cache/<capture>.parquet
with one row per label-matched Zeek conn record:

  conn features (condition A), identifiers (capture, incident_id, cls, y), and
  DNS / alert window features for each variant
      <anchor>_<window>   anchor in {start, end}, window in {60, 300, 900}
  "start_300" is the pre-registered definition (PLAN.md section 4). "end" uses
  the connection's end time (ts + duration), when Zeek writes the record.

Alert features are stored per category for ALL categories seen in any capture
(column ``<variant>|alert_cat|<category>``); each analysis then keeps the
top-10 categories of its own training captures and sums the rest into
"other", which reproduces the primary definition fold by fold. Alert counts
per capture and category go to results/robust_cache/alert_categories.json.

    python build_feature_cache.py [capture ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import common  # noqa: F401
from features import alert_features, conn_frame, dns_features
from zeek_io import read_eve, read_zeek_tsv

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "results" / "robust_cache"
VARIANTS = [("start", 300), ("end", 300), ("start", 60), ("start", 900)]


def captures() -> list[str]:
    return sorted(p.stem.replace("stage3_", "") for p in
                  (ROOT / "results").glob("stage3_CTU-*.json"))


def all_alerts(caps: list[str]) -> dict[str, pd.DataFrame]:
    return {c: read_eve(ROOT / "sensor_out" / c / "suricata" / "eve.json",
                        event_types=("alert",)) for c in caps}


def build(capture: str, alerts: pd.DataFrame, cats: list[str]) -> pd.DataFrame:
    res = ROOT / "results"
    full = pd.read_parquet(res / f"conn_labelled_{capture}.parquet")
    rec = pd.read_parquet(res / f"records_linked_{capture}.parquet",
                          columns=["rtype", "incident_id"])
    full["incident_id"] = rec.loc[rec["rtype"] == "conn", "incident_id"].to_numpy()
    conn = full[full["label_matched"]].reset_index(drop=True)
    dns_p = ROOT / "sensor_out" / capture / "zeek" / "dns.log"
    dns = read_zeek_tsv(dns_p) if dns_p.exists() else None

    t = conn_frame(conn)
    start = conn["ts"].astype(float)
    dur = pd.to_numeric(conn["duration"].replace("-", np.nan), errors="coerce").fillna(0.0)
    for anchor, w in VARIANTS:
        q = conn.copy()
        q["ts"] = start if anchor == "start" else start + dur
        v = f"{anchor}_{w}"
        d = dns_features(q, dns, w).add_prefix(f"{v}|")
        a = alert_features(q, alerts, cats, w)
        a.columns = ([f"{v}|alert_count", f"{v}|alert_max_severity"]
                     + [f"{v}|alert_cat|{c}" for c in cats] + [f"{v}|alert_cat|__none__"])
        t = t.join(d).join(a)
    t["capture"] = capture
    t["incident_id"] = capture + "|" + conn["incident_id"].astype(str)
    t["cls"] = conn["cls"].to_numpy()
    t["y"] = (t["cls"] != "benign").astype("int8")
    return t


def main(argv: list[str]) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    caps = argv or captures()
    every = captures()
    alerts = all_alerts(every)
    cats = sorted({c for a in alerts.values() if len(a) for c in a["category"].fillna("none")})
    counts = {c: (a["category"].fillna("none").value_counts().to_dict() if len(a) else {})
              for c, a in alerts.items()}
    (CACHE / "alert_categories.json").write_text(
        json.dumps({"categories": cats, "counts_by_capture": counts}, indent=2))
    for c in caps:
        t = build(c, alerts[c], cats)
        t.to_parquet(CACHE / f"{c}.parquet")
        print(c, len(t), t.shape[1], flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
