"""Pre-flight check for raw source files, before committing to a full run.

    .venv/bin/python check_sources.py [root]

Parses the first few thousand rows of every file under ``root`` with the same
Stage 1 readers the pipeline uses, then reports, per file: which reader handled
it, how many rows it yields, the label distribution, and - importantly - whether
the columns Stage 3 correlates on (src_ip, dst_ip, proto) were actually found.
That last warning is what catches a CSV whose vendor column names differ from
the canonical schema, which would otherwise only surface as a silent failure
several minutes into a full run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from pipeline.config import DATA_RAW
from pipeline.ingest import (flows_from_csv, flows_from_pcap, flows_from_zeek_log,
                             iter_source_files, kind_of, out_of_vocabulary,
                             source_name)

# Columns the correlation stage and the flow key depend on.
REQUIRED = ("src_ip", "dst_ip", "proto")
SAMPLE_ROWS = 5000


def _peek(gen) -> pd.DataFrame:
    """First SAMPLE_ROWS rows of a streaming reader, without draining it."""
    parts, total = [], 0
    for chunk in gen:
        parts.append(chunk)
        total += len(chunk)
        if total >= SAMPLE_ROWS:
            break
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True).head(SAMPLE_ROWS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path, nargs="?", default=DATA_RAW,
                    help="directory of raw captures / flow tables (default: data/raw)")
    ap.add_argument("--quiet", action="store_true",
                    help="only print problems")
    args = ap.parse_args()

    files = iter_source_files(args.root)
    if not files:
        print(f"no source files found under {args.root}")
        return 1

    print(f"checking {len(files)} file(s) under {args.root}\n")
    problems = 0
    for path in files:
        kind = kind_of(path)
        source = source_name(path)
        try:
            if kind == "csv":
                df = _peek(flows_from_csv(path, source))
            elif kind == "zeek":
                df = _peek(flows_from_zeek_log(path, source))
            else:
                df = _peek(flows_from_pcap(path, source, "unknown"))
        except Exception as exc:                       # noqa: BLE001 - report, don't crash
            print(f"  FAIL  {source:40s} {kind:5s} {type(exc).__name__}: {exc}")
            problems += 1
            continue

        if df.empty:
            print(f"  WARN  {source:40s} {kind:5s} parsed 0 rows")
            problems += 1
            continue

        missing = [c for c in REQUIRED if c not in df.columns]
        labels = df["label"].value_counts().to_dict() if "label" in df.columns else {}
        # Labels the shared vocabulary does not know, or rows with no label at
        # all, would otherwise flow silently into training as extra classes.
        oov = out_of_vocabulary(labels)
        n_unknown = int(labels.get("unknown", 0))
        bad_labels = bool(oov or n_unknown)
        status = "ok  " if not (missing or bad_labels) else "WARN"
        if missing or bad_labels:
            problems += 1
        print(f"  {status}  {source:40s} {kind:5s} {len(df):>6,} rows sampled")
        if oov:
            print(f"        >>> labels outside config.CLASSES: {oov}")
        if n_unknown:
            print(f"        >>> {n_unknown:,} sampled row(s) labelled 'unknown'")
        if not args.quiet or missing or bad_labels:
            print(f"        labels : {labels}")
            print(f"        columns: {len(df.columns)} "
                  f"({', '.join(sorted(df.columns)[:8])}"
                  f"{'...' if len(df.columns) > 8 else ''})")
            if missing:
                print(f"        >>> MISSING correlation columns: {missing}")
                print("        >>> Stage 3 cannot key on this file; map its "
                      "column names in ingest.CANONICAL_COLUMNS.")

    print()
    if problems:
        print(f"{problems} file(s) need attention before a full run.")
        return 1
    print("all sources parsed cleanly - ready for run_all.ps1 (Windows) "
          "or ./run_all.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
