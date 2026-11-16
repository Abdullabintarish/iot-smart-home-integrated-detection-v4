"""Markdown tables for E3 RESULTS.md from results/*.csv and *.json.

    code/.venv/Scripts/python.exe -B experiments/v4_extension/e3/report_e3.py > experiments/v4_extension/e3/results/tables.md
"""
import json
from pathlib import Path

import pandas as pd

RES = Path(__file__).resolve().parent / "results"
ORDER = ["A/C", "B", "event_only", "event_plus_thin", "oracle", "none"]
NAME = {"A/C": "A/C fragmented", "B": "B integrated", "event_only": "event_only (s42)",
        "event_plus_thin": "event_plus_thin (s42)", "oracle": "oracle (not achievable)",
        "none": "no response"}
POL = {"P1_flow": "P1 flow", "P2_host": "P2 host"}


def pct(v, nd=2):
    return "–" if pd.isna(v) else f"{100 * v:.{nd}f}%"


def sec(v):
    return "–" if pd.isna(v) else f"{v:.1f}"


def sort(df):
    return df.assign(_o=df.trigger.map(ORDER.index)).sort_values(["policy", "_o"])


def main():
    r = pd.read_csv(RES / "response_all.csv", dtype={"duration": str})
    b = pd.read_csv(RES / "response_breakdown.csv", dtype={"duration": str})
    pc = pd.read_csv(RES / "response_per_capture.csv")
    boot = json.loads((RES / "bootstrap.json").read_text())
    wins = json.loads((RES / "per_capture_wins.json").read_text())

    print("## Main table (300 s block)\n")
    print("| Policy | Trigger | Attack prevented | Excl. DoS | Wrongly blocked | Benign hosts | "
          "Contained ≥90% | None blocked | Never blocked | Time to block median / p90 (s) | Block actions |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for x in sort(r[r.duration == "300"]).itertuples():
        print(f"| {POL[x.policy]} | {NAME[x.trigger]} | {pct(x.attack_prevented_share)} | "
              f"{pct(x.attack_prevented_share_excl_dos)} | {pct(x.benign_blocked_share)} "
              f"({x.benign_blocked:,}) | {x.benign_hosts_affected} | {x.incidents_contained_90:,} | "
              f"{x.incidents_none_blocked:,} | {x.incidents_never_blocked:,} | "
              f"{sec(x.time_to_block_median_s)} / {sec(x.time_to_block_p90_s)} | {x.block_actions:,} |")

    print("\n## All durations\n")
    print("| Policy | Trigger | Block | Attack prevented | Excl. DoS | Wrongly blocked | Benign hosts | "
          "Contained ≥90% | None blocked | Time to block median / p90 (s) | Starts / extensions |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    rr = r.assign(_o=r.trigger.map(ORDER.index),
                  _d=r.duration.map({"60": 0, "300": 1, "900": 2, "end": 3}))
    for x in rr.sort_values(["policy", "_o", "_d"]).itertuples():
        d = "end" if x.duration == "end" else f"{x.duration} s"
        print(f"| {POL[x.policy]} | {NAME[x.trigger]} | {d} | {pct(x.attack_prevented_share)} | "
              f"{pct(x.attack_prevented_share_excl_dos)} | {pct(x.benign_blocked_share)} | "
              f"{x.benign_hosts_affected} | {x.incidents_contained_90:,} | {x.incidents_none_blocked:,} | "
              f"{sec(x.time_to_block_median_s)} / {sec(x.time_to_block_p90_s)} | "
              f"{x.block_starts:,} / {x.block_extensions:,} |")

    s = b[b.duration == "300"]
    print("\n## Per class (300 s): attack events prevented\n")
    cls = ["c2", "dos", "malware", "recon"]
    n = s[(s.group == "class")].drop_duplicates("value").set_index("value")["events"]
    print("| Policy | Trigger | " + " | ".join(f"{c} (n={n[c]:,})" for c in cls) + " |")
    print("|---|---|" + "---|" * len(cls))
    for pol in POL:
        for t in ORDER:
            q = s[(s.policy == pol) & (s.trigger == t) & (s.group == "class")].set_index("value")
            print(f"| {POL[pol]} | {NAME[t]} | " + " | ".join(pct(q.loc[c, "share"]) for c in cls) + " |")

    print("\n## Per dataset (300 s)\n")
    cols = [("dataset_attack", "IoT-23"), ("dataset_attack", "Bot-IoT"),
            ("dataset_attack_excl_dos", "IoT-23"), ("dataset_attack_excl_dos", "Bot-IoT"),
            ("dataset_benign", "IoT-23"), ("dataset_benign", "Bot-IoT")]
    hdr = {"dataset_attack": "prevented", "dataset_attack_excl_dos": "prevented excl. DoS",
           "dataset_benign": "wrongly blocked"}
    nn = s.drop_duplicates(["group", "value"]).set_index(["group", "value"])["events"]
    print("| Policy | Trigger | " + " | ".join(f"{v} {hdr[g]} (n={nn[(g, v)]:,})" for g, v in cols) + " |")
    print("|---|---|" + "---|" * len(cols))
    for pol in POL:
        for t in ORDER:
            q = s[(s.policy == pol) & (s.trigger == t)].set_index(["group", "value"])
            print(f"| {POL[pol]} | {NAME[t]} | " + " | ".join(pct(q.loc[(g, v), "share"]) for g, v in cols) + " |")

    print("\n## Per capture (300 s): A/C vs B\n")
    print("| Capture | Attack / benign events | P1 prevented A/C vs B | P1 wrongly blocked A/C vs B | "
          "P2 prevented A/C vs B | P2 wrongly blocked A/C vs B |")
    print("|---|---|---|---|---|---|")
    for src in sorted(pc.source.unique()):
        q = pc[pc.source == src]
        g = lambda t, p, c: q[(q.trigger == t) & (q.policy == p)][c].iloc[0]
        print(f"| {src} | {g('A/C', 'P1_flow', 'attack_events'):,} / {g('A/C', 'P1_flow', 'benign_events'):,} | "
              + " | ".join(f"{pct(g('A/C', p, c), 1)} vs {pct(g('B', p, c), 1)}"
                           for p in POL for c in ("attack_prevented_share", "benign_blocked_share")) + " |")
    print("\n| Policy | Captures with attacks | A/C more / less / tie prevented | Captures with benign | "
          "A/C fewer / more / tie wrongly blocked |")
    print("|---|---|---|---|---|")
    for pol, w in wins.items():
        print(f"| {POL[pol]} | {w['captures_with_attacks']} | {w['AC_more_prevented']} / "
              f"{w['AC_less_prevented']} / {w['prevented_ties']} | {w['captures_with_benign']} | "
              f"{w['AC_fewer_wrongly_blocked']} / {w['AC_more_wrongly_blocked']} / {w['wrongly_blocked_ties']} |")

    print("\n## Bootstrap: A/C − B (300 s; 1,000 incident-clustered replicates, seed 42)\n")
    print("| Policy | Δ attack prevented [95% interval] | Δ wrongly blocked [95% interval] | "
          "Δ prevented excl. DoS [95% interval] |")
    print("|---|---|---|---|")
    f = lambda v, ci: f"{100 * v:+.2f} pp [{100 * ci[0]:+.2f}, {100 * ci[1]:+.2f}]"
    for pol, x in boot.items():
        print(f"| {POL[pol]} | {f(x['prevented_diff'], x['prevented_diff_ci'])} | "
              f"{f(x['wrongly_blocked_diff'], x['wrongly_blocked_diff_ci'])} | "
              f"{f(x['prevented_excl_dos_diff'], x['prevented_excl_dos_diff_ci'])} |")


if __name__ == "__main__":
    main()
