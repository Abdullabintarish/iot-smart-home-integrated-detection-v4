"""Read-only evidence access for the Research Demonstration Lab.

Every number the demo shows comes through this module, from the verified
pipeline outputs under the code folder (``results/``, ``models/``,
``data/interim``, ``data/processed``, ``data/raw_combined``). Nothing here
writes outside ``demo/``: the only files it creates are the derived,
rebuildable cache under ``demo/cache/``.

Identifier mapping (verified in earlier phases and re-checked by the tests):

  event_id   0-based position in the Stage 3 event stream; the same position
             in ``data/processed/stage2`` and in ``data/interim`` (stream order
             over the sorted shard files).
  record     event_id - first event_id of the event's source = 0-based data
             record of the original file (Zeek: n-th non-comment, non-blank
             line of ``conn.log.labeled``; Bot-IoT: n-th non-blank CSV row
             after the header).

No streamlit import: the functions are plain Python so they can be unit
tested and reused by the verification scripts.
"""
from __future__ import annotations

import bisect
import hashlib
import io
import json
import math
import os
import sys
import threading
import time
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

DEMO_DIR = Path(__file__).resolve().parent
CODE_DIR = DEMO_DIR.parent
CACHE_DIR = DEMO_DIR / "cache"

# Verified evidence, relative to the code folder (portable bundle).
REPORT = "results/stage5_report.json"
MANIFEST = "results/run_manifest.json"
REPORT_MD = "results/report/REPORT.md"
REPORT_DIR = "results/report"
TRANSCRIPTS = "results/transcripts"
FRAG_PRED = "results/fragmented_event_predictions.csv"
INTEG_PRED = "results/integrated_event_predictions.csv"
DIAG_PRED = "results/diagnostic_event_predictions.csv"
INTERIM = "data/interim"
STAGE2 = "data/processed/stage2"
STAGE3_EVENTS = "data/processed/stage3_events"
INCIDENTS = "data/processed/stage3_incidents/incidents_0000.parquet"
DIAGNOSTICS = "data/processed/stage3_incident_diagnostics/diagnostics_0000.parquet"
FEATURE_PLAN = "data/processed/stage2_feature_plan.csv"
MODEL = "models/rf_integrated.joblib"
MODEL_FEATURES = "models/rf_integrated_features.csv"

PRED_CACHE = CACHE_DIR / "predictions.parquet"
META_CACHE = CACHE_DIR / "meta.json"
CACHE_MANIFEST = CACHE_DIR / "cache_manifest.json"
LIVE_CHECK = CACHE_DIR / "live_inference_check.json"
CACHE_VERSION = 1

BENIGN = "benign"
CLASS_NAMES = {"benign": "Benign", "c2": "Command and Control (c2)",
               "dos": "Denial of Service (dos; DoS + DDoS)",
               "malware": "Malware", "recon": "Reconnaissance (recon)"}
OUTCOMES = ("both correct", "baseline wrong only", "integrated wrong only",
            "both wrong")
SHOWN_RAW = ("ts", "src_ip", "sport", "dst_ip", "dport", "proto", "label")
MAX_SELECTION = 5_000          # hard cap on rows materialised per selection
_SHA_BLOCK = 1 << 20


# --------------------------------------------------------------------------
# Paths, JSON, provenance strings
# --------------------------------------------------------------------------
def path(rel: str) -> Path:
    """Absolute path of an evidence file given relative to the code folder."""
    return CODE_DIR / rel


def rel(p: Path) -> str:
    """Path relative to the code folder, POSIX style, for display."""
    try:
        return Path(p).resolve().relative_to(CODE_DIR).as_posix()
    except ValueError:
        return Path(p).as_posix()


def _files(rel_dir: str, pattern: str) -> list[Path]:
    return sorted(path(rel_dir).glob(pattern))


def required_evidence() -> list[tuple[str, bool]]:
    """(relative path, exists) for every input the demo needs."""
    singles = [REPORT, MANIFEST, FRAG_PRED, INTEG_PRED, DIAG_PRED, INCIDENTS,
               DIAGNOSTICS, FEATURE_PLAN, MODEL, MODEL_FEATURES]
    out = [(r, path(r).is_file()) for r in singles]
    for d, pat in ((INTERIM, "shard_*.parquet"), (STAGE2, "*.parquet"),
                   (STAGE3_EVENTS, "*.parquet")):
        out.append((f"{d}/{pat}", bool(_files(d, pat))))
    return out


def missing_evidence() -> list[str]:
    return [r for r, ok in required_evidence() if not ok]


@lru_cache(maxsize=None)
def _json(rel_path: str, mtime_ns: int) -> dict:
    # Python's json accepts the NaN tokens the pipeline writes for undefined
    # rates (e.g. FNR of a capture without attack events).
    return json.loads(path(rel_path).read_text(encoding="utf-8"))


def load_json(rel_path: str) -> dict:
    return _json(rel_path, path(rel_path).stat().st_mtime_ns)


def load_report() -> dict:
    return load_json(REPORT)


def load_manifest() -> dict:
    return load_json(MANIFEST)


def json_get(obj, dotted: str):
    """Value at a dotted path (``a.b.0.c``); list positions are integers."""
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur[part]
    return cur


def src(dotted: str, file: str = REPORT) -> str:
    """Provenance string shown next to a displayed value."""
    return f"{file} → {dotted}"


def is_nan(v) -> bool:
    return isinstance(v, float) and math.isnan(v)


# --------------------------------------------------------------------------
# File spans: global event_id -> (file, local row)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Span:
    path: Path
    start: int
    n: int

    @property
    def end(self) -> int:
        return self.start + self.n


@lru_cache(maxsize=None)
def spans(rel_dir: str, pattern: str = "*.parquet") -> tuple[Span, ...]:
    """Stream layout of a parquet directory from file metadata only."""
    out, start = [], 0
    for f in _files(rel_dir, pattern):
        n = pq.ParquetFile(f).metadata.num_rows
        out.append(Span(f, start, n))
        start += n
    return tuple(out)


def interim_spans() -> tuple[Span, ...]:
    return spans(INTERIM, "shard_*.parquet")


def stage2_spans() -> tuple[Span, ...]:
    return spans(STAGE2)


def stage3_spans() -> tuple[Span, ...]:
    return spans(STAGE3_EVENTS)


def n_stream_events() -> int:
    s = interim_spans()
    return s[-1].end if s else 0


def locate(sp: tuple[Span, ...], event_id: int) -> tuple[Span, int]:
    starts = [s.start for s in sp]
    i = bisect.bisect_right(starts, int(event_id)) - 1
    if i < 0 or event_id >= sp[i].end:
        raise IndexError(f"event_id {event_id} outside the stream")
    return sp[i], int(event_id) - sp[i].start


def take_rows(sp: tuple[Span, ...], event_ids: Iterable[int],
              columns: list[str] | None = None) -> pd.DataFrame:
    """Rows at global positions ``event_ids`` (input order kept).

    Reads only the files that hold the requested rows, with column
    projection; a ``event_id`` column is added. Capped at MAX_SELECTION.
    """
    ids = np.asarray(list(event_ids), dtype="int64")
    if len(ids) > MAX_SELECTION:
        raise ValueError(f"selection of {len(ids):,} rows exceeds the cap "
                         f"of {MAX_SELECTION:,}")
    if len(ids) == 0:
        return pd.DataFrame({"event_id": pd.Series(dtype="int64")})
    if ids.min() < 0 or ids.max() >= sp[-1].end:
        raise IndexError("event_id outside the stream")
    parts = []
    for s in sp:
        m = (ids >= s.start) & (ids < s.end)
        if not m.any():
            continue
        pos = np.flatnonzero(m)
        cols = None
        if columns is not None:
            have = set(pq.ParquetFile(s.path).schema_arrow.names)
            cols = [c for c in columns if c in have]
        t = pq.read_table(s.path, columns=cols).take(pa.array(ids[pos] - s.start))
        df = t.to_pandas()
        df.index = pos
        parts.append(df)
    out = pd.concat(parts).sort_index() if len(parts) > 1 else parts[0]
    out = out.reset_index(drop=True)
    out.insert(0, "event_id", ids)
    return out


# --------------------------------------------------------------------------
# Sources: stream order, raw files, dataset family
# --------------------------------------------------------------------------
def manifest_datasets() -> pd.DataFrame:
    """Dataset files recorded in run_manifest.json (path, bytes, sha256...)."""
    m = load_manifest()["datasets"]
    rows = []
    for f in m["files"]:
        prov = f.get("provenance", {})
        p = Path(f["path"])
        name = (p.parent.parent.name if p.name == "conn.log.labeled"
                and p.parent.name == "bro" else p.stem)
        rows.append({"source": name, "dataset": prov.get("dataset", ""),
                     "raw_file": f"data/{f['path']}", "bytes": f["bytes"],
                     "sha256": f["sha256"],
                     "origin": prov.get("url") or prov.get("source", "")})
    return pd.DataFrame(rows)


@lru_cache(maxsize=None)
def _source_index() -> pd.DataFrame:
    rows = []
    for s in interim_spans():
        vals = pq.read_table(s.path, columns=["source"]).column(0).unique()
        vals = vals.to_pylist()
        if len(vals) != 1:
            raise ValueError(f"{rel(s.path)} holds {len(vals)} sources")
        rows.append({"source": vals[0], "start": s.start, "n": s.n,
                     "shard": rel(s.path)})
    df = pd.DataFrame(rows)
    idx = (df.groupby("source", sort=False)
           .agg(first_event_id=("start", "min"), n_events=("n", "sum"),
                shards=("shard", lambda v: ";".join(v)))
           .reset_index())
    # Contiguity: one source must occupy one unbroken block of the stream.
    end = idx["first_event_id"] + idx["n_events"]
    if not (idx["first_event_id"].iloc[1:].to_numpy() == end.iloc[:-1].to_numpy()).all():
        raise ValueError("sources are not contiguous in the interim stream")
    ds = manifest_datasets().set_index("source")
    idx["dataset"] = [ds.loc[s, "dataset"] if s in ds.index else
                      ("IoT-23" if s.startswith("CTU-") else "Bot-IoT")
                      for s in idx["source"]]
    idx["raw_file"] = [ds.loc[s, "raw_file"] if s in ds.index else ""
                       for s in idx["source"]]
    idx["kind"] = ["zeek" if r.endswith("conn.log.labeled") else "csv"
                   for r in idx["raw_file"]]
    return idx


def source_index() -> pd.DataFrame:
    """One row per source in stream order: first_event_id, n_events, raw file."""
    return _source_index().copy()


def source_of(event_id: int) -> pd.Series:
    idx = _source_index()
    i = int(np.searchsorted(idx["first_event_id"].to_numpy(), event_id,
                            side="right")) - 1
    row = idx.iloc[i]
    if not (row["first_event_id"] <= event_id < row["first_event_id"] + row["n_events"]):
        raise IndexError(f"event_id {event_id} outside the stream")
    return row


def record_index(event_id: int) -> int:
    """0-based data record of the event within its original raw file."""
    return int(event_id) - int(source_of(event_id)["first_event_id"])


def family(source: str) -> str:
    idx = _source_index().set_index("source")
    return str(idx.loc[source, "dataset"])


# --------------------------------------------------------------------------
# Raw files: bounded line reader with incremental offset checkpoints
# --------------------------------------------------------------------------
class _RawIndex:
    """Byte offsets of every ``step``-th data record, filled as far as read.

    A lookup seeks to the nearest checkpoint below the wanted record and reads
    forward only up to that record; nothing is ever loaded whole.
    """

    def __init__(self, p: Path, kind: str, step: int = 20_000) -> None:
        self.p, self.kind, self.step = p, kind, step
        self.lock = threading.Lock()
        self.header: list[str] = []          # comment / header lines
        self.sep = "\t" if kind == "zeek" else ","
        self.fields: list[str] = []
        # checkpoints[k] = (byte offset, physical line no) of record k*step
        self.checkpoints: list[tuple[int, int]] = []
        self._read_header()

    def _is_data(self, line: bytes) -> bool:
        if not line.strip():
            return False
        return not (self.kind == "zeek" and line.startswith(b"#"))

    def _read_header(self) -> None:
        with self.p.open("rb") as fh:
            line_no = 0
            while True:
                off = fh.tell()
                line = fh.readline()
                if not line:
                    break
                line_no += 1
                if self.kind == "zeek":
                    if line.startswith(b"#"):
                        txt = line.decode("utf-8", "replace").rstrip("\r\n")
                        self.header.append(txt)
                        if txt.startswith("#separator"):
                            tok = txt.split()
                            if len(tok) >= 2 and tok[1].startswith("\\x"):
                                self.sep = chr(int(tok[1][2:], 16))
                        elif txt.startswith("#fields"):
                            f = txt.split(self.sep)[1:]
                            if f and " " in f[-1]:
                                f = f[:-1] + f[-1].split()
                            self.fields = f
                        continue
                    if not line.strip():
                        continue
                    self.checkpoints.append((off, line_no))
                    return
                # CSV: first line is the header, data starts after it.
                if not self.header:
                    txt = line.decode("utf-8", "replace").rstrip("\r\n")
                    self.header.append(txt)
                    self.fields = [c.strip() for c in txt.split(",")]
                    continue
                if not line.strip():
                    continue
                self.checkpoints.append((off, line_no))
                return

    def read(self, record: int) -> tuple[int, str]:
        """(1-based physical line number, text) of 0-based data record."""
        if record < 0:
            raise IndexError("negative record")
        with self.lock:
            k = min(record // self.step, len(self.checkpoints) - 1)
            off, line_no = self.checkpoints[k]
            rec = k * self.step
            with self.p.open("rb") as fh:
                fh.seek(off)
                line_no -= 1
                while True:
                    pos = fh.tell()
                    line = fh.readline()
                    if not line:
                        raise IndexError(f"record {record} beyond end of "
                                         f"{rel(self.p)}")
                    line_no += 1
                    if not self._is_data(line):
                        continue
                    if rec % self.step == 0 and rec // self.step == len(self.checkpoints):
                        self.checkpoints.append((pos, line_no))
                    if rec == record:
                        return line_no, line.decode("utf-8", "replace").rstrip("\r\n")
                    rec += 1


_RAW: dict[str, _RawIndex] = {}
_RAW_LOCK = threading.Lock()


def _raw_index(source: str) -> _RawIndex:
    with _RAW_LOCK:
        if source not in _RAW:
            row = _source_index().set_index("source").loc[source]
            _RAW[source] = _RawIndex(path(row["raw_file"]), row["kind"])
        return _RAW[source]


def read_raw_record(source: str, record: int) -> dict:
    """The original raw line of one record, split into its declared fields."""
    ix = _raw_index(source)
    line_no, text = ix.read(record)
    cols = text.split(ix.sep)
    if ix.kind == "zeek" and len(cols) < len(ix.fields):
        cols = _pipeline("ingest")._expand_tail(cols, len(ix.fields))
    fields = {f: (cols[i] if i < len(cols) else None)
              for i, f in enumerate(ix.fields)}
    return {"source": source, "record": int(record), "line_no": line_no,
            "text": text, "fields": fields, "kind": ix.kind,
            "raw_file": rel(ix.p), "header": list(ix.header)}


# --------------------------------------------------------------------------
# Pipeline reuse (read-only import, no bytecode written into pipeline/)
# --------------------------------------------------------------------------
def _pipeline(name: str):
    """Import ``pipeline.<name>`` from the code folder without writing .pyc."""
    if str(CODE_DIR) not in sys.path:
        sys.path.insert(0, str(CODE_DIR))
    prev = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        import importlib
        return importlib.import_module(f"pipeline.{name}")
    finally:
        sys.dont_write_bytecode = prev


class _NamedText(io.StringIO):
    """In-memory text file with a ``name``, standing in for a path argument."""

    def __init__(self, text: str, name: str) -> None:
        super().__init__(text)
        self._name = name

    @property
    def name(self) -> str:
        return self._name


def normalise_raw_record(source: str, record: int) -> dict:
    """The raw record passed through the same Stage 1 functions ingest uses.

    Zeek: ``_zeek_row`` + ``_zeek_frame`` (as ``flows_from_zeek_log``).
    CSV: ``flows_from_csv`` on an in-memory two-line copy (header + record)
    that carries the original file name, so the filename-based fallback label
    is identical. Nothing is written to disk.
    """
    ing = _pipeline("ingest")
    raw = read_raw_record(source, record)
    ix = _raw_index(source)
    if ix.kind == "zeek":
        names = list(ix.fields) if ix.fields else list(ing.ZEEK_DEFAULT_FIELDS)
        label_idx, detailed_idx = ing._zeek_positions(names)
        cols = raw["text"].split(ix.sep)
        if len(cols) < len(names):
            cols = ing._expand_tail(cols, len(names))
        fallback = ing.infer_label_from_name(ix.p.name)
        rec = ing._zeek_row(cols, names, label_idx, detailed_idx, source,
                            fallback)
        df = ing._zeek_frame([rec])
    else:
        buf = _NamedText(ix.header[0] + "\n" + raw["text"] + "\n", ix.p.name)
        gen = ing.flows_from_csv(buf, source)
        try:
            df = next(gen)
        finally:
            gen.close()
    out = df.iloc[0].to_dict()
    return {k: (None if (v is None or (isinstance(v, float) and math.isnan(v))
                         or v is pd.NA) else v) for k, v in out.items()}


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    try:
        fa, fb = float(a), float(b)
        return math.isclose(fa, fb, rel_tol=1e-12, abs_tol=1e-9)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _clean(v):
    if v is None or v is pd.NA:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (np.floating,)):
        return None if np.isnan(v) else float(v)
    if isinstance(v, np.integer):
        return int(v)
    return v


def compare_with_raw(event_id: int) -> dict:
    """Staged (interim) values of one event next to its raw-file record.

    ``rows`` lists every staged column with the raw value after the Stage 1
    normalisation and whether they agree; ``key_match`` covers
    ts/src_ip/sport/dst_ip/dport/proto/label.
    """
    srow = source_of(event_id)
    staged = take_rows(interim_spans(), [event_id]).iloc[0].to_dict()
    record = int(event_id) - int(srow["first_event_id"])
    raw = read_raw_record(srow["source"], record)
    norm = normalise_raw_record(srow["source"], record)
    rows = []
    for col, sv in staged.items():
        if col == "event_id":
            continue
        sv = _clean(sv)
        nv = _clean(norm.get(col))
        rows.append({"field": col, "staged (data/interim)": sv,
                     "raw after Stage 1 normalisation": nv,
                     "match": _same(sv, nv)})
    table = pd.DataFrame(rows)
    key = table[table["field"].isin(SHOWN_RAW)]
    return {"event_id": int(event_id), "source": srow["source"],
            "record": record, "line_no": raw["line_no"],
            "raw_file": raw["raw_file"], "raw_text": raw["text"],
            "raw_fields": raw["fields"], "rows": table,
            "key_match": bool(len(key) == len(SHOWN_RAW) and key["match"].all()),
            "all_match": bool(table["match"].all())}


# --------------------------------------------------------------------------
# Hashing and the derived cache
# --------------------------------------------------------------------------
def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with Path(p).open("rb") as fh:
        while True:
            b = fh.read(_SHA_BLOCK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def cache_inputs() -> list[Path]:
    """Verified outputs the derived cache is built from."""
    files = [path(FRAG_PRED), path(INTEG_PRED), path(DIAG_PRED)]
    files += [s.path for s in interim_spans()]
    files += [s.path for s in stage2_spans()]
    return files


def _fingerprint(p: Path, with_hash: bool = True) -> dict:
    st = p.stat()
    d = {"path": rel(p), "bytes": st.st_size, "mtime_ns": st.st_mtime_ns}
    if with_hash:
        d["sha256"] = sha256_file(p)
    return d


def _read_pred_csv(p: Path, pred_cols: list[str], with_ids: bool) -> pa.Table:
    types = {"event_id": pa.int64(), "incident_id": pa.string(),
             "source": pa.dictionary(pa.int32(), pa.string()),
             "split": pa.dictionary(pa.int32(), pa.string()),
             "label": pa.dictionary(pa.int32(), pa.string())}
    for c in pred_cols:
        types[c] = pa.dictionary(pa.int32(), pa.string())
    cols = (["event_id", "source", "incident_id", "split", "label"]
            if with_ids else ["event_id", "label"]) + pred_cols
    return pacsv.read_csv(p, convert_options=pacsv.ConvertOptions(
        column_types={k: v for k, v in types.items() if k in cols},
        include_columns=cols))


def _plain(col) -> pa.ChunkedArray:
    """Dictionary column as plain strings, for exact comparisons."""
    if pa.types.is_dictionary(col.type):
        return col.cast(pa.string())
    return col


def build_cache(log=print) -> dict:
    """Build ``demo/cache`` from verified outputs only; returns the meta dict.

    Joins the three prediction CSVs by event_id after checking that they
    describe identical events, and derives small lookup tables (source index,
    label counts, protocol code map, time ranges) from the staged data. The
    input fingerprints (size, mtime, SHA-256) are recorded so a changed input
    marks the cache stale.
    """
    t0 = time.perf_counter()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    log("reading prediction CSVs")
    frag = _read_pred_csv(path(FRAG_PRED), ["pred"], True)
    integ = _read_pred_csv(path(INTEG_PRED), ["pred"], True)
    diag = _read_pred_csv(path(DIAG_PRED), ["pred_pooled", "pred_enriched"], False)
    checks = {}
    for c in ("event_id", "source", "incident_id", "split", "label"):
        checks[f"frag_vs_integ_{c}_identical"] = bool(
            _plain(frag[c]).equals(_plain(integ[c])))
    for c in ("event_id", "label"):
        checks[f"frag_vs_diagnostic_{c}_identical"] = bool(
            _plain(frag[c]).equals(_plain(diag[c])))
    eid = frag["event_id"].to_numpy()
    checks["event_id_strictly_increasing"] = bool((np.diff(eid) > 0).all())
    checks["split_all_test"] = bool(pc.all(pc.equal(_plain(frag["split"]), "test")).as_py())
    bad = [k for k, v in checks.items() if not v]
    if bad:
        raise ValueError(f"prediction files disagree: {bad}")
    table = pa.table({
        "event_id": frag["event_id"], "source": frag["source"],
        "incident_id": frag["incident_id"], "label": frag["label"],
        "pred_fragmented": frag["pred"], "pred_integrated": integ["pred"],
        "pred_pooled": diag["pred_pooled"], "pred_enriched": diag["pred_enriched"]})
    tmp = PRED_CACHE.with_suffix(".tmp")
    pq.write_table(table, tmp)
    os.replace(tmp, PRED_CACHE)
    n_pred = table.num_rows
    del frag, integ, diag, table

    log("deriving source index, label counts, protocol map from data/interim")
    idx = _source_index()
    label_counts, proto_pairs, ts_rng, botiot_cats = [], [], [], []
    s2 = stage2_spans()
    for s in interim_spans():
        names = pq.ParquetFile(s.path).schema_arrow.names
        cols = ["source", "label", "ts", "proto"] + [
            c for c in ("category", "subcategory") if c in names]
        df = pq.read_table(s.path, columns=cols).to_pandas()
        label_counts.append(df.groupby(["source", "label"]).size())
        ts_rng.append(df.groupby("source")["ts"].agg(["min", "max"]))
        if "category" in df.columns:
            botiot_cats.append(df.groupby(["source", "category", "subcategory",
                                           "label"]).size())
        # Same global rows in Stage 2 -> encoded protocol code.
        codes = take_proto_codes(s2, s.start, s.n)
        proto_pairs.append(pd.DataFrame({"code": codes, "name": df["proto"].to_numpy()})
                           .value_counts())
    lc = pd.concat(label_counts).groupby(level=[0, 1]).sum()
    pp = pd.concat(proto_pairs).groupby(level=[0, 1]).sum().reset_index(name="events")
    tr = pd.concat(ts_rng).groupby(level=0).agg({"min": "min", "max": "max"})
    bc = (pd.concat(botiot_cats).groupby(level=[0, 1, 2, 3]).sum()
          .reset_index(name="events") if botiot_cats else pd.DataFrame())
    meta = {
        "cache_version": CACHE_VERSION,
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_predictions": int(n_pred), "join_checks": checks,
        "n_stream_events": n_stream_events(),
        "sources": idx.to_dict(orient="records"),
        "label_counts": [{"source": k[0], "label": k[1], "events": int(v)}
                         for k, v in lc.items()],
        "ts_range": {k: {"min": float(r["min"]), "max": float(r["max"])}
                     for k, r in tr.iterrows()},
        "proto_map": pp.astype({"code": "int64"}).to_dict(orient="records"),
        "botiot_categories": bc.to_dict(orient="records"),
    }
    META_CACHE.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    log("fingerprinting inputs (SHA-256)")
    inputs = [_fingerprint(p) for p in cache_inputs()]
    man = {"cache_version": CACHE_VERSION, "built_utc": meta["built_utc"],
           "builder": "demo/build_cache.py (evidence.build_cache)",
           "note": "derived and rebuildable; reads verified outputs only",
           "inputs": inputs,
           "outputs": [_fingerprint(PRED_CACHE), _fingerprint(META_CACHE)],
           "build_seconds": round(time.perf_counter() - t0, 2)}
    CACHE_MANIFEST.write_text(json.dumps(man, indent=1), encoding="utf-8")
    _load_meta.cache_clear()
    log(f"cache built in {man['build_seconds']} s")
    return meta


def take_proto_codes(s2: tuple[Span, ...], start: int, n: int) -> np.ndarray:
    """Stage 2 ``proto`` codes of global rows [start, start + n)."""
    parts = []
    for s in s2:
        lo, hi = max(start, s.start), min(start + n, s.end)
        if lo >= hi:
            continue
        col = pq.read_table(s.path, columns=["proto"]).column(0)
        parts.append(col.slice(lo - s.start, hi - lo).to_numpy())
    return np.concatenate(parts)


def cache_status(deep: bool = False) -> dict:
    """``state``: ok | missing | stale, with the reasons.

    An input whose size and mtime are unchanged is accepted; otherwise its
    SHA-256 is recomputed and must equal the recorded one (``deep`` forces
    the hash check for every input).
    """
    if not (CACHE_MANIFEST.is_file() and PRED_CACHE.is_file() and META_CACHE.is_file()):
        return {"state": "missing", "reasons": ["demo/cache not built"]}
    man = json.loads(CACHE_MANIFEST.read_text(encoding="utf-8"))
    if man.get("cache_version") != CACHE_VERSION:
        return {"state": "stale", "reasons": ["cache version changed"]}
    reasons = []
    recorded = {d["path"]: d for d in man["inputs"]}
    current = {rel(p): p for p in cache_inputs()}
    for r in sorted(set(recorded) ^ set(current)):
        reasons.append(f"input set changed: {r}")
    for r, d in recorded.items():
        p = current.get(r)
        if p is None:
            continue
        st = p.stat()
        if not deep and st.st_size == d["bytes"] and st.st_mtime_ns == d["mtime_ns"]:
            continue
        if st.st_size != d["bytes"] or sha256_file(p) != d["sha256"]:
            reasons.append(f"input changed since cache build: {r}")
    for d in man["outputs"]:
        p = CODE_DIR / d["path"]
        if not p.is_file() or p.stat().st_size != d["bytes"]:
            reasons.append(f"cache output changed: {d['path']}")
    return {"state": "stale" if reasons else "ok", "reasons": reasons,
            "built_utc": man.get("built_utc"), "inputs": man["inputs"]}


@lru_cache(maxsize=1)
def _load_meta(mtime_ns: int) -> dict:
    return json.loads(META_CACHE.read_text(encoding="utf-8"))


def load_meta() -> dict:
    return _load_meta(META_CACHE.stat().st_mtime_ns)


def label_counts() -> pd.DataFrame:
    """Events per (source, label) in data/interim (Stage 1 ground truth)."""
    return pd.DataFrame(load_meta()["label_counts"])


def classes_present() -> list[str]:
    return sorted(label_counts()["label"].unique())


def classes_absent() -> tuple[list[str], list[str]]:
    """(config CLASSES from the manifest, those with no event in the data)."""
    conf = list(load_manifest()["config"]["pipeline.config"]["CLASSES"])
    present = set(classes_present())
    return conf, [c for c in conf if c not in present]


def proto_names() -> dict[int, str]:
    """Stage 2 protocol code -> raw protocol name (derived; one-to-one)."""
    pm = pd.DataFrame(load_meta()["proto_map"])
    by = pm.groupby("code")["name"].nunique()
    if (by > 1).any():
        raise ValueError("protocol code maps to several names")
    return dict(zip(pm["code"].astype(int), pm["name"]))


# --------------------------------------------------------------------------
# Predictions
# --------------------------------------------------------------------------
def load_predictions() -> pd.DataFrame:
    """Joined per-event predictions (all held-out test events) from the cache.

    Adds ``frag_ok`` / ``integ_ok`` and the four-way ``outcome``.
    """
    df = pq.read_table(PRED_CACHE).to_pandas()
    lab = df["label"].astype(str).to_numpy()
    df["frag_ok"] = df["pred_fragmented"].astype(str).to_numpy() == lab
    df["integ_ok"] = df["pred_integrated"].astype(str).to_numpy() == lab
    code = np.select([df["frag_ok"] & df["integ_ok"],
                      ~df["frag_ok"] & df["integ_ok"],
                      df["frag_ok"] & ~df["integ_ok"]], [0, 1, 2], default=3)
    df["outcome"] = pd.Categorical.from_codes(code, categories=list(OUTCOMES))
    return df


def outcome_counts(preds: pd.DataFrame) -> dict[str, int]:
    vc = preds["outcome"].value_counts()
    return {o: int(vc.get(o, 0)) for o in OUTCOMES}


def outcome_consistency(preds: pd.DataFrame, report: dict) -> dict:
    """Check outcome counts against the confusion matrices in the report.

    The confusion matrices fix each condition's number of correct events
    (the trace) and the total; the joint four-way split itself is only
    available from the per-event predictions.
    """
    oc = outcome_counts(preds)
    tf = int(np.trace(np.array(report["fragmented"]["confusion_matrix"])))
    ti = int(np.trace(np.array(report["integrated"]["confusion_matrix"])))
    n = int(report["fragmented"]["n_samples"])
    checks = {
        "both correct + integrated wrong only = trace(fragmented CM)":
            (oc["both correct"] + oc["integrated wrong only"], tf),
        "both correct + baseline wrong only = trace(integrated CM)":
            (oc["both correct"] + oc["baseline wrong only"], ti),
        "sum of the four groups = n_samples": (sum(oc.values()), n),
    }
    return {"counts": oc, "trace_fragmented": tf, "trace_integrated": ti,
            "n_samples": n,
            "checks": [{"check": k, "from predictions": a,
                        "from confusion matrix": b, "ok": a == b}
                       for k, (a, b) in checks.items()]}


def metrics_from_predictions(y_true, y_pred) -> dict:
    """Recompute the Stage 5 headline metrics with sklearn (as evaluate_split)."""
    from sklearn.metrics import (accuracy_score, confusion_matrix,
                                 precision_recall_fscore_support)
    yt = np.asarray(y_true).astype(str)
    yp = np.asarray(y_pred).astype(str)
    classes = sorted(set(yt) | set(yp))
    p, r, f, _ = precision_recall_fscore_support(yt, yp, labels=classes,
                                                 zero_division=0)
    neg_t, neg_p = yt == BENIGN, yp == BENIGN
    with warnings.catch_warnings():
        # a single-class capture triggers sklearn's "single label" notice
        warnings.simplefilter("ignore", UserWarning)
        cm = confusion_matrix(yt, yp, labels=classes).tolist()
    return {"accuracy": float(accuracy_score(yt, yp)),
            "precision_macro": float(p.mean()), "recall_macro": float(r.mean()),
            "f1_macro": float(f.mean()),
            "fpr": float((neg_t & ~neg_p).sum() / neg_t.sum()) if neg_t.any() else float("nan"),
            "fnr": float((~neg_t & neg_p).sum() / (~neg_t).sum()) if (~neg_t).any() else float("nan"),
            "classes": classes, "confusion_matrix": cm}


# --------------------------------------------------------------------------
# Confusion matrix arithmetic (page 5 walkthrough)
# --------------------------------------------------------------------------
def cm_class_counts(cm, classes: list[str], cls: str) -> dict[str, int]:
    """One-vs-rest TP / FP / FN / TN of ``cls`` (rows = true, cols = predicted)."""
    m = np.asarray(cm, dtype="int64")
    i = classes.index(cls)
    tp = int(m[i, i])
    fp = int(m[:, i].sum() - tp)
    fn = int(m[i, :].sum() - tp)
    tn = int(m.sum() - tp - fp - fn)
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn}


def metrics_from_cm(cm, classes: list[str], negative: str = BENIGN) -> dict:
    """Accuracy, per-class and macro P/R/F1, FPR/FNR from a confusion matrix."""
    m = np.asarray(cm, dtype="int64")
    per = {}
    for c in classes:
        k = cm_class_counts(m, classes, c)
        p = k["TP"] / (k["TP"] + k["FP"]) if (k["TP"] + k["FP"]) else 0.0
        r = k["TP"] / (k["TP"] + k["FN"]) if (k["TP"] + k["FN"]) else 0.0
        f = 2 * p * r / (p + r) if (p + r) else 0.0
        per[c] = {"precision": p, "recall": r, "f1": f, **k}
    i = classes.index(negative)
    n_neg = int(m[i, :].sum())
    n_pos = int(m.sum() - n_neg)
    fp_bin = int(n_neg - m[i, i])                # benign predicted as any attack
    fn_bin = int(m[:, i].sum() - m[i, i])        # attack predicted as benign
    return {"accuracy": float(np.trace(m) / m.sum()),
            "precision_macro": float(np.mean([v["precision"] for v in per.values()])),
            "recall_macro": float(np.mean([v["recall"] for v in per.values()])),
            "f1_macro": float(np.mean([v["f1"] for v in per.values()])),
            "fpr": fp_bin / n_neg if n_neg else float("nan"),
            "fnr": fn_bin / n_pos if n_pos else float("nan"),
            "per_class": per, "n_negative": n_neg, "n_positive": n_pos,
            "fp_binary": fp_bin, "fn_binary": fn_bin}


def close(a, b, tol: float = 1e-12) -> bool:
    if is_nan(a) and is_nan(b):
        return True
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)


# --------------------------------------------------------------------------
# Incidents
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _incidents(mtime_ns: int) -> pd.DataFrame:
    return pq.read_table(path(INCIDENTS)).to_pandas()


def incidents() -> pd.DataFrame:
    """Stage 3 incident feature table (704k rows, read once)."""
    return _incidents(path(INCIDENTS).stat().st_mtime_ns)


@lru_cache(maxsize=1)
def _diagnostics(mtime_ns: int) -> pd.DataFrame:
    return pq.read_table(path(DIAGNOSTICS)).to_pandas()


def diagnostics() -> pd.DataFrame:
    """Stage 3 incident diagnostics (label-derived audit stats, not features)."""
    return _diagnostics(path(DIAGNOSTICS).stat().st_mtime_ns)


def incident_row(incident_id: str) -> tuple[dict, dict]:
    """(incident feature row, diagnostics row) for one incident id."""
    inc, dg = incidents(), diagnostics()
    a = inc[inc["incident_id"] == incident_id]
    b = dg[dg["incident_id"] == incident_id]
    if a.empty or b.empty:
        raise KeyError(f"unknown incident_id {incident_id!r}")
    return a.iloc[0].to_dict(), b.iloc[0].to_dict()


def window_of(ts_first: float, window_s: int) -> tuple[float, float, int]:
    """Tumbling window (start, end, bucket) holding ``ts_first``."""
    b = int(math.floor(ts_first / window_s))
    return b * window_s, (b + 1) * window_s, b


MEMBER_COLUMNS = ["incident_id", "source", "src_ip", "dst_ip", "proto", "ts",
                  "label", "split", "corr_rule"]


def incident_members(incident_id: str, cap: int = MAX_SELECTION) -> dict:
    """Member events of one incident from data/processed/stage3_events.

    Scans only the event files overlapping the incident's source block. All
    members feed the consistency check and the timeline histogram; at most
    ``cap`` rows (earliest by ts) are returned as a table.
    """
    inc, dg = incident_row(incident_id)
    srow = _source_index().set_index("source").loc[dg["source"]]
    lo, hi = int(srow["first_event_id"]), int(srow["first_event_id"] + srow["n_events"])
    parts = []
    for s in stage3_spans():
        if s.end <= lo or s.start >= hi:
            continue
        t = pq.read_table(s.path, columns=MEMBER_COLUMNS)
        mask = pc.equal(t.column("incident_id"), incident_id)
        pos = pc.indices_nonzero(mask)
        if len(pos) == 0:
            continue
        sub = t.take(pos).to_pandas()
        sub.insert(0, "event_id", pos.to_numpy().astype("int64") + s.start)
        parts.append(sub)
    m = (pd.concat(parts, ignore_index=True) if parts
         else pd.DataFrame(columns=["event_id"] + MEMBER_COLUMNS))
    window = int(load_manifest()["config"]["pipeline.config"]["CORRELATION_WINDOW_S"])
    m = m.sort_values(["ts", "event_id"], kind="mergesort").reset_index(drop=True)
    bucket = np.floor_divide(m["ts"].to_numpy(dtype="float64"), window).astype("int64")
    checks = [
        ("member count = incidents.n_events", len(m), int(inc["n_events"])),
        ("member count = diagnostics.n_events", len(m), int(dg["n_events"])),
        ("distinct source", int(m["source"].nunique()), 1),
        ("distinct src_ip", int(m["src_ip"].nunique()), 1),
        ("distinct dst_ip", int(m["dst_ip"].nunique()), 1),
        ("distinct proto (Stage 2 code)", int(m["proto"].nunique()), 1),
        (f"distinct window bucket floor(ts/{window})", int(len(np.unique(bucket))), 1),
        ("distinct corr_rule", int(m["corr_rule"].nunique()), 1),
        ("min ts = diagnostics.ts_first", float(m["ts"].min()), float(dg["ts_first"])),
        ("max ts = diagnostics.ts_last", float(m["ts"].max()), float(dg["ts_last"])),
        ("test members = diagnostics.n_test_events",
         int((m["split"] == "test").sum()), int(dg["n_test_events"])),
        ("train members = diagnostics.n_train_events",
         int((m["split"] == "train").sum()), int(dg["n_train_events"])),
        ("first member event_id = diagnostics.first_row",
         int(m["event_id"].min()), int(dg["first_row"])),
    ]
    if len(m):
        checks += [
            ("member source = incident source", str(m["source"].iloc[0]), str(dg["source"])),
            ("member src_ip = diagnostics.src_ip", str(m["src_ip"].iloc[0]), str(dg["src_ip"])),
            ("member dst_ip = diagnostics.dst_ip", str(m["dst_ip"].iloc[0]), str(dg["dst_ip"])),
            ("member proto code = diagnostics.proto", str(int(m["proto"].iloc[0])), str(dg["proto"])),
        ]
    check_df = pd.DataFrame([{"check": c, "observed": o, "expected": e,
                              "ok": (close(o, e) if isinstance(e, float) else o == e)}
                             for c, o, e in checks])
    return {"incident": inc, "diagnostics": dg, "n_members": int(len(m)),
            "members": m.head(cap), "ts": m["ts"].to_numpy(dtype="float64"),
            "labels": m["label"].astype(str).to_numpy(),
            "bucket": int(bucket[0]) if len(bucket) else None,
            "window_s": window, "checks": check_df,
            "all_ok": bool(check_df["ok"].all())}


def alert_reduction_recomputed() -> pd.DataFrame:
    """events / incidents / reduction per source from the incidents table."""
    inc = incidents()
    g = inc.groupby("source", sort=False).agg(incidents=("incident_id", "size"),
                                              events=("n_events", "sum"))
    g["alert_reduction"] = 1 - g["incidents"] / g["events"]
    return g.reset_index()


# --------------------------------------------------------------------------
# Live inference with the saved integrated model
# --------------------------------------------------------------------------
def load_model():
    """The saved integrated RandomForestClassifier (read-only joblib load)."""
    import joblib
    return joblib.load(path(MODEL))


def model_feature_order() -> list[str]:
    return pd.read_csv(path(MODEL_FEATURES))["feature"].astype(str).tolist()


def incident_feature_matrix(inc_rows: pd.DataFrame) -> pd.DataFrame:
    """Incident features exactly as Stage 4 fed them (detect.feature_matrix)."""
    det = _pipeline("detect")
    return det.feature_matrix(inc_rows, model_feature_order())[0]


def live_proba(model, inc_rows: pd.DataFrame) -> pd.DataFrame:
    X = incident_feature_matrix(inc_rows)
    proba = model.predict_proba(X)
    return pd.DataFrame(proba, columns=[str(c) for c in model.classes_],
                        index=inc_rows.index)


def saved_incident_predictions(preds: pd.DataFrame) -> pd.Series:
    """incident_id -> saved integrated prediction (must be unique per incident)."""
    g = preds.groupby("incident_id", sort=False, observed=True)["pred_integrated"]
    nun = g.nunique()
    if (nun > 1).any():
        raise ValueError("an incident has several saved integrated predictions")
    return g.first().astype(str)


def verify_live_inference(preds: pd.DataFrame, model=None, batch: int = 50_000) -> dict:
    """Live ``predict`` of the saved model on every test incident vs saved."""
    t0 = time.perf_counter()
    model = model or load_model()
    saved = saved_incident_predictions(preds)
    inc = incidents().set_index("incident_id").reindex(saved.index)
    if inc["n_events"].isna().any():
        raise KeyError("test incident missing from the incident table")
    live = []
    for i in range(0, len(inc), batch):
        X = incident_feature_matrix(inc.iloc[i:i + batch])
        live.append(model.predict(X).astype(str))
    live = np.concatenate(live)
    agree = live == saved.to_numpy()
    mism = saved.index[~agree][:20].tolist()
    return {"n_test_incidents": int(len(saved)), "n_agree": int(agree.sum()),
            "n_mismatch": int((~agree).sum()), "mismatch_examples": mism,
            "seconds": round(time.perf_counter() - t0, 2),
            "model": rel(path(MODEL)),
            "model_sha256": sha256_file(path(MODEL)),
            "checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def load_live_check() -> dict | None:
    """Result of verify_live_inference.py if run against the current model."""
    if not LIVE_CHECK.is_file():
        return None
    d = json.loads(LIVE_CHECK.read_text(encoding="utf-8"))
    d["model_unchanged"] = d.get("model_sha256") == sha256_file(path(MODEL))
    return d


# --------------------------------------------------------------------------
# Event-level access (pages 2 and 4)
# --------------------------------------------------------------------------
def event_feature_names() -> list[str]:
    """The 20 baseline event features (Stage 2 plan, decision = kept)."""
    plan = pd.read_csv(path(FEATURE_PLAN))
    return plan.loc[plan["decision"] == "kept", "feature"].astype(str).tolist()


def class_events(source: str, cls: str) -> tuple[np.ndarray, np.ndarray]:
    """(event_ids, ts) of one class in one capture, sorted by (ts, event_id)."""
    srow = _source_index().set_index("source").loc[source]
    lo, hi = int(srow["first_event_id"]), int(srow["first_event_id"] + srow["n_events"])
    ids, tss = [], []
    for s in interim_spans():
        if s.end <= lo or s.start >= hi:
            continue
        t = pq.read_table(s.path, columns=["label", "ts"])
        pos = pc.indices_nonzero(pc.equal(t.column("label"), cls))
        if len(pos) == 0:
            continue
        ids.append(pos.to_numpy().astype("int64") + s.start)
        tss.append(t.column("ts").take(pos).to_numpy(zero_copy_only=False))
    if not ids:
        return np.array([], dtype="int64"), np.array([], dtype="float64")
    ids, tss = np.concatenate(ids), np.concatenate(tss).astype("float64")
    # NaN timestamps sort last; ties keep stream (file) order.
    order = np.lexsort((ids, np.where(np.isnan(tss), np.inf, tss)))
    return ids[order], tss[order]


def to_utc(ts) -> pd.Series:
    """Epoch seconds -> ISO 8601 UTC, rounded to the microsecond."""
    us = np.round(pd.Series(ts, dtype="float64") * 1e6)
    s = pd.to_datetime(us, unit="us", utc=True)
    return s.dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def event_rows(event_ids: Iterable[int]) -> pd.DataFrame:
    """Staged raw records + split + incident for a bounded set of events."""
    ids = np.asarray(list(event_ids), dtype="int64")
    raw = take_rows(interim_spans(), ids)
    split = take_rows(stage2_spans(), ids, ["split"])
    inc = take_rows(stage3_spans(), ids, ["incident_id"])
    idx = _source_index()
    first = dict(zip(idx["source"], idx["first_event_id"]))
    fam = dict(zip(idx["source"], idx["dataset"]))
    out = pd.DataFrame({
        "dataset": raw["source"].map(fam), "capture": raw["source"],
        "event_id": ids,
        "record_in_file": ids - raw["source"].map(first).to_numpy(dtype="int64"),
        "ts_utc": to_utc(raw["ts"]).to_numpy(), "ts_epoch": raw["ts"].to_numpy(),
        "src_ip": raw["src_ip"], "sport": raw.get("sport"),
        "dst_ip": raw["dst_ip"], "dport": raw.get("dport"),
        "proto": raw["proto"], "label": raw["label"],
        "split": split["split"].to_numpy(),
        "incident_id": inc["incident_id"].to_numpy()})
    other = [c for c in raw.columns if c not in
             ("event_id", "source", "ts", "src_ip", "sport", "dst_ip",
              "dport", "proto", "label")]

    def attrs(r: pd.Series) -> str:
        return "; ".join(f"{c}={_fmt_attr(r[c])}" for c in other
                         if _clean(r[c]) is not None)
    out["attributes (non-null raw columns)"] = raw.apply(attrs, axis=1).to_numpy()
    return out


def _fmt_attr(v) -> str:
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def raw_attributes(event_id: int) -> dict:
    """All non-null staged raw columns of one event."""
    row = take_rows(interim_spans(), [event_id]).iloc[0].to_dict()
    return {k: _clean(v) for k, v in row.items() if _clean(v) is not None}


def event_features(event_id: int) -> dict:
    """The baseline's 20 Stage 2 (scaled / encoded) features of one event."""
    names = event_feature_names()
    row = take_rows(stage2_spans(), [event_id], names).iloc[0]
    return {n: _clean(row[n]) for n in names}


# --------------------------------------------------------------------------
# Artefacts (page 5 traceability)
# --------------------------------------------------------------------------
def artefact_paths() -> list[tuple[str, Path]]:
    groups = [("results", sorted(path("results").glob("*.*"))),
              ("report", sorted(path(REPORT_DIR).glob("*.*"))),
              ("transcripts", sorted(path(TRANSCRIPTS).glob("*.*"))),
              ("model", sorted(path("models").glob("*.*"))),
              ("stage 1 staged", [s.path for s in interim_spans()]),
              ("stage 2", [path(FEATURE_PLAN)] + [s.path for s in stage2_spans()]),
              ("stage 3", [path("data/processed/stage3_alert_stats.csv")]
               + [s.path for s in stage3_spans()]
               + [path(INCIDENTS), path(DIAGNOSTICS)])]
    return [(g, p) for g, ps in groups for p in ps if p.is_file()]


def artefact_table() -> pd.DataFrame:
    rows = [{"group": g, "path": rel(p), "bytes": p.stat().st_size,
             "sha256": sha256_file(p)} for g, p in artefact_paths()]
    return pd.DataFrame(rows)


def raw_hash_check() -> pd.DataFrame:
    """Current SHA-256 of each raw file vs the hash recorded in the manifest."""
    ds = manifest_datasets()
    cur = []
    for r in ds["raw_file"]:
        p = path(r)
        cur.append(sha256_file(p) if p.is_file() else "missing")
    ds = ds.assign(sha256_now=cur)
    ds["match"] = ds["sha256"] == ds["sha256_now"]
    return ds[["source", "dataset", "raw_file", "bytes", "sha256", "sha256_now", "match"]]
