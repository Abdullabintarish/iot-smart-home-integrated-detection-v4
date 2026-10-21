"""Stage 4 tests: metrics, feature whitelists, group split, fair evaluation."""
from __future__ import annotations

import functools
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score

from pipeline import correlate as cr
from pipeline import detect as dt
from pipeline import preprocess as pp
from pipeline.config import BUDGET, N_SPLITS

FEATS = ["f_a", "f_b", "f_c"]
_MEAN = {"benign": 0.0, "dos": 2.5, "recon": -2.5}
_SOURCES = {"capA": ("benign", "dos"), "capB": ("benign", "recon"),
            "capC": ("benign", "dos", "recon")}


def _corpus(seed: int = 0, n_conv: int = 60) -> pd.DataFrame:
    """Stage-2-like events: conversations of 1-5 related events per class."""
    rng = np.random.RandomState(seed)
    rows = []
    for src, classes in _SOURCES.items():
        for c in range(n_conv):
            lab = classes[c % len(classes)]
            t0 = 300.0 * rng.randint(0, 40) + rng.uniform(0, 250)
            for j in range(rng.randint(1, 6)):
                m = _MEAN[lab]
                rows.append({"source": src, "src_ip": f"10.{c % 7}.0.{c}",
                             "dst_ip": f"10.9.{c % 3}.1", "proto": "tcp",
                             "ts": t0 + j, "f_a": m + rng.normal(0, 1),
                             "f_b": m / 2 + rng.normal(0, 1),
                             "f_c": float(rng.randint(0, 3)), "label": lab})
    df = pd.DataFrame(rows)
    df["split"] = pp.assign_split(df, {})
    return df


def _correlated(seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    ev = cr.assign_incidents(_corpus(seed))
    return ev, cr.summarise_incidents(ev)


def _chunks(ev: pd.DataFrame, step: int = 97) -> list[pd.DataFrame]:
    return [ev.iloc[i:i + step].reset_index(drop=True)
            for i in range(0, len(ev), step)]


_small_rf = functools.partial(dt._build, n_estimators=25)


def _fast():
    """Small forests on one core: same code path, test-sized cost."""
    return [mock.patch.object(dt, "_build", _small_rf),
            mock.patch.object(BUDGET, "n_jobs", 1)]


class _Patched(unittest.TestCase):
    def setUp(self) -> None:
        for p in _fast():
            p.start()
            self.addCleanup(p.stop)


# --------------------------------------------------------------------------
class MetricTests(unittest.TestCase):
    T = ["benign", "benign", "benign", "benign", "dos", "dos", "recon"]
    P = ["benign", "dos", "benign", "recon", "dos", "benign", "recon"]

    def test_hand_computed_multiclass(self):
        m = dt.evaluate_split(pd.Series(self.T), pd.Series(self.P))
        # 2 of 4 benign events flagged as attacks; 1 of 3 attacks missed.
        self.assertAlmostEqual(m["fpr"], 2 / 4)
        self.assertAlmostEqual(m["fnr"], 1 / 3)
        self.assertAlmostEqual(m["accuracy"], 4 / 7)
        self.assertEqual(m["classes"], ["benign", "dos", "recon"])
        self.assertEqual(m["confusion_matrix"], [[2, 1, 1], [1, 1, 0], [0, 0, 1]])
        self.assertAlmostEqual(m["precision_macro"], (2 / 3 + 1 / 2 + 1 / 2) / 3)
        self.assertAlmostEqual(m["recall_macro"], (2 / 4 + 1 / 2 + 1) / 3)
        pc = m["per_class"]
        self.assertAlmostEqual(pc["benign"]["precision"], 2 / 3)
        self.assertAlmostEqual(pc["benign"]["recall"], 1 / 2)
        self.assertAlmostEqual(pc["recon"]["f1"], 2 * 0.5 * 1 / 1.5)
        self.assertEqual([pc[c]["support"] for c in m["classes"]], [4, 2, 1])
        self.assertEqual(m["binary_counts"], {"benign": 4, "attack": 3,
                                              "false_positive": 2,
                                              "false_negative": 1})

    def test_macro_matches_sklearn_default_labels(self):
        # A spurious predicted class ("theft") counts, as in sklearn's default.
        t = self.T + ["dos"]
        p = self.P + ["theft"]
        m = dt.evaluate_split(t, p)
        self.assertIn("theft", m["classes"])
        for key, fn in (("precision_macro", precision_score),
                        ("recall_macro", recall_score), ("f1_macro", f1_score)):
            self.assertAlmostEqual(m[key], fn(t, p, average="macro",
                                              zero_division=0), msg=key)

    def test_no_benign_events_gives_nan_fpr(self):
        m = dt.evaluate_split(["dos", "recon", "dos"], ["dos", "benign", "recon"])
        self.assertTrue(math.isnan(m["fpr"]))
        self.assertIn("FPR undefined", m["note"])
        self.assertAlmostEqual(m["fnr"], 1 / 3)

    def test_no_attack_events_gives_nan_fnr(self):
        m = dt.evaluate_split(["benign"] * 4, ["benign", "dos", "benign", "benign"])
        self.assertAlmostEqual(m["fpr"], 1 / 4)
        self.assertTrue(math.isnan(m["fnr"]))

    def test_mixed_dtypes_coerced(self):
        m = dt.evaluate_split(pd.Series(["benign", "dos"], dtype=object),
                              pd.Series(["benign", np.nan], dtype=object))
        self.assertIn("nan", m["classes"])


# --------------------------------------------------------------------------
class FeatureWhitelistTests(unittest.TestCase):
    def test_identifier_columns_rejected(self):
        for col in ("ts", "src_ip", "dst_ip", "source", "incident_id",
                    "corr_rule", "split", "label", "is_attack", "event_id"):
            with self.assertRaises(ValueError, msg=col):
                dt.check_features(["f_a", col])

    def test_feature_matrix_selects_exactly_the_whitelist(self):
        ev, _ = _correlated()
        ev = ev.assign(stray=1.0)              # unlisted numeric column
        X, y = dt.feature_matrix(ev, FEATS)
        self.assertEqual(list(X.columns), FEATS)
        self.assertEqual(str(X.dtypes.iloc[0]), "float32")
        self.assertEqual(len(y), len(ev))

    def test_missing_feature_raises(self):
        ev, _ = _correlated()
        with self.assertRaises(KeyError):
            dt.feature_matrix(ev.drop(columns="f_b"), FEATS)

    def test_event_features_read_from_plan(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "plan.csv"
            pd.DataFrame({"feature": ["sport", "proto", "bwd_bytes", "seq"],
                          "decision": ["kept", "kept", "dropped", "excluded"]}
                         ).to_csv(p, index=False)
            self.assertEqual(dt.event_features(p), ["sport", "proto"])
            pd.DataFrame({"feature": ["sport", "ts"], "decision": ["kept", "kept"]}
                         ).to_csv(p, index=False)
            with self.assertRaises(ValueError):
                dt.event_features(p)

    def test_incident_features_are_the_seven_stage3_features(self):
        self.assertEqual(len(dt.INCIDENT_FEATURES), 7)
        dt.check_features(dt.INCIDENT_FEATURES)


# --------------------------------------------------------------------------
class GroupSplitTests(unittest.TestCase):
    def test_no_incident_spans_both_splits(self):
        ev, _ = _correlated()
        self.assertEqual(set(ev["split"]), {"train", "test"})
        per_inc = ev.groupby("incident_id")["split"].nunique()
        self.assertTrue((per_inc == 1).all())
        self.assertGreater((ev.groupby("incident_id").size() > 1).sum(), 50)

    def test_split_is_stable(self):
        a, b = _corpus(), _corpus()
        self.assertTrue(a["split"].equals(b["split"]))


# --------------------------------------------------------------------------
class ConditionTests(_Patched):
    @classmethod
    def setUpClass(cls):
        cls.ev, cls.inc = _correlated()
        with mock.patch.object(dt, "_build", _small_rf), \
                mock.patch.object(BUDGET, "n_jobs", 1):
            cls.res, cls.preds = dt.run_stage4(_chunks(cls.ev), cls.inc, FEATS,
                                               do_cv=True, save_model=False)

    def test_both_conditions_scored_on_identical_test_events(self):
        test_ids = np.flatnonzero(self.ev["split"].to_numpy() == "test")
        self.assertEqual(self.preds["event_id"].tolist(), test_ids.tolist())
        self.assertTrue((self.preds["split"] == "test").all())
        f, i = self.res["fragmented"], self.res["integrated"]
        self.assertEqual(f["n_test"], i["n_test"])
        self.assertEqual(f["n_samples"], len(test_ids))
        self.assertEqual(i["n_samples"], len(test_ids))
        self.assertEqual(self.res["split"]["n_mixed_incidents"], 0)

    def test_reported_metrics_match_saved_predictions(self):
        for cond in ("fragmented", "integrated"):
            m = dt.evaluate_split(self.preds["label"], self.preds[f"pred_{cond}"])
            self.assertAlmostEqual(m["f1_macro"], self.res[cond]["f1_macro"])
            self.assertAlmostEqual(m["accuracy"], self.res[cond]["accuracy"])

    def test_integrated_predictions_are_model_predictions(self):
        # Shuffle the TRUE labels of test incidents after the fact: a model's
        # predictions cannot change, a propagation of ground truth would.
        inc = self.inc.copy()
        test_ids = set(self.ev.loc[self.ev["split"] == "test", "incident_id"])
        is_test = inc["incident_id"].isin(test_ids)
        rng = np.random.RandomState(1)
        inc.loc[is_test, "label"] = rng.permutation(
            inc.loc[is_test, "label"].map(
                {"benign": "dos", "dos": "recon", "recon": "benign"}).to_numpy())
        train_ids = np.array(sorted(set(self.ev["incident_id"]) - test_ids))
        test = self.ev[self.ev["split"] == "test"].reset_index(drop=True)
        _, pred, _ = dt.train_integrated(inc, train_ids, test, do_cv=False,
                                         save_model=False)
        self.assertEqual(pred.astype(str).tolist(),
                         self.preds["pred_integrated"].tolist())
        truth_old = test["incident_id"].map(self.inc.set_index("incident_id")["label"])
        truth_new = test["incident_id"].map(inc.set_index("incident_id")["label"])
        self.assertFalse(truth_old.equals(truth_new))   # the shuffle bit

    def test_feature_sets_per_condition(self):
        f, i = self.res["fragmented"], self.res["integrated"]
        self.assertEqual(f["features"], FEATS)
        self.assertFalse(set(f["features"]) & set(dt.INCIDENT_FEATURES))
        self.assertEqual(i["features"], list(dt.INCIDENT_FEATURES))
        d = self.res["diagnostics"]
        self.assertEqual(d["pooled_event_model"]["features"], FEATS)
        self.assertEqual(d["enriched_event_model"]["features"],
                         FEATS + list(dt.ENRICH_FEATURES))

    def test_baseline_ignores_incident_features(self):
        inc = self.inc.copy()
        for c in dt.INCIDENT_FEATURES:
            inc[c] = np.random.RandomState(2).permutation(inc[c].to_numpy())
        _, preds = dt.run_stage4(_chunks(self.ev), inc, FEATS, do_cv=False,
                                 diagnostics=False, save_model=False)
        self.assertEqual(preds["pred_fragmented"].tolist(),
                         self.preds["pred_fragmented"].tolist())

    def test_cv_uses_train_split_only_and_groups(self):
        calls = []
        real = dt.grouped_cv

        def spy(X, y, groups=None):
            calls.append((len(y), None if groups is None else set(map(str, groups))))
            return real(X, y, groups)

        with mock.patch.object(dt, "grouped_cv", spy):
            res, _ = dt.run_stage4(_chunks(self.ev), self.inc, FEATS,
                                   do_cv=True, diagnostics=False,
                                   save_model=False)
        test_inc = set(self.ev.loc[self.ev["split"] == "test", "incident_id"])
        train_inc = set(self.ev.loc[self.ev["split"] == "train", "incident_id"])
        grouped = [g for _, g in calls if g is not None]
        self.assertEqual(len(grouped), 3)                   # one per source
        for g in grouped:
            self.assertTrue(g <= train_inc)
            self.assertFalse(g & test_inc)
        n_inc = [n for n, g in calls if g is None]
        self.assertEqual(n_inc, [res["integrated"]["n_train"]])
        self.assertIn("cv_f1_mean", res["fragmented"])
        self.assertIn("cv_f1_mean", res["integrated"])

    def test_deterministic(self):
        res, preds = dt.run_stage4(_chunks(self.ev, step=55), self.inc, FEATS,
                                   do_cv=True, save_model=False)
        pd.testing.assert_frame_equal(preds, self.preds)
        for cond in ("fragmented", "integrated"):
            self.assertEqual(res[cond]["cv_folds"], self.res[cond]["cv_folds"])

    def test_report_sections_present(self):
        lvl = self.res["integrated_incident_level"]
        n_test_inc = self.ev.loc[self.ev["split"] == "test", "incident_id"].nunique()
        self.assertEqual(lvl["n_samples"], n_test_inc)
        dup = self.res["diagnostics"]["duplicates"]
        self.assertEqual(set(dup["novel_only_metrics"]),
                         {"fragmented", "integrated", "pooled", "enriched"})
        self.assertEqual(set(self.res["fragmented"]["per_source"]), set(_SOURCES))


# --------------------------------------------------------------------------
class GroupedCVTests(_Patched):
    def test_folds_never_share_a_group(self):
        rng = np.random.RandomState(4)
        n = 300
        groups = pd.Series([f"g{i // 3}" for i in range(n)])
        y = pd.Series(np.where(np.arange(n) // 3 % 2, "dos", "benign"))
        y.iloc[:2] = "c2"                   # one group of "c2": < N_SPLITS
        X = pd.DataFrame({"a": rng.normal(size=n)}, index=y.index)
        seen = []

        class Rec:
            def __init__(self):
                self.m = _small_rf()

            def fit(self, X, y):
                seen.append(("fit", set(X.index)))
                self.m.fit(X, y)
                return self

            def predict(self, X):
                seen.append(("predict", set(X.index)))
                return self.m.predict(X)

        with mock.patch.object(dt, "_build", Rec):
            res, oof = dt.grouped_cv(X, y, groups)
        self.assertEqual(res["cv_excluded_classes"], ["c2"])
        self.assertEqual(len(res["cv_folds"]), N_SPLITS)
        self.assertNotIn("c2", set(oof["y"]))
        for k in range(0, len(seen), 2):
            fit_g = set(groups[list(seen[k][1])])
            val_g = set(groups[list(seen[k + 1][1])])
            self.assertFalse(fit_g & val_g)


class BaselineTests(_Patched):
    def _frames(self):
        rng = np.random.RandomState(5)

        def ev(src, labels, split):
            return pd.DataFrame({
                "event_id": 0, "source": src, "split": split,
                "incident_id": [f"{src}-{split}-{i}" for i in range(len(labels))],
                "label": labels, "f_a": rng.normal(size=len(labels)),
                "f_b": rng.normal(size=len(labels)), "f_c": 0.0})

        train = {"multi": ev("multi", ["benign", "dos"] * 20, "train"),
                 "single": ev("single", ["benign"] * 10, "train")}
        test = pd.concat([ev("multi", ["benign", "dos"] * 5, "test"),
                          ev("single", ["benign"] * 6 + ["recon"] * 2, "test"),
                          ev("unseen", ["dos"] * 3, "test")], ignore_index=True)
        test["event_id"] = np.arange(len(test))
        return train, test

    def test_single_class_and_untrained_sources_get_real_metrics(self):
        train, test = self._frames()
        res, pred = dt.train_fragmented_baseline(train, test, FEATS, do_cv=False)
        single = res["per_source"]["single"]
        self.assertEqual(single["n_test"], 8)               # held-out only
        self.assertAlmostEqual(single["accuracy"], 6 / 8)
        self.assertAlmostEqual(single["fnr"], 1.0)
        self.assertAlmostEqual(single["fpr"], 0.0)
        self.assertIn("single-class", single["note"])
        self.assertTrue((pred[test["source"] == "single"] == "benign").all())
        unseen = res["per_source"]["unseen"]
        self.assertAlmostEqual(unseen["fnr"], 1.0)
        self.assertIn("no train events", unseen["note"])
        self.assertEqual(res["n_samples"], len(test))

    def test_each_source_model_trained_once(self):
        train, test = self._frames()
        fits = []
        real = dt._build

        def counting(*a, **k):
            m = real(*a, **k)
            orig = m.fit
            m.fit = lambda X, y: (fits.append(len(y)), orig(X, y))[1]
            return m

        with mock.patch.object(dt, "_build", counting):
            dt.train_fragmented_baseline(train, test, FEATS, do_cv=False)
        self.assertEqual(fits, [40])                 # "multi" only, once


class ModelConfigTests(unittest.TestCase):
    def test_hyperparameters_fixed(self):
        rf = dt._build()
        self.assertEqual((rf.n_estimators, rf.max_depth, rf.min_samples_leaf,
                          rf.class_weight, rf.random_state),
                         (300, 24, 2, "balanced_subsample", 42))


if __name__ == "__main__":
    unittest.main()
