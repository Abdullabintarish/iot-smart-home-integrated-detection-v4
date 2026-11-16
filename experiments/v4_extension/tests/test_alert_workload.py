"""Unit tests for E2 alert counting (hand-made events)."""
import sys, unittest
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run_alert_workload as W

def events():
    # incident I1: 3 dos events (t 0, 10, 400 -> two 300 s buckets for C), I2: 2 benign, I3: 1 recon
    rows = [(0, "a", "b", "I1", "dos"), (10, "a", "b", "I1", "dos"), (400, "a", "b", "I1", "dos"),
            (20, "c", "d", "I2", "benign"), (30, "c", "d", "I2", "benign"), (50, "e", "f", "I3", "recon")]
    d = pd.DataFrame(rows, columns=["ts", "src_ip", "dst_ip", "incident_id", "label"])
    d["proto"] = 6.0; d["source"] = "S"; d["split"] = "test"; d["event_id"] = range(len(d))
    return d

class Workload(unittest.TestCase):
    def setUp(self):
        self.ev = events(); self.t = W.truth(self.ev)
        # event predictions: I1 events 2 and 3 alerted, one benign of I2 alerted, I3 missed
        self.p = np.array(["benign", "dos", "dos", "dos", "benign", "benign"])

    def test_design_a(self):
        al = self.p != "benign"
        r = W.summarise("A", "A", None, self.ev, self.p, np.arange(al.sum()), self.t,
                        W.first_alert_event(self.ev, self.p), "x")
        self.assertEqual(r["n_alerts"], 3); self.assertEqual(r["false_alarm_alerts"], 1)
        self.assertEqual(r["attack_incidents"], 2); self.assertEqual(r["attack_incidents_detected"], 1)
        self.assertEqual(r["attack_incidents_missed"], 1)
        self.assertEqual(r["delay_median_s"], 10.0)          # first attack t=0, first alerted attack t=10

    def test_design_c_groups_and_closed_delay(self):
        al = self.p != "benign"
        g = W.groups(self.ev, al, 300)
        self.assertEqual(len(set(g)), 3)                    # (a,b) bucket 0, (a,b) bucket 1, (c,d) bucket 0
        r = W.summarise("C", "C", 300, self.ev, self.p, g, self.t,
                        W.first_alert_closed(self.ev, self.p, g), "x")
        self.assertEqual(r["n_alerts"], 3); self.assertEqual(r["false_alarm_alerts"], 1)
        self.assertEqual(r["delay_median_s"], 10.0)         # bucket-0 group closes at t=10
        g9 = W.groups(self.ev, al, 900)
        self.assertEqual(len(set(g9)), 2)
        r9 = W.summarise("C", "C", 900, self.ev, self.p, g9, self.t,
                         W.first_alert_closed(self.ev, self.p, g9), "x")
        self.assertEqual(r9["n_alerts"], 2); self.assertEqual(r9["delay_median_s"], 400.0)
        a = W.summarise("A", "A", None, self.ev, self.p, np.arange(al.sum()), self.t,
                        W.first_alert_event(self.ev, self.p), "x")
        for m in ("f1_macro", "fpr", "fnr", "accuracy"):
            self.assertEqual(r[m], a[m])                    # same event decisions

    def test_label_free_grouping(self):
        al = self.p != "benign"
        g1 = W.groups(self.ev, al, 300); g2 = W.groups(self.ev.assign(label="benign"), al, 300)
        self.assertTrue(np.array_equal(g1, g2))

if __name__ == "__main__": unittest.main()
