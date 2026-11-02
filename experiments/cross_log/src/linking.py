"""Stage 3 step 6: link conn, DNS and alert records into incidents.

1. Community ID first: all records of one flow (conn row, its DNS rows via
   ``uid``, Suricata alerts with the same ``community_id``) form one flow group.
   A flow group is never split.
2. Then host + window: flow groups (and records without a Community ID) are
   linked when they have the same capture, the same local host and their first
   timestamp falls in the same tumbling ``WINDOW_S`` bucket, as in the thesis
   Stage 3 (``floor(ts / window)``).

An incident is cross-source when it holds at least two record types.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from common import WINDOW_S, local_host

RECORD_TYPES = ("conn", "dns", "alert")


def records(capture: str, conn: pd.DataFrame, dns: pd.DataFrame,
            alerts: pd.DataFrame) -> pd.DataFrame:
    """One table of all records with ``rtype, ts, cid, host, capture, rid``."""
    c = pd.DataFrame({
        "rtype": "conn", "ts": conn["ts"].astype(float).to_numpy(),
        "cid": conn["community_id"].to_numpy(), "uid": conn["uid"].to_numpy(),
        "host": [local_host(a, b) for a, b in
                 zip(conn["id.orig_h"], conn["id.resp_h"])]})
    cid_by_uid = dict(zip(conn["uid"], conn["community_id"]))
    d = pd.DataFrame({
        "rtype": "dns", "ts": dns["ts"].astype(float).to_numpy() if len(dns) else [],
        "cid": [cid_by_uid.get(u) for u in dns["uid"]] if len(dns) else [],
        "uid": dns["uid"].to_numpy() if len(dns) else [],
        "host": [local_host(a, b) for a, b in
                 zip(dns["id.orig_h"], dns["id.resp_h"])] if len(dns) else []})
    a = pd.DataFrame({
        "rtype": "alert", "ts": alerts["ts"].astype(float).to_numpy() if len(alerts) else [],
        "cid": alerts["community_id"].to_numpy() if len(alerts) else [],
        "uid": None,
        "host": [local_host(s, t) for s, t in
                 zip(alerts["src_ip"], alerts["dest_ip"])] if len(alerts) else []})
    out = pd.concat([c, d, a], ignore_index=True)
    out["capture"] = capture
    out["rid"] = out["rtype"] + ":" + out.groupby("rtype").cumcount().astype(str)
    return out


def link(rec: pd.DataFrame, window_s: int = WINDOW_S) -> pd.DataFrame:
    """Add ``flow_group`` and ``incident_id`` to the record table."""
    rec = rec.copy()
    has_cid = rec["cid"].notna() & (rec["cid"].astype(str) != "-")
    fg = np.where(has_cid, "cid|" + rec["capture"] + "|" + rec["cid"].astype(str),
                  "rec|" + rec["capture"] + "|" + rec["rid"])
    rec["flow_group"] = fg
    g = rec.groupby("flow_group", sort=False)
    first_ts = g["ts"].transform("min")
    # Host of the flow group = host of its earliest record (conn first on ties).
    order = rec.assign(_t=rec["rtype"].map({"conn": 0, "dns": 1, "alert": 2}))
    order = order.sort_values(["flow_group", "ts", "_t"], kind="mergesort")
    host_of = order.drop_duplicates("flow_group").set_index("flow_group")["host"]
    rec["anchor_host"] = rec["flow_group"].map(host_of)
    rec["bucket"] = np.floor_divide(first_ts.to_numpy(), max(1, window_s)).astype("int64")
    key = (rec["capture"] + "|" + rec["anchor_host"].astype(str) + "|"
           + rec["bucket"].astype(str) + f"|w{window_s}")
    uniq = {k: hashlib.blake2b(k.encode(), digest_size=8).hexdigest()
            for k in key.unique()}
    rec["incident_id"] = key.map(uniq)
    return rec


def incident_summary(rec: pd.DataFrame) -> dict:
    types = rec.groupby("incident_id")["rtype"].agg(lambda s: tuple(sorted(set(s))))
    combos = types.map("+".join).value_counts()
    n_types = types.map(len)
    cid_cross = rec[rec["flow_group"].str.startswith("cid|")].groupby(
        "flow_group")["rtype"].nunique()
    return {
        "records": {t: int((rec["rtype"] == t).sum()) for t in RECORD_TYPES},
        "incidents": int(len(types)),
        "incidents_ge2_source_types": int((n_types >= 2).sum()),
        "incidents_all_3_types": int((n_types == 3).sum()),
        "incident_type_combinations": {k: int(v) for k, v in combos.items()},
        "flow_groups_linked_by_cid_ge2_types": int((cid_cross >= 2).sum()),
    }
