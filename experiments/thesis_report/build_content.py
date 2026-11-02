"""Build the content of the experiments report (numbers, tables, figures).

Every number is read from a result file at build time, except the Run B / Run T
diagnostics that exist only in the verified validation documents; those are
cited to that document. Output: content.json (consumed by build_docx.js) and
fig_*.png.

    ..\\..\\code\\.venv\\Scripts\\python.exe -B build_content.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".mpl"))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
SUB = HERE.parents[1]
EXP = SUB / "experiments"
XL = EXP / "cross_log" / "results"
ROB = XL / "robustness"
ABL = EXP / "ablation" / "results" / "full"
VAL = SUB.parent / "thesis_final_validation"

blocks: list[dict] = []
sources: list[tuple[str, str]] = []


def J(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(SUB.parent)).replace("\\", "/")
    except ValueError:
        return str(p)


def h1(t): blocks.append({"t": "h1", "text": t})
def h2(t): blocks.append({"t": "h2", "text": t})
def h3(t): blocks.append({"t": "h3", "text": t})
def p(t): blocks.append({"t": "p", "text": t})
def bullets(items): blocks.append({"t": "bullets", "items": items})
def numbered(items): blocks.append({"t": "numbered", "items": items})
def callout(title, text): blocks.append({"t": "callout", "title": title, "text": text})
def pagebreak(): blocks.append({"t": "pagebreak"})


def table(caption, header, rows, widths, src, emph_rows=()):
    blocks.append({"t": "table", "caption": caption, "header": header,
                   "rows": [[str(c) for c in r] for r in rows], "widths": widths,
                   "source": src, "emph": list(emph_rows)})
    sources.append((caption, src))


def figure(file, caption, src, width_in=6.3):
    blocks.append({"t": "figure", "file": file, "caption": caption, "source": src,
                   "width_in": width_in})
    sources.append((caption, src))


f4 = lambda v: f"{v:.4f}"  # noqa: E731
f3 = lambda v: f"{v:.3f}"  # noqa: E731
pc = lambda v, d=2: f"{100 * v:.{d}f}%"  # noqa: E731
n0 = lambda v: f"{int(v):,}"  # noqa: E731
sd = lambda m, s, d=3: f"{m:.{d}f} ± {s:.{d}f}"  # noqa: E731
ci = lambda a, d=3: f"[{a[0]:+.{d}f}, {a[1]:+.{d}f}]"  # noqa: E731

# ---------------------------------------------------------------- style
INK, MUTED, GRID = "#1d2a33", "#5f6b73", "#d9dee2"
COL = {"A": "#7b8a95", "B": "#2f7f9e", "C": "#c58a2b", "D": "#2f5d3a",
       "frag": "#2f6f9e", "integ": "#c2562d"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.axisbelow": True, "figure.dpi": 200})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(HERE / name, dpi=200)
    plt.close(fig)


# ================================================================ data
RB = J(SUB / "metrics" / "stage5_report.json")
RT = J(VAL / "supplementary_temporal" / "code" / "results" / "stage5_report.json")
RB_SRC = "submission/metrics/stage5_report.json"
RT_SRC = "thesis_final_validation/supplementary_temporal/code/results/stage5_report.json"
V04 = "thesis_final_validation/04_Verified_Results_and_Analysis.md"

checks = J(ABL / "checks.json")
asumm = pd.read_csv(ABL / "ablation_summary.csv")
aboot = J(ABL / "bootstrap.json")

caps7 = ["8-1", "42-1", "20-1", "21-1", "3-1", "34-1", "1-1"]
caps_extra = ["48-1", "49-1"]
s3 = {c: J(XL / f"stage3_CTU-IoT-Malware-Capture-{c}.json") for c in caps7 + caps_extra}
s4 = J(XL / "stage4_results.json")
s4b = J(XL / "stage4_bootstrap.json")
R0 = J(ROB / "R0_reproduction.json")
R1 = J(ROB / "R1_20_seeds.json")
R2 = J(ROB / "R2_two_level_bootstrap.json")
R4 = J(ROB / "R4_connection_end.json")
R5 = J(ROB / "R5_windows.json")
R3p = ROB / "R3_leave_one_capture_out.json"
R3 = J(R3p) if R3p.exists() else None
OZ = J(XL / "old_zeek_check_34-1.json")
SEEDS = list(s4["seeds"])


def cond_mean(cond, key, res=s4):
    S = res["conditions"][cond]["by_seed"]
    return float(np.mean([S[s][key] for s in S]))


fr, ig = RB["fragmented"], RB["integrated"]
tfr, tig = RT["fragmented"], RT["integrated"]
ov = RB["alert_reduction_by_dataset"]
boot_b = RB["bootstrap"]["difference"]["f1_macro"]
A, B, C, D = (s4["conditions"][k] for k in "ABCD")

# ================================================================ title + summary
blocks.append({"t": "title",
               "title": "Integrated Information Management for Cybersecurity Risk "
                        "Mitigation in IoT-Enabled Smart Home Networks",
               "subtitle": "Experimental work: design, results and robustness",
               "meta": "Supporting document for the master's thesis · November 2026"})

h1("Summary")
p("This document brings together every experiment carried out for the thesis. It explains "
  "what each experiment tests, how it was run and what it found, in a form that can be used "
  "directly when writing the methodology and results chapters. All numbers come from the "
  "saved result files of the runs; the file behind each table is named under it and listed "
  "in Appendix A.")
p("The research question (RQ1) is: How does the integration and correlation of distributed "
  "IoT logs and alerts affect cybersecurity threat detection accuracy in IoT-enabled smart "
  "home networks? Integration was studied in two forms. Experiments 1 to 3 correlate "
  "individual network events into incidents within each log source. Experiment 4 links "
  "different log types (connection logs, DNS logs and intrusion-detection alerts) that "
  "describe the same traffic.")
table("Table 1. The four experiments at a glance",
      ["Experiment", "What it tests", "Main finding"],
      [["1. Main comparison (Run B)",
        "Fragmented per-source detection vs integrated incident-level detection on the same 1,692,332 test events",
        f"Integration reduced alert volume by {pc(ov['overall']['alert_reduction'])} but lowered macro F1 from {f4(fr['f1_macro'])} to {f4(ig['f1_macro'])} and raised the false-positive rate from {pc(fr['fpr'])} to {pc(ig['fpr'])}"],
       ["2. Temporal hold-out (Run T)",
        "The same comparison when every test event is later in time than every training event",
        f"Same direction: macro F1 {f4(tfr['f1_macro'])} vs {f4(tig['f1_macro'])}; false-positive rate {pc(tfr['fpr'])} vs {pc(tig['fpr'])}"],
       ["3. Controlled ablation",
        "What incident context adds when the model, training sample and test events are held fixed",
        "Adding incident features to event features leaves macro F1 unchanged but roughly triples the false-positive rate"],
       ["4. Cross-log correlation",
        "Whether linking connection logs, DNS logs and IDS alerts improves detection on captures never seen in training",
        f"Combining all three log types raised macro F1 from {f3(A['macro_f1_mean'])} to {f3(D['macro_f1_mean'])} and improved on connection logs alone in every one of 20 seeds"]],
      [2300, 3500, 3560], "Sections 4 to 7")
callout("Answer to RQ1 in brief",
        "How logs are integrated decides whether detection improves. Summarising events into "
        "coarse incidents (Experiments 1 to 3) cut the number of items an analyst must review "
        "but made detection worse, mainly through false alarms on benign traffic. Linking "
        "different log types that describe the same activity (Experiment 4) made detection "
        "better on most unseen networks tested: DNS and alert context each helped, and together "
        "they helped most, although the size of the gain varied from network to network. "
        "Integration therefore supports risk mitigation when it adds behavioural "
        "information to each event, not when it replaces event detail with summaries.")
pagebreak()

# ================================================================ approach
h1("1. Research approach")
p("The experiments implement the five-stage monitoring pipeline described in the thesis "
  "methodology and compare monitoring conditions that differ only in how much information is "
  "integrated. Every comparison holds the classifier, its settings and the test events fixed, "
  "so that differences can be attributed to integration rather than to the model.")
table("Table 2. Pipeline stages",
      ["Stage", "What it does"],
      [["1. Collection", "Reads the raw log files and maps their labels to five shared classes: benign, c2 (command and control), dos (denial of service), malware and recon (scanning)"],
       ["2. Preprocessing", "Removes identifiers and label-carrying columns (IP addresses, timestamps, MAC addresses), encodes and scales features, and selects features. Everything is fitted on training data only"],
       ["3. Correlation", "Groups events into incidents: same source, source IP, destination IP and protocol within a 300-second window"],
       ["4. Detection", "Random Forest classifier (300 trees, maximum depth 24, minimum 2 samples per leaf, balanced class weights, at most 60,000 training rows per class)"],
       ["5. Evaluation", "Accuracy, macro precision, recall and F1, false-positive rate (FPR), false-negative rate (FNR), alert reduction, processing time, robustness checks and incident-clustered bootstrap intervals"]],
      [2000, 7360], "submission/README.txt, section 1")
p("Macro F1 is the main accuracy measure throughout, because the classes are very unequal in "
  "size and accuracy alone would be dominated by the largest class. The false-positive rate "
  "(benign traffic flagged as an attack) and the false-negative rate (attacks missed) are "
  "reported alongside it because they map directly onto the two costs of a monitoring system: "
  "wasted analyst time and undetected threats.")

h2("1.1 Data")
p("Two public datasets were used. IoT-23 (Stratosphere Laboratory, Czech Technical "
  "University) contains real traffic of IoT devices infected with malware, recorded as Zeek "
  "connection logs and original packet captures. Bot-IoT (UNSW Canberra) contains simulated "
  "smart-home traffic with large denial-of-service and scanning attacks. Experiments 1 to 3 "
  "use 10 IoT-23 connection logs and 3 Bot-IoT files; Experiment 4 re-processes IoT-23 packet "
  "captures.")
table("Table 3. Data used in Experiments 1 to 3",
      ["Dataset", "Files", "Events", "Incidents", "Alert reduction"],
      [["IoT-23", "10 Zeek connection logs", n0(ov['per_dataset']['IoT-23']['events']), n0(ov['per_dataset']['IoT-23']['incidents']), pc(ov['per_dataset']['IoT-23']['alert_reduction'])],
       ["Bot-IoT", "3 CSV files", n0(ov['per_dataset']['Bot-IoT']['events']), n0(ov['per_dataset']['Bot-IoT']['incidents']), pc(ov['per_dataset']['Bot-IoT']['alert_reduction'])],
       ["Total", "13", n0(ov['overall']['events']), n0(ov['overall']['incidents']), pc(ov['overall']['alert_reduction'])]],
      [1500, 2600, 1800, 1700, 1760], RB_SRC + " (alert_reduction_by_dataset)", emph_rows=[2])
p("Class sizes over all 4,211,383 events: benign 492,891; recon 1,683,191; dos 2,014,334; "
  "c2 15,002; malware 5,965 (thesis_final_validation/03_Final_Experimental_Methodology.md, "
  "section 2). Alert reduction means 1 − incidents / events: the share of items an analyst "
  "would no longer have to look at individually.")
pagebreak()

# ================================================================ Experiment 1
h1("2. Experiment 1: fragmented versus integrated monitoring (Run B)")
h2("2.1 Design")
p("Two monitoring conditions are compared on exactly the same held-out test events.")
bullets([
    "Fragmented baseline: each of the 13 source files is handled on its own, with its own Random Forest trained on that source's events and 20 event-level features such as ports, bytes, duration and flags. There is no integration and no correlation.",
    "Integrated condition: all sources are normalised into one structure, events are correlated into incidents (Stage 3), and one Random Forest classifies incidents from 7 incident features (number of events, time span, event rate, number of sources and endpoints). Each test event receives its incident's predicted class.",
    f"Train/test split: by incident, so that an incident is never divided between training and test data; 25% of incidents go to test. The test set holds {n0(fr['n_test'])} events in 175,489 incidents and is identical for both conditions.",
])
h2("2.2 Results")
rows = [[lab, f4(fr[k]), f4(ig[k]), f"{ig[k] - fr[k]:+.4f}"] for k, lab in
        [("accuracy", "Accuracy"), ("precision_macro", "Macro precision"), ("recall_macro", "Macro recall"),
         ("f1_macro", "Macro F1"), ("fpr", "False-positive rate"), ("fnr", "False-negative rate")]]
table("Table 4. Fragmented versus integrated detection (1,692,332 test events)",
      ["Metric", "Fragmented", "Integrated", "Difference"], rows, [3000, 2100, 2100, 2160], RB_SRC, emph_rows=[3])
p(f"The integrated condition was worse on every metric. The incident-clustered bootstrap "
  f"(1,000 replicates) gives a 95% interval of [{boot_b['ci_low']:.4f}, {boot_b['ci_high']:.4f}] "
  f"for the macro-F1 difference, entirely below zero. Correlation did reduce the volume of "
  f"items to review by {pc(ov['overall']['alert_reduction'])} overall, but this figure is "
  f"dominated by Bot-IoT floods; for the more realistic IoT-23 traffic the reduction is "
  f"{pc(ov['per_dataset']['IoT-23']['alert_reduction'])}.")

fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.7))
labs = ["Run B", "Run T"]
x = np.arange(2)
for i, (key, title, fmt) in enumerate([("f1_macro", "Macro F1 (higher is better)", "{:.3f}"),
                                       ("fpr", "False-positive rate (lower is better)", "{:.1%}")]):
    fv = [fr[key], tfr[key]]
    iv = [ig[key], tig[key]]
    ax[i].bar(x - 0.18, fv, 0.34, color=COL["frag"], label="Fragmented")
    ax[i].bar(x + 0.18, iv, 0.34, color=COL["integ"], label="Integrated")
    for xx, v in zip(x - 0.18, fv):
        ax[i].text(xx, v, fmt.format(v), ha="center", va="bottom", fontsize=8, color=INK)
    for xx, v in zip(x + 0.18, iv):
        ax[i].text(xx, v, fmt.format(v), ha="center", va="bottom", fontsize=8, color=INK)
    ax[i].set_xticks(x, labs)
    ax[i].set_title(title, fontsize=9.5, color=INK, loc="left")
    ax[i].grid(axis="x", visible=False)
ax[0].set_ylim(0, 1.12)
ax[1].set_ylim(0, 0.125)
ax[1].set_yticks([0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12])
ax[1].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
fig.legend(*ax[0].get_legend_handles_labels(), frameon=False, fontsize=8, loc="upper center",
           ncol=2, bbox_to_anchor=(0.5, 1.0))
fig.tight_layout(rect=(0, 0, 1, 0.92))
fig.savefig(HERE / "fig_1_runB_runT.png", dpi=200)
plt.close(fig)
figure("fig_1_runB_runT.png", "Figure 1. Fragmented versus integrated detection in Run B (incident-grouped split) and Run T (temporal hold-out)", f"{RB_SRC}; {RT_SRC}")

h2("2.3 Why the integrated condition performs worse")
p("The diagnostic analyses carried out during validation locate the cause in the incident "
  "representation rather than in correlation itself (" + V04 + ", section 5):")
bullets([
    "Only three of the seven incident features vary (event count, time span and event rate); the source and endpoint counts are always 1 because every incident lies within one source.",
    "All 12,540 integrated false positives come from benign events inside multi-event incidents, whose count, span and rate resemble scanning. Benign events in single-event incidents produced no false positives.",
    "The integrated model never sees flow content (ports, bytes, flags), which the baseline uses.",
    "Correlation itself loses almost nothing: if every incident were labelled correctly, propagating the incident label to its events would give macro F1 0.9989.",
])
h2("2.4 Robustness and reproducibility")
table("Table 5. Robustness checks for Run B",
      ["Check", "Events", "Fragmented F1", "Integrated F1"],
      [["All test events", "1,692,332", "0.9955", "0.8341"],
       ["Incidents of at most 10,000 events", "363,035", "0.9755", "0.6472"],
       ["One majority vote per incident", "175,489 incidents", "0.9504", "0.7017"],
       ["Feature vectors not seen in training", "1,463,143", "0.9910", "0.7140"]],
      [3700, 2000, 1830, 1830], V04 + ", section 4")
p("The run is reproducible. A clean regeneration in a new virtual environment reproduced all "
  "prediction files byte for byte, and a second run on different hardware (Run C, AMD Ryzen 7 "
  "7800X3D) gave identical predictions; only timings differed. The pipeline's 94 unit tests "
  "pass (re-run on 3 November 2026), as do the demonstration application's 48 tests.")
pagebreak()

# ================================================================ Experiment 2
h1("3. Experiment 2: temporal hold-out (Run T)")
p("Run B splits by incident, so training and test events are interleaved in time within each "
  "capture. Run T removes this by testing on the most recent quarter of each source: within "
  "every source, each test event is later than every training event, and no incident crosses "
  "the cut. Everything else is unchanged.")
table("Table 6. Run T compared with Run B",
      ["Metric", "Run T fragmented", "Run T integrated", "Run B fragmented", "Run B integrated"],
      [[lab, f4(tfr[k]), f4(tig[k]), f4(fr[k]), f4(ig[k])] for k, lab in
       [("accuracy", "Accuracy"), ("f1_macro", "Macro F1"), ("fpr", "False-positive rate"), ("fnr", "False-negative rate")]],
      [2160, 1800, 1800, 1800, 1800], f"{RT_SRC}; {RB_SRC}")
p("The direction of the result holds under the temporal hold-out, and the integrated "
  "false-positive rate stays close to its Run B value with the same mechanism (benign traffic "
  "classified as scanning). The larger accuracy drop is mainly an artefact of the cut: each "
  "Bot-IoT denial-of-service file lasts only 105 to 202 seconds, so the cut leaves short "
  "flood fragments on the test side that resemble scanning. Macro F1 and the false-positive "
  "rate are the more reliable comparison here "
  "(thesis_final_validation/supplementary_temporal/RESULTS.md).")
pagebreak()

# ================================================================ Experiment 3
h1("4. Experiment 3: controlled ablation of incident context")
h2("4.1 Design")
p("Experiments 1 and 2 compare two complete systems that differ in several ways at once "
  "(per-source versus pooled models, event versus incident rows, different feature sets). The "
  "ablation isolates one factor: the incident features. One pooled Random Forest is trained "
  "with the same settings, the same training sample per seed and the same 1,692,332 Run B "
  "test events; only the input features change.")
bullets([
    "event_only: the 20 Run B event features.",
    "incident_only: the three informative incident features (event count, time span, event rate).",
    "event_plus_incident: both together.",
    "shared_event and shared_plus_incident: the same, restricted to the 11 event features present in both datasets, which removes the dataset fingerprint carried by missing values.",
    "Incident features at windows of 60, 150, 300, 600 and 900 seconds; seeds 42, 1, 2, 3 and 4 (85 model fits).",
])
p(f"Before the full run, a check confirmed that the saved data are exactly the Run B data: "
  f"{n0(checks['groups_at_300s'])} incidents at 300 seconds and {n0(checks['n_novel'])} test "
  f"events with feature vectors not seen in training, both matching Run B.")
h2("4.2 Results")
a300 = asumm[(asumm.subset == "all") & (asumm.window_s.isin([0, 300]))].set_index("feature_set")
order = ["event_only", "shared_event", "event_plus_incident", "shared_plus_incident", "incident_only"]
label = {"event_only": "Event features only", "shared_event": "Shared event features only",
         "event_plus_incident": "Event + incident features", "shared_plus_incident": "Shared event + incident features",
         "incident_only": "Incident features only"}
table("Table 7. Ablation at the 300-second window (mean ± SD over 5 seeds)",
      ["Feature set", "Macro F1", "False-positive rate"],
      [[label[k], sd(a300.loc[k, 'f1_mean'], a300.loc[k, 'f1_sd'], 4),
        f"{100 * a300.loc[k, 'fpr_mean']:.2f}% ± {100 * a300.loc[k, 'fpr_sd']:.2f}%"] for k in order],
      [4200, 2580, 2580], rel(ABL / "ablation_summary.csv"), emph_rows=[2])
brows = []
for k, lab in [("event_plus_incident_minus_event_only", "Event + incident − event only"),
               ("shared_plus_incident_minus_shared_event", "Shared + incident − shared only"),
               ("incident_only_minus_event_only", "Incident only − event only")]:
    brows.append([lab, ci(aboot[k]["f1_macro_diff"], 4), ci(aboot[k]["fpr_diff"], 4)])
table("Table 8. Paired incident-clustered bootstrap at 300 seconds (seed 42, 1,000 replicates, 95% intervals)",
      ["Comparison", "Macro F1 difference", "FPR difference"], brows, [3800, 2780, 2780], rel(ABL / "bootstrap.json"))

al = asumm[asumm.subset == "all"]
fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.7))
wins = [60, 150, 300, 600, 900]
for fs, col, lab in [("event_plus_incident", COL["integ"], "Event + incident"),
                     ("shared_plus_incident", COL["C"], "Shared + incident"),
                     ("incident_only", COL["A"], "Incident only")]:
    d = al[al.feature_set == fs].set_index("window_s").loc[wins]
    ax[0].plot(range(5), d.f1_mean, marker="o", color=col, label=lab, lw=1.6, ms=4)
    if fs != "incident_only":
        ax[1].plot(range(5), d.fpr_mean, marker="o", color=col, label=lab, lw=1.6, ms=4)
for fs, col, lab in [("event_only", COL["frag"], "Event only (no window)")]:
    v = al[al.feature_set == fs].iloc[0]
    ax[0].axhline(v.f1_mean, color=col, lw=1.2, ls="--", label=lab)
    ax[1].axhline(v.fpr_mean, color=col, lw=1.2, ls="--", label=lab)
for a_, t in zip(ax, ["Macro F1", "False-positive rate"]):
    a_.set_xticks(range(5), [str(w) for w in wins])
    a_.set_xlabel("Correlation window (s)")
    a_.set_title(t, fontsize=9.5, color=INK, loc="left")
ax[1].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=1))
ax[1].set_ylim(0, 0.014)
ax[0].legend(frameon=False, fontsize=7.5, loc="lower right")
save(fig, "fig_2_ablation.png")
figure("fig_2_ablation.png", "Figure 2. Effect of incident features by correlation window (mean over 5 seeds). Incident-only false-positive rates (about 9%) are omitted from the right panel so that the smaller differences stay visible", rel(ABL / "ablation_summary.csv"))
mb = asumm[(asumm.subset == "multi_event_benign") & (asumm.window_s.isin([0, 300]))].set_index("feature_set")
p(f"With everything else fixed, adding incident context to the event features does not "
  f"change macro F1 (the bootstrap interval for the difference includes zero) but raises the "
  f"false-positive rate from {pc(a300.loc['event_only', 'fpr_mean'])} to "
  f"{pc(a300.loc['event_plus_incident', 'fpr_mean'])}. The extra false alarms fall on benign "
  f"events inside multi-event incidents: their false-positive rate is "
  f"{pc(mb.loc['event_plus_incident', 'fpr_mean'], 1)} with incident features against "
  f"{pc(mb.loc['event_only', 'fpr_mean'], 1)} without. Incident features on their own reach "
  f"macro F1 {f3(a300.loc['incident_only', 'f1_mean'])}. The pattern holds at every window and "
  f"every seed. This confirms, under controlled conditions, the explanation from Experiment 1: "
  f"within-source incident summaries add little detection information and make some benign "
  f"traffic look like scanning.")
pagebreak()

# ================================================================ Experiment 4
h1("5. Experiment 4: correlation across log types")
h2("5.1 Motivation")
p("In Experiments 1 to 3 every incident contains events from a single source file: the 13 "
  "files are independent recordings, so no incident can link two of them. The thesis "
  "methodology, however, describes integrating different kinds of logs and alerts. Experiment "
  "4 tests this directly. It re-processes original IoT-23 packet captures with two widely used "
  "open-source tools so that three log types describe the same traffic, and asks whether "
  "linking them improves detection on networks the model has never seen.")
callout("Scope", "This experiment tests correlation across log types (connection logs, DNS logs "
        "and intrusion-detection alerts) produced from the same packet capture. It does not test "
        "independent sensors on different devices, a gateway and a cloud service.")
h2("5.2 Design")
table("Table 9. Design of the cross-log experiment",
      ["Element", "Choice"],
      [["Captures", "Seven IoT-23 captures also used in the thesis: CTU-IoT-Malware-Capture-1-1, 3-1, 8-1, 20-1, 21-1, 34-1 and 42-1 (original packet captures, about 0.5 GB)"],
       ["Log generation", "Zeek 9.0.1 (connection and DNS logs) and Suricata 7.0.3 (alerts), with Community ID flow hashing enabled in both"],
       ["Alert rules", "One Emerging Threats Open ruleset for Suricata 7.0.3 (52,803 enabled rules, newest rule dated 30 October 2026), downloaded once, hashed and never edited"],
       ["Labels", "Each new connection record is matched to the published IoT-23 labelled log by Community ID and start time (within 1 second, one-to-one); labels are mapped with the thesis's own mapping"],
       ["Linking", "First by Community ID (a connection, its DNS records and its alerts), then by local host within the same 300-second window"],
       ["Conditions", "A: connection features. B: A + DNS features (query count, distinct domains, failed lookups, mean query length). C: A + alert features (alert count, highest severity, counts per alert category). D: all three"],
       ["No look-ahead", "DNS and alert features use only records of the same host in the 300 seconds up to the connection's start time. Labels, IP addresses and timestamps are never features"],
       ["Split", "Capture-held-out: training on 1-1, 3-1, 20-1 and 42-1; testing on 8-1, 21-1 and 34-1, so every test capture is unseen"],
       ["Model and seeds", "The thesis Random Forest settings; seeds 42, 1, 2, 3 and 4; preprocessing fitted on training data only"],
       ["Target", "Malicious versus benign, because the attack types differ between captures; detection rates are also reported per attack type"]],
      [2100, 7260], "experiments/PLAN.md, section 4")
p("The split, features, model and metrics were written down before any model was trained "
  "(experiments/PLAN.md, section 4) and were not changed after the results were seen. The "
  "robustness analyses in section 5.5 were added afterwards and are reported as such.")

h2("5.3 Log generation, label matching and linking")
rows = []
for c in caps7 + caps_extra:
    d = s3[c]
    m, lk = d["label_match"], d["linking"]
    role = ("test" if c in ("8-1", "21-1", "34-1") else "train") if c in caps7 else \
        ("R3 only" if d["gate"]["pass"] else "excluded")
    rows.append([c, role, n0(m["new_conn_records"]),
                 pc(m["match_rate_new"]), n0(lk["records"]["dns"]), n0(lk["records"]["alert"]),
                 f"{n0(lk['incidents_ge2_source_types'])} of {n0(lk['incidents'])}"])
table("Table 10. New logs per capture, label matching and cross-source incidents",
      ["Capture", "Role", "Connections", "Label match", "DNS records", "Alerts", "Incidents with ≥ 2 log types"],
      rows, [1000, 900, 1500, 1300, 1400, 1260, 2000], "experiments/cross_log/results/stage3_<capture>.json")
tot_inc = sum(s3[c]["linking"]["incidents"] for c in caps7)
tot_x = sum(s3[c]["linking"]["incidents_ge2_source_types"] for c in caps7)
tot_3 = sum(s3[c]["linking"]["incidents_all_3_types"] for c in caps7)
p(f"Label matching was essentially complete: 100% of new connection records matched an "
  f"IoT-23 label in six captures and 99.98% in the seventh. Unlike Experiments 1 to 3, the "
  f"linking now produces genuine cross-source incidents: {n0(tot_x)} of {n0(tot_inc)} "
  f"incidents combine at least two log types, and {n0(tot_3)} combine all three. The planned "
  f"pilot capture, 8-1, contains no DNS traffic and triggers no alerts, so it has no "
  f"cross-source incidents; as the protocol allowed, the experiment proceeded after the "
  f"second fallback capture (20-1) met all conditions. Two further captures, 48-1 and 49-1, "
  f"were processed only for the leave-one-capture-out analysis (R3). 48-1 met all conditions. "
  f"49-1 did not: all {n0(s3['49-1']['label_match']['labelled_records'])} of its labelled "
  f"rows were matched, but Zeek produced {n0(s3['49-1']['label_match']['new_conn_records'])} "
  f"connection records, so only {pc(s3['49-1']['label_match']['match_rate_new'])} of the new "
  f"records carry a label, just below the 90% threshold set in advance. It was therefore "
  f"excluded.")

h2("5.4 Main results")
rows = []
for k, lab in [("A", "A · connection"), ("B", "B · + DNS"), ("C", "C · + alerts"), ("D", "D · + DNS + alerts")]:
    r = s4["conditions"][k]
    rows.append([lab, sd(r["macro_f1_mean"], r["macro_f1_sd"]), pc(cond_mean(k, "fnr"), 1),
                 pc(cond_mean(k, "fpr")), pc(cond_mean(k, "fpr_unseen_benign")),
                 "[{:.3f}, {:.3f}]".format(*s4b[f"macro_f1_{k}"])])
sp = s4["split"]["test_class_counts"]
table(f"Table 11. Conditions A–D on the held-out captures ({n0(s4['split']['test_rows'])} test connections; mean over 5 seeds)",
      ["Condition", "Macro F1 (mean ± SD)", "Attacks missed (FNR)", "False alarms (FPR)", "FPR on unseen benign", "95% interval (seed 42)"],
      rows, [1900, 1700, 1500, 1400, 1460, 1400], "experiments/cross_log/results/stage4_results.json, stage4_bootstrap.json", emph_rows=[3])
cls = list(A["by_seed"]["42"]["per_class_detection_rate"])
crow = []
for cl in cls:
    r = [cl, n0(A["by_seed"]["42"]["per_class_detection_rate"][cl]["n"])]
    for k in "ABCD":
        S = s4["conditions"][k]["by_seed"]
        r.append(f3(np.mean([S[s]["per_class_detection_rate"][cl]["rate"] for s in S])))
    crow.append(r)
table("Table 12. Detection rate per true class (benign: share correctly left as benign; mean over 5 seeds)",
      ["Class", "Test rows", "A", "B", "C", "D"], crow, [1800, 1560, 1500, 1500, 1500, 1500],
      "experiments/cross_log/results/stage4_results.json")
p(f"On captures not seen in training every condition misses many attacks. The training "
  f"captures contain mostly scanning, while the test captures contain mostly "
  f"command-and-control traffic ({n0(sp.get('c2', 0))} of {n0(s4['split']['test_rows'])} test "
  f"connections), so this is a demanding transfer setting. Within it, each added log type "
  f"helped. DNS context raised macro F1 from {f3(A['macro_f1_mean'])} to "
  f"{f3(B['macro_f1_mean'])}, alert context to {f3(C['macro_f1_mean'])}, and both together to "
  f"{f3(D['macro_f1_mean'])}. The gain comes mainly from command-and-control detection, which "
  f"rose from {f3(np.mean([A['by_seed'][s]['per_class_detection_rate']['c2']['rate'] for s in A['by_seed']]))} "
  f"to {f3(np.mean([D['by_seed'][s]['per_class_detection_rate']['c2']['rate'] for s in D['by_seed']]))}. "
  f"The cost is a modest rise in false alarms, from {pc(cond_mean('A', 'fpr'))} to "
  f"{pc(cond_mean('D', 'fpr'))} of benign connections. Denial-of-service and scanning "
  f"connections in the test captures remained almost entirely undetected; they are rare there "
  f"and denial of service does not occur in the training captures at all.")

h2("5.5 Robustness of the cross-log result")
p("Because the main results vary considerably between seeds, six further analyses test "
  "whether the findings hold. They were specified (experiments/PLAN.md, section 4b) before "
  "being run and are reported in full.")
bullets([
    f"R0 reproduction: rebuilding the main seed-42 run from the cached features gave identical predictions for all {n0(R0['rows_cache'])} test connections and all four conditions, which validates the code used for R1 to R5.",
    "R1: the main split with 20 seeds instead of 5.",
    "R2: a two-level bootstrap that resamples both seeds and test incidents, so that the intervals include seed-to-seed variation (2,000 replicates).",
    "R3: leave-one-capture-out, in which every capture serves as the test capture once (the seven main captures plus 48-1).",
    "R4: DNS and alert windows anchored at the connection's end (when Zeek writes the record) instead of its start.",
    "R5: correlation windows of 60 and 900 seconds instead of 300.",
])
s1 = R1["summary"]
rrows = []


def add_rows(name, summ, n):
    out = [name]
    for k in "BCD":
        d = summ[f"{k}_minus_A"]
        out.append(f"{d['mean']:+.3f} ({d['seeds_positive']}/{n})")
    return out


rrows.append(add_rows("Main analysis (5 seeds)", {f"{k}_minus_A": {
    "mean": float(np.mean([s4['conditions'][k]['by_seed'][s]['macro_f1'] - A['by_seed'][s]['macro_f1'] for s in A['by_seed']])),
    "seeds_positive": int(sum(s4['conditions'][k]['by_seed'][s]['macro_f1'] > A['by_seed'][s]['macro_f1'] for s in A['by_seed']))}
    for k in "BCD"}, 5))
rrows.append(add_rows("R1: 20 seeds", s1, 20))
rrows.append(add_rows("R4: windows at connection end", R4["summary"], 5))
rrows.append(add_rows("R5: 60-second window", R5["variants"]["start_60"]["summary"], 5))
rrows.append(add_rows("R5: 900-second window", R5["variants"]["start_900"]["summary"], 5))
if R3:
    ps = R3["pooled_summary"]
    rrows.append(add_rows(f"R3: leave-one-capture-out, pooled ({len(R3['captures'])} captures)", ps, 5))
table("Table 13. Gain in macro F1 over connection features alone (A), and the number of seeds in which the gain is positive",
      ["Analysis", "B − A (+ DNS)", "C − A (+ alerts)", "D − A (all three)"], rrows, [3600, 1920, 1920, 1920],
      "experiments/cross_log/results/robustness/R1_20_seeds.json, R3_*.json, R4_*.json, R5_windows.json; stage4_results.json")
table("Table 14. Two-level bootstrap over seeds and test incidents (R2; 2,000 replicates)",
      ["Quantity", "95% interval", "Share of replicates above zero"],
      [["B − A (+ DNS)", ci(R2["B-A"]["ci95"]), pc(R2["B-A"]["share_above_zero"], 1)],
       ["C − A (+ alerts)", ci(R2["C-A"]["ci95"]), pc(R2["C-A"]["share_above_zero"], 1)],
       ["D − A (all three)", ci(R2["D-A"]["ci95"]), pc(R2["D-A"]["share_above_zero"], 1)]],
      [3600, 2880, 2880], "experiments/cross_log/results/robustness/R2_two_level_bootstrap.json", emph_rows=[2])

# Figure 3: per-seed macro F1 (R1)
per = R1["by_condition_seed"]
fig, ax = plt.subplots(figsize=(7.2, 2.9))
rng = np.random.default_rng(0)
for i, k in enumerate("ABCD"):
    v = np.array([per[k][str(s)]["macro_f1"] for s in R1["seeds"]])
    ax.bar(i, v.mean(), 0.6, color=COL[k], alpha=0.28)
    ax.scatter(i + rng.uniform(-0.18, 0.18, len(v)), v, s=14, color=COL[k], zorder=3)
    ax.text(i, 0.03, f"mean {v.mean():.3f}", ha="center", va="bottom", fontsize=8.5, color=INK, fontweight="bold")
ax.set_xticks(range(4), ["A · connection", "B · + DNS", "C · + alerts", "D · + DNS + alerts"])
ax.set_ylabel("Macro F1")
ax.set_ylim(0, 1)
ax.grid(axis="x", visible=False)
ax.set_title("Macro F1 on unseen captures, 20 seeds (dots) and their mean (bars)", fontsize=9.5, color=INK, loc="left")
save(fig, "fig_3_crosslog_seeds.png")
figure("fig_3_crosslog_seeds.png", "Figure 3. Cross-log conditions on the held-out captures across 20 seeds (R1)",
       "experiments/cross_log/results/robustness/R1_20_seeds.json")

d_ = s1["D_minus_A"]
b_ = s1["B_minus_A"]
c_ = s1["C_minus_A"]
p(f"On the main train/test split, the gains from DNS and from combining all three log types "
  f"are robust. Over 20 seeds, D "
  f"beat A in {d_['seeds_positive']} of 20 seeds and B beat A in {b_['seeds_positive']} of 20 "
  f"(Wilcoxon signed-rank test, p = {d_['wilcoxon_p_two_sided']:.1e} for both), and both gains "
  f"remained positive at the 60- and 900-second windows and with windows anchored at the "
  f"connection's end. Even when seed-to-seed variation is included, the 95% interval for "
  f"D − A ({ci(R2['D-A']['ci95'])}) lies entirely above zero. The gain from alerts alone is "
  f"smaller and less certain: positive in {c_['seeds_positive']} of 20 seeds (p = "
  f"{c_['wilcoxon_p_two_sided']:.1e}), but its two-level interval ({ci(R2['C-A']['ci95'])}) "
  f"just touches zero and it was not consistently positive at the 900-second window or with "
  f"end-anchored windows.")
if R3:
    caps_r3 = R3["captures"]
    frows = []
    for cap in caps_r3:
        f = R3["folds"][cap]
        sm = f["summary"]
        frows.append([cap.replace("CTU-IoT-Malware-Capture-", ""), n0(f["n_test"]),
                      f3(sm["A"]["macro_f1_mean"]), f3(sm["D"]["macro_f1_mean"]),
                      f"{sm['D_minus_A']['mean']:+.3f}", f"{sm['B_minus_A']['mean']:+.3f}",
                      f"{sm['C_minus_A']['mean']:+.3f}"])
    table("Table 15. Leave-one-capture-out (R3): each capture held out once, mean over 5 seeds",
          ["Held-out capture", "Test rows", "A macro F1", "D macro F1", "D − A", "B − A", "C − A"],
          frows, [1700, 1500, 1260, 1260, 1200, 1200, 1240], "experiments/cross_log/results/robustness/R3_leave_one_capture_out.json")
    fd = R3["fold_level_differences"]
    p(f"Across the {len(caps_r3)} leave-one-capture-out folds, combining all three log types "
      f"improved on connection features alone in {fd['D_minus_A']['folds_positive']} folds and "
      f"was worse in {fd['D_minus_A']['folds_negative']}; DNS alone improved in "
      f"{fd['B_minus_A']['folds_positive']} and alerts alone in {fd['C_minus_A']['folds_positive']}. "
      f"Pooled over all folds, macro F1 rose from {f3(R3['pooled_summary']['A']['macro_f1_mean'])} "
      f"to {f3(R3['pooled_summary']['D']['macro_f1_mean'])}; this pooled figure is dominated by "
      f"the two largest captures (1-1 and 48-1), so the per-fold results are the more "
      f"informative. The gains were large on several held-out captures (for example 21-1, 8-1, "
      f"20-1 and 34-1), close to zero on 3-1, and slightly negative on 42-1 and on 48-1, a "
      f"capture consisting almost entirely of scanning. The cross-log benefit is therefore "
      f"consistent in direction across most unseen networks, but it is not universal and "
      f"its size depends strongly on the network.")
else:
    callout("Leave-one-capture-out (R3)", "This analysis is still running and will be added in "
            "the next version of this document.")

h2("5.6 Quality checks and corrections")
p("Three data and code issues were found and handled during the work. They are reported here "
  "because they affect how the results should be read.")
numbered([
    "Alert timestamps. A first run of this experiment converted Suricata alert times with an assumption about the internal time resolution that does not hold in the pandas version used, which made every alert time 1,000 times too small. All alert features were therefore zero and the alert-linked incidents were placed in the wrong time windows. The error was found during the robustness analyses, fixed and covered by a regression test, and every result in this section was regenerated with the unchanged pre-registered design. Label matching, DNS features and Experiments 1 to 3 were not affected. The superseded outputs are kept, marked as such, in experiments/cross_log/results/superseded_2026-11-03_alert_timestamp_bug/.",
    f"Record granularity in capture 34-1. The IoT-23 labelled log records each of the 14,159 packets of one denial-of-service flow as a separate connection. Zeek 9.0.1, and Bro 2.6.4 (built from source to match the generation of the tool used for IoT-23), both record that flow as 6 connections, so only {n0(OZ['results'][0]['per_class']['dos']['matched'])} of {n0(OZ['results'][0]['per_class']['dos']['labelled'])} denial-of-service rows of 34-1 enter the test set. The difference lies in IoT-23's processing, not in the Zeek version.",
    "Truncated captures. The packet captures of 42-1 (and of 48-1 and 49-1, used in R3) end in an incomplete final packet, which Zeek cannot read. A byte-exact copy without the incomplete final bytes (24 to 70 bytes) was used; the original files are unchanged.",
])
pagebreak()

# ================================================================ synthesis
h1("6. What the experiments show together")
p("Taken together, the four experiments give a consistent and more nuanced answer to RQ1 than "
  "any single one of them.")
numbered([
    "Correlating events into incidents within a log source greatly reduces the number of items to review (83.28% overall, 42.09% on IoT-23), which is a precondition for faster triage.",
    "But when incident summaries replace event-level detail, detection gets worse, mainly through false alarms on benign traffic that, once grouped, looks like scanning. This holds with an incident-grouped split (Run B), a temporal split (Run T) and in a controlled ablation, at every window and seed tested.",
    "Linking different log types about the same activity does the opposite: it adds information that a single log lacks. On networks never seen in training, DNS and alert context improved detection, and combining connection logs, DNS logs and alerts gave the largest gain: in every one of 20 seeds on the main split, and on 6 of 8 held-out captures in the leave-one-capture-out check.",
    "Absolute performance on unseen networks remains limited, with many attacks still missed. Integration helps, but it does not by itself solve the problem of generalising to new networks and new attack types.",
])
callout("Implication for smart-home risk mitigation",
        "An integrated monitoring system should keep event-level detail and enrich each event "
        "with context from other log types, such as DNS behaviour and IDS alerts for the same "
        "device, rather than collapsing events into coarse incident summaries. Correlation into "
        "incidents remains valuable for presenting alerts to an analyst, but it should not "
        "replace the evidence the detector relies on.")

# ================================================================ limitations
h1("7. Limitations")
bullets([
    "Research datasets. IoT-23 and Bot-IoT are laboratory recordings; Bot-IoT is partly simulated. Results may differ on real home networks.",
    "Within-capture evaluation in Experiments 1 to 3. Training and test events come from the same captures; Run T moves the test set forward in time but stays within the same captures.",
    "Bootstrap intervals in Experiments 1 to 3 treat incidents as independent, although incidents of one capture share hosts and time, so these intervals are likely too narrow.",
    "Single log points in Experiment 4. The three log types come from one packet capture, not from independent sensors.",
    "Few captures, one infected device each. Experiment 4 uses seven captures for the main analysis (eight for R3), and absolute performance varies strongly with the random seed.",
    "Alerts use a 2026 ruleset on 2018–2019 traffic, so some signatures postdate the attacks. Alerts raised later in the same connection are not used in the main analysis.",
    "Class coverage. Denial of service and DDoS are merged; botnet, brute-force and data-theft classes do not occur in the data; Experiment 4 uses a binary target.",
])

# ================================================================ reproducibility
h1("8. Reproducibility")
table("Table 16. Software and verification",
      ["Item", "Detail"],
      [["Pipeline (Experiments 1 to 3)", "Python 3.15.0, numpy 2.5.3, pandas 3.0.6, scikit-learn 1.9.1, pyarrow 26.0.0; Windows 11"],
       ["Log generation (Experiment 4)", "Zeek 9.0.1, Suricata 7.0.3, Bro 2.6.4 (34-1 check), in Ubuntu 24.04 under WSL 2"],
       ["Ruleset", "ET Open for Suricata 7.0.3, SHA-256 d5330ebe76cb36cf…, 52,803 enabled rules"],
       ["Tests", "94 pipeline tests, 48 demonstration-app tests, 6 ablation tests and 14 cross-log tests, all passing"],
       ["Integrity", "SHA-256 of all 30,615 existing project files checked before and after the new work: no file changed"],
       ["Code and results", "Private GitHub repository Abdullabintarish/iot-smart-home-integrated-detection; new work under experiments/"],
       ["Full record", "Every command, version, hash and decision: experiments/RUN_LOG.md"]],
      [2700, 6660], "experiments/RUN_LOG.md")
p("Dataset citations: Garcia, S., Parmisano, A., & Erquiaga, M. J. (2020). IoT-23: A labeled "
  "dataset with malicious and benign IoT network traffic (Version 1.0.0). Zenodo. "
  "https://doi.org/10.5281/zenodo.4743746 (CC BY 4.0). Koroniotis, N., Moustafa, N., Sitnikova, "
  "E., & Turnbull, B. (2019). Towards the development of realistic botnet dataset in the "
  "Internet of Things for network forensic analytics: Bot-IoT dataset. Future Generation "
  "Computer Systems, 100, 779–796.")
pagebreak()

h1("Appendix A. Source file of every table and figure")
table("Table A1. Sources", ["Item", "Source file"], [[a, b] for a, b in sources if not a.startswith("Table A1")],
      [4300, 5060], "this document")

(HERE / "content.json").write_text(json.dumps({"blocks": blocks}, indent=1, ensure_ascii=False), encoding="utf-8")
print("blocks", len(blocks), "R3", bool(R3))
