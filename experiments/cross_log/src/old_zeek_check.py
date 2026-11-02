"""Sensitivity check: does an older Zeek (Bro 2.6.4) reproduce IoT-23's conn.log?

Compares, for one capture, the IoT-23 labelled log with conn.logs written by
Bro 2.6.4 and by Zeek 9.0.1 (used in Stages 3-4): record counts, label match
rate, labelled-row coverage per class, and exact row agreement on
(ts, 5-tuple, conn_state, orig_pkts, resp_pkts).

    python old_zeek_check.py <capture> <bro_conn_log> <out_json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

import common  # noqa: F401
from community_id import community_id
from label_match import labelled_with_cid, match
from zeek_io import read_zeek_tsv

ROOT = Path(__file__).resolve().parents[1]
KEY = ["ts", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "proto",
       "conn_state", "orig_pkts", "resp_pkts"]


def with_cid(df: pd.DataFrame) -> pd.DataFrame:
    if "community_id" not in df.columns:
        df = df.copy()
        df["community_id"] = [
            community_id(a, b, p, int(x), int(y)) for a, b, p, x, y in
            zip(df["id.orig_h"], df["id.resp_h"], df["proto"],
                df["id.orig_p"], df["id.resp_p"])]
    return df


def summary(name: str, conn: pd.DataFrame, lab: pd.DataFrame) -> dict:
    out, st = match(with_cid(conn), lab)
    labc = labelled_with_cid(lab)
    per_class = {}
    for c, n in labc["cls"].value_counts().items():
        per_class[c] = {"labelled": int(n),
                        "matched": int((out["cls"] == c).sum()),
                        "coverage": round(float((out["cls"] == c).sum() / n), 4)}
    exact = conn[KEY].astype(str).merge(lab[KEY].astype(str).drop_duplicates(),
                                        on=KEY, how="inner")
    return {"sensor": name, "conn_records": int(len(conn)),
            "match_rate_new": st["match_rate_new"],
            "labelled_covered": st["labelled_covered"],
            "per_class": per_class,
            "rows_identical_to_iot23": int(len(exact)),
            "conn_state_counts": conn["conn_state"].value_counts().head(8).to_dict()}


def main(capture: str, bro_log: str, out_json: str) -> None:
    lab = read_zeek_tsv(ROOT / "pcaps" / capture / "conn.log.labeled.server")
    z9 = read_zeek_tsv(ROOT / "sensor_out" / capture / "zeek" / "conn.log")
    b26 = read_zeek_tsv(Path(bro_log))
    res = {"capture": capture, "iot23_labelled_rows": int(len(lab)),
           "results": [summary("zeek-9.0.1", z9, lab), summary("bro-2.6.4", b26, lab)]}
    Path(out_json).write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
