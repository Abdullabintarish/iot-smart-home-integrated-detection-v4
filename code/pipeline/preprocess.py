"""Stage 2 - Data preprocessing and log normalisation.

Applies the transformations named in section 3.2, all chunk-at-a-time:

  1. drop missing (all-empty) and duplicate rows
  2. label-encode categorical features (vocabulary = union over train rows)
  3. MinMax-normalise numeric features (global train min/max)
  4. remove constant / low-variance features (global scaled variance)
  5. correlation analysis: remove redundant numeric features whose pairwise
     |Pearson r| >= REDUNDANCY_THRESHOLD (``FEATURE_SELECTION="redundancy"``),
     or - for comparison - keep numeric features correlated with the label
     code (``"label_pearson"``)

Every row is first assigned to a deterministic "train" / "test" split
(``assign_split``), hashed per Stage 3 correlation group so related events
never straddle the two. ``fit`` learns every statistic from train rows only, so
nothing label-dependent is learnt from held-out rows. ``fit`` streams the
corpus twice (column roles, then moments / vocabularies); ``transform``
streams it once more to emit clean shards. Peak memory is one chunk plus
k x k moment matrices, not one corpus.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence, Union

import numpy as np
import pandas as pd

from .config import (BUDGET, CLASSES, DATA_INT, DATA_OUT, DROP_COLUMNS,
                     FEATURE_SELECTION, ID_COLUMNS, LEAKAGE_COLUMNS,
                     LOW_VARIANCE_THRESHOLD, MIN_CORR_WITH_LABEL,
                     MISSING_SENTINEL, REDUNDANCY_THRESHOLD, TEST_FRACTION,
                     VARIANCE_FLOOR)
from .correlate import correlation_key
from .io_utils import iter_parquet

log = logging.getLogger(__name__)

NA_TOKEN = "__NA__"            # vocabulary entry for a missing categorical value
NUMERIC_SHARE = 0.9            # share of non-null values that must parse as numbers
CARRY_COLUMNS = ("src_ip", "dst_ip", "source", "ts")
SPLIT_KEY = ("source", "ts", "src_ip", "dst_ip", "sport", "dport", "proto")
PLAN_COLUMNS = ("feature", "role", "n_present", "missing_frac", "global_min",
                "global_max", "scaled_variance", "abs_corr_with_label",
                "redundant_with", "redundancy_r", "decision", "reason")

# fit() needs several passes, so it takes a re-iterable (list of chunks) or a
# zero-argument callable returning a fresh chunk iterator.
ChunkSource = Union[Callable[[], Iterable[pd.DataFrame]], Sequence[pd.DataFrame]]


class ColumnPlan:
    """Which columns survive, plus the encoders needed to apply the plan."""

    def __init__(self) -> None:
        self.numeric: list[str] = []
        self.categorical: list[str] = []
        self.categories: dict[str, list[str]] = {}
        self.kept: list[str] = []
        self.dropped: list[str] = []
        self.correlations: dict[str, float] = {}   # |r(feature, label code)|
        self.mins: dict[str, float] = {}
        self.maxs: dict[str, float] = {}
        self.label_codes: dict[str, int] = {}
        self.method: str = FEATURE_SELECTION
        self.redundancy: pd.DataFrame = pd.DataFrame()  # pairwise |r| matrix
        self.row_counts: dict[str, int] = {}
        self.excluded: dict[str, str] = {}             # column -> reason
        self.rows: dict[str, dict] = {}                # feature -> plan row

    def summary(self) -> pd.DataFrame:
        rows = list(self.rows.values())
        rows += [{"feature": c, "role": "excluded", "decision": "excluded",
                  "reason": r} for c, r in self.excluded.items()]
        out = pd.DataFrame(rows, columns=list(PLAN_COLUMNS))
        out["n_present"] = out["n_present"].astype("Int64")
        return out


def _numeric(s: pd.Series) -> pd.Series:
    """Coerce to float64; unparseable text and +/-inf become NaN."""
    x = s if pd.api.types.is_numeric_dtype(s) else pd.to_numeric(s, errors="coerce")
    return x.astype("float64").replace([np.inf, -np.inf], np.nan)


def _as_str(s: pd.Series) -> pd.Series:
    """Categorical view of a column: strings, missing -> NA_TOKEN."""
    return s.astype("string").fillna(NA_TOKEN).astype(object)


def assign_split(df: pd.DataFrame, offsets: dict[str, int] | None = None,
                 test_fraction: float | None = None) -> pd.Series:
    """Mark each row "train" or "test" by a stable blake2b hash.

    The key is Stage 3's correlation group key (source, rule, src_ip, dst_ip,
    proto, ts bucket; ``correlate.correlation_key``), so related events - one
    future incident - always share a split. Rows Stage 3 cannot correlate (no
    timestamp, or neither IP) fall back to the flow tuple plus the row's
    position within its source. ``offsets`` carries each source's running row
    count across chunks (updated in place) so the split does not depend on
    chunk boundaries.
    """
    offsets = {} if offsets is None else offsets
    if df.empty:
        return pd.Series([], index=df.index, dtype=object)
    blank = pd.Series("", index=df.index, dtype="string")
    src = df["source"].astype("string").fillna("") if "source" in df else blank
    start = src.map(offsets).fillna(0).astype("int64")
    pos = src.groupby(src, sort=False).cumcount().astype("int64") + start
    for s, c in src.value_counts(sort=False).items():
        offsets[s] = offsets.get(s, 0) + int(c)
    parts = [df[c].astype("string").fillna("") if c in df else blank
             for c in SPLIT_KEY[1:]] + [pos.astype("string")]
    row_key = "row|" + src.str.cat(parts, sep="|")
    group_key, _, _ = correlation_key(df)
    key = ("group|" + group_key).fillna(row_key)
    frac = TEST_FRACTION if test_fraction is None else test_fraction
    cut = int(frac * 2 ** 64)
    is_test = [int.from_bytes(hashlib.blake2b(k.encode("utf-8"), digest_size=8)
                              .digest(), "big") < cut for k in key]
    return pd.Series(np.where(is_test, "test", "train"), index=df.index)


def _clean_chunk(df: pd.DataFrame, counts: dict[str, int] | None = None
                 ) -> pd.DataFrame:
    """Step 1 (and stable column naming); the original index is preserved."""
    counts = {} if counts is None else counts
    n0 = len(df)
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(how="all")
    n1 = len(df)
    df = df.drop_duplicates()
    counts["rows_in"] = counts.get("rows_in", 0) + n0
    counts["dropped_all_nan"] = counts.get("dropped_all_nan", 0) + n0 - n1
    counts["dropped_duplicate"] = counts.get("dropped_duplicate", 0) + n1 - len(df)
    df = df.loc[:, ~df.columns.duplicated()]
    # Identifier/text noise that cannot generalise across sources.
    df = df.drop(columns=[c for c in DROP_COLUMNS if c in df.columns], errors="ignore")
    # Wall-clock times, row counters and the raw label columns leak the answer.
    df = df.drop(columns=[c for c in LEAKAGE_COLUMNS if c in df.columns],
                 errors="ignore")
    return df


def _prepare(raw: pd.DataFrame, offsets: dict[str, int],
             counts: dict[str, int] | None = None) -> pd.DataFrame:
    """Split-tag the raw rows, then clean; ``split`` is joined back by index.

    The split is computed before cleaning (positions count raw rows) and kept
    out of duplicate detection.
    """
    raw = raw.drop(columns=["split"], errors="ignore").reset_index(drop=True)
    split = assign_split(raw, offsets)
    df = _clean_chunk(raw, counts)
    df["split"] = split.loc[df.index]
    return df


def _features(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in ID_COLUMNS]


def _passes(chunks: ChunkSource) -> Callable[[], Iterable[pd.DataFrame]]:
    if callable(chunks):
        return chunks
    if iter(chunks) is chunks:
        raise TypeError("fit() needs a re-iterable or a callable, not an iterator")
    return lambda: chunks


def _pearson(n, sx, sy, sxx, syy, sxy):
    """r = (n.Sxy - Sx.Sy) / sqrt((n.Sxx - Sx^2)(n.Syy - Sy^2)); NaN if undefined."""
    with np.errstate(divide="ignore", invalid="ignore"):
        vx = n * sxx - sx * sx
        vy = n * syy - sy * sy
        r = (n * sxy - sx * sy) / np.sqrt(vx * vy)
        ok = (n >= 2) & (vx > 0) & (vy > 0)
    return np.where(ok, np.clip(r, -1.0, 1.0), np.nan)


def fit(chunks: ChunkSource, method: str | None = None,
        label_order: Sequence[str] | None = None) -> ColumnPlan:
    """Learn the normalisation/selection plan from train rows only.

    Pass 1 fixes each column's role (numeric if >= 90 % of its non-null train
    values parse as numbers), the label vocabulary and per-column mean/min/max.
    Pass 2 accumulates, over rows where a column is present, moments centred
    on the pass-1 mean (numerically stable for 1e9-scale values) and the
    categorical vocabularies. ``label_order`` overrides the label -> code order
    (default: sorted CLASSES plus any extra labels) for diagnostics.
    """
    plan = ColumnPlan()
    plan.method = method or FEATURE_SELECTION
    if plan.method not in ("redundancy", "label_pearson"):
        raise ValueError(f"unknown FEATURE_SELECTION {plan.method!r}")
    stream = _passes(chunks)

    # ---- pass 1: roles, label vocabulary, mean / min / max ---------------
    order: list[str] = []
    role_n: dict[str, list[int]] = {}       # col -> [non_null, parses_numeric]
    xs: dict[str, list[float]] = {}         # col -> [n, sum, min, max]
    labels: dict[str, int] = {}
    n_train = 0
    offsets: dict[str, int] = {}
    for raw in stream():
        for c in raw.columns:
            if c in LEAKAGE_COLUMNS or c in DROP_COLUMNS:
                plan.excluded.setdefault(
                    c, "leakage column" if c in LEAKAGE_COLUMNS
                    else "identifier/noise column")
        df = _prepare(raw, offsets, plan.row_counts)
        plan.row_counts["train"] = plan.row_counts.get("train", 0) + int(
            (df["split"] == "train").sum())
        plan.row_counts["test"] = plan.row_counts.get("test", 0) + int(
            (df["split"] == "test").sum())
        df = df[df["split"] == "train"]
        if df.empty:
            continue
        n_train += len(df)
        for lab, c in df["label"].astype(str).value_counts(sort=False).items():
            labels[lab] = labels.get(lab, 0) + int(c)
        for col in _features(df):
            if col not in role_n:
                order.append(col)
                role_n[col] = [0, 0]
                xs[col] = [0.0, 0.0, np.inf, -np.inf]
            s = df[col]
            x = _numeric(s)
            role_n[col][0] += int(s.notna().sum())
            role_n[col][1] += int(x.notna().sum())
            v = x.dropna()
            if len(v):
                a = xs[col]
                a[0] += len(v)
                a[1] += float(v.sum())
                a[2] = min(a[2], float(v.min()))
                a[3] = max(a[3], float(v.max()))
    plan.row_counts["train_rows_fitted"] = n_train

    for col in order:
        nn, parsed = role_n[col]
        if nn and parsed >= NUMERIC_SHARE * nn:
            plan.numeric.append(col)
        elif nn:
            plan.categorical.append(col)
        else:
            plan.numeric.append(col)    # no train values at all; dropped below

    # Fixed label -> code mapping, identical for every chunk.
    names = list(label_order) if label_order is not None else sorted(
        set(CLASSES) | set(labels))
    names += sorted(set(labels) - set(names))
    plan.label_codes = {lab: i for i, lab in enumerate(names)}
    n_lab = sum(labels.values())
    y_mean = (sum(plan.label_codes[k] * v for k, v in labels.items()) / n_lab
              if n_lab else 0.0)

    # ---- pass 2: centred moments over present rows, vocabularies ---------
    num = plan.numeric
    k = len(num)
    mean = np.array([xs[c][1] / xs[c][0] if xs[c][0] else 0.0 for c in num])
    N = np.zeros((k, k)); S = np.zeros((k, k)); Q = np.zeros((k, k))
    P = np.zeros((k, k))
    Sy = np.zeros(k); Syy = np.zeros(k); Sxy = np.zeros(k)
    vocab: dict[str, set[str]] = {c: set() for c in plan.categorical}
    offsets = {}
    for raw in stream():
        df = _prepare(raw, offsets)
        df = df[df["split"] == "train"]
        if df.empty:
            continue
        X = np.full((len(df), k), np.nan)
        for j, col in enumerate(num):
            if col in df.columns:
                X[:, j] = _numeric(df[col]).to_numpy()
        M = (~np.isnan(X)).astype("float64")
        D = np.where(M > 0, X - mean, 0.0)
        y = df["label"].astype(str).map(plan.label_codes).to_numpy("float64") - y_mean
        N += M.T @ M            # N[i,j] = rows where i and j are both present
        S += D.T @ M            # S[i,j] = sum of d_i over those rows
        Q += (D * D).T @ M      # Q[i,j] = sum of d_i^2 over those rows
        P += D.T @ D            # P[i,j] = sum of d_i * d_j
        Sy += M.T @ y
        Syy += M.T @ (y * y)
        Sxy += D.T @ y
        for col in plan.categorical:
            if col in df.columns:
                vocab[col].update(df[col].dropna().astype("string").unique().tolist())

    # ---- statistics ------------------------------------------------------
    n = np.diag(N)
    r_label = _pearson(n, np.diag(S), Sy, np.diag(Q), Syy, Sxy)
    r_pair = _pearson(N, S, S.T, Q, Q.T, P)
    plan.redundancy = pd.DataFrame(np.abs(r_pair), index=num, columns=num)
    with np.errstate(divide="ignore", invalid="ignore"):
        var = np.where(n > 0, np.diag(Q) / n - (np.diag(S) / n) ** 2, np.nan)

    candidates: list[str] = []
    for j, col in enumerate(num):
        cnt, _, lo, hi = xs[col]
        rng = hi - lo if cnt else 0.0
        if cnt:
            plan.mins[col], plan.maxs[col] = lo, hi
        sv = float(max(var[j], 0.0) / rng ** 2) if rng >= VARIANCE_FLOOR else 0.0
        rl = float(abs(r_label[j]))
        if np.isfinite(rl):
            plan.correlations[col] = rl
        row = {"feature": col, "role": "numeric", "n_present": int(cnt),
               "missing_frac": 1.0 - cnt / n_train if n_train else 1.0,
               "global_min": lo if cnt else np.nan,
               "global_max": hi if cnt else np.nan,
               "scaled_variance": sv, "abs_corr_with_label": rl,
               "redundant_with": "", "redundancy_r": np.nan}
        if cnt < 2 or rng < VARIANCE_FLOOR:
            row.update(decision="dropped", reason="constant (or absent) in train")
        elif sv <= LOW_VARIANCE_THRESHOLD:
            row.update(decision="dropped",
                       reason=f"scaled variance <= {LOW_VARIANCE_THRESHOLD}")
        else:
            row.update(decision="kept", reason="")
            candidates.append(col)
        plan.rows[col] = row

    if plan.method == "redundancy":
        # Greedy, deterministic: fewer missing values first, then by name; a
        # feature is dropped if it is redundant with one already kept.
        idx = {c: j for j, c in enumerate(num)}
        kept_num: list[str] = []
        for col in sorted(candidates, key=lambda c: (-xs[c][0], c)):
            hits = [(abs(r_pair[idx[col], idx[o]]), o) for o in kept_num
                    if abs(r_pair[idx[col], idx[o]]) >= REDUNDANCY_THRESHOLD]
            if hits:
                r, o = max(hits, key=lambda h: (h[0], h[1]))
                plan.rows[col].update(
                    decision="dropped", redundant_with=o, redundancy_r=r,
                    reason=f"redundant: |r| >= {REDUNDANCY_THRESHOLD}")
            else:
                kept_num.append(col)
                plan.rows[col]["reason"] = "not redundant"
    else:
        for col in candidates:
            rl = plan.rows[col]["abs_corr_with_label"]
            if np.isfinite(rl) and rl >= MIN_CORR_WITH_LABEL:
                plan.rows[col]["reason"] = f"|r(label)| >= {MIN_CORR_WITH_LABEL}"
            else:
                plan.rows[col].update(
                    decision="dropped", reason=f"|r(label)| < {MIN_CORR_WITH_LABEL}")

    for col in plan.categorical:
        cats = sorted(vocab[col])
        plan.categories[col] = sorted(set(cats) | {NA_TOKEN})
        row = {"feature": col, "role": "categorical",
               "n_present": role_n[col][0],
               "missing_frac": 1.0 - role_n[col][0] / n_train if n_train else 1.0,
               "global_min": np.nan, "global_max": np.nan,
               "scaled_variance": np.nan, "abs_corr_with_label": np.nan,
               "redundant_with": "", "redundancy_r": np.nan}
        if len(cats) <= 1:
            row.update(decision="dropped", reason="constant (or absent) in train")
        else:
            row.update(decision="kept", reason=f"{len(cats)} categories")
        plan.rows[col] = row

    plan.kept = [c for c in order if plan.rows[c]["decision"] == "kept"]
    plan.dropped = [c for c in order if plan.rows[c]["decision"] == "dropped"]
    plan.rows = {c: plan.rows[c] for c in order}
    return plan


def transform(chunks: Iterable[pd.DataFrame], plan: ColumnPlan,
              counts: dict[str, int] | None = None) -> Iterator[pd.DataFrame]:
    """Second streaming pass: steps 2-3 applied, plan's columns emitted.

    Every row (train and test) is emitted with its ``split``. Numeric values
    are scaled with the train min/max, so test values may fall outside [0, 1];
    missing / absent numeric values become MISSING_SENTINEL. Categories unseen
    in train encode to -1.
    """
    offsets: dict[str, int] = {}
    for raw in chunks:
        df = _prepare(raw, offsets, counts)
        if df.empty:
            continue
        out = pd.DataFrame(index=df.index)
        for col in plan.kept:
            s = df[col] if col in df.columns else pd.Series(np.nan, index=df.index)
            if col in plan.numeric:
                # 3. MinMax normalisation with the global (train) range.
                lo, hi = plan.mins[col], plan.maxs[col]
                out[col] = ((_numeric(s) - lo) / (hi - lo)).fillna(MISSING_SENTINEL)
            else:
                # 2. Label encoding, using the fitted vocabulary.
                mapping = {c: i for i, c in enumerate(plan.categories[col])}
                out[col] = _as_str(s).map(mapping).fillna(-1).astype("int32")

        # Identifiers, label and split are carried through on the same index.
        for col in CARRY_COLUMNS:
            if col in df.columns:
                out[col] = df[col]
        out["label"] = df["label"].astype(str)
        out["split"] = df["split"]
        yield out.reset_index(drop=True)


def preprocess(source_dir: Path, shard_dir: Path = DATA_INT
               ) -> tuple[ColumnPlan, list[Path]]:
    """Full Stage 2 over every staged shard in ``source_dir``."""
    shards = sorted(Path(source_dir).glob("*.parquet"))
    if not shards:
        raise FileNotFoundError(f"no staged shards in {source_dir}")

    def stream():
        for s in shards:
            yield from iter_parquet(s, batch_size=BUDGET.csv_chunksize)

    plan = fit(stream)
    log.info("stage2 rows: %s", plan.row_counts)
    out_dir = DATA_OUT / "stage2"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.parquet"):
        old.unlink()
    # Sequentially numbered shards: file order == stream order.
    buf: list[pd.DataFrame] = []
    buffered = 0
    written: list[Path] = []

    def flush() -> None:
        path = out_dir / f"stage2_{len(written):04d}.parquet"
        pd.concat(buf, ignore_index=True).to_parquet(path, index=False)
        written.append(path)

    for chunk in transform(stream(), plan):
        buf.append(chunk)
        buffered += len(chunk)
        if buffered >= BUDGET.flush_rows:
            flush()
            buf, buffered = [], 0
    if buf:
        flush()
    plan.summary().to_csv(DATA_OUT / "stage2_feature_plan.csv", index=False)
    return plan, written
