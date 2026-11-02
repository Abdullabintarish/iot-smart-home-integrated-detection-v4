"""Read-only pcap pre-check (NOT a replacement for Zeek).

For each candidate capture it reports packet count, time range and how many
IoT-23 labelled conn.log rows have their Community ID among the pcap's IP flows
and a start time inside the pcap's time range. This only estimates whether the
pcap is the one the labels were made from; the real match rate is measured on
Zeek output in Stage 3.

Usage: python pcap_precheck.py <pcaps_dir> <out_json>
"""
from __future__ import annotations

import json
import socket
import sys
from collections import Counter
from pathlib import Path

import dpkt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from community_id import community_id  # noqa: E402
from zeek_io import read_zeek_tsv  # noqa: E402


def _ip(b: bytes) -> str:
    return socket.inet_ntop(socket.AF_INET6 if len(b) == 16 else socket.AF_INET, b)


def scan_pcap(path: Path) -> dict:
    cids: set[str] = set()
    n = n_ip = 0
    t0 = t1 = None
    with open(path, "rb") as fh:
        try:
            reader = dpkt.pcap.Reader(fh)
        except ValueError:
            fh.seek(0)
            reader = dpkt.pcapng.Reader(fh)
        link = reader.datalink()
        for ts, buf in reader:
            n += 1
            t0 = ts if t0 is None else min(t0, ts)
            t1 = ts if t1 is None else max(t1, ts)
            try:
                if link == dpkt.pcap.DLT_EN10MB:
                    ip = dpkt.ethernet.Ethernet(buf).data
                elif link == dpkt.pcap.DLT_LINUX_SLL:
                    ip = dpkt.sll.SLL(buf).data
                else:
                    ip = dpkt.ip.IP(buf)
            except Exception:
                continue
            if not isinstance(ip, (dpkt.ip.IP, dpkt.ip6.IP6)):
                continue
            n_ip += 1
            l4 = ip.data
            proto = ip.p if isinstance(ip, dpkt.ip.IP) else ip.nxt
            sp = dp = None
            if isinstance(l4, (dpkt.tcp.TCP, dpkt.udp.UDP)):
                sp, dp = l4.sport, l4.dport
            elif isinstance(l4, (dpkt.icmp.ICMP, dpkt.icmp6.ICMP6)):
                sp, dp = l4.type, l4.code
            try:
                cids.add(community_id(_ip(ip.src), _ip(ip.dst), proto, sp, dp))
            except Exception:
                continue
    return {"packets": n, "ip_packets": n_ip, "ts_first": t0, "ts_last": t1,
            "linktype": link, "distinct_flow_cids": len(cids), "_cids": cids}


def check(capture_dir: Path) -> dict:
    pcap = next(p for p in capture_dir.iterdir() if p.suffix == ".pcap")
    lab = read_zeek_tsv(capture_dir / "conn.log.labeled.server").rename(
        columns={"id.orig_h": "oh", "id.orig_p": "op", "id.resp_h": "rh",
                 "id.resp_p": "rp"})
    info = scan_pcap(pcap)
    cids = info.pop("_cids")
    in_pcap = in_time = 0
    labels = Counter()
    for r in lab.itertuples(index=False):
        labels[r.label] += 1
        try:
            cid = community_id(r.oh, r.rh, r.proto, int(r.op), int(r.rp))
        except Exception:
            continue
        if cid in cids:
            in_pcap += 1
            if info["ts_first"] - 1 <= float(r.ts) <= info["ts_last"] + 1:
                in_time += 1
    n = len(lab)
    return {"capture": capture_dir.name, "pcap": pcap.name,
            "pcap_bytes": pcap.stat().st_size, **info,
            "labeled_rows": n, "labels": dict(labels),
            "labeled_ts_first": float(lab["ts"].astype(float).min()),
            "labeled_ts_last": float(lab["ts"].astype(float).max()),
            "rows_cid_in_pcap": in_pcap, "rows_cid_and_time_in_pcap": in_time,
            "share_cid_and_time_in_pcap": round(in_time / n, 4) if n else None}


def main() -> None:
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    res = [check(d) for d in sorted(root.iterdir()) if d.is_dir()]
    out.write_text(json.dumps(res, indent=2))
    for r in res:
        print(r["capture"], r["packets"], r["labeled_rows"],
              r["share_cid_and_time_in_pcap"], r["labels"])


if __name__ == "__main__":
    main()
