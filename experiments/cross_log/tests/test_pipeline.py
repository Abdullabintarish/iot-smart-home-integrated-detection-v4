import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import thesis_class  # noqa: E402
from community_id import community_id  # noqa: E402
import experiment  # noqa: E402
from features import (Preprocessor, alert_categories, alert_columns,  # noqa: E402
                      alert_features, conn_frame, dns_features)
from label_match import match  # noqa: E402
from linking import incident_summary, link, records  # noqa: E402

H = "192.168.1.5"


def conn_df(rows):
    cols = ["ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p",
            "proto", "service", "duration", "orig_bytes", "resp_bytes",
            "conn_state", "missed_bytes", "orig_pkts", "orig_ip_bytes",
            "resp_pkts", "resp_ip_bytes"]
    df = pd.DataFrame(rows, columns=cols)
    df["community_id"] = [community_id(a, b, p, int(x), int(y)) for a, b, p, x, y in
                          zip(df["id.orig_h"], df["id.resp_h"], df["proto"],
                              df["id.orig_p"], df["id.resp_p"])]
    return df


def row(ts, uid, dst, dport, proto="tcp", sport=40000):
    return [str(ts), uid, H, str(sport), dst, str(dport), proto, "-", "1.0",
            "10", "20", "SF", "0", "2", "100", "2", "120"]


class LabelMatchTest(unittest.TestCase):
    def test_one_to_one_closest(self):
        new = conn_df([row(100.0, "N1", "8.8.8.8", 53, "udp"),
                       row(100.4, "N2", "8.8.8.8", 53, "udp"),
                       row(500.0, "N3", "1.2.3.4", 80)])
        lab = new.drop(columns="community_id").copy()
        lab["ts"] = ["100.3", "100.0", "900.0"]   # third is outside tolerance
        lab["label"] = ["malicious", "benign", "benign"]
        lab["detailed_label"] = ["C&C", "-", "-"]
        out, st = match(new, lab)
        self.assertEqual(out["cls"].tolist()[:2], ["benign", "c2"])
        self.assertFalse(out["label_matched"].iloc[2])
        self.assertAlmostEqual(st["match_rate_new"], 2 / 3, places=5)

    def test_thesis_mapping(self):
        self.assertEqual(thesis_class("Malicious", "C&C-Torii"), "c2")
        self.assertEqual(thesis_class("Malicious", "DDoS"), "dos")
        self.assertEqual(thesis_class("Malicious", "PartOfAHorizontalPortScan"), "recon")
        self.assertEqual(thesis_class("Benign", "-"), "benign")


class LinkingTest(unittest.TestCase):
    def test_cid_first_then_host_window(self):
        conn = conn_df([row(10, "U1", "1.2.3.4", 80), row(50, "U2", "5.6.7.8", 443),
                        row(400, "U3", "1.2.3.4", 80, sport=41000)])
        dns = pd.DataFrame({"ts": ["9.5"], "uid": ["UD"], "id.orig_h": [H],
                            "id.resp_h": ["8.8.8.8"], "query": ["a.com"],
                            "rcode_name": ["NOERROR"]})
        # Alert at ts 320 belongs to U1's flow: stays with U1 (bucket 0), not bucket 1.
        alerts = pd.DataFrame({"ts": [320.0], "src_ip": ["1.2.3.4"], "dest_ip": [H],
                               "community_id": [conn["community_id"][0]],
                               "severity": [2], "category": ["Trojan"]})
        rec = link(records("cap", conn, dns, alerts))
        inc = rec.set_index("rid")["incident_id"]
        self.assertEqual(inc["conn:0"], inc["alert:0"])
        self.assertEqual(inc["conn:0"], inc["conn:1"])      # same host, same bucket
        self.assertNotEqual(inc["conn:0"], inc["conn:2"])   # next bucket
        self.assertEqual(inc["dns:0"], inc["conn:0"])        # host + window
        s = incident_summary(rec)
        self.assertEqual(s["incidents"], 2)
        self.assertEqual(s["incidents_ge2_source_types"], 1)
        self.assertEqual(s["flow_groups_linked_by_cid_ge2_types"], 1)


class FeatureTest(unittest.TestCase):
    def setUp(self):
        self.conn = conn_df([row(100, "U1", "1.2.3.4", 80), row(400, "U2", "1.2.3.4", 80),
                             row(1000, "U3", "1.2.3.4", 80)])
        self.dns = pd.DataFrame({
            "ts": ["90", "100", "101", "350"], "uid": list("abcd"),
            "id.orig_h": [H] * 4, "id.resp_h": ["8.8.8.8"] * 4,
            "query": ["x.com", "y.org", "z.net", "x.com"],
            "rcode_name": ["NOERROR", "NXDOMAIN", "NOERROR", "NOERROR"]})

    def test_dns_causal_window(self):
        f = dns_features(self.conn, self.dns)
        # conn@100 sees dns@90,@100 (not @101: in the future)
        self.assertEqual(f.loc[0, "dns_query_count"], 2)
        self.assertEqual(f.loc[0, "dns_nxdomain_count"], 1)
        self.assertEqual(f.loc[0, "dns_unique_domains"], 2)
        self.assertAlmostEqual(f.loc[0, "dns_mean_query_len"], 5.0)
        # conn@400 sees dns@101 and @350 (window [100, 400])
        self.assertEqual(f.loc[1, "dns_query_count"], 3)
        self.assertEqual(f.loc[2, "dns_query_count"], 0)

    def test_alert_causal_and_categories(self):
        al = pd.DataFrame({"ts": [99.0, 101.0, 300.0], "src_ip": [H, H, "1.2.3.4"],
                           "dest_ip": ["1.2.3.4", "1.2.3.4", H], "severity": [3, 1, 2],
                           "category": ["A", "B", "Z"]})
        cats = alert_categories(al.iloc[:2])
        f = alert_features(self.conn, al, cats)
        self.assertEqual(list(f.columns), alert_columns(cats))
        self.assertEqual(f.loc[0, "alert_count"], 1)          # only @99
        self.assertEqual(f.loc[0, "alert_max_severity"], 1)   # severity 3 -> score 1
        self.assertEqual(f.loc[1, "alert_count"], 2)          # @101, @300
        self.assertEqual(f.loc[1, "alert_max_severity"], 3)
        self.assertEqual(f.loc[1, "alert_cat_other"], 1)      # "Z" not in train vocab

    def test_preprocessor_fit_on_train_only(self):
        tr = conn_frame(self.conn.iloc[:2])
        te = conn_frame(self.conn.iloc[2:]).assign(proto="icmp")
        pre = Preprocessor().fit(tr, ["duration"], ["proto"])
        X = pre.transform(te)
        self.assertEqual(pre.columns, ["duration", "proto=tcp", "proto=__other__"])
        self.assertEqual(X[0].tolist(), [1.0, 0.0, 1.0])

    def test_forbidden_columns_rejected(self):
        with self.assertRaises(ValueError):
            experiment.check_no_forbidden(["duration", "id.orig_h"])
        for num, cat in experiment.condition_columns(["alert_count"]).values():
            experiment.check_no_forbidden(num + cat)


class ExperimentSmokeTest(unittest.TestCase):
    def test_run_and_bootstrap(self):
        rng = np.random.default_rng(0)
        n = 400
        df = pd.DataFrame({c: rng.random(n) for c in
                           experiment.condition_columns(["alert_count"])["D"][0]})
        df["y"] = (rng.random(n) < 0.4).astype(int)
        df["alert_count"] += df["y"] * 2
        for c in ("proto", "service", "conn_state"):
            df[c] = "x"
        df["cls"] = np.where(df["y"] == 1, "c2", "benign")
        df["incident_id"] = (np.arange(n) // 4).astype(str)
        df["capture"] = np.where(np.arange(n) < 300, "train_cap", "test_cap")
        tr, te = df[df.capture == "train_cap"], df[df.capture == "test_cap"]
        res, preds = experiment.run(tr, te, ["alert_count"], seeds=(42, 1))
        self.assertEqual(set(res["conditions"]), set("ABCD"))
        self.assertGreater(res["conditions"]["C"]["macro_f1_mean"],
                           res["conditions"]["A"]["macro_f1_mean"])
        bs = experiment.cluster_bootstrap(preds, reps=50)
        self.assertEqual(bs["clusters"], 25)
        lo, hi = bs["diff_C_minus_A"]
        self.assertLessEqual(lo, hi)


if __name__ == "__main__":
    unittest.main()
