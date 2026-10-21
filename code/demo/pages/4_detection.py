"""Page 4 - Random Forest Detection Comparison on the saved test predictions."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import evidence as ev  # noqa: E402
import ui  # noqa: E402

ui.setup("Random Forest Detection Comparison",
         "Saved per-event predictions of both thesis conditions on the identical "
         "held-out test events (results/*_event_predictions.csv).")
rep = ui.report()
preds = ui.predictions()
idx = ui.source_index()
S = st.session_state

tab_main, tab_diag = st.tabs(["Thesis conditions", "Diagnostic models (not thesis conditions)"])

with tab_main:
    # ---- filters ----------------------------------------------------------
    f = st.columns(3)
    caps = ["All captures"] + [s for s in idx["source"] if s in set(preds["source"].cat.categories)]
    cap = f[0].selectbox("Capture", caps, key="det_capture")
    classes = ["All classes"] + sorted(preds["label"].cat.categories)
    cls = f[1].selectbox("True class", classes, key="det_class")
    outs = ["All outcomes"] + list(ev.OUTCOMES)
    out = f[2].selectbox("Outcome", outs, key="det_outcome")

    m = np.ones(len(preds), dtype=bool)
    if cap != "All captures":
        m &= (preds["source"] == cap).to_numpy()
    if cls != "All classes":
        m &= (preds["label"] == cls).to_numpy()
    base_mask = m.copy()
    if out != "All outcomes":
        m &= (preds["outcome"] == out).to_numpy()
    sel = np.flatnonzero(m)

    oc = preds["outcome"][base_mask].value_counts()
    c = st.columns(4)
    for i, o in enumerate(ev.OUTCOMES):
        c[i].metric(o, f"{int(oc.get(o, 0)):,}")
    st.caption(f"Outcome counts for capture = {cap}, class = {cls} "
               f"({int(base_mask.sum()):,} test events), computed from the saved predictions. "
               f"'baseline wrong only' = fragmented wrong and integrated correct; "
               f"'integrated wrong only' = integrated wrong and fragmented correct.")
    with st.expander("Consistency with the confusion matrices (all test events)"):
        cons = ev.outcome_consistency(preds, rep)
        ui.checks_table(pd.DataFrame(cons["checks"]))
        st.caption("The confusion matrices fix each condition's correct count (trace) and the "
                   "total; the four-way split itself exists only in the per-event predictions.")
        ui.sources("fragmented.confusion_matrix", "integrated.confusion_matrix",
                   "fragmented.n_samples")

    # ---- paginated table ------------------------------------------------------
    PAGE_SIZES = [50, 100, 200]
    p1, p2 = st.columns([1, 3])
    size = p1.selectbox("Rows per page", PAGE_SIZES, index=1, key="det_size")
    pages = max(1, int(np.ceil(len(sel) / size)))
    key = f"det_page_{cap}_{cls}_{out}_{size}"
    page = p2.number_input(f"Page (1 … {pages:,}; {len(sel):,} matching events)",
                           min_value=1, max_value=pages, value=1, key=key)
    rows = sel[(page - 1) * size: page * size]
    view = preds.iloc[rows]
    tbl = pd.DataFrame({
        "event_id": view["event_id"].to_numpy(), "capture": view["source"].astype(str).to_numpy(),
        "true label": view["label"].astype(str).to_numpy(),
        "fragmented prediction": view["pred_fragmented"].astype(str).to_numpy(),
        "fragmented": np.where(view["frag_ok"], "✓", "✗"),
        "integrated prediction": view["pred_integrated"].astype(str).to_numpy(),
        "integrated": np.where(view["integ_ok"], "✓", "✗"),
        "incident_id": view["incident_id"].astype(str).to_numpy()})
    ui.table(tbl, height=300)

EIDS = preds["event_id"].to_numpy()


def test_pos(eid: int) -> int | None:
    """Row of ``eid`` in the predictions, or None if it is not a test event."""
    p = int(np.searchsorted(EIDS, eid))
    return p if p < len(EIDS) and int(EIDS[p]) == eid else None


def details(row: pd.Series) -> None:
    eid = int(row["event_id"])

    st.subheader(f"Event {eid:,}")
    raw = ev.raw_attributes(eid)
    feats = ev.event_features(eid)
    I, D = ev.incident_row(str(row["incident_id"]))
    a, b, c3 = st.columns([1.1, 1, 1.1])
    with a:
        ui.kv_card("Staged raw record (data/interim)", [
            ("capture", row["source"]), ("record in original file", f"{ev.record_index(eid):,}"),
            ("true label", row["label"])] + [(k, v) for k, v in raw.items()
                                             if k not in ("event_id", "source", "label")])
    with b:
        ui.kv_card(f"Fragmented baseline: prediction = {row['pred_fragmented']} "
                   f"{ui.mark(bool(row['frag_ok']))}",
                   [(k, f"{v:.6g}" if isinstance(v, float) else v) for k, v in feats.items()],
                   css_title="lab-frag")
        st.caption(f"The {len(feats)} event features the baseline used (Stage 2 scaled / encoded "
                   f"values, data/processed/stage2; feature list = "
                   f"{ev.FEATURE_PLAN} decision 'kept' = {ev.REPORT} → fragmented.features).")
        ui.note("Baseline confidence is <b>not available</b>: the per-source baseline models "
                "were not saved, only their predictions. No live baseline inference is "
                "possible.")
    with c3:
        ui.kv_card(f"Integrated condition: prediction = {row['pred_integrated']} "
                   f"{ui.mark(bool(row['integ_ok']))}",
                   [("incident_id", I["incident_id"]), ("incident majority label", I["label"]),
                    ("corr_rule", I["corr_rule"])] + [(f, I[f]) for f in ev.model_feature_order()],
                   css_title="lab-integ")
        st.caption(f"The {len(ev.model_feature_order())} incident features the integrated model used "
                   "(data/processed/stage3_incidents; order = models/rf_integrated_features.csv). "
                   "The incident prediction is propagated to every member event.")
        proba = ev.live_proba(ui.model(), pd.DataFrame([I]))
        pr = proba.iloc[0]
        live_arg = str(pr.idxmax())
        saved = str(row["pred_integrated"])
        st.markdown("**Model confidence (live inference with the saved integrated model)**")
        ui.chart(ui.proba_chart(pr))
        ui.check_line(live_arg == saved,
                      f"live argmax = {live_arg}; saved integrated prediction for this "
                      f"incident = {saved}")
        lc = ui.live_check()
        if lc and lc.get("model_unchanged"):
            ui.check_line(lc["n_mismatch"] == 0,
                          f"verify_live_inference.py: live predict agreed with the saved "
                          f"prediction on {lc['n_agree']:,} of {lc['n_test_incidents']:,} test "
                          f"incidents ({lc['checked_utc']})")
        else:
            st.caption("Run verify_live_inference.py to check live vs saved predictions on all "
                       "test incidents.")
        st.caption("predict_proba of the RandomForest = mean of the trees' class "
                   "probabilities; it is a model score, not a calibrated probability.")
    with st.expander("Incident diagnostics (label-derived; not model features)"):
        ui.kv_card("diagnostics", [(k, D[k]) for k in ("source", "src_ip", "dst_ip", "proto",
                                                     "n_events", "label_counts", "label_purity",
                                                     "n_train_events", "n_test_events")])


# ---- event selection ------------------------------------------------------------
with tab_main:
    if len(tbl) == 0:
        st.info("No test event matches this filter.")
    else:
        e1, e2 = st.columns(2)
        pick = e1.selectbox("Inspect an event from this page", tbl["event_id"].tolist(),
                            key=f"det_pick_{key}_{page}")
        typed = e2.text_input("… or type any test event_id", key="det_typed").strip()
        eid = int(pick)
        if typed:
            if typed.isdigit() and test_pos(int(typed)) is not None:
                eid = int(typed)
            else:
                st.warning(f"{typed} is not a held-out test event_id; showing {eid:,}.")
        S.det_selected = eid
        details(preds.iloc[test_pos(eid)])

with tab_diag:
    ui.note("These two models are <b>diagnostic ablations, not thesis conditions</b>: a single "
            "pooled event model over all sources, and the same model enriched with three "
            "incident context features. They answer 'how much of the gap is model pooling vs "
            "incident features?' and are reported separately.")
    dg = rep["diagnostics"]
    rows = []
    for name, key_ in (("pooled event model", "pooled_event_model"),
                       ("enriched event model", "enriched_event_model")):
        r = {"model": name}
        r.update({ui.METRIC_LABEL[m]: ui.fmt(dg[key_][m]) for m in ui.METRICS})
        r["features"] = len(dg[key_]["features"])
        rows.append(r)
    ui.table(pd.DataFrame(rows))
    ui.sources("diagnostics.note", "diagnostics.pooled_event_model",
               "diagnostics.enriched_event_model")
    chosen = int(S.get("det_selected", int(EIDS[0])))
    eid_d = st.number_input("Test event_id (defaults to the event inspected in the first tab)",
                            min_value=0, value=chosen, key=f"det_diag_eid_{chosen}")
    p_ = test_pos(int(eid_d))
    if p_ is not None:
        r = preds.iloc[p_]
        ui.table(pd.DataFrame([{
            "event_id": int(r["event_id"]), "true label": r["label"],
            "fragmented (thesis)": r["pred_fragmented"], "integrated (thesis)": r["pred_integrated"],
            "pooled (diagnostic)": r["pred_pooled"], "enriched (diagnostic)": r["pred_enriched"]}]))
        st.caption("Source: results/diagnostic_event_predictions.csv joined by event_id "
                   "(demo/cache/predictions.parquet).")
    else:
        st.warning("Not a held-out test event_id.")
