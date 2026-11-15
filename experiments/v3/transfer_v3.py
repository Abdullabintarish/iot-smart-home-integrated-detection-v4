"""v3 transfer study (PLAN_V3.md §A): pooled RF / HGB / LR vs the source-specific
baseline, on the Run B split and leave-one-source-out, 5 seeds.

Reuses experiments/ablation/run_ablation.py (loader, sampler, context) and
experiments/v2/ablation_v2.py (context helpers) unchanged.

    code/.venv/Scripts/python.exe -B experiments/v3/transfer_v3.py runB loso

Writes experiments/v3/results/transfer/<design>/: rows.parquet (test-row index),
run_<name>_s<seed>.parquet (pred + float16 probabilities), metrics.json,
manifest.json.
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, balanced_accuracy_score,
                             f1_score, matthews_corrcoef, roc_auc_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SUB = HERE.parents[1]
sys.path.insert(0, str(SUB / "experiments" / "v2"))
import ablation_v2 as AV  # noqa: E402  (also puts code/ and ablation/ on sys.path)
import run_ablation as A  # noqa: E402
from manifest import write_manifest  # noqa: E402
from pipeline import config as C  # noqa: E402
from pipeline.detect import evaluate_split  # noqa: E402

OUT = HERE / "results" / "transfer"
SEEDS = (42, 1, 2, 3, 4)
WINDOW = 300
CATEGORICAL = ("proto", "app", "conn_state", "history", "flgs", "state")
MODELS = ("rf", "hgb", "lr")
SET_NAMES = ("event_only", "incident_only", "event_plus_incident")
BENIGN = "benign"


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
def rf(seed: int) -> RandomForestClassifier:
    return RandomForestClassifier(n_estimators=C.N_ESTIMATORS, max_depth=C.MAX_TREE_DEPTH,
                                  min_samples_leaf=A.MIN_SAMPLES_LEAF,
                                  class_weight=A.CLASS_WEIGHT, bootstrap=True,
                                  n_jobs=C.BUDGET.n_jobs, random_state=seed)


def symlog(x):
    return np.sign(x) * np.log1p(np.abs(x))


def build(model: str, cols: list[str], seed: int):
    if model == "rf":
        return rf(seed)
    if model == "hgb":
        return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.1, max_leaf_nodes=31,
                                              class_weight="balanced", early_stopping=False,
                                              random_state=seed)
    cat = [c for c in cols if c in CATEGORICAL]
    num = [c for c in cols if c not in CATEGORICAL]
    pre = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore"), cat),
         ("num", make_pipeline(FunctionTransformer(symlog), StandardScaler()), num)],
        sparse_threshold=0.0)
    return make_pipeline(pre, LogisticRegression(max_iter=1000, class_weight="balanced"))


def full_proba(est, X, classes: list[str]) -> np.ndarray:
    """Probabilities in the global class order; untrained classes get 0."""
    p = est.predict_proba(X)
    out = np.zeros((len(X), len(classes)), dtype="float64")
    for j, c in enumerate(est.classes_):
        out[:, classes.index(c)] = p[:, j]
    return out


class Constant:
    def __init__(self, label):
        self.classes_ = np.array([label])

    def predict_proba(self, X):
        return np.ones((len(X), 1))


def fit_source_model(X, y, seed):
    if len(np.unique(y)) == 1:
        return Constant(y[0])
    return rf(seed).fit(X, y)


# --------------------------------------------------------------------------
# Metrics (original + added)
# --------------------------------------------------------------------------
def score(y: np.ndarray, pred: np.ndarray, proba16: np.ndarray, classes: list[str],
          attack_score: np.ndarray | None = None) -> dict:
    r = evaluate_split(pd.Series(y), pd.Series(pred))
    out = {k: r[k] for k in ("accuracy", "precision_macro", "recall_macro", "f1_macro", "fpr",
                             "fnr", "n_samples", "per_class", "confusion_matrix", "classes")}
    out = {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in out.items()}
    present = sorted(set(y))
    out["f1_macro_present"] = float(f1_score(y, pred, labels=present, average="macro", zero_division=0))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out["balanced_accuracy"] = float(balanced_accuracy_score(y, pred))
    out["mcc"] = float(matthews_corrcoef(y, pred))
    yb = y != BENIGN
    out["binary_f1"] = float(f1_score(yb, pred != BENIGN, zero_division=0))
    p = proba16.astype("float64")
    s = 1.0 - p[:, classes.index(BENIGN)] if attack_score is None else attack_score.astype("float64")
    both = yb.any() and (~yb).any()
    out["pr_auc_binary"] = float(average_precision_score(yb, s)) if both else None
    out["roc_auc_binary"] = float(roc_auc_score(yb, s)) if both else None
    if len(present) >= 2:
        out["pr_auc_macro_present"] = float(np.mean(
            [average_precision_score(y == c, p[:, classes.index(c)]) for c in present]))
    else:
        out["pr_auc_macro_present"] = None
    return out


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------
def log(msg):
    A.log(msg)


def run_design(design: str, df: pd.DataFrame, feats: list[str]) -> None:
    out = OUT / design
    out.mkdir(parents=True, exist_ok=True)
    by_split = design == "runB"
    log(f"{design}: building 300 s context")
    X = pd.concat([df[feats], AV.full_context(df, WINDOW, by_split)], axis=1)
    sets = {"event_only": feats, "incident_only": list(A.INCIDENT),
            "event_plus_incident": feats + list(A.INCIDENT)}
    y = df["label"].astype(str).to_numpy()
    src = df["source"].astype(str).to_numpy()
    classes = sorted(np.unique(y))
    sources = sorted(np.unique(src))
    if by_split:
        split = df["split"].astype(str).to_numpy()
        folds = {"runB": (np.flatnonzero(split == "train"), np.flatnonzero(split == "test"))}
    else:
        folds = {s: (np.flatnonzero(src != s), np.flatnonzero(src == s)) for s in sources}
    order = np.concatenate([t for _, t in folds.values()])
    pos = np.empty(len(df), dtype=np.int64)
    pos[order] = np.arange(len(order))
    rows = pd.DataFrame({"event_id": df["event_id"].to_numpy()[order], "source": src[order],
                         "label": y[order], "incident_id": df["incident_id"].astype(str).to_numpy()[order],
                         "fold": np.concatenate([[f] * len(t) for f, (_, t) in folds.items()])})
    rows.to_parquet(out / "rows.parquet")
    metrics: dict = {"design": design, "classes": classes, "seeds": list(SEEDS),
                     "feature_sets": sets, "folds": {f: {"n_test": int(len(t)),
                     "test_classes": pd.Series(y[t]).value_counts().to_dict(),
                     "train_classes": pd.Series(y[tr]).value_counts().to_dict()}
                     for f, (tr, t) in folds.items()}, "runs": {}}
    saved = [out / "rows.parquet"]

    def save_run(name, seed, pred, proba16, attack=None):
        f = out / f"run_{name}_s{seed}.parquet"
        d = pd.DataFrame(proba16, columns=[f"p_{c}" for c in classes])
        d.insert(0, "pred", pd.Categorical(pred, categories=classes))
        if attack is not None:
            d["attack_score"] = attack
        d.to_parquet(f)
        saved.append(f)
        per = {}
        for fold in folds:
            m = (rows["fold"] == fold).to_numpy()
            per[fold] = score(rows["label"].to_numpy()[m], pred[m], proba16[m], classes,
                              None if attack is None else attack[m])
        metrics["runs"][f"{name}|{seed}"] = per
        (out / "metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")

    for seed in SEEDS:
        # ---- pooled models: same sample for every model and set -------------
        acc = {(m, s): (np.empty(len(order), dtype=object), np.zeros((len(order), len(classes)), "float16"))
               for m in MODELS for s in SET_NAMES}
        for fold, (train_all, test) in folds.items():
            sample = A.sample_train(train_all, y, C.BUDGET.train_budget_per_class, seed)
            for m in MODELS:
                for sname in SET_NAMES:
                    t0 = time.perf_counter()
                    cols = sets[sname]
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        est = build(m, cols, seed).fit(X.iloc[sample][cols], y[sample])
                    p = full_proba(est, X.iloc[test][cols], classes)
                    pred_arr, prob_arr = acc[(m, sname)]
                    pred_arr[pos[test]] = np.array(classes, dtype=object)[p.argmax(1)]
                    prob_arr[pos[test]] = p.astype("float16")
                    log(f"  {design} {fold[:26]:26s} s{seed:<2d} {m:3s} {sname:20s} ({time.perf_counter() - t0:.0f}s)")
        for (m, sname), (pred_arr, prob_arr) in acc.items():
            save_run(f"{m}_{sname}", seed, pred_arr.astype(str), prob_arr)
        # ---- source-specific baseline ---------------------------------------
        t0 = time.perf_counter()
        if by_split:
            train_all, test = folds["runB"]
            pred_arr = np.empty(len(order), dtype=object)
            prob_arr = np.zeros((len(order), len(classes)), "float16")
            for s in sources:
                tr = train_all[src[train_all] == s]
                te = test[src[test] == s]
                smp = A.sample_train(tr, y, C.BUDGET.train_budget_per_class, seed)
                est = fit_source_model(X.iloc[smp][feats], y[smp], seed)
                p = full_proba(est, X.iloc[te][feats], classes)
                pred_arr[pos[te]] = np.array(classes, dtype=object)[p.argmax(1)]
                prob_arr[pos[te]] = p.astype("float16")
            save_run("frag", seed, pred_arr.astype(str), prob_arr)
        else:
            n = len(order)
            k = len(classes)
            bi = classes.index(BENIGN)
            psum = np.zeros((n, k))
            alert_sum = np.zeros((n, k))
            any_alert = np.zeros(n, bool)
            max_attack = np.zeros(n)
            n_models = np.zeros(n)
            for s in sources:
                own = np.flatnonzero(src == s)
                smp = A.sample_train(own, y, C.BUDGET.train_budget_per_class, seed)
                est = fit_source_model(X.iloc[smp][feats], y[smp], seed)
                other = np.flatnonzero(src != s)
                p = full_proba(est, X.iloc[other][feats], classes)
                i = pos[other]
                psum[i] += p
                n_models[i] += 1
                alerting = p.argmax(1) != bi
                any_alert[i] |= alerting
                alert_sum[i[alerting]] += p[alerting]
                max_attack[i] = np.maximum(max_attack[i], 1.0 - p[:, bi])
                log(f"  loso frag model {s} s{seed} ({time.perf_counter() - t0:.0f}s)")
            assert (n_models == len(sources) - 1).all()
            soft = (psum / n_models[:, None]).astype("float16")
            save_run("frag_soft", seed, np.array(classes)[soft.astype("float64").argmax(1)], soft)
            att = alert_sum.copy()
            att[:, bi] = -1.0
            union = np.where(any_alert, np.array(classes)[att.argmax(1)], BENIGN)
            save_run("frag_union", seed, union, soft, attack=max_attack.astype("float16"))
    write_manifest(out / "manifest.json", f"transfer_v3_{design}",
                   inputs=sorted((C.DATA_OUT / "stage3_events").glob("*.parquet"))
                   + [C.DATA_OUT / "stage2_feature_plan.csv"],
                   config={"plan": "experiments/v3/PLAN_V3.md §A", "window_s": WINDOW,
                           "models": MODELS, "feature_sets": sets, "categorical": CATEGORICAL,
                           "per_class": C.BUDGET.train_budget_per_class,
                           "context_groups_cut_at_split": by_split},
                   seeds=SEEDS, outputs=saved + [out / "metrics.json"])
    log(f"{design}: done")


if __name__ == "__main__":
    df, feats = AV.load()
    log(f"{len(df):,} events, {len(feats)} event features")
    for d in (sys.argv[1:] or ["runB", "loso"]):
        run_design(d, df, feats)
    log("done")
