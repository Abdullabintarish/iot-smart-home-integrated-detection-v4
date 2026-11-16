"""Rich incident summaries for experiment E1 (label-free, per partition).

Groups are exactly those of experiments/ablation/run_ablation.incident_context:
the pipeline's correlation key plus the event's split, so no group crosses
train and test; uncorrelatable events are their own group. Every value is a
statistic of non-label columns of the group's own events. The label column is
never read.

Stored feature values are the Stage-2 encodings: numeric features MinMax-scaled
with the training range, categorical features integer codes. MISSING_SENTINEL
(-1) marks a missing numeric value or an unseen category. A categorical
column's ``__NA__`` code (the field is absent from a dataset) is not saved by
Stage 2; it is recovered as the one code that every event of a dataset carries
for that column (see ``na_codes``) and is also treated as missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ablation"))
import run_ablation as R  # noqa: E402  (unchanged original)

C = R.C
correlation_key = R.correlation_key
MISSING = float(C.MISSING_SENTINEL)
FILL = MISSING                      # value when a group has no observed value
DISTINCT = (("dport", "dst_port"), ("sport", "src_port"), ("dst_ip", "dst_ip"),
            ("proto", "proto"))
PORTS = ("sport", "dport")          # identifiers of a service: counted, not averaged
MAX_SHARE_CATEGORIES = 16           # above this, top share + distinct count
STATS = ("mean", "std", "min", "max", "median", "sum")
FORBIDDEN = ("label", "is_attack", "incident_id", "event_id")


def group_codes(df: pd.DataFrame, window_s: int) -> np.ndarray:
    """Group id per event, identical to run_ablation.incident_context."""
    key, _, _ = correlation_key(df, window_s=window_s)
    key = key.astype("string") + "|" + df["split"].astype("string")
    codes, uniques = pd.factorize(key)
    codes = codes.astype("int64")
    lonely = codes < 0
    codes[lonely] = len(uniques) + np.arange(lonely.sum())
    return codes


def dataset_of(source: pd.Series) -> np.ndarray:
    return np.where(source.astype(str).str.startswith("data_"), "botiot", "iot23")


def na_codes(df: pd.DataFrame, categorical: list[str]) -> dict[str, float]:
    """Code a dataset carries on *every* event for a column = absent field."""
    ds = dataset_of(df["source"])
    out = {}
    for c in categorical:
        for d in np.unique(ds):
            v = df[c].to_numpy()[ds == d]
            u = np.unique(v)
            if len(u) == 1 and u[0] != MISSING and len(np.unique(df[c].to_numpy())) > 1:
                out[c] = float(u[0])
    return out


def feature_roles(plan_path: Path, features: list[str]) -> dict[str, str]:
    plan = pd.read_csv(plan_path).set_index("feature")["role"]
    return {f: str(plan.get(f, "numeric")) for f in features}


def category_sets(df: pd.DataFrame, categorical: list[str], na: dict[str, float],
                  train_mask: np.ndarray) -> dict[str, list[float]]:
    """Observed categories per column, from training events only."""
    out = {}
    for c in categorical:
        v = df[c].to_numpy()[train_mask]
        v = v[(v != MISSING) & (v != na.get(c, np.nan))]
        out[c] = sorted(float(x) for x in np.unique(v))
    return out


def rich_incident_context(df: pd.DataFrame, window_s: int, features: list[str],
                          roles: dict[str, str], categories: dict[str, list[float]],
                          na: dict[str, float]) -> pd.DataFrame:
    """One row per event: its group's rich summary (see FEATURES.md)."""
    bad = [c for c in features if c in FORBIDDEN]
    if bad:
        raise ValueError(f"label or id columns requested as features: {bad}")
    codes = group_codes(df, window_s)
    ng = int(codes.max()) + 1 if len(codes) else 0
    cols: dict[str, np.ndarray] = {}

    thin = R.incident_context(df, window_s)
    for c in R.INCIDENT:
        cols[c] = thin[c].to_numpy("float32")

    def per_event(v: np.ndarray) -> np.ndarray:
        return v[codes].astype("float32")

    for col, name in DISTINCT:
        if col not in df.columns or (col in roles and col not in features):
            continue
        s = df[col]
        ok = s.notna().to_numpy().copy()
        if pd.api.types.is_numeric_dtype(s):
            ok &= s.to_numpy() != MISSING
        if col in na:
            ok &= s.to_numpy() != na[col]
        n = pd.Series(s.to_numpy()[ok]).groupby(codes[ok]).nunique()
        cols[f"n_distinct_{name}"] = per_event(n.reindex(range(ng), fill_value=0).to_numpy())

    numeric = [f for f in features if roles.get(f) == "numeric" and f not in PORTS]
    for f in numeric:
        v = df[f].to_numpy("float64")
        ok = v != MISSING
        g = pd.Series(v[ok]).groupby(codes[ok])
        agg = {"mean": g.mean(), "std": g.std(ddof=0), "min": g.min(), "max": g.max(),
               "median": g.median(), "sum": g.sum()}
        for st in STATS:
            cols[f"{f}_{st}"] = per_event(agg[st].reindex(range(ng)).fillna(FILL).to_numpy())

    for f in [f for f in features if roles.get(f) == "categorical"]:
        v = df[f].to_numpy("float64")
        ok = (v != MISSING) & (v != na.get(f, np.nan))
        nobs = np.bincount(codes[ok], minlength=ng).astype("float64")
        cats = categories.get(f, [])
        if len(cats) <= MAX_SHARE_CATEGORIES:
            for cat in cats:
                hit = ok & (v == cat)
                k = np.bincount(codes[hit], minlength=ng)
                share = np.where(nobs > 0, k / np.maximum(nobs, 1), FILL)
                cols[f"{f}_share_{int(cat)}"] = per_event(share)
        else:
            cnt = pd.Series(1, index=pd.MultiIndex.from_arrays([codes[ok], v[ok]])
                            ).groupby(level=[0, 1]).size()
            top = cnt.groupby(level=0).max().reindex(range(ng), fill_value=0).to_numpy()
            cols[f"{f}_top_share"] = per_event(np.where(nobs > 0, top / np.maximum(nobs, 1), FILL))
        if f in dict(DISTINCT):
            continue                                   # already counted above
        nd = pd.Series(v[ok]).groupby(codes[ok]).nunique()
        cols[f"n_distinct_{f}"] = per_event(nd.reindex(range(ng), fill_value=0).to_numpy())

    out = pd.DataFrame(cols, index=df.index)
    out.attrs["n_groups"] = ng
    return out
