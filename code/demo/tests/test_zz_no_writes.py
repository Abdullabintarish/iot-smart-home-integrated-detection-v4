"""Runs last: nothing outside demo/ was created, changed or deleted."""
import unittest

import _common


class TestNoWritesOutsideDemo(unittest.TestCase):
    def test_code_folder_unchanged(self):
        before, after = _common.SNAPSHOT_BEFORE, _common.snapshot_now()
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(k for k in before if k in after and before[k] != after[k])
        self.assertEqual((added, removed, changed), ([], [], []),
                         f"added={added[:10]} removed={removed[:10]} changed={changed[:10]}")


if __name__ == "__main__":
    unittest.main()
