"""Map the attack category of each Bot-IoT CSV without downloading it fully.

    .venv/bin/python probe_botiot.py [--max-files N] [--rows 200000]

Each published CSV is ~218 MB, but its zipped form is ~23 MB. This script
downloads only the zip, reads the ``category`` column from the first
``--rows`` rows *inside* the archive, records the distribution, then deletes
the zip. Result: a defensible map of which file covers which threat, so only
the scenarios named in section 3.3 (DDoS, DoS, reconnaissance) are downloaded
in full for the experiment.
"""
from __future__ import annotations

import argparse
import io
import zipfile
from collections import Counter
from pathlib import Path

import pandas as pd
from kaggle.api.kaggle_api_extended import KaggleApi

CACHE = Path("data/probe")


def category_of(csv_bytes: bytes, rows: int) -> tuple[dict, int]:
    """Category distribution from the head of one CSV inside a zip."""
    df = pd.read_csv(io.BytesIO(csv_bytes), usecols=["category"], nrows=rows)
    counts = df["category"].astype("string").str.strip().str.lower().value_counts()
    return {str(k): int(v) for k, v in counts.items()}, len(df)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="vigneshvenkateswaran/bot-iot")
    ap.add_argument("--max-files", type=int, default=12)
    ap.add_argument("--start", type=int, default=0,
                    help="skip this many files (ordered by their numeric suffix)")
    ap.add_argument("--rows", type=int, default=200_000)
    args = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    api = KaggleApi()
    api.authenticate()

    # kaggle 2.x returns a paged response object (20 files/page), and the
    # filename lives in .name (.ref is empty in this version).
    files, token = [], None
    while True:
        listing = api.dataset_list_files(args.dataset, page_token=token)
        files.extend(getattr(listing, "dataset_files", None)
                     or getattr(listing, "files", []))
        token = getattr(listing, "next_page_token", None)
        if not token:
            break
    targets = sorted(((getattr(f, "name", "") or getattr(f, "ref", "")) for f in files),
                     key=lambda n: int("".join(c for c in n if c.isdigit()) or 0))
    targets = [n for n in targets if n.endswith(".csv")]
    selected = targets[args.start:args.start + args.max_files]
    print(f"{len(targets)} csv file(s) in the dataset; probing "
          f"{len(selected)} starting at index {args.start}\n")

    for ref in selected:
        zip_path = CACHE / f"{ref}.zip"
        try:
            if not zip_path.exists():
                api.dataset_download_file(args.dataset, ref, path=str(CACHE),
                                          force=True)
                produced = CACHE / ref
                if produced.suffix == ".zip":
                    produced.rename(zip_path)
            with zipfile.ZipFile(zip_path) as zf:
                member = zf.namelist()[0]
                data = zf.read(member)
            dist, n = category_of(data, args.rows)
            top = ", ".join(f"{k}={v}" for k, v in list(dist.items())[:5])
            print(f"  {ref:14s} rows~{n:<7} {top}")
        except Exception as exc:                       # noqa: BLE001 - keep going
            print(f"  {ref:14s} ERROR {type(exc).__name__}: {exc}")
        finally:
            if zip_path.exists():
                zip_path.unlink()      # keep only the summary, not the data
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
