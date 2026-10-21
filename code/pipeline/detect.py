"""Stage 4 - Threat detection and analysis (Random Forest).

Both monitoring conditions use the identical Random Forest configuration and
are scored on the **same held-out events**: every Stage 2 ``split == "test"``
event, at its natural class distribution (not sampled). Stage 2 hashes the
split per Stage 3 correlation group, so no incident has events on both sides.

  fragmented (baseline) : one model per source (isolated monitoring that never
                          sees another source), trained on a stratified sample
                          of that source's train events, event features only;
                          it predicts every test event of its source
  integrated (proposed): one model over Stage 3 incident features, trained on
                          a stratified sample of train incidents; each test
                          incident's *predicted* label is propagated onto its
                          member test events

Features are explicit whitelists (``event_features`` / ``INCIDENT_FEATURES``),
so timestamps, addresses and identifiers can never become model inputs.

Diagnostics (not thesis conditions, reported separately): a pooled event model
(isolates pooling from fragmentation), an enriched event model (event features
plus the event's incident context) and a train/test duplicate-vector check.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_recall_fscore_support, precision_score,
                             recall_score)
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold

from .config import (BUDGET, DATA_OUT, MAX_TREE_DEPTH, MODELS, N_ESTIMATORS,
                     N_SPLITS, RANDOM_STATE)
from .correlate import INCIDENT_FEATURES

BENIGN = "benign"              # the negative class for FPR / FNR
# Columns that identify, locate in time or label an event; never features.
NON_FEATURES = ("ts", "src_ip", "dst_ip", "source", "incident_id", "corr_rule",
                "split", "label", "is_attack", "event_id")
# Incident context appended to event features by the "enriched" diagnostic.
ENRICH_FEATURES = ("n_events", "span_s", "events_per_s")
MIN_SAMPLES_LEAF = 2
CLASS_WEIGHT = "balanced_subsample"


# --------------------------------------------------------------------------
# Features
# --------------------------------------------------------------------------
def check_features(features: Iterable[str]) -> list[str]:
    """Validate a feature whitelist: non-empty, unique, no identifier column."""
    feats = [str(f) for f in features]
    bad = sorted(set(feats) & set(NON_FEATURES))
    if bad:
        raise ValueError(f"identifier columns in feature list: {bad}")
    if not feats or len(set(feats)) != len(feats):
        raise ValueError(f"feature list empty or duplicated: {feats}")
    return feats


def event_features(plan_path: Path = DATA_OUT / "stage2_feature_plan.csv"
                   ) -> list[str]:
    """Event-level whitelist: the features Stage 2's plan marked "kept"."""
    plan = pd.read_csv(plan_path)
    return check_features(plan.loc[plan["decision"] == "kept", "feature"])


def feature_matrix(df: pd.DataFrame, features: Iterable[str]
                   ) -> tuple[pd.DataFrame, pd.Series | None]:
    """Exactly ``features`` as float32 (raises if one is missing), plus target."""
    feats = check_features(features)
    missing = [c for c in feats if c not in df.columns]
    if missing:
        raise KeyError(f"required features missing: {missing}")
    X = df.loc[:, feats].astype("float64")
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0).astype("float32")
    y = df["label"].astype(str) if "label" in df.columns else None
    return X, y


def _row_hash(df: pd.DataFrame, features: list[str]) -> np.ndarray:
    """64-bit hash of each row's feature vector exactly as the model sees it
    (float32), so train and test rows hash alike whatever their storage."""
    X = df.loc[:, features].astype("float32").astype("float64")
    return pd.util.hash_pandas_object(X, index=False).to_numpy()


# --------------------------------------------------------------------------
# Sampling
# --------------------------------------------------------------------------
def stratified_sample(df: pd.DataFrame, per_class: int, seed: int = RANDOM_STATE
                      ) -> pd.DataFrame:
    """Cap each class at ``per_class`` rows, preserving class balance."""
    if df is None or df.empty:
        return df
    parts = []
    for _, grp in df.groupby("label", sort=True):
        parts.append(grp.sample(n=min(per_class, len(grp)), random_state=seed))
    return pd.concat(parts, ignore_index=True).sample(frac=1.0, random_state=seed)


def sample_stream(chunks: Iterator[pd.DataFrame], per_class: int,
                  seed: int = RANDOM_STATE) -> pd.DataFrame:
    """Stratified sample across a *stream* of chunks, never materialising all.

    Each row carries a uniform random priority; the per-class reservoir keeps
    the ``per_class`` lowest priorities seen so far. That is exactly reservoir
    sampling, but applied a chunk at a time instead of row by row, so peak
    memory stays at O(classes x budget + chunk) regardless of corpus size -
    the property that lets this run on a multi-GB corpus inside 8 GB.
    """
    rng = np.random.default_rng(seed)
    reservoir: dict[str, pd.DataFrame] = {}
    for chunk in chunks:
        if chunk.empty or "label" not in chunk.columns:
            continue
        chunk = chunk.assign(__p=rng.random(len(chunk)))
        for cls, grp in chunk.groupby("label", sort=False):
            _reservoir_add(reservoir, cls, grp, per_class)
    out = [df.drop(columns="__p") for _, df in sorted(reservoir.items()) if len(df)]
    if not out:
        return pd.DataFrame()
    return pd.concat(out, ignore_index=True).sample(frac=1.0, random_state=seed)


def _reservoir_add(store: dict, key, grp: pd.DataFrame, budget: int) -> None:
    """Keep the ``budget`` lowest-priority (``__p``) rows seen under ``key``."""
    cur = store.get(key)
    cur = grp if cur is None else pd.concat([cur, grp], ignore_index=True)
    if len(cur) > budget:
        cur = cur.nsmallest(budget, "__p", keep="first")
    store[key] = cur


def _finish_sample(parts: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate reservoirs in stream order (row order is then reproducible)."""
    df = pd.concat(parts, ignore_index=True).drop(columns="__p")
    return df.sort_values("event_id", kind="mergesort").reset_index(drop=True)


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
def _build(n_estimators: int = N_ESTIMATORS) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=MAX_TREE_DEPTH,
        min_samples_leaf=MIN_SAMPLES_LEAF,
        class_weight=CLASS_WEIGHT,
        n_jobs=BUDGET.n_jobs,
        random_state=RANDOM_STATE,
        bootstrap=True,
    )


def model_config() -> dict:
    """The single RF configuration shared by every condition and diagnostic."""
    return {"n_estimators": N_ESTIMATORS, "max_depth": MAX_TREE_DEPTH,
            "min_samples_leaf": MIN_SAMPLES_LEAF, "class_weight": CLASS_WEIGHT,
            "bootstrap": True, "random_state": RANDOM_STATE,
            "train_budget_per_class": BUDGET.train_budget_per_class,
            "cv_folds": N_SPLITS}


class ConstantModel:
    """Stand-in for a training set with one class: always predicts it."""

    def __init__(self, label: str) -> None:
        self.label = str(label)
        self.classes_ = np.array([self.label], dtype=object)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), self.label, dtype=object)


def _fit(X: pd.DataFrame, y: pd.Series):
    """Fit once; returns (model, seconds). One class -> ConstantModel."""
    t = time.perf_counter()
    if y.nunique() < 2:
        model = ConstantModel(y.iloc[0])
    else:
        model = _build()
        model.fit(X, y)
    return model, time.perf_counter() - t


def _importance(model, features: list[str], top: int = 15) -> pd.DataFrame:
    if not hasattr(model, "feature_importances_"):
        return pd.DataFrame(columns=["feature", "importance"])
    return (pd.DataFrame({"feature": features,
                          "importance": model.feature_importances_})
            .sort_values("importance", ascending=False).head(top)
            .reset_index(drop=True))


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
def evaluate_split(y_true: pd.Series, y_pred: pd.Series) -> dict:
    """All Stage 3.5 metrics for one set of predictions.

    Multi-class metrics (accuracy, macro precision / recall / F1, per-class
    table, confusion matrix) use sklearn's default label set: the sorted union
    of true and predicted classes, identical for every condition. Binary
    rates treat ``benign`` as negative and every other class as positive:

      FPR = benign events predicted as any attack class / benign events
      FNR = attack events predicted as benign / attack events

    A rate whose denominator is empty is NaN, with a note. Labels are coerced
    to ``str`` so mixed dtypes cannot break the class sort.
    """
    y_true = pd.Series(y_true).to_numpy(dtype=object).astype(str)
    y_pred = pd.Series(y_pred).to_numpy(dtype=object).astype(str)
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred differ in length")
    classes = sorted(set(y_true) | set(y_pred))
    cm = confusion_matrix(y_true, y_pred, labels=classes)
    true_neg, pred_neg = y_true == BENIGN, y_pred == BENIGN
    n_benign, n_attack = int(true_neg.sum()), int((~true_neg).sum())
    fp = int((true_neg & ~pred_neg).sum())
    fn = int((~true_neg & pred_neg).sum())
    p, r, f, s = precision_recall_fscore_support(
        y_true, y_pred, labels=classes, zero_division=0)
    out = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision_score(y_true, y_pred, labels=classes,
                                                 average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_true, y_pred, labels=classes,
                                           average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_true, y_pred, labels=classes,
                                   average="macro", zero_division=0)),
        "fpr": fp / n_benign if n_benign else float("nan"),
        "fnr": fn / n_attack if n_attack else float("nan"),
        "binary_counts": {"benign": n_benign, "attack": n_attack,
                          "false_positive": fp, "false_negative": fn},
        "per_class": {c: {"precision": float(p[i]), "recall": float(r[i]),
                          "f1": float(f[i]), "support": int(s[i])}
                      for i, c in enumerate(classes)},
        "n_samples": int(len(y_true)),
        "confusion_matrix": cm.tolist(),
        "classes": classes,
        "macro_label_set": "union of true and predicted classes (sklearn default)",
    }
    notes = []
    if not n_benign:
        notes.append("no benign events: FPR undefined (NaN)")
    if not n_attack:
        notes.append("no attack events: FNR undefined (NaN)")
    if notes:
        out["note"] = "; ".join(notes)
    return out


_SLIM_KEYS = ("accuracy", "precision_macro", "recall_macro", "f1_macro", "fpr",
              "fnr", "n_samples")


def _slim(m: dict) -> dict:
    """Headline metrics only; a metric note is kept as ``metric_note``."""
    out = {k: m[k] for k in _SLIM_KEYS if k in m}
    if "note" in m:
        out["metric_note"] = m["note"]
    return out


def grouped_cv(X: pd.DataFrame, y: pd.Series, groups: pd.Series | None = None
               ) -> tuple[dict, pd.DataFrame]:
    """Stratified k-fold CV on *training* rows only, related rows kept together.

    ``groups`` (incident ids) -> StratifiedGroupKFold, so the events of one
    incident never sit in both a fit and a validation fold; ``None`` (one row
    per incident) -> StratifiedKFold. Classes with fewer than ``N_SPLITS``
    groups are excluded and recorded. Returns (summary, out-of-fold frame with
    ``y``, ``pred``, ``fold``).
    """
    g = (pd.Series(np.arange(len(y)), index=y.index) if groups is None
         else pd.Series(np.asarray(groups), index=y.index))
    per_class = g.groupby(y).nunique()
    big = per_class[per_class >= N_SPLITS].index
    dropped = sorted(map(str, per_class.index.difference(big)))
    res: dict = {"cv_kind": ("StratifiedKFold" if groups is None
                             else "StratifiedGroupKFold(groups=incident_id)")}
    if dropped:
        res["cv_excluded_classes"] = dropped
    if len(big) < 2:
        res["cv_note"] = f"skipped: fewer than 2 classes with >= {N_SPLITS} groups"
        return res, pd.DataFrame(columns=["y", "pred", "fold"])
    keep = y.isin(big).to_numpy()
    Xc, yc, gc = X[keep], y[keep], g[keep]
    if groups is None:
        cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True,
                             random_state=RANDOM_STATE)
        splits = cv.split(Xc, yc)
    else:
        cv = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True,
                                  random_state=RANDOM_STATE)
        splits = cv.split(Xc, yc, gc)
    t = time.perf_counter()
    pred = np.empty(len(yc), dtype=object)
    fold = np.full(len(yc), -1, dtype=int)
    scores = []
    for k, (tr, va) in enumerate(splits):
        clf = _build()
        clf.fit(Xc.iloc[tr], yc.iloc[tr])
        pred[va] = clf.predict(Xc.iloc[va])
        fold[va] = k
        scores.append(f1_score(yc.iloc[va], pred[va], average="macro",
                               zero_division=0))
    res.update(cv_f1_mean=float(np.mean(scores)), cv_f1_std=float(np.std(scores)),
               cv_folds=[round(float(s), 4) for s in scores],
               cv_n_rows=int(len(yc)), cv_time_s=round(time.perf_counter() - t, 4))
    oof = pd.DataFrame({"y": yc.to_numpy(), "pred": pred, "fold": fold},
                       index=yc.index)
    return res, oof


# --------------------------------------------------------------------------
# One streaming pass over the correlated events
# --------------------------------------------------------------------------
def scan_events(chunks: Iterable[pd.DataFrame], features: list[str],
                budget: int | None = None, seed: int = RANDOM_STATE) -> dict:
    """Split the Stage 3 event stream into everything Stage 4 needs.

    Every row gets ``event_id`` (its position in the stream). Returns the full
    test set (ids + features), per-(source, class) and per-class reservoir
    samples of *train* events, the train / test incident ids, exact train
    feature-vector hashes and split counts. Peak memory: the test set plus
    the reservoirs plus one chunk.
    """
    budget = max(1, budget or BUDGET.train_budget_per_class)
    rng = np.random.default_rng(seed)
    keep = ["event_id", "source", "incident_id", "split", "label"] + features
    by_source: dict[tuple[str, str], pd.DataFrame] = {}
    pooled: dict[str, pd.DataFrame] = {}
    test_parts, hashes, inc_tr, inc_te, counts = [], [], [], [], []
    offset = 0
    for chunk in chunks:
        if chunk.empty:
            continue
        if "split" not in chunk.columns:
            raise KeyError("events carry no Stage 2 'split' column")
        feature_matrix(chunk, features)          # raises on a missing feature
        chunk = chunk.assign(
            event_id=np.arange(offset, offset + len(chunk), dtype="int64"),
            source=chunk["source"].astype(str), label=chunk["label"].astype(str),
            split=chunk["split"].astype(str),
            incident_id=chunk["incident_id"].astype(str))
        offset += len(chunk)
        bad = set(chunk["split"]) - {"train", "test"}
        if bad:
            raise ValueError(f"unexpected split values {sorted(bad)}")
        counts.append(chunk.groupby(["split", "source", "label"]).size())
        sub = chunk[keep].assign(__p=rng.random(len(chunk)))
        sub[features] = sub[features].astype("float32")
        is_test = (chunk["split"] == "test").to_numpy()
        test_parts.append(sub[is_test].drop(columns="__p"))
        train = sub[~is_test]
        hashes.append(np.unique(_row_hash(train, features)))
        inc_tr.append(chunk.loc[~is_test, "incident_id"].unique())
        inc_te.append(chunk.loc[is_test, "incident_id"].unique())
        for (src, cls), grp in train.groupby(["source", "label"], sort=True):
            _reservoir_add(by_source, (src, cls), grp, budget)
        for cls, grp in train.groupby("label", sort=True):
            _reservoir_add(pooled, cls, grp, budget)
    if not offset:
        raise ValueError("no events to scan")

    per_source: dict[str, pd.DataFrame] = {}
    for src in sorted({s for s, _ in by_source}):
        per_source[src] = _finish_sample(
            [by_source[k] for k in sorted(by_source) if k[0] == src])
    # Hash-based set algebra (numpy's set routines are quadratic on strings).
    tr_ids = pd.Index(np.concatenate(inc_tr)).unique().sort_values()
    te_ids = pd.Index(np.concatenate(inc_te)).unique().sort_values()
    split_counts = (pd.concat(counts).groupby(level=[0, 1, 2]).sum()
                    .rename("events").reset_index())
    test = (pd.concat(test_parts, ignore_index=True) if test_parts
            else pd.DataFrame(columns=keep))
    return {
        "test": test,
        "train_by_source": per_source,
        "train_pooled": _finish_sample(list(pooled.values())) if pooled else None,
        "train_incidents": tr_ids.difference(te_ids).to_numpy(dtype=object),
        "test_incidents": te_ids.to_numpy(dtype=object),
        "mixed_incidents": tr_ids.intersection(te_ids).to_numpy(dtype=object),
        "train_hashes": np.unique(np.concatenate(hashes)) if hashes else np.array([]),
        "split_counts": split_counts,
        "n_events": offset,
    }


# --------------------------------------------------------------------------
# The two thesis conditions
# --------------------------------------------------------------------------
def train_fragmented_baseline(train_by_source: dict[str, pd.DataFrame],
                              test: pd.DataFrame, features: list[str],
                              do_cv: bool = True) -> tuple[dict, pd.Series]:
    """The baseline: one isolated model per source, no cross-source visibility.

    Each source's model is fitted once on its own train sample (event features
    only) and predicts every test event of that source. A source whose train
    sample holds one class predicts that class; a source with no train events
    at all raises no alert (predicts ``benign``). Both are scored like any
    other source. Returns (result, predictions aligned to ``test.index``).
    """
    pred = pd.Series(pd.NA, index=test.index, dtype=object)
    per_source: dict[str, dict] = {}
    oof_parts = []
    train_time = predict_time = 0.0
    n_train = n_rf = 0
    for src in sorted(set(train_by_source) | set(test["source"].unique())):
        tr = train_by_source.get(src)
        mask = (test["source"] == src).to_numpy()
        entry: dict = {}
        if tr is None or tr.empty:
            model, secs = ConstantModel(BENIGN), 0.0
            entry["note"] = "no train events: no-alert default (predicts benign)"
            trained = []
        else:
            X, y = feature_matrix(tr, features)
            model, secs = _fit(X, y)
            trained = sorted(y.unique().tolist())
            n_train += len(y)
            entry["n_train"] = int(len(y))
            entry["train_class_counts"] = y.value_counts().sort_index().to_dict()
            if isinstance(model, ConstantModel):
                entry["note"] = (f"single-class train sample ({model.label}): "
                                 "predicts it for every test event")
            else:
                n_rf += 1
            if do_cv and not isinstance(model, ConstantModel):
                # CV on this source's train sample only, grouped by incident.
                cv, oof = grouped_cv(X, y, tr["incident_id"])
                entry.update(cv)
                if len(oof):
                    oof_parts.append(oof.assign(source=src))
            entry["top_features"] = _importance(model, features, 10).to_dict(
                orient="records")
        train_time += secs
        if mask.any():
            t = time.perf_counter()
            pred[mask] = model.predict(feature_matrix(test[mask], features)[0])
            predict_time += time.perf_counter() - t
            entry.update(_slim(evaluate_split(test.loc[mask, "label"], pred[mask])))
        entry.update(n_test=int(mask.sum()), classes_trained=trained,
                     train_time_s=round(secs, 4))
        per_source[src] = entry
    if pred.isna().any():
        raise RuntimeError("baseline left test events unpredicted")

    res = evaluate_split(test["label"], pred)
    n_test = len(test)
    res.update(condition="fragmented", unit="event", features=list(features),
               n_features=len(features), n_sources=len(per_source),
               n_rf_models=n_rf,
               n_train=n_train, n_test=n_test,
               train_time_s=round(train_time, 4),
               predict_time_s=round(predict_time, 4),
               predict_us_per_event=round(1e6 * predict_time / max(1, n_test), 4),
               per_source=per_source)
    if oof_parts:
        # Pool fold k of every source into one fold-k score, so the baseline
        # has one CV figure over the same label space as the integrated model.
        oof = pd.concat(oof_parts)
        scores = [f1_score(g["y"].astype(str), g["pred"].astype(str),
                           average="macro", zero_division=0)
                  for _, g in oof.groupby("fold")]
        res.update(cv_f1_mean=float(np.mean(scores)),
                   cv_f1_std=float(np.std(scores)),
                   cv_folds=[round(float(s), 4) for s in scores],
                   cv_n_sources=int(oof["source"].nunique()),
                   cv_kind="per-source StratifiedGroupKFold(groups=incident_id); "
                           "fold k pooled across sources",
                   cv_sources_skipped=sorted(
                       k for k, v in per_source.items() if "cv_f1_mean" not in v))
    return res, pred


def train_integrated(incidents: pd.DataFrame, train_ids: np.ndarray,
                     test: pd.DataFrame, do_cv: bool = True,
                     save_model: bool = True) -> tuple[dict, pd.Series, dict]:
    """The proposed framework: one model over correlated incident features.

    Trained on a stratified sample of train incidents (target: the incident's
    majority label); every incident with a test event is then predicted and
    that *prediction* is propagated onto its member test events, which are
    scored against their own event labels. Returns (event-level result, event
    predictions aligned to ``test.index``, incident-level secondary result).
    """
    feats = list(INCIDENT_FEATURES)
    inc = incidents.assign(incident_id=incidents["incident_id"].astype(str))
    if not inc["incident_id"].is_unique:
        raise ValueError("duplicate incident ids in the incident table")
    is_train = inc["incident_id"].isin(train_ids)
    sample = stratified_sample(inc[is_train], BUDGET.train_budget_per_class)
    X, y = feature_matrix(sample, feats)
    model, train_time = _fit(X, y)

    test_ids = pd.unique(test["incident_id"])
    tinc = inc.set_index("incident_id").reindex(test_ids)
    if tinc["label"].isna().any():
        raise KeyError("test events reference incidents missing from the table")
    t = time.perf_counter()
    inc_pred = pd.Series(model.predict(feature_matrix(tinc, feats)[0]),
                         index=tinc.index, dtype=object)
    pred = test["incident_id"].map(inc_pred)
    predict_time = time.perf_counter() - t

    res = evaluate_split(test["label"], pred)
    res.update(condition="integrated", unit="event (incident prediction "
               "propagated to member events)", features=feats,
               n_features=len(feats), n_train=int(len(y)),
               train_class_counts=y.value_counts().sort_index().to_dict(),
               n_test=int(len(test)), n_test_incidents=int(len(tinc)),
               train_time_s=round(train_time, 4),
               predict_time_s=round(predict_time, 4),
               predict_us_per_event=round(1e6 * predict_time / max(1, len(test)), 4),
               feature_importance=_importance(model, feats))
    if do_cv:
        cv, _ = grouped_cv(X, y, None)
        res.update(cv)
    per_source = {}
    for src, idx in test.groupby("source", sort=True).groups.items():
        per_source[src] = _slim(evaluate_split(test.loc[idx, "label"],
                                               pred.loc[idx]))
    res["per_source"] = per_source

    level = evaluate_split(tinc["label"], inc_pred)
    level.update(unit="incident (target: incident majority label)",
                 n_test_incidents=int(len(tinc)))
    if save_model:
        Path(MODELS).mkdir(parents=True, exist_ok=True)
        import joblib
        joblib.dump(model, Path(MODELS) / "rf_integrated.joblib", compress=3)
        pd.Series(feats).to_csv(Path(MODELS) / "rf_integrated_features.csv",
                                index=False, header=["feature"])
    return res, pred, level


# --------------------------------------------------------------------------
# Diagnostics (not thesis conditions)
# --------------------------------------------------------------------------
def _join_incident(df: pd.DataFrame, incidents: pd.DataFrame) -> pd.DataFrame:
    ctx = (incidents.assign(incident_id=incidents["incident_id"].astype(str))
           .set_index("incident_id")[list(ENRICH_FEATURES)])
    add = ctx.reindex(df["incident_id"].astype(str))
    if add.isna().any().any():
        raise KeyError("events reference incidents missing from the table")
    return df.assign(**{c: add[c].to_numpy() for c in ENRICH_FEATURES})


def _diagnostic_model(name: str, train: pd.DataFrame, test: pd.DataFrame,
                      features: list[str]) -> tuple[dict, pd.Series]:
    X, y = feature_matrix(train, features)
    model, secs = _fit(X, y)
    t = time.perf_counter()
    pred = pd.Series(model.predict(feature_matrix(test, features)[0]),
                     index=test.index, dtype=object)
    ptime = time.perf_counter() - t
    res = evaluate_split(test["label"], pred)
    res.update(condition=name, features=list(features), n_train=int(len(y)),
               n_test=int(len(test)), train_time_s=round(secs, 4),
               predict_time_s=round(ptime, 4),
               feature_importance=_importance(model, features).to_dict(
                   orient="records"))
    return res, pred


def run_stage4(event_chunks: Iterable[pd.DataFrame], incidents: pd.DataFrame,
               features: list[str] | None = None, do_cv: bool = True,
               diagnostics: bool = True, save_model: bool = True
               ) -> tuple[dict, pd.DataFrame]:
    """Train and score both conditions (plus diagnostics) on one test set.

    Returns (results dict, per-event prediction frame with ``event_id``,
    ``source``, ``incident_id``, ``split``, ``label`` and one ``pred_*``
    column per model).
    """
    features = check_features(features if features is not None
                              else event_features())
    t = time.perf_counter()
    scan = scan_events(event_chunks, features)
    scan_time = time.perf_counter() - t
    test = scan["test"]
    if test.empty:
        raise ValueError("no test events")

    frag, frag_pred = train_fragmented_baseline(
        scan["train_by_source"], test, features, do_cv=do_cv)
    integ, integ_pred, inc_level = train_integrated(
        incidents, scan["train_incidents"], test, do_cv=do_cv,
        save_model=save_model)
    # The comparison is only valid on identical events in identical order.
    if not (frag_pred.index.equals(test.index)
            and integ_pred.index.equals(test.index)):
        raise AssertionError("conditions were not scored on the same events")
    frag["scan_time_s"] = integ["scan_time_s"] = round(scan_time, 4)

    preds = test[["event_id", "source", "incident_id", "split", "label"]].copy()
    preds["pred_fragmented"] = frag_pred.astype(str).to_numpy()
    preds["pred_integrated"] = integ_pred.astype(str).to_numpy()

    inc_ids = incidents["incident_id"].astype(str)
    inc_label = incidents.assign(incident_id=inc_ids).set_index("incident_id")["label"]
    split_info = {
        "strategy": "Stage 2 hash of the Stage 3 correlation group key "
                    "(source, rule, src_ip, dst_ip, proto, floor(ts/window)); "
                    "uncorrelatable rows hashed individually",
        "n_events": int(scan["n_events"]),
        "events": scan["split_counts"].to_dict(orient="records"),
        "n_train_incidents": int(len(scan["train_incidents"])),
        "n_test_incidents": int(len(scan["test_incidents"])),
        "n_mixed_incidents": int(len(scan["mixed_incidents"])),
        "train_incidents_by_class": inc_label.reindex(scan["train_incidents"])
        .value_counts().sort_index().to_dict(),
        "test_incidents_by_class": inc_label.reindex(scan["test_incidents"])
        .value_counts().sort_index().to_dict(),
    }
    out = {"model_config": model_config(), "split": split_info,
           "fragmented": frag, "integrated": integ,
           "integrated_incident_level": inc_level}

    if diagnostics:
        diag: dict = {"note": "diagnostic ablations on the same test events; "
                              "NOT the thesis conditions"}
        pooled = scan["train_pooled"]
        diag["pooled_event_model"], p = _diagnostic_model(
            "pooled_event_model", pooled, test, features)
        preds["pred_pooled"] = p.astype(str).to_numpy()
        enr = features + list(ENRICH_FEATURES)
        diag["enriched_event_model"], p = _diagnostic_model(
            "enriched_event_model", _join_incident(pooled, incidents),
            _join_incident(test, incidents), enr)
        preds["pred_enriched"] = p.astype(str).to_numpy()

        dup = np.isin(_row_hash(test, features), scan["train_hashes"])
        by_class = pd.Series(dup).groupby(test["label"].to_numpy()).agg(
            ["mean", "sum", "size"])
        novel = ~dup
        diag["duplicates"] = {
            "definition": "test event whose exact event-feature vector also "
                          "occurs among train events",
            "fraction_all": float(dup.mean()),
            "by_class": {c: {"fraction": float(r["mean"]), "n_dup": int(r["sum"]),
                             "n": int(r["size"])} for c, r in by_class.iterrows()},
            "n_novel": int(novel.sum()),
            "novel_only_metrics": {
                col[5:]: _slim(evaluate_split(preds.loc[novel, "label"],
                                              preds.loc[novel, col]))
                for col in preds.columns if col.startswith("pred_")},
        }
        out["diagnostics"] = diag
    return out, preds
