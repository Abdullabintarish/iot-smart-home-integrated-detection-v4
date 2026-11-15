"""P2 + P4 (audit 2026-11-03): ablation v2 with saved predictions and unseen sources.

Reuses experiments/ablation/run_ablation.py unchanged (loader, incident context,
per-class sampling, Random Forest). Window fixed at 300 s (Run B).

Feature sets
  event_only                    20 Run B event features
  event_no_sport                event_only without the ephemeral source port (M2)
  incident_only                 n_events, span_s, events_per_s (completed window)
  event_plus_incident           event_only + completed-window incident context
  event_plus_causal             event_only + context from earlier events of the
                                same incident only (n_so_far, span_so_far, rate_so_far; M4)

Designs
  runB  Run B split (25 % of correlation keys held out), 5 seeds, all sets      (P4)
  loso  leave-one-source-out over the 13 sources, 3 seeds, all sets            (P2)
        Training pool = every event of the other 12 sources. The per-source
        fragmented baseline is undefined for an unseen source and is not run.
        Inputs are the Run B preprocessed events: scaling was fitted on Run B
        training rows of all sources (monotone, so a Random Forest is unaffected);
        categorical codes unseen in Run B training are -1.

    code/.venv/Scripts/python.exe -B experiments/v2/ablation_v2.py runB loso

Writes experiments/v2/results/ablation/<design>_metrics.json,
<design>_predictions.parquet and manifest_<design>.json.
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
SUB = HERE.parents[1]
sys.path.insert(0, str(SUB / "code"))
sys.path.insert(0, str(SUB / "experiments" / "ablation"))
import run_ablation as A  # noqa: E402
from manifest import write_manifest  # noqa: E402
from pipeline import config as C  # noqa: E402
from pipeline.correlate import correlation_key  # noqa: E402
from pipeline.detect import NON_FEATURES, event_features, evaluate_split  # noqa: E402

OUT = HERE / "results" / "ablation"
WINDOW = 300
CAUSAL = ["n_so_far", "span_so_far", "rate_so_far"]
DESIGNS = {"runB": (42, 1, 2, 3, 4), "loso": (42, 1, 2)}


def causal_context(df: pd.DataFrame, window_s: int, by_split: bool) -> pd.DataFrame:
    """Context from the event itself and earlier events of its incident only.

    Same grouping as ``run_ablation.incident_context``; ties in ``ts`` are
    ordered by row position, so an event never sees a later-positioned event.
    """
    key, _, _ = correlation_key(df, window_s=window_s)
    if by_split:
        key = key.astype("string") + "|" + df["split"].astype("string")
    codes, uniq = pd.factorize(key)
    codes = codes.astype("int64")
    lonely = codes < 0
    codes[lonely] = len(uniq) + np.arange(lonely.sum())
    ts = pd.to_numeric(df["ts"], errors="coerce").to_numpy("float64")
    t = pd.DataFrame({"g": codes, "ts": ts, "pos": np.arange(len(df))})
    t = t.sort_values(["g", "ts", "pos"], kind="mergesort")
    n = t.groupby("g", sort=False).cumcount().to_numpy() + 1
    span = (t["ts"] - t.groupby("g", sort=False)["ts"].transform("min")).fillna(0.0).clip(lower=0.0).to_numpy()
    rate = np.where(span > 0, n / np.where(span > 0, span, 1.0), 0.0)
    out = pd.DataFrame({"n_so_far": n, "span_so_far": span, "rate_so_far": rate},
                       index=t.index).sort_index()
    out.index = df.index
    return out.astype("float32")


def full_context(df: pd.DataFrame, window_s: int, by_split: bool) -> pd.DataFrame:
    if by_split:
        return A.incident_context(df, window_s)
    tmp = df.assign(split="all")
    return A.incident_context(tmp, window_s)


def feature_sets(feats: list[str]) -> dict[str, list[str]]:
    no_sport = [f for f in feats if f != "sport"]
    return {"event_only": feats, "event_no_sport": no_sport,
            "incident_only": list(A.INCIDENT), "event_plus_incident": feats + A.INCIDENT,
            "event_plus_causal": feats + CAUSAL}


def slim(m: dict) -> dict:
    keep = ("accuracy", "precision_macro", "recall_macro", "f1_macro", "fpr", "fnr",
            "n_samples", "per_class", "confusion_matrix", "classes", "binary_counts")
    return {k: m[k] for k in keep if k in m}


def per_source(y, p, src) -> dict:
    out = {}
    for s in np.unique(src):
        m = src == s
        r = evaluate_split(pd.Series(y[m]), pd.Series(p[m]))
        out[str(s)] = {k: r[k] for k in ("f1_macro", "fpr", "fnr", "n_samples", "classes")}
    return out


def load():
    feats = event_features(C.DATA_OUT / "stage2_feature_plan.csv")
    if set(feats) & set(NON_FEATURES):
        raise ValueError("identifier in feature list")
    df = A.load_events(C.DATA_OUT / "stage3_events", feats)
    return df, feats


def run_design(design: str, df: pd.DataFrame, feats: list[str]) -> None:
    seeds = DESIGNS[design]
    by_split = design == "runB"
    A.log(f"{design}: building 300 s context (completed and causal)")
    X = pd.concat([df[feats], full_context(df, WINDOW, by_split),
                   causal_context(df, WINDOW, by_split)], axis=1)
    sets = feature_sets(feats)
    y = df["label"].astype(str).to_numpy()
    src = df["source"].astype(str).to_numpy()
    if design == "runB":
        split = df["split"].astype(str).to_numpy()
        folds = {"runB": (np.flatnonzero(split == "train"), np.flatnonzero(split == "test"))}
    else:
        folds = {s: (np.flatnonzero(src != s), np.flatnonzero(src == s)) for s in sorted(np.unique(src))}
    classes = sorted(np.unique(y))
    pred_cols, idx_all, metrics = {}, [], {}
    for fold, (train_all, test) in folds.items():
        idx_all.append(test)
        metrics[fold] = {"n_test": int(len(test)),
                         "test_classes": pd.Series(y[test]).value_counts().to_dict(),
                         "train_classes": pd.Series(y[train_all]).value_counts().to_dict(),
                         "test_classes_unseen_in_train": sorted(set(y[test]) - set(y[train_all])),
                         "runs": {}}
        for seed in seeds:
            sample = A.sample_train(train_all, y, C.BUDGET.train_budget_per_class, seed)
            for name, cols in sets.items():
                t0 = time.perf_counter()
                p, imp = A.fit_predict(X[cols], y, sample, test, seed, C.N_ESTIMATORS, C.BUDGET.n_jobs)
                col = f"pred_{name}_s{seed}"
                pred_cols.setdefault(col, []).append(p)
                r = evaluate_split(pd.Series(y[test]), pd.Series(p))
                entry = slim(r)
                entry["n_train"] = int(len(sample))
                entry["importances"] = dict(zip(cols, np.round(imp, 5).tolist()))
                if design == "runB":
                    entry["per_source"] = per_source(y[test], p, src[test])
                metrics[fold]["runs"][f"{name}|{seed}"] = entry
                A.log(f"  {fold:32s} {name:20s} seed={seed:<3d} f1={r['f1_macro']:.4f} "
                      f"fpr={r['fpr']:.4f} ({time.perf_counter() - t0:.0f}s)")
    idx = np.concatenate(idx_all)
    preds = pd.DataFrame({"event_id": df["event_id"].to_numpy()[idx], "source": src[idx],
                          "label": pd.Categorical(y[idx], categories=classes),
                          "fold": np.concatenate([[f] * len(t) for f, (_, t) in folds.items()])})
    for col, parts in pred_cols.items():
        preds[col] = pd.Categorical(np.concatenate(parts), categories=classes)
    OUT.mkdir(parents=True, exist_ok=True)
    mpath, ppath = OUT / f"{design}_metrics.json", OUT / f"{design}_predictions.parquet"
    mpath.write_text(json.dumps({"design": design, "window_s": WINDOW, "seeds": list(seeds),
                                 "feature_sets": sets, "folds": metrics}, indent=2, default=float),
                     encoding="utf-8")
    preds.to_parquet(ppath)
    write_manifest(OUT / f"manifest_{design}.json", f"ablation_v2_{design}",
                   inputs=sorted((C.DATA_OUT / "stage3_events").glob("*.parquet"))
                   + [C.DATA_OUT / "stage2_feature_plan.csv"],
                   config={"window_s": WINDOW, "feature_sets": sets, "trees": C.N_ESTIMATORS,
                           "max_depth": C.MAX_TREE_DEPTH, "per_class": C.BUDGET.train_budget_per_class,
                           "split": "Run B key-hash split" if by_split else "leave-one-source-out",
                           "context_groups_cut_at_split": by_split},
                   seeds=seeds, outputs=[mpath, ppath])
    A.log(f"{design}: saved {len(preds):,} prediction rows")


if __name__ == "__main__":
    df, feats = load()
    A.log(f"{len(df):,} events, {len(feats)} event features")
    for d in (sys.argv[1:] or list(DESIGNS)):
        run_design(d, df, feats)
    A.log("done")
