import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from zeek_io import read_eve  # noqa: E402


class ReadEveTest(unittest.TestCase):
    def test_timestamp_is_epoch_seconds(self):
        # Regression test: alert times were 1,000x too small under pandas 3.
        ev = {"event_type": "alert", "timestamp": "2019-01-10T17:34:51.790672+0400",
              "src_ip": "192.168.1.197", "dest_ip": "1.2.3.4", "proto": "TCP",
              "community_id": "1:x", "alert": {"signature_id": 1, "category": "c",
                                               "severity": 2}}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "eve.json"
            p.write_text(json.dumps(ev) + "\n" + json.dumps({"event_type": "flow"}) + "\n")
            a = read_eve(p, event_types=("alert",))
        # 2019-01-10T13:34:51.790672Z
        self.assertAlmostEqual(a["ts"].iloc[0], 1547127291.790672, places=5)
        self.assertEqual(len(a), 1)


if __name__ == "__main__":
    unittest.main()
