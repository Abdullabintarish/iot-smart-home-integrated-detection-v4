"""Stage 3 - Event correlation and information integration.

This is the stage the thesis is actually about, so it is implemented as a real
rule-based correlator rather than a label passthrough.

Alerts are unified into **incidents** using the keys named in section 3.2,
taking the first rule whose fields are present:

  R1_pair_proto  (src_ip, dst_ip, proto) - one conversation, many packets
  R2_src_proto   (src_ip, proto)          - one host's behaviour (no dst_ip)
  R3_dst_proto   (dst_ip, proto)          - fan-out against a target (no src_ip)
  R0_singleton   no timestamp, or neither IP present: never grouped

Events match into the same incident when they share a key *and* fall inside the
same tumbling ``CORRELATION_WINDOW_S`` bucket (``floor(ts / window)``). With
``CORRELATION_SCOPE = "source"`` the key also contains the event's source
capture, so independently recorded captures are never merged. A missing,
``__NA__`` (code 0) or unseen (code -1) protocol is keyed as ``"unknown"``; it
only ever matches together with the IP fields, never on its own.

The incident id is a pure function of (scope, rule, key, bucket) - no chunk
salt - and incident summaries are merged from per-chunk partial aggregates, so
the result is identical whatever the batch size.

Each incident is summarised into a feature vector (event count, span, rate,
distinct sources / endpoints); that table is what Stage 4 trains on for the
integrated condition. Label-derived statistics (purity, entropy) go to a
separate diagnostics table so they can never become model features, and event
rows carry no correlation-derived numeric column.

The baseline condition in Stage 5 deliberately skips all of this.
"""
from __future__ import annotations

import hashlib
from typing import Iterator

import numpy as np
import pandas as pd

from .config import (CORRELATION_RULES, CORRELATION_SCOPE, CORRELATION_WINDOW_S,
                     DATA_OUT, SINGLETON_RULE)

_ID_SALT = "iot23-botiot-corr-v2"
_SEP = "\x1f"                    # key separator; cannot occur in IPs or protos
UNKNOWN = "unknown"
# Text values that mean "absent" in an IP / protocol column.
_MISSING_TEXT = {"", "-", "nan", "none", "null", "<na>", "unknown", "__na__"}
# Stage 2 label-encodes proto: 0 = __NA__ (missing), -1 = unseen in train.
_PROTO_MISSING_CODES = (0, -1)

# The numeric incident features - the only columns the integrated model may
# use (Stage 4 selects exactly these; see detect.feature_matrix).
INCIDENT_FEATURES = ("n_events", "n_sources", "n_src_ips", "n_dst_ips",
                     "span_s", "events_per_s", "cross_source")
# Incident feature table: identifiers, the features above, and the target.
INCIDENT_COLUMNS = (["incident_id", "source", "corr_rule"]
                    + list(INCIDENT_FEATURES) + ["label", "is_attack"])
# Audit-only table: ground-truth statistics and raw keys. Never a feature.
DIAGNOSTIC_COLUMNS = ["incident_id", "first_row", "source", "corr_rule",
                      "src_ip", "dst_ip", "proto", "ts_first", "ts_last",
                      "n_events", "label", "n_labels", "label_purity",
                      "label_entropy", "label_counts", "n_train_events",
                      "n_test_events"]


def _incident_id(key: str) -> str:
    h = hashlib.blake2b(digest_size=8)
    h.update(_ID_SALT.encode())
    h.update(key.encode())
    return h.hexdigest()


def _ident(df: pd.DataFrame, name: str) -> pd.Series:
    """Identifier column as stripped strings; absent values become <NA>."""
    if name not in df.columns:
        return pd.Series(pd.NA, index=df.index, dtype="string")
    s = df[name].astype("string").str.strip()
    return s.mask(s.isna() | s.str.lower().isin(_MISSING_TEXT))


def _proto(df: pd.DataFrame) -> pd.Series:
    """Protocol token; missing / __NA__ / unseen codes all become "unknown"."""
    if "proto" not in df.columns:
        return pd.Series(UNKNOWN, index=df.index, dtype="string")
    p = df["proto"]
    if pd.api.types.is_numeric_dtype(p):
        num = pd.to_numeric(p, errors="coerce")
        tok = num.astype("Int64").astype("string")
        tok = tok.mask(num.isin(_PROTO_MISSING_CODES))
    else:
        tok = _ident(df, "proto").str.lower()
    return tok.fillna(UNKNOWN)


def correlation_key(df: pd.DataFrame, window_s: int = CORRELATION_WINDOW_S,
                    scope: str = CORRELATION_SCOPE
                    ) -> tuple[pd.Series, np.ndarray, pd.Series]:
    """Grouping key per event: ``(key, rule, scope token)``.

    ``key`` is ``scope|rule|fields|bucket`` as a string, ``<NA>`` for an
    uncorrelatable (singleton) event. Stage 2's split hashes the same key, so
    every incident lies wholly in train or wholly in test.
    """
    if scope not in ("source", "global"):
        raise ValueError(f"unknown correlation scope {scope!r}")
    ts = (pd.to_numeric(df["ts"], errors="coerce") if "ts" in df.columns
          else pd.Series(np.nan, index=df.index)).astype("float64")
    ts_ok = np.isfinite(ts.to_numpy())
    src, dst, proto = _ident(df, "src_ip"), _ident(df, "dst_ip"), _proto(df)
    has_s, has_d = src.notna().to_numpy(), dst.notna().to_numpy()

    r1, r2, r3 = CORRELATION_RULES
    rule = np.select([~ts_ok | (~has_s & ~has_d), has_s & has_d, has_s],
                     [SINGLETON_RULE, r1, r2], default=r3)

    if scope == "source":
        scope_tok = _ident(df, "source").fillna(UNKNOWN)
    else:
        scope_tok = pd.Series("*", index=df.index, dtype="string")
    s, d = src.fillna(""), dst.fillna("")
    fields = np.select([rule == r1, rule == r2, rule == r3],
                       [s + _SEP + d + _SEP + proto, s + _SEP + proto,
                        d + _SEP + proto], default="")
    bucket = np.floor_divide(np.where(ts_ok, ts.to_numpy(), 0.0),
                             max(1, window_s)).astype("int64")
    key = (scope_tok + _SEP + pd.Series(rule, index=df.index, dtype="string")
           + _SEP + pd.Series(fields, index=df.index, dtype="string")
           + _SEP + pd.Series(bucket, index=df.index).astype("string"))
    key = key.mask(pd.Series(rule == SINGLETON_RULE, index=df.index))
    return key, rule, scope_tok


def assign_incidents(df: pd.DataFrame, window_s: int = CORRELATION_WINDOW_S,
                     scope: str = CORRELATION_SCOPE,
                     row_offset: int = 0) -> pd.DataFrame:
    """Add ``incident_id`` and ``corr_rule`` (both strings) to event rows.

    ``row_offset`` is the position of the first row in the whole stream; it
    makes singleton ids unique across chunks. Vectorised: ids are hashed once
    per distinct (key, bucket), not once per row.
    """
    if scope not in ("source", "global"):
        raise ValueError(f"unknown correlation scope {scope!r}")
    if df.empty:
        return df.assign(incident_id=pd.Series(dtype="string"),
                         corr_rule=pd.Series(dtype="string"))

    df = df.copy()
    key, rule, scope_tok = correlation_key(df, window_s, scope)
    # A singleton is keyed by its global stream position, so it never matches.
    single = rule == SINGLETON_RULE
    if single.any():
        pos = pd.Series(np.arange(len(df)) + row_offset, index=df.index)
        key = key.where(~single, scope_tok + _SEP + SINGLETON_RULE + _SEP + "#"
                        + pos.astype("string"))

    codes, uniques = pd.factorize(key)
    ids = np.array([_incident_id(k) for k in uniques], dtype=object)
    df["incident_id"] = pd.Series(ids[codes], index=df.index, dtype="string")
    df["corr_rule"] = pd.Series(rule, index=df.index, dtype="string")
    return df


def _majority(counts: pd.DataFrame) -> pd.Series:
    """Majority label per incident: most events, ties -> benign, then A-Z."""
    c = counts.assign(_benign=(counts["label"] == "benign").astype("int8"))
    c = c.sort_values(["incident_id", "n", "_benign", "label"],
                      ascending=[True, False, False, True], kind="mergesort")
    return c.drop_duplicates("incident_id").set_index("incident_id")["label"]


class IncidentAccumulator:
    """Merge per-chunk partial aggregates into exact whole-corpus incidents.

    After every chunk the partials are re-aggregated, so memory stays at
    O(incidents seen so far + one chunk) and the result does not depend on
    where chunk boundaries fall.
    """

    def __init__(self) -> None:
        self.base: pd.DataFrame | None = None
        self.pairs: dict[str, pd.DataFrame | None] = {
            "source": None, "src_ip": None, "dst_ip": None}
        self.counts: dict[str, pd.DataFrame | None] = {
            "label": None, "split": None}

    @property
    def n_incidents(self) -> int:
        return 0 if self.base is None else len(self.base)

    def add(self, events: pd.DataFrame, row_offset: int = 0) -> None:
        """Fold one chunk of correlated events into the running aggregates."""
        if events.empty:
            return
        iid = events["incident_id"].astype(str)
        ts = (pd.to_numeric(events["ts"], errors="coerce")
              if "ts" in events.columns else pd.Series(np.nan, index=events.index))
        part = pd.DataFrame({
            "incident_id": iid.to_numpy(),
            "n_events": 1,
            "first_row": np.arange(len(events), dtype="int64") + row_offset,
            "ts_first": ts.to_numpy(dtype="float64"),
            "ts_last": ts.to_numpy(dtype="float64"),
            "corr_rule": events["corr_rule"].astype(str).to_numpy(),
            "proto": _proto(events).astype(str).to_numpy(),
        })
        part = part.groupby("incident_id", sort=False).agg(
            n_events=("n_events", "sum"), first_row=("first_row", "min"),
            ts_first=("ts_first", "min"), ts_last=("ts_last", "max"),
            corr_rule=("corr_rule", "first"), proto=("proto", "first"))
        self.base = self._fold_base(part.reset_index())

        for col in self.pairs:
            vals = _ident(events, col)
            p = pd.DataFrame({"incident_id": iid.to_numpy(),
                              col: vals.to_numpy(dtype=object)}).dropna()
            prev = self.pairs[col]
            p = p if prev is None else pd.concat([prev, p], ignore_index=True)
            self.pairs[col] = p.drop_duplicates(ignore_index=True)

        for col in self.counts:
            if col not in events.columns:
                continue
            p = (pd.DataFrame({"incident_id": iid.to_numpy(),
                               col: events[col].astype(str).to_numpy()})
                 .groupby(["incident_id", col], sort=False).size()
                 .reset_index(name="n"))
            prev = self.counts[col]
            if prev is not None:
                p = (pd.concat([prev, p], ignore_index=True)
                     .groupby(["incident_id", col], sort=False)["n"].sum()
                     .reset_index())
            self.counts[col] = p

    def _fold_base(self, part: pd.DataFrame) -> pd.DataFrame:
        if self.base is None:
            return part
        both = pd.concat([self.base, part], ignore_index=True)
        return both.groupby("incident_id", sort=False).agg(
            n_events=("n_events", "sum"), first_row=("first_row", "min"),
            ts_first=("ts_first", "min"), ts_last=("ts_last", "max"),
            corr_rule=("corr_rule", "first"), proto=("proto", "first")
        ).reset_index()

    def finish(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Return (incident feature table, incident diagnostics table)."""
        if self.base is None:
            return (pd.DataFrame(columns=INCIDENT_COLUMNS),
                    pd.DataFrame(columns=DIAGNOSTIC_COLUMNS))
        out = self.base.sort_values("first_row", kind="mergesort")
        out = out.set_index("incident_id")
        idx = out.index

        def distinct(col: str) -> pd.Series:
            p = self.pairs[col]
            return (p.groupby("incident_id")[col].nunique().reindex(idx)
                    .fillna(0).astype("int64"))

        def first_value(col: str) -> pd.Series:
            p = self.pairs[col]
            return p.groupby("incident_id")[col].min().reindex(idx)

        out["n_sources"] = distinct("source")
        out["n_src_ips"] = distinct("src_ip")
        out["n_dst_ips"] = distinct("dst_ip")
        srcs = self.pairs["source"]
        out["source"] = (srcs.groupby("incident_id")["source"]
                         .agg(lambda v: ";".join(sorted(v))).reindex(idx)
                         .fillna(UNKNOWN))
        out["src_ip"], out["dst_ip"] = first_value("src_ip"), first_value("dst_ip")

        span = (out["ts_last"] - out["ts_first"]).fillna(0.0).clip(lower=0)
        out["span_s"] = span
        out["events_per_s"] = np.where(span > 0, out["n_events"] / span.where(
            span > 0, 1.0), 0.0)
        out["cross_source"] = out["n_sources"]

        lab = self.counts["label"]
        if lab is not None:
            tot = lab.groupby("incident_id")["n"].transform("sum")
            p = lab["n"] / tot
            ent = (-(p * np.log(p))).groupby(lab["incident_id"]).sum()
            out["label"] = _majority(lab).reindex(idx)
            out["n_labels"] = lab.groupby("incident_id").size().reindex(idx)
            out["label_purity"] = (lab.groupby("incident_id")["n"].max()
                                   .reindex(idx) / out["n_events"])
            out["label_entropy"] = ent.reindex(idx).fillna(0.0).abs()
            out["label_counts"] = (
                lab.sort_values(["incident_id", "label"])
                   .assign(_t=lambda d: d["label"] + ":" + d["n"].astype(str))
                   .groupby("incident_id")["_t"].agg(";".join).reindex(idx))
        else:
            out["label"] = "benign"
            out["n_labels"], out["label_purity"] = 1, 1.0
            out["label_entropy"], out["label_counts"] = 0.0, ""
        out["is_attack"] = (out["label"] != "benign").astype("int8")

        spl = self.counts["split"]
        for name in ("train", "test"):
            if spl is None:
                out[f"n_{name}_events"] = 0
                continue
            n = spl[spl["split"] == name].groupby("incident_id")["n"].sum()
            out[f"n_{name}_events"] = n.reindex(idx).fillna(0).astype("int64")

        out = out.reset_index()
        return (out[INCIDENT_COLUMNS].reset_index(drop=True),
                out[DIAGNOSTIC_COLUMNS].reset_index(drop=True))


def summarise_incidents(events: pd.DataFrame) -> pd.DataFrame:
    """One row per incident: the unit of analysis for the integrated model.

    Contains no label-derived statistic except the target (``label``,
    ``is_attack``); see :func:`incident_diagnostics` for purity / entropy.
    """
    acc = IncidentAccumulator()
    acc.add(events)
    return acc.finish()[0]


def incident_diagnostics(events: pd.DataFrame) -> pd.DataFrame:
    """Audit table per incident: raw key, time range, label purity/entropy."""
    acc = IncidentAccumulator()
    acc.add(events)
    return acc.finish()[1]


def correlate_stream(chunks: Iterator[pd.DataFrame], out_dir=DATA_OUT,
                     window_s: int = CORRELATION_WINDOW_S,
                     scope: str = CORRELATION_SCOPE
                     ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Correlate every staged event chunk and persist event + incident tables.

    Events keep their row-level detail plus ``incident_id`` / ``corr_rule``
    (strings, so the baseline gains no correlation feature); incidents are the
    aggregated view the integrated model consumes, merged across chunks.
    """
    ev_dir = out_dir / "stage3_events"
    in_dir = out_dir / "stage3_incidents"
    dg_dir = out_dir / "stage3_incident_diagnostics"
    for d in (ev_dir, in_dir, dg_dir):
        d.mkdir(parents=True, exist_ok=True)
    # Idempotent runs: clear stale outputs from any previous corpus.
    for d, pattern in ((ev_dir, "events_*.parquet"),
                       (in_dir, "incidents_*.parquet"),
                       (dg_dir, "diagnostics_*.parquet")):
        for old in d.glob(pattern):
            old.unlink()

    acc = IncidentAccumulator()
    alert_stats = []
    offset = 0
    for i, chunk in enumerate(chunks):
        c = assign_incidents(chunk, window_s, scope, row_offset=offset)
        c.to_parquet(ev_dir / f"events_{i:04d}.parquet", index=False)
        before = acc.n_incidents
        acc.add(c, row_offset=offset)
        offset += len(c)
        alert_stats.append({
            "chunk": i, "raw_events": len(c),
            "incidents_touched": int(c["incident_id"].nunique()),
            "new_incidents": acc.n_incidents - before,
            "cum_events": offset, "cum_incidents": acc.n_incidents,
            # Whole-corpus-so-far reduction; the last row is the final figure.
            "alert_reduction": 1 - (acc.n_incidents / max(1, offset)),
        })

    incidents, diagnostics = acc.finish()
    if len(incidents):
        incidents.to_parquet(in_dir / "incidents_0000.parquet", index=False)
        diagnostics.to_parquet(dg_dir / "diagnostics_0000.parquet", index=False)
    stats = pd.DataFrame(alert_stats)
    if not stats.empty:
        stats["cross_source_incidents"] = 0
        stats.loc[stats.index[-1], "cross_source_incidents"] = int(
            (incidents["cross_source"] > 1).sum())
        stats.to_csv(out_dir / "stage3_alert_stats.csv", index=False)
    return incidents, stats
