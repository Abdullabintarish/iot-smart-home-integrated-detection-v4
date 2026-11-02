"""Stage 4: compare conditions A-D on the same capture-held-out test events.

Target: binary (malicious = 1, benign = 0). Per-class results are the
detection rate per thesis class of the true label. Same split, same training
sample per seed, same Random Forest settings (thesis Stage 4) for every
condition; only the input columns differ.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

from features import (CONN_CATEGORICAL, CONN_NUMERIC, DNS_FEATURES, FORBIDDEN,
                      Preprocessor)

RF_PARAMS = dict(n_estimators=300, max_depth=24, min_samples_leaf=2,
                 class_weight="balanced_subsample", n_jobs=-1)
TRAIN_BUDGET_PER_CLASS = 60_000
SEEDS = (42, 1, 2, 3, 4)


def condition_columns(alert_cols: list[str]) -> dict[str, tuple[list[str], list[str]]]:
    num_a = list(CONN_NUMERIC)
    return {
        "A": (num_a, list(CONN_CATEGORICAL)),
        "B": (num_a + list(DNS_FEATURES), list(CONN_CATEGORICAL)),
        "C": (num_a + alert_cols, list(CONN_CATEGORICAL)),
        "D": (num_a + list(DNS_FEATURES) + alert_cols, list(CONN_CATEGORICAL)),
    }


def check_no_forbidden(cols) -> None:
    bad = [c for c in cols if c in FORBIDDEN]
    if bad:
        raise ValueError(f"forbidden feature columns: {bad}")


def train_sample(train: pd.DataFrame, seed: int,
                 budget: int = TRAIN_BUDGET_PER_CLASS) -> pd.DataFrame:
    parts = []
    for _, g in train.groupby("y", sort=True):
        parts.append(g.sample(n=min(budget, len(g)), random_state=seed))
    return pd.concat(parts).sort_index()


def metrics(y: np.ndarray, p: np.ndarray, cls: np.ndarray) -> dict:
    ben = y == 0
    att = y == 1
    out = {
        "n": int(len(y)), "n_benign": int(ben.sum()), "n_attack": int(att.sum()),
        "macro_f1": float(f1_score(y, p, average="macro", labels=[0, 1], zero_division=0)),
        "fpr": float((p[ben] == 1).mean()) if ben.any() else None,
        "fnr": float((p[att] == 0).mean()) if att.any() else None,
        "per_class_detection_rate": {},
    }
    for c in sorted(set(cls)):
        m = cls == c
        # benign: share predicted benign; attack classes: share predicted malicious
        target = 0 if c == "benign" else 1
        out["per_class_detection_rate"][c] = {
            "n": int(m.sum()), "rate": float((p[m] == target).mean())}
    return out


def run(train: pd.DataFrame, test: pd.DataFrame, alert_cols: list[str],
        seeds=SEEDS) -> tuple[dict, pd.DataFrame]:
    conds = condition_columns(alert_cols)
    for num, cat in conds.values():
        check_no_forbidden(num + cat)
    preds = pd.DataFrame({"incident_id": test["incident_id"].to_numpy(),
                          "capture": test["capture"].to_numpy(),
                          "cls": test["cls"].to_numpy(), "y": test["y"].to_numpy()})
    # "Unseen benign": test benign rows whose condition-A feature vector does
    # not occur in the training data (same definition for every condition).
    pa = Preprocessor().fit(train, *conds["A"])
    seen = {r.tobytes() for r in pa.transform(train)}
    novel = np.array([r.tobytes() not in seen for r in pa.transform(test)])
    preds["novel_vector"] = novel
    results: dict = {"seeds": list(seeds), "conditions": {}}
    for name, (num, cat) in conds.items():
        results["conditions"][name] = {"numeric": num, "categorical": cat, "by_seed": {}}
    for seed in seeds:
        tr = train_sample(train, seed)
        for name, (num, cat) in conds.items():
            pre = Preprocessor().fit(tr, num, cat)
            rf = RandomForestClassifier(random_state=seed, **RF_PARAMS)
            rf.fit(pre.transform(tr), tr["y"].to_numpy())
            p = rf.predict(pre.transform(test))
            preds[f"pred_{name}_s{seed}"] = p
            m = metrics(test["y"].to_numpy(), p, test["cls"].to_numpy())
            nb = novel & (test["y"].to_numpy() == 0)
            m["fpr_unseen_benign"] = float((p[nb] == 1).mean()) if nb.any() else None
            m["n_unseen_benign"] = int(nb.sum())
            m["n_train"] = int(len(tr))
            m["n_features"] = len(pre.columns)
            results["conditions"][name]["by_seed"][str(seed)] = m
    for name, r in results["conditions"].items():
        f1s = [r["by_seed"][str(s)]["macro_f1"] for s in seeds]
        r["macro_f1_mean"] = float(np.mean(f1s))
        r["macro_f1_sd"] = float(np.std(f1s, ddof=1)) if len(f1s) > 1 else 0.0
    return results, preds


def cluster_bootstrap(preds: pd.DataFrame, seed_col: int = 42, reps: int = 1000,
                      rng_seed: int = 42) -> dict:
    """Incident-clustered percentile bootstrap of macro F1 and of B/C/D - A."""
    rng = np.random.default_rng(rng_seed)
    inc = preds["incident_id"].to_numpy()
    codes, uniq = pd.factorize(inc)
    rows_by = pd.Series(np.arange(len(preds))).groupby(codes).apply(np.array).to_list()
    y = preds["y"].to_numpy()
    P = {c: preds[f"pred_{c}_s{seed_col}"].to_numpy() for c in "ABCD"}
    draws = {c: [] for c in "ABCD"}
    for _ in range(reps):
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([rows_by[i] for i in pick])
        for c in "ABCD":
            draws[c].append(f1_score(y[idx], P[c][idx], average="macro",
                                     labels=[0, 1], zero_division=0))
    out = {"reps": reps, "rng_seed": rng_seed, "model_seed": seed_col,
           "clusters": int(len(uniq))}
    for c in "ABCD":
        a = np.array(draws[c])
        out[f"macro_f1_{c}"] = [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
    for c in "BCD":
        dlt = np.array(draws[c]) - np.array(draws["A"])
        out[f"diff_{c}_minus_A"] = [float(np.percentile(dlt, 2.5)), float(np.percentile(dlt, 97.5))]
    return out
