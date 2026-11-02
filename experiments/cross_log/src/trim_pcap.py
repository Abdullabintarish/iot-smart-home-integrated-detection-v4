"""Find pcaps whose last record is truncated and write a byte-exact prefix.

Zeek stops with "truncated dump file" on such files. The fix keeps every
complete record byte for byte and drops only the incomplete tail. The original
file is not changed; the copy is written next to it as <name>.trimmed.pcap.

Usage: python trim_pcap.py <pcaps_dir> <out_json>
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

_MAGIC = {b"\xd4\xc3\xb2\xa1": "<", b"\xa1\xb2\xc3\xd4": ">",
          b"\x4d\x3c\xb2\xa1": "<", b"\xa1\xb2\x3c\x4d": ">"}


def complete_prefix(path: Path) -> tuple[int, int, int]:
    """(bytes of complete records incl. header, complete records, file size)."""
    data = path.read_bytes()
    endian = _MAGIC.get(data[:4])
    if endian is None:
        raise ValueError(f"{path.name}: not a classic pcap file")
    off, n = 24, 0
    while off + 16 <= len(data):
        incl = struct.unpack(endian + "IIII", data[off:off + 16])[2]
        if off + 16 + incl > len(data):
            break
        off += 16 + incl
        n += 1
    return off, n, len(data)


def main() -> None:
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    report = []
    for pcap in sorted(root.glob("*/*.pcap")):
        if pcap.name.endswith(".trimmed.pcap"):
            continue
        end, n, size = complete_prefix(pcap)
        r = {"pcap": str(pcap.relative_to(root)), "size": size,
             "complete_records": n, "trailing_bytes_dropped": size - end}
        if end < size:
            dst = pcap.with_name(pcap.stem + ".trimmed.pcap")
            dst.write_bytes(pcap.read_bytes()[:end])
            r["trimmed_copy"] = dst.name
            r["trimmed_sha256"] = hashlib.sha256(dst.read_bytes()).hexdigest()
        report.append(r)
        print(r)
    out.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
