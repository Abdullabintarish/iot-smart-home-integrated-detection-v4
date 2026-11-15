"""Tests for the audit gaps (P3, 2026-11-03). Synthetic data only.

    code/.venv/Scripts/python.exe -B -m unittest discover -s experiments/v2/tests
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
SUB = V2.parents[1]
sys.path.insert(0, str(V2))
sys.path.insert(0, str(SUB / "experiments" / "cross_log" / "src"))
sys.path.insert(0, str(SUB / "experiments" / "ablation"))
sys.path.insert(0, str(SUB / "code"))
sys.path.insert(0, str(SUB / "experiments" / "cross_log" / "tests"))

import ablation_v2 as AV  # noqa: E402
import cross_log_v2 as XV  # noqa: E402
from common import local_host  # noqa: E402
from experiment import train_sample  # noqa: E402
from features import _window_bounds  # noqa: E402
from label_match import match  # noqa: E402
from manifest import REQUIRED, write_manifest  # noqa: E402
from test_pipeline import conn_df, row  # noqa: E402


def xl_frame(n=2000, seed=0):
    r = np.random.default_rng(seed)
    cls = np.array(["benign"] * (n - 40) + ["c2"] * 5 + ["malware"] * 35)
    return pd.DataFrame({"cls": cls, "y": (cls != "benign").astype(int),
                         "capture": r.choice(["a", "b"], n), "ctx1": r.random(n),
                         "ctx2": r.integers(0, 3, n).astype(float)})


class CrossLogSamplingTest(unittest.TestCase):
    def test_class_stratified_keeps_every_rare_class_row(self):
        df = xl_frame()
        s = XV.class_stratified_sample(df, seed=1, budget=500)
        self.assertEqual(s["cls"].value_counts()["c2"], 5)
        self.assertEqual(s["cls"].value_counts()["malware"], 35)
        self.assertEqual(s["cls"].value_counts()["benign"], 500)

    def test_binary_sampling_can_lose_rare_class(self):
        """Documents audit defect D1: the historical sampler balances y only."""
        df = xl_frame()
        counts = [train_sample(df, s, budget=10)["cls"].value_counts().get("c2", 0)
                  for s in range(20)]
        self.assertLess(min(counts), 5)


class NegativeControlTest(unittest.TestCase):
    def setUp(self):
        self.df = xl_frame()
        self.out = XV.add_controls(self.df, ["ctx1", "ctx2"], seed=3)

    def test_zero_columns_are_zero(self):
        self.assertTrue((self.out[["z_ctx1", "z_ctx2"]] == 0).all().all())

    def test_permutation_stays_within_capture_and_keeps_rows_joint(self):
        for k, g in self.out.groupby("capture"):
            orig = self.df[self.df["capture"] == k]
            self.assertEqual(sorted(map(tuple, g[["p_ctx1", "p_ctx2"]].to_numpy())),
                             sorted(map(tuple, orig[["ctx1", "ctx2"]].to_numpy())))
        self.assertFalse(np.array_equal(self.out["p_ctx1"], self.df["ctx1"]))

    def test_original_columns_unchanged(self):
        pd.testing.assert_frame_equal(self.out[self.df.columns], self.df)


class CausalWindowTest(unittest.TestCase):
    def test_record_exactly_at_ts_included_and_older_than_window_excluded(self):
        ev = np.array([0.0, 99.999, 100.0, 400.0, 400.001])
        lo, hi = _window_bounds(ev, np.array([400.0]), 300)
        self.assertEqual(ev[lo[0]:hi[0]].tolist(), [100.0, 400.0])


class LocalHostTest(unittest.TestCase):
    def test_cases(self):
        self.assertEqual(local_host("192.168.1.2", "8.8.8.8"), "192.168.1.2")
        self.assertEqual(local_host("8.8.8.8", "192.168.1.2"), "192.168.1.2")
        self.assertEqual(local_host("192.168.1.2", "192.168.1.9"), "192.168.1.2")
        self.assertEqual(local_host("1.1.1.1", "8.8.8.8"), "1.1.1.1")


class LabelMatchEdgeTest(unittest.TestCase):
    def lab(self, new, ts):
        lab = new.drop(columns="community_id").copy()
        lab["ts"] = ts
        lab["label"] = "malicious"
        lab["detailed_label"] = "C&C"
        return lab

    def test_tolerance_boundary(self):
        new = conn_df([row(100.0, "N1", "8.8.8.8", 53, "udp"),
                       row(200.0, "N2", "1.2.3.4", 80)])
        out, _ = match(new, self.lab(new, ["101.0", "201.001"]))
        self.assertEqual(out["label_matched"].tolist(), [True, False])

    def test_different_community_id_never_matches(self):
        new = conn_df([row(100.0, "N1", "1.2.3.4", 80)])
        lab = self.lab(conn_df([row(100.0, "L1", "1.2.3.4", 81)]), ["100.0"])
        out, _ = match(new, lab)
        self.assertFalse(out["label_matched"].iloc[0])

    def test_duplicate_labelled_rows_used_once(self):
        new = conn_df([row(100.0, "N1", "1.2.3.4", 80), row(100.2, "N2", "1.2.3.4", 80),
                       row(100.4, "N3", "1.2.3.4", 80)])
        lab = self.lab(new.iloc[:2], ["100.1", "100.3"])
        out, st = match(new, lab)
        self.assertEqual(st["matched"], 2)


class CausalContextTest(unittest.TestCase):
    def events(self):
        return pd.DataFrame({"ts": [10.0, 50.0, 20.0, 400.0, 30.0, 30.0],
                             "src_ip": ["a", "a", "a", "a", "b", "b"],
                             "dst_ip": "d", "proto": 6.0, "source": "s",
                             "split": "train"})

    def test_counts_only_earlier_events(self):
        c = AV.causal_context(self.events(), 300, by_split=True)
        self.assertEqual(c["n_so_far"].tolist(), [1, 3, 2, 1, 1, 2])
        self.assertEqual(c["span_so_far"].tolist(), [0, 40, 10, 0, 0, 0])

    def test_unchanged_when_later_events_removed(self):
        d = self.events()
        full = AV.causal_context(d, 300, by_split=True)
        early = AV.causal_context(d[d["ts"] <= 20], 300, by_split=True)
        pd.testing.assert_frame_equal(full.loc[early.index], early)

    def test_last_event_equals_completed_context(self):
        d = self.events()
        c = AV.causal_context(d, 300, by_split=True)
        f = AV.full_context(d, 300, by_split=True)
        self.assertEqual(c["n_so_far"].max(), f["n_events"].max())

    def test_no_sport_set(self):
        sets = AV.feature_sets(["sport", "dport", "bytes"])
        self.assertNotIn("sport", sets["event_no_sport"])
        self.assertEqual(sets["event_plus_causal"][-3:], AV.CAUSAL)


class ManifestTest(unittest.TestCase):
    def test_required_fields_and_hashes(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "in.txt"
            p.write_text("x")
            m = write_manifest(Path(t) / "m.json", "r", [p], {"a": 1}, (1, 2), [p])
            self.assertTrue(set(REQUIRED) <= set(m))
            self.assertEqual(m["inputs"]["in.txt"],
                             "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881")
            self.assertEqual(json.loads((Path(t) / "m.json").read_text())["seeds"], [1, 2])


if __name__ == "__main__":
    unittest.main()
