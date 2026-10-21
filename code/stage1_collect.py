"""Stage 1 driver - collect raw captures/flow tables into parquet shards.

    python stage1_collect.py [--root data/raw] [--limit-rows N]

Streams every .pcap/.csv/Zeek conn.log under --root through pipeline.ingest
and writes normalised shards to data/interim/. Reports peak RSS so the memory
ceiling is observable rather than assumed.
"""
from __future__ import annotations

import argparse
import time
from collections import Counter
from pathlib import Path

import pandas as pd

from pipeline.config import DATA_INT, DATA_RAW
from pipeline.ingest import (flows_from_csv, flows_from_pcap, flows_from_zeek_log,
                             infer_label_from_name, iter_source_files, kind_of,
                             source_name)
from pipeline.io_utils import peak_rss_mb


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=DATA_RAW)
    ap.add_argument("--out", type=Path, default=DATA_INT)
    ap.add_argument("--limit-rows", type=int, default=0,
                    help="stop after N rows per file (smoke tests)")
    args = ap.parse_args()

    files = iter_source_files(args.root)
    if not files:
        print(f"no captures found under {args.root}")
        return 1
    print(f"found {len(files)} source file(s) under {args.root}\n")

    args.out.mkdir(parents=True, exist_ok=True)
    # Idempotent runs: stale shards from a previous corpus would otherwise
    # mix into the new staging set.
    for old in args.out.glob("shard_*.parquet"):
        old.unlink()
    total_rows = 0
    shard_i = 0

    for path in files:
        t = time.perf_counter()
        # IoT-23 ships every capture as ``<scenario>/bro/conn.log.labeled``;
        # the folder name is the only distinguishing part, so use it.
        source = source_name(path)
        # Filename guess, only a fallback for rows without their own label.
        label = infer_label_from_name(path.name)
        kind = kind_of(path)

        buf: list[pd.DataFrame] = []
        written = 0
        counts: Counter = Counter()   # real per-file label distribution
        if kind == "csv":
            gen = flows_from_csv(path, source)
        elif kind == "zeek":
            gen = flows_from_zeek_log(path, source, label=label)
        else:
            gen = flows_from_pcap(path, source, label)
        for chunk in gen:
            buf.append(chunk)
            counts.update(chunk["label"].value_counts().to_dict())
            if sum(len(b) for b in buf) >= 200_000:
                pd.concat(buf, ignore_index=True).to_parquet(
                    args.out / f"shard_{shard_i:04d}.parquet", index=False)
                written += sum(len(b) for b in buf)
                total_rows += sum(len(b) for b in buf)
                shard_i += 1
                buf = []
            if args.limit_rows and written + sum(len(b) for b in buf) >= args.limit_rows:
                break
        if buf:
            n = sum(len(b) for b in buf)
            pd.concat(buf, ignore_index=True).to_parquet(
                args.out / f"shard_{shard_i:04d}.parquet", index=False)
            written += n
            total_rows += n
            shard_i += 1
        dist = " ".join(f"{k}={v}" for k, v in counts.most_common())
        print(f"  {source[:44]:46s} {kind:5s} {written:>9,} rows "
              f"{time.perf_counter() - t:6.1f}s  {dist}")

    print(f"\ntotal {total_rows:,} rows staged in {shard_i} shard(s)")
    print(f"peak RSS {peak_rss_mb():.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())