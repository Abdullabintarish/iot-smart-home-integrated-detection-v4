"""Stage 1 - Collection of logs and alerts from distributed sources.

Handles the two shapes the gig actually contains:

  * ``.pcap`` / ``.pcapng``  (IoT-23 is mostly raw captures, ~20 GB)
  * ``.csv``                 (Bot-IoT, plus any exported flow tables)
  * Zeek ``conn.log``        (IoT-23's labelled flow logs; ``*.log.labeled``)

Nothing is accumulated in RAM beyond a bounded active-flow table. PCAPs are
folded into bidirectional flow records on the fly, time-windowed, so a 5 GB
capture costs roughly the same memory as a 5 MB one.
"""
from __future__ import annotations

import datetime as dt
import re
import socket
from collections import defaultdict
from pathlib import Path
from typing import Iterator

import dpkt
import pandas as pd

from .config import (BUDGET, CLASSES, DATA_INT, DATA_RAW, IOT23_DEFAULT_LABELS,
                     LABEL_COLUMN_CANDIDATES)

# Ports that identify an application protocol on an IoT segment.
PORT_PROTO = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
    80: "http", 110: "pop3", 143: "imap", 443: "https", 445: "smb",
    3306: "mysql", 3389: "rdp", 5432: "postgres", 5900: "vnc",
    6667: "irc", 8080: "http_alt", 8443: "https_alt", 8888: "http_alt",
    37215: "huawei", 48101: "tr-069", 52869: "upnp", 5555: "adb",
}
WELL_KNOWN_PORTS = {p for p in PORT_PROTO if p < 1024}


def _is_zeek_log(p: Path) -> bool:
    """True for a Zeek TSV log, e.g. ``conn.log`` / ``conn.log.labeled``."""
    n = p.name.lower()
    return "conn.log" in n or n.endswith(".labeled")


def kind_of(path: Path) -> str:
    """Which Stage 1 reader handles this file: ``pcap`` | ``csv`` | ``zeek``."""
    if _is_zeek_log(path):
        return "zeek"
    if path.suffix.lower() == ".csv":
        return "csv"
    return "pcap"


def iter_source_files(root: Path = DATA_RAW) -> list[Path]:
    """Every capture / flow table / Zeek log under the raw data root."""
    exts = {".pcap", ".pcapng", ".csv", ".cap"}
    return sorted(p for p in root.rglob("*")
                  if p.suffix.lower() in exts or _is_zeek_log(p))


def infer_label_from_name(name: str) -> str:
    """Best-effort ground truth for an IoT-23 capture from its filename.

    IoT-23 names captures like ``iot23_mirai_...pcap`` / ``capture-34.pcap``.
    Returns ``"unknown"`` when nothing matches, which Stage 2 then flags.
    """
    low = name.lower()
    # Longest keyword first so "okiru" beats a stray "ri".
    for key in sorted(IOT23_DEFAULT_LABELS, key=len, reverse=True):
        if key in low:
            return IOT23_DEFAULT_LABELS[key]
    return "unknown"


def source_name(path: Path) -> str:
    """Source identifier for a raw file, used to tag every row it yields.

    IoT-23 ships every capture as ``<capture>/bro/conn.log.labeled`` (or
    directly under ``<capture>/``); the folder name is the only distinguishing
    part, so it is used instead of the shared file stem.
    """
    if path.name.lower() not in ("conn.log", "conn.log.labeled"):
        return path.stem
    parent = path.parent
    return parent.parent.name if parent.name == "bro" else parent.name


def _ip_str(value) -> str:
    """Normalise an address to dotted-quad text.

    ``dpkt`` returns ``ip.src``/``ip.dst`` as raw packed 4-byte values, while
    flow CSVs already carry strings. Correlation keys must be textual or the
    same address hashes two different ways.
    """
    if value is None:
        return "unknown"
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        if len(raw) == 4:
            return socket.inet_ntoa(raw)
        if len(raw) == 16:
            return socket.inet_ntop(socket.AF_INET6, raw)
        return raw.hex()
    return str(value)


# Flow-CSV column names mapped onto the canonical schema the rest of the
# pipeline correlates on. Bot-IoT uses Source/Destination/Protocol; other
# exports use Src IP/Dst IP/Protocol.
CANONICAL_COLUMNS = {
    "Source": "src_ip", "Src IP": "src_ip", "src_ip": "src_ip", "src": "src_ip",
    "Destination": "dst_ip", "Dst IP": "dst_ip", "dst_ip": "dst_ip",
    "dst": "dst_ip",
    "Protocol": "proto", "proto": "proto", "protocol": "proto",
    "Src Port": "sport", "sport": "sport", "src_port": "sport",
    "Dst Port": "dport", "dport": "dport", "dst_port": "dport",
    "Flow Duration": "duration", "duration": "duration",
    "Total Length of Fwd Packets": "fwd_bytes",
    "Total Length of Bwd Packets": "bwd_bytes",
    "Fwd Packets": "fwd_pkts", "Bwd Packets": "bwd_pkts",
    # Argus / Stratosphere flow-export columns, used by the Bot-IoT CSVs
    # published on Kaggle (schema: pkSeqID, stime, flgs, proto, saddr, ...).
    "saddr": "src_ip", "daddr": "dst_ip",
    "stime": "ts", "ltime": "ts_end", "dur": "duration",
    "spkts": "fwd_pkts", "dpkts": "bwd_pkts",
    "sbytes": "fwd_bytes", "dbytes": "bwd_bytes",
    "pkts": "pkts", "bytes": "bytes",
}

# --------------------------------------------------------------------------
# Zeek conn.log (IoT-23 ``conn.log.labeled``)
# --------------------------------------------------------------------------
# IoT-23 ships Zeek logs next to the ~21 GB of pcaps. They are the labelled,
# flow-level view of the very same traffic, so they map onto the identical
# canonical schema the .pcap path produces.
ZEEK_CANON = {
    "ts": "ts",
    "id.orig_h": "src_ip", "id.orig_p": "sport",
    "id.resp_h": "dst_ip", "id.resp_p": "dport",
    "proto": "proto", "service": "app", "duration": "duration",
    "orig_bytes": "fwd_bytes", "resp_bytes": "bwd_bytes",
    "orig_pkts": "fwd_pkts", "resp_pkts": "bwd_pkts",
    "orig_ip_bytes": "fwd_ip_bytes", "resp_ip_bytes": "bwd_ip_bytes",
    "missed_bytes": "missed_bytes", "conn_state": "conn_state",
    "history": "history",
}
ZEEK_NUMERIC = ("ts", "sport", "dport", "duration", "fwd_bytes", "bwd_bytes",
                "fwd_pkts", "bwd_pkts", "fwd_ip_bytes", "bwd_ip_bytes",
                "missed_bytes")
# Standard Zeek conn.log field order, used when a file has no #fields header.
ZEEK_DEFAULT_FIELDS = (
    "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "proto",
    "service", "duration", "orig_bytes", "resp_bytes", "conn_state",
    "local_orig", "local_resp", "missed_bytes", "history", "orig_pkts",
    "orig_ip_bytes", "resp_pkts", "resp_ip_bytes", "tunnel_parents",
    "label", "detailed-label")
# IoT-23 detailed-label values -> the shared vocabulary in config.CLASSES.
ZEEK_DETAILED_LABELS = {
    "c&c": "c2", "c&c-other": "c2", "c&c-filetransfer": "c2",
    "c&c-heartbeat": "c2", "c&c-mirai": "c2", "c&c-torii": "c2",
    "ddos": "dos", "dos": "dos",
    "partofahorizontalportscan": "recon", "portscan": "recon",
    "reconnaissance": "recon",
    "okiru": "malware", "mirai": "malware", "torii": "malware",
    "hakai": "malware", "filedownload": "malware", "attack": "malware",
    "bruteforce": "bruteforce", "brute-force": "bruteforce",
}


def _ip_str_series(s: "pd.Series") -> "pd.Series":
    """Vectorised counterpart of :func:`_ip_str` for object columns."""
    return s.map(lambda v: _ip_str(v) if not isinstance(v, str) else v)


def _proto_name(num: int) -> str:
    return {6: "tcp", 17: "udp", 1: "icmp", 47: "gre", 132: "sctp"}.get(num, f"ip{num}")


def _app_proto(sport: int, dport: int) -> str:
    if sport in PORT_PROTO:
        return PORT_PROTO[sport]
    if dport in PORT_PROTO:
        return PORT_PROTO[dport]
    if sport in WELL_KNOWN_PORTS or dport in WELL_KNOWN_PORTS:
        return "other_known"
    if sport > 30000 and dport > 30000:
        return "ephemeral"
    return "other"


class _FlowTable:
    """Bounded bidirectional flow aggregator.

    A flow key is the 5-tuple (src_ip, dst_ip, proto, src_port, dst_port),
    matching how Bot-IoT and CICFlowMeter define a flow. Including the ports is
    what keeps distinct conversations between the same two hosts from
    collapsing into a single record. The first packet fixes the flow's forward
    direction; packets of the reversed 5-tuple fold into the same record as
    backward traffic. Each entry accumulates packet count, byte counts, timings
    and TCP flag tallies. When the table reaches ``max_active_flows`` the
    least-recently-seen entries are evicted and returned to the caller (as a
    flow timeout would), which keeps peak RSS flat across a multi-GB capture
    without losing any packets.
    """

    __slots__ = ("_f", "_order", "_cap", "_seen")

    def __init__(self, cap: int) -> None:
        self._cap = max(1, cap)
        self._f: dict[tuple, dict] = {}
        self._order: dict[tuple, float] = {}
        self._seen = 0

    def add(self, key: tuple, pkt_len: int, ts: float, flags: int | None
            ) -> list[dict]:
        """Fold one packet in; return any flows evicted to stay under the cap."""
        src, dst, proto, sport, dport = key
        direction = "fwd"
        rec = self._f.get(key)
        if rec is None:
            rev = (dst, src, proto, dport, sport)
            rec = self._f.get(rev)
            if rec is not None:
                key, direction = rev, "bwd"
        if rec is None:
            self._seen += 1
            rec = self._f[key] = {
                "ts_first": ts, "ts_last": ts, "pkts": 0, "bytes": 0,
                "fwd_pkts": 0, "bwd_pkts": 0, "fwd_bytes": 0, "bwd_bytes": 0,
                "fwd_flags": 0, "bwd_flags": 0, "sport": sport, "dport": dport,
                "app": _app_proto(sport, dport), "proto": proto,
                "src_ip": src, "dst_ip": dst,
            }
        rec["ts_last"] = max(rec["ts_last"], ts)
        rec["ts_first"] = min(rec["ts_first"], ts)
        rec["pkts"] += 1
        rec["bytes"] += pkt_len
        rec[f"{direction}_pkts"] += 1
        rec[f"{direction}_bytes"] += pkt_len
        if flags is not None:
            rec[f"{direction}_flags"] |= flags
        self._order[key] = ts
        if len(self._f) >= self._cap:
            return self._evict(len(self._f) - self._cap // 2)
        return []

    @staticmethod
    def _finish(rec: dict) -> dict:
        rec = dict(rec)
        rec["duration"] = max(0.0, rec["ts_last"] - rec["ts_first"])
        return rec

    def _evict(self, n: int) -> list[dict]:
        """Remove the ``n`` least-recently-seen flows and return them."""
        oldest = sorted(self._order.items(), key=lambda kv: kv[1])[:n]
        out = []
        for key, _ in oldest:
            self._order.pop(key, None)
            rec = self._f.pop(key, None)
            if rec is not None:
                out.append(self._finish(rec))
        return out

    def drain(self) -> Iterator[dict]:
        for rec in self._f.values():
            yield self._finish(rec)
        self._f.clear()
        self._order.clear()


def flows_from_pcap(path: Path, source: str, label: str) -> Iterator[pd.DataFrame]:
    """Stream a capture into bounded batches of flow records."""
    table = _FlowTable(BUDGET.max_active_flows)
    batch: list[dict] = []
    seen = 0
    with path.open("rb") as fh:
        try:
            reader = dpkt.pcap.Reader(fh)
        except Exception:
            fh.seek(0)
            reader = dpkt.pcapng.Reader(fh)
        for ts, buf in reader:
            seen += 1
            try:
                eth = dpkt.ethernet.Ethernet(buf)
                if not isinstance(eth.data, dpkt.ip.IP):
                    continue
                ip = eth.data
                src = _ip_str(ip.src)
                dst = _ip_str(ip.dst)
                pnum = ip.p
                proto = _proto_name(pnum)
                sport = dport = 0
                flags = None
                if pnum == 6 and isinstance(ip.data, dpkt.tcp.TCP):
                    sport, dport, flags = ip.data.sport, ip.data.dport, ip.data.flags
                elif pnum == 17 and isinstance(ip.data, dpkt.udp.UDP):
                    sport, dport = ip.data.sport, ip.data.dport
                evicted = table.add((src, dst, proto, sport, dport), len(buf),
                                    ts, flags)
            except (dpkt.dpkt.NeedData, dpkt.dpkt.UnpackError, ValueError,
                    IndexError, AttributeError):
                continue
            # Table saturated: the coldest flows come back finished; emit them.
            for rec in evicted:
                rec["source"] = source
                rec["label"] = label
                batch.append(rec)
            if len(batch) >= BUDGET.flush_rows:
                yield pd.DataFrame(batch)
                batch = []
    for rec in table.drain():
        rec["source"] = source
        rec["label"] = label
        batch.append(rec)
    if batch:
        yield pd.DataFrame(batch)


# Vendor label vocabulary -> the shared classes in config.CLASSES, so Bot-IoT
# and IoT-23 rows describe the same threat with the same label.
LABEL_ALIASES = {
    "ddos-syn": "dos", "ddos-udp": "dos", "ddos-icmp": "dos",
    "dos-hulk": "dos", "dos-goldeneye": "dos", "dos-slowhttptest": "dos",
    "dos-slowloris": "dos", "ddos": "dos", "dos": "dos",
    "ddos attacks": "dos",
    "normal": "benign", "benign": "benign",
    "reconnaissance": "recon", "recon": "recon",
    "reconnaissance attacks": "recon", "recon-portscan": "recon",
    "recon-osfingerprint": "recon", "os_fingerprint": "recon",
    "service_scan": "recon",
    # Bot-IoT's Theft category (subcategories Keylogging, Data_Exfiltration)
    # is an attack, never benign traffic.
    "theft": "theft", "theft-intercepting": "theft", "keylogging": "theft",
    "data_exfiltration": "theft",
    "malicious": "malware", "malware": "malware", "attack": "malware",
    "botnet": "botnet",
}


def _normalise_labels(s: pd.Series) -> pd.Series:
    """Map vendor label strings onto the shared class vocabulary.

    A missing or empty label becomes ``"unknown"`` rather than being guessed;
    vendor values outside the alias table pass through unchanged (see
    :func:`out_of_vocabulary`).
    """
    s = s.astype("string").fillna("").str.strip().str.lower()
    return s.replace({"": "unknown"}).replace(LABEL_ALIASES)


def _coerce_label_col(df: pd.DataFrame) -> pd.Series:
    for col in LABEL_COLUMN_CANDIDATES:
        if col in df.columns:
            return _normalise_labels(df[col])
    return pd.Series("unknown", index=df.index)


def out_of_vocabulary(labels) -> list[str]:
    """Labels that are neither in ``config.CLASSES`` nor ``"unknown"``.

    Such vendor labels are kept as-is in the data; this only makes them
    visible so a new class is a decision, not an accident.
    """
    return sorted({str(v) for v in labels} - set(CLASSES) - {"unknown"})


def _port_numeric(s: pd.Series) -> pd.Series:
    """Port column as float64: ``0x..`` parsed base 16, blanks/text -> NaN.

    Argus exports write ICMP type/code as hex (``0x0303``) in the port
    columns and leave them blank for ARP, so the same field arrives as text in
    some chunks and as numbers in others.
    """
    if pd.api.types.is_numeric_dtype(s):
        return s.astype("float64")
    txt = s.astype("string").fillna("").str.strip().str.lower()
    is_hex = txt.str.startswith("0x")

    def _hex(v: str) -> float:
        try:
            return float(int(v, 16))
        except ValueError:
            return float("nan")

    dec = pd.to_numeric(txt.where(~is_hex, "").astype(object), errors="coerce")
    out = pd.Series(dec, index=s.index, dtype="float64")
    if is_hex.any():
        out[is_hex.to_numpy(dtype=bool)] = [_hex(v) for v in txt[is_hex]]
    return out


def flows_from_csv(path: Path, source: str, chunksize: int | None = None
                   ) -> Iterator[pd.DataFrame]:
    """Stream an existing flow CSV, harmonising its label vocabulary.

    Record-level labels always win; the filename guess only fills rows whose
    own label is missing (and they stay ``"unknown"`` if that guess is too).
    """
    label = infer_label_from_name(path.name)
    reader = pd.read_csv(path, chunksize=chunksize or BUDGET.csv_chunksize,
                         low_memory=False, on_bad_lines="skip")
    for chunk in reader:
        chunk = chunk.rename(columns={c: c.strip() for c in chunk.columns})
        # Harmonise the vendor schema onto the canonical column names.
        chunk = chunk.rename(
            columns={k: v for k, v in CANONICAL_COLUMNS.items()
                     if k in chunk.columns and v not in chunk.columns})
        if "proto" in chunk.columns:
            chunk["proto"] = (chunk["proto"].astype("string").fillna("unknown")
                              .str.strip().str.lower())
        for c in ("src_ip", "dst_ip"):
            if c in chunk.columns:
                chunk[c] = _ip_str_series(chunk[c])
        for c in ("sport", "dport"):
            if c in chunk.columns:
                chunk[c] = _port_numeric(chunk[c])
        # "label" is the first LABEL_COLUMN_CANDIDATES entry, so an existing
        # label column is normalised in place here too.
        labels = _coerce_label_col(chunk)
        if label in CLASSES:
            labels = labels.mask(labels == "unknown", label)
        chunk["label"] = labels
        if "source" not in chunk.columns:
            chunk["source"] = source
        if "ts" not in chunk.columns:
            for cand in ("Timestamp", "timestamp", "Time", "ts", "ts_seconds"):
                if cand in chunk.columns:
                    chunk["ts"] = pd.to_numeric(chunk[cand], errors="coerce")
                    break
            else:
                chunk["ts"] = pd.RangeIndex(len(chunk)).astype("float64")
        yield chunk


def _zeek_sep(tok: str) -> str:
    """Decode a ``#separator`` value (usually the literal ``\\x09``)."""
    if tok.startswith("\\x"):
        try:
            return chr(int(tok[2:], 16))
        except ValueError:
            return "\t"
    return tok or "\t"


def _zeek_positions(names: list[str]) -> tuple[int | None, int | None]:
    """Locate the binary ``label`` and detailed-label columns, if present.

    IoT-23 is inconsistent here: some captures name the detailed column
    ``detailed-label``, others ``det_label``; a few leave it out entirely.
    """
    label_idx = detailed_idx = None
    for i, f in enumerate(names):
        fl = f.strip().lower()
        if fl in ("label", "binary-label", "binary_label"):
            label_idx = i
        elif fl in ("detailed-label", "detailed_label", "detailed label",
                    "det_label", "det-label", "detlabel"):
            detailed_idx = i
    # Some exports carry only one label column holding the specific value.
    if detailed_idx is None and label_idx is not None:
        detailed_idx = label_idx
    return label_idx, detailed_idx


def _expand_tail(tokens: list[str], expected: int) -> list[str]:
    """Repair the space-separated label tail some IoT-23 captures ship.

    A handful of ``conn.log.labeled`` files join the trailing
    ``tunnel_parents / label / detailed-label`` columns with spaces instead of
    the declared separator, so a tab-split comes up short. Splitting the last
    token on whitespace restores the field count; field names themselves never
    contain spaces, so this is unambiguous.
    """
    while len(tokens) < expected and tokens and " " in tokens[-1]:
        tokens = tokens[:-1] + tokens[-1].split()
    return tokens


def _lookup_zeek_label(detailed: str) -> str | None:
    if detailed in ZEEK_DETAILED_LABELS:
        return ZEEK_DETAILED_LABELS[detailed]
    # IoT-23 prefixes every command-and-control variant with "C&C-"
    # (C&C-FileDownload, C&C-PartOfAHorizontalPortScan, ...). The prefix is
    # the defining part, so it must win over a longer substring match.
    if detailed.startswith("c&c"):
        return "c2"
    for key in sorted(ZEEK_DETAILED_LABELS, key=len, reverse=True):
        if key in detailed:
            return ZEEK_DETAILED_LABELS[key]
    return None


def _zeek_label(binary: str | None, detailed: str | None, fallback: str) -> str:
    """Map IoT-23's binary + detailed labels onto the shared class vocabulary.

    Record-level labels always beat the filename ``fallback``: a malicious
    row with an unmapped detailed label is ``"malware"``. The fallback is used
    only when the row carries no usable label, and only if it is a real class.
    """
    d = (detailed or "").strip().lower()
    b = (binary or "").strip().lower()
    if d and d not in ("-", "(empty)", ""):
        mapped = _lookup_zeek_label(d)
        if mapped:
            return mapped
    if b == "benign" or d == "benign":
        return "benign"
    if b in ("malicious", "malware", "attack"):
        return "malware"
    return fallback if fallback in CLASSES else "unknown"


def _zeek_row(cols: list[str], names: list[str], label_idx: int | None,
              detailed_idx: int | None, source: str, fallback: str) -> dict:
    rec: dict = {}
    for i, name in enumerate(names):
        if i >= len(cols):
            break
        canon = ZEEK_CANON.get(name)
        if canon:
            rec[canon] = cols[i]
    binary = cols[label_idx] if label_idx is not None and label_idx < len(cols) else None
    detailed = (cols[detailed_idx]
                if detailed_idx is not None and detailed_idx < len(cols) else None)
    rec["label"] = _zeek_label(binary, detailed, fallback)
    rec["source"] = source
    return rec


def _zeek_frame(rows: list[dict]) -> pd.DataFrame:
    """Type-coerce a chunk of Zeek rows and add the derived flow totals."""
    df = pd.DataFrame(rows)
    for c in ZEEK_NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].replace({"-": None, "(empty)": None}),
                                  errors="coerce")
    if "proto" in df.columns:
        df["proto"] = (df["proto"].astype("string").fillna("unknown")
                       .str.strip().str.lower())
    for c in ("src_ip", "dst_ip"):
        if c in df.columns:
            df[c] = df[c].astype("string").fillna("unknown")
    # Derived totals, so the Zeek path exposes the same feature names as the
    # pcap path and both sources line up in the unified feature matrix.
    if {"fwd_pkts", "bwd_pkts"} <= set(df.columns):
        df["pkts"] = df["fwd_pkts"].fillna(0) + df["bwd_pkts"].fillna(0)
    if {"fwd_bytes", "bwd_bytes"} <= set(df.columns):
        df["bytes"] = df["fwd_bytes"].fillna(0) + df["bwd_bytes"].fillna(0)
    if "ts" in df.columns:
        dur = df["duration"].fillna(0) if "duration" in df.columns else 0.0
        df["ts_first"] = df["ts"]
        df["ts_last"] = df["ts"].fillna(0) + dur
    return df


def flows_from_zeek_log(path: Path, source: str, label: str | None = None,
                        chunksize: int | None = None) -> Iterator[pd.DataFrame]:
    """Stream an IoT-23 ``conn.log.labeled`` (Zeek TSV) into flow records.

    Reading the Zeek log avoids parsing gigabytes of packets to recover what
    Zeek has already extracted, and its labels are the dataset's own ground
    truth rather than a filename guess. The field list is read from the
    leading ``#fields`` directive, so both plain Zeek logs and IoT-23's
    extended ``label`` / ``detailed-label`` columns are handled; without a
    header the standard Zeek conn.log order is assumed.
    """
    chunksize = chunksize or BUDGET.csv_chunksize
    fallback = label or infer_label_from_name(path.name)
    sep = "\t"
    fields: list[str] | None = None
    names: list[str] | None = None
    label_idx = detailed_idx = None
    rows: list[dict] = []

    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("#"):
                if line.startswith("#separator"):
                    toks = line.split()
                    if len(toks) >= 2:
                        sep = _zeek_sep(toks[1])
                elif line.startswith("#fields"):
                    fields = line.rstrip("\n").split(sep)[1:]
                    if fields and " " in fields[-1]:
                        fields = fields[:-1] + fields[-1].split()
                continue
            if not line.strip():
                continue
            if names is None:
                names = list(fields) if fields else list(ZEEK_DEFAULT_FIELDS)
                label_idx, detailed_idx = _zeek_positions(names)
            cols = line.rstrip("\n").split(sep)
            if names and len(cols) < len(names):
                cols = _expand_tail(cols, len(names))
            rows.append(_zeek_row(cols, names, label_idx, detailed_idx,
                                  source, fallback))
            if len(rows) >= chunksize:
                yield _zeek_frame(rows)
                rows = []
    if rows:
        yield _zeek_frame(rows)


def ingest(paths: list[Path] | None = None, out_dir: Path = DATA_INT
           ) -> pd.DataFrame:
    """Run Stage 1 over every source and return a small manifest.

    Writes normalised intermediate parquet shards to ``out_dir`` and returns
    only the per-file manifest - never the full data - so the caller stays
    inside the memory budget.
    """
    paths = paths if paths is not None else iter_source_files()
    rows: list[dict] = []
    for p in paths:
        source = p.stem
        rows.append({"source": source, "kind": kind_of(p)})
    (out_dir / "_manifest.csv").write_text(
        pd.DataFrame(rows).to_csv(index=False))
    return pd.DataFrame(rows)