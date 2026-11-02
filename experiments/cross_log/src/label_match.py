"""Stage 3 step 5: attach IoT-23 labels to newly generated Zeek conn records.

A new record and a labelled record match when they have the same Community ID
(computed for the labelled rows, which predate it) and start times within
``LABEL_TS_TOLERANCE_S``. Matching is one-to-one, closest start time first.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import LABEL_TS_TOLERANCE_S, thesis_class
from community_id import community_id


def _cid_row(oh, rh, proto, op, rp) -> str | None:
    try:
        return community_id(oh, rh, proto, int(op), int(rp))
    except (ValueError, TypeError):
        return None


def labelled_with_cid(labelled: pd.DataFrame) -> pd.DataFrame:
    lab = labelled.copy()
    lab["community_id"] = [
        _cid_row(*r) for r in zip(lab["id.orig_h"], lab["id.resp_h"], lab["proto"],
                                  lab["id.orig_p"], lab["id.resp_p"])]
    lab["ts"] = lab["ts"].astype(float)
    lab["cls"] = [thesis_class(b, d) for b, d in
                  zip(lab["label"], lab["detailed_label"])]
    return lab


def match(new_conn: pd.DataFrame, labelled: pd.DataFrame,
          tol: float = LABEL_TS_TOLERANCE_S) -> tuple[pd.DataFrame, dict]:
    """Return ``new_conn`` with label columns, plus match statistics."""
    lab = labelled_with_cid(labelled).reset_index(drop=True)
    new = new_conn.copy().reset_index(drop=True)
    new["ts"] = new["ts"].astype(float)
    pairs = new[["ts", "community_id"]].reset_index().merge(
        lab[["ts", "community_id"]].reset_index(), on="community_id",
        suffixes=("_n", "_l"))
    pairs["d"] = (pairs["ts_n"] - pairs["ts_l"]).abs()
    pairs = pairs[pairs["d"] <= tol].sort_values(
        ["d", "index_n", "index_l"], kind="mergesort")
    used_n: set[int] = set()
    used_l: set[int] = set()
    assign = np.full(len(new), -1, dtype=np.int64)
    for i_n, i_l in zip(pairs["index_n"].to_numpy(), pairs["index_l"].to_numpy()):
        if i_n in used_n or i_l in used_l:
            continue
        used_n.add(i_n)
        used_l.add(i_l)
        assign[i_n] = i_l
    ok = assign >= 0
    for col in ("label", "detailed_label", "cls"):
        vals = np.full(len(new), None, dtype=object)
        vals[ok] = lab[col].to_numpy()[assign[ok]]
        new[col] = vals
    new["label_matched"] = ok
    stats = {
        "new_conn_records": int(len(new)),
        "labelled_records": int(len(lab)),
        "matched": int(ok.sum()),
        "match_rate_new": round(float(ok.mean()), 6) if len(new) else None,
        "labelled_covered": round(float(ok.sum() / len(lab)), 6) if len(lab) else None,
        "ts_tolerance_s": tol,
        "matched_by_class": {k: int(v) for k, v in
                             pd.Series(new.loc[ok, "cls"]).value_counts().items()},
    }
    return new, stats
