"""Page 1 - Research Overview: question, data, headline results, limitations."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import evidence as ev  # noqa: E402
import ui  # noqa: E402

ui.setup(ui.TITLE, "Research Demonstration Lab — a read-only demonstration of "
         "the verified pipeline outputs. Nothing on these pages is retrained.")
rep, man = ui.report(), ui.manifest()

st.subheader("Research question (RQ1)")
ui.note(ui.RQ1)
st.markdown(
    "The thesis compares two monitoring conditions on the same held-out events: "
    "<span class='lab-frag'>a fragmented baseline</span> (one model per source "
    "capture, trained only on that capture's individual flow records; a capture "
    "whose training data holds a single class predicts that class) and "
    "<span class='lab-integ'>an integrated condition</span> (flow records "
    "correlated into incidents; one Random Forest over incident features, its "
    "incident prediction propagated to every member event).",
    unsafe_allow_html=True)

# ---- corpus at a glance --------------------------------------------------
st.subheader("Corpus at a glance")
idx = ui.source_index()
ov = rep["alert_reduction_by_dataset"]["overall"]
c = st.columns(5)
c[0].metric("Source captures / files", f"{len(idx):,}")
c[1].metric("Flow records (events)", ui.fmt(rep["split"]["n_events"]))
c[2].metric("Correlated incidents", ui.fmt(ov["incidents"]))
c[3].metric("Held-out test events", ui.fmt(rep["fragmented"]["n_test"]))
c[4].metric("Test incidents", ui.fmt(rep["split"]["n_test_incidents"]))
ui.sources("split.n_events", "alert_reduction_by_dataset.overall.incidents",
           "fragmented.n_test", "split.n_test_incidents")
st.caption("Source captures: counted from data/interim (one staged source per shard).")

# ---- datasets --------------------------------------------------------------
st.subheader("Datasets")
ds = ev.manifest_datasets()
per_src = rep["alert_reduction_by_dataset"]["per_source"]
tbl = idx[["source", "dataset", "first_event_id", "n_events"]].merge(
    ds[["source", "raw_file", "bytes", "sha256", "origin"]], on="source", how="left")
tbl["events in report"] = [per_src.get(s, {}).get("events") for s in tbl["source"]]
tbl["staged = report"] = [ui.mark(a == b) for a, b in zip(tbl["n_events"], tbl["events in report"])]
tbl["sha256"] = tbl["sha256"].str[:16] + "…"
tbl = tbl.rename(columns={"source": "capture / file", "n_events": "staged records (Stage 1)",
                          "first_event_id": "first event_id", "bytes": "raw bytes"})
ui.table(tbl, thousands=True)
fam = rep["alert_reduction_by_dataset"]["per_dataset"]
st.caption(" · ".join(f"{k}: {v['n_sources']} sources, {v['events']:,} events"
                           for k, v in fam.items()))
ui.sources_expander([(ev.MANIFEST, "datasets.files[*] (path, bytes, sha256, provenance)"),
                     ("data/interim/shard_*.parquet", "source column (staged records per source)"),
                     (ev.REPORT, "alert_reduction_by_dataset.per_source.*.events"),
                     (ev.REPORT, "alert_reduction_by_dataset.per_dataset")])

# ---- headline results ---------------------------------------------------------
st.subheader("Headline detection results (held-out test events)")
comp = pd.DataFrame(rep["comparison"])
rows = []
for m in ui.METRICS:
    f, i = rep["fragmented"][m], rep["integrated"][m]
    rows.append({"metric": ui.METRIC_LABEL[m], "fragmented baseline": ui.fmt(f),
                 "integrated": ui.fmt(i), "difference (integrated − fragmented)": ui.fmt_diff(i - f),
                 "better": ui.better_of(m, f, i),
                 "direction": "lower is better" if m in ui.LOWER_BETTER else "higher is better"})
head = pd.DataFrame(rows)
n_frag = int((head["better"] == "fragmented").sum())
n_int = int((head["better"] == "integrated").sum())
ui.table(head)                       # full width: every column visible
if n_int == 0:
    verdict = (f"The fragmented baseline scored better on {n_frag} of {len(head)} "
               f"headline metrics; the integrated condition did not score higher on any.")
elif n_frag == 0:
    verdict = (f"The integrated condition scored better on {n_int} of {len(head)} "
               f"headline metrics.")
else:
    verdict = (f"The fragmented baseline scored better on {n_frag} and the integrated "
               f"condition on {n_int} of {len(head)} headline metrics.")
ui.note(verdict + " (Derived from the values above and each metric's direction.)")
agree = all(r["better"] == ui.better_of(r["metric"], r["fragmented"], r["integrated"])
            for r in rep["comparison"])
ui.check_line(agree, "the report's own 'better' column agrees with this derivation")

# Scores (0-1, higher is better) and error rates (lower is better) get separate
# charts and scales, so the small FPR/FNR bars are not read on the score axis.
SCORES = [m for m in ui.METRICS if m not in ui.LOWER_BETTER]
RATES = [m for m in ui.METRICS if m in ui.LOWER_BETTER]
SHORT = {"accuracy": "Accuracy", "precision_macro": "Macro precision",
         "recall_macro": "Macro recall", "f1_macro": "Macro F1", "fpr": "FPR", "fnr": "FNR"}


def _bars(metrics: list[str]) -> pd.DataFrame:
    return pd.DataFrame([{"metric": SHORT[m], "condition": ui.COND_SHORT[c_], "value": rep[c_][m]}
                         for m in metrics for c_ in ("fragmented", "integrated")])


g1, g2 = st.columns([2, 1])
with g1:
    st.caption("Scores (higher is better)")
    ui.chart(ui.metric_bars(_bars(SCORES), domain=(0, 1)))
with g2:
    st.caption("Error rates (lower is better; own scale)")
    ui.chart(ui.metric_bars(_bars(RATES), domain=None, title_y="rate"))
ui.sources(*[f"{c_}.{m}" for c_ in ("fragmented", "integrated") for m in ui.METRICS],
           "comparison[*].better")

# ---- alert reduction -----------------------------------------------------------
st.subheader("Alert reduction through correlation")
c = st.columns(4)
c[0].metric("Raw events (alerts)", ui.fmt(ov["events"]))
c[1].metric("Unified incidents", ui.fmt(ov["incidents"]))
c[2].metric("Alert reduction", ui.fmt_pct(ov["alert_reduction"]))
c[3].metric("Cross-source incidents", ui.fmt(ov["cross_source_incidents"]))
st.caption("alert reduction = 1 − incidents / events")
ar = pd.DataFrame([{"dataset": k, "sources": v["n_sources"], "events": v["events"],
                    "incidents": v["incidents"], "alert reduction": ui.fmt_pct(v["alert_reduction"]),
                    "mean events per incident": round(v["mean_events_per_incident"], 2)}
                   for k, v in rep["alert_reduction_by_dataset"]["per_dataset"].items()])
ui.table(ar, thousands=True)
ui.sources("alert_reduction_by_dataset.overall", "alert_reduction_by_dataset.per_dataset")
st.caption("Alert reduction measures how many records collapse into incidents; it is not a "
           "detection-accuracy metric.")

# ---- limitations ---------------------------------------------------------------
st.subheader("Limitations")
ui.show_limitations(rep, man)
