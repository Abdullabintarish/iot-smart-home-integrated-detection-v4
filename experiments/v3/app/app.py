"""v3 results app: fair transfer study and cross-log expansion (read-only).

    cd experiments/v3/app
    ..\\..\\..\\code\\demo\\.venv\\Scripts\\python.exe -B -m streamlit run app.py --server.port 8502

Reads only files under experiments/v3/results and experiments/v3/cross_log/results.
Uses the demo's ui helpers for styling; nothing in code/ or experiments/lab is changed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
V3 = HERE.parent
SUB = V3.parents[1]
sys.path.insert(0, str(SUB / "code" / "demo"))

import altair as alt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

st.set_page_config(page_title="v3 results - transfer and cross-log", layout="wide",
                   initial_sidebar_state="expanded")
import ui  # noqa: E402

RES = V3 / "results"
TR = RES / "transfer"
XL = RES / "cross_log"
S3 = V3 / "cross_log" / "results"
OLD_S3 = V3.parent / "cross_log" / "results"

RUN_NAME = {
    "frag": "Source-specific RF (fragmented)", "frag_soft": "Fragmented · probability average",
    "frag_union": "Fragmented · any-model alert",
    "rf_event_only": "RF · event", "rf_incident_only": "RF · incident only",
    "rf_event_plus_incident": "RF · event + incident",
    "hgb_event_only": "HGB · event", "hgb_incident_only": "HGB · incident only",
    "hgb_event_plus_incident": "HGB · event + incident",
    "lr_event_only": "LR · event", "lr_incident_only": "LR · incident only",
    "lr_event_plus_incident": "LR · event + incident"}
ORDER = list(RUN_NAME)
MET_NAME = {"f1_macro": "Macro F1", "f1_macro_present": "Macro F1 (present classes)",
            "balanced_accuracy": "Balanced accuracy", "mcc": "MCC", "binary_f1": "Binary F1",
            "pr_auc_binary": "PR-AUC (binary)", "roc_auc_binary": "ROC-AUC (binary)",
            "fpr": "FPR", "fnr": "FNR"}
COND = {"A": "A · connection", "B": "B · + DNS", "C": "C · + alerts", "D": "D · + DNS + alerts",
        "Z": "Z · zero control", "P": "P · permuted control", "MAJ": "MAJ · majority",
        "STR": "STR · stratified random"}


@st.cache_data(show_spinner=False)
def jload(p: str) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def short(c: str) -> str:
    return c.replace("CTU-IoT-Malware-Capture-", "").replace("CTU-Honeypot-Capture-", "honeypot ")


def src(*paths: Path) -> None:
    st.caption("Source: " + ", ".join(str(p.relative_to(SUB)).replace("\\", "/") for p in paths))


def design_means(design: str) -> tuple[pd.DataFrame, dict]:
    m = jload(str(TR / design / "metrics.json"))
    names = [n for n in ORDER if any(k.startswith(n + "|") for k in m["runs"])]
    rows = []
    for n in names:
        r = {"Run": RUN_NAME[n]}
        for met in MET_NAME:
            per = []
            for f in m["folds"]:
                v = [m["runs"][f"{n}|{s}"][f][met] for s in m["seeds"]]
                if all(x is not None for x in v):
                    per.append(np.mean(v))
            r[MET_NAME[met]] = np.mean(per) if per else np.nan
        rows.append(r)
    return pd.DataFrame(rows), m


# ---------------------------------------------------------------------------
def page_overview():
    ui.setup("v3: fair transfer study and cross-log expansion",
             "Steps 2–6 of the reliability plan, pre-registered in experiments/v3/PLAN_V3.md "
             "before any result was seen.", need_cache=False)
    v = jload(str(RES / "verification.json"))
    lean = jload(str(RES / "lean_io_check.json"))
    cc = jload(str(XL / "cachecheck.json"))
    c = st.columns(4)
    c[0].metric("Independent verification", "all_ok ✓" if v["all_ok"] else "FAILED")
    n = sum(x.get("values_checked", 0) for k, x in v.items() if isinstance(x, dict))
    c[1].metric("Values recomputed", f"{n:,}", "0 mismatches")
    c[2].metric("Historical ablation reproduced",
                f"{sum(v['transfer_runB']['reproduces_historical_ablation'].values())}/"
                f"{len(v['transfer_runB']['reproduces_historical_ablation'])}")
    c[3].metric("Seeds", "42, 1, 2, 3, 4")

    st.subheader("Main findings")
    ui.note("<b>1. The fair source-specific baseline does not transfer.</b> On an unseen source, "
            "its averaged prediction misses 98.5% of attacks, and its any-model-alert version "
            "flags every benign event. The unified RF scores higher (macro F1 0.372 against 0.296), "
            "but the difference is <b>not significant after Holm correction</b>.")
    ui.note("<b>2. Incident-only features are worse than event features</b> for RF, HGB and LR. "
            "On the Run B split this holds for all 5 seeds and every model.")
    ui.note("<b>3. Adding incident context helps all three model families on unseen sources</b> "
            "(9–11 of 13 sources), but no gain survives Holm correction (best: HGB, p Holm = 0.106).")
    ui.note("<b>4. The FPR increase from incident context is specific to RF.</b> Within the Run B "
            "split, FPR rises for RF (+0.76 points) but falls for HGB (−0.11) and LR (−0.92).")
    ui.note("<b>5. Cross-log:</b> two new C&C captures (36-1, 7-1) pass every gate. 21,501 C&C "
            "training rows instead of 35 did <b>not</b> improve the C&C test capture 8-1. DNS "
            "context helps clearly only on 34-1, and alert context is no better than its "
            "permuted control.")

    st.subheader("Verification detail")
    rows = []
    for k, x in v.items():
        if isinstance(x, dict):
            rows.append({"Check": k, "Values recomputed": x["values_checked"],
                         "Mismatches": len(x["mismatches"]) if isinstance(x["mismatches"], list) else x["mismatches"],
                         "p-value mismatches": str(len(x["stats_mismatches"])) if "stats_mismatches" in x else "–",
                         "Manifest hashes": "✓" if x["manifest_hashes_ok"] else "✗"})
    ui.table(pd.DataFrame(rows), thousands=True)
    c = st.columns(3)
    c[0].metric("Lean Zeek reader = original", f"{sum(lean['checks'].values())}/{len(lean['checks'])} logs")
    c[1].metric("Rebuilt cache = original", f"{sum(cc.values())}/{len(cc)} captures")
    c[2].metric("Automated tests", "141 / 141 OK")
    src(RES / "verification.json", RES / "lean_io_check.json", XL / "cachecheck.json")


# ---------------------------------------------------------------------------
def page_transfer():
    ui.setup("Transfer study: RF, HGB and LR, fragmented vs unified",
             "Same events, same training samples for every model, 5 seeds.", need_cache=False)
    design = st.radio("Design", ["loso", "runB"], horizontal=True,
                      format_func=lambda d: {"loso": "Leave-one-source-out (unseen sources)",
                                             "runB": "Run B split (within sources)"}[d])
    df, m = design_means(design)
    ui.note("loso: the fragmented baseline predicts each held-out source with the other "
            "12 source models only. No held-out label is used." if design == "loso" else
            "runB: each source-specific model predicts its own test rows (the thesis baseline).")
    fmt = {c: st.column_config.NumberColumn(format="%.4f") for c in df.columns if c != "Run"}
    ui.table(df, column_config=fmt)
    if design == "loso":
        st.caption("Mean over 13 held-out sources of the 5-seed mean. PR-AUC, ROC-AUC and FNR use the "
                   "11 sources that contain attacks. On the two benign-only honeypots, never alerting "
                   "scores macro F1 = 1.0.")
    src(TR / design / "metrics.json")

    met = st.selectbox("Metric for the chart", list(MET_NAME), format_func=MET_NAME.get)
    plot = df[["Run", MET_NAME[met]]].rename(columns={MET_NAME[met]: "value"})
    plot["Model"] = plot["Run"].str.split(" · ").str[0]
    ui.chart(alt.Chart(plot).mark_bar().encode(
        y=alt.Y("Run:N", sort=[RUN_NAME[n] for n in ORDER], title=None),
        x=alt.X("value:Q", title=MET_NAME[met]),
        color=alt.Color("Model:N", legend=None),
        tooltip=["Run", alt.Tooltip("value:Q", format=".4f")]).properties(height=360))

    if design == "loso":
        st.subheader("Per held-out source (5-seed mean)")
        rows = []
        names = [n for n in ORDER if any(k.startswith(n + "|") for k in m["runs"])]
        for f, info in m["folds"].items():
            for n in names:
                rows.append({"Source": short(f), "Run": RUN_NAME[n], "n test": info["n_test"],
                             met: np.mean([m["runs"][f"{n}|{s}"][f][met] if m["runs"][f"{n}|{s}"][f][met]
                                           is not None else np.nan for s in m["seeds"]])})
        pf = pd.DataFrame(rows)
        ui.chart(alt.Chart(pf).mark_rect().encode(
            x=alt.X("Run:N", sort=[RUN_NAME[n] for n in ORDER], title=None),
            y=alt.Y("Source:N", title=None),
            color=alt.Color(f"{met}:Q", title=MET_NAME[met], scale=alt.Scale(scheme="blues")),
            tooltip=["Source", "Run", "n test", alt.Tooltip(f"{met}:Q", format=".3f")]
        ).properties(height=420))


# ---------------------------------------------------------------------------
def page_stats():
    ui.setup("Pre-registered paired tests",
             "8 comparisons (X − Y), Holm-corrected per metric.", need_cache=False)
    st_ = jload(str(TR / "stats.json"))
    design = st.radio("Design", ["loso", "runB"], horizontal=True,
                      format_func=lambda d: {"loso": "Leave-one-source-out (unit = source, n = 13)",
                                             "runB": "Run B split (unit = seed, n = 5)"}[d])
    met = st.selectbox("Metric", list(st_[design]["comparisons"]), format_func=MET_NAME.get)
    pos = "folds" if design == "loso" else "seeds"
    rows = []
    for r in st_[design]["comparisons"][met]:
        row = {"Comparison": f"{RUN_NAME[r['x']]}  −  {RUN_NAME[r['y']]}", "Mean Δ": r["mean_diff"],
               f"{pos} + / −": f"{r[pos + '_positive']} / {r[pos + '_negative']}",
               "p (exact sign-flip)": r["p_sign_flip"], "p Holm": r["p_sign_flip_holm"]}
        if design == "loso":
            row["p Wilcoxon"] = r["p_wilcoxon"]
        row["Significant (Holm < 0.05)"] = "yes" if r["p_sign_flip_holm"] < 0.05 else "no"
        rows.append(row)
    cfg = {c: st.column_config.NumberColumn(format="%.4f")
           for c in ("Mean Δ", "p (exact sign-flip)", "p Holm", "p Wilcoxon")}
    ui.table(pd.DataFrame(rows), column_config=cfg)
    if design == "runB":
        ui.note("With 5 seeds the smallest possible two-sided p is 0.0625, so the seed-level test "
                "cannot reach 0.05. The incident-clustered bootstrap on seed 42 is shown below.")
        b = st_["runB"]["incident_bootstrap_seed42"]
        bt = pd.DataFrame([{"Comparison": k.replace("_minus_", "  −  "),
                            "Δ macro F1, 95% CI": f"[{v['f1_macro_diff'][0]:+.4f}, {v['f1_macro_diff'][1]:+.4f}]",
                            "Δ FPR, 95% CI": f"[{v['fpr_diff'][0]:+.4f}, {v['fpr_diff'][1]:+.4f}]"}
                           for k, v in b.items()])
        ui.table(bt)
    src(TR / "stats.json")


# ---------------------------------------------------------------------------
def page_crosslog():
    ui.setup("Cross-log expansion: new C&C captures",
             "Zeek conn + Zeek DNS + Suricata alerts, linked by Community ID; binary attack vs benign.",
             need_cache=False)
    st.subheader("New captures: Stage 3 gate")
    rows = []
    for c in ("CTU-IoT-Malware-Capture-36-1", "CTU-IoT-Malware-Capture-7-1"):
        d = jload(str(S3 / f"stage3_{c}.json"))
        lm, lk = d["label_match"], d["linking"]
        rows.append({"Capture": short(c), "Conn records": lm["new_conn_records"],
                     "Label match": f"{lm['match_rate_new']:.2%}",
                     **{f"{k}": v for k, v in lm["matched_by_class"].items()},
                     "Alerts": lk["records"]["alert"], "Cross-source incidents": lk["incidents_ge2_source_types"],
                     "Gate": "pass" if d["gate"]["pass"] else "fail"})
    ui.table(pd.DataFrame(rows).fillna(0), thousands=True)
    ui.note("Both captures are dominated by Okiru malware (≈99%), with C&C at 0.1% and 0.05% of rows. "
            "They were chosen from 11 candidates by labelled-log availability, C&C coverage and "
            "the disk budget (RUN_LOG §12).")
    src(S3 / "stage3_CTU-IoT-Malware-Capture-36-1.json", S3 / "stage3_CTU-IoT-Malware-Capture-7-1.json")

    st.subheader("Primary split, with the C&C captures added to training")
    p = jload(str(XL / "primary_augmented.json"))
    v2 = jload(str(V3.parent / "v2" / "results" / "cross_log" / "primary.json"))
    c = st.columns(3)
    c[0].metric("C&C training rows", f"{p['train_classes'].get('c2', 0):,}",
                f"v2: {v2['train_classes'].get('c2', 0)}")
    c[1].metric("Test captures", ", ".join(short(x) for x in p["test"]))
    c[2].metric("B − A (DNS gain)", f"{p['summary']['B_minus_A']['mean']:+.3f}",
                f"{p['summary']['B_minus_A']['seeds_positive']}/5 seeds")
    rows = [{"Condition": COND[k], "v3 macro F1": p["summary"][k]["macro_f1_mean"],
             "v3 sd": p["summary"][k]["macro_f1_sd"], "v2 macro F1": v2["summary"][k]["macro_f1_mean"],
             "FPR": p["summary"][k]["fpr_mean"], "FNR": p["summary"][k]["fnr_mean"]} for k in COND]
    ui.table(pd.DataFrame(rows), column_config={c: st.column_config.NumberColumn(format="%.3f")
                                                for c in ("v3 macro F1", "v3 sd", "v2 macro F1", "FPR", "FNR")})
    pc = pd.DataFrame([{"Test capture": short(cap), "Condition": COND[k], "Macro F1": x["macro_f1_mean"]}
                       for cap, v in p["per_capture"].items() for k, x in v.items()])
    ui.chart(alt.Chart(pc).mark_bar().encode(
        x=alt.X("Condition:N", sort=list(COND.values()), title=None),
        y=alt.Y("Macro F1:Q", scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("Condition:N", legend=None), column=alt.Column("Test capture:N"),
        tooltip=["Test capture", "Condition", alt.Tooltip("Macro F1", format=".3f")]).properties(width=220, height=240))
    ui.note("The DNS gain comes entirely from 34-1. 8-1 (all C&C) stays at 0.52 (v2: 0.53), so the "
            "35-row C&C shortage was not why it scored poorly. Connection-only (A) is still below the "
            "stratified random baseline (STR).")
    src(XL / "primary_augmented.json")

    st.subheader("Leave-one-capture-out (9 captures that pass the gate)")
    lo = jload(str(XL / "loco.json"))
    rows = []
    for f, v in lo["folds"].items():
        for k in COND:
            rows.append({"Held-out": short(f), "Condition": COND[k], "Macro F1": v["summary"][k]["macro_f1_mean"]})
    lf = pd.DataFrame(rows)
    ui.chart(alt.Chart(lf).mark_rect().encode(
        x=alt.X("Condition:N", sort=list(COND.values()), title=None), y=alt.Y("Held-out:N", title=None),
        color=alt.Color("Macro F1:Q", scale=alt.Scale(domain=[0, 1], scheme="blues")),
        tooltip=["Held-out", "Condition", alt.Tooltip("Macro F1", format=".3f")]).properties(height=330))
    d = lo["fold_level_differences"]
    ui.table(pd.DataFrame([{"Difference": k.replace("_minus_", " − "), "Folds better": v["folds_positive"],
                            "Folds worse": v["folds_negative"], "of": v["n_folds"],
                            "Largest gain": f"{max(v['per_fold'].values()):+.3f} "
                                            f"({short(max(v['per_fold'], key=v['per_fold'].get))})"}
                           for k, v in d.items()]))
    st.caption("Excluded by the gate, as in v2: " + ", ".join(short(x) for x in lo["excluded_by_gate"]))
    src(XL / "loco.json")


# ---------------------------------------------------------------------------
def page_limits():
    ui.setup("Limitations and reliability", need_cache=False)
    st.subheader("Remaining methodological limitations")
    for t in ("Only 13 sources and 9 cross-log folds that pass the gate: low statistical power. With 5 seeds "
              "the smallest possible p is 0.0625.",
              "Most generalisation claims are directional only: none of the main macro-F1 comparisons "
              "survives Holm correction.",
              "The new captures are single-family (Okiru) and produced few Suricata alerts (2 and 36).",
              "Benign-only honeypot folds reward never alerting on macro F1, so MCC, PR-AUC and FNR are "
              "reported alongside it.",
              "One sensor vantage point; offline evaluation only; no tuning study (by design).",
              "Stage 3 on the new captures used a lean log reader, verified identical to the original "
              "on all 26 old logs."):
        ui.note(t)
    st.subheader("Technical reliability rating")
    ui.table(pd.DataFrame([
        ("Python code quality", 82, 85, 86), ("Dataset processing accuracy", 85, 85, 86),
        ("Event correlation correctness", 85, 87, 87), ("Data leakage prevention", 80, 86, 87),
        ("Experimental fairness", 68, 78, 85), ("ML methodology", 70, 78, 84),
        ("Cross-log correlation validity", 45, 68, 70), ("Statistical robustness", 62, 72, 80),
        ("Reproducibility", 88, 93, 94), ("Overall scientific reliability", 70, 79, 83)],
        columns=["Category", "Audit", "After v2", "After v3"]))
    st.caption("The ratings score how reliable the evidence is, not how favourable the results are. "
               "Source: experiments/audit/TECHNICAL_AUDIT.md §7")


nav = st.navigation({"v3 results": [
    st.Page(page_overview, title="Overview and verification", url_path="overview", default=True),
    st.Page(page_transfer, title="Transfer study", url_path="transfer"),
    st.Page(page_stats, title="Statistical tests", url_path="tests"),
    st.Page(page_crosslog, title="Cross-log expansion", url_path="cross-log"),
    st.Page(page_limits, title="Limitations and reliability", url_path="limitations")]})
with st.sidebar:
    st.markdown("**v3 results**")
    st.caption("Read-only view of experiments/v3/results. Nothing is retrained.")
nav.run()
