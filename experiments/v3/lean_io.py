"""Memory-lean drop-in for cross_log/src/zeek_io.read_zeek_tsv (v3 only).

The original reader builds a Python list of string lists, which needs roughly
17 GB per 13.6 M-row log (captures 36-1 and 7-1) and does not fit in RAM. This
reader parses the same files with pandas' C parser into Arrow-backed strings
and applies the same post-processing (IoT-23 3-space tail split, column
renames, label lower/strip). verify_lean_io() checks frame equality against
the original reader on every original capture before the reader is used.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "cross_log" / "src"))
import zeek_io  # noqa: E402

_IOT23_TAIL = zeek_io._IOT23_TAIL


def _header(path: Path) -> tuple[list[str], int]:
    n = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith("#"):
                break
            n += 1
            if line.startswith("#fields"):
                fields = line.rstrip("\n").split("\t")[1:]
    return fields, n


def read_zeek_tsv(path: Path) -> pd.DataFrame:
    fields, skip = _header(path)
    df = pd.read_csv(path, sep="\t", header=None, names=fields, skiprows=skip, dtype=str,
                     na_filter=False, quoting=csv.QUOTE_NONE, encoding_errors="replace",
                     skip_blank_lines=True, engine="c")
    df = df[~df[fields[0]].str.startswith("#")].reset_index(drop=True)
    if fields[-1] == _IOT23_TAIL:
        parts = df[fields[-1]].str.split("   ", expand=True)
        for i in range(3):
            if i not in parts.columns:
                parts[i] = "-"
        parts = parts[[0, 1, 2]].fillna("-")
        df = df.drop(columns=fields[-1])
        df["tunnel_parents"], df["label"], df["detailed_label"] = parts[0], parts[1], parts[2]
    df = df.rename(columns={"det_label": "detailed_label", "detailed-label": "detailed_label"})
    if "label" in df.columns:
        df["label"] = df["label"].str.strip().str.lower()
    if "detailed_label" in df.columns:
        df["detailed_label"] = df["detailed_label"].str.strip()
    return df


def same_frame(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    if list(a.columns) != list(b.columns) or len(a) != len(b):
        return False
    return all((a[c].astype(object).to_numpy() == b[c].astype(object).to_numpy()).all()
               for c in a.columns)


def verify_lean_io(roots: list[Path], skip: tuple[str, ...] = ()) -> dict:
    """Original vs lean reader on every conn/dns/labelled log under the roots."""
    out = {}
    for root in roots:
        for cap in sorted(p.name for p in (root / "pcaps").iterdir() if p.is_dir()):
            if cap in skip:
                continue
            for p in (root / "sensor_out" / cap / "zeek" / "conn.log",
                      root / "sensor_out" / cap / "zeek" / "dns.log",
                      root / "pcaps" / cap / "conn.log.labeled.server"):
                if p.exists():
                    out[f"{cap}/{p.name}"] = same_frame(zeek_io.read_zeek_tsv(p), read_zeek_tsv(p))
                    print(cap, p.name, out[f"{cap}/{p.name}"], flush=True)
    return out


if __name__ == "__main__":
    import json
    skip = tuple(sys.argv[1:])
    res = verify_lean_io([HERE.parent / "cross_log"], skip)
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "lean_io_check.json").write_text(
        json.dumps({"skipped": list(skip), "checks": res, "all_equal": all(res.values())}, indent=2))
    print("all_equal", all(res.values()))
