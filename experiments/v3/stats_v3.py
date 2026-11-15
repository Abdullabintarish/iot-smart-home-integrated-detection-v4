"""Pre-registered paired tests for the v3 transfer study (PLAN_V3.md §A, Statistics).

    code/.venv/Scripts/python.exe -B experiments/v3/stats_v3.py

Reads results/transfer/<design>/metrics.json (+ rows/run files for the runB
bootstrap) and writes results/transfer/stats.json.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
OUT = HERE / "results" / "transfer"
METRICS = ("f1_macro", "f1_macro_present", "pr_auc_binary", "fpr")


def comparisons(frag: str) -> list[tuple[str, str]]:
    return [(frag, "rf_event_only"), ("rf_incident_only", frag),
            ("rf_incident_only", "rf_event_only"), ("rf_event_plus_incident", "rf_event_only"),
            ("hgb_incident_only", "hgb_event_only"), ("hgb_event_plus_incident", "hgb_event_only"),
            ("lr_incident_only", "lr_event_only"), ("lr_event_plus_incident", "lr_event_only")]


def sign_flip_p(d: np.ndarray) -> float:
    """Exact two-sided paired sign-flip permutation p-value for mean(d) = 0."""
    d = np.asarray(d, float)
    if len(d) == 0 or np.all(d == 0):
        return 1.0
    obs = abs(d.sum())
    stats = [abs(np.dot(s, d)) for s in itertools.product((1.0, -1.0), repeat=len(d))]
    return float(np.mean(np.array(stats) >= obs - 1e-12))


def holm(ps: list[float]) -> list[float]:
    m = len(ps)
    order = np.argsort(ps)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * ps[i]))
        adj[i] = running
    return adj.tolist()


def fold_means(metrics: dict, name: str, metric: str) -> dict[str, float | None]:
    out = {}
    for fold in metrics["folds"]:
        vals = [metrics["runs"][f"{name}|{s}"][fold][metric] for s in metrics["seeds"]]
        out[fold] = None if any(v is None for v in vals) else float(np.mean(vals))
    return out


def _wilcoxon(d):
    if len(d) == 0 or np.all(d == 0):
        return None
    return float(wilcoxon(d).pvalue)


def loso_tests(metrics: dict) -> dict:
    res = {"unit": "held-out source (seed-mean)", "comparisons": {}}
    comps = comparisons("frag_soft")
    for metric in METRICS:
        rows = []
        for x, y in comps:
            fx, fy = fold_means(metrics, x, metric), fold_means(metrics, y, metric)
            folds = [f for f in fx if fx[f] is not None and fy[f] is not None]
            d = np.array([fx[f] - fy[f] for f in folds])
            rows.append({"x": x, "y": y, "n": len(d), "mean_diff": float(d.mean()) if len(d) else None,
                         "median_diff": float(np.median(d)) if len(d) else None,
                         "folds_positive": int((d > 0).sum()), "folds_negative": int((d < 0).sum()),
                         "per_fold": dict(zip(folds, d.round(6).tolist())),
                         "p_sign_flip": sign_flip_p(d), "p_wilcoxon": _wilcoxon(d)})
        for r, a in zip(rows, holm([r["p_sign_flip"] for r in rows])):
            r["p_sign_flip_holm"] = a
        res["comparisons"][metric] = rows
    return res


def runb_tests(metrics: dict, design_dir: Path, reps: int = 1000) -> dict:
    sys.path.insert(0, str(HERE.parents[0] / "ablation"))
    sys.path.insert(0, str(HERE.parents[1] / "code"))
    import run_ablation as A  # noqa: E402
    res = {"unit": "seed (n=5; smallest two-sided p = 0.0625)", "comparisons": {}}
    comps = comparisons("frag")
    for metric in METRICS:
        rows = []
        for x, y in comps:
            d = np.array([metrics["runs"][f"{x}|{s}"]["runB"][metric]
                          - metrics["runs"][f"{y}|{s}"]["runB"][metric] for s in metrics["seeds"]])
            rows.append({"x": x, "y": y, "n": len(d), "mean_diff": float(d.mean()),
                         "per_seed": d.round(6).tolist(), "seeds_positive": int((d > 0).sum()),
                         "seeds_negative": int((d < 0).sum()), "p_sign_flip": sign_flip_p(d)})
        for r, a in zip(rows, holm([r["p_sign_flip"] for r in rows])):
            r["p_sign_flip_holm"] = a
        res["comparisons"][metric] = rows
    rows = pd.read_parquet(design_dir / "rows.parquet")
    y = rows["label"].astype(str).to_numpy()
    seed = metrics["seeds"][0]
    boot = {}
    for x, z in comps:
        a = pd.read_parquet(design_dir / f"run_{x}_s{seed}.parquet", columns=["pred"])["pred"].astype(str).to_numpy()
        b = pd.read_parquet(design_dir / f"run_{z}_s{seed}.parquet", columns=["pred"])["pred"].astype(str).to_numpy()
        boot[f"{x}_minus_{z}"] = A.paired_bootstrap(y, a, b, rows["incident_id"].to_numpy(),
                                                    sorted(set(y)), reps, seed)
    res["incident_bootstrap_seed42"] = boot
    return res


def main() -> None:
    out = {}
    for design, fn in (("runB", None), ("loso", None)):
        p = OUT / design / "metrics.json"
        if not p.exists():
            continue
        m = json.loads(p.read_text(encoding="utf-8"))
        out[design] = runb_tests(m, OUT / design) if design == "runB" else loso_tests(m)
    (OUT / "stats.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", OUT / "stats.json")


if __name__ == "__main__":
    main()
