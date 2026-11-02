"""Readers for Zeek TSV logs, IoT-23 labelled conn.logs and Suricata eve.json."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

# IoT-23 conn.log.labeled: the last header field is the literal
# "tunnel_parents   label   detailed-label" joined by spaces, not tabs.
_IOT23_TAIL = "tunnel_parents   label   detailed-label"


def read_zeek_tsv(path: Path) -> pd.DataFrame:
    """Read a Zeek ASCII log (``#fields`` header). Returns strings only.

    IoT-23 labelled logs end each row with ``tunnel_parents<3 spaces>label
    <3 spaces>detailed-label``; those are split into three columns, and
    ``label`` is lower-cased ("benign" / "malicious").
    """
    fields: list[str] | None = None
    rows: list[list[str]] = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("#fields"):
                fields = line.split("\t")[1:]
                continue
            if line.startswith("#") or not line:
                continue
            rows.append(line.split("\t"))
    if fields is None:
        raise ValueError(f"{path}: no #fields header")
    iot23 = fields[-1] == _IOT23_TAIL
    if iot23:
        fields = fields[:-1] + ["tunnel_parents", "label", "detailed_label"]
        rows = [r[:-1] + (r[-1].split("   ") + ["-", "-", "-"])[:3] for r in rows]
    df = pd.DataFrame(rows, columns=fields)
    # Some IoT-23 logs (e.g. capture 34-1) use proper tab-separated
    # "label" / "det_label" columns instead.
    df = df.rename(columns={"det_label": "detailed_label",
                            "detailed-label": "detailed_label"})
    if "label" in df.columns:
        df["label"] = df["label"].str.strip().str.lower()
    if "detailed_label" in df.columns:
        df["detailed_label"] = df["detailed_label"].str.strip()
    return df


def read_eve(path: Path, event_types=("alert", "dns", "flow")) -> pd.DataFrame:
    """Flatten Suricata eve.json lines of the given event types."""
    recs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            e = json.loads(line)
            if e.get("event_type") not in event_types:
                continue
            a = e.get("alert") or {}
            recs.append({
                "event_type": e.get("event_type"),
                "timestamp": e.get("timestamp"),
                "src_ip": e.get("src_ip"), "src_port": e.get("src_port"),
                "dest_ip": e.get("dest_ip"), "dest_port": e.get("dest_port"),
                "proto": e.get("proto"), "community_id": e.get("community_id"),
                "flow_id": e.get("flow_id"),
                "signature_id": a.get("signature_id"),
                "signature": a.get("signature"),
                "category": a.get("category"), "severity": a.get("severity"),
            })
    df = pd.DataFrame(recs)
    if not df.empty:
        # Epoch seconds independent of the datetime resolution: pandas 3 parses
        # these timestamps as datetime64[us], so dividing the int64 value by
        # 1e9 (which assumes ns) gave times 1,000x too small.
        t = pd.to_datetime(df["timestamp"], utc=True)
        df["ts"] = (t - pd.Timestamp(0, tz="UTC")) / pd.Timedelta(seconds=1)
    return df
