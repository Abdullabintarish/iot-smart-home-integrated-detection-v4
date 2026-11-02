"""Stage 3 pilot: label match rate, linking and the Stage 4 gate for one capture.

    python run_stage3.py <capture_name>

Reads pcaps/<capture>/conn.log.labeled.server and
sensor_out/<capture>/{zeek/conn.log, zeek/dns.log, suricata/eve.json};
writes results/stage3_<capture>.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import common  # noqa: F401  (sets dont_write_bytecode before other imports)
from label_match import match
from linking import incident_summary, link, records
from zeek_io import read_eve, read_zeek_tsv

ROOT = Path(__file__).resolve().parents[1]
GATE_MATCH_RATE = 0.90


def load(capture: str):
    so = ROOT / "sensor_out" / capture
    conn = read_zeek_tsv(so / "zeek" / "conn.log")
    dns_path = so / "zeek" / "dns.log"
    dns = read_zeek_tsv(dns_path) if dns_path.exists() else None
    eve = read_eve(so / "suricata" / "eve.json", event_types=("alert",))
    lab = read_zeek_tsv(ROOT / "pcaps" / capture / "conn.log.labeled.server")
    return conn, dns, eve, lab


def main(capture: str) -> dict:
    conn, dns, alerts, lab = load(capture)
    import pandas as pd
    dns = dns if dns is not None else pd.DataFrame(columns=["ts", "uid", "id.orig_h", "id.resp_h"])
    labelled, mstats = match(conn, lab)
    rec = link(records(capture, labelled, dns, alerts))
    lstats = incident_summary(rec)
    m = labelled[labelled["label_matched"]]
    has_both = bool((m["cls"] == "benign").any() and (m["cls"] != "benign").any())
    gate = {
        "benign_and_attack_present": has_both,
        "match_rate_ge_0_90": bool((mstats["match_rate_new"] or 0) >= GATE_MATCH_RATE),
        "cross_source_incidents_exist": lstats["incidents_ge2_source_types"] > 0,
    }
    gate["pass"] = all(gate.values())
    out = {"capture": capture, "label_match": mstats, "linking": lstats,
           "alerts": {"n": int(len(alerts)),
                      "by_category": alerts["category"].value_counts().to_dict()
                      if len(alerts) else {}},
           "gate": gate}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / f"stage3_{capture}.json").write_text(json.dumps(out, indent=2))
    labelled.to_parquet(ROOT / "results" / f"conn_labelled_{capture}.parquet")
    rec.to_parquet(ROOT / "results" / f"records_linked_{capture}.parquet")
    print(json.dumps(out["gate"]), out["label_match"]["match_rate_new"],
          out["linking"]["incidents_ge2_source_types"])
    return out


if __name__ == "__main__":
    main(sys.argv[1])
