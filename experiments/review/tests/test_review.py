"""Synthetic tests for the reviewer analyses (no real data)."""
import sys, tempfile, unittest
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import permuted_context as P
import boundary_sensitivity as B
R = P.R

def make(n=6000, seed=0):
    r = np.random.default_rng(seed)
    lab = r.choice(["benign", "c2", "dos", "malware", "recon"], n, p=[.4, .1, .2, .1, .2])
    src = np.where(lab == "dos", "data_10", "CTU-IoT-Malware-Capture-1-1")
    host = r.integers(0, 40, n)
    d = pd.DataFrame({"event_id": np.arange(n), "ts": 1000 + r.uniform(0, 3000, n), "source": src,
        "label": lab, "src_ip": ["10.0.0.%d" % h for h in host], "dst_ip": "10.0.1.1", "proto": 6.0,
        "signal": pd.Categorical(lab).codes + r.normal(0, .1, n)})
    key, _, _ = R.correlation_key(d, window_s=300)
    h = pd.util.hash_pandas_object(key.astype(str), index=False).to_numpy()
    d["split"] = np.where(h % 4 == 0, "test", "train")
    d["incident_id"] = pd.factorize(key)[0].astype(str)
    return d

class Shuffle(unittest.TestCase):
    def setUp(self):
        self.d = make(); self.ctx = R.incident_context(self.d, 300)
        self.sp, self.src = self.d["split"].to_numpy(), self.d["source"].to_numpy()
        self.p = P.permute_context(self.ctx, self.sp, self.src, 42)
    def test_distribution_kept_per_stratum(self):
        for s in ("train", "test"):
            for src in set(self.src):
                m = (self.sp == s) & (self.src == src)
                a = self.ctx[m].sort_values(R.INCIDENT).to_numpy()
                b = self.p[m].sort_values(R.INCIDENT).to_numpy()
                self.assertTrue(np.array_equal(a, b))     # same multiset of whole rows
    def test_rows_move_whole(self):
        orig = set(map(tuple, self.ctx.to_numpy())); new = set(map(tuple, self.p.to_numpy()))
        self.assertEqual(orig, new)
        self.assertEqual(list(self.p.dtypes), list(self.ctx.dtypes))
    def test_link_broken(self):
        # Within a true incident the context is constant; after shuffling it no longer is.
        same = (self.p.to_numpy() == self.ctx.to_numpy()).all(axis=1)
        self.assertLess(same.mean(), 0.2)
        multi = self.d.groupby("incident_id")["event_id"].transform("size") > 3
        varies = self.p[multi.to_numpy()].groupby(self.d.loc[multi, "incident_id"])["n_events"].nunique()
        self.assertGreater((varies > 1).mean(), 0.9)
    def test_train_and_test_shuffled_separately(self):
        # No test event receives a row from a training event, and vice versa.
        for s in ("train", "test"):
            m = self.sp == s
            pool = set(map(tuple, self.ctx[m].to_numpy()))
            self.assertTrue(set(map(tuple, self.p[m].to_numpy())) <= pool)
        # Changing only the training rows leaves the shuffled test rows unchanged.
        ctx2 = self.ctx.copy(); ctx2.loc[self.sp == "train", "n_events"] += 1000
        p2 = P.permute_context(ctx2, self.sp, self.src, 42)
        self.assertTrue(np.array_equal(p2[self.sp == "test"].to_numpy(), self.p[self.sp == "test"].to_numpy()))
    def test_class_blind_and_seeded(self):
        d2 = self.d.assign(label="benign")              # labels are not an input at all
        self.assertTrue(np.array_equal(P.permute_context(self.ctx, d2["split"].to_numpy(), self.src, 42).to_numpy(), self.p.to_numpy()))
        self.assertTrue(np.array_equal(P.permute_context(self.ctx, self.sp, self.src, 42).to_numpy(), self.p.to_numpy()))
        self.assertFalse(np.array_equal(P.permute_context(self.ctx, self.sp, self.src, 1).to_numpy(), self.p.to_numpy()))
    def test_permuted_is_not_better_than_true_context(self):
        # Planted signal in the incident features: shuffling must remove it.
        d = self.d.copy(); d["signal"] = 0.0
        tr, te = np.flatnonzero(self.sp == "train"), np.flatnonzero(self.sp == "test")
        y = d["label"].to_numpy(); ctx = self.ctx.copy()
        ctx["n_events"] = pd.Categorical(y).codes.astype("float32")   # label leaks via context
        s = R.sample_train(tr, y, 300, 1)
        X = pd.concat([d[["signal"]], ctx], axis=1)
        Xp = pd.concat([d[["signal"]], P.permute_context(ctx, self.sp, self.src, 1)], axis=1)
        f = lambda X: R.evaluate_split(pd.Series(y[te]), pd.Series(R.fit_predict(X, y, s, te, 1, 20, 1)[0]))["f1_macro"]
        self.assertGreater(f(X), f(Xp) + 0.3)

    def test_end_to_end_and_reproduction_gate(self):
        import json
        with tempfile.TemporaryDirectory() as t:
            p = Path(t); (p / "ev").mkdir(); self.d.to_parquet(p / "ev" / "a.parquet")
            pd.DataFrame({"feature": ["signal"], "decision": "kept"}).to_csv(p / "plan.csv", index=False)
            base = ["--events", str(p / "ev"), "--plan", str(p / "plan.csv"), "--windows", "60", "300",
                    "--seeds", "42", "1", "--trees", "10", "--per-class", "200", "--n-jobs", "1", "--bootstrap", "10"]
            R.main(base[:4] + ["--out", str(p / "orig"), "--windows", "300", "--seeds", "42", "--trees", "10",
                               "--per-class", "200", "--n-jobs", "1", "--bootstrap", "0"])
            self.assertEqual(P.main(base + ["--out", str(p / "a"), "--original", str(p / "orig" / "ablation_results.csv")]), 0)
            k = json.loads((p / "a" / "checks.json").read_text()); self.assertTrue(k["reproduction"]["all_match"])
            r = pd.read_csv(p / "a" / "review_results.csv"); a = r[r.subset == "all"]
            self.assertEqual(len(a), 2 + 2 * 2 * 2)                       # event_only x2, two sets x 2 windows x 2 seeds
            self.assertEqual(a.n.nunique(), 1)
            self.assertEqual(len(json.loads((p / "a" / "bootstrap.json").read_text())), 4)
            bad = pd.read_csv(p / "orig" / "ablation_results.csv"); bad["f1_macro"] += 0.01
            bad.to_csv(p / "bad.csv", index=False)                        # gate must stop on a mismatch
            self.assertEqual(P.main(base + ["--out", str(p / "b"), "--original", str(p / "bad.csv")]), 2)
            self.assertFalse((p / "b" / "bootstrap.json").exists())

class Boundary(unittest.TestCase):
    def events(self):
        # Source A: cut at ts 250. Group g1 (bucket 0, 10.0.0.1) spans it; g2 is train-only; g3 test-only.
        rows = [(100, "10.0.0.1", "train"), (200, "10.0.0.1", "train"), (260, "10.0.0.1", "test"),
                (290, "10.0.0.1", "test"), (120, "10.0.0.2", "train"), (310, "10.0.0.3", "test"),
                (320, "10.0.0.3", "test"), (330, "10.0.0.1", "test")]   # last: next bucket of g1's flow
        d = pd.DataFrame(rows, columns=["ts", "src_ip", "split"])
        d["dst_ip"] = "10.0.1.1"; d["proto"] = 6.0; d["source"] = "A"
        return d
    def test_detects_group_spanning_cut(self):
        m = B.boundary_mask(self.events(), 300)
        self.assertEqual(m.tolist(), [True, True, True, True, False, False, False, False])
    def test_other_source_and_singletons_not_boundary(self):
        d = self.events(); e = d.copy(); e["source"] = "B"; e["split"] = "test"
        both = pd.concat([d, e], ignore_index=True)
        m = B.boundary_mask(both, 300)
        self.assertFalse(m[len(d):].any())               # same IPs in another source: separate key
        s = d.copy(); s["src_ip"] = None; s["dst_ip"] = None   # uncorrelatable rows
        self.assertFalse(B.boundary_mask(s, 300).any())
    def test_flow_definition_ignores_bucket(self):
        m = B.boundary_mask(self.events(), B.NO_BUCKET)
        self.assertEqual(m.tolist(), [True, True, True, True, False, False, False, True])
    def test_end_to_end_on_fake_run_t(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); ev = root / "data" / "processed" / "stage3_events"; res = root / "results"
            ev.mkdir(parents=True); res.mkdir()
            d = self.events(); d["label"] = ["dos"] * 4 + ["benign"] * 4
            d["incident_id"] = (d["src_ip"] + d["split"] + (d["ts"] // 300).astype(int).astype(str))
            d.to_parquet(ev / "events_0000.parquet")
            te = d[d.split == "test"].assign(event_id=lambda x: x.index)
            pred = np.where(te.ts < 300, "recon", te.label)       # errors only on boundary events
            for name in ("fragmented", "integrated"):
                te.assign(pred=pred)[["event_id", "source", "incident_id", "split", "label", "pred"]].to_csv(
                    res / f"{name}_event_predictions.csv", index=False)
            r = R.evaluate_split(te.label, pd.Series(pred))
            import json
            (res / "stage5_report.json").write_text(json.dumps({n: {k: r[k] for k in B.METRICS} for n in ("fragmented", "integrated")}))
            self.assertEqual(B.main(["--run-t", str(root), "--out", str(root / "out")]), 0)
            m = pd.read_csv(root / "out" / "boundary_metrics.csv").set_index(["condition", "subset"])
            self.assertEqual(m.loc[("integrated", "all"), "n"], 5)
            self.assertEqual(m.loc[("integrated", "excluding_boundary_groups"), "n"], 3)
            self.assertEqual(m.loc[("integrated", "excluding_boundary_groups"), "accuracy"], 1.0)
            c = json.loads((root / "out" / "checks.json").read_text())
            self.assertTrue(c["integrated_all_matches_stage5_report"])
            self.assertEqual(json.loads((root / "out" / "boundary_counts.json").read_text())["boundary_test_incidents"], 1)

if __name__ == "__main__": unittest.main()
