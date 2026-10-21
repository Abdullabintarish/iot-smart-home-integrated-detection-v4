"""Stage 3 tests: rule-based correlation, missing values, scope, chunking."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import correlate as cr
from pipeline.detect import feature_matrix

FEATURES = ["duration", "fwd_bytes"]


def _ev(src, dst, proto, ts, source="capA", label="benign", split="train"):
    return {"duration": 0.5, "fwd_bytes": 0.25, "proto": proto,
            "src_ip": src, "dst_ip": dst, "source": source, "ts": ts,
            "label": label, "split": split}


def _frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["proto"] = pd.to_numeric(df["proto"]).astype("float64")
    df["src_ip"] = df["src_ip"].astype("string")
    df["dst_ip"] = df["dst_ip"].astype("string")
    return df


def _run(df: pd.DataFrame, batch: int | None = None, scope: str | None = None,
         window: int = 300):
    """Run correlate_stream on ``df`` cut into ``batch``-row chunks.

    Returns (events, incidents, stats, diagnostics or None).
    """
    step = batch or max(1, len(df))
    chunks = [df.iloc[i:i + step].reset_index(drop=True)
              for i in range(0, len(df), step)]
    kw = {} if scope is None else {"scope": scope}
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        inc, stats = cr.correlate_stream(iter(chunks), out_dir=out,
                                         window_s=window, **kw)
        ev = pd.concat([pd.read_parquet(p) for p in
                        sorted((out / "stage3_events").glob("*.parquet"))],
                       ignore_index=True)
        dg_files = sorted((out / "stage3_incident_diagnostics").glob("*.parquet"))
        diag = (pd.concat([pd.read_parquet(p) for p in dg_files],
                          ignore_index=True) if dg_files else None)
    return ev, inc, stats, diag


def _groups(ev: pd.DataFrame) -> list[list[int]]:
    """Partition of event positions into incidents, order-independent."""
    g = ev.reset_index(drop=True).groupby("incident_id").groups
    return sorted(sorted(int(i) for i in v) for v in g.values())


class GroupingRuleTests(unittest.TestCase):
    def test_related_events_form_one_incident(self):
        df = _frame([_ev("10.0.0.1", "10.0.0.2", 4, 1000.0 + t) for t in (0, 10, 20)])
        ev, inc, _, _ = _run(df)
        self.assertEqual(len(inc), 1)
        self.assertEqual(int(inc["n_events"].iloc[0]), 3)
        self.assertEqual(ev["incident_id"].nunique(), 1)

    def test_different_src_or_dst_are_separate(self):
        df = _frame([_ev("10.0.0.1", "10.0.0.2", 4, 1000.0),
                     _ev("10.0.0.9", "10.0.0.2", 4, 1001.0),
                     _ev("10.0.0.1", "10.0.0.9", 4, 1002.0)])
        _, inc, _, _ = _run(df)
        self.assertEqual(len(inc), 3)

    def test_different_protocols_are_separate(self):
        df = _frame([_ev("10.0.0.1", "10.0.0.2", 4, 1000.0),
                     _ev("10.0.0.1", "10.0.0.2", 5, 1001.0)])
        _, inc, _, _ = _run(df)
        self.assertEqual(len(inc), 2)

    def test_rule_label_recorded_per_event(self):
        df = _frame([_ev("10.0.0.1", "10.0.0.2", 4, 1000.0),
                     _ev("10.0.0.1", None, 4, 1000.0),
                     _ev(None, "10.0.0.2", 4, 1000.0),
                     _ev(None, None, 4, 1000.0)])
        ev, _, _, _ = _run(df)
        self.assertEqual(ev["corr_rule"].tolist(),
                         ["R1_pair_proto", "R2_src_proto", "R3_dst_proto",
                          "R0_singleton"])

    def test_r2_and_r3_keys_never_collide(self):
        # Same address once as source-only, once as destination-only: different
        # rules, so different incidents (R3 used to be hashed as R2).
        df = _frame([_ev("10.0.0.5", None, 4, 1000.0),
                     _ev(None, "10.0.0.5", 4, 1000.0)])
        _, inc, _, _ = _run(df)
        self.assertEqual(len(inc), 2)

    def test_r2_groups_same_source_without_destination(self):
        df = _frame([_ev("10.0.0.5", None, 4, 1000.0),
                     _ev("10.0.0.5", "-", 4, 1010.0)])
        _, inc, _, _ = _run(df)
        self.assertEqual(len(inc), 1)


class MissingValueTests(unittest.TestCase):
    def test_missing_timestamp_is_singleton(self):
        df = _frame([_ev("10.0.0.1", "10.0.0.2", 4, np.nan),
                     _ev("10.0.0.1", "10.0.0.2", 4, np.nan),
                     _ev("10.0.0.1", "10.0.0.2", 4, 0.0)])
        ev, inc, _, _ = _run(df)
        self.assertEqual(len(inc), 3)
        self.assertEqual(ev["corr_rule"].iloc[0], "R0_singleton")

    def test_missing_both_ips_is_singleton(self):
        df = _frame([_ev(None, None, 4, 1000.0), _ev("", "-", 4, 1000.0),
                     _ev("unknown", None, 4, 1001.0)])
        _, inc, _, _ = _run(df)
        self.assertEqual(len(inc), 3)

    def test_unknown_protocol_never_matches_on_its_own(self):
        # Codes 0 (__NA__), -1 (unseen) and NaN are "unknown"; with different
        # endpoints they must stay apart.
        df = _frame([_ev("10.0.0.1", "10.0.0.2", 0, 1000.0),
                     _ev("10.0.0.3", "10.0.0.4", -1, 1000.0),
                     _ev("10.0.0.5", "10.0.0.6", np.nan, 1000.0)])
        _, inc, _, _ = _run(df)
        self.assertEqual(len(inc), 3)

    def test_unknown_protocol_grouped_only_with_both_ips(self):
        # Documented choice: same src+dst, protocol unknown -> one incident,
        # keyed (src, dst, "unknown"); never merged with a known protocol.
        df = _frame([_ev("10.0.0.1", "10.0.0.2", 0, 1000.0),
                     _ev("10.0.0.1", "10.0.0.2", -1, 1001.0),
                     _ev("10.0.0.1", "10.0.0.2", np.nan, 1002.0),
                     _ev("10.0.0.1", "10.0.0.2", 4, 1003.0)])
        ev, inc, _, _ = _run(df)
        self.assertEqual(len(inc), 2)
        self.assertEqual(_groups(ev), [[0, 1, 2], [3]])


class WindowBoundaryTests(unittest.TestCase):
    """Tumbling buckets: floor(ts / 300). Documents boundary behaviour."""

    def test_events_straddling_a_boundary_split(self):
        df = _frame([_ev("10.0.0.1", "10.0.0.2", 4, 299.9),
                     _ev("10.0.0.1", "10.0.0.2", 4, 300.0)])
        _, inc, _, _ = _run(df)
        self.assertEqual(len(inc), 2)

    def test_events_inside_one_bucket_group(self):
        df = _frame([_ev("10.0.0.1", "10.0.0.2", 4, 0.0),
                     _ev("10.0.0.1", "10.0.0.2", 4, 299.9)])
        _, inc, _, _ = _run(df)
        self.assertEqual(len(inc), 1)
        self.assertAlmostEqual(float(inc["span_s"].iloc[0]), 299.9)


class ScopeTests(unittest.TestCase):
    def _two_captures(self) -> pd.DataFrame:
        return _frame([_ev("192.168.1.1", "192.168.1.2", 4, 1000.0, "iot23_cap"),
                       _ev("192.168.1.1", "192.168.1.2", 4, 1005.0, "botiot_csv"),
                       _ev("192.168.1.1", "192.168.1.2", 4, 1010.0, "iot23_cap")])

    def test_source_scope_keeps_captures_apart(self):
        _, inc, stats, _ = _run(self._two_captures(), scope="source")
        self.assertEqual(len(inc), 2)
        self.assertTrue((inc["cross_source"] == 1).all())
        self.assertEqual(int(stats["cross_source_incidents"].iloc[-1]), 0)

    def test_global_scope_merges_captures(self):
        _, inc, stats, _ = _run(self._two_captures(), scope="global")
        self.assertEqual(len(inc), 1)
        self.assertEqual(int(inc["cross_source"].iloc[0]), 2)
        self.assertEqual(inc["source"].iloc[0], "botiot_csv;iot23_cap")
        self.assertEqual(int(stats["cross_source_incidents"].iloc[-1]), 1)

    def test_default_scope_is_source(self):
        _, inc, _, _ = _run(self._two_captures())
        self.assertEqual(len(inc), 2)


def _random_corpus(n: int = 120, seed: int = 3) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    rows = []
    for i in range(n):
        src = f"10.0.0.{rng.randint(1, 4)}" if rng.rand() > 0.05 else None
        dst = f"10.0.1.{rng.randint(1, 3)}" if rng.rand() > 0.05 else None
        ts = float(rng.randint(0, 1500)) if rng.rand() > 0.03 else np.nan
        rows.append(_ev(src, dst, int(rng.choice([4, 5, 0])), ts,
                        str(rng.choice(["capA", "capB"])),
                        str(rng.choice(["benign", "dos", "recon"])),
                        "train" if rng.rand() > 0.25 else "test"))
    return _frame(rows)


class ChunkIndependenceTests(unittest.TestCase):
    def test_same_result_for_any_batch_size(self):
        df = _random_corpus()
        ref_ev, ref_inc, _, _ = _run(df, batch=None)
        ref = ref_inc.sort_values("incident_id").reset_index(drop=True)
        for batch in (7, 50):
            ev, inc, _, _ = _run(df, batch=batch)
            self.assertEqual(ev["incident_id"].tolist(),
                             ref_ev["incident_id"].tolist(), f"batch={batch}")
            got = inc.sort_values("incident_id").reset_index(drop=True)
            pd.testing.assert_frame_equal(got, ref, check_dtype=False,
                                          obj=f"incidents batch={batch}")

    def test_conversation_spanning_chunks_is_one_incident(self):
        df = _frame([_ev("10.0.0.1", "10.0.0.2", 4, 1000.0 + t) for t in range(4)])
        _, inc, stats, _ = _run(df, batch=2)
        self.assertEqual(len(inc), 1)
        self.assertEqual(int(inc["n_events"].iloc[0]), 4)
        self.assertAlmostEqual(float(stats["alert_reduction"].iloc[-1]), 0.75)


class IncidentTableTests(unittest.TestCase):
    def test_majority_tie_breaks_to_benign_then_alphabetical(self):
        a = [_ev("10.0.0.1", "10.0.0.2", 4, 1000.0, label=l)
             for l in ("dos", "dos", "benign", "benign")]
        b = [_ev("10.0.0.3", "10.0.0.4", 4, 1000.0, label=l)
             for l in ("recon", "recon", "dos", "dos")]
        for rows in (a + b, list(reversed(a + b))):
            ev, inc, _, _ = _run(_frame(rows))
            src_of = ev.drop_duplicates("incident_id").set_index(
                "incident_id")["src_ip"]
            lab = dict(zip(inc["incident_id"].map(src_of), inc["label"]))
            self.assertEqual(lab, {"10.0.0.1": "benign", "10.0.0.3": "dos"})
            self.assertEqual(int(inc["is_attack"].sum()), 1)

    def test_tie_break_is_deterministic_at_scale(self):
        # Many tied incidents: an unstable sort would pick arbitrary winners.
        rows = []
        for i in range(400):
            for lab in ("recon", "dos", "dos", "recon", "benign", "benign")[i % 2:]:
                rows.append(_ev(f"10.{i // 250}.0.{i % 250}", "10.9.9.9", 4,
                                1000.0, label=lab))
        _, inc, _, _ = _run(_frame(rows))
        # Even i: 2 recon, 2 dos, 2 benign -> benign. Odd i: 2 dos, 2 benign,
        # 1 recon -> benign. Then a dos/recon tie -> dos (alphabetical).
        self.assertEqual(len(inc), 400)
        self.assertTrue((inc["label"] == "benign").all())
        rows2 = [_ev(f"10.{i // 250}.1.{i % 250}", "10.9.9.9", 4, 1000.0,
                     label=lab)
                 for i in range(400) for lab in ("recon", "dos")]
        _, inc2, _, _ = _run(_frame(rows2))
        self.assertTrue((inc2["label"] == "dos").all())

    def test_no_label_statistic_in_incident_features(self):
        df = _random_corpus()
        _, inc, _, _ = _run(df)
        self.assertEqual(sorted(cr.INCIDENT_FEATURES),
                         sorted(["n_events", "n_sources", "n_src_ips",
                                 "n_dst_ips", "span_s", "events_per_s",
                                 "cross_source"]))
        # Every numeric incident column is either a feature or the target.
        numeric = set(inc.select_dtypes(include=[np.number]).columns)
        self.assertEqual(numeric, set(cr.INCIDENT_FEATURES) | {"is_attack"})
        X, _ = feature_matrix(inc, cr.INCIDENT_FEATURES)
        # Relabelling every event must not change any feature value.
        flipped = df.assign(label=df["label"].map(
            {"benign": "dos", "dos": "recon", "recon": "benign"}))
        _, inc2, _, _ = _run(flipped)
        X2, _ = feature_matrix(inc2, cr.INCIDENT_FEATURES)
        pd.testing.assert_frame_equal(X.reset_index(drop=True),
                                      X2.reset_index(drop=True))

    def test_label_statistics_go_to_diagnostics(self):
        df = _frame([_ev("10.0.0.1", "10.0.0.2", 4, 1000.0, label=l, split=s)
                     for l, s in (("dos", "train"), ("dos", "test"),
                                  ("benign", "train"), ("dos", "train"))])
        _, inc, _, diag = _run(df)
        self.assertIsNotNone(diag)
        self.assertNotIn("label_entropy", inc.columns)
        row = diag.iloc[0]
        self.assertEqual(row["label"], "dos")
        self.assertAlmostEqual(float(row["label_purity"]), 0.75)
        p = np.array([0.75, 0.25])
        self.assertAlmostEqual(float(row["label_entropy"]), float(-(p * np.log(p)).sum()))
        self.assertEqual((int(row["n_train_events"]), int(row["n_test_events"])), (3, 1))
        self.assertEqual(row["label_counts"], "benign:1;dos:3")

    def test_event_rows_carry_no_correlation_feature(self):
        df = _random_corpus()
        ev, _, _, _ = _run(df)
        self.assertNotIn("correlated_alert_count", ev.columns)
        # Stage 3 adds exactly two string columns and no numeric one.
        self.assertEqual(set(ev.columns) - set(df.columns),
                         {"incident_id", "corr_rule"})
        self.assertEqual(set(ev.select_dtypes(include=[np.number]).columns),
                         set(df.select_dtypes(include=[np.number]).columns))
        X, _ = feature_matrix(ev, FEATURES + ["proto"])
        Xin, _ = feature_matrix(df, FEATURES + ["proto"])
        pd.testing.assert_frame_equal(X, Xin)

    def test_counts_and_ids_are_consistent(self):
        df = _random_corpus()
        ev, inc, stats, diag = _run(df, batch=13)
        self.assertEqual(int(inc["n_events"].sum()), len(df))
        self.assertTrue(inc["incident_id"].is_unique)
        self.assertEqual(set(ev["incident_id"]), set(inc["incident_id"]))
        sizes = ev["incident_id"].value_counts()
        self.assertTrue((sizes.reindex(inc["incident_id"]).to_numpy()
                         == inc["n_events"].to_numpy()).all())
        self.assertEqual(int(stats["raw_events"].sum()), len(df))
        self.assertAlmostEqual(float(stats["alert_reduction"].iloc[-1]),
                               1 - len(inc) / len(df))
        self.assertTrue(((diag["n_train_events"] + diag["n_test_events"])
                         == diag["n_events"]).all())

    def test_empty_input(self):
        ev = cr.assign_incidents(_frame([_ev("a", "b", 4, 1.0)]).iloc[0:0])
        self.assertIn("incident_id", ev.columns)
        self.assertEqual(len(cr.summarise_incidents(ev)), 0)


if __name__ == "__main__":
    unittest.main()
