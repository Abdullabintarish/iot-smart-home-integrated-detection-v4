"""E3 figures (300 dpi) from results/response_all.csv.

    code/.venv/Scripts/python.exe -B experiments/v4_extension/e3/make_figures_e3.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
FIG = RES / "figures"
ORDER = ["A/C", "B", "event_only", "event_plus_thin", "oracle", "none"]
LABEL = {"A/C": "A/C fragmented", "B": "B integrated", "event_only": "event_only s42",
         "event_plus_thin": "event_plus_thin s42", "oracle": "oracle (not achievable)",
         "none": "no response"}
COLOR = dict(zip(ORDER, ["#2a6fdb", "#d9822b", "#3aa17e", "#8e6bbf", "#777777", "#bbbbbb"]))
MARK = {"60": "o", "300": "s", "900": "^", "end": "D"}


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    r = pd.read_csv(RES / "response_all.csv", dtype={"duration": str})

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    for ax, pol in zip(axes, ("P1_flow", "P2_host")):
        s = r[r.policy == pol]
        for t in ORDER:
            for d, m in MARK.items():
                q = s[(s.trigger == t) & (s.duration == d)]
                ax.scatter(100 * q.benign_blocked_share, 100 * q.attack_prevented_share, marker=m,
                           s=46, color=COLOR[t], edgecolor="black", linewidth=0.4, alpha=0.85)
        ax.set_xscale("symlog", linthresh=0.01)
        ax.set_xlim(-0.002, 150)
        ax.set_title({"P1_flow": "P1 block the flow", "P2_host": "P2 quarantine the host"}[pol])
        ax.set_xlabel("Harmless events wrongly blocked (%, symlog)")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Attack events prevented (%)")
    h = [plt.Line2D([], [], ls="", marker="o", color=COLOR[t], label=LABEL[t]) for t in ORDER]
    h += [plt.Line2D([], [], ls="", marker=m, color="black", mfc="none",
                     label=f"block {d}{'' if d == 'end' else ' s'}") for d, m in MARK.items()]
    fig.legend(handles=h, loc="lower center", ncol=5, fontsize=8, frameon=False)
    fig.suptitle("E3 simulated response (offline replay): prevented vs wrongly blocked")
    fig.text(0.5, 0.005, "A/C, event_only and event_plus_thin lie on top of each other "
             "(values within 0.1 pp); durations overlap where blocking barely depends on them.",
             ha="center", fontsize=7.5, style="italic")
    fig.tight_layout(rect=(0, 0.14, 1, 0.95))
    fig.savefig(FIG / "e3_prevented_vs_wrongly_blocked.png", dpi=300)
    plt.close(fig)

    s = r[r.duration == "300"]
    trig = ORDER[:-1]
    x = np.arange(len(trig))
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4))
    for ax, col, title in zip(axes, ("attack_prevented_share", "attack_prevented_share_excl_dos",
                                     "benign_blocked_share"),
                              ("Attack events prevented", "Attack events prevented, excl. DoS",
                               "Harmless events wrongly blocked")):
        for j, pol in enumerate(("P1_flow", "P2_host")):
            v = [100 * s[(s.trigger == t) & (s.policy == pol)][col].iloc[0] for t in trig]
            b = ax.bar(x + (j - 0.5) * 0.4, v, 0.4, label=pol.replace("_", " "),
                       color=["#2a6fdb", "#d9822b"][j], hatch=["", "//"][j], edgecolor="white")
            ax.bar_label(b, fmt="%.1f", fontsize=6.5, padding=1)
        ax.set_xticks(x, [LABEL[t].replace(" (not achievable)", "\n(not achievable)") for t in trig],
                      rotation=30, ha="right", fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.set_ylim(0, 112)
        ax.set_ylabel("%")
        ax.grid(axis="y", alpha=0.3)
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper right", ncol=2, fontsize=8, frameon=False)
    fig.suptitle("E3 simulated response (offline replay), 300 s block")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIG / "e3_main_table_bars.png", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    main()
