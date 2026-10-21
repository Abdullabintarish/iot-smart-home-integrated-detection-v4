"""Stage 2 tests: streaming Pearson, encoders, alignment, split, selection."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from pipeline import preprocess as pp
from pipeline.config import CLASSES
from pipeline.correlate import correlation_key


def _no_test_split():
    """Every row is "train", so references can use the whole fixture."""
    return mock.patch.object(pp, "TEST_FRACTION", 0.0, create=True)


def _codes(labels: pd.Series) -> np.ndarray:
    names = sorted(set(CLASSES) | set(labels.astype(str)))
    return labels.astype(str).map({n: i for i, n in enumerate(names)}).to_numpy(float)


def _chunks(seed: int = 0) -> list[pd.DataFrame]:
    """Three chunks with different label subsets, 1e9 offsets, an absent
    feature (``z`` is missing from chunk 2), a constant feature (``k``) and one
    constant only within chunk 1 (``pkts``)."""
    rng = np.random.RandomState(seed)
    out = []
    for i, labs in enumerate((["benign", "malware"], ["recon", "benign", "dos"],
                              ["malware", "dos"])):
        n = 300
        lab = pd.Series(rng.choice(labs, n))
        y = _codes(lab)
        df = pd.DataFrame({
            "src_ip": [f"10.0.{i}.{j % 250}" for j in range(n)],
            "dst_ip": "10.1.0.1", "source": f"src{i % 2}",
            "ts": 1.5e9 + i * n + np.arange(n, dtype=float),
            "bytes": 1e9 + 1e3 * y + rng.normal(0, 2e3, n),
            "pkts": rng.randint(0, 50, n).astype("int64"),
            "z": y * 0.5 + rng.normal(0, 1, n),
            "k": 7.0,
            "label": lab,
        })
        if i == 0:
            df["pkts"] = 60       # constant in this chunk only, not globally
        if i == 1:
            df = df.drop(columns="z")
        out.append(df)
    return out


def _pair_r(a: pd.Series, b: pd.Series) -> float:
    m = a.notna() & b.notna()
    return float(np.corrcoef(a[m], b[m])[0, 1])


class PearsonTests(unittest.TestCase):
    def test_label_pearson_matches_numpy(self) -> None:
        chunks = _chunks()
        with _no_test_split():
            plan = pp.fit(chunks)
        full = pd.concat(chunks, ignore_index=True)
        y = pd.Series(_codes(full["label"]))
        for col in ("bytes", "pkts", "z"):
            ref = abs(_pair_r(full[col], y))
            self.assertLess(ref, 0.999)      # fixture is not degenerate
            self.assertAlmostEqual(plan.correlations[col], ref, delta=1e-9 * ref,
                                   msg=col)
        self.assertNotIn("k", plan.kept)     # constant column
        # The chunk where pkts is constant still contributes its value.
        self.assertEqual(plan.summary().set_index("feature").loc["pkts", "global_max"], 60)

    def test_pairwise_pearson_matches_numpy(self) -> None:
        chunks = _chunks(1)
        with _no_test_split():
            plan = pp.fit(chunks)
        full = pd.concat(chunks, ignore_index=True)
        for a, b in (("bytes", "pkts"), ("bytes", "z"), ("pkts", "z")):
            ref = abs(_pair_r(full[a], full[b]))
            self.assertAlmostEqual(plan.redundancy.loc[a, b], ref,
                                   delta=1e-9 * max(ref, 1e-3), msg=(a, b))

    def test_label_codes_fixed_across_chunks(self) -> None:
        with _no_test_split():
            plan = pp.fit(_chunks())
        names = sorted(CLASSES)
        self.assertEqual(plan.label_codes, {n: i for i, n in enumerate(names)})


def _frame(**cols) -> pd.DataFrame:
    n = len(next(iter(cols.values())))
    base = {"src_ip": [f"10.0.0.{i}" for i in range(n)], "dst_ip": "10.0.0.254",
            "source": "s", "ts": np.arange(n, dtype=float), "label": "benign"}
    base.update(cols)
    return pd.DataFrame(base)


class EncoderTests(unittest.TestCase):
    def test_global_minmax(self) -> None:
        c1 = _frame(pkts=[0.0, 5.0, 10.0], label=["benign", "dos", "recon"])
        c2 = _frame(pkts=[5.0, 6.0, 7.0], label=["dos", "benign", "dos"])
        with _no_test_split():
            plan = pp.fit([c1, c2])
            o1, o2 = list(pp.transform([c1, c2], plan))
        self.assertEqual(list(o1["pkts"]), [0.0, 0.5, 1.0])
        self.assertAlmostEqual(o2["pkts"].iloc[0], 0.5)
        self.assertAlmostEqual(o2["pkts"].iloc[2], 0.7)

    def test_vocabulary_union_and_unseen(self) -> None:
        c1 = _frame(proto=["tcp", "udp", "tcp"])
        c2 = _frame(proto=["icmp", "arp", "udp"])
        c3 = _frame(proto=["gre", "icmp", None])
        with _no_test_split():
            plan = pp.fit([c1, c2])
            out = list(pp.transform([c1, c2, c3], plan))
        self.assertTrue({"arp", "icmp", "tcp", "udp"} <= set(plan.categories["proto"]))
        self.assertTrue((out[1]["proto"] >= 0).all())
        self.assertEqual(out[2]["proto"].iloc[0], -1)        # unseen in train
        self.assertGreaterEqual(out[2]["proto"].iloc[1], 0)
        self.assertNotEqual(out[2]["proto"].iloc[2], -1)     # missing != unseen
        self.assertEqual(out[1]["proto"].iloc[0], out[2]["proto"].iloc[1])

    def test_alignment_after_dropped_rows(self) -> None:
        df = _frame(pkts=[0.0, 1.0, 1.0, 2.0, 3.0, 4.0],
                    label=["benign", "dos", "dos", "recon", "malware", "c2"])
        df.loc[2] = df.loc[1]                     # exact duplicate of row 1
        df.loc[4] = np.nan                        # all-empty row
        with _no_test_split():
            plan = pp.fit([df])
            out = pd.concat(pp.transform([df], plan), ignore_index=True)
        self.assertEqual(len(out), 4)
        expect = {0.0: ("benign", "10.0.0.0"), 1.0: ("dos", "10.0.0.1"),
                  2.0: ("recon", "10.0.0.3"), 4.0: ("c2", "10.0.0.5")}
        for _, r in out.iterrows():
            raw = round(r["pkts"] * 4.0, 6)
            self.assertEqual((r["label"], r["src_ip"]), expect[raw])
        self.assertEqual(plan.row_counts["dropped_duplicate"], 1)
        self.assertEqual(plan.row_counts["dropped_all_nan"], 1)

    def test_one_role_per_column(self) -> None:
        c1 = _frame(sport=[1.0, 2.0, 3.0], proto=["tcp", "udp", "tcp"])
        c2 = _frame(sport=["a", "b", "c"], proto=["1", "2", "3"])
        c3 = _frame(sport=["x", "y", "z"], proto=["tcp", "udp", "icmp"])
        with _no_test_split():
            plan = pp.fit([c1, c2, c3])
        for col in ("sport", "proto"):
            self.assertEqual((col in plan.numeric) + (col in plan.categorical), 1,
                             msg=col)
        self.assertIn("sport", plan.categorical)   # 3 of 9 values parse

    def test_test_rows_scale_outside_unit_range(self) -> None:
        train = _frame(pkts=[0.0, 10.0, 5.0])
        later = _frame(pkts=[20.0, -10.0, np.nan])
        with _no_test_split():
            plan = pp.fit([train])
            out = list(pp.transform([later], plan))[0]
        self.assertEqual(list(out["pkts"]), [2.0, -1.0, -1.0])
        self.assertEqual(pp.MISSING_SENTINEL, -1.0)


class LeakageTests(unittest.TestCase):
    def test_label_source_columns_never_features(self) -> None:
        leak = ("category", "subcategory", "attack", "Label", "Category",
                "Subcategory", "attack_type", "class", "detailed-label",
                "det_label")
        n = 6
        cols = {c: [f"{c}{i % 3}" for i in range(n)] for c in leak}
        cols["attack"] = [i % 2 for i in range(n)]
        cols["pkts"] = [float(i) for i in range(n)]
        df = _frame(**cols)
        with _no_test_split():
            plan = pp.fit([df])
            out = list(pp.transform([df], plan))[0]
        for c in leak:
            self.assertNotIn(c, plan.kept)
            self.assertNotIn(c, out.columns)
        self.assertEqual(plan.kept, ["pkts"])

    def test_fit_ignores_test_rows(self) -> None:
        rng = np.random.RandomState(3)
        n = 400
        df = _frame(pkts=rng.normal(100, 10, n), dur=rng.exponential(2, n),
                    app=rng.choice(["dns", "http"], n),
                    label=rng.choice(["benign", "dos", "recon"], n))
        split = pp.assign_split(df, {})
        test = split == "test"
        self.assertTrue(test.any() and (~test).any())
        df2 = df.copy()
        df2.loc[test, "pkts"] *= 1000.0
        df2.loc[test, "dur"] = -5.0
        df2.loc[test, "app"] = "ssh"        # (split-key columns left as-is)
        df2.loc[test, "label"] = "theft"
        a, b = pp.fit([df.iloc[:150], df.iloc[150:]]), pp.fit([df2])
        pd.testing.assert_frame_equal(a.summary(), b.summary())
        self.assertEqual(a.categories, b.categories)
        self.assertEqual(a.label_codes, b.label_codes)


class SelectionTests(unittest.TestCase):
    def _data(self) -> pd.DataFrame:
        rng = np.random.RandomState(7)
        n = 500
        a = rng.normal(0, 1, n)
        return _frame(a=a, b=3.0 * a + 7.0, c=rng.normal(0, 1, n), k=2.0,
                      label=rng.choice(["benign", "dos"], n))

    def test_redundancy_drops_linear_copy_only(self) -> None:
        with _no_test_split():
            plan = pp.fit([self._data()], method="redundancy")
        self.assertEqual(plan.kept, ["a", "c"])
        self.assertEqual(plan.dropped, ["b", "k"])
        rows = plan.summary().set_index("feature")
        self.assertEqual(rows.loc["b", "redundant_with"], "a")
        self.assertAlmostEqual(rows.loc["b", "redundancy_r"], 1.0, places=9)
        self.assertIn("constant", rows.loc["k", "reason"])
        self.assertEqual(list(plan.summary().columns), list(pp.PLAN_COLUMNS))

    def test_label_pearson_method(self) -> None:
        rng = np.random.RandomState(11)
        n = 2000
        lab = pd.Series(rng.choice(["benign", "dos"], n))
        df = _frame(sig=_codes(lab) + rng.normal(0, 0.5, n),
                    noise=rng.normal(0, 1, n), label=lab)
        with _no_test_split():
            plan = pp.fit([df], method="label_pearson")
        self.assertIn("sig", plan.kept)
        self.assertIn("noise", plan.dropped)
        self.assertLess(plan.correlations["noise"], pp.MIN_CORR_WITH_LABEL)

    def test_fit_is_deterministic(self) -> None:
        chunks = _chunks(5)
        a, b = pp.fit(chunks), pp.fit(chunks)
        pd.testing.assert_frame_equal(a.summary(), b.summary())
        self.assertEqual(a.kept, b.kept)

    def test_assign_split_stable_and_chunk_independent(self) -> None:
        # 2 sources x 10 hosts x 100 five-minute buckets = 2000 correlation
        # groups, plus 2000 uncorrelatable rows (no IPs) split one by one.
        rng = np.random.RandomState(0)
        n = 20000
        df = pd.DataFrame({"source": np.where(np.arange(n) % 3, "a", "b"),
                           "ts": np.sort(rng.uniform(0, 30000, n)),
                           "src_ip": [f"10.0.0.{i}" for i in rng.randint(0, 10, n)],
                           "dst_ip": "2.2.2.2", "sport": 1, "dport": 2,
                           "proto": "tcp"})
        df.loc[::10, ["src_ip", "dst_ip"]] = None
        whole = pp.assign_split(df, {})
        offsets: dict[str, int] = {}
        parts = pd.concat([pp.assign_split(df.iloc[i:i + 3000], offsets)
                           for i in range(0, n, 3000)])
        self.assertTrue(whole.equals(parts))
        self.assertTrue(whole.equals(pp.assign_split(df, {})))
        # One split per correlation group; ~25 % of groups (and singletons).
        key, _, _ = correlation_key(df)
        grouped = key.notna()
        by_group = whole[grouped].groupby(key[grouped])
        self.assertTrue((by_group.nunique() == 1).all())
        self.assertGreater(by_group.ngroups, 1900)
        self.assertAlmostEqual((by_group.first() == "test").mean(), 0.25,
                               delta=0.03)
        self.assertEqual(int((~grouped).sum()), 2000)
        self.assertAlmostEqual((whole[~grouped] == "test").mean(), 0.25,
                               delta=0.03)


class PreprocessEndToEndTests(unittest.TestCase):
    def test_writes_plan_and_numbered_shards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src, out = tmp / "interim", tmp / "processed"
            src.mkdir()
            for i, c in enumerate(_chunks()):
                c.to_parquet(src / f"shard_{i:04d}.parquet", index=False)
            with mock.patch.object(pp, "DATA_OUT", out):
                plan, written = pp.preprocess(src)
            self.assertEqual([p.name for p in written], ["stage2_0000.parquet"])
            df = pd.read_parquet(written[0])
            self.assertEqual(len(df), 900)
            self.assertEqual(set(df["split"]), {"train", "test"})
            self.assertTrue((df["z"] == -1.0).sum() >= 300)   # absent in chunk 2
            csv = pd.read_csv(out / "stage2_feature_plan.csv")
            self.assertEqual(list(csv.columns), list(pp.PLAN_COLUMNS))


if __name__ == "__main__":
    unittest.main()
