"""event_id -> interim row -> raw-file line agreement, for every source.

The raw record is read with a bounded read and normalised with the same
pipeline.ingest functions Stage 1 used (imported read-only).
"""
import unittest

import numpy as np
import pyarrow.parquet as pq

from _common import ev


class TestIdentifierMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.idx = ev.source_index()
        rng = np.random.default_rng(42)
        cls.samples = {}
        for r in cls.idx.itertuples():
            n = int(r.n_events)
            picks = {0, 1, n // 2, n - 1, int(rng.integers(0, n))}
            cls.samples[r.source] = sorted(int(r.first_event_id) + p for p in picks if 0 <= p < n)

    def test_thirteen_sources_contiguous(self):
        self.assertEqual(len(self.idx), 13)
        end = (self.idx["first_event_id"] + self.idx["n_events"]).to_numpy()
        self.assertTrue((self.idx["first_event_id"].to_numpy()[1:] == end[:-1]).all())
        self.assertEqual(int(end[-1]), ev.n_stream_events())
        rep = ev.load_report()
        self.assertEqual(ev.n_stream_events(), rep["split"]["n_events"])

    def test_stage_streams_have_equal_length(self):
        n = ev.n_stream_events()
        self.assertEqual(ev.stage2_spans()[-1].end, n)
        self.assertEqual(ev.stage3_spans()[-1].end, n)

    def test_raw_line_agrees_with_staged_record(self):
        checked = 0
        for source, eids in self.samples.items():
            self.assertGreaterEqual(len(eids), 3, source)
            for eid in eids:
                with self.subTest(source=source, event_id=eid):
                    c = ev.compare_with_raw(eid)
                    self.assertEqual(c["source"], source)
                    self.assertTrue(c["key_match"], c["rows"][~c["rows"]["match"]])
                    self.assertTrue(c["all_match"], c["rows"][~c["rows"]["match"]])
                    checked += 1
        self.assertGreaterEqual(checked, 3 * 13)

    def test_raw_record_count_equals_staged_count(self):
        # The last record exists and the one after it does not: the raw file
        # holds exactly n_events data records, so no row was skipped.
        for r in self.idx.itertuples():
            with self.subTest(source=r.source):
                ev.read_raw_record(r.source, int(r.n_events) - 1)
                with self.assertRaises(IndexError):
                    ev.read_raw_record(r.source, int(r.n_events))

    def test_same_position_in_interim_stage2_stage3(self):
        cols = ["src_ip", "dst_ip", "ts", "label", "source"]
        eids = [e for v in self.samples.values() for e in v]
        a = ev.take_rows(ev.interim_spans(), eids, cols)
        b = ev.take_rows(ev.stage2_spans(), eids, cols)
        c = ev.take_rows(ev.stage3_spans(), eids, cols)
        for col in ("src_ip", "dst_ip", "label", "source"):
            self.assertEqual(a[col].astype(str).tolist(), b[col].astype(str).tolist(), col)
            self.assertEqual(a[col].astype(str).tolist(), c[col].astype(str).tolist(), col)
        np.testing.assert_array_equal(a["ts"].to_numpy(), b["ts"].to_numpy())
        np.testing.assert_array_equal(a["ts"].to_numpy(), c["ts"].to_numpy())

    def test_record_index(self):
        r = self.idx.iloc[5]
        self.assertEqual(ev.record_index(int(r["first_event_id"])), 0)
        self.assertEqual(ev.record_index(int(r["first_event_id"]) + 7), 7)

    def test_selection_cap(self):
        with self.assertRaises(ValueError):
            ev.take_rows(ev.interim_spans(), range(ev.MAX_SELECTION + 1))

    def test_one_source_per_shard(self):
        for s in ev.interim_spans():
            vals = pq.read_table(s.path, columns=["source"]).column(0).unique()
            self.assertEqual(len(vals), 1, ev.rel(s.path))


if __name__ == "__main__":
    unittest.main()
