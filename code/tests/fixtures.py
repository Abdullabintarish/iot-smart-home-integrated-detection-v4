"""Synthetic fixtures modelled on the real raw formats (no real data copied).

Every builder writes into a caller-supplied directory, normally a
``tempfile.TemporaryDirectory``, so tests never touch ``data/``.
"""
from __future__ import annotations

from pathlib import Path

import dpkt

T = "\t"
_HEAD = ("#separator \\x09\n#set_separator\t,\n#empty_field\t(empty)\n"
         "#unset_field\t-\n#path\tconn\n#open\t2019-01-01-00-00-00\n")
_BASE_FIELDS = ("ts uid id.orig_h id.orig_p id.resp_h id.resp_p proto service "
                "duration orig_bytes resp_bytes conn_state local_orig local_resp "
                "missed_bytes history orig_pkts orig_ip_bytes resp_pkts "
                "resp_ip_bytes").split()

# (binary label, detailed label, expected class) for every value seen in the
# real IoT-23 logs, plus C&C-PartOfAHorizontalPortScan from other captures.
# Every "C&C-" variant is command-and-control, whatever follows the prefix.
ZEEK_CASES = (
    ("Benign", "-", "benign"),
    ("benign", "-", "benign"),
    ("Malicious", "PartOfAHorizontalPortScan", "recon"),
    ("Malicious", "C&C", "c2"),
    ("Malicious", "C&C-Torii", "c2"),
    ("Malicious", "C&C-FileDownload", "c2"),
    ("Malicious", "C&C-PartOfAHorizontalPortScan", "c2"),
    ("Malicious", "FileDownload", "malware"),
    ("Malicious", "Attack", "malware"),
    ("Malicious", "DDoS", "dos"),
    ("Malicious", "-", "malware"),
)


def _zeek_body(i: int) -> list[str]:
    """20 base conn.log values for synthetic row ``i``."""
    return [f"{1547150789.5 + i:.6f}", f"Cuid{i}", "192.168.1.10",
            str(40000 + i), "10.0.0.1", "80", "tcp", "-", "1.5", "100", "200",
            "SF", "-", "-", "0", "ShADadfF", "3", "180", "2", "300"]


def write_zeek_spacejoined(path: Path) -> Path:
    """21 declared fields; the label tail joined by 3 spaces (9 real logs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = _BASE_FIELDS + ["tunnel_parents   label   detailed-label"]
    lines = [_HEAD, "#fields\t" + T.join(fields) + "\n"]
    for i, (b, d, _) in enumerate(ZEEK_CASES):
        lines.append(T.join(_zeek_body(i) + [f"-   {b}   {d}"]) + "\n")
    lines.append("#close\t2019-01-01-01-00-00\n")
    path.write_text("".join(lines), encoding="utf-8")
    return path


def write_zeek_det_label(path: Path) -> Path:
    """23 proper tab fields, detailed column named ``det_label`` (34-1)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = _BASE_FIELDS + ["tunnel_parents", "label", "det_label"]
    body = _zeek_body(0)
    # Unset / empty values in numeric and string columns.
    body[8] = body[9] = body[10] = "-"
    body[7] = "(empty)"
    rows = [body + ["-", "Benign", "-"],
            _zeek_body(1) + ["-", "Malicious", "C&C"],
            _zeek_body(2) + ["(empty)", "Malicious", "DDoS"]]
    lines = [_HEAD, "#fields\t" + T.join(fields) + "\n"]
    lines += [T.join(r) + "\n" for r in rows]
    path.write_text("".join(lines), encoding="utf-8")
    return path


def write_zeek_headerless(path: Path) -> Path:
    """No ``#fields`` directive: the standard 23-column order is assumed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_zeek_body(0) + ["-", "Malicious", "PartOfAHorizontalPortScan"],
            _zeek_body(1) + ["-", "Benign", "-"]]
    path.write_text("".join(T.join(r) + "\n" for r in rows), encoding="utf-8")
    return path


BOTIOT_HEADER = (
    "pkSeqID,stime,flgs,proto,saddr,sport,daddr,dport,pkts,bytes,state,ltime,"
    "seq,dur,mean,stddev,smac,dmac,sum,min,max,soui,doui,sco,dco,spkts,dpkts,"
    "sbytes,dbytes,rate,srate,drate,attack,category,subcategory ")


def _botiot_row(seq: int, stime: float, proto: str, sport: str, dport: str,
                attack: int, category: str, sub: str) -> str:
    return (f"{seq},{stime},e,{proto},192.168.100.{seq},{sport},"
            f"192.168.100.200,{dport},4,240,CON,{stime + 10},{seq},10.0,"
            f"0.1,0.01,,,0.4,0.05,0.2,,,,,2,2,120,120,0.4,0.2,0.2,"
            f"{attack},{category},{sub}")


# (proto, sport, dport, category, subcategory, expected label, sport, dport)
BOTIOT_CASES = (
    ("tcp", "139", "36390", "Normal", "Normal", "benign", 139.0, 36390.0),
    ("udp", "6000", "53", "Reconnaissance", "OS_Fingerprint", "recon",
     6000.0, 53.0),
    ("tcp", "1822", "80", "DoS", "HTTP", "dos", 1822.0, 80.0),
    ("udp", "2001", "80", "DDoS", "UDP", "dos", 2001.0, 80.0),
    ("tcp", "40000", "21", "Theft", "Keylogging", "theft", 40000.0, 21.0),
    ("arp", "", "", "Normal", "Normal", "benign", None, None),
    ("icmp", "0x0303", "0x817e", "Reconnaissance", "Service_Scan", "recon",
     771.0, 33150.0),
)


def write_botiot_csv(path: Path) -> Path:
    """Kaggle Bot-IoT layout: 35 columns, ``subcategory `` with a space."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [BOTIOT_HEADER]
    for i, (proto, sp, dp, cat, sub, *_rest) in enumerate(BOTIOT_CASES, 1):
        attack = 0 if cat == "Normal" else 1
        lines.append(_botiot_row(i, 1526344121.0 + i, proto, sp, dp, attack,
                                 cat, sub))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _eth(ip: dpkt.ip.IP) -> bytes:
    return bytes(dpkt.ethernet.Ethernet(src=b"\x00\x01\x02\x03\x04\x05",
                                        dst=b"\x00\x01\x02\x03\x04\x06",
                                        type=dpkt.ethernet.ETH_TYPE_IP,
                                        data=ip))


def _ip(src: bytes, dst: bytes, l4) -> dpkt.ip.IP:
    p = dpkt.ip.IP_PROTO_TCP if isinstance(l4, dpkt.tcp.TCP) else dpkt.ip.IP_PROTO_UDP
    ip = dpkt.ip.IP(src=src, dst=dst, p=p, data=l4)
    ip.len = len(ip)
    return ip


A, B, C = b"\x0a\x00\x00\x01", b"\x0a\x00\x00\x02", b"\x0a\x00\x00\x03"


def write_pcap(path: Path) -> tuple[Path, int]:
    """TCP A<->B (3 fwd, 2 bwd), UDP A->C (2 pkts), one ARP frame.

    Returns the path and the number of IP packets written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tcp = dpkt.tcp
    frames = [
        _eth(_ip(A, B, tcp.TCP(sport=40000, dport=80, flags=tcp.TH_SYN))),
        _eth(_ip(B, A, tcp.TCP(sport=80, dport=40000,
                               flags=tcp.TH_SYN | tcp.TH_ACK))),
        _eth(_ip(A, B, tcp.TCP(sport=40000, dport=80, flags=tcp.TH_ACK))),
        _eth(_ip(A, C, dpkt.udp.UDP(sport=5353, dport=53, data=b"q"))),
        _eth(_ip(A, B, tcp.TCP(sport=40000, dport=80,
                               flags=tcp.TH_PUSH | tcp.TH_ACK, data=b"GET"))),
        _eth(_ip(B, A, tcp.TCP(sport=80, dport=40000, flags=tcp.TH_FIN))),
        _eth(_ip(A, C, dpkt.udp.UDP(sport=5353, dport=53, data=b"q2"))),
        # Non-IP frame (ARP): must be skipped, not counted.
        bytes(dpkt.ethernet.Ethernet(src=b"\x00" * 6, dst=b"\xff" * 6,
                                     type=dpkt.ethernet.ETH_TYPE_ARP,
                                     data=dpkt.arp.ARP())),
    ]
    with path.open("wb") as fh:
        w = dpkt.pcap.Writer(fh)
        for i, f in enumerate(frames):
            w.writepkt(f, ts=1000.0 + i)
    return path, 7
