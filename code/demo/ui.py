"""Shared styling, cached data accessors and components for the demo pages.

All data comes from :mod:`evidence`; this module only adds Streamlit caching
and presentation. Numbers are never written here - only labels and wording.
"""
from __future__ import annotations

import html
import math
import sys
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
if str(DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(DEMO_DIR))

import altair as alt  # noqa: E402  (bundled with streamlit)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import evidence as ev  # noqa: E402

FRAG = "#3987e5"        # fragmented baseline, everywhere
INTEG = "#d95926"       # integrated condition, everywhere
OK_C, BAD_C, MUTED = "#4caf7d", "#e5534b", "#8b949e"
DIAG_C = "#9a8fc0"      # diagnostic models (not thesis conditions)
COND = {"fragmented": "Fragmented baseline", "integrated": "Integrated (correlated incidents)"}
COND_COLOR = {"fragmented": FRAG, "integrated": INTEG}
METRICS = ("accuracy", "precision_macro", "recall_macro", "f1_macro", "fpr", "fnr")
METRIC_LABEL = {"accuracy": "Accuracy", "precision_macro": "Macro precision",
                "recall_macro": "Macro recall", "f1_macro": "Macro F1",
                "fpr": "False positive rate (FPR)", "fnr": "False negative rate (FNR)"}
LOWER_BETTER = {"fpr", "fnr"}
RQ1 = ("How does the integration and correlation of distributed IoT logs and "
       "alerts affect cybersecurity threat detection accuracy in IoT-enabled "
       "smart home networks?")
TITLE = ("Integrated Information Management for Cybersecurity Risk Mitigation "
         "in IoT-Enabled Smart Home Networks")
REPLAY_BANNER = ("Replay of historical dataset records — no traffic is "
                 "generated or sent.")

CSS = """
<style>
.block-container {padding-top: 2.2rem; max-width: 1400px;}
.lab-banner {border-left: 4px solid #c9a227; background: rgba(201,162,39,0.10);
  padding: .55rem .9rem; border-radius: 4px; margin: .2rem 0 .9rem 0;
  font-weight: 600;}
.lab-note {border-left: 3px solid #5d6b7a; background: rgba(255,255,255,0.03);
  padding: .45rem .8rem; border-radius: 4px; margin: .3rem 0 .6rem 0;
  font-size: .92rem;}
.lab-card {border: 1px solid rgba(255,255,255,0.12); border-radius: 6px;
  padding: .7rem 1rem; background: rgba(255,255,255,0.025); margin-bottom: .6rem;}
.lab-card h4 {margin: 0 0 .35rem 0; font-size: 1.0rem;}
.lab-kv {display: grid; grid-template-columns: max-content 1fr; gap: .1rem .9rem;
  font-size: .88rem;}
.lab-kv .k {color: #8b949e;}
.lab-kv .v {font-family: ui-monospace, Consolas, monospace; word-break: break-all;}
.lab-frag {color: #3987e5; font-weight: 600;}
.lab-integ {color: #d95926; font-weight: 600;}
.lab-ok {color: #4caf7d; font-weight: 700;}
.lab-bad {color: #e5534b; font-weight: 700;}
.lab-src {color: #8b949e; font-size: .78rem; font-family: ui-monospace, Consolas, monospace;}
</style>
"""


# --------------------------------------------------------------------------
# Page setup and evidence / cache gate
# --------------------------------------------------------------------------
def setup(title: str, subtitle: str | None = None, need_cache: bool = True) -> None:
    """Style, evidence check and (optionally) derived-cache check; then title."""
    st.markdown(CSS, unsafe_allow_html=True)
    missing = ev.missing_evidence()
    if missing:
        st.error("Required verified evidence is missing. Run the pipeline "
                 "first (run_all.ps1 in the code folder), then restart the demo.")
        st.code("\n".join(missing))
        st.stop()
    if need_cache:
        status = cache_status()
        if status["state"] != "ok":
            st.error(f"Derived demo cache is {status['state']}: "
                     + "; ".join(status["reasons"]))
            st.caption("The cache (demo/cache/) is derived from verified outputs "
                       "only and can be rebuilt at any time.")
            if st.button("Build / rebuild derived cache now", key="rebuild_cache"):
                with st.spinner("Building demo/cache from verified outputs ..."):
                    ev.build_cache(log=lambda m: None)
                st.cache_data.clear()
                st.cache_resource.clear()
                st.rerun()
            st.stop()
    st.title(title)
    if subtitle:
        st.caption(subtitle)


def sidebar() -> None:
    man = manifest()
    with st.sidebar:
        st.markdown("**Research Demonstration Lab**")
        st.caption("Demonstrates the verified outputs of one recorded pipeline "
                   "run. Nothing is retrained, no traffic is generated or sent.")
        st.caption(f"Run recorded: {man.get('timestamp_utc', 'n/a')}  \n"
                   f"Code snapshot: {man.get('code', {}).get('snapshot_id', '')[:16]}…")
        status = cache_status()
        mark = "✓" if status["state"] == "ok" else "✗"
        st.caption(f"Derived cache: {mark} {status['state']}")
        st.markdown(f"<span class='lab-frag'>■ Fragmented baseline</span><br>"
                    f"<span class='lab-integ'>■ Integrated condition</span>",
                    unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Cached accessors (read-only)
# --------------------------------------------------------------------------
@st.cache_data(ttl=120, show_spinner=False)
def cache_status() -> dict:
    return ev.cache_status()


@st.cache_data(show_spinner=False)
def report() -> dict:
    return ev.load_report()


@st.cache_data(show_spinner=False)
def manifest() -> dict:
    return ev.load_manifest()


@st.cache_data(show_spinner=False)
def source_index() -> pd.DataFrame:
    return ev.source_index()


@st.cache_data(show_spinner=False)
def label_counts() -> pd.DataFrame:
    return ev.label_counts()


@st.cache_data(show_spinner=False)
def meta() -> dict:
    return ev.load_meta()


@st.cache_data(show_spinner=False)
def proto_names() -> dict:
    return ev.proto_names()


@st.cache_resource(show_spinner="Loading saved per-event predictions ...")
def predictions() -> pd.DataFrame:
    """Shared, read-only frame (never mutate it in a page)."""
    return ev.load_predictions()


@st.cache_resource(show_spinner="Loading incident table ...")
def incidents() -> pd.DataFrame:
    return ev.incidents()


@st.cache_resource(show_spinner="Loading incident diagnostics ...")
def diagnostics() -> pd.DataFrame:
    return ev.diagnostics()


@st.cache_resource(show_spinner="Loading the saved integrated model (read-only) ...")
def model():
    return ev.load_model()


@st.cache_data(show_spinner=False)
def saved_incident_pred() -> pd.Series:
    return ev.saved_incident_predictions(predictions())


@st.cache_data(max_entries=8, show_spinner="Selecting events ...")
def class_events(source: str, cls: str) -> tuple[np.ndarray, np.ndarray]:
    return ev.class_events(source, cls)


@st.cache_data(max_entries=32, show_spinner="Reading staged records ...")
def window_rows(source: str, cls: str, start: int, size: int) -> pd.DataFrame:
    ids, _ = class_events(source, cls)
    return ev.event_rows(ids[start:start + size])


@st.cache_data(max_entries=16, show_spinner="Collecting incident members ...")
def incident_members(incident_id: str) -> dict:
    return ev.incident_members(incident_id)


@st.cache_data(max_entries=64, show_spinner=False)
def compare_with_raw(event_id: int) -> dict:
    return ev.compare_with_raw(event_id)


@st.cache_data(show_spinner=False)
def alert_reduction_recomputed() -> pd.DataFrame:
    return ev.alert_reduction_recomputed()


@st.cache_data(show_spinner="Computing SHA-256 of the artefacts ...")
def artefact_table() -> pd.DataFrame:
    return ev.artefact_table()


@st.cache_data(show_spinner=False)
def live_check() -> dict | None:
    return ev.load_live_check()


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------
def fmt(v, digits: int = 4) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float) and math.isnan(v):
        return "undefined (NaN)"
    if isinstance(v, (int, np.integer)) and not isinstance(v, bool):
        return f"{int(v):,}"
    return f"{float(v):.{digits}f}"


def fmt_pct(v, digits: int = 2) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "undefined (NaN)"
    return f"{100 * float(v):.{digits}f}%"


def fmt_diff(v, digits: int = 4) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "undefined (NaN)"
    return f"{float(v):+.{digits}f}"


def mark(ok: bool) -> str:
    return "✓" if ok else "✗"


def better_of(metric: str, frag: float, integ: float) -> str:
    """Condition with the better value, from the numbers and the direction."""
    if frag == integ:
        return "tie"
    lower = metric in LOWER_BETTER
    return "fragmented" if (frag < integ) == lower else "integrated"


# --------------------------------------------------------------------------
# Components
# --------------------------------------------------------------------------
def banner(text: str) -> None:
    st.markdown(f"<div class='lab-banner'>{html.escape(text)}</div>",
                unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f"<div class='lab-note'>{text}</div>", unsafe_allow_html=True)


def sources(*paths: str, file: str = ev.REPORT, label: str = "Source") -> None:
    """Caption naming the JSON paths a block was read from."""
    items = "<br>".join(html.escape(ev.src(p, file)) for p in paths)
    st.markdown(f"<div class='lab-src'>{label}: <br>{items}</div>",
                unsafe_allow_html=True)


def sources_expander(paths: list[tuple[str, str]], title: str = "Data sources") -> None:
    """Expander listing (file, json path) pairs."""
    with st.expander(title):
        for f, p in paths:
            st.markdown(f"<div class='lab-src'>{html.escape(ev.src(p, f) if p else f)}</div>",
                        unsafe_allow_html=True)


def kv_card(title: str, items: list[tuple[str, object]], css_title: str = "") -> None:
    rows = "".join(f"<div class='k'>{html.escape(str(k))}</div>"
                   f"<div class='v'>{html.escape(str(v))}</div>" for k, v in items)
    st.markdown(f"<div class='lab-card'><h4 class='{css_title}'>{html.escape(title)}</h4>"
                f"<div class='lab-kv'>{rows}</div></div>", unsafe_allow_html=True)


def table(df: pd.DataFrame, thousands: bool = False, **kw) -> None:
    """st.dataframe at full width (``width`` API, older-version fallback).

    ``thousands``: show integer columns with thousands separators (display
    only; the values stay numeric).
    """
    kw.setdefault("hide_index", True)
    if thousands:
        cfg = dict(kw.pop("column_config", None) or {})
        for c in df.columns:
            if pd.api.types.is_integer_dtype(df[c]) and c not in cfg:
                cfg[c] = st.column_config.NumberColumn(format="localized")
        kw["column_config"] = cfg
    try:
        st.dataframe(df, width="stretch", **kw)
    except Exception:  # older Streamlit without width="stretch"
        st.dataframe(df, use_container_width=True, **kw)


def chart(c: alt.Chart) -> None:
    try:
        st.altair_chart(c, width="stretch")
    except Exception:  # older Streamlit without width="stretch"
        st.altair_chart(c, use_container_width=True)


def checks_table(df: pd.DataFrame, ok_col: str = "ok") -> None:
    show = df.copy()
    show[ok_col] = show[ok_col].map(mark)
    for c in show.columns:
        if show[c].dtype == object:
            show[c] = show[c].astype(str)
    table(show)


def check_line(ok: bool, text: str) -> None:
    cls = "lab-ok" if ok else "lab-bad"
    st.markdown(f"<span class='{cls}'>{mark(ok)}</span> {html.escape(text)}",
                unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Charts (Altair, bundled with Streamlit)
# --------------------------------------------------------------------------
COND_SHORT = {"fragmented": "Fragmented baseline", "integrated": "Integrated"}
UTC_FMT = "%Y-%m-%d %H:%M:%S"
PROBA_CLASSES = ("benign", "c2", "dos", "malware", "recon")


def utc_x(field: str, title: str = "time (UTC)", fmt: str = "%m-%d %H:%M:%S") -> alt.X:
    """Temporal x encoding rendered in UTC (utc scale and utc label format).

    Without this Vega-Lite draws timestamps in the browser's local time zone.
    On a utc scale Vega-Lite applies the axis ``format`` with utcFormat (an
    explicit formatType="utc" is not honoured by the renderer and drops the
    format).
    """
    return alt.X(field, type="temporal", title=title, scale=alt.Scale(type="utc"),
                 axis=alt.Axis(format=fmt, labelAngle=-30, labelOverlap=True))


def time_fmt(span_s: float) -> str:
    """Compact UTC axis label format for a time range of ``span_s`` seconds."""
    return "%H:%M:%S" if span_s < 86_400 else "%m-%d %H:%M"


def axis_title(start: float | None, span_s: float) -> str:
    """Axis title; names the start date when the labels show time of day only."""
    if start is None or span_s >= 86_400:
        return "time (UTC)"
    return f"time (UTC), from {ev.to_utc([start])[0][:10]}"


def grouped_bars(df: pd.DataFrame, x: str, value: str, title_y: str | None = None,
                 domain: list[float] | None = None, height: int = 230,
                 x_sort: list[str] | None = None) -> alt.Chart:
    """Bars per ``x`` with the two conditions side by side (xOffset)."""
    y_scale = alt.Scale(domain=domain) if domain else alt.Scale(zero=True)
    return (alt.Chart(df).mark_bar()
            .encode(x=alt.X(f"{x}:N", title=None, sort=x_sort,
                            axis=alt.Axis(labelAngle=0, labelLimit=160)),
                    xOffset=alt.XOffset("condition:N", sort=list(COND_SHORT.values())),
                    y=alt.Y(f"{value}:Q", title=title_y, scale=y_scale),
                    color=alt.Color("condition:N", sort=list(COND_SHORT.values()),
                                    scale=alt.Scale(domain=list(COND_SHORT.values()),
                                                    range=[FRAG, INTEG]),
                                    legend=alt.Legend(orient="bottom", title=None,
                                                      labelLimit=300)),
                    tooltip=[f"{x}:N", "condition:N", alt.Tooltip(f"{value}:Q", format=".4f")])
            .properties(height=height))


def metric_bars(df: pd.DataFrame, domain: list[float] | None = (0, 1),
                title_y: str | None = None) -> alt.Chart:
    """Grouped bars; df columns: metric, condition (short label), value."""
    return grouped_bars(df, "metric", "value", title_y=title_y,
                        domain=list(domain) if domain else None,
                        x_sort=list(dict.fromkeys(df["metric"])))


def proba_chart(proba: pd.Series) -> alt.Chart:
    """Horizontal bars of class probabilities in a fixed class order, values as text."""
    order = [c for c in PROBA_CLASSES if c in proba.index] + \
            [c for c in proba.index if c not in PROBA_CLASSES]
    df = pd.DataFrame({"class": order, "probability": [float(proba[c]) for c in order]})
    df["text"] = [f"{p:.3f}" for p in df["probability"]]
    base = alt.Chart(df).encode(
        y=alt.Y("class:N", sort=order, title=None,
                axis=alt.Axis(labelOverlap=False, labelLimit=120)),
        x=alt.X("probability:Q", scale=alt.Scale(domain=[0, 1.15]),
                axis=alt.Axis(values=[0, 0.25, 0.5, 0.75, 1.0], format=".2f")))
    bars = base.mark_bar(color=INTEG).encode(
        tooltip=["class", alt.Tooltip("probability:Q", format=".4f")])
    text = base.mark_text(align="left", dx=4, color="#e3e6ea").encode(text="text:N")
    return (bars + text).properties(height=34 * len(order) + 20)


def window_scatter(win: pd.DataFrame, pos: int, first_seq: int) -> alt.Chart:
    """Replay window: event time (UTC) vs replay position, current event highlighted."""
    w = pd.DataFrame({
        "t": pd.to_datetime(np.round(win["ts_epoch"].to_numpy(dtype="float64") * 1e6),
                            unit="us", utc=True),
        "seq": np.arange(len(win)) + first_seq,
        "current": np.arange(len(win)) == pos,
        "event_id": win["event_id"].to_numpy(), "time (UTC)": win["ts_utc"].to_numpy(),
        "src_ip": win["src_ip"].to_numpy(), "dst_ip": win["dst_ip"].to_numpy(),
        "proto": win["proto"].to_numpy(), "label": win["label"].to_numpy()})
    span = float(np.nanmax(win["ts_epoch"]) - np.nanmin(win["ts_epoch"])) if len(win) else 0.0
    return alt.Chart(w).mark_circle().encode(
        x=utc_x("t", title=axis_title(float(np.nanmin(win["ts_epoch"])) if len(win) else None, span),
                fmt=time_fmt(span)),
        y=alt.Y("seq:Q", title="event # in replay", scale=alt.Scale(zero=False)),
        color=alt.condition("datum.current", alt.value(INTEG), alt.value(MUTED)),
        size=alt.condition("datum.current", alt.value(160), alt.value(28)),
        tooltip=["event_id", "time (UTC)", "src_ip", "dst_ip", "proto", "label"]
    ).properties(title="Events in this window", height=240)


def cm_chart(cm, classes: list[str], color: str, title: str) -> alt.Chart:
    m = np.asarray(cm, dtype="int64")
    rows = m.sum(axis=1, keepdims=True)
    pct = np.divide(m, rows, out=np.zeros_like(m, dtype=float), where=rows > 0)
    df = pd.DataFrame([{"true": classes[i], "predicted": classes[j],
                        "count": int(m[i, j]), "row_pct": float(pct[i, j])}
                       for i in range(len(classes)) for j in range(len(classes))])
    df["label"] = [f"{c:,} | {p:.1%}" for c, p in zip(df["count"], df["row_pct"])]
    base = alt.Chart(df).encode(
        x=alt.X("predicted:N", sort=classes, title="predicted"),
        y=alt.Y("true:N", sort=classes, title="true"))
    heat = base.mark_rect().encode(
        color=alt.Color("row_pct:Q", scale=alt.Scale(range=["#161b22", color], domain=[0, 1]),
                        legend=alt.Legend(title="row %", format=".0%")),
        tooltip=["true", "predicted", alt.Tooltip("count:Q", format=","),
                 alt.Tooltip("row_pct:Q", format=".2%")])
    text = base.mark_text(fontSize=11).encode(
        text="label:N",
        color=alt.condition("datum.row_pct > 0.55", alt.value("#0f1318"), alt.value("#e3e6ea")))
    return (heat + text).properties(title=title, height=300)


def time_hist(ts: np.ndarray, labels: np.ndarray | None = None, bins: int = 60,
              marker_ts: float | None = None, color: str = INTEG,
              title: str = "") -> alt.Chart:
    """Histogram of epoch timestamps (UTC), optionally stacked by label."""
    ts = np.asarray(ts, dtype="float64")
    keep = np.isfinite(ts)
    ts = ts[keep]
    if labels is not None:
        labels = np.asarray(labels).astype(str)[keep]
    if len(ts) == 0:
        return alt.Chart(pd.DataFrame({"t": []})).mark_bar()
    lo, hi = float(ts.min()), float(ts.max())
    if hi <= lo:
        hi = lo + 1.0
    edges = np.linspace(lo, hi, bins + 1)
    rows = []
    groups = [("events", ts)] if labels is None else [
        (lab, ts[labels == lab]) for lab in sorted(set(labels))]
    for name, vals in groups:
        h, _ = np.histogram(vals, bins=edges)
        for i, c in enumerate(h):
            if c:
                rows.append({"start": edges[i], "end": edges[i + 1], "events": int(c),
                             "group": name})
    df = pd.DataFrame(rows)
    df["start_utc"] = pd.to_datetime(df["start"], unit="s", utc=True)
    df["end_utc"] = pd.to_datetime(df["end"], unit="s", utc=True)
    # tooltip text is pre-formatted UTC, so no browser-local conversion happens
    df["bin start (UTC)"] = df["start_utc"].dt.strftime(UTC_FMT)
    df["bin end (UTC)"] = df["end_utc"].dt.strftime(UTC_FMT)
    enc_color = (alt.value(color) if labels is None
                 else alt.Color("group:N", title="label"))
    fmt = time_fmt(hi - lo)
    chart = alt.Chart(df).mark_bar().encode(
        x=utc_x("start_utc", title=axis_title(lo, hi - lo), fmt=fmt), x2="end_utc:T",
        y=alt.Y("sum(events):Q", title="events", stack=True), color=enc_color,
        tooltip=["bin start (UTC)", "bin end (UTC)",
                 alt.Tooltip("sum(events):Q", title="events"), "group:N"])
    if marker_ts is not None and np.isfinite(marker_ts):
        rule = alt.Chart(pd.DataFrame({"t": [pd.to_datetime(marker_ts, unit="s", utc=True)]})
                         ).mark_rule(color="#f2f2f2", strokeDash=[4, 3]).encode(
            x=utc_x("t", title=axis_title(lo, hi - lo), fmt=fmt))   # same title: no merged double title
        chart = chart + rule
    return chart.properties(title=title, height=230)


def limitations(rep: dict, man: dict) -> list[tuple[str, str, list[str]]]:
    """(heading, text, source paths) for every limitation; numbers from files."""
    ar = rep["alert_reduction_by_dataset"]["overall"]
    scope = man["config"]["pipeline.config"]["CORRELATION_SCOPE"]
    window = man["config"]["pipeline.config"]["CORRELATION_WINDOW_S"]
    small = rep["robustness"]["small_incidents"]
    n_test = small["n_events_kept"] + small["n_events_excluded"]
    dup = rep["diagnostics"]["duplicates"]
    nov = dup["novel_only_metrics"]
    mc = rep["model_config"]
    boot = rep["bootstrap"]
    conf, absent = ev.classes_absent()
    cats = pd.DataFrame(meta()["botiot_categories"])
    dos_cats = (cats[cats["label"] == "dos"].groupby("category")["events"].sum()
                if not cats.empty else pd.Series(dtype="int64"))
    models = sorted(p.name for p in ev.path("models").glob("*"))
    frag = rep["fragmented"]
    single = [s for s, v in frag["per_source"].items() if "single-class" in str(v.get("note", ""))]
    out = [
        ("No cross-source correlation",
         f"Correlation scope is \"{scope}\": the key includes the source capture, so "
         f"events from different captures or datasets are never merged. Cross-source "
         f"incidents in this run: {ar['cross_source_incidents']:,}. The demo therefore "
         f"makes no claim about cross-capture correlation.",
         [f"{ev.MANIFEST} → config.pipeline.config.CORRELATION_SCOPE",
          f"{ev.REPORT} → alert_reduction_by_dataset.overall.cross_source_incidents"]),
        ("A few giant incidents dominate the event-level scores",
         f"{small['n_incidents_excluded']:,} test incidents with more than "
         f"{small['max_incident_events']:,} events hold {small['n_events_excluded']:,} of "
         f"{n_test:,} test events ({fmt_pct(small['n_events_excluded'] / n_test)}). "
         f"Restricted to the remaining {small['n_events_kept']:,} events, macro F1 is "
         f"{fmt(small['fragmented']['f1_macro'])} (fragmented) vs "
         f"{fmt(small['integrated']['f1_macro'])} (integrated).",
         [f"{ev.REPORT} → robustness.small_incidents"]),
        ("Within-capture evaluation and duplicates",
         f"Train and test events come from the same captures (split by hashed "
         f"correlation key within a {window} s window). {fmt_pct(dup['fraction_all'])} "
         f"of test events have an exact feature-vector duplicate among train events. On "
         f"the {dup['n_novel']:,} novel test events, macro F1 is "
         f"{fmt(nov['fragmented']['f1_macro'])} (fragmented) vs "
         f"{fmt(nov['integrated']['f1_macro'])} (integrated).",
         [f"{ev.REPORT} → diagnostics.duplicates.fraction_all",
          f"{ev.REPORT} → diagnostics.duplicates.novel_only_metrics"]),
        ("DoS and DDoS merged",
         "Bot-IoT categories mapped to the single class 'dos': "
         + ", ".join(f"{k} = {int(v):,} events" for k, v in dos_cats.items())
         + " (staged category column in data/interim).",
         ["demo/cache/meta.json → botiot_categories (derived from data/interim)"]),
        ("Classes absent from the data",
         f"Configured vocabulary: {', '.join(conf)}. No event carries: "
         f"{', '.join(absent) if absent else 'none'}.",
         [f"{ev.MANIFEST} → config.pipeline.config.CLASSES",
          "demo/cache/meta.json → label_counts (derived from data/interim)"]),
        ("One seed, one configuration",
         f"A single run: random_state = {mc['random_state']}, n_estimators = "
         f"{mc['n_estimators']}, max_depth = {mc['max_depth']}, "
         f"train budget {mc['train_budget_per_class']:,} per class. Variance across seeds "
         f"or configurations was not measured.",
         [f"{ev.REPORT} → model_config"]),
        ("Bootstrap intervals are not a significance test",
         f"{boot['method']}; {boot['interval']}; n_boot = {boot['n_boot']:,}. "
         f"{boot['note']}.",
         [f"{ev.REPORT} → bootstrap.method / interval / note"]),
        ("Baseline models were not saved",
         f"models/ contains only: {', '.join(models)}. The {frag['n_sources']} per-source "
         f"baseline models ({frag['n_rf_models']} Random Forests; "
         f"{len(single)} single-class sources predict their one class) exist only as "
         f"saved predictions, so there is no live baseline inference and no baseline "
         f"confidence.",
         [f"{ev.REPORT} → fragmented.n_sources / n_rf_models / per_source.*.note",
          "models/ (directory listing)"]),
    ]
    return out


def show_limitations(rep: dict, man: dict) -> None:
    for head, text, paths in limitations(rep, man):
        st.markdown(f"**{head}.** {html.escape(text)}")
        st.markdown("<div class='lab-src'>" + "<br>".join(html.escape(p) for p in paths)
                    + "</div>", unsafe_allow_html=True)
