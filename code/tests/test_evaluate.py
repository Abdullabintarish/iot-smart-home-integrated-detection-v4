"""Stage 5 tests: comparison table, alert reduction by dataset, robustness
re-scoring (incl. majority-vote tie-break) and the clustered bootstrap."""
from __future__ import annotations

import math
import unittest

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

from pipeline import evaluate as ev
from pipeline.detect import evaluate_split


def _preds(rows: list[tuple[str, str, str, str]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(incident_id, label, pred_fragmented, pred_integrated) rows -> the two
    per-condition frames run_pipeline writes (event_id, ..., label, pred)."""
    df = pd.DataFrame(rows, columns=["incident_id", "label", "pf", "pi"])
    df.insert(0, "event_id", np.arange(len(df)) * 3 + 1)
    df["source"], df["split"] = "CTU-x", "test"
    base = ["event_id", "source", "incident_id", "split", "label"]
    return (df[base + ["pf"]].rename(columns={"pf": "pred"}),
            df[base + ["pi"]].rename(columns={"pi": "pred"}))


class ComparisonTableTests(unittest.TestCase):
    def test_difference_is_integrated_minus_fragmented(self):
        f = {"accuracy": 0.9, "precision_macro": 0.5, "recall_macro": 0.5,
             "f1_macro": 0.8, "fpr": 0.10, "fnr": 0.02}
        i = {"accuracy": 0.8, "precision_macro": 0.5, "recall_macro": 0.6,
             "f1_macro": 0.7, "fpr": 0.05, "fnr": 0.04}
        t = ev.comparison_table(f, i).set_index("metric")
        self.assertNotIn("improvement", t.columns)
        for k in f:
            self.assertAlmostEqual(t.loc[k, "difference"], i[k] - f[k])
        self.assertEqual(t.loc["accuracy", "better"], "fragmented")
        self.assertEqual(t.loc["recall_macro", "better"], "integrated")
        self.assertEqual(t.loc["precision_macro", "better"], "tie")
        # Lower is better for the error rates.
        self.assertEqual(t.loc["fpr", "better"], "integrated")
        self.assertEqual(t.loc["fnr", "better"], "fragmented")
        self.assertEqual(t.loc["fpr", "direction"], "lower_is_better")

    def test_missing_or_nan_has_no_difference(self):
        t = ev.comparison_table({"accuracy": 0.9, "fnr": float("nan")},
                                {"accuracy": 0.9, "fnr": 0.1}).set_index("metric")
        self.assertTrue(pd.isna(t.loc["fnr", "difference"]))
        self.assertTrue(pd.isna(t.loc["fnr", "better"]))
        self.assertTrue(pd.isna(t.loc["f1_macro", "difference"]))
        self.assertEqual(t.loc["accuracy", "better"], "tie")


class AlertReductionByDatasetTests(unittest.TestCase):
    def test_per_source_family_and_overall(self):
        inc = pd.DataFrame({
            "incident_id": list("abcdefg"),
            "source": ["CTU-1", "CTU-1", "CTU-2", "data_1", "data_1", "data_10", "zz"],
            "n_events": [3, 1, 2, 60, 40, 10, 4],
            "cross_source": [1] * 7})
        r = ev.alert_reduction_by_dataset(inc)
        self.assertEqual(r["per_source"]["CTU-1"]["events"], 4)
        self.assertEqual(r["per_source"]["CTU-1"]["incidents"], 2)
        self.assertAlmostEqual(r["per_source"]["CTU-1"]["alert_reduction"], 0.5)
        self.assertEqual(r["per_source"]["data_10"]["dataset"], "Bot-IoT")
        iot = r["per_dataset"]["IoT-23"]
        self.assertEqual((iot["events"], iot["incidents"], iot["n_sources"]), (6, 3, 2))
        bot = r["per_dataset"]["Bot-IoT"]
        self.assertEqual((bot["events"], bot["incidents"]), (110, 3))
        self.assertAlmostEqual(bot["alert_reduction"], 1 - 3 / 110)
        self.assertIn("other", r["per_dataset"])
        self.assertEqual((r["overall"]["events"], r["overall"]["incidents"]), (120, 7))
        self.assertAlmostEqual(r["overall"]["alert_reduction"], 1 - 7 / 120)
        self.assertEqual(r["overall"]["cross_source_incidents"], 0)


class RobustnessTests(unittest.TestCase):
    ROWS = [
        # i1: 3 events, true majority recon; frag votes recon, integ dos
        ("i1", "recon", "recon", "dos"), ("i1", "recon", "benign", "dos"),
        ("i1", "benign", "recon", "dos"),
        # i2: true tie benign/recon -> benign; frag tie dos/recon -> dos (A-Z)
        ("i2", "benign", "dos", "benign"), ("i2", "recon", "recon", "benign"),
        # i3: true tie dos/recon -> dos; frag tie benign/recon -> benign
        ("i3", "recon", "benign", "recon"), ("i3", "dos", "recon", "recon"),
        # i4: one event (the "large" incident in the size check)
        ("i4", "dos", "dos", "dos"),
    ]
    INC = pd.DataFrame({"incident_id": ["i1", "i2", "i3", "i4", "unused"],
                        "n_events": [3, 2, 2, 50, 7]})

    def test_majority_vote_tie_break(self):
        f, i = _preds(self.ROWS)
        df = ev._aligned(f, i)
        self.assertEqual(ev.incident_vote(df, "label").to_dict(),
                         {"i1": "recon", "i2": "benign", "i3": "dos", "i4": "dos"})
        self.assertEqual(ev.incident_vote(df, "pred_fragmented").to_dict(),
                         {"i1": "recon", "i2": "dos", "i3": "benign", "i4": "dos"})

    def test_incident_vote_scored_with_evaluate_split(self):
        f, i = _preds(self.ROWS)
        r = ev.robustness(f, i, self.INC, max_incident_events=10)
        vote = r["incident_majority_vote"]
        self.assertEqual(vote["n_incidents"], 4)
        truth = ["recon", "benign", "dos", "dos"]
        want_f = evaluate_split(pd.Series(truth),
                                pd.Series(["recon", "dos", "benign", "dos"]))
        want_i = evaluate_split(pd.Series(truth),
                                pd.Series(["dos", "benign", "recon", "dos"]))
        for k in ("accuracy", "f1_macro", "fpr", "fnr"):
            self.assertAlmostEqual(vote["fragmented"][k], want_f[k])
            self.assertAlmostEqual(vote["integrated"][k], want_i[k])

    def test_small_incident_restriction(self):
        f, i = _preds(self.ROWS)
        sm = ev.robustness(f, i, self.INC, max_incident_events=10)["small_incidents"]
        self.assertEqual((sm["n_events_kept"], sm["n_events_excluded"]), (7, 1))
        self.assertEqual((sm["n_incidents_kept"], sm["n_incidents_excluded"]), (3, 1))
        keep = [r for r in self.ROWS if r[0] != "i4"]
        want = evaluate_split(pd.Series([r[1] for r in keep]),
                              pd.Series([r[2] for r in keep]))
        self.assertAlmostEqual(sm["fragmented"]["f1_macro"], want["f1_macro"])
        self.assertEqual(sm["fragmented"]["n_samples"], 7)

    def test_conditions_must_cover_same_events(self):
        f, i = _preds(self.ROWS)
        with self.assertRaises(ValueError):
            ev.robustness(f, i.iloc[1:], self.INC)
        with self.assertRaises(KeyError):
            ev.robustness(f, i, self.INC[self.INC["incident_id"] != "i1"])


class ClusterBootstrapTests(unittest.TestCase):
    @staticmethod
    def _synthetic(seed: int = 3) -> list[tuple[str, str, str, str]]:
        rng = np.random.RandomState(seed)
        classes = ["benign", "dos", "recon"]
        rows = []
        for k in range(14):
            for _ in range(rng.randint(1, 6)):
                y = classes[rng.randint(0, 3)]
                pf = y if rng.rand() < 0.8 else classes[rng.randint(0, 3)]
                pi = y if rng.rand() < 0.6 else classes[rng.randint(0, 3)]
                rows.append((f"inc{k:02d}", y, pf, pi))
        return rows

    @staticmethod
    def _brute(rows, n_boot: int, seed: int) -> dict:
        """Resample incidents, materialise the events, score with sklearn."""
        df = pd.DataFrame(rows, columns=["incident_id", "label", "pf", "pi"])
        ids = sorted(df["incident_id"].unique())
        groups = {g: d for g, d in df.groupby("incident_id")}
        labels = {c: sorted(set(df["label"]) | set(df[c])) for c in ("pf", "pi")}
        rng = np.random.default_rng(seed)
        out = {c: {m: [] for m in ev.BOOT_METRICS} for c in ("pf", "pi")}
        for _ in range(n_boot):
            draw = rng.integers(0, len(ids), size=len(ids))
            s = pd.concat([groups[ids[j]] for j in draw])
            y = s["label"].to_numpy()
            for c in ("pf", "pi"):
                p = s[c].to_numpy()
                ben, pben = y == "benign", p == "benign"
                out[c]["accuracy"].append(accuracy_score(y, p))
                out[c]["f1_macro"].append(f1_score(
                    y, p, labels=labels[c], average="macro", zero_division=0))
                out[c]["fpr"].append((ben & ~pben).sum() / ben.sum()
                                     if ben.any() else np.nan)
                out[c]["fnr"].append((~ben & pben).sum() / (~ben).sum()
                                     if (~ben).any() else np.nan)
        return {c: {m: np.array(v, dtype=float) for m, v in d.items()}
                for c, d in out.items()}

    def test_matches_brute_force_bootstrap(self):
        rows = self._synthetic()
        f, i = _preds(rows)
        n_boot, seed = 60, 11
        n_inc = len({r[0] for r in rows})
        # A tiny memory cap forces several weight-matrix batches.
        got = ev.cluster_bootstrap(f, i, n_boot=n_boot, seed=seed,
                                   max_bytes=16 * n_inc * 7)
        want = self._brute(rows, n_boot, seed)
        self.assertEqual(got["n_incidents"], n_inc)
        for cond, c in (("fragmented", "pf"), ("integrated", "pi")):
            for m in ev.BOOT_METRICS:
                v = want[c][m]
                v = v[~np.isnan(v)]
                self.assertAlmostEqual(got[cond][m]["mean"], v.mean(), places=10)
                self.assertAlmostEqual(got[cond][m]["ci_low"],
                                       np.percentile(v, 2.5), places=10)
                self.assertAlmostEqual(got[cond][m]["ci_high"],
                                       np.percentile(v, 97.5), places=10)
        for m in ev.BOOT_METRICS:
            d = want["pi"][m] - want["pf"][m]
            d = d[~np.isnan(d)]
            self.assertAlmostEqual(got["difference"][m]["mean"], d.mean(), places=10)
            self.assertAlmostEqual(got["difference"][m]["ci_low"],
                                   np.percentile(d, 2.5), places=10)

    def test_point_estimate_equals_evaluate_split(self):
        rows = self._synthetic(seed=5)
        f, i = _preds(rows)
        got = ev.cluster_bootstrap(f, i, n_boot=20, seed=1)
        for cond, frame in (("fragmented", f), ("integrated", i)):
            want = evaluate_split(frame["label"], frame["pred"])
            for m in ev.BOOT_METRICS:
                self.assertAlmostEqual(got[cond][m]["point"], want[m])
        self.assertIn("NOT a significance test", got["note"])
        self.assertTrue(math.isclose(
            got["difference"]["f1_macro"]["point"],
            got["integrated"]["f1_macro"]["point"]
            - got["fragmented"]["f1_macro"]["point"]))


if __name__ == "__main__":
    unittest.main()
