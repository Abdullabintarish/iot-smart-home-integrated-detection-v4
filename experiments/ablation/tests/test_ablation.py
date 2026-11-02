"""Synthetic tests for run_ablation.py (no real data)."""
import json, sys, tempfile, unittest
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run_ablation as R

def make(n=6000, seed=0):
    r = np.random.default_rng(seed)
    lab = r.choice(["benign", "c2", "dos", "malware", "recon"], n, p=[.4, .1, .2, .1, .2])
    src = np.where(lab == "dos", "data_10", "CTU-IoT-Malware-Capture-1-1")
    host = r.integers(0, 40, n)
    ts = 1000 + r.uniform(0, 3000, n)
    d = pd.DataFrame({"event_id": np.arange(n), "ts": ts, "source": src, "label": lab,
        "src_ip": ["10.0.0.%d" % h for h in host], "dst_ip": "10.0.1.1", "proto": 6.0,
        "signal": pd.Categorical(lab).codes + r.normal(0, .1, n),
        "zeek_only": np.where(src == "data_10", -1.0, r.normal(size=n)),
        "argus_only": np.where(src == "data_10", r.normal(size=n), -1.0)})
    key, _, _ = R.correlation_key(d, window_s=300)
    h = pd.util.hash_pandas_object(key.astype(str), index=False).to_numpy()
    d["split"] = np.where(h % 4 == 0, "test", "train")
    d["incident_id"] = pd.factorize(key)[0].astype(str)
    return d

class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); p = Path(self.tmp.name)
        self.d = make(); (p / "ev").mkdir()
        self.d.to_parquet(p / "ev" / "a.parquet")
        pd.DataFrame({"feature": ["signal", "zeek_only", "argus_only"], "decision": "kept"}).to_csv(p / "plan.csv", index=False)
        self.p = p
    def tearDown(self): self.tmp.cleanup()
    def test_context_matches_manual(self):
        c = R.incident_context(self.d, 300)
        self.assertEqual(c.attrs["n_groups"], self.d["incident_id"].nunique())
        g = self.d.groupby("incident_id")["ts"]
        self.assertTrue(np.allclose(c["n_events"], g.transform("size")))
        self.assertTrue(np.allclose(c["span_s"], g.transform("max") - g.transform("min"), atol=1e-2))
    def test_no_group_crosses_split(self):
        c = R.incident_context(self.d, 900)
        k, _, _ = R.correlation_key(self.d, window_s=900)
        k2 = k.astype(str) + self.d["split"]
        self.assertTrue(np.allclose(c["n_events"], k2.map(k2.value_counts()).to_numpy()))
    def test_shared_drops_dataset_only(self):
        self.assertEqual(R.shared_features(self.d, ["signal", "zeek_only", "argus_only"]), ["signal"])
    def test_sample_same_for_all_sets_and_capped(self):
        y = self.d["label"].to_numpy(); tr = np.flatnonzero(self.d["split"] == "train")
        a = R.sample_train(tr, y, 100, 1); b = R.sample_train(tr, y, 100, 1)
        self.assertTrue((a == b).all()); self.assertTrue(pd.Series(y[a]).value_counts().max() <= 100)
        self.assertFalse(set(a) & set(np.flatnonzero(self.d["split"] == "test")))
    def test_bootstrap_identical_predictions_give_zero(self):
        y = self.d["label"].to_numpy()
        o = R.paired_bootstrap(y, y, y, self.d["incident_id"].to_numpy(), sorted(set(y)), 20, 1)
        self.assertEqual(o["f1_macro_diff"], [0.0, 0.0])
    def test_end_to_end(self):
        out = self.p / "out"
        rc = R.main(["--events", str(self.p / "ev"), "--plan", str(self.p / "plan.csv"), "--out", str(out),
                     "--windows", "60", "120", "300", "900", "--seeds", "42", "1", "--trees", "20", "--per-class", "300",
                     "--n-jobs", "2", "--bootstrap", "20"])
        self.assertEqual(rc, 0)
        r = pd.read_csv(out / "ablation_results.csv"); a = r[r.subset == "all"]
        self.assertEqual(set(a.feature_set), {"event_only", "shared_event", "incident_only", "event_plus_incident", "shared_plus_incident"})
        self.assertEqual(a.n.nunique(), 1)                          # same test events
        self.assertEqual(a[a.seed == 42].n_train.nunique(), 1)      # same sample per seed
        self.assertTrue(a[a.window_s.isin([120, 900])].window_cut.all()); self.assertFalse(a[a.window_s.isin([60, 300])].window_cut.any())
        e = a[a.feature_set == "event_only"].f1_macro.mean(); i = a[a.feature_set == "incident_only"].f1_macro.mean()
        self.assertGreater(e, i)                                    # planted signal is an event feature
        k = json.load(open(out / "checks.json")); self.assertEqual(k["groups_at_300s"], k["run_b_incidents"])
        self.assertTrue((out / "thesis_table.md").exists())
if __name__ == "__main__": unittest.main()
