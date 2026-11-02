"""Controlled feature ablation for the thesis (run after the main pipeline).

Question: with everything else held constant, what does incident context
change? Every feature set uses the same pooled Random Forest settings, the
same sampled training events (per seed) and the same held-out test events.
Only the input features change.

Reads   data/processed/stage3_events/*.parquet, stage2_feature_plan.csv
Writes  results_ablation/ (run_all deletes results/, so it is kept apart)
Never   retrains or changes Run B. Nothing in results/ or models/ is touched.

    .venv\\Scripts\\python.exe run_ablation.py
    .venv\\Scripts\\python.exe run_ablation.py --seeds 42 --windows 300   (quick)

Feature sets
  event_only              the 20 Run B event features
  incident_only           n_events, span_s, events_per_s
  event_plus_incident     both
  shared_event            event features present in both datasets
  shared_plus_incident    shared_event plus the incident features
The two shared_* sets remove the dataset fingerprint in missing values.

Windows. Test events stay fixed, so incidents are built inside each partition.
Windows that divide 300 s exactly (60, 150, 300) nest inside the Run B split
and are not cut. Longer windows (600, 900) are cut at the partition boundary,
so their incident features are incomplete; these rows carry window_cut = True
and must be reported with that caveat.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.ensemble import RandomForestClassifier

from pipeline import config as C
from pipeline.correlate import correlation_key
from pipeline.detect import (CLASS_WEIGHT, MIN_SAMPLES_LEAF, NON_FEATURES,
                             _row_hash, event_features, evaluate_split)

INCIDENT = ["n_events", "span_s", "events_per_s"]
RUN_B_WINDOW = 300
LARGE_GROUP = 10_000
METRICS = ("accuracy", "precision_macro", "recall_macro", "f1_macro", "fpr", "fnr")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_events(path: Path, features: list[str]) -> pd.DataFrame:
    want = list(dict.fromkeys(list(features) + [
        "event_id", "ts", "src_ip", "dst_ip", "proto", "source", "incident_id",
        "split", "label"]))
    files = sorted(Path(path).glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"no parquet files in {path}; run the pipeline first")
    parts = []
    for f in files:
        have = set(pq.ParquetFile(f).schema_arrow.names)
        missing = [c for c in want if c not in have and c != "event_id"]
        if missing:
            raise KeyError(f"{f.name} lacks required columns: {missing}")
        parts.append(pd.read_parquet(f, columns=[c for c in want if c in have]))
    df = pd.concat(parts, ignore_index=True)
    if "event_id" not in df.columns:
        df["event_id"] = np.arange(len(df))
    df[features] = df[features].astype("float64").replace(
        [np.inf, -np.inf], np.nan).fillna(0.0).astype("float32")
    return df


def incident_context(df: pd.DataFrame, window_s: int) -> pd.DataFrame:
    """n_events, span_s, events_per_s per event, using the pipeline's own key.

    The split is part of the group, so no group crosses train and test. Each
    partition's features use that partition's events only.
    """
    key, _, _ = correlation_key(df, window_s=window_s)
    key = key.astype("string") + "|" + df["split"].astype("string")
    codes, uniques = pd.factorize(key)
    codes = codes.astype("int64")
    lonely = codes < 0                      # uncorrelatable events stay alone
    codes[lonely] = len(uniques) + np.arange(lonely.sum())
    ts = pd.to_numeric(df["ts"], errors="coerce").to_numpy(dtype="float64")
    g = pd.DataFrame({"g": codes, "ts": ts}).groupby("g", sort=False)["ts"]
    stats = pd.DataFrame({"n": g.size(), "lo": g.min(), "hi": g.max()})
    span = (stats["hi"] - stats["lo"]).fillna(0.0).clip(lower=0.0)
    rate = (stats["n"] / span.where(span > 0, 1.0)).where(span > 0, 0.0)
    out = pd.DataFrame({
        "n_events": stats["n"].reindex(codes).to_numpy(dtype="float32"),
        "span_s": span.reindex(codes).to_numpy(dtype="float32"),
        "events_per_s": rate.reindex(codes).to_numpy(dtype="float32"),
    }, index=df.index)
    out.attrs["n_groups"] = int(len(stats))
    return out


def shared_features(df: pd.DataFrame, features: list[str]) -> list[str]:
    """Event features not wholly missing in either dataset."""
    bot = df["source"].astype(str).str.startswith("data_").to_numpy()
    keep = []
    for f in features:
        missing = (df[f].to_numpy() == C.MISSING_SENTINEL)
        if (not bot.any() or missing[bot].mean() < 0.99) and \
           (not (~bot).any() or missing[~bot].mean() < 0.99):
            keep.append(f)
    return keep


def sample_train(train_idx: np.ndarray, labels: np.ndarray, per_class: int,
                 seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    parts = []
    for c in np.unique(labels[train_idx]):
        idx = train_idx[labels[train_idx] == c]
        parts.append(rng.choice(idx, size=min(per_class, len(idx)), replace=False))
    return np.sort(np.concatenate(parts))


def fit_predict(X: pd.DataFrame, y: np.ndarray, train: np.ndarray,
                test: np.ndarray, seed: int, n_trees: int, n_jobs: int
                ) -> tuple[np.ndarray, list]:
    rf = RandomForestClassifier(
        n_estimators=n_trees, max_depth=C.MAX_TREE_DEPTH,
        min_samples_leaf=MIN_SAMPLES_LEAF, class_weight=CLASS_WEIGHT,
        bootstrap=True, n_jobs=n_jobs, random_state=seed)
    rf.fit(X.iloc[train], y[train])
    return rf.predict(X.iloc[test]), rf.feature_importances_.tolist()


def score(y: np.ndarray, p: np.ndarray, masks: dict[str, np.ndarray]) -> list[dict]:
    rows = []
    for name, m in masks.items():
        if not m.any():
            continue
        r = evaluate_split(pd.Series(y[m]), pd.Series(p[m]))
        rows.append({"subset": name, "n": int(m.sum()),
                     **{k: r[k] for k in METRICS}})
    return rows


def paired_bootstrap(y, a, b, clusters, labels, reps, seed) -> dict:
    """Incident-clustered interval for metric(a) - metric(b)."""
    ix = {c: i for i, c in enumerate(labels)}
    k = len(labels)
    t = np.array([ix[v] for v in y])
    inc, uniq = pd.factorize(clusters)

    def sparse(pred):
        q = np.array([ix[v] for v in pred])
        v, n = np.unique(inc.astype("int64") * k * k + t * k + q, return_counts=True)
        return v // (k * k), (v % (k * k)) // k, v % k, n

    def metric(s, w):
        cm = np.zeros((k, k))
        np.add.at(cm, (s[1], s[2]), w[s[0]] * s[3])
        tp = np.diag(cm)
        pr = np.divide(tp, cm.sum(0), out=np.zeros(k), where=cm.sum(0) > 0)
        rc = np.divide(tp, cm.sum(1), out=np.zeros(k), where=cm.sum(1) > 0)
        f = np.divide(2 * pr * rc, pr + rc, out=np.zeros(k), where=pr + rc > 0)
        b_i = ix.get("benign")
        fpr = (cm[b_i].sum() - cm[b_i, b_i]) / cm[b_i].sum() if cm[b_i].sum() else np.nan
        return f.mean(), fpr

    sa, sb = sparse(a), sparse(b)
    rng = np.random.default_rng(seed)
    d = []
    for _ in range(reps):
        w = np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq))
        ma, mb = metric(sa, w), metric(sb, w)
        d.append((ma[0] - mb[0], ma[1] - mb[1]))
    d = np.array(d)
    q = lambda c: [float(np.nanpercentile(d[:, c], 2.5)),
                   float(np.nanpercentile(d[:, c], 97.5))]
    return {"f1_macro_diff": q(0), "fpr_diff": q(1), "n_boot": reps}


def markdown(summary: pd.DataFrame) -> str:
    s = summary[summary["subset"] == "all"]
    lines = ["| Window (s) | Feature set | Runs | Macro F1 (mean ± SD) | FPR (mean ± SD) | Cut |",
             "|---|---|---|---|---|---|"]
    for r in s.itertuples():
        win = "n/a" if r.window_s == 0 else r.window_s
        lines.append(f"| {win} | {r.feature_set} | {r.runs} | {r.f1_mean:.4f} ± "
                     f"{r.f1_sd:.4f} | {r.fpr_mean:.2%} ± {r.fpr_sd:.2%} | "
                     f"{'yes' if r.window_cut else 'no'} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", type=Path, default=C.DATA_OUT / "stage3_events")
    ap.add_argument("--plan", type=Path, default=C.DATA_OUT / "stage2_feature_plan.csv")
    ap.add_argument("--out", type=Path, default=C.ROOT / "results_ablation")
    ap.add_argument("--windows", type=int, nargs="+", default=[60, 150, 300, 600, 900])
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 1, 2, 3, 4])
    ap.add_argument("--trees", type=int, default=C.N_ESTIMATORS)
    ap.add_argument("--per-class", type=int, default=C.BUDGET.train_budget_per_class)
    ap.add_argument("--n-jobs", type=int, default=C.BUDGET.n_jobs)
    ap.add_argument("--bootstrap", type=int, default=1000)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    feats = event_features(a.plan)
    if set(feats) & set(NON_FEATURES):
        raise ValueError("identifier in feature list")
    log(f"loading events ({len(feats)} event features)")
    df = load_events(a.events, feats)
    y = df["label"].astype(str).to_numpy()
    split = df["split"].astype(str).to_numpy()
    train_all, test = np.flatnonzero(split == "train"), np.flatnonzero(split == "test")
    if not len(train_all) or not len(test):
        raise ValueError("train or test partition is empty")
    log(f"{len(df):,} events: {len(train_all):,} train, {len(test):,} test")

    shared = shared_features(df, feats)
    log(f"shared features ({len(shared)}): {', '.join(shared)}")
    dup = np.isin(_row_hash(df.iloc[test], feats), _row_hash(df.iloc[train_all], feats))
    y_test = y[test]
    benign = y_test == "benign"
    run_b_sizes = df.iloc[test].groupby("incident_id")["label"].transform("size").to_numpy()

    sets = {"event_only": feats, "shared_event": shared}          # window-free
    ctx_sets = {"incident_only": [], "event_plus_incident": feats,
                "shared_plus_incident": shared}
    checks = {"n_events": len(df), "n_test": len(test), "n_novel": int((~dup).sum()),
              "event_features": feats, "shared_features": shared}
    rows, preds = [], {}

    def run(name, X, window, seed, sample, group_sizes):
        cols = list(X.columns)
        t = time.perf_counter()
        p, imp = fit_predict(X, y, sample, test, seed, a.trees, a.n_jobs)
        masks = {"all": np.ones(len(test), bool), "novel_vector": ~dup,
                 f"groups_le_{LARGE_GROUP}": group_sizes <= LARGE_GROUP,
                 "multi_event_benign": benign & (group_sizes > 1),
                 "single_event_benign": benign & (group_sizes == 1)}
        for r in score(y_test, p, masks):
            rows.append({"window_s": window, "seed": seed, "feature_set": name,
                         "n_features": len(cols), "n_train": len(sample),
                         "window_cut": bool(window and RUN_B_WINDOW % window), **r})
        log(f"  {name:22s} w={window:<4d} seed={seed:<3d} "
            f"f1={next(r for r in reversed(rows) if r['subset'] == 'all')['f1_macro']:.4f} "
            f"({time.perf_counter() - t:.1f}s)")
        pd.DataFrame(rows).to_csv(a.out / "ablation_results.csv", index=False)
        if seed == a.seeds[0] and window in (0, RUN_B_WINDOW):
            preds[name] = p

    samples = {s: sample_train(train_all, y, a.per_class, s) for s in a.seeds}
    for name, cols in sets.items():
        for seed in a.seeds:
            run(name, df[cols], 0, seed, samples[seed], run_b_sizes)
    for w in a.windows:
        log(f"window {w}s: building incident context")
        ctx = incident_context(df, w)
        if w == RUN_B_WINDOW:
            checks["groups_at_300s"] = ctx.attrs["n_groups"]
            checks["run_b_incidents"] = int(df["incident_id"].nunique())
        sizes = ctx["n_events"].to_numpy()[test]
        joined = pd.concat([df[feats], ctx], axis=1)
        for name, cols in ctx_sets.items():
            for seed in a.seeds:
                run(name, joined[list(cols) + INCIDENT], w, seed, samples[seed], sizes)

    res = pd.DataFrame(rows)
    res.to_csv(a.out / "ablation_results.csv", index=False)
    g = res.groupby(["window_s", "feature_set", "subset", "window_cut"], sort=True)
    summary = g.agg(runs=("seed", "nunique"), n=("n", "first"),
                    f1_mean=("f1_macro", "mean"), f1_sd=("f1_macro", "std"),
                    fpr_mean=("fpr", "mean"), fpr_sd=("fpr", "std"),
                    fnr_mean=("fnr", "mean"), acc_mean=("accuracy", "mean")
                    ).reset_index().fillna({"f1_sd": 0.0, "fpr_sd": 0.0})
    summary.to_csv(a.out / "ablation_summary.csv", index=False)
    (a.out / "thesis_table.md").write_text(markdown(summary), encoding="utf-8")

    boot = {}
    if a.bootstrap and "event_only" in preds:
        labels = sorted(set(y_test))
        ids = df["incident_id"].astype(str).to_numpy()[test]
        for name in ("incident_only", "event_plus_incident", "shared_plus_incident"):
            base = "shared_event" if name.startswith("shared") else "event_only"
            if name in preds:
                log(f"bootstrap {name} minus {base}")
                boot[f"{name}_minus_{base}"] = paired_bootstrap(
                    y_test, preds[name], preds[base], ids, labels, a.bootstrap,
                    a.seeds[0])
    (a.out / "bootstrap.json").write_text(json.dumps(boot, indent=2), encoding="utf-8")
    checks["minutes"] = round((time.perf_counter() - t0) / 60, 1)
    (a.out / "checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(markdown(summary))
    log(f"finished; results in {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
