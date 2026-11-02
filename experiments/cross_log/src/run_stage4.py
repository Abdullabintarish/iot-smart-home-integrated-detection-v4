"""Stage 4: conditions A-D on the pre-registered capture split (PLAN.md).

    python run_stage4.py

Needs run_stage3.py output for every capture in TRAIN + TEST. Writes
results/stage4_results.json, results/stage4_bootstrap.json and
results/stage4_predictions.parquet. The split below is fixed in PLAN.md and
must not be changed after results are seen.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import common  # noqa: F401
from experiment import SEEDS, cluster_bootstrap, run
from features import (alert_categories, alert_columns, alert_features,
                      conn_frame, dns_features)
from zeek_io import read_eve, read_zeek_tsv

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ["CTU-IoT-Malware-Capture-1-1", "CTU-IoT-Malware-Capture-3-1",
         "CTU-IoT-Malware-Capture-20-1", "CTU-IoT-Malware-Capture-42-1"]
TEST = ["CTU-IoT-Malware-Capture-8-1", "CTU-IoT-Malware-Capture-21-1",
        "CTU-IoT-Malware-Capture-34-1"]


def capture_table(capture: str, categories: list[str]) -> pd.DataFrame:
    res = ROOT / "results"
    conn = pd.read_parquet(res / f"conn_labelled_{capture}.parquet")
    conn = conn[conn["label_matched"]].reset_index(drop=True)
    rec = pd.read_parquet(res / f"records_linked_{capture}.parquet")
    inc = rec[rec["rtype"] == "conn"]["incident_id"].to_numpy()
    so = ROOT / "sensor_out" / capture
    dns_p = so / "zeek" / "dns.log"
    dns = read_zeek_tsv(dns_p) if dns_p.exists() else None
    alerts = read_eve(so / "suricata" / "eve.json", event_types=("alert",))
    full = pd.read_parquet(res / f"conn_labelled_{capture}.parquet")
    inc_by_uid = dict(zip(full["uid"], inc))
    t = conn_frame(conn)
    t = t.join(dns_features(conn, dns)).join(alert_features(conn, alerts, categories))
    t["incident_id"] = capture + "|" + conn["uid"].map(inc_by_uid)
    t["capture"] = capture
    t["cls"] = conn["cls"].to_numpy()
    t["y"] = (t["cls"] != "benign").astype(int)
    return t


def main() -> None:
    train_alerts = pd.concat([read_eve(ROOT / "sensor_out" / c / "suricata" / "eve.json",
                                       event_types=("alert",)) for c in TRAIN])
    cats = alert_categories(train_alerts)
    train = pd.concat([capture_table(c, cats) for c in TRAIN], ignore_index=True)
    test = pd.concat([capture_table(c, cats) for c in TEST], ignore_index=True)
    assert not set(train["incident_id"]) & set(test["incident_id"])
    results, preds = run(train, test, alert_columns(cats), seeds=SEEDS)
    results["split"] = {"train": TRAIN, "test": TEST,
                        "train_rows": int(len(train)), "test_rows": int(len(test)),
                        "train_class_counts": train["cls"].value_counts().to_dict(),
                        "test_class_counts": test["cls"].value_counts().to_dict()}
    results["alert_categories_from_train"] = cats
    out = ROOT / "results"
    (out / "stage4_results.json").write_text(json.dumps(results, indent=2))
    preds.to_parquet(out / "stage4_predictions.parquet")
    bs = cluster_bootstrap(preds)
    (out / "stage4_bootstrap.json").write_text(json.dumps(bs, indent=2))
    for c, r in results["conditions"].items():
        print(c, round(r["macro_f1_mean"], 4), round(r["macro_f1_sd"], 4))


if __name__ == "__main__":
    main()
