import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trim_pcap import complete_prefix  # noqa: E402


def pcap_bytes(payloads, cut=0):
    out = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    for i, p in enumerate(payloads):
        out += struct.pack("<IIII", i, 0, len(p), len(p)) + p
    return out[:len(out) - cut] if cut else out


class TrimTest(unittest.TestCase):
    def test_complete_and_truncated(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.pcap"
            f.write_bytes(pcap_bytes([b"x" * 10, b"y" * 20]))
            self.assertEqual(complete_prefix(f), (24 + 26 + 36, 2, 86))
            f.write_bytes(pcap_bytes([b"x" * 10, b"y" * 20], cut=5))
            end, n, size = complete_prefix(f)
            self.assertEqual((end, n, size), (24 + 26, 1, 81))


if __name__ == "__main__":
    unittest.main()
