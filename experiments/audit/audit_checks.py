"""Read-only audit checks (2026-11-03). Trains nothing; writes audit_checks.json.

1. Metrics recomputed from saved predictions (Run B, Run T, cross-log) vs reports.
2. Cross-log: thesis classes in each seed's training sample (experiment.train_sample).
3. Run B: share of per-source models whose top-4 features include ``sport``.

Run from the repository root:
    code/.venv/Scripts/python.exe -B experiments/audit/audit_checks.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parents[2]
RUN_T = ROOT.parent / "thesis_final_validation" / "supplementary_temporal" / "code" / "results"
OUT = Path(__file__).with_name("audit_checks.json")
sys.dont_write_bytecode = True


def recompute_runs() -> dict:
    out = {}
    for name, pred_dir, report in (
            ("run_B", ROOT / "predictions", ROOT / "metrics" / "stage5_report.json"),
            ("run_T", RUN_T, RUN_T / "stage5_report.json")):
        if not report.exists():
            out[name] = "report not found"
            continue
        r = json.loads(report.read_text(encoding="utf-8"))
        res = {}
        for cond in ("fragmented", "integrated"):
            df = pd.read_csv(pred_dir / f"{cond}_event_predictions.csv")
            y, p = df["label"].astype(str), df["pred"].astype(str)
            labels = sorted(set(y) | set(p))
            ben = y == "benign"
            got = {"f1_macro": f1_score(y, p, labels=labels, average="macro", zero_division=0),
                   "fpr": float(((p != "benign") & ben).sum() / ben.sum()),
                   "fnr": float(((p == "benign") & ~ben).sum() / (~ben).sum())}
            res[cond] = {
                "n": int(len(df)),
                **{k: {"recomputed": round(v, 6), "reported": round(r[cond][k], 6),
                       "equal": abs(v - r[cond][k]) < 1e-9} for k, v in got.items()},
                "confusion_matrix_equal": confusion_matrix(
                    y, p, labels=r[cond]["classes"]).tolist() == r[cond]["confusion_matrix"]}
        out[name] = res
    return out


def recompute_crosslog() -> dict:
    res_dir = ROOT / "experiments" / "cross_log" / "results"
    p = pd.read_parquet(res_dir / "stage4_predictions.parquet")
    r = json.loads((res_dir / "stage4_results.json").read_text(encoding="utf-8"))
    out = {}
    for c in "ABCD":
        for s in (42, 1, 2, 3, 4):
            f1 = f1_score(p["y"], p[f"pred_{c}_s{s}"], average="macro", labels=[0, 1],
                          zero_division=0)
            rep = r["conditions"][c]["by_seed"][str(s)]["macro_f1"]
            out[f"{c}_s{s}"] = abs(f1 - rep) < 1e-9
    return {"all_equal": all(out.values()), "n_checked": len(out)}


def crosslog_sample_composition() -> dict:
    src = ROOT / "experiments" / "cross_log" / "src"
    sys.path.insert(0, str(src))
    sys.argv = ["audit"]
    import robustness as R  # noqa: E402
    from experiment import train_sample  # noqa: E402
    pre = "CTU-IoT-Malware-Capture-"
    tr = R.split([pre + c for c in ("1-1", "3-1", "20-1", "42-1")],
                 [pre + c for c in ("8-1", "21-1", "34-1")])[0]
    return {"train_rows_by_class": tr["cls"].value_counts().to_dict(),
            "sample_by_seed": {s: train_sample(tr, s)["cls"].value_counts().to_dict()
                               for s in [42, 1, 2, 3, 4] + list(range(5, 20))}}


def sport_importance() -> dict:
    r = json.loads((ROOT / "metrics" / "stage5_report.json").read_text(encoding="utf-8"))
    out = {}
    for src, v in r["fragmented"]["per_source"].items():
        top = v.get("top_features", [])
        out[src] = {t["feature"]: round(t["importance"], 3) for t in top[:4]}
    return {"top4_per_source": out,
            "sources_with_sport_in_top4": sorted(s for s, t in out.items() if "sport" in t)}


def main() -> None:
    out = {"run_metrics_recomputed": recompute_runs(),
           "crosslog_metrics_recomputed": recompute_crosslog(),
           "crosslog_train_sample": crosslog_sample_composition(),
           "runB_sport_importance": sport_importance()}
    OUT.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps(out, indent=2, default=str)[:4000])


if __name__ == "__main__":
    main()
