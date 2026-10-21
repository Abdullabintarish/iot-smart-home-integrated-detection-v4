"""Live inference of the saved integrated model vs the saved predictions."""
import time
import unittest

import numpy as np

from _common import ensure_cache, ev


class TestLiveInference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_cache()
        cls.p = ev.load_predictions()
        cls.model = ev.load_model()

    def test_model_matches_feature_file(self):
        self.assertEqual(list(self.model.feature_names_in_), ev.model_feature_order())
        self.assertEqual(ev.model_feature_order(), ev.load_report()["integrated"]["features"])

    def test_live_predict_equals_saved_on_all_test_incidents(self):
        t = time.perf_counter()
        res = ev.verify_live_inference(self.p, self.model)
        print(f"\n    live vs saved: {res['n_agree']:,} / {res['n_test_incidents']:,} agree "
              f"({res['n_mismatch']} mismatches) in {time.perf_counter() - t:.1f} s")
        self.assertEqual(res["n_test_incidents"], ev.load_report()["split"]["n_test_incidents"])
        self.assertEqual(res["n_mismatch"], 0, res["mismatch_examples"])

    def test_proba_argmax_equals_predict(self):
        inc = ev.incidents()
        sample = inc.sample(n=2000, random_state=42)
        proba = ev.live_proba(self.model, sample)
        pred = self.model.predict(ev.incident_feature_matrix(sample)).astype(str)
        self.assertTrue((proba.idxmax(axis=1).to_numpy() == pred).all())
        np.testing.assert_allclose(proba.sum(axis=1).to_numpy(), 1.0, rtol=0, atol=1e-9)

    def test_feature_matrix_is_float32(self):
        X = ev.incident_feature_matrix(ev.incidents().head(5))
        self.assertTrue((X.dtypes == "float32").all())
        self.assertEqual(list(X.columns), ev.model_feature_order())


if __name__ == "__main__":
    unittest.main()
