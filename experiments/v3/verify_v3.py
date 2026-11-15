"""Independent verification of every v3 result (PLAN_V3.md §A, Verification).

Recomputes each metric from the saved predictions/probabilities with
scikit-learn only (not transfer_v3.score), recomputes the permutation p-values
with a separate implementation, re-hashes manifest outputs, and checks that
RF event_only / incident_only on runB reproduce the historical ablation.

    code/.venv/Scripts/python.exe -B experiments/v3/verify_v3.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, balanced_accuracy_score,
                             confusion_matrix, f1_score, matthews_corrcoef, roc_auc_score)

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "v2"))
from manifest import sha256  # noqa: E402

RES = HERE / "results"
OLD_ABL = HERE.parent / "ablation" / "results" / "full" / "ablation_results.csv"
TOL = 1e-9


def recompute(y, pred, P, classes, attack=None) -> dict:
    labels = sorted(set(y) | set(pred))
    ben, att = y == "benign", y != "benign"
    out = {"f1_macro": f1_score(y, pred, labels=labels, average="macro", zero_division=0),
           "fpr": float((pred[ben] != "benign").mean()) if ben.any() else None,
           "fnr": float((pred[att] == "benign").mean()) if att.any() else None,
           "f1_macro_present": f1_score(y, pred, labels=sorted(set(y)), average="macro", zero_division=0),
           "balanced_accuracy": balanced_accuracy_score(y, pred),
           "mcc": matthews_corrcoef(y, pred),
           "binary_f1": f1_score(att, pred != "benign", zero_division=0),
           "confusion_matrix": confusion_matrix(y, pred, labels=labels).tolist()}
    s = 1.0 - P[:, classes.index("benign")] if attack is None else attack
    both = att.any() and ben.any()
    out["pr_auc_binary"] = average_precision_score(att, s) if both else None
    out["roc_auc_binary"] = roc_auc_score(att, s) if both else None
    pres = sorted(set(y))
    out["pr_auc_macro_present"] = (float(np.mean([average_precision_score(y == c, P[:, classes.index(c)])
                                                  for c in pres])) if len(pres) >= 2 else None)
    return out


def same(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, list):
        return a == b
    return abs(float(a) - float(b)) <= TOL


def verify_design(d: Path) -> dict:
    m = json.loads((d / "metrics.json").read_text(encoding="utf-8"))
    rows = pd.read_parquet(d / "rows.parquet")
    y_all = rows["label"].astype(str).to_numpy()
    fold_all = rows["fold"].to_numpy()
    classes = m["classes"]
    bad, n = [], 0
    for key, per_fold in m["runs"].items():
        name, seed = key.split("|")
        f = pd.read_parquet(d / f"run_{name}_s{seed}.parquet")
        pred_all = f["pred"].astype(str).to_numpy()
        P_all = f[[f"p_{c}" for c in classes]].to_numpy("float64")
        A_all = f["attack_score"].to_numpy("float64") if "attack_score" in f else None
        for fold, rep in per_fold.items():
            k = fold_all == fold
            got = recompute(y_all[k], pred_all[k], P_all[k], classes, None if A_all is None else A_all[k])
            for metric, v in got.items():
                n += 1
                if not same(v, rep[metric]):
                    bad.append(f"{key} {fold} {metric}: {v} vs {rep[metric]}")
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8")) if (d / "manifest.json").exists() else None
    hashes = ({k: (d / k).exists() and sha256(d / k) == h for k, h in man["outputs"].items()}
              if man else {})
    return {"values_checked": n, "mismatches": bad, "manifest_present": man is not None,
            "manifest_hashes_ok": bool(hashes) and all(hashes.values())}


def _p_exact(d: np.ndarray) -> float:
    """Sign-flip p via the full {0,1}^n bit table (independent of stats_v3)."""
    d = np.asarray(d, float)
    if len(d) == 0 or np.all(d == 0):
        return 1.0
    bits = ((np.arange(2 ** len(d))[:, None] >> np.arange(len(d))) & 1)
    sums = np.abs(((1 - 2 * bits) * d).sum(axis=1))
    return float((sums >= abs(d.sum()) - 1e-12).mean())


def recheck_stats(st: dict, metrics: dict) -> list[str]:
    bad = []
    seeds = metrics["seeds"]
    for metric, rows in st["comparisons"].items():
        for r in rows:
            if "per_fold" in r:
                d = []
                for fold, v in r["per_fold"].items():
                    xs = [metrics["runs"][f"{r['x']}|{s}"][fold][metric] for s in seeds]
                    ys = [metrics["runs"][f"{r['y']}|{s}"][fold][metric] for s in seeds]
                    d.append(np.mean(xs) - np.mean(ys))
                    if abs(d[-1] - v) > 1e-6:
                        bad.append(f"{metric} {r['x']}-{r['y']} {fold}")
            else:
                d = [metrics["runs"][f"{r['x']}|{s}"]["runB"][metric]
                     - metrics["runs"][f"{r['y']}|{s}"]["runB"][metric] for s in seeds]
            if abs(_p_exact(np.array(d)) - r["p_sign_flip"]) > 1e-9:
                bad.append(f"p {metric} {r['x']}-{r['y']}")
    return bad


def crosslog(name: str) -> dict:
    """Binary macro F1, FPR and FNR of every (fold, condition, seed) from saved predictions."""
    d = json.loads((RES / "cross_log" / f"{name}.json").read_text(encoding="utf-8"))
    p = pd.read_parquet(RES / "cross_log" / f"{name}_predictions.parquet")
    blocks = ({"all": d["by_condition_seed"]} if "by_condition_seed" in d
              else {k: v["by_condition_seed"] for k, v in d["folds"].items()})
    bad, n = [], 0
    for fold, res in blocks.items():
        g = p if fold == "all" else p[p["capture"] == fold]
        y = g["y"].to_numpy()
        for c, by_seed in res.items():
            for s, m in by_seed.items():
                q = g[f"pred_{c}_s{s}"].to_numpy()
                got = {"macro_f1": f1_score(y, q, average="macro", labels=[0, 1], zero_division=0),
                       "fpr": float((q[y == 0] == 1).mean()) if (y == 0).any() else None,
                       "fnr": float((q[y == 1] == 0).mean()) if (y == 1).any() else None}
                for k, v in got.items():
                    n += 1
                    if not same(v, m[k]):
                        bad.append(f"{fold} {c} s{s} {k}")
    man = RES / "cross_log" / f"manifest_{name}.json"
    mm = json.loads(man.read_text(encoding="utf-8"))
    hashes = {k: sha256(man.parent / k) == h for k, h in mm["outputs"].items()}
    return {"values_checked": n, "mismatches": bad, "manifest_hashes_ok": all(hashes.values())}


def historical(d: Path) -> dict:
    if not OLD_ABL.exists():
        return {}
    m = json.loads((d / "metrics.json").read_text(encoding="utf-8"))
    old = pd.read_csv(OLD_ABL)
    old = old[old["subset"] == "all"]
    out = {}
    for name, fs, w in (("rf_event_only", "event_only", 0), ("rf_incident_only", "incident_only", 300),
                        ("rf_event_plus_incident", "event_plus_incident", 300)):
        for s in m["seeds"]:
            o = old[(old["feature_set"] == fs) & (old["window_s"] == w) & (old["seed"] == s)]
            new = m["runs"].get(f"{name}|{s}", {}).get("runB")
            if len(o) and new:
                out[f"{name}|{s}"] = abs(float(o["f1_macro"].iloc[0]) - new["f1_macro"]) < TOL
    return out


def main() -> None:
    out = {}
    tdir = RES / "transfer"
    st = json.loads((tdir / "stats.json").read_text(encoding="utf-8")) if (tdir / "stats.json").exists() else {}
    for design in ("runB", "loso"):
        d = tdir / design
        if not (d / "metrics.json").exists():
            continue
        v = verify_design(d)
        if design in st:
            v["stats_mismatches"] = recheck_stats(st[design], json.loads((d / "metrics.json").read_text()))
        if design == "runB":
            v["reproduces_historical_ablation"] = historical(d)
        out[f"transfer_{design}"] = v
    for name in ("primary_augmented", "loco"):
        if (RES / "cross_log" / f"{name}.json").exists():
            out[f"cross_log_{name}"] = crosslog(name)
    ok = True
    for v in out.values():
        ok &= not v["mismatches"] and not v.get("stats_mismatches")
        ok &= v.get("manifest_hashes_ok", v.get("manifest", {}).get("all", False))
        ok &= all(v.get("reproduces_historical_ablation", {}).values())
    out["all_ok"] = bool(ok)
    (RES / "verification.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: (v if k == "all_ok" else {kk: (len(vv) if isinstance(vv, list) else vv)
                                                     for kk, vv in v.items() if kk != "per_fold"})
                      for k, v in out.items()}, indent=1, default=str)[:4000])


if __name__ == "__main__":
    warnings.simplefilter("ignore")
    main()
