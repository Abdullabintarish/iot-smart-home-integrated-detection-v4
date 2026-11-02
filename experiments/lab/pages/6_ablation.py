"""Page 6 - Controlled ablation on the Run B data (supplementary)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import supp  # noqa: E402
import ui  # noqa: E402

ui.setup("Controlled Ablation",
         "What does incident context change when the model, training sample and "
         "test events are all held fixed?", need_cache=False)
ui.banner(supp.PENDING)

full = supp.ABL / "full"
checks = supp.jload(str(full / "checks.json"))
summ = supp.csv(str(full / "ablation_summary.csv"))
boot = supp.jload(str(full / "bootstrap.json"))

st.subheader("Data check against Run B")
c = st.columns(4)
c[0].metric("Events", ui.fmt(checks["n_events"]))
c[1].metric("Held-out test events", ui.fmt(checks["n_test"]))
c[2].metric("Incidents at 300 s", ui.fmt(checks["groups_at_300s"]))
c[3].metric("Novel-vector test events", ui.fmt(checks["n_novel"]))
ok = checks["groups_at_300s"] == 704_090 and checks["n_novel"] == 1_463_143
st.markdown(f"{ui.mark(ok)} Both numbers match Run B (704,090 and 1,463,143), so "
            "the saved data are Run B's data.", unsafe_allow_html=True)
supp.src(full / "checks.json")

st.subheader("Results by feature set and window")
ui.note("Mean ± SD over seeds 42, 1, 2, 3, 4 on all 1,692,332 test events. "
        "Windows of 600 and 900 s are cut at the Run B train/test boundary.")
allrows = summ[summ["subset"] == "all"].copy()
allrows["Window (s)"] = allrows["window_s"].map(lambda w: "—" if w == 0 else str(w))
allrows["Macro F1"] = [f"{m:.4f} ± {s:.4f}" for m, s in zip(allrows.f1_mean, allrows.f1_sd)]
allrows["FPR"] = [f"{m:.2%} ± {s:.2%}" for m, s in zip(allrows.fpr_mean, allrows.fpr_sd)]
allrows["Window cut"] = allrows["window_cut"].map({True: "yes", False: "no"})
ui.table(allrows[["Window (s)", "feature_set", "Macro F1", "FPR", "Window cut"]]
         .rename(columns={"feature_set": "Feature set"}))
supp.src(full / "ablation_summary.csv")

ctx = allrows[allrows.window_s > 0]
base = allrows[allrows.window_s == 0]
lines = []
for fs, b in (("event_plus_incident", "event_only"), ("shared_plus_incident", "shared_event"),
              ("incident_only", "event_only")):
    d = ctx[ctx.feature_set == fs][["window_s", "fpr_mean"]].assign(feature_set=fs)
    lines.append(d)
    lines.append(pd.DataFrame({"window_s": ctx.window_s.unique(),
                               "fpr_mean": float(base[base.feature_set == b].fpr_mean.iloc[0]),
                               "feature_set": f"{b} (no window)"}))
chart_df = pd.concat(lines).drop_duplicates()
chart_df = chart_df[chart_df.feature_set != "incident_only"]
st.markdown("**False-positive rate against window** (incident_only, at about 9%, "
            "is left out so the small differences stay visible)")
st.altair_chart(
    alt.Chart(chart_df).mark_line(point=True).encode(
        x=alt.X("window_s:O", title="Correlation window (s)"),
        y=alt.Y("fpr_mean:Q", title="FPR (mean over seeds)", axis=alt.Axis(format=".1%")),
        color=alt.Color("feature_set:N", title="Feature set"),
        tooltip=["feature_set", "window_s", alt.Tooltip("fpr_mean", format=".3%")]
    ).properties(height=300), width="stretch")

st.subheader("Paired bootstrap at 300 s (seed 42)")
rows = [{"Comparison": k.replace("_minus_", " − "),
         "Macro F1 difference": "[{:+.4f}, {:+.4f}]".format(*v["f1_macro_diff"]),
         "FPR difference": "[{:+.4f}, {:+.4f}]".format(*v["fpr_diff"]),
         "Replicates": v["n_boot"]} for k, v in boot.items()]
ui.table(pd.DataFrame(rows))
supp.src(full / "bootstrap.json")

st.subheader("Where the extra false positives fall (300 s)")
sub = summ[(summ.subset.isin(["multi_event_benign", "single_event_benign"]))
           & (summ.window_s.isin([0, 300]))]
sub = sub[["feature_set", "subset", "n", "fpr_mean"]].assign(
    FPR=lambda d: d.fpr_mean.map(lambda v: f"{v:.2%}")).drop(columns="fpr_mean")
ui.table(sub.rename(columns={"feature_set": "Feature set", "subset": "Benign events in",
                             "n": "Events"}), thousands=True)
supp.src(full / "ablation_summary.csv")

st.subheader("Reading")
ui.note("Adding incident context does not change macro F1 (the bootstrap interval "
        "includes zero) but roughly triples the false-positive rate, from 0.38% to "
        "1.14% at 300 s. The extra false alarms fall on benign events that sit in "
        "multi-event incidents. The pattern holds at every window and seed, which "
        "supports the Run B conclusion under controlled conditions.")
ui.note("Not directly comparable with the Run B headline numbers: the ablation uses "
        "one pooled event model, while Run B uses 13 per-source models and an "
        "incident-level model. The settings are the package defaults and were not "
        "agreed with the supervisor in advance.")
