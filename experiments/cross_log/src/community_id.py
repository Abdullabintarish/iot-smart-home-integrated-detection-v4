"""Community ID v1 (https://github.com/corelight/community-id-spec).

Used to give IoT-23 labelled conn.log rows, which predate Community ID, the
same flow hash that Zeek and Suricata write, so records can be matched.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import struct

PROTO_NUM = {"icmp": 1, "tcp": 6, "udp": 17, "icmp6": 58, "sctp": 132}
# ICMP type -> reply type, used to make ICMP "ports" symmetric (spec 3.3).
_ICMP4_PAIRS = {8: 0, 0: 8, 13: 14, 14: 13, 15: 16, 16: 15, 17: 18, 18: 17,
                10: 9, 9: 10}
_ICMP6_PAIRS = {128: 129, 129: 128, 133: 134, 134: 133, 135: 136, 136: 135,
                130: 131, 131: 130}


def community_id(saddr: str, daddr: str, proto, sport: int | None,
                 dport: int | None, seed: int = 0) -> str:
    """Return the ``1:<base64>`` Community ID of one flow."""
    p = PROTO_NUM.get(str(proto).lower(), proto)
    p = int(p)
    s = ipaddress.ip_address(saddr).packed
    d = ipaddress.ip_address(daddr).packed
    has_ports = p in (1, 6, 17, 58, 132) and sport is not None and dport is not None
    sp, dp = (int(sport), int(dport)) if has_ports else (0, 0)
    one_way = False
    if p in (1, 58) and has_ports:
        pairs = _ICMP4_PAIRS if p == 1 else _ICMP6_PAIRS
        # Zeek/Suricata pass ICMP type as sport and code as dport.
        if sp in pairs:
            dp = pairs[sp]
        else:
            one_way = True
    # Order endpoints so both directions hash the same.
    if not one_way and (s, sp) > (d, dp):
        s, d, sp, dp = d, s, dp, sp
    buf = struct.pack("!H", seed) + s + d + struct.pack("!BB", p, 0)
    if has_ports:
        buf += struct.pack("!HH", sp, dp)
    return "1:" + base64.b64encode(hashlib.sha1(buf).digest()).decode()
