"""Incident membership and alert reduction recomputed from the Stage 3 tables."""
import unittest

import numpy as np

from _common import ensure_cache, ev


class TestIncidents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_cache()
        cls.rep = ev.load_report()
        cls.inc = ev.incidents()

    def test_membership_for_sample_incidents(self):
        ids = []
        for s, g in self.inc.groupby("source"):
            ids.append(g.nlargest(1, "n_events")["incident_id"].iloc[0])   # largest
            ids.append(g.sample(n=1, random_state=42)["incident_id"].iloc[0])
            multi = g[g["n_events"] > 1]
            if len(multi):
                ids.append(multi.sample(n=1, random_state=7)["incident_id"].iloc[0])
        self.assertGreaterEqual(len(ids), 26)
        for iid in ids:
            with self.subTest(incident=iid):
                d = ev.incident_members(iid)
                self.assertTrue(d["all_ok"], d["checks"][~d["checks"]["ok"]])
                self.assertEqual(d["n_members"], int(d["incident"]["n_events"]))
                self.assertLessEqual(len(d["members"]), ev.MAX_SELECTION)

    def test_window_bucket(self):
        start, end, b = ev.window_of(1528095725.534862, 300)
        self.assertEqual(b, 1528095725 // 300)
        self.assertEqual(end - start, 300)
        self.assertTrue(start <= 1528095725.534862 < end)

    def test_alert_reduction_recomputed_equals_json(self):
        ard = self.rep["alert_reduction_by_dataset"]
        rec = ev.alert_reduction_recomputed().set_index("source")
        for s, v in ard["per_source"].items():
            with self.subTest(source=s):
                self.assertEqual(int(rec.loc[s, "events"]), v["events"])
                self.assertEqual(int(rec.loc[s, "incidents"]), v["incidents"])
                self.assertTrue(ev.close(float(rec.loc[s, "alert_reduction"]), v["alert_reduction"], 1e-12))
        idx = ev.source_index().set_index("source")
        for fam, v in ard["per_dataset"].items():
            srcs = idx.index[idx["dataset"] == fam]
            self.assertEqual(int(rec.loc[srcs, "events"].sum()), v["events"], fam)
            self.assertEqual(int(rec.loc[srcs, "incidents"].sum()), v["incidents"], fam)
        ov = ard["overall"]
        self.assertEqual(int(rec["events"].sum()), ov["events"])
        self.assertEqual(len(self.inc), ov["incidents"])
        self.assertTrue(ev.close(1 - len(self.inc) / rec["events"].sum(), ov["alert_reduction"], 1e-12))
        self.assertEqual(int((self.inc["cross_source"] > 1).sum()), ov["cross_source_incidents"])
        self.assertEqual(self.rep["alert_reduction"]["unified_incidents"], ov["incidents"])
        self.assertEqual(self.rep["alert_reduction"]["raw_alerts"], ov["events"])

    def test_staged_counts_equal_report_per_source(self):
        idx = ev.source_index().set_index("source")
        for s, v in self.rep["alert_reduction_by_dataset"]["per_source"].items():
            self.assertEqual(int(idx.loc[s, "n_events"]), v["events"], s)

    def test_test_incident_count(self):
        dg = ev.diagnostics()
        n_test = int((dg["n_test_events"] > 0).sum())
        self.assertEqual(n_test, self.rep["split"]["n_test_incidents"])
        mixed = int(((dg["n_test_events"] > 0) & (dg["n_train_events"] > 0)).sum())
        self.assertEqual(mixed, self.rep["split"]["n_mixed_incidents"])

    def test_proto_map_one_to_one(self):
        pn = ev.proto_names()
        self.assertEqual(len(set(pn.values())), len(pn))
        dg = ev.diagnostics()
        self.assertTrue(set(dg["proto"].astype(int).unique()) <= set(pn))

    def test_classes_absent(self):
        conf, absent = ev.classes_absent()
        present = ev.classes_present()
        self.assertEqual(sorted(set(conf) - set(present)), sorted(absent))
        self.assertTrue(set(present) <= set(conf))
        self.assertEqual(sorted(present), sorted(self.rep["fragmented"]["classes"]))

    def test_class_events_sorted(self):
        ids, ts = ev.class_events("CTU-IoT-Malware-Capture-34-1", "dos")
        self.assertEqual(len(ids), int(ev.label_counts().query(
            "source == 'CTU-IoT-Malware-Capture-34-1' and label == 'dos'")["events"].iloc[0]))
        self.assertTrue((np.diff(ts) >= 0).all())


if __name__ == "__main__":
    unittest.main()
