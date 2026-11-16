"""Unit tests for the E3 simulated response replay (hand-made events)."""
import sys, unittest
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run_response_sim as S

INF = np.inf


def frame():
    # replay order already (source, ts, event_id). Host a talks to b (flow 0) and c (flow 1).
    rows = [  # ts, src, dst, incident, label, pred_event, pred_incident
        (0,   "a", "b", "I1", "benign", "benign", "dos"),
        (10,  "a", "b", "I1", "dos",    "dos",    "dos"),
        (20,  "a", "b", "I1", "dos",    "benign", "dos"),
        (20,  "a", "b", "I1", "dos",    "benign", "dos"),    # tie: same ts, later event_id
        (100, "a", "c", "I2", "benign", "benign", "benign"),
        (400, "a", "b", "I3", "dos",    "benign", "benign"),
        (600, "a", "b", "I3", "dos",    "benign", "benign"),
        (50,  "x", "y", "I4", "recon",  "benign", "benign"),
    ]
    d = pd.DataFrame(rows, columns=["ts", "src_ip", "dst_ip", "incident_id", "label",
                                    "pred_event", "pred_inc"])
    d["source"] = "S"; d["proto"] = 6.0; d["event_id"] = range(len(d))
    d = d.sort_values(["source", "ts", "event_id"], kind="mergesort").reset_index(drop=True)
    for c in ("pred_fragmented", "pred_event_only", "pred_event_plus_thin"):
        d[c] = d["pred_event"]
    d["pred_integrated"] = d["pred_inc"]
    return d


def keys(d, pol):
    return S.key_codes(d, S.POLICIES[pol])


class Replay(unittest.TestCase):
    def setUp(self):
        self.d = frame()
        self.ts = self.d["ts"].to_numpy(float)
        self.pos = {e: i for i, e in enumerate(self.d["event_id"])}
        self.alert = S.event_trigger(self.d["pred_fragmented"])      # event_id 1 (t=10)

    def blocked_ids(self, sim):
        return set(self.d["event_id"][sim["blocked"]])

    def test_right_events_blocked_and_trigger_not_counted(self):
        sim = S.simulate(keys(self.d, "P1_flow"), self.ts, self.alert, 300.0)
        self.assertEqual(self.blocked_ids(sim), {2, 3})              # t=20 (incl. tie); not 1 itself
        self.assertEqual((sim["starts"], sim["extensions"]), (1, 0))

    def test_nothing_before_first_alert(self):
        sim = S.simulate(keys(self.d, "P1_flow"), self.ts, self.alert, INF)
        self.assertFalse(sim["blocked"][self.pos[0]])                # t=0 precedes the alert
        self.assertEqual(self.blocked_ids(sim), {2, 3, 5, 6})        # until end of capture
        none = S.simulate(keys(self.d, "P1_flow"), self.ts, np.empty(0, "int64"), INF)
        self.assertFalse(none["blocked"].any())

    def test_expiry_and_extension(self):
        sim = S.simulate(keys(self.d, "P1_flow"), self.ts, self.alert, 60.0)
        self.assertEqual(self.blocked_ids(sim), {2, 3})              # expires at 70 < 400
        sim = S.simulate(keys(self.d, "P1_flow"), self.ts, self.alert, 390.0)
        self.assertEqual(self.blocked_ids(sim), {2, 3})              # [10, 400): 400 not blocked
        two = np.array([self.pos[1], self.pos[5]])                   # second alert at t=400 extends
        sim = S.simulate(keys(self.d, "P1_flow"), self.ts, two, 300.0)
        self.assertEqual(self.blocked_ids(sim), {2, 3, 6})           # 600 < 400 + 300
        self.assertEqual((sim["starts"], sim["extensions"]), (2, 0))  # 400 - 10 >= 300: new start
        sim = S.simulate(keys(self.d, "P1_flow"), self.ts, two, 391.0)
        self.assertEqual((sim["starts"], sim["extensions"]), (1, 1))  # 400 - 10 < 391: extension

    def test_policies(self):
        f = S.simulate(keys(self.d, "P1_flow"), self.ts, self.alert, 300.0)
        h = S.simulate(keys(self.d, "P2_host"), self.ts, self.alert, 300.0)
        self.assertNotIn(4, self.blocked_ids(f))                     # other flow, same host
        self.assertIn(4, self.blocked_ids(h))                        # host quarantine
        self.assertNotIn(7, self.blocked_ids(h))                     # other host never

    def test_incident_trigger_at_last_event(self):
        b = S.incident_trigger(self.d["incident_id"].to_numpy(), self.d["pred_integrated"].to_numpy())
        self.assertEqual(list(self.d["event_id"][b]), [3])           # I1's last event (t=20)
        sim = S.simulate(keys(self.d, "P1_flow"), self.ts, b, 300.0)
        self.assertEqual(self.blocked_ids(sim), set())               # nothing on the flow in [20, 320)
        sim = S.simulate(keys(self.d, "P1_flow"), self.ts, b, 900.0)
        self.assertEqual(self.blocked_ids(sim), {5, 6})

    def test_labels_do_not_affect_blocking(self):
        t1 = S.triggers(self.d)
        rng = np.random.default_rng(0)
        d2 = self.d.assign(label=rng.permutation(self.d["label"].to_numpy()))
        t2 = S.triggers(d2)
        for name in ("A/C", "B", "event_only", "event_plus_thin", "none"):
            self.assertTrue(np.array_equal(t1[name], t2[name]), name)
        self.assertTrue(np.array_equal(S.grouped_trigger(self.d, self.d["pred_fragmented"].to_numpy()),
                                       t1["A/C"]))

    def test_scoring_and_time_to_block(self):
        tr = S.Truth(self.d)
        sim = S.simulate(keys(self.d, "P1_flow"), self.ts, self.alert, 300.0)
        r = S.score(tr, sim)
        self.assertEqual((r["attack_events"], r["attack_prevented"]), (6, 2))
        self.assertEqual((r["benign_events"], r["benign_blocked"]), (2, 0))
        self.assertEqual(r["attack_incidents"], 3)                   # I1, I3, I4
        self.assertEqual(r["incidents_eligible"], 2)                 # I1 (3 attack), I3 (2 attack)
        self.assertEqual(r["incidents_contained_90"], 1)             # I1: both later attacks blocked
        self.assertEqual(r["incidents_none_blocked"], 1)             # I3
        # I1: first attack t=10 raises its own alert -> 0 s; I3, I4: no later alert -> never
        self.assertEqual(r["incidents_with_block"], 1)
        self.assertEqual(r["time_to_block_median_s"], 0.0)
        b = S.incident_trigger(self.d["incident_id"].to_numpy(), self.d["pred_integrated"].to_numpy())
        r = S.score(tr, S.simulate(keys(self.d, "P1_flow"), self.ts, b, 300.0))
        self.assertEqual(r["time_to_block_median_s"], 10.0)          # alert at I1's end (t=20)
        h = S.simulate(keys(self.d, "P2_host"), self.ts, self.alert, 300.0)
        self.assertEqual(S.score(tr, h)["benign_hosts_affected"], 1)  # host a (event 4 blocked)


if __name__ == "__main__":
    unittest.main()
