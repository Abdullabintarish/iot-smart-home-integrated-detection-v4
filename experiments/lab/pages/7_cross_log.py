"""Page 7 - Cross-log correlation on unseen captures (supplementary)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import supp  # noqa: E402
import ui  # noqa: E402

ui.setup("Cross-Log Correlation",
         "Does linking Zeek connection logs, Zeek DNS logs and Suricata alerts "
         "improve detection on captures the model has never seen?", need_cache=False)
ui.banner(supp.PENDING)
ui.note("Scope: this tests correlation across <b>log types</b> made from the same "
        "packet capture. It does not test independent device, gateway and cloud "
        "sensors.")

XL = supp.XL
s4 = supp.jload(str(XL / "stage4_results.json"))
bs = supp.jload(str(XL / "stage4_bootstrap.json"))

# ---- Stage 3 -------------------------------------------------------------
st.subheader("Stage 3: new logs, label matching and linking")
rows = []
for c in supp.CAPTURES:
    d = supp.jload(str(XL / f"stage3_CTU-IoT-Malware-Capture-{c}.json"))
    m, lk = d["label_match"], d["linking"]
    rows.append({"Capture": c, "Role": "train" if c in supp.TRAIN else "test",
                 "Conn records": m["new_conn_records"],
                 "Label match": f"{m['match_rate_new']:.2%}",
                 "Labelled rows covered": f"{m['labelled_covered']:.1%}",
                 "DNS": lk["records"]["dns"], "Alerts": lk["records"]["alert"],
                 "Incidents": lk["incidents"],
                 "Cross-source incidents": lk["incidents_ge2_source_types"],
                 "Gate": "pass" if d["gate"]["pass"] else "fail"})
ui.table(pd.DataFrame(rows), thousands=True)
supp.src(XL / "stage3_CTU-IoT-Malware-Capture-<capture>.json")
ui.note("Pilot 8-1 failed the gate (no DNS, no alerts, so no cross-source "
        "incident). Fallback 20-1 passed, so Stage 4 went ahead. Zeek 9.0.1 and "
        "Suricata 7.0.3 with one fixed ET Open ruleset; Community ID in both.")

# ---- Stage 4 -------------------------------------------------------------
st.subheader("Stage 4: conditions A–D on the held-out captures")
sp = s4["split"]
c = st.columns(4)
c[0].metric("Training rows", ui.fmt(sp["train_rows"]))
c[1].metric("Test rows", ui.fmt(sp["test_rows"]))
c[2].metric("Test captures", ", ".join(x.split("-", 3)[-1] for x in sp["test"]))
c[3].metric("Seeds", len(s4["seeds"]))

per = []
summary = []
for k, r in s4["conditions"].items():
    S = r["by_seed"]
    for s in supp.SEEDS:
        per.append({"Condition": supp.COND_NAME[k], "Seed": s, "Macro F1": S[s]["macro_f1"]})
    mean = lambda key: sum(S[s][key] for s in supp.SEEDS) / len(supp.SEEDS)  # noqa: E731
    summary.append({"Condition": supp.COND_NAME[k],
                    "Macro F1": f"{r['macro_f1_mean']:.3f} ± {r['macro_f1_sd']:.3f}",
                    "Missed attacks (FNR)": f"{mean('fnr'):.1%}",
                    "False alarms (FPR)": f"{mean('fpr'):.2%}",
                    "FPR, unseen benign": f"{mean('fpr_unseen_benign'):.2%}",
                    "95% CI (seed 42)": "[{:.3f}, {:.3f}]".format(*bs[f"macro_f1_{k}"])})
ui.table(pd.DataFrame(summary))
supp.src(XL / "stage4_results.json", XL / "stage4_bootstrap.json")

per_df = pd.DataFrame(per)
st.markdown("**Macro F1 per seed** (each dot is one seed; the bar is the mean)")
bars = alt.Chart(per_df).mark_bar(opacity=0.35).encode(
    x=alt.X("Condition:N", sort=list(supp.COND_NAME.values()), title=None),
    y=alt.Y("mean(Macro F1):Q", title="Macro F1", scale=alt.Scale(domain=[0, 1])))
dots = alt.Chart(per_df).mark_circle(size=70).encode(
    x=alt.X("Condition:N", sort=list(supp.COND_NAME.values())),
    y="Macro F1:Q", tooltip=["Condition", "Seed", alt.Tooltip("Macro F1", format=".4f")])
st.altair_chart((bars + dots).properties(height=300), width="stretch")

st.markdown("**Paired difference against A**")
drows = []
for k in "BCD":
    diffs = [s4["conditions"][k]["by_seed"][s]["macro_f1"]
             - s4["conditions"]["A"]["by_seed"][s]["macro_f1"] for s in supp.SEEDS]
    drows.append({"Comparison": f"{k} − A",
                  "Per seed (42, 1, 2, 3, 4)": ", ".join(f"{d:+.3f}" for d in diffs),
                  "Bootstrap 95% (seed 42)": "[{:+.3f}, {:+.3f}]".format(*bs[f"diff_{k}_minus_A"])})
ui.table(pd.DataFrame(drows))
supp.src(XL / "stage4_results.json", XL / "stage4_bootstrap.json")

st.markdown("**Detection rate per true class** (benign: share kept benign; mean over seeds)")
classes = list(s4["conditions"]["A"]["by_seed"]["42"]["per_class_detection_rate"])
crows = []
for cl in classes:
    row = {"Class": cl, "Test rows": s4["conditions"]["A"]["by_seed"]["42"]
           ["per_class_detection_rate"][cl]["n"]}
    for k in "ABCD":
        S = s4["conditions"][k]["by_seed"]
        row[supp.COND_NAME[k]] = f"{sum(S[s]['per_class_detection_rate'][cl]['rate'] for s in supp.SEEDS) / 5:.3f}"
    crows.append(row)
ui.table(pd.DataFrame(crows), thousands=True)
supp.src(XL / "stage4_results.json")

st.subheader("Reading")
ui.note("On unseen captures every condition misses most attacks: training attacks "
        "are mostly port scans, test attacks mostly command-and-control. Within "
        "that, DNS context helps in every seed, and DNS plus alerts gives the "
        "largest gain in every seed. Alerts alone add nothing. Results vary strongly "
        "by seed, and the bootstrap covers seed 42 only.")

# ---- 34-1 follow-up --------------------------------------------------------
st.subheader("Follow-up: the 34-1 DDoS gap")
oz = supp.jload(str(XL / "old_zeek_check_34-1.json"))
z9, b26 = oz["results"]
ui.table(pd.DataFrame([
    {"": "Conn records", "IoT-23 log": oz["iot23_labelled_rows"],
     "Bro 2.6.4": b26["conn_records"], "Zeek 9.0.1": z9["conn_records"]},
    {"": "Rows identical to IoT-23", "IoT-23 log": "—",
     "Bro 2.6.4": b26["rows_identical_to_iot23"], "Zeek 9.0.1": z9["rows_identical_to_iot23"]},
    {"": "DDoS rows covered", "IoT-23 log": b26["per_class"]["dos"]["labelled"],
     "Bro 2.6.4": b26["per_class"]["dos"]["matched"], "Zeek 9.0.1": z9["per_class"]["dos"]["matched"]},
]).astype(str))
supp.src(XL / "old_zeek_check_34-1.json")
ui.note("IoT-23's log records each of the 14,159 packets of one DDoS flow as its own "
        "connection. Both Zeek versions record that flow as 6 connections, so the gap "
        "is not a Zeek-version effect. Only 237 of 14,394 DDoS rows enter the test set.")
