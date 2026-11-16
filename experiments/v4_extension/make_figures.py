"""Figures for E1 and E2 (PNG, 300 dpi), from the result CSVs only.

    code/.venv/Scripts/python.exe -B experiments/v4_extension/make_figures.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
FIG = RES / "figures"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"
ORDER = ["incident_thin", "incident_rich", "event_only", "event_plus_thin",
         "event_plus_rich", "event_plus_rich_permuted"]


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def e1():
    s = pd.read_csv(RES / "e1" / "runb_summary.csv")
    s = s[(s.window_s == 300) & (s.subset == "all")].set_index("condition").loc[ORDER[::-1]]
    color = [ORANGE if c.startswith("incident") else BLUE for c in s.index]
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.6), sharey=True)
    for ax, (m, sd, title, fmt) in zip(axes, [("f1_mean", "f1_sd", "Macro F1", "{:.4f}"),
                                             ("fpr_mean", "fpr_sd", "False-positive rate", "{:.2%}")]):
        ax.barh(s.index, s[m], xerr=s[sd], color=color, height=0.6, edgecolor="white",
                linewidth=2, error_kw={"ecolor": INK, "elinewidth": 0.8, "capsize": 2})
        for y, v in enumerate(s[m]):
            ax.text(v, y, "  " + fmt.format(v), va="center", fontsize=7.5, color=INK)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        style(ax)
    axes[0].set_xlim(0.80, 1.012)
    axes[1].set_xlim(0, s["fpr_mean"].max() * 1.35)
    axes[1].xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color=ORANGE, label="incident features only"),
                        Patch(color=BLUE, label="event features (+ incident)")],
               loc="lower center", ncol=2, frameon=False, fontsize=8)
    fig.suptitle("E1 - Run B test set (1,692,332 events), 300 s window, mean ± SD over 5 seeds",
                 fontsize=9, color=MUTED, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(FIG / "e1_f1_fpr_by_condition.png", dpi=300)
    plt.close(fig)


def e2():
    r = pd.read_csv(RES / "e2" / "alert_workload.csv")
    keep = [("A_fragmented", "A  fragmented: one alert per event"),
            ("B_integrated", "B  integrated: one alert per incident"),
            ("C_fragmented_w60_closed", "C  detect then correlate, 60 s"),
            ("C_fragmented_w300_closed", "C  detect then correlate, 300 s"),
            ("C_fragmented_w900_closed", "C  detect then correlate, 900 s")]
    r = r.set_index("name").loc[[k for k, _ in keep][::-1]]
    labels = [l for _, l in keep][::-1]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2), sharey=True)
    for ax, col, title in ((axes[0], "n_alerts", "Alerts to review (log scale)"),
                           (axes[1], "false_alarm_alerts", "False-alarm alerts (only benign events)")):
        ax.barh(labels, r[col], color=BLUE, height=0.6, edgecolor="white", linewidth=2)
        for y, v in enumerate(r[col]):
            ax.text(v, y, f"  {int(v):,}", va="center", fontsize=7.5, color=INK)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        style(ax)
    axes[0].set_xscale("log")
    axes[0].set_xlim(1e4, 1e7)
    axes[1].set_xlim(0, r["false_alarm_alerts"].max() * 1.3)
    fig.suptitle("E2 - alert-workload PROXY on the Run B test set (no analysts involved; offline grouping)",
                 fontsize=9, color=MUTED, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIG / "e2_alerts_by_design.png", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    if (RES / "e2" / "alert_workload.csv").exists():
        e2()
    if (RES / "e1" / "runb_summary.csv").exists():
        e1()
    print("figures in", FIG)
