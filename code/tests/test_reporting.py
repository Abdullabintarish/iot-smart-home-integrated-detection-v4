"""Reporting smoke test: build the Markdown report from a small synthetic
Stage 5 report dict and check its wording and table numbers."""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import evaluate as ev
from pipeline import reporting as rp
from pipeline.detect import evaluate_split


def _synthetic_report() -> dict:
    """A Stage-5-shaped dict built by the real Stage 5 functions on toy data."""
    rng = np.random.RandomState(0)
    classes = ["benign", "dos", "recon"]
    rows = []
    for k in range(30):
        src = "CTU-a" if k % 2 else "data_1"
        y = classes[k % 3]
        for _ in range(rng.randint(1, 4)):
            rows.append((f"i{k:02d}", src, y,
                         y if rng.rand() < 0.9 else classes[rng.randint(0, 3)],
                         y if rng.rand() < 0.7 else classes[rng.randint(0, 3)]))
    df = pd.DataFrame(rows, columns=["incident_id", "source", "label", "pf", "pi"])
    df["event_id"], df["split"] = np.arange(len(df)), "test"
    base = ["event_id", "source", "incident_id", "split", "label"]
    pf = df[base + ["pf"]].rename(columns={"pf": "pred"})
    pi = df[base + ["pi"]].rename(columns={"pi": "pred"})
    inc = (df.groupby(["incident_id", "source"]).size().rename("n_events")
           .reset_index().assign(cross_source=1))

    frag = evaluate_split(df["label"], df["pf"])
    frag.update(n_test=len(df), n_sources=2, n_rf_models=2, n_features=3,
                features=["f_a", "f_b", "f_c"], cv_f1_mean=0.9, cv_f1_std=0.01,
                cv_n_sources=1, cv_sources_skipped=["CTU-a"],
                per_source={"CTU-a": {"accuracy": 1.0, "f1_macro": 1.0, "fpr": 0.0,
                                      "n_test": 10, "train_class_counts": {"benign": 5}}})
    integ = evaluate_split(df["label"], df["pi"])
    integ.update(n_test=len(df), n_features=2, features=["n_events", "n_sources"],
                 train_class_counts={"benign": 4, "dos": 3},
                 feature_importance=[{"feature": "n_events", "importance": 1.0},
                                     {"feature": "n_sources", "importance": 0.0}])
    table = ev.comparison_table(frag, integ)
    report = {"fragmented": frag, "integrated": integ,
              "alert_reduction": {"raw_alerts": len(df), "unified_incidents": len(inc),
                                  "alert_reduction": 1 - len(inc) / len(df),
                                  "cross_source_incidents": 0},
              "comparison": table.to_dict(orient="records"),
              "model_config": {"n_estimators": 300},
              "split": {"strategy": "toy", "n_events": 2 * len(df),
                        "n_train_incidents": 30, "n_test_incidents": 30,
                        "n_mixed_incidents": 0, "events": []},
              "integrated_incident_level": evaluate_split(
                  pd.Series(["dos", "recon"]), pd.Series(["dos", "dos"])),
              "alert_reduction_by_dataset": ev.alert_reduction_by_dataset(inc),
              "robustness": ev.robustness(pf, pi, inc, max_incident_events=2),
              "bootstrap": ev.cluster_bootstrap(pf, pi, n_boot=30, seed=1),
              "diagnostics": {"note": "diag",
                              "pooled_event_model": evaluate_split(df["label"], df["pf"]),
                              "duplicates": {"fraction_all": 0.1, "n_novel": 5,
                                             "novel_only_metrics": {}}}}
    # Round-trip through JSON, as make_report reads it from disk.
    return json.loads(json.dumps(report, default=str))


class ReportSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        results = root / "results"
        results.mkdir()
        (results / "stage5_report.json").write_text("{}")
        cls.report = _synthetic_report()
        cls.md_path = rp.build_report(cls.report, out=results / "report",
                                      results_dir=results)
        cls.md = cls.md_path.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_no_outdated_wording(self):
        self.assertNotIn("Improvement", self.md)
        self.assertNotIn("improvement", self.md.lower())
        self.assertNotIn("Cross-source event correlation consolidated", self.md)
        self.assertIn("Difference (integrated − baseline)", self.md)
        self.assertIn("0 incidents span more than one source", self.md)
        self.assertIn("not a significance test", self.md)

    def test_results_table_matches_report_values(self):
        for r in self.report["comparison"]:
            name = r["metric"].replace("_", " ")
            if r["direction"] == "lower_is_better":
                name += " (lower is better)"
            m = re.search(rf"^\| {re.escape(name)} \| ([^|]+) \| ([^|]+) \| "
                          rf"([^|]+) \| ([^|]+) \|$", self.md, re.M)
            self.assertIsNotNone(m, name)
            f_, i_, d_, b_ = (g.strip() for g in m.groups())
            self.assertEqual(f_, f"{r['fragmented']:.4f}")
            self.assertEqual(i_, f"{r['integrated']:.4f}")
            self.assertEqual(d_, f"{r['integrated'] - r['fragmented']:+.4f}")
            self.assertEqual(b_, r["better"])

    def test_outcome_sentence_derived_from_numbers(self):
        f = self.report["fragmented"]["f1_macro"]
        i = self.report["integrated"]["f1_macro"]
        word = "higher" if i > f else "lower"
        self.assertIn(f"scored {word} macro F1 than the baseline "
                      f"(integrated {i:.4f} vs baseline {f:.4f}", self.md)

    def test_figures_and_artefacts(self):
        out = self.md_path.parent
        for name in ("fig_metrics_comparison.png", "fig_per_class_f1.png",
                     "fig_confusion_fragmented.png", "fig_confusion_integrated.png",
                     "fig_alert_reduction_by_dataset.png"):
            self.assertTrue((out / name).exists(), name)
        self.assertIn("`results/stage5_report.json`", self.md)
        self.assertNotIn("rf_integrated.joblib", self.md)   # not created here


if __name__ == "__main__":
    unittest.main()
