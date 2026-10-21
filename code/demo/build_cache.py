"""Build the derived demo cache (demo/cache/) from verified outputs.

    python build_cache.py [--check]

Reads only results/*_event_predictions.csv, data/interim and
data/processed/stage2; writes only under demo/cache/. The cache is derived
and rebuildable (safe to delete); its manifest records the SHA-256 of every
input so the app can detect a stale cache.
"""
from __future__ import annotations

import argparse
import sys

import evidence as ev


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="only report whether the cache is ok / missing / stale")
    ap.add_argument("--deep", action="store_true",
                    help="with --check: re-hash every input")
    args = ap.parse_args()
    missing = ev.missing_evidence()
    if missing:
        print("missing verified evidence (run run_all.ps1 first):")
        for m in missing:
            print("  ", m)
        return 2
    if args.check:
        st = ev.cache_status(deep=args.deep)
        print(st["state"])
        for r in st["reasons"]:
            print("  ", r)
        return 0 if st["state"] == "ok" else 1
    meta = ev.build_cache()
    for k, v in meta["join_checks"].items():
        print(f"  {k}: {v}")
    print(f"  predictions joined: {meta['n_predictions']:,} events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
