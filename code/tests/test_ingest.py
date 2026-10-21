"""Stage 1 reader tests: Zeek, Bot-IoT CSV, PCAP, labels, source naming."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pipeline import ingest
from pipeline.config import CLASSES
from pipeline.ingest import (_normalise_labels, _zeek_label, flows_from_csv,
                             flows_from_pcap, flows_from_zeek_log,
                             out_of_vocabulary, source_name)
from tests import fixtures as fx

CODE_DIR = Path(__file__).resolve().parent.parent


def _collect(gen) -> pd.DataFrame:
    return pd.concat(list(gen), ignore_index=True)


class _TmpCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()


class ZeekReaderTests(_TmpCase):
    def test_space_joined_tail(self) -> None:
        p = fx.write_zeek_spacejoined(
            self.tmp / "CTU-IoT-Malware-Capture-9-1" / "bro" / "conn.log.labeled")
        df = _collect(flows_from_zeek_log(p, "cap"))
        self.assertEqual(len(df), len(fx.ZEEK_CASES))
        self.assertEqual(df["label"].tolist(), [c[2] for c in fx.ZEEK_CASES])
        self.assertEqual(df.loc[0, "src_ip"], "192.168.1.10")
        self.assertEqual(df.loc[0, "dst_ip"], "10.0.0.1")
        self.assertEqual(df.loc[0, "proto"], "tcp")
        self.assertEqual(df.loc[0, "sport"], 40000)
        self.assertEqual(df.loc[0, "dport"], 80)
        self.assertAlmostEqual(df.loc[0, "ts"], 1547150789.5)
        for c in ("ts", "sport", "dport", "duration", "fwd_bytes", "bwd_pkts"):
            self.assertTrue(pd.api.types.is_numeric_dtype(df[c]), c)
        self.assertEqual(df.loc[0, "pkts"], 5)
        self.assertEqual(df.loc[0, "bytes"], 300)

    def test_det_label_and_unset_values(self) -> None:
        p = fx.write_zeek_det_label(self.tmp / "x" / "bro" / "conn.log.labeled")
        df = _collect(flows_from_zeek_log(p, "cap"))
        self.assertEqual(df["label"].tolist(), ["benign", "c2", "dos"])
        self.assertTrue(pd.isna(df.loc[0, "duration"]))
        self.assertTrue(pd.isna(df.loc[0, "fwd_bytes"]))
        self.assertEqual(df.loc[0, "app"], "(empty)")
        self.assertTrue(pd.api.types.is_numeric_dtype(df["duration"]))

    def test_headerless_uses_default_fields(self) -> None:
        p = fx.write_zeek_headerless(self.tmp / "conn.log.labeled")
        df = _collect(flows_from_zeek_log(p, "cap"))
        self.assertEqual(df["label"].tolist(), ["recon", "benign"])
        self.assertEqual(df.loc[1, "sport"], 40001)
        self.assertEqual(df.loc[1, "src_ip"], "192.168.1.10")


class BotIoTCsvTests(_TmpCase):
    def test_canonical_columns_ports_labels(self) -> None:
        p = fx.write_botiot_csv(self.tmp / "data_1.csv")
        df = _collect(flows_from_csv(p, "data_1"))
        for c in ("src_ip", "dst_ip", "proto", "sport", "dport", "ts", "ts_end",
                  "duration", "fwd_pkts", "bwd_pkts", "fwd_bytes", "bwd_bytes",
                  "label", "source", "subcategory"):
            self.assertIn(c, df.columns)
        self.assertEqual(df["label"].tolist(), [c[5] for c in fx.BOTIOT_CASES])
        for c in ("sport", "dport"):
            self.assertEqual(df[c].dtype, "float64", c)
        exp_s = [c[6] for c in fx.BOTIOT_CASES]
        exp_d = [c[7] for c in fx.BOTIOT_CASES]
        for got, exp in zip(df["sport"].tolist() + df["dport"].tolist(),
                            exp_s + exp_d):
            if exp is None:
                self.assertTrue(pd.isna(got))
            else:
                self.assertEqual(got, exp)
        self.assertAlmostEqual(df.loc[0, "ts"], 1526344122.0)
        self.assertEqual(df.loc[0, "src_ip"], "192.168.100.1")
        self.assertEqual(df.loc[5, "proto"], "arp")

    def test_ports_numeric_across_chunks(self) -> None:
        # The ICMP hex row lands in a different chunk from the decimal rows.
        p = fx.write_botiot_csv(self.tmp / "data_1.csv")
        for chunk in flows_from_csv(p, "data_1", chunksize=2):
            self.assertEqual(chunk["sport"].dtype, "float64")
            self.assertEqual(chunk["dport"].dtype, "float64")

    def test_missing_label_is_unknown_or_filename_fallback(self) -> None:
        hdr = fx.BOTIOT_HEADER
        good = fx._botiot_row(1, 1.0, "tcp", "1", "2", 1, "DoS", "TCP")
        blank = fx._botiot_row(2, 2.0, "tcp", "1", "2", 1, "", "")
        for name, fallback in (("data_2.csv", "unknown"),
                               ("mirai_flows.csv", "malware")):
            p = self.tmp / name
            p.write_text("\n".join([hdr, good, blank]) + "\n", encoding="utf-8")
            df = _collect(flows_from_csv(p, "s"))
            # Record label wins; the filename guess fills only the blank row.
            self.assertEqual(df["label"].tolist(), ["dos", fallback], name)

    def test_no_label_column_is_unknown(self) -> None:
        p = self.tmp / "flows.csv"
        p.write_text("saddr,daddr,proto\n1.1.1.1,2.2.2.2,tcp\n", encoding="utf-8")
        df = _collect(flows_from_csv(p, "s"))
        self.assertEqual(df["label"].tolist(), ["unknown"])


class LabelMappingTests(unittest.TestCase):
    def test_aliases(self) -> None:
        raw = ["Normal", "Reconnaissance", "DoS", "DDoS", "Theft", "Keylogging",
               "Data_Exfiltration", "OS_Fingerprint", "Service_Scan",
               " BENIGN ", "Theft-Intercepting"]
        exp = ["benign", "recon", "dos", "dos", "theft", "theft", "theft",
               "recon", "recon", "benign", "theft"]
        self.assertEqual(_normalise_labels(pd.Series(raw)).tolist(), exp)
        self.assertIn("theft", CLASSES)

    def test_ambiguous_subcategories_not_aliased(self) -> None:
        out = _normalise_labels(pd.Series(["TCP", "UDP", "HTTP"])).tolist()
        self.assertEqual(out, ["tcp", "udp", "http"])

    def test_missing_is_unknown(self) -> None:
        out = _normalise_labels(pd.Series(["Normal", None, "", "  "])).tolist()
        self.assertEqual(out, ["benign", "unknown", "unknown", "unknown"])

    def test_out_of_vocabulary(self) -> None:
        labels = ["benign", "dos", "unknown", "weird", "tcp", "weird"]
        self.assertEqual(out_of_vocabulary(labels), ["tcp", "weird"])
        self.assertEqual(out_of_vocabulary(["benign", "theft", "unknown"]), [])
        # value_counts().to_dict() keys are accepted too.
        self.assertEqual(out_of_vocabulary({"x": 3, "c2": 1}), ["x"])

    def test_zeek_precedence(self) -> None:
        # Mapped detailed label wins over everything.
        self.assertEqual(_zeek_label("Malicious", "C&C", "benign"), "c2")
        # Malicious + unmapped detailed: record says malware, not the filename.
        self.assertEqual(_zeek_label("Malicious", "NewThing", "c2"), "malware")
        self.assertEqual(_zeek_label("Malicious", "-", "recon"), "malware")
        self.assertEqual(_zeek_label("Benign", "-", "malware"), "benign")
        # No usable record label: fallback only if it is a real class.
        self.assertEqual(_zeek_label(None, None, "recon"), "recon")
        self.assertEqual(_zeek_label("-", "-", "unknown"), "unknown")
        self.assertEqual(_zeek_label("", "(empty)", ""), "unknown")
        self.assertEqual(_zeek_label("???", "-", "notaclass"), "unknown")


class PcapTests(_TmpCase):
    def test_bidirectional_flows(self) -> None:
        p, n_ip = fx.write_pcap(self.tmp / "t.pcap")
        df = _collect(flows_from_pcap(p, "t", "benign"))
        self.assertEqual(int(df["pkts"].sum()), n_ip)
        self.assertEqual(len(df), 2)
        tcp = df[df["proto"] == "tcp"].iloc[0]
        self.assertEqual((tcp["src_ip"], tcp["dst_ip"]), ("10.0.0.1", "10.0.0.2"))
        self.assertEqual((tcp["sport"], tcp["dport"]), (40000, 80))
        self.assertEqual((tcp["fwd_pkts"], tcp["bwd_pkts"]), (3, 2))
        self.assertEqual(tcp["fwd_bytes"] + tcp["bwd_bytes"], tcp["bytes"])
        self.assertTrue(tcp["fwd_flags"] & 0x02)          # SYN
        self.assertTrue(tcp["bwd_flags"] & 0x01)          # FIN
        self.assertEqual(tcp["app"], "http")
        self.assertAlmostEqual(tcp["duration"], 5.0)
        udp = df[df["proto"] == "udp"].iloc[0]
        self.assertEqual((udp["fwd_pkts"], udp["bwd_pkts"]), (2, 0))
        self.assertEqual(set(df["label"]), {"benign"})

    def test_eviction_loses_no_packets(self) -> None:
        p, n_ip = fx.write_pcap(self.tmp / "t.pcap")
        old = ingest.BUDGET.max_active_flows
        ingest.BUDGET.max_active_flows = 1
        try:
            df = _collect(flows_from_pcap(p, "t", "benign"))
        finally:
            ingest.BUDGET.max_active_flows = old
        self.assertEqual(int(df["pkts"].sum()), n_ip)
        self.assertEqual(int((df["fwd_pkts"] + df["bwd_pkts"]).sum()), n_ip)


class SourceNamingTests(unittest.TestCase):
    def test_capture_name(self) -> None:
        cap = Path("raw") / "CTU-IoT-Malware-Capture-3-1"
        self.assertEqual(source_name(cap / "bro" / "conn.log.labeled"),
                         "CTU-IoT-Malware-Capture-3-1")
        self.assertEqual(source_name(cap / "conn.log.labeled"),
                         "CTU-IoT-Malware-Capture-3-1")
        self.assertEqual(source_name(cap / "conn.log"),
                         "CTU-IoT-Malware-Capture-3-1")
        self.assertEqual(source_name(Path("raw") / "data_1.csv"), "data_1")


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, script, *args], cwd=CODE_DIR,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)


class ScriptTests(_TmpCase):
    def _clean_tree(self) -> Path:
        root = self.tmp / "raw"
        fx.write_zeek_spacejoined(root / "CTU-Fake-Capture-1-1" / "bro"
                                  / "conn.log.labeled")
        fx.write_zeek_det_label(root / "CTU-Fake-Capture-2-1"
                                / "conn.log.labeled")
        fx.write_botiot_csv(root / "data_1.csv")
        return root

    def test_check_sources_ok(self) -> None:
        r = _run("check_sources.py", str(self._clean_tree()))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ok = [l for l in r.stdout.splitlines() if l.strip().startswith("ok")]
        self.assertEqual(len(ok), 3, r.stdout)
        self.assertIn("CTU-Fake-Capture-1-1", r.stdout)
        self.assertIn("CTU-Fake-Capture-2-1", r.stdout)
        self.assertNotIn("WARN", r.stdout)

    def test_check_sources_warns_on_bad_labels(self) -> None:
        root = self.tmp / "raw"
        root.mkdir()
        hdr = fx.BOTIOT_HEADER
        rows = [fx._botiot_row(1, 1.0, "tcp", "1", "2", 1, "Weird", "X"),
                fx._botiot_row(2, 2.0, "tcp", "1", "2", 1, "", "")]
        (root / "data_9.csv").write_text("\n".join([hdr] + rows) + "\n",
                                         encoding="utf-8")
        r = _run("check_sources.py", str(root))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("WARN", r.stdout)
        self.assertIn("['weird']", r.stdout)
        self.assertIn("labelled 'unknown'", r.stdout)

    def test_stage1_reports_real_label_distribution(self) -> None:
        out = self.tmp / "shards"
        r = _run("stage1_collect.py", "--root", str(self._clean_tree()),
                 "--out", str(out))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("label=unknown", r.stdout)
        line = next(l for l in r.stdout.splitlines() if "Capture-2-1" in l)
        for part in ("benign=1", "c2=1", "dos=1"):
            self.assertIn(part, line)
        line = next(l for l in r.stdout.splitlines() if "data_1" in l)
        self.assertIn("benign=2", line)
        self.assertIn("recon=2", line)
        self.assertIn("theft=1", line)
        shards = sorted(out.glob("shard_*.parquet"))
        df = pd.concat([pd.read_parquet(s) for s in shards], ignore_index=True)
        self.assertEqual(len(df), len(fx.ZEEK_CASES) + 3 + len(fx.BOTIOT_CASES))
        self.assertEqual(set(df["source"]), {"CTU-Fake-Capture-1-1",
                                             "CTU-Fake-Capture-2-1", "data_1"})


if __name__ == "__main__":
    unittest.main()
