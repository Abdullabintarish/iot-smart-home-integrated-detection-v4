"""Draw the v3 figures for the figures booklet, from saved v3 outputs only (no retraining).

    code/.venv/Scripts/python.exe -B experiments/figures_book/make_v3_figures.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(HERE / ".mpl"))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

V3 = HERE.parent / "v3" / "results"
OUT = HERE / "v3_figures"
OUT.mkdir(exist_ok=True)

# same style as experiments/thesis_report/build_content.py
INK, MUTED, GRID = "#1d2a33", "#5f6b73", "#d9dee2"
COL = {"rf": "#2f7f9e", "hgb": "#c58a2b", "lr": "#2f5d3a", "frag": "#7b8a95",
       "event": "#2f6f9e", "ctx": "#c2562d"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.axisbelow": True, "figure.dpi": 200})


def J(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=200)
    plt.close(fig)


def short(src: str) -> str:
    if src.startswith("CTU-IoT-Malware-Capture-"):
        return "IoT-23 " + src.removeprefix("CTU-IoT-Malware-Capture-")
    if src.startswith("CTU-Honeypot-Capture-"):
        return "Honeypot " + src.removeprefix("CTU-Honeypot-Capture-")
    return "Bot-IoT " + src


def seed_mean(m, run, fold, met):
    vals = [m["runs"][f"{run}|{s}"][fold][met] for s in m["seeds"]]
    return None if any(v is None for v in vals) else float(np.mean(vals))


LOSO = J(V3 / "transfer" / "loso" / "metrics.json")
RUNB = J(V3 / "transfer" / "runB" / "metrics.json")
FOLDS = list(LOSO["folds"])

# ------------------------------------------------ V3-1 per held-out source
fig, ax = plt.subplots(figsize=(7.2, 5.4))
y = np.arange(len(FOLDS))[::-1]
for run, col, lab, mk in [("rf_event_only", COL["event"], "RF event only", "o"),
                          ("rf_event_plus_incident", COL["ctx"], "RF event + incident", "D"),
                          ("frag_soft", COL["frag"], "Source-specific baseline (frag_soft)", "s")]:
    v = [seed_mean(LOSO, run, f, "f1_macro") for f in FOLDS]
    ax.scatter(v, y, color=col, marker=mk, s=30, label=lab, zorder=3)
for i, f in enumerate(FOLDS):
    a, b = seed_mean(LOSO, "rf_event_only", f, "f1_macro"), seed_mean(LOSO, "rf_event_plus_incident", f, "f1_macro")
    ax.plot([a, b], [y[i], y[i]], color=GRID, lw=2, zorder=2)
ax.set_yticks(y, [f"{short(f)}  (n={LOSO['folds'][f]['n_test']:,})" for f in FOLDS], fontsize=8.5)
ax.set_xlim(0, 1.02)
ax.set_xlabel("Macro F1 on the held-out source (mean of 5 seeds)")
ax.set_title("Leave-one-source-out: macro F1 per unseen source", fontsize=9.5, color=INK, loc="left")
ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.4, -0.11), ncol=3, frameon=False)
save(fig, "fig_v3_1_loso_per_source.png")

# ------------------------------------------------ V3-2/3 model comparison
MODELS = [("rf", "RF"), ("hgb", "HGB"), ("lr", "LR")]
FSETS = [("event_only", "Event only", COL["event"]), ("event_plus_incident", "Event + incident", COL["ctx"]),
         ("incident_only", "Incident only", COL["frag"])]


def model_panel(m, design, name, title):
    fig, axs = plt.subplots(1, 2, figsize=(7.6, 3.8))
    for k, (met, lab) in enumerate([("f1_macro", "Macro F1"), ("fpr", "False-positive rate")]):
        ax = axs[k]
        x = np.arange(len(MODELS))
        for j, (fs, flab, col) in enumerate(FSETS):
            means, sds = [], []
            for mod, _ in MODELS:
                run = f"{mod}_{fs}"
                if design == "runB":
                    vals = [m["runs"][f"{run}|{s}"]["runB"][met] for s in m["seeds"]]
                    means.append(np.mean(vals)); sds.append(np.std(vals, ddof=1))
                else:
                    per = [seed_mean(m, run, f, met) for f in m["folds"]]
                    per = [p for p in per if p is not None]
                    means.append(np.mean(per)); sds.append(0)
            xx = x + (j - 1) * 0.26
            ax.bar(xx, means, 0.24, color=col, label=flab, yerr=sds if design == "runB" else None,
                   error_kw={"elinewidth": 0.8, "capsize": 2, "ecolor": INK})
            for a_, v in zip(xx, means):
                ax.text(a_, v, f"{v:.3f}", ha="center", va="bottom", fontsize=6.5, color=INK, rotation=90)
        frag = ["frag"] if design == "runB" else ["frag_soft"]
        for fr in frag:
            if design == "runB":
                fv = np.mean([m["runs"][f"{fr}|{s}"]["runB"][met] for s in m["seeds"]])
            else:
                per = [seed_mean(m, fr, f, met) for f in m["folds"]]
                fv = np.mean([p for p in per if p is not None])
            ax.axhline(fv, color=INK, ls="--", lw=1, label=f"{fr} baseline ({fv:.3f})")
        ax.set_xticks(x, [lab_ for _, lab_ in MODELS])
        ax.set_title(lab, fontsize=9.5, color=INK, loc="left")
        top = ax.get_ylim()[1]
        ax.set_ylim(0, top * 1.18)
    fig.suptitle(title, fontsize=9.5, color=INK, x=0.01, ha="left")
    h, l = axs[0].get_legend_handles_labels()
    h2, l2 = axs[1].get_legend_handles_labels()
    fig.legend(h[1:] + [h[0], h2[0]], l[1:] + ["Macro F1: " + l[0], "FPR: " + l2[0]],
               loc="lower center", ncol=3, fontsize=7.5, frameon=False)
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    fig.savefig(OUT / name, dpi=200)
    plt.close(fig)


model_panel(LOSO, "loso", "fig_v3_2_models_loso.png",
            "Leave-one-source-out (mean over 13 held-out sources of the 5-seed mean)")
model_panel(RUNB, "runB", "fig_v3_3_models_runB.png",
            "Run B split (mean ± sd over 5 seeds)")

# ------------------------------------------------ V3-4 cross-log primary
P = J(V3 / "cross_log" / "primary_augmented.json")
conds = [c for c in P["summary"] if "_minus_" not in c]
fig, ax = plt.subplots(figsize=(7.2, 3.2))
for i, c in enumerate(conds):
    s = P["summary"][c]
    ax.bar(i, s["macro_f1_mean"], 0.6, color=COL["ctx"] if c in ("B", "C", "D") else COL["frag"], alpha=0.85)
    ax.errorbar(i, s["macro_f1_mean"], yerr=[[s["macro_f1_mean"] - s["macro_f1_min"]],
                                             [s["macro_f1_max"] - s["macro_f1_mean"]]],
                color=INK, capsize=3, lw=0.9)
    ax.text(i, s["macro_f1_max"] + 0.01, f"{s['macro_f1_mean']:.3f}", ha="center", va="bottom", fontsize=8, color=INK)
ax.set_xticks(range(len(conds)), conds)
ax.set_ylim(0, 1)
ax.set_ylabel("Macro F1 (5 seeds)")
ax.set_title("Cross-log primary split (v3 augmented training): mean, whiskers = seed min–max",
             fontsize=9.5, color=INK, loc="left")
save(fig, "fig_v3_4_crosslog_primary.png")

# ------------------------------------------------ V3-5 cross-log loco B-A
LO = J(V3 / "cross_log" / "loco.json")
d = LO["fold_level_differences"]["B_minus_A"]["per_fold"]
fig, ax = plt.subplots(figsize=(7.2, 3.2))
names = list(d)
vals = [d[n] for n in names]
ax.bar(range(len(names)), vals, 0.6, color=[COL["ctx"] if v > 0 else COL["event"] for v in vals])
for i, v in enumerate(vals):
    ax.text(i, v, "≈0" if abs(v) < 5e-4 else f"{v:+.3f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=7.5, color=INK)
ax.axhline(0, color=INK, lw=0.8)
ax.set_xticks(range(len(names)), [short(n).replace("IoT-23 ", "") for n in names])
ax.set_xlabel("Held-out IoT-23 capture")
ax.set_ylabel("Macro F1 difference, B − A")
ax.set_title(f"Leave-one-capture-out: effect of incident context (B − A), "
             f"{LO['fold_level_differences']['B_minus_A']['folds_positive']} positive / "
             f"{LO['fold_level_differences']['B_minus_A']['folds_negative']} negative of 9 folds",
             fontsize=9.5, color=INK, loc="left")
save(fig, "fig_v3_5_crosslog_loco.png")
print("wrote", sorted(p.name for p in OUT.glob("*.png")))
