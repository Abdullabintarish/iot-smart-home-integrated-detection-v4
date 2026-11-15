"""Tests for v3 (synthetic data only).

    code/.venv/Scripts/python.exe -B -m unittest discover -s experiments/v3/tests
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
V3 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V3))
import stats_v3 as S  # noqa: E402
import transfer_v3 as T  # noqa: E402
import verify_v3 as V  # noqa: E402

FEATS = ["sport", "dport", "proto", "history", "bytes"]


def make(n=3000, seed=0):
    r = np.random.default_rng(seed)
    srcs = ["CTU-a", "CTU-b", "CTU-c", "data_1"]
    src = r.choice(srcs, n)
    lab = np.where(r.random(n) < 0.5, "benign",
                   np.where(src == "data_1", "dos", r.choice(["c2", "recon"], n)))
    lab[src == "CTU-c"] = "benign"                    # single-class source -> constant model
    d = pd.DataFrame({"event_id": np.arange(n), "ts": 1000 + r.uniform(0, 2000, n),
                      "source": src, "label": lab,
                      "src_ip": ["10.0.0.%d" % h for h in r.integers(0, 30, n)],
                      "dst_ip": "10.0.1.1",
                      "sport": r.random(n).astype("float32"),
                      "dport": (pd.Categorical(lab).codes / 5 + r.normal(0, .05, n)).astype("float32"),
                      "proto": r.integers(2, 5, n).astype("float32"),
                      "history": r.integers(-1, 8, n).astype("float32"),
                      "bytes": r.random(n).astype("float32")})
    d["split"] = np.where(r.random(n) < 0.25, "test", "train")
    d["incident_id"] = np.arange(n).astype(str)
    return d


class TransferRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        T.OUT = Path(cls.tmp.name)
        T.SEEDS = (42, 1)
        cls.df = make()
        for d in ("runB", "loso"):
            T.run_design(d, cls.df, FEATS)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def metrics(self, d):
        return json.loads((T.OUT / d / "metrics.json").read_text())

    def test_all_runs_saved(self):
        for d in ("runB", "loso"):
            names = {k.split("|")[0] for k in self.metrics(d)["runs"]}
            expect = {f"{m}_{s}" for m in T.MODELS for s in T.SET_NAMES}
            expect |= {"frag"} if d == "runB" else {"frag_soft", "frag_union"}
            self.assertEqual(names, expect)

    def test_rows_cover_test_partition_once(self):
        r = pd.read_parquet(T.OUT / "loso" / "rows.parquet")
        self.assertEqual(sorted(r["event_id"]), list(range(len(self.df))))
        r = pd.read_parquet(T.OUT / "runB" / "rows.parquet")
        self.assertEqual(len(r), (self.df["split"] == "test").sum())

    def test_loso_baseline_never_uses_held_out_source_model(self):
        """The fold of source s is predicted by the other sources' models only."""
        r = pd.read_parquet(T.OUT / "loso" / "rows.parquet")
        p = pd.read_parquet(T.OUT / "loso" / "run_frag_soft_s42.parquet")
        m = (r["fold"] == "data_1").to_numpy()
        # only data_1 has dos: no other source's model can predict it there
        self.assertEqual(float(p.loc[m, "p_dos"].astype(float).max()), 0.0)

    def test_union_alerts_superset_of_soft(self):
        soft = pd.read_parquet(T.OUT / "loso" / "run_frag_soft_s42.parquet")["pred"].astype(str)
        uni = pd.read_parquet(T.OUT / "loso" / "run_frag_union_s42.parquet")["pred"].astype(str)
        self.assertTrue(((soft != "benign") <= (uni != "benign")).all())

    def test_probabilities_sum_to_one(self):
        p = pd.read_parquet(T.OUT / "runB" / "run_lr_event_only_s1.parquet")
        s = p.filter(like="p_").astype(float).sum(axis=1)
        self.assertTrue(np.allclose(s, 1.0, atol=5e-3))

    def test_verifier_and_stats_agree(self):
        res = V.verify_design(T.OUT / "loso")
        self.assertFalse(res["mismatches"], res["mismatches"][:5])
        st = S.loso_tests(self.metrics("loso"))
        self.assertIn("comparisons", st)
        self.assertEqual(V.recheck_stats(st, self.metrics("loso")), [])


class MetricTest(unittest.TestCase):
    def test_present_class_f1_ignores_absent_predicted_class(self):
        classes = ["benign", "c2", "dos"]
        y = np.array(["benign"] * 4 + ["c2"] * 4)
        pred = np.array(["benign"] * 3 + ["dos"] + ["c2"] * 4)
        pr = np.eye(3)[[classes.index(v) for v in pred]].astype("float16")
        m = T.score(y, pred, pr, classes)
        self.assertLess(m["f1_macro"], m["f1_macro_present"])
        self.assertIsNotNone(m["pr_auc_binary"])

    def test_undefined_metrics_are_null(self):
        classes = ["benign", "c2"]
        y = np.array(["benign"] * 5)
        m = T.score(y, y.copy(), np.tile([1, 0], (5, 1)).astype("float16"), classes)
        self.assertIsNone(m["fnr"])
        self.assertIsNone(m["pr_auc_binary"])
        self.assertIsNone(m["pr_auc_macro_present"])


class LeanReaderTest(unittest.TestCase):
    HEAD = ("#separator \\x09\n#set_separator\t,\n#empty_field\t(empty)\n#unset_field\t-\n"
            "#path\tconn\n#open\t2019-01-04-05-23-25\n")

    def check(self, text):
        import lean_io
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "conn.log"
            p.write_text(text, encoding="utf-8")
            a, b = lean_io.zeek_io.read_zeek_tsv(p), lean_io.read_zeek_tsv(p)
            self.assertTrue(lean_io.same_frame(a, b), (a, b))
            return b

    def test_iot23_tail(self):
        b = self.check(self.HEAD + "#fields\tts\tuid\ttunnel_parents   label   detailed-label\n"
                       "#types\ttime\tstring\tset[string]   string   string\n"
                       "1.5\tCa\t-   Malicious   C&C-HeartBeat\n2.5\tCb\t-   Benign   -\n"
                       "3.5\tCc\t-\n#close\t2019-01-04-06-01-47\n")
        self.assertEqual(b["label"].tolist(), ["malicious", "benign", "-"])
        self.assertEqual(b["detailed_label"].tolist(), ["C&C-HeartBeat", "-", "-"])

    def test_tab_label_columns_and_unset(self):
        b = self.check(self.HEAD + "#fields\tts\tuid\tlabel\tdetailed-label\n#types\ttime\tstring\tstring\tstring\n"
                       "1.5\t-\tMalicious \tOkiru\n2.5\t(empty)\tBenign\t-\n#close\tx\n")
        self.assertEqual(b["uid"].tolist(), ["-", "(empty)"])
        self.assertEqual(b["label"].tolist(), ["malicious", "benign"])


class StatsTest(unittest.TestCase):
    def test_exact_sign_flip(self):
        self.assertAlmostEqual(S.sign_flip_p(np.array([1.0, 2.0, 3.0, 4.0, 5.0])), 2 / 32)
        self.assertEqual(S.sign_flip_p(np.zeros(4)), 1.0)

    def test_holm(self):
        adj = S.holm([0.01, 0.04, 0.03])
        self.assertEqual([round(a, 4) for a in adj], [0.03, 0.06, 0.06])


if __name__ == "__main__":
    unittest.main()
