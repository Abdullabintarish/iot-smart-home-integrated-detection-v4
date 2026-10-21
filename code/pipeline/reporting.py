"""Evidence and figures for the thesis report.

Produces, under ``results/report/``:

  * terminal screenshots - headless Chrome / Edge renders a real terminal
    transcript to PNG, so the report shows the pipeline's actual output rather
    than a retyped summary
  * charts - baseline vs integrated metrics, per-class F1, confusion matrices
    (counts and row shares), feature importance, alert reduction overall and
    per dataset family
  * a Markdown report tying the two together; its text is generated from the
    Stage 5 JSON, so no result number is written by hand

Everything is generated from the artefacts a pipeline run already writes, so the
report is reproducible rather than assembled by hand.
"""
from __future__ import annotations

import base64
import html
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")          # headless: no display on the VPS
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import CLASSES, CORRELATION_SCOPE, N_SPLITS, RESULTS, TEST_FRACTION

REPORT_DIR = RESULTS / "report"


def _find_chrome() -> str | None:
    """First headless-capable Chromium browser found (Linux, macOS, Windows)."""
    import os
    import shutil
    candidates = [
        "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            candidates += [os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"),
                           os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")]
    for c in candidates:
        if Path(c).exists():
            return c
    for name in ("google-chrome", "chromium", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    return None


CHROME = _find_chrome()

# Palette chosen to stay legible in greyscale print (thesis submissions are
# frequently printed B/W), and to remain distinguishable for colour-blind
# readers: blue/orange rather than red/green.
C_BASE = "#4C6EF5"
C_INTEG = "#F08C00"
C_MUTED = "#868E96"
C_GRID = "#DEE2E6"


def _fig(nrows=1, ncols=1, figsize=(10, 5)):
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    return fig, axes


def _style(ax, title="", xlabel="", ylabel=""):
    ax.set_title(title, fontsize=11, weight="bold", pad=10)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(axis="y", color=C_GRID, linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(labelsize=8)


def metrics_chart(report: dict, out: Path) -> Path:
    """Grouped bars: fragmented vs integrated on each Stage 3.5 metric."""
    comp = pd.DataFrame(report["comparison"])
    comp = comp[comp["fragmented"].notna() & comp["integrated"].notna()]
    lower = (comp["direction"] == "lower_is_better") if "direction" in comp \
        else pd.Series(False, index=comp.index)
    labels = [m.replace("_", "\n") + ("\n(lower is better)" if lo else "")
              for m, lo in zip(comp["metric"], lower)]
    x = np.arange(len(comp))
    w = 0.36

    fig, ax = _fig(figsize=(10, 5.2))
    b1 = ax.bar(x - w / 2, comp["fragmented"], w, label="Fragmented (baseline)",
                color=C_BASE, edgecolor="white")
    b2 = ax.bar(x + w / 2, comp["integrated"], w, label="Integrated (proposed)",
                color=C_INTEG, edgecolor="white")
    for bars in (b1, b2):
        ax.bar_label(bars, fmt="%.3f", fontsize=7, padding=2)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, max(0.1, float(comp[["fragmented", "integrated"]].max().max()) * 1.25))
    _style(ax, "Detection performance: fragmented vs integrated monitoring",
           "", "score")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    p = out / "fig_metrics_comparison.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def confusion_chart(report: dict, out: Path) -> list[Path]:
    """Confusion matrices for both conditions: event counts and row-normalised
    shares in each cell, shaded by the row-normalised share."""
    paths = []
    for cond in ("fragmented", "integrated"):
        block = report.get(cond, {})
        cm = block.get("confusion_matrix")
        classes = block.get("classes")
        if not cm or not classes:
            continue
        m = np.asarray(cm, dtype=float)
        norm = m / np.maximum(m.sum(axis=1, keepdims=True), 1)

        fig, ax = _fig(figsize=(7.2, 6.0))
        im = ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
        ax.set_xticks(range(len(classes)), classes, rotation=45, ha="right", fontsize=7)
        ax.set_yticks(range(len(classes)), classes, fontsize=7)
        ax.set_xlabel("predicted", fontsize=9)
        ax.set_ylabel("actual", fontsize=9)
        ax.set_title(f"Confusion matrix — {cond}\n(event counts; row-normalised "
                     "share in brackets)", fontsize=10, weight="bold")
        for i in range(len(classes)):
            for j in range(len(classes)):
                v = norm[i, j]
                ax.text(j, i, f"{int(m[i, j]):,}\n({v:.2f})", ha="center",
                        va="center", fontsize=6,
                        color="white" if v > 0.55 else "#212529")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04).ax.tick_params(labelsize=7)
        fig.tight_layout()
        p = out / f"fig_confusion_{cond}.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        paths.append(p)
    return paths


def per_class_f1_chart(report: dict, out: Path) -> Path | None:
    """Grouped bars: per-class F1 of both conditions on the test events."""
    pf = report.get("fragmented", {}).get("per_class") or {}
    pi = report.get("integrated", {}).get("per_class") or {}
    classes = sorted(set(pf) | set(pi))
    if not classes:
        return None
    x = np.arange(len(classes))
    w = 0.36
    fig, ax = _fig(figsize=(9, 4.8))
    b1 = ax.bar(x - w / 2, [pf.get(c, {}).get("f1", 0.0) for c in classes], w,
                label="Fragmented (baseline)", color=C_BASE, edgecolor="white")
    b2 = ax.bar(x + w / 2, [pi.get(c, {}).get("f1", 0.0) for c in classes], w,
                label="Integrated (proposed)", color=C_INTEG, edgecolor="white")
    for bars in (b1, b2):
        ax.bar_label(bars, fmt="%.3f", fontsize=7, padding=2)
    ax.set_xticks(x, classes)
    # Headroom above the 1.0 bars so the legend never covers a bar label.
    ax.set_ylim(0, 1.3)
    _style(ax, "Per-class F1 on the held-out test events", "class", "F1")
    ax.legend(frameon=False, fontsize=9, loc="upper center", ncol=2)
    fig.tight_layout()
    p = out / "fig_per_class_f1.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def alert_reduction_by_dataset_chart(report: dict, out: Path) -> Path | None:
    """Events vs incidents per dataset family (log scale), reduction labelled."""
    per = (report.get("alert_reduction_by_dataset") or {}).get("per_dataset") or {}
    if not per:
        return None
    names = sorted(per)
    x = np.arange(len(names))
    w = 0.36
    ev = [per[n]["events"] for n in names]
    inc = [per[n]["incidents"] for n in names]
    fig, ax = _fig(figsize=(8, 4.8))
    b1 = ax.bar(x - w / 2, ev, w, label="events (raw alerts)", color=C_MUTED,
                edgecolor="none")
    b2 = ax.bar(x + w / 2, inc, w, label="incidents (Stage 3)", color=C_INTEG,
                edgecolor="none")
    for bars in (b1, b2):
        ax.bar_label(bars, fmt="{:,}", fontsize=8, padding=2)
    ax.set_yscale("log")
    ax.set_xticks(x, [f"{n}\n({per[n]['alert_reduction'] * 100:.2f}% reduction)"
                      for n in names])
    ax.set_ylim(1, max(ev + inc) * 6)
    _style(ax, "Alert reduction per dataset family (correlation within each "
               "source capture)", "", "count (log scale)")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    p = out / "fig_alert_reduction_by_dataset.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def feature_importance_chart(report: dict, out: Path) -> list[Path]:
    """Top features driving each model — the interpretability the literature
    review flags as a gap (Levshun & Kotenko, 2023)."""
    paths = []
    for cond in ("fragmented", "integrated"):
        fi = report.get(cond, {}).get("feature_importance")
        if not fi:
            continue
        if isinstance(fi, list):
            fi = pd.DataFrame(fi)
        if not isinstance(fi, pd.DataFrame) or fi.empty:
            continue
        fi = fi.head(12).iloc[::-1]
        color = C_BASE if cond == "fragmented" else C_INTEG
        fig, ax = _fig(figsize=(8.4, 4.6))
        ax.barh(fi["feature"], fi["importance"], color=color, edgecolor="none")
        _style(ax, f"Random Forest feature importance — {cond}",
               "Gini importance", "")
        ax.grid(axis="x", color=C_GRID, linewidth=0.6)
        ax.grid(axis="y", visible=False)
        fig.tight_layout()
        p = out / f"fig_importance_{cond}.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        paths.append(p)
    return paths


def funnel_chart(report: dict, out: Path) -> Path | None:
    """Raw alerts -> unified incidents: the correlation stage's compression."""
    red = report.get("alert_reduction", {})
    if not red or not red.get("raw_alerts"):
        return None
    raw = red["raw_alerts"]
    inc = red["unified_incidents"]
    fig, ax = _fig(figsize=(7, 4.4))
    bars = ax.bar(["Raw alerts\n(Stage 1-2 output)", "Unified incidents\n(Stage 3)"],
                  [raw, inc], color=[C_MUTED, C_INTEG], width=0.55, edgecolor="none")
    ax.bar_label(bars, fmt="{:,}", fontsize=10, weight="bold", padding=4)
    _style(ax, f"Alert reduction through event correlation "
               f"({red['alert_reduction'] * 100:.1f}% consolidated)", "", "count")
    ax.set_ylim(0, raw * 1.18)
    fig.tight_layout()
    p = out / "fig_alert_reduction.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def terminal_screenshot(transcript: str, out: Path, title: str = "pipeline run",
                        width: int = 150, max_lines: int = 70,
                        name: str = "run") -> Path | None:
    """Render a terminal transcript to PNG via headless Chrome.

    Chrome draws the text with a real monospace font and CSS, which looks far
    closer to a genuine terminal capture than PIL text rendering does.
    """
    if not CHROME or not Path(CHROME).exists():
        return None
    lines = transcript.rstrip().splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines // 2] + [f"  ... {len(lines) - max_lines} lines elided ...",
                                         *lines[-(max_lines // 2):]]
    body = "\n".join(html.escape(ln) for ln in lines) or "(no output)"
    page = f"""<!doctype html><meta charset="utf-8">
<style>
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:#1e1e2e; font-family:'DejaVu Sans Mono',Consolas,monospace; }}
  .win {{ font-size:12.5px; width:{width}ch; margin:14px; border-radius:8px; overflow:hidden;
          box-shadow:0 4px 18px rgba(0,0,0,.45); }}
  .bar {{ background:#313244; padding:7px 12px; display:flex; align-items:center; }}
  .d {{ width:11px; height:11px; border-radius:50%; margin-right:7px; }}
  .t {{ color:#cdd6f4; font-size:12px; margin-left:10px; }}
  pre {{ margin:0; padding:12px 14px; color:#a6e3a1; font-size:12.5px;
         line-height:1.5; white-space:pre-wrap; overflow-wrap:anywhere; }}
</style>
<div class="win">
  <div class="bar">
    <div class="d" style="background:#f38ba8"></div>
    <div class="d" style="background:#f9e2af"></div>
    <div class="d" style="background:#a6e3a1"></div>
    <div class="t">{html.escape(title)}</div>
  </div>
  <pre>{body}</pre>
</div>"""
    tmp = out / f"_terminal_{name}.html"
    tmp.write_text(page, encoding="utf-8")
    png = out / f"fig_terminal_{name}.png"
    # Long lines wrap rather than clip, so size the window to the wrapped
    # text: ~8.2 px per character at 12.5 px, ~19 px per rendered row.
    rows = sum(max(1, -(-len(ln) // width)) for ln in lines)
    win_w = int(width * 7.6) + 60
    win_h = min(6000, 90 + 19 * rows)
    cmd = [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
           "--hide-scrollbars", "--force-device-scale-factor=2",
           f"--screenshot={png}", f"--window-size={win_w},{win_h}",
           tmp.as_uri()]
    try:
        subprocess.run(cmd, capture_output=True, timeout=90, check=True)
    except (subprocess.SubprocessError, OSError):
        return None
    finally:
        tmp.unlink(missing_ok=True)
    return png if png.exists() and png.stat().st_size > 1000 else None


def _num(v, spec: str = ".4f") -> str:
    """Format a number for a table cell; None / NaN / non-numbers -> n/a."""
    if isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, float, np.number)):
        return "n/a"
    if not np.isfinite(v):
        return "n/a"
    return format(v, spec)


def _metric_name(metric: str, direction: str | None = None) -> str:
    name = metric.replace("_", " ")
    return name + " (lower is better)" if direction == "lower_is_better" else name


_HEADLINE = (("accuracy", "accuracy"), ("f1_macro", "macro F1"), ("fpr", "FPR"),
             ("fnr", "FNR"))


def _headline_row(label: str, m: dict, n_key: str = "n_samples") -> str:
    cells = " | ".join(_num(m.get(k)) for k, _ in _HEADLINE)
    return f"| {label} | {cells} | {_num(m.get(n_key), ',')} |"


def _compare_sentence(frag: dict, integ: dict, metric: str, label: str,
                      lower_is_better: bool = False) -> str | None:
    """'The integrated condition scored lower macro F1 than the baseline
    (X vs Y)', derived from the numbers."""
    f, i = frag.get(metric), integ.get(metric)
    if _num(f) == "n/a" or _num(i) == "n/a":
        return None
    if i == f:
        return f"Both conditions scored the same {label} ({_num(i)})."
    word = "higher" if i > f else "lower"
    better = (i < f) if lower_is_better else (i > f)
    return (f"The integrated condition scored {word} {label} than the baseline "
            f"(integrated {_num(i)} vs baseline {_num(f)}; "
            f"{'better' if better else 'worse'} for the integrated condition).")


def _artefacts(results_dir: Path) -> list[str]:
    """Run artefacts that actually exist, as paths relative to the code root."""
    root = results_dir.parent
    pats = ["results/stage5_report.json", "results/stage5_summary.txt",
            "results/baseline_vs_integrated.csv",
            "results/fragmented_event_predictions.csv",
            "results/integrated_event_predictions.csv",
            "results/diagnostic_event_predictions.csv",
            "results/run_manifest.json", "results/transcripts/*.log",
            "models/*.joblib", "models/*.csv"]
    found: list[str] = []
    for pat in pats:
        found += sorted(p.relative_to(root).as_posix() for p in root.glob(pat)
                        if p.is_file())
    return found


def build_report(report: dict, transcripts: dict[str, str] | None = None,
                 out: Path = REPORT_DIR, results_dir: Path = RESULTS) -> Path:
    """Assemble every figure and write the Markdown report.

    Every number in the text comes from ``report`` (the Stage 5 JSON); the
    sentences that compare conditions are derived from those numbers.
    """
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    transcripts = transcripts or {}

    figs: dict[str, object] = {}
    figs["metrics"] = metrics_chart(report, out)
    figs["per_class"] = per_class_f1_chart(report, out)
    figs["funnel"] = funnel_chart(report, out)
    figs["by_dataset"] = alert_reduction_by_dataset_chart(report, out)
    figs["confusion"] = confusion_chart(report, out)
    figs["importance"] = feature_importance_chart(report, out)
    titles = {"run": "run_pipeline.py - stages 2-5",
              "stage1": "stage1_collect.py - stage 1 collection"}
    for key, text in transcripts.items():
        p = terminal_screenshot(text, out, title=titles.get(key, key), name=key)
        if p:
            figs[f"terminal_{key}"] = p

    frag, integ = report.get("fragmented", {}), report.get("integrated", {})
    red = report.get("alert_reduction", {})
    by_ds = report.get("alert_reduction_by_dataset") or {}
    split = report.get("split") or {}
    comp = pd.DataFrame(report.get("comparison", []))
    sec = iter(range(1, 100))

    lines = [
        "# Integrated Information Management for Cybersecurity Risk Mitigation",
        "## Experimental Results — IoT-Enabled Smart Home Networks",
        "",
        f"*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
        f"by `pipeline.reporting` from `results/stage5_report.json`; every "
        f"number below is read from that file.*",
        "",
    ]
    for k in ("terminal_stage1", "terminal_run"):
        path = figs.get(k)
        if path is not None:
            lines += [f"![terminal]({path.name})", ""]

    # ---- design --------------------------------------------------------------
    lines += [
        f"## {next(sec)}. Design",
        "",
        f"- **Fragmented (baseline):** one Random Forest per source capture "
        f"({_num(frag.get('n_sources'), 'd')} sources, "
        f"{_num(frag.get('n_rf_models'), 'd')} fitted forests; single-class "
        f"sources predict their one class), each trained only on its own "
        f"source's train events with {_num(frag.get('n_features'), 'd')} event "
        f"features.",
        f"- **Integrated (proposed):** one Random Forest over Stage 3 incident "
        f"features ({_num(integ.get('n_features'), 'd')} features); each test "
        f"incident's predicted label is propagated to its member events, which "
        f"are scored against their own event labels.",
        f"- **Correlation scope:** `{CORRELATION_SCOPE}` - incidents are formed "
        f"within one source capture; events of different captures are never "
        f"merged.",
        "- Both conditions use the same Random Forest configuration (section "
        "on model configuration below) and the same metrics.",
        "",
    ]

    # ---- held-out set ----------------------------------------------------------
    n_test = frag.get("n_test")
    same = n_test is not None and n_test == integ.get("n_test")
    n_ev = split.get("n_events")
    n_tr_i, n_te_i = split.get("n_train_incidents"), split.get("n_test_incidents")
    lines += [f"## {next(sec)}. Held-out test set", ""]
    if split:
        share_ev = (n_test / n_ev) if n_test and n_ev else None
        tot_i = (n_tr_i or 0) + (n_te_i or 0)
        share_i = (n_te_i / tot_i) if n_te_i and tot_i else None
        lines += [
            "The train/test split is grouped by Stage 3 correlation group, so "
            "the events of one incident stay on one side "
            f"({_num(split.get('n_mixed_incidents'), ',')} incidents have events "
            f"on both sides). Strategy: {split.get('strategy', 'n/a')}.",
            "",
            "| | Events | Incidents |",
            "|---|---|---|",
            f"| Corpus | {_num(n_ev, ',')} | {_num(tot_i, ',')} |",
            f"| Test | {_num(n_test, ',')} ({_num(share_ev, '.1%')}) | "
            f"{_num(n_te_i, ',')} ({_num(share_i, '.1%')}) |",
            "",
            ("Both conditions are scored on the **identical** "
             f"{_num(n_test, ',')} held-out test events."
             if same else
             "**Warning:** the two conditions report different test-set sizes."),
            "",
        ]

    # ---- headline results ------------------------------------------------------
    lines += [
        f"## {next(sec)}. Results (event level, held-out test events)",
        "",
        "| Metric | Fragmented (baseline) | Integrated (proposed) | "
        "Difference (integrated − baseline) | Better |",
        "|---|---|---|---|---|",
    ]
    for _, r in comp.iterrows():
        lines.append(
            f"| {_metric_name(r['metric'], r.get('direction'))} | "
            f"{_num(r.get('fragmented'))} | {_num(r.get('integrated'))} | "
            f"{_num(r.get('difference'), '+.4f')} | "
            f"{r['better'] if isinstance(r.get('better'), str) else 'n/a'} |")
    lines += ["", "FPR and FNR are error rates: lower is better. "
              "Macro averages use the union of true and predicted classes.", ""]
    for metric, label, lo in (("f1_macro", "macro F1", False),
                              ("accuracy", "accuracy", False),
                              ("fpr", "FPR", True), ("fnr", "FNR", True)):
        s = _compare_sentence(frag, integ, metric, label, lo)
        if s:
            lines.append(f"- {s}")
    lines.append("")
    if figs.get("metrics"):
        lines += [f"![metrics]({figs['metrics'].name})", ""]

    # ---- per-class -------------------------------------------------------------
    pf, pi = frag.get("per_class") or {}, integ.get("per_class") or {}
    if pf or pi:
        lines += ["### Per-class F1", "",
                  "| Class | Test events (support) | F1 fragmented | F1 integrated |",
                  "|---|---|---|---|"]
        for c in sorted(set(pf) | set(pi)):
            sup = (pf.get(c) or pi.get(c) or {}).get("support")
            lines.append(f"| {c} | {_num(sup, ',')} | "
                         f"{_num((pf.get(c) or {}).get('f1'))} | "
                         f"{_num((pi.get(c) or {}).get('f1'))} |")
        lines.append("")
        if figs.get("per_class"):
            lines += [f"![per-class F1]({figs['per_class'].name})", ""]
    for p in figs.get("confusion", []) or []:
        lines += [f"![confusion]({p.name})", ""]

    # ---- incident level (secondary) --------------------------------------------
    lvl = report.get("integrated_incident_level") or {}
    if lvl:
        lines += [
            "### Integrated condition at incident level (secondary)", "",
            "One row per test incident; target = the incident's majority label.",
            "", "| | Accuracy | Macro F1 | FPR | FNR | Incidents |",
            "|---|---|---|---|---|---|",
            _headline_row("Integrated, incident level", lvl), ""]

    # ---- robustness ------------------------------------------------------------
    rob = report.get("robustness") or {}
    if rob:
        sm, vote = rob.get("small_incidents") or {}, rob.get("incident_majority_vote") or {}
        lines += [f"## {next(sec)}. Robustness checks", "",
                  "| Check | Condition | Accuracy | Macro F1 | FPR | FNR | n |",
                  "|---|---|---|---|---|---|---|"]
        for name, blk in ((f"Events in incidents ≤ "
                           f"{_num(sm.get('max_incident_events'), ',')} events", sm),
                          ("Incident majority vote", vote)):
            for cond in ("fragmented", "integrated"):
                m = blk.get(cond)
                if m:
                    cells = " | ".join(_num(m.get(k)) for k, _ in _HEADLINE)
                    lines.append(f"| {name} | {cond} | {cells} | "
                                 f"{_num(m.get('n_samples'), ',')} |")
        lines.append("")
        if sm:
            lines += [
                f"The size-restricted check keeps {_num(sm.get('n_events_kept'), ',')} "
                f"test events in {_num(sm.get('n_incidents_kept'), ',')} incidents "
                f"and excludes {_num(sm.get('n_events_excluded'), ',')} events in "
                f"{_num(sm.get('n_incidents_excluded'), ',')} large incidents.", ""]
        if vote:
            lines += [f"The majority-vote check gives each of the "
                      f"{_num(vote.get('n_incidents'), ',')} test incidents one "
                      f"vote: {vote.get('rule', '')}.", ""]

    # ---- bootstrap -------------------------------------------------------------
    boot = report.get("bootstrap") or {}
    if boot.get("difference"):
        lines += [
            f"## {next(sec)}. Uncertainty: incident-clustered bootstrap", "",
            f"{_num(boot.get('n_boot'), ',')} replicates (seed "
            f"{boot.get('seed')}) resampling the "
            f"{_num(boot.get('n_incidents'), ',')} test incidents with "
            "replacement; all events of a drawn incident are included and both "
            "conditions use the same draws. Cells show the full-sample value "
            "and the 95% percentile interval. **This is a percentile confidence "
            "interval from a clustered bootstrap, not a significance test.**",
            "", "| Metric | Fragmented | Integrated | Difference (integrated − baseline) |",
            "|---|---|---|---|"]
        for m, label in _HEADLINE:
            cells = []
            for blk in ("fragmented", "integrated", "difference"):
                s = (boot.get(blk) or {}).get(m) or {}
                spec = "+.4f" if blk == "difference" else ".4f"
                cells.append(f"{_num(s.get('point'), spec)} "
                             f"[{_num(s.get('ci_low'), spec)}, "
                             f"{_num(s.get('ci_high'), spec)}]")
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        lines.append("")

    # ---- alert consolidation ---------------------------------------------------
    if red or by_ds:
        ov = by_ds.get("overall") or {}
        n_raw = ov.get("events", red.get("raw_alerts"))
        n_inc = ov.get("incidents", red.get("unified_incidents"))
        rate = ov.get("alert_reduction", red.get("alert_reduction"))
        cross = ov.get("cross_source_incidents", red.get("cross_source_incidents"))
        lines += [
            f"## {next(sec)}. Alert consolidation", "",
            f"Within-capture correlation grouped {_num(n_raw, ',')} events into "
            f"{_num(n_inc, ',')} incidents, an overall alert reduction of "
            f"{_num(rate, '.2%')}. The reduction differs strongly between "
            "the datasets:", ""]
        per = by_ds.get("per_dataset") or {}
        if per:
            lines += ["| Dataset | Sources | Events | Incidents | Alert reduction |",
                      "|---|---|---|---|---|"]
            for name in sorted(per):
                d = per[name]
                lines.append(f"| {name} | {_num(d.get('n_sources'), ',')} | "
                             f"{_num(d.get('events'), ',')} | "
                             f"{_num(d.get('incidents'), ',')} | "
                             f"{_num(d.get('alert_reduction'), '.2%')} |")
            lines.append(f"| overall | {_num(len(by_ds.get('per_source') or {}), ',')} | "
                         f"{_num(n_raw, ',')} | {_num(n_inc, ',')} | "
                         f"{_num(rate, '.2%')} |")
            lines.append("")
        lines += [
            f"{_num(cross, ',')} incidents span more than one source; captures "
            "are independent, so no cross-source correlation is claimed.", ""]
    if figs.get("by_dataset"):
        lines += [f"![alert reduction by dataset]({figs['by_dataset'].name})", ""]
    if figs.get("funnel"):
        lines += [f"![alert reduction]({figs['funnel'].name})", ""]

    # ---- diagnostics -----------------------------------------------------------
    diag = report.get("diagnostics") or {}
    rows = [(k, v) for k, v in diag.items() if isinstance(v, dict) and "f1_macro" in v]
    if rows or diag.get("duplicates"):
        lines += [
            f"## {next(sec)}. Diagnostic ablations (not thesis conditions)", "",
            "Same test events, same Random Forest configuration. The pooled "
            "model is one event model over all sources (pooling without "
            "correlation); the enriched model adds the event's incident context "
            "to the event features. They help explain the two conditions and "
            "are **not** part of the thesis comparison.", "",
            "| Model | Accuracy | Macro F1 | FPR | FNR | n |", "|---|---|---|---|---|---|"]
        for k, v in rows:
            lines.append(_headline_row(k.replace("_", " "), v))
        lines.append("")
        dup = diag.get("duplicates") or {}
        if dup:
            lines += [
                f"Train/test duplicates: {_num(dup.get('fraction_all'), '.2%')} of "
                f"test events have an exact event-feature vector that also "
                f"occurs among train events. Metrics on the {_num(dup.get('n_novel'), ',')} novel test "
                "events only:", "",
                "| Model | Accuracy | Macro F1 | FPR | FNR | n |",
                "|---|---|---|---|---|---|"]
            for k, v in (dup.get("novel_only_metrics") or {}).items():
                lines.append(_headline_row(k, v))
            lines.append("")

    # ---- per-source baseline ---------------------------------------------------
    if frag.get("per_source"):
        lines += [
            f"## {next(sec)}. Per-source baseline performance", "",
            "Per-source macro F1 uses the union of that source's true and "
            "predicted classes, so single-class sources can score 1.0.", "",
            "| Source | Accuracy | Macro F1 | FPR | Test events | Note |",
            "|---|---|---|---|---|---|"]
        for src, m in frag["per_source"].items():
            note = "; ".join(x for x in (m.get("note"), m.get("metric_note")) if x)
            lines.append(f"| {src} | {_num(m.get('accuracy'))} | "
                         f"{_num(m.get('f1_macro'))} | {_num(m.get('fpr'))} | "
                         f"{_num(m.get('n_test'), ',')} | {note} |")
        lines.append("")

    # ---- cross-validation ------------------------------------------------------
    if frag.get("cv_f1_mean") is not None or integ.get("cv_f1_mean") is not None:
        skipped = frag.get("cv_sources_skipped") or []
        lines += [
            f"## {next(sec)}. Cross-validation (training data only)", "",
            f"- Baseline: {_num(frag.get('cv_f1_mean'))} ± "
            f"{_num(frag.get('cv_f1_std'))} macro F1 ({frag.get('cv_kind', 'n/a')}), "
            f"covering {_num(frag.get('cv_n_sources'), 'd')} sources"
            + (f"; skipped (single-class or too few incidents per class): "
               f"{', '.join(skipped)}" if skipped else "") + ".",
            f"- Integrated: {_num(integ.get('cv_f1_mean'))} ± "
            f"{_num(integ.get('cv_f1_std'))} macro F1 ({integ.get('cv_kind', 'n/a')}).",
            "",
            "The two CV figures cover different rows, units and label sets, so "
            "they are not directly comparable with each other; the held-out "
            "results above are the comparison.", ""]
        if integ.get("cv_excluded_classes"):
            lines += [f"_Integrated CV excludes classes with fewer than {N_SPLITS} "
                      f"members: {', '.join(integ['cv_excluded_classes'])}._", ""]

    # ---- configuration and features --------------------------------------------
    mc = report.get("model_config") or {}
    fi = integ.get("feature_importance") or []
    if isinstance(fi, pd.DataFrame):
        fi = fi.to_dict(orient="records")
    constant = [r["feature"] for r in fi if r.get("importance") == 0]
    lines += [f"## {next(sec)}. Model configuration and features", ""]
    if mc:
        lines += ["| Parameter | Value |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in mc.items()]
        lines.append("")
    lines += [f"- Fragmented event features ({len(frag.get('features') or [])}): "
              + ", ".join(f"`{f}`" for f in frag.get("features") or []),
              f"- Integrated incident features ({len(integ.get('features') or [])}): "
              + ", ".join(f"`{f}`" for f in integ.get("features") or [])]
    if constant:
        lines.append(f"- Integrated features with zero importance (never used "
                     f"for a split, consistent with being constant in the "
                     f"training sample): {', '.join(f'`{c}`' for c in constant)}")
    lines.append("")
    for p in figs.get("importance", []) or []:
        lines += [f"![importance]({p.name})", ""]

    # ---- caveats ---------------------------------------------------------------
    classes = sorted(set(frag.get("classes") or []) | set(integ.get("classes") or []))
    seen = {e.get("label") for e in split.get("events", [])} | set(classes)
    absent = [c for c in CLASSES if c not in seen]
    lines += [f"## {next(sec)}. Caveats", ""]
    if "dos" in classes:
        lines.append("- **DoS and DDoS share one class.** Vendor labels are mapped "
                     "to a common vocabulary at ingest; DoS and DDoS ground truth "
                     "both become `dos`, so no metric separates them.")
    if absent:
        lines.append(f"- **Classes absent from the data:** "
                     f"{', '.join(f'`{c}`' for c in absent)} are in the label "
                     "vocabulary but no event carries them, so they are not "
                     "evaluated.")
    lines.append("- **Within-capture evaluation.** Train and test events come "
                 "from the same captures, which share hosts and time context; "
                 "the scores are not field performance on unseen networks.")
    if split and n_test and n_ev and n_te_i:
        sm = (rob.get("small_incidents") or {}) if rob else {}
        extra = ""
        if sm.get("n_incidents_excluded"):
            extra = (f" {_num(sm['n_incidents_excluded'], ',')} incidents with more "
                     f"than {_num(sm.get('max_incident_events'), ',')} events hold "
                     f"{_num(sm.get('n_events_excluded'), ',')} of the test events.")
        lines.append(
            f"- **Lumpy split.** The split is by incident, so the test set holds "
            f"{_num(n_test / n_ev, '.1%')} of events but "
            f"{_num(n_te_i / ((n_tr_i or 0) + n_te_i), '.1%')} of incidents "
            f"(nominal test fraction {_num(TEST_FRACTION, '.0%')})." + extra)
    frag_counts: dict[str, int] = {}
    for m in (frag.get("per_source") or {}).values():
        for c, n in (m.get("train_class_counts") or {}).items():
            frag_counts[c] = frag_counts.get(c, 0) + int(n)
    integ_counts = integ.get("train_class_counts") or {}
    if frag_counts or integ_counts:
        lines += ["- **Unequal training sets.** Both use the same per-class "
                  "budget, but the baseline samples events per source while the "
                  "integrated model samples incidents, so the class make-up "
                  "differs:", "",
                  "  | Class | Fragmented train events (all sources) | "
                  "Integrated train incidents |", "  |---|---|---|"]
        for c in sorted(set(frag_counts) | set(integ_counts)):
            lines.append(f"  | {c} | {_num(frag_counts.get(c), ',')} | "
                         f"{_num(integ_counts.get(c), ',')} |")
        lines.append("")
    if constant:
        kept = [f for f in integ.get("features") or [] if f not in constant]
        lines.append(f"- **Constant incident features.** {len(constant)} of the "
                     f"{len(integ.get('features') or [])} incident features have "
                     f"zero importance - the model never splits on them "
                     f"({', '.join(constant)}) - so the integrated model "
                     f"effectively uses {', '.join(kept)}.")
    s = _compare_sentence(frag, integ, "f1_macro", "macro F1")
    if s:
        d = ((boot.get("difference") or {}).get("f1_macro") or {}) if boot else {}
        ci = (f" The 95% clustered-bootstrap percentile interval of the "
              f"difference is [{_num(d.get('ci_low'), '+.4f')}, "
              f"{_num(d.get('ci_high'), '+.4f')}]." if d else "")
        lines.append(f"- **Outcome.** {s}{ci} No claim of statistical "
                     "significance is made.")
    lines += ["", "---", ""]

    arts = _artefacts(Path(results_dir))
    lines.append("Artefacts: " + (", ".join(f"`{a}`" for a in arts)
                                  if arts else "none found"))

    md = out / "REPORT.md"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Machine-readable index so the handoff can be checked programmatically.
    manifest = {k: (v.name if isinstance(v, Path) else
                    [p.name for p in v] if isinstance(v, list) else None)
                for k, v in figs.items()}
    (out / "figures.json").write_text(json.dumps(manifest, indent=2))
    return md
