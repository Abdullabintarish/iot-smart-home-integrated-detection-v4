"""Saved predictions: join, outcome counts, metrics recomputed vs the JSON."""
import unittest

import numpy as np
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from _common import ensure_cache, ev

TOL = 1e-12


class TestPredictions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_cache()
        cls.rep = ev.load_report()
        cls.p = ev.load_predictions()

    def test_cache_fresh_and_join_checks(self):
        self.assertEqual(ev.cache_status(deep=True)["state"], "ok")
        meta = ev.load_meta()
        self.assertTrue(all(meta["join_checks"].values()), meta["join_checks"])
        self.assertEqual(meta["n_predictions"], self.rep["fragmented"]["n_test"])

    def test_join_matches_source_csvs(self):
        # Independent of the cache: event_id/label of both condition files are
        # identical and equal to the cached join.
        opts = pacsv.ConvertOptions(include_columns=["event_id", "label", "pred"])
        f = pacsv.read_csv(ev.path(ev.FRAG_PRED), convert_options=opts)
        i = pacsv.read_csv(ev.path(ev.INTEG_PRED), convert_options=opts)
        self.assertTrue(f["event_id"].equals(i["event_id"]))
        self.assertTrue(f["label"].equals(i["label"]))
        np.testing.assert_array_equal(f["event_id"].to_numpy(), self.p["event_id"].to_numpy())
        self.assertEqual(f["pred"].to_pylist(), self.p["pred_fragmented"].astype(str).tolist())
        self.assertEqual(i["pred"].to_pylist(), self.p["pred_integrated"].astype(str).tolist())
        self.assertEqual(len(self.p), self.rep["integrated"]["n_test"])

    def test_outcome_counts_match_confusion_matrices(self):
        cons = ev.outcome_consistency(self.p, self.rep)
        for c in cons["checks"]:
            self.assertTrue(c["ok"], c)
        oc = cons["counts"]
        # Each condition's wrong count = total minus its CM trace.
        n = self.rep["fragmented"]["n_samples"]
        self.assertEqual(oc["baseline wrong only"] + oc["both wrong"], n - cons["trace_fragmented"])
        self.assertEqual(oc["integrated wrong only"] + oc["both wrong"], n - cons["trace_integrated"])

    def _check_metrics(self, got, want, name):
        for m in ("accuracy", "precision_macro", "recall_macro", "f1_macro", "fpr", "fnr"):
            self.assertTrue(ev.close(got[m], want[m], TOL), f"{name}.{m}: {got[m]} vs {want[m]}")
        self.assertEqual(got["classes"], want["classes"], name)
        self.assertEqual(got["confusion_matrix"], want["confusion_matrix"], name)

    def test_metrics_recomputed_from_predictions(self):
        y = self.p["label"].astype(str).to_numpy()
        for cond, col in (("fragmented", "pred_fragmented"), ("integrated", "pred_integrated")):
            got = ev.metrics_from_predictions(y, self.p[col].astype(str).to_numpy())
            self._check_metrics(got, self.rep[cond], cond)
        dg = self.rep["diagnostics"]
        for key, col in (("pooled_event_model", "pred_pooled"),
                         ("enriched_event_model", "pred_enriched")):
            got = ev.metrics_from_predictions(y, self.p[col].astype(str).to_numpy())
            self._check_metrics(got, dg[key], key)

    def test_metrics_from_confusion_matrix_equal_json(self):
        for cond in ("fragmented", "integrated"):
            r = self.rep[cond]
            calc = ev.metrics_from_cm(r["confusion_matrix"], r["classes"])
            for m in ("accuracy", "precision_macro", "recall_macro", "f1_macro", "fpr", "fnr"):
                self.assertTrue(ev.close(calc[m], r[m], TOL), (cond, m))
            for k, v in r["per_class"].items():
                for q in ("precision", "recall", "f1"):
                    self.assertTrue(ev.close(calc["per_class"][k][q], v[q], TOL), (cond, k, q))
            bc = r["binary_counts"]
            self.assertEqual(calc["fp_binary"], bc["false_positive"])
            self.assertEqual(calc["fn_binary"], bc["false_negative"])

    def test_cm_class_counts_partition(self):
        r = self.rep["integrated"]
        for k in r["classes"]:
            c = ev.cm_class_counts(r["confusion_matrix"], r["classes"], k)
            self.assertEqual(sum(c.values()), r["n_samples"])
            self.assertEqual(c["TP"] + c["FN"], r["per_class"][k]["support"])

    def test_per_source_metrics(self):
        y = self.p["label"].astype(str).to_numpy()
        src = self.p["source"].astype(str).to_numpy()
        for cond, col in (("fragmented", "pred_fragmented"), ("integrated", "pred_integrated")):
            pred = self.p[col].astype(str).to_numpy()
            for s, want in self.rep[cond]["per_source"].items():
                m = src == s
                got = ev.metrics_from_predictions(y[m], pred[m])
                with self.subTest(cond=cond, source=s):
                    self.assertEqual(int(m.sum()), want["n_samples"])
                    for q in ("accuracy", "f1_macro", "fpr", "fnr"):
                        self.assertTrue(ev.close(got[q], want[q], 1e-9), (q, got[q], want[q]))

    def test_split_counts_test_events(self):
        rows = [r for r in self.rep["split"]["events"] if r["split"] == "test"]
        self.assertEqual(sum(r["events"] for r in rows), len(self.p))
        got = self.p.groupby(["source", "label"], observed=True).size()
        for r in rows:
            self.assertEqual(int(got.loc[(r["source"], r["label"])]), r["events"], r)

    def test_cache_parquet_schema(self):
        names = pq.ParquetFile(ev.PRED_CACHE).schema_arrow.names
        self.assertEqual(names, ["event_id", "source", "incident_id", "label", "pred_fragmented",
                                 "pred_integrated", "pred_pooled", "pred_enriched"])


if __name__ == "__main__":
    unittest.main()
