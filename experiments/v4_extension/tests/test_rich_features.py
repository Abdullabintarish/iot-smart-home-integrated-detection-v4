"""Unit tests for the E1 rich incident features (hand-made data, no real data)."""
import sys, unittest
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rich_features as F
M = -1.0
ROLES = {"sport": "numeric", "dport": "numeric", "proto": "categorical", "bytes": "numeric",
         "duration": "numeric", "flgs": "categorical", "history": "categorical"}
FEATS = list(ROLES)

def example():
    # Group A: train, 10.0.0.1 -> 10.0.1.1 proto 6, bucket 0 (3 events)
    # Group B: test, same pair and bucket as A (2 events) -> must be its own group
    # Group C: train, 10.0.0.2 -> 10.0.1.1, bucket 0 (1 event, every numeric missing)
    # D: uncorrelatable train event (no IPs) -> singleton
    rows = [  # ts, src, dst, split, sport, dport, bytes, duration, flgs, history, label
        (10, "10.0.0.1", "10.0.1.1", "train", .1, .5, .2, .1, 1, 0, "dos"),
        (20, "10.0.0.1", "10.0.1.1", "train", .1, .6, .4, M, 1, 1, "dos"),
        (40, "10.0.0.1", "10.0.1.1", "train", .2, .6, M, .3, 2, 2, "benign"),
        (50, "10.0.0.1", "10.0.1.1", "test", .3, .7, .5, .5, 2, 3, "dos"),
        (60, "10.0.0.1", "10.0.1.1", "test", .3, .7, .7, .5, M, 3, "dos"),
        (70, "10.0.0.2", "10.0.1.1", "train", M, M, M, M, M, M, "recon"),
        (80, None, None, "train", .4, .4, .9, .9, 1, 4, "benign")]
    d = pd.DataFrame(rows, columns=["ts", "src_ip", "dst_ip", "split", "sport", "dport", "bytes",
                                    "duration", "flgs", "history", "label"])
    d["proto"] = 4.0; d["source"] = "CTU-IoT-Malware-Capture-1-1"
    return d

def rich(d, cats=None, na=None, max_share=None):
    if max_share is not None:
        old, F.MAX_SHARE_CATEGORIES = F.MAX_SHARE_CATEGORIES, max_share
    try:
        cats = cats or F.category_sets(d, ["proto", "flgs", "history"], na or {}, d["split"].eq("train").to_numpy())
        return F.rich_incident_context(d, 300, FEATS, ROLES, cats, na or {})
    finally:
        if max_share is not None:
            F.MAX_SHARE_CATEGORIES = old

class RichFeatures(unittest.TestCase):
    def setUp(self):
        self.d = example(); self.r = rich(self.d)

    def test_hand_values_group_a(self):
        a = self.r.iloc[0]
        self.assertEqual(a.n_events, 3); self.assertAlmostEqual(a.span_s, 30); self.assertAlmostEqual(a.events_per_s, 0.1)
        self.assertEqual(a.n_distinct_dst_port, 2); self.assertEqual(a.n_distinct_src_port, 2)
        self.assertEqual(a.n_distinct_dst_ip, 1); self.assertEqual(a.n_distinct_proto, 1)
        # bytes: sentinel ignored -> values .2, .4
        self.assertAlmostEqual(a.bytes_mean, .3, places=6); self.assertAlmostEqual(a.bytes_std, .1, places=6)
        self.assertAlmostEqual(a.bytes_min, .2, places=6); self.assertAlmostEqual(a.bytes_max, .4, places=6)
        self.assertAlmostEqual(a.bytes_median, .3, places=6); self.assertAlmostEqual(a.bytes_sum, .6, places=6)
        self.assertAlmostEqual(a.duration_mean, .2, places=6)                        # .1, .3
        self.assertAlmostEqual(a.flgs_share_1, 2 / 3, places=6); self.assertAlmostEqual(a.flgs_share_2, 1 / 3, places=6)
        self.assertEqual(a.n_distinct_flgs, 2)
        for i in (1, 2):                      # every event of a group carries the same row
            self.assertTrue(np.allclose(self.r.iloc[i].to_numpy(), a.to_numpy()))

    def test_no_group_crosses_split(self):
        b = self.r.iloc[3]                     # same key and bucket as A but test side
        self.assertEqual(b.n_events, 2); self.assertEqual(b.span_s, 10)
        self.assertAlmostEqual(b.bytes_mean, .6, places=6)
        self.assertEqual(b.flgs_share_2, 1.0)  # the missing flag is not a category
        self.assertEqual(b.n_distinct_flgs, 1)
        codes = F.group_codes(self.d, 300)
        g = pd.DataFrame({"g": codes, "s": self.d["split"]}).groupby("g")["s"].nunique()
        self.assertTrue((g == 1).all())

    def test_missing_sentinel_is_missing(self):
        c = self.r.iloc[5]                     # all numeric values missing
        for col in ("bytes_mean", "bytes_std", "bytes_min", "bytes_max", "bytes_median", "bytes_sum",
                    "flgs_share_1", "flgs_share_2"):
            self.assertEqual(c[col], F.FILL)
        self.assertEqual(c.n_distinct_dst_port, 0); self.assertEqual(c.n_distinct_flgs, 0)
        self.assertEqual(self.r.iloc[6].n_events, 1)          # singleton
        self.assertEqual(self.r.iloc[6].n_distinct_dst_ip, 0)

    def test_many_categories_use_top_share(self):
        r = rich(self.d, max_share=3)          # history has 4 training categories
        self.assertIn("history_top_share", r.columns)
        self.assertFalse(any(c.startswith("history_share_") for c in r.columns))
        self.assertAlmostEqual(r.iloc[0].history_top_share, 1 / 3, places=6)
        self.assertEqual(r.iloc[3].history_top_share, 1.0); self.assertEqual(r.iloc[0].n_distinct_history, 3)

    def test_categories_from_training_only(self):
        self.assertNotIn("history_share_3", self.r.columns)   # code 3 appears only in test
        self.assertIn("history_share_4", self.r.columns)

    def test_na_code_treated_as_missing(self):
        d = pd.concat([self.d, self.d.assign(source="data_1", flgs=9.0)], ignore_index=True)
        na = F.na_codes(d, ["flgs", "history", "proto"])
        self.assertEqual(na, {"flgs": 9.0})                     # data_* carries flgs 9 on every event
        r = F.rich_incident_context(d, 300, FEATS, ROLES,
                                    F.category_sets(d, ["proto", "flgs", "history"], na, d["split"].eq("train").to_numpy()), na)
        self.assertNotIn("flgs_share_9", r.columns)
        self.assertEqual(r.iloc[len(self.d)].flgs_share_1, F.FILL)

    def test_no_label_used(self):
        for lab in ("benign", "dos"):
            r = rich(self.d.assign(label=lab))
            pd.testing.assert_frame_equal(r, self.r)
        r = rich(self.d.drop(columns="label"))                  # works without any label column
        pd.testing.assert_frame_equal(r, self.r)
        with self.assertRaises(ValueError):
            F.rich_incident_context(self.d, 300, FEATS + ["label"], ROLES, {}, {})
        self.assertFalse(any("label" in c for c in self.r.columns))

    def test_thin_part_matches_ablation(self):
        thin = F.R.incident_context(self.d, 300)
        self.assertTrue(np.array_equal(self.r[F.R.INCIDENT].to_numpy(), thin.to_numpy()))

if __name__ == "__main__": unittest.main()
