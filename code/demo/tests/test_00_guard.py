"""Takes the write-guard snapshot (via _common) before any other test runs."""
import unittest

import _common


class TestGuardSnapshot(unittest.TestCase):
    def test_snapshot_taken(self):
        self.assertGreater(len(_common.SNAPSHOT_BEFORE), 0)
        self.assertIn("results/stage5_report.json", _common.SNAPSHOT_BEFORE)


if __name__ == "__main__":
    unittest.main()
