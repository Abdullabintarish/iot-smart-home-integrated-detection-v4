"""Keep a lossless gzip of a full eve.json and replace eve.json by its alert lines.

The pipeline reads only event_type == "alert" from eve.json (read_eve with
event_types=("alert",)), so the alerts-only file gives an identical frame;
this is checked before the full file is removed. Hashes go to shrink_eve.json.

    python shrink_eve.py <sensor_out/<capture>/suricata>
"""
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "cross_log" / "src"))
from zeek_io import read_eve  # noqa: E402


def sha256_stream(fh) -> str:
    h = hashlib.sha256()
    for b in iter(lambda: fh.read(1 << 24), b""):
        h.update(b)
    return h.hexdigest()


def main(d: Path) -> None:
    eve, gz, alerts = d / "eve.json", d / "eve.json.full.gz", d / "eve.alerts.json"
    with open(eve, "rb") as fh:
        full_hash = sha256_stream(fh)
    with open(eve, "rb") as src, gzip.open(gz, "wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst, 1 << 24)
    with gzip.open(gz, "rb") as fh:
        assert sha256_stream(fh) == full_hash, "gzip round trip differs"
    with open(eve, encoding="utf-8") as src, open(alerts, "w", encoding="utf-8", newline="") as dst:
        for line in src:
            if '"event_type":"alert"' in line and json.loads(line).get("event_type") == "alert":
                dst.write(line)
    a, b = read_eve(eve, event_types=("alert",)), read_eve(alerts, event_types=("alert",))
    assert a.equals(b), "alerts-only frame differs"
    rec = {"full_eve_sha256": full_hash, "full_eve_bytes": eve.stat().st_size,
           "gzip_sha256": hashlib.sha256(gz.read_bytes()).hexdigest(), "gzip_bytes": gz.stat().st_size,
           "alerts_only_lines": int(len(b)), "read_eve_alert_frame_identical": True}
    eve.unlink()
    alerts.rename(eve)
    rec["alerts_only_sha256"] = hashlib.sha256(eve.read_bytes()).hexdigest()
    (d / "shrink_eve.json").write_text(json.dumps(rec, indent=2))
    print(json.dumps(rec))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
