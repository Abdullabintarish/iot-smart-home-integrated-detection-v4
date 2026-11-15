"""Read-only re-tabulation of the saved cross-log predictions (no training).

Reads   experiments/cross_log/results/stage4_predictions.parquet
        experiments/cross_log/results/stage3_<capture>.json
        experiments/cross_log/results/robustness/R3_leave_one_capture_out.json
        experiments/cross_log/results/robust_cache/CTU-IoT-Malware-Capture-8-1.parquet
Writes  thesis_writing_package/evidence/crosslog_breakdown.json

Run from the repository root:
    code/demo/.venv/Scripts/python.exe -B thesis_writing_package/evidence/crosslog_breakdown.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "experiments" / "cross_log" / "results"
OUT = Path(__file__).with_name("crosslog_breakdown.json")
SEEDS = [42, 1, 2, 3, 4]
CONDS = "ABCD"
PREFIX = "CTU-IoT-Malware-Capture-"


def mean_f1(df: pd.DataFrame, cond: str) -> float:
    return round(sum(f1_score(df.y, df[f"pred_{cond}_s{s}"], average="macro")
                     for s in SEEDS) / len(SEEDS), 4)


def main() -> None:
    p = pd.read_parquet(RES / "stage4_predictions.parquet")
    p["cap"] = p.capture.str.replace(PREFIX, "", regex=False)
    out: dict = {}

    # Trivial reference: every test row predicted benign.
    n_b, n_a = int((p.y == 0).sum()), int((p.y == 1).sum())
    out["all_benign_macro_f1"] = round((2 * n_b / (2 * n_b + n_a)) / 2, 4)

    out["test_rows_by_capture_class"] = {
        f"{c}|{k}": int(v) for (c, k), v in p.groupby(["cap", "cls"]).size().items()}

    out["detection_rate_by_capture_class_mean_5_seeds"] = {
        f"{c}|{k}": {cond: round(sum(g[f"pred_{cond}_s{s}"].mean() for s in SEEDS) / 5, 4)
                     for cond in CONDS}
        for (c, k), g in p.groupby(["cap", "cls"])}

    out["c2_detection_by_seed"] = {
        cap: {cond: [round(float(g[f"pred_{cond}_s{s}"].mean()), 4) for s in SEEDS]
              for cond in CONDS}
        for cap, g in p[p.cls == "c2"].groupby("cap")}

    out["macro_f1_mean_5_seeds"] = {
        "all_test_captures": {c: mean_f1(p, c) for c in CONDS},
        "without_8-1": {c: mean_f1(p[p.cap != "8-1"], c) for c in CONDS},
        "8-1_only": {c: mean_f1(p[p.cap == "8-1"], c) for c in CONDS},
    }

    # Context records available per capture (from Stage 3).
    ctx = {}
    for f in sorted(RES.glob("stage3_*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        r = d["linking"]["records"]
        ctx[d["capture"].replace(PREFIX, "")] = {"dns": r["dns"], "alert": r["alert"]}
    out["context_records_by_capture"] = ctx

    cache = pd.read_parquet(RES / "robust_cache" / f"{PREFIX}8-1.parquet")
    cols = [c for c in cache.columns if c.startswith("start_300|")]
    out["8-1_nonzero_context_values"] = int((cache[cols].fillna(0) != 0).to_numpy().sum())

    # Leave-one-capture-out: mean macro F1 per fold and per condition.
    r3 = json.loads((RES / "robustness" / "R3_leave_one_capture_out.json").read_text())
    folds = {}
    for cap, f in r3["folds"].items():
        b = f["by_condition_seed"]
        m = {c: round(sum(v["macro_f1"] for v in b[c].values()) / len(b[c]), 4) for c in CONDS}
        short = cap.replace(PREFIX, "")
        folds[short] = {"n_test": f["n_test"], **m,
                        "B-A": round(m["B"] - m["A"], 4), "C-A": round(m["C"] - m["A"], 4),
                        "D-A": round(m["D"] - m["A"], 4),
                        "test_dns": ctx.get(short, {}).get("dns"),
                        "test_alerts": ctx.get(short, {}).get("alert")}
    out["r3_folds"] = folds

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
