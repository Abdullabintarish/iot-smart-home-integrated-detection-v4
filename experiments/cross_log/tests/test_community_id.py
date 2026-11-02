import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from community_id import community_id  # noqa: E402


class CommunityIdTest(unittest.TestCase):
    def test_spec_example_tcp(self):
        # Example from the community-id-spec README.
        self.assertEqual(
            community_id("128.232.110.120", "66.35.250.204", "tcp", 34855, 80),
            "1:LQU9qZlK+B5F3KDmev6m5PMibrg=")

    def test_direction_independent(self):
        a = community_id("10.0.0.1", "10.0.0.2", "udp", 5353, 53)
        b = community_id("10.0.0.2", "10.0.0.1", "udp", 53, 5353)
        self.assertEqual(a, b)

    def test_icmp_echo_pair(self):
        req = community_id("10.0.0.1", "10.0.0.2", "icmp", 8, 0)
        rep = community_id("10.0.0.2", "10.0.0.1", "icmp", 0, 0)
        self.assertEqual(req, rep)

    def test_seed_changes_hash(self):
        self.assertNotEqual(
            community_id("10.0.0.1", "10.0.0.2", "tcp", 1, 2, seed=0),
            community_id("10.0.0.1", "10.0.0.2", "tcp", 1, 2, seed=1))


if __name__ == "__main__":
    unittest.main()
