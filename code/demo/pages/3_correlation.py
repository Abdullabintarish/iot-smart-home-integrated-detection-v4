"""Page 3 - Event Correlation Explorer: how many events become one incident."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import evidence as ev  # noqa: E402
import ui  # noqa: E402

ui.setup("Event Correlation Explorer",
         "Stage 3 rule-based correlation: member events of one incident, the rule "
         "that grouped them, and the resulting alert reduction.")
rep, man = ui.report(), ui.manifest()
cfg = man["config"]["pipeline.config"]
W, SCOPE, RULES = cfg["CORRELATION_WINDOW_S"], cfg["CORRELATION_SCOPE"], cfg["CORRELATION_RULES"]
S = st.session_state

ui.note(
    f"<b>R1 ({RULES[0]})</b>: events are merged into one incident when they share the "
    f"same source capture, src_ip, dst_ip and protocol <i>and</i> fall into the same "
    f"tumbling {W} s window, i.e. the same bucket floor(ts / {W}). "
    f"Correlation scope is \"{SCOPE}\", so the capture is part of the key. "
    f"Rules R2/R3 apply only when an IP is missing; every incident in this run used "
    f"the rule shown in its corr_rule field.")
ui.sources("config.pipeline.config.CORRELATION_WINDOW_S",
           "config.pipeline.config.CORRELATION_SCOPE",
           "config.pipeline.config.CORRELATION_RULES", file=ev.MANIFEST)

inc = ui.incidents()
idx = ui.source_index()
n_inc = inc.groupby("source").size()
c1, c2 = st.columns([1, 1])
with c1:
    source = st.selectbox("Capture", list(idx["source"]), key="corr_source",
                          format_func=lambda s: f"{s} — {int(n_inc.get(s, 0)):,} incidents")
with c2:
    mode = st.radio("Choose an incident", ["Largest incidents", "Random sample (seed 42)",
                                           "By label", "Paste an incident_id"],
                    horizontal=True, key="corr_mode")
sub = inc[inc["source"] == source]
iid = None
LIST_N = 50
if mode == "Paste an incident_id":
    iid = st.text_input("incident_id (16 hex characters)", key="corr_paste").strip() or None
    if iid and not (inc["incident_id"] == iid).any():
        st.warning("No incident with this id in data/processed/stage3_incidents.")
        st.stop()
else:
    if mode == "Largest incidents":
        opts = sub.nlargest(LIST_N, "n_events")
    elif mode == "Random sample (seed 42)":
        opts = sub.sample(n=min(LIST_N, len(sub)), random_state=42)
    else:
        labs = sorted(sub["label"].unique())
        lab = st.selectbox("Incident (majority) label", labs, key="corr_label")
        opts = sub[sub["label"] == lab].nlargest(LIST_N, "n_events")
    fmt = {r.incident_id: f"{r.incident_id} · {r.label} · {r.n_events:,} events"
           for r in opts.itertuples()}
    iid = st.selectbox(f"Incident ({len(opts)} listed)", list(fmt), key="corr_incident",
                       format_func=lambda k: fmt[k])
if not iid:
    st.info("Enter an incident_id to continue.")
    st.stop()

d = ui.incident_members(iid)
I, D = d["incident"], d["diagnostics"]
start, end, bucket = ev.window_of(float(D["ts_first"]), W)
pn = ui.proto_names()

st.subheader(f"Incident {iid}")
m = st.columns(5)
m[0].metric("Member events", ui.fmt(int(I["n_events"])))
m[1].metric("Incidents", "1")
m[2].metric("Span (s)", ui.fmt(float(I["span_s"]), 3))
m[3].metric("Majority label", str(I["label"]))
m[4].metric("Test / train events", f"{int(D['n_test_events']):,} / {int(D['n_train_events']):,}")
a, b = st.columns(2)
with a:
    ui.kv_card("Correlation key", [
        ("capture (source)", D["source"]), ("dataset", ev.family(D["source"])),
        ("rule (corr_rule)", D["corr_rule"]), ("src_ip", D["src_ip"]), ("dst_ip", D["dst_ip"]),
        ("proto (Stage 2 code)", f"{D['proto']}  = {pn.get(int(D['proto']), '?')}"),
        (f"window bucket floor(ts/{W})", f"{bucket:,}"),
        ("window start (UTC)", ev.to_utc([start])[0]), ("window end (UTC)", ev.to_utc([end])[0]),
        ("ts_first (UTC)", ev.to_utc([D["ts_first"]])[0]), ("ts_last (UTC)", ev.to_utc([D["ts_last"]])[0]),
        ("span_s", f"{float(I['span_s']):.6f}"),
    ])
    st.caption("proto: Stage 2 stores the protocol as an integer code; the name comes from "
               "the staged raw value of the same events (demo/cache/meta.json → proto_map).")
with b:
    ui.kv_card("Incident features used by the integrated model (stage3_incidents)",
               [(f, I[f]) for f in ev.model_feature_order()], css_title="lab-integ")
    ui.kv_card("Label diagnostics (label-derived audit statistics, NOT model features)", [
        ("label_counts", D["label_counts"]), ("n_labels", D["n_labels"]),
        ("label_purity", f"{float(D['label_purity']):.4f}"),
        ("label_entropy", f"{float(D['label_entropy']):.4f}")])
    st.caption("Sources: data/processed/stage3_incidents/incidents_0000.parquet, "
               "data/processed/stage3_incident_diagnostics/diagnostics_0000.parquet")

st.markdown("#### Membership check")
ui.check_line(d["all_ok"], f"all {d['n_members']:,} member events (read from "
              f"data/processed/stage3_events) share source, src_ip, dst_ip, proto and "
              f"window bucket, and the counts match the incident tables")
with st.expander("Check details", expanded=not d["all_ok"]):
    ui.checks_table(d["checks"])

st.markdown("#### Many events → one incident")
ui.chart(ui.time_hist(d["ts"], labels=d["labels"], bins=60,
                      title=f"{d['n_members']:,} member events over time (UTC), stacked by "
                            f"ground-truth label → 1 incident"))
mem = d["members"]
shown = len(mem)
st.caption(f"Member events: {d['n_members']:,} in total; "
           + (f"all shown." if shown == d["n_members"] else
              f"the first {shown:,} by timestamp are listed (cap {ev.MAX_SELECTION:,})."))
first = dict(zip(idx["source"], idx["first_event_id"]))
view = pd.DataFrame({
    "event_id": mem["event_id"], "record_in_file": mem["event_id"] - mem["source"].map(first),
    "ts_utc": ev.to_utc(mem["ts"]).to_numpy(), "src_ip": mem["src_ip"], "dst_ip": mem["dst_ip"],
    "proto": [f"{int(p)} ({pn.get(int(p), '?')})" for p in mem["proto"]],
    "bucket": np.floor_divide(mem["ts"].to_numpy(), W).astype("int64"),
    "label": mem["label"], "split": mem["split"], "corr_rule": mem["corr_rule"]})
PAGE = 200
pages = max(1, int(np.ceil(len(view) / PAGE)))
p = st.number_input(f"Member page (1 … {pages}, {PAGE} rows each)", 1, pages, 1,
                    key=f"corr_page_{iid}")
ui.table(view.iloc[(p - 1) * PAGE: p * PAGE], height=320)

# ---- alert reduction --------------------------------------------------------
st.subheader("Alert reduction")
ard = rep["alert_reduction_by_dataset"]
ov = ard["overall"]
ui.note(f"alert reduction = 1 − incidents / events = 1 − {ov['incidents']:,} / "
        f"{ov['events']:,} = {ov['alert_reduction']:.6f} ({ui.fmt_pct(ov['alert_reduction'])})")
recomp = ui.alert_reduction_recomputed()
rec = recomp.set_index("source")
rows = []
for s, v in ard["per_source"].items():
    r = rec.loc[s] if s in rec.index else None
    ok = (r is not None and int(r["events"]) == v["events"] and int(r["incidents"]) == v["incidents"]
          and ev.close(float(r["alert_reduction"]), v["alert_reduction"], 1e-9))
    rows.append({"capture": s, "dataset": v["dataset"], "events": v["events"],
                 "incidents": v["incidents"],
                 "reduction = 1 − incidents/events": f"{v['alert_reduction']:.6f}",
                 "recomputed from stage3_incidents": ui.mark(ok)})
for k, v in ard["per_dataset"].items():
    rows.append({"capture": f"[{k} total]", "dataset": k, "events": v["events"],
                 "incidents": v["incidents"],
                 "reduction = 1 − incidents/events": f"{v['alert_reduction']:.6f}",
                 "recomputed from stage3_incidents": ""})
rows.append({"capture": "[overall]", "dataset": "both", "events": ov["events"],
             "incidents": ov["incidents"],
             "reduction = 1 − incidents/events": f"{ov['alert_reduction']:.6f}",
             "recomputed from stage3_incidents": ui.mark(
                 int(recomp["events"].sum()) == ov["events"] and len(inc) == ov["incidents"])})
ui.table(pd.DataFrame(rows), thousands=True)
ui.sources("alert_reduction_by_dataset.per_source", "alert_reduction_by_dataset.per_dataset",
           "alert_reduction_by_dataset.overall")
st.markdown(f"**Cross-source incidents: {ov['cross_source_incidents']:,}.** With correlation "
            f"scope \"{SCOPE}\" the capture is part of the correlation key, so an incident "
            f"never spans two captures or datasets. This demo does not claim cross-capture "
            f"correlation.")
ui.sources("alert_reduction_by_dataset.overall.cross_source_incidents")
