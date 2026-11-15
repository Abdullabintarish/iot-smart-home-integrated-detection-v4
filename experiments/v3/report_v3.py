"""Markdown tables for RESULTS_V3.md, generated from the saved v3 outputs only.

    code/.venv/Scripts/python.exe -B experiments/v3/report_v3.py > experiments/v3/results/tables.md
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
SHOW = ("f1_macro", "f1_macro_present", "balanced_accuracy", "mcc", "binary_f1",
        "pr_auc_binary", "roc_auc_binary", "fpr", "fnr")


def _fmt(v, nd=4):
    return "–" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.{nd}f}"


def transfer_table(design: str) -> str:
    m = json.loads((RES / "transfer" / design / "metrics.json").read_text(encoding="utf-8"))
    names = sorted({k.split("|")[0] for k in m["runs"]})
    out = [f"| run | {' | '.join(SHOW)} |", "|---" * (len(SHOW) + 1) + "|"]
    for n in names:
        cells = []
        for met in SHOW:
            # mean over folds of the seed-mean; folds where the metric is null are dropped
            per_fold = []
            for f in m["folds"]:
                vals = [m["runs"][f"{n}|{s}"][f][met] for s in m["seeds"]]
                if all(v is not None for v in vals):
                    per_fold.append(np.mean(vals))
            sd = ""
            if design == "runB":
                vals = [m["runs"][f"{n}|{s}"]["runB"][met] for s in m["seeds"]]
                if all(v is not None for v in vals):
                    sd = f" ± {np.std(vals, ddof=1):.4f}"
            n_note = "" if len(per_fold) == len(m["folds"]) else f" (n={len(per_fold)})"
            cells.append(_fmt(np.mean(per_fold) if per_fold else None) + sd + n_note)
        out.append(f"| {n} | {' | '.join(cells)} |")
    return "\n".join(out)


def stats_table(design: str) -> str:
    st = json.loads((RES / "transfer" / "stats.json").read_text(encoding="utf-8"))[design]
    pos = "folds" if design == "loso" else "seeds"
    hdr = f"| metric | comparison (X − Y) | mean diff | {pos} +/− | p (sign-flip) | p Holm |"
    if design == "loso":
        hdr += " p Wilcoxon |"
    out = [hdr, "|---" * (hdr.count("|") - 1) + "|"]
    for metric, rows in st["comparisons"].items():
        for r in rows:
            line = (f"| {metric} | {r['x']} − {r['y']} | {r['mean_diff']:+.4f} | "
                    f"{r[pos + '_positive']}/{r[pos + '_negative']} (n={r['n']}) | "
                    f"{r['p_sign_flip']:.4f} | {r['p_sign_flip_holm']:.4f} |")
            if design == "loso":
                line += f" {_fmt(r['p_wilcoxon'])} |"
            out.append(line)
    return "\n".join(out)


def bootstrap_table() -> str:
    b = json.loads((RES / "transfer" / "stats.json").read_text(encoding="utf-8"))["runB"]
    out = ["| comparison | macro F1 diff 95% CI | FPR diff 95% CI |", "|---|---|---|"]
    for k, v in b["incident_bootstrap_seed42"].items():
        out.append(f"| {k} | [{v['f1_macro_diff'][0]:+.4f}, {v['f1_macro_diff'][1]:+.4f}] | "
                   f"[{v['fpr_diff'][0]:+.4f}, {v['fpr_diff'][1]:+.4f}] |")
    return "\n".join(out)


def loso_per_fold(metric: str = "f1_macro") -> str:
    m = json.loads((RES / "transfer" / "loso" / "metrics.json").read_text(encoding="utf-8"))
    names = sorted({k.split("|")[0] for k in m["runs"]})
    out = [f"| held-out source | n test | {' | '.join(names)} |", "|---" * (len(names) + 2) + "|"]
    for f, info in m["folds"].items():
        cells = [_fmt(np.mean([m["runs"][f"{n}|{s}"][f][metric] for s in m["seeds"]]), 3) for n in names]
        out.append(f"| {f} | {info['n_test']:,} | {' | '.join(cells)} |")
    return "\n".join(out)


def crosslog_tables() -> str:
    parts = []
    d = RES / "cross_log"
    if (d / "primary_augmented.json").exists():
        p = json.loads((d / "primary_augmented.json").read_text(encoding="utf-8"))
        parts.append(f"**primary_augmented** — train {p['train']}, test {p['test']}\n")
        parts.append("| condition | macro F1 mean | sd | min | max | FPR | FNR |\n|---|---|---|---|---|---|---|")
        for k, v in p["summary"].items():
            if "_minus_" not in k:
                parts.append(f"| {k} | {_fmt(v['macro_f1_mean'])} | {_fmt(v['macro_f1_sd'])} | "
                             f"{_fmt(v['macro_f1_min'])} | {_fmt(v['macro_f1_max'])} | "
                             f"{_fmt(v['fpr_mean'])} | {_fmt(v['fnr_mean'])} |")
        parts.append("\n| difference | mean | seeds +/− |\n|---|---|---|")
        for k, v in p["summary"].items():
            if "_minus_" in k:
                parts.append(f"| {k} | {v['mean']:+.4f} | {v['seeds_positive']}/{v['seeds_negative']} |")
        conds = list(next(iter(p["per_capture"].values())))
        parts.append("\n| test capture (macro F1) | " + " | ".join(conds) + " |\n" + "|---" * (len(conds) + 1) + "|")
        for cap, v in p["per_capture"].items():
            parts.append(f"| {cap} | " + " | ".join(_fmt(v[c]["macro_f1_mean"], 3) for c in conds) + " |")
    if (d / "loco.json").exists():
        lo = json.loads((d / "loco.json").read_text(encoding="utf-8"))
        conds = [k for k in next(iter(lo["folds"].values()))["summary"] if "_minus_" not in k]
        parts.append(f"\n**loco** — captures {lo['captures']}; excluded by gate {list(lo['excluded_by_gate'])}\n")
        parts.append(f"| held-out | n test | {' | '.join(conds)} |\n" + "|---" * (len(conds) + 2) + "|")
        for f, v in lo["folds"].items():
            parts.append(f"| {f} | {v['n_test']:,} | "
                         + " | ".join(_fmt(v["summary"][c]["macro_f1_mean"], 3) for c in conds) + " |")
        parts.append("\n| difference | folds +/− | per fold |\n|---|---|---|")
        for k, v in lo["fold_level_differences"].items():
            parts.append(f"| {k} | {v['folds_positive']}/{v['folds_negative']} of {v['n_folds']} | "
                         + ", ".join(f"{c.split('-')[-2]}-{c.split('-')[-1]}: {x:+.3f}"
                                     for c, x in v["per_fold"].items()) + " |")
    return "\n".join(parts)


if __name__ == "__main__":
    print("## Transfer runB (mean ± sd over 5 seeds)\n")
    print(transfer_table("runB"))
    print("\n## Transfer loso (mean over held-out sources of the 5-seed mean)\n")
    print(transfer_table("loso"))
    print("\n### loso macro F1 per held-out source (5-seed mean)\n")
    print(loso_per_fold())
    print("\n## Tests loso\n")
    print(stats_table("loso"))
    print("\n## Tests runB (seed level)\n")
    print(stats_table("runB"))
    print("\n## Incident-clustered bootstrap, runB seed 42\n")
    print(bootstrap_table())
    print("\n## Cross-log v3\n")
    print(crosslog_tables())
