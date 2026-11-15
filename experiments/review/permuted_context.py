"""Reviewer analysis 1: permuted-context control for the Run B ablation.

Question: does event_plus_incident gain from the *link* between an event and
its own incident, or only from the distribution of the incident features?
The control keeps the distribution and breaks the link.

  event_plus_permuted_incident  event features plus n_events, span_s,
      events_per_s, with the three incident columns shuffled together as one
      row across events, within each (partition, source) stratum. Labels are
      not used (class-blind). Train and test are separate strata, so they are
      shuffled separately. The shuffle seed equals the model seed.

Everything else is experiments/ablation/run_ablation.py, imported unchanged:
the same Random Forest settings, the same training sample per seed, the same
1,692,332 Run B test events, the same subsets and the same clustered
bootstrap. Before the full run, event_only and event_plus_incident at seed 42
(300 s) must reproduce experiments/ablation/results/full exactly; if not, the
script stops with exit code 2.

Reads   code/data/processed/stage3_events, stage2_feature_plan.csv
Writes  experiments/review/results/permuted_context/ only

    PYTHONPATH=code code/.venv/Scripts/python.exe -B \
        experiments/review/permuted_context.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ablation"))
import run_ablation as R  # noqa: E402  (original, unchanged)

ORIGINAL = HERE.parent / "ablation" / "results" / "full" / "ablation_results.csv"
PERMUTED = "event_plus_permuted_incident"
TOL = 1e-12


def permute_context(ctx: pd.DataFrame, split: np.ndarray, source: np.ndarray,
                    seed: int) -> pd.DataFrame:
    """Shuffle whole incident-feature rows within each (split, source) stratum.

    Each stratum keeps exactly its own multiset of rows (distribution kept);
    rows move between events, so an event no longer carries its own
    incident's values. Labels are never read.
    """
    strata = pd.factorize(pd.Series(split, dtype="string") + "|" +
                          pd.Series(source, dtype="string"))[0]
    rng = np.random.default_rng(seed)
    n = len(ctx)
    home = np.lexsort((np.arange(n), strata))        # stratum order, stable
    donor = np.lexsort((rng.random(n), strata))      # same strata, shuffled
    vals = ctx.to_numpy()
    out = np.empty_like(vals)
    out[home] = vals[donor]
    res = pd.DataFrame(out, index=ctx.index, columns=ctx.columns)
    return res.astype(ctx.dtypes.to_dict())


def compare_to_original(rows: list[dict], original: pd.DataFrame) -> list[dict]:
    """Metric-by-metric comparison with the saved ablation rows."""
    out = []
    for r in rows:
        o = original[(original.window_s == r["window_s"]) & (original.seed == r["seed"])
                     & (original.feature_set == r["feature_set"])
                     & (original.subset == r["subset"])]
        if len(o) != 1:
            out.append({**{k: r[k] for k in ("window_s", "seed", "feature_set", "subset")},
                        "match": False, "reason": f"{len(o)} original rows"})
            continue
        o = o.iloc[0]
        diffs = {}
        for m in ("n", "n_train") + R.METRICS:
            a, b = r[m], o[m]
            same = (pd.isna(a) and pd.isna(b)) or abs(float(a) - float(b)) <= TOL
            if not same:
                diffs[m] = [float(a), float(b)]
        out.append({**{k: r[k] for k in ("window_s", "seed", "feature_set", "subset")},
                    "match": not diffs, "diffs": diffs})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", type=Path, default=R.C.DATA_OUT / "stage3_events")
    ap.add_argument("--plan", type=Path, default=R.C.DATA_OUT / "stage2_feature_plan.csv")
    ap.add_argument("--out", type=Path, default=HERE / "results" / "permuted_context")
    ap.add_argument("--original", type=Path, default=ORIGINAL)
    ap.add_argument("--windows", type=int, nargs="+", default=[60, 150, 300, 600, 900])
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 1, 2, 3, 4])
    ap.add_argument("--trees", type=int, default=R.C.N_ESTIMATORS)
    ap.add_argument("--per-class", type=int, default=R.C.BUDGET.train_budget_per_class)
    ap.add_argument("--n-jobs", type=int, default=R.C.BUDGET.n_jobs)
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--boot-seed", type=int, default=42)
    ap.add_argument("--skip-repro", action="store_true",
                    help="tests only: skip the check against the saved ablation")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    feats = R.event_features(a.plan)
    R.log(f"loading events ({len(feats)} event features)")
    df = R.load_events(a.events, feats)
    y = df["label"].astype(str).to_numpy()
    split = df["split"].astype(str).to_numpy()
    source = df["source"].astype(str).to_numpy()
    train_all, test = np.flatnonzero(split == "train"), np.flatnonzero(split == "test")
    R.log(f"{len(df):,} events: {len(train_all):,} train, {len(test):,} test")
    dup = np.isin(R._row_hash(df.iloc[test], feats), R._row_hash(df.iloc[train_all], feats))
    y_test = y[test]
    benign = y_test == "benign"
    run_b_sizes = df.iloc[test].groupby("incident_id")["label"].transform("size").to_numpy()
    samples = {s: R.sample_train(train_all, y, a.per_class, s) for s in a.seeds}
    checks = {"n_events": len(df), "n_test": len(test), "n_novel": int((~dup).sum()),
              "event_features": feats, "seeds": a.seeds, "windows": a.windows,
              "trees": a.trees, "per_class": a.per_class, "n_jobs": a.n_jobs,
              "n_train_per_seed": {str(s): len(v) for s, v in samples.items()}}
    rows, preds = [], {}

    def run(name, X, window, seed, sizes):
        t = time.perf_counter()
        p, _ = R.fit_predict(X, y, samples[seed], test, seed, a.trees, a.n_jobs)
        masks = {"all": np.ones(len(test), bool), "novel_vector": ~dup,
                 f"groups_le_{R.LARGE_GROUP}": sizes <= R.LARGE_GROUP,
                 "multi_event_benign": benign & (sizes > 1),
                 "single_event_benign": benign & (sizes == 1)}
        new = []
        for r in R.score(y_test, p, masks):
            new.append({"window_s": window, "seed": seed, "feature_set": name,
                        "n_features": X.shape[1], "n_train": len(samples[seed]),
                        "window_cut": bool(window and R.RUN_B_WINDOW % window), **r})
        rows.extend(new)
        R.log(f"  {name:30s} w={window:<4d} seed={seed:<3d} "
              f"f1={new[0]['f1_macro']:.4f} ({time.perf_counter() - t:.1f}s)")
        pd.DataFrame(rows).to_csv(a.out / "review_results.csv", index=False)
        if seed == a.seeds[0]:
            preds[(name, window)] = p
        return new

    ctx_cache = {}

    def context(w):
        if w not in ctx_cache:
            R.log(f"window {w}s: building incident context")
            ctx_cache.clear()
            ctx_cache[w] = R.incident_context(df, w)
        return ctx_cache[w]

    # 1. Reproduction gate: seed 42, event_only and event_plus_incident at 300 s.
    s0 = a.seeds[0]
    repro_rows = run("event_only", df[feats], 0, s0, run_b_sizes)
    ctx = context(R.RUN_B_WINDOW)
    checks["groups_at_300s"] = ctx.attrs["n_groups"]
    joined = pd.concat([df[feats], ctx], axis=1)
    repro_rows += run("event_plus_incident", joined[feats + R.INCIDENT],
                      R.RUN_B_WINDOW, s0, ctx["n_events"].to_numpy()[test])
    if not a.skip_repro:
        cmp = compare_to_original(repro_rows, pd.read_csv(a.original))
        checks["reproduction"] = {"original": str(a.original), "tolerance": TOL,
                                  "all_match": all(c["match"] for c in cmp), "rows": cmp}
        (a.out / "checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
        if not checks["reproduction"]["all_match"]:
            R.log("STOP: seed-42 results do not reproduce the saved ablation; see checks.json")
            return 2
        R.log("reproduction check passed: event_only and event_plus_incident (seed 42, "
              "300 s) match the saved ablation in every subset and metric")

    # 2. Full grid.
    for seed in a.seeds[1:]:
        run("event_only", df[feats], 0, seed, run_b_sizes)
    perm_checks = {}
    for w in a.windows:
        ctx = context(w)
        sizes = ctx["n_events"].to_numpy()[test]       # true sizes: same subsets
        joined = pd.concat([df[feats], ctx], axis=1)
        for seed in a.seeds:
            if not (w == R.RUN_B_WINDOW and seed == s0):
                run("event_plus_incident", joined[feats + R.INCIDENT], w, seed, sizes)
            perm = permute_context(ctx, split, source, seed)
            same_row = (perm.to_numpy() == ctx.to_numpy()).all(axis=1)
            kept = all(np.array_equal(np.sort(perm[c].to_numpy()[m]), np.sort(ctx[c].to_numpy()[m]))
                       for c in R.INCIDENT for m in (split == "train", split == "test"))
            perm_checks[f"{w}_{seed}"] = {
                "distribution_kept_per_partition": bool(kept),
                "test_rows_equal_to_own_context": float(same_row[test].mean()),
                "train_rows_equal_to_own_context": float(same_row[train_all].mean())}
            pj = pd.concat([df[feats], perm], axis=1)
            run(PERMUTED, pj[feats + R.INCIDENT], w, seed, sizes)
    checks["permutation"] = perm_checks

    res = pd.DataFrame(rows).sort_values(["window_s", "feature_set", "seed", "subset"])
    res.to_csv(a.out / "review_results.csv", index=False)
    g = res.groupby(["window_s", "feature_set", "subset", "window_cut"], sort=True)
    summary = g.agg(runs=("seed", "nunique"), n=("n", "first"),
                    f1_mean=("f1_macro", "mean"), f1_sd=("f1_macro", "std"),
                    fpr_mean=("fpr", "mean"), fpr_sd=("fpr", "std"),
                    fnr_mean=("fnr", "mean"), acc_mean=("accuracy", "mean")
                    ).reset_index()
    summary.to_csv(a.out / "review_summary.csv", index=False)
    (a.out / "review_table.md").write_text(R.markdown(summary), encoding="utf-8")

    boot = {}
    if a.bootstrap:
        labels = sorted(set(y_test))
        ids = df["incident_id"].astype(str).to_numpy()[test]
        for w in a.windows:
            for hi, lo in (("event_plus_incident", PERMUTED), (PERMUTED, "event_only")):
                pa = preds[(hi, w)]
                pb = preds[(lo, 0 if lo == "event_only" else w)]
                R.log(f"bootstrap w={w} {hi} minus {lo}")
                ma = R.evaluate_split(pd.Series(y_test), pd.Series(pa))
                mb = R.evaluate_split(pd.Series(y_test), pd.Series(pb))
                boot[f"w{w}:{hi}_minus_{lo}"] = {
                    "window_s": w, "seed": s0, "boot_seed": a.boot_seed,
                    "cluster": "Run B incident_id",
                    "f1_macro_point": ma["f1_macro"] - mb["f1_macro"],
                    "fpr_point": ma["fpr"] - mb["fpr"],
                    **R.paired_bootstrap(y_test, pa, pb, ids, labels, a.bootstrap,
                                         a.boot_seed)}
    (a.out / "bootstrap.json").write_text(json.dumps(boot, indent=2), encoding="utf-8")
    checks["minutes"] = round((time.perf_counter() - t0) / 60, 1)
    (a.out / "checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(R.markdown(summary))
    R.log(f"finished; results in {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
