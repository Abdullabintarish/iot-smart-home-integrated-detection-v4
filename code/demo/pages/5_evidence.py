"""Page 5 - Research Evidence Explorer: every reported number and its source."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import evidence as ev  # noqa: E402
import ui  # noqa: E402

ui.setup("Research Evidence Explorer",
         "Metrics, confusion matrices, robustness checks and artefact hashes of the "
         "verified run, each with its source.")
rep, man = ui.report(), ui.manifest()
CONDS = ("fragmented", "integrated")

tabs = st.tabs(["Metrics", "Confusion matrices", "From matrix to metrics",
                "Per class / per capture", "Robustness & bootstrap", "Alert reduction",
                "Diagnostics", "Limitations", "Artefacts & figures"])

# ---- metrics ----------------------------------------------------------------
with tabs[0]:
    rows = []
    for m in ui.METRICS:
        f, i = rep["fragmented"][m], rep["integrated"][m]
        rows.append({"metric": ui.METRIC_LABEL[m], "fragmented": ui.fmt(f),
                     "integrated": ui.fmt(i), "difference (integrated − fragmented)": ui.fmt_diff(i - f),
                     "better (derived)": ui.better_of(m, f, i),
                     "JSON path": f"fragmented.{m} / integrated.{m}"})
    ui.table(pd.DataFrame(rows))
    ui.sources(*[f"{c}.{m}" for c in CONDS for m in ui.METRICS])
    st.markdown("**Training / inference and cross-validation**")
    keys = ["n_train", "n_test", "n_features", "train_time_s", "predict_time_s",
            "predict_us_per_event", "cv_kind", "cv_f1_mean", "cv_f1_std"]
    ui.table(pd.DataFrame([{"field": k, **{c: ui.fmt(rep[c].get(k)) if not isinstance(rep[c].get(k), str)
                                           else rep[c].get(k) for c in CONDS}} for k in keys]))
    ui.sources(*[f"{c}.{k}" for c in CONDS for k in ("n_train", "train_time_s", "cv_f1_mean")])
    il = rep["integrated_incident_level"]
    st.markdown("**Integrated model at incident level (secondary view; target = incident "
                "majority label)**")
    ui.table(pd.DataFrame([{ui.METRIC_LABEL[m]: ui.fmt(il[m]) for m in ui.METRICS}
                           | {"test incidents": f"{il['n_test_incidents']:,}"}]))
    ui.sources("integrated_incident_level")

# ---- confusion matrices -----------------------------------------------------
with tabs[1]:
    cols = st.columns(2)
    for col, c in zip(cols, CONDS):
        with col:
            r = rep[c]
            ui.chart(ui.cm_chart(r["confusion_matrix"], r["classes"], ui.COND_COLOR[c],
                                 f"{ui.COND[c]} (counts | row %)"))
            cm = np.asarray(r["confusion_matrix"])
            df = pd.DataFrame(cm, index=[f"true {k}" for k in r["classes"]],
                              columns=[f"pred {k}" for k in r["classes"]])
            st.dataframe(df)
            ui.sources(f"{c}.confusion_matrix", f"{c}.classes")
    st.caption("Rows are true classes, columns predicted classes; row % = share of the true "
               "class's events.")

# ---- from matrix to metrics -------------------------------------------------
with tabs[2]:
    a, b = st.columns(2)
    c = a.radio("Condition", CONDS, format_func=lambda k: ui.COND[k], horizontal=True,
                key="ev_cm_cond")
    r = rep[c]
    classes = r["classes"]
    k = b.selectbox("Class", classes, key="ev_cm_class")
    calc = ev.metrics_from_cm(r["confusion_matrix"], classes)
    pc_ = calc["per_class"][k]
    cnt = ev.cm_class_counts(r["confusion_matrix"], classes, k)
    m = st.columns(4)
    for i, n in enumerate(("TP", "FP", "FN", "TN")):
        m[i].metric(n, f"{cnt[n]:,}")
    st.caption(f"TP = cell [{k}, {k}]; FP = column '{k}' minus TP; FN = row '{k}' minus TP; "
               f"TN = all remaining events (one-vs-rest).")
    P, R, F = pc_["precision"], pc_["recall"], pc_["f1"]
    st.latex(rf"\text{{precision}} = \frac{{TP}}{{TP+FP}} = \frac{{{cnt['TP']:,}}}{{{cnt['TP']:,} + {cnt['FP']:,}}} = {P:.6f}")
    st.latex(rf"\text{{recall}} = \frac{{TP}}{{TP+FN}} = \frac{{{cnt['TP']:,}}}{{{cnt['TP']:,} + {cnt['FN']:,}}} = {R:.6f}")
    st.latex(rf"F_1 = \frac{{2PR}}{{P+R}} = {F:.6f}")
    js = r["per_class"][k]
    checks = [
        (f"precision[{k}]", P, js["precision"], f"{c}.per_class.{k}.precision"),
        (f"recall[{k}]", R, js["recall"], f"{c}.per_class.{k}.recall"),
        (f"f1[{k}]", F, js["f1"], f"{c}.per_class.{k}.f1"),
        ("accuracy = trace / total", calc["accuracy"], r["accuracy"], f"{c}.accuracy"),
        ("macro precision = mean of per-class precision", calc["precision_macro"],
         r["precision_macro"], f"{c}.precision_macro"),
        ("macro recall = mean of per-class recall", calc["recall_macro"], r["recall_macro"],
         f"{c}.recall_macro"),
        ("macro F1 = mean of per-class F1", calc["f1_macro"], r["f1_macro"], f"{c}.f1_macro"),
        (f"FPR = benign predicted as attack / benign = {calc['fp_binary']:,} / {calc['n_negative']:,}",
         calc["fpr"], r["fpr"], f"{c}.fpr"),
        (f"FNR = attack predicted as benign / attack = {calc['fn_binary']:,} / {calc['n_positive']:,}",
         calc["fnr"], r["fnr"], f"{c}.fnr"),
    ]
    st.markdown("**Live consistency check: values computed from the matrix vs the JSON**")
    ui.checks_table(pd.DataFrame([{"quantity": q, "computed from matrix": f"{x:.12f}",
                                   "value in JSON": f"{y:.12f}", "JSON path": p,
                                   "ok": ev.close(x, y)} for q, x, y, p in checks]))
    st.caption("Macro averages are unweighted means over the classes in the matrix (the union "
               "of true and predicted classes, sklearn's default). Binary rates treat benign as "
               "negative and every other class as positive.")

# ---- per class / per capture -----------------------------------------------------
with tabs[3]:
    pcf = pd.DataFrame([{"class": k, "condition": ui.COND_SHORT[c], "F1": v["f1"]}
                        for c in CONDS for k, v in rep[c]["per_class"].items()])
    ui.chart(ui.grouped_bars(pcf, "class", "F1", title_y="F1", domain=[0, 1]))
    ui.table(pd.DataFrame([{"class": k, "support": v["support"],
                            **{f"{c} {q}": ui.fmt(rep[c]["per_class"][k][q])
                               for c in CONDS for q in ("precision", "recall", "f1")}}
                           for k, v in rep["fragmented"]["per_class"].items()]), thousands=True)
    ui.sources("fragmented.per_class", "integrated.per_class")
    st.markdown("**Per capture (held-out test events of each capture)**")
    rows = []
    for s in rep["fragmented"]["per_source"]:
        f, i = rep["fragmented"]["per_source"][s], rep["integrated"]["per_source"].get(s, {})
        rows.append({"capture": s, "test events": f.get("n_test"),
                     "frag accuracy": ui.fmt(f.get("accuracy")), "integ accuracy": ui.fmt(i.get("accuracy")),
                     "frag macro F1": ui.fmt(f.get("f1_macro")), "integ macro F1": ui.fmt(i.get("f1_macro")),
                     "frag FPR": ui.fmt(f.get("fpr")), "integ FPR": ui.fmt(i.get("fpr")),
                     "frag FNR": ui.fmt(f.get("fnr")), "integ FNR": ui.fmt(i.get("fnr")),
                     "note": "; ".join(x for x in (f.get("note"), f.get("metric_note")) if x)})
    ui.table(pd.DataFrame(rows), thousands=True)
    ui.sources("fragmented.per_source.*", "integrated.per_source.*")

# ---- robustness & bootstrap ----------------------------------------------------
with tabs[4]:
    rb = rep["robustness"]
    for key, title in (("small_incidents", "Small incidents only"),
                       ("incident_majority_vote", "Incident majority vote")):
        d = rb[key]
        st.markdown(f"**{title}** — {d['rule']}")
        ui.table(pd.DataFrame([{"condition": ui.COND[c], **{ui.METRIC_LABEL[m]: ui.fmt(d[c].get(m))
                                                           for m in ui.METRICS},
                                "n": f"{d[c]['n_samples']:,}"} for c in CONDS]))
        extra = {k_: v for k_, v in d.items() if k_ not in CONDS and k_ != "rule"}
        st.caption(" · ".join(f"{k_} = {v:,}" if isinstance(v, int) else f"{k_} = {v}"
                                   for k_, v in extra.items()))
        ui.sources(f"robustness.{key}")
    bt = rep["bootstrap"]
    st.markdown("**Clustered bootstrap intervals**")
    ui.note(f"{bt['method']}. {bt['interval']}. n_boot = {bt['n_boot']:,}, seed = {bt['seed']}, "
            f"{bt['n_incidents']:,} incidents / {bt['n_events']:,} events. "
            f"<b>{bt['note']}.</b>")
    brow = []
    for grp in ("fragmented", "integrated", "difference"):
        for m, v in bt[grp].items():
            brow.append({"block": grp, "metric": ui.METRIC_LABEL.get(m, m), "point": ui.fmt(v["point"]),
                         "95% CI low": ui.fmt(v["ci_low"]), "95% CI high": ui.fmt(v["ci_high"]),
                         "replicate mean": ui.fmt(v["mean"]),
                         "difference CI excludes 0": (ui.mark(v["ci_low"] > 0 or v["ci_high"] < 0)
                                                      if grp == "difference" else "")})
    ui.table(pd.DataFrame(brow))
    st.caption("difference = integrated − fragmented. A percentile interval that excludes 0 "
               "describes the resampling spread; it is not a hypothesis test.")
    ui.sources("bootstrap.method", "bootstrap.interval", "bootstrap.note", "bootstrap.difference")

# ---- alert reduction -------------------------------------------------------------
with tabs[5]:
    ar = rep["alert_reduction"]
    ard = rep["alert_reduction_by_dataset"]
    st.markdown(f"Overall: **{ar['raw_alerts']:,}** raw alerts → **{ar['unified_incidents']:,}** "
                f"unified incidents; reduction 1 − {ar['unified_incidents']:,}/{ar['raw_alerts']:,} "
                f"= **{ar['alert_reduction']:.6f}**; mean {ar['mean_alerts_per_incident']:.4f} alerts "
                f"per incident; cross-source incidents: {ar['cross_source_incidents']:,}.")
    ui.sources("alert_reduction")
    ui.table(pd.DataFrame([{"capture": s, **v} for s, v in ard["per_source"].items()]), thousands=True)
    ui.table(pd.DataFrame([{"dataset": s, **v} for s, v in ard["per_dataset"].items()]), thousands=True)
    ui.sources("alert_reduction_by_dataset.per_source", "alert_reduction_by_dataset.per_dataset")
    st.caption(ard["family_rule"])

# ---- diagnostics -----------------------------------------------------------------
with tabs[6]:
    dg = rep["diagnostics"]
    ui.note(f"<b>Not thesis conditions.</b> {dg['note']}.")
    ui.table(pd.DataFrame([{"model": k, **{ui.METRIC_LABEL[m]: ui.fmt(dg[k][m]) for m in ui.METRICS},
                            "features": len(dg[k]["features"]), "n_train": f"{dg[k]['n_train']:,}"}
                           for k in ("pooled_event_model", "enriched_event_model")]))
    ui.sources("diagnostics.pooled_event_model", "diagnostics.enriched_event_model")
    du = dg["duplicates"]
    st.markdown(f"**Train/test duplicates** — {du['definition']}: "
                f"{ui.fmt_pct(du['fraction_all'])} of test events; novel test events: {du['n_novel']:,}.")
    ui.table(pd.DataFrame([{"class": k, "duplicates": v["n_dup"], "events": v["n"],
                            "fraction": ui.fmt_pct(v["fraction"])} for k, v in du["by_class"].items()]))
    ui.table(pd.DataFrame([{"model": k, **{ui.METRIC_LABEL[m]: ui.fmt(v[m]) for m in ui.METRICS},
                            "n": f"{v['n_samples']:,}"} for k, v in du["novel_only_metrics"].items()]))
    ui.sources("diagnostics.duplicates")

# ---- limitations -----------------------------------------------------------------
with tabs[7]:
    ui.show_limitations(rep, man)

# ---- artefacts & figures ---------------------------------------------------------
with tabs[8]:
    st.markdown("**Artefacts of the verified run (SHA-256 computed now, cached per session)**")
    if st.toggle("Compute SHA-256 of all artefacts", value=False, key="ev_hash"):
        at = ui.artefact_table()
        ui.table(at, height=360)
        st.caption(f"{len(at)} files, {at['bytes'].sum():,} bytes.")
    st.markdown("**Raw datasets (hashes recorded in the manifest before Stage 1)**")
    ds = ev.manifest_datasets()
    ui.table(ds[["source", "dataset", "raw_file", "bytes", "sha256", "origin"]])
    if st.button("Re-hash the raw files now and compare (reads every raw file once)",
                 key="ev_rawhash"):
        with st.spinner("Hashing raw files ..."):
            rc = ev.raw_hash_check()
        ui.check_line(bool(rc["match"].all()),
                      f"{int(rc['match'].sum())} of {len(rc)} raw files match the manifest hash")
        ui.table(rc.assign(match=rc["match"].map(ui.mark)))
    ui.sources("datasets.files[*].sha256", file=ev.MANIFEST)
    st.markdown("**Figures from the verified run** (results/report/fig_*.png)")
    figs = sorted(ev.path(ev.REPORT_DIR).glob("fig_*.png"))
    for i in range(0, len(figs), 2):
        cols = st.columns(2)
        for col, f in zip(cols, figs[i:i + 2]):
            col.image(str(f), caption=ev.rel(f))
    with st.expander("results/report/REPORT.md (verbatim)"):
        st.code(ev.path(ev.REPORT_MD).read_text(encoding="utf-8"), language="markdown")
    with st.expander("Run transcripts (results/transcripts/*.log)"):
        for f in sorted(ev.path(ev.TRANSCRIPTS).glob("*.log")):
            st.markdown(f"`{ev.rel(f)}`")
            st.code(f.read_text(encoding="utf-8", errors="replace")[-6000:], language=None)
