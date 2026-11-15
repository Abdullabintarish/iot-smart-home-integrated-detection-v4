"""P5: independent verification of every v2 result from its saved predictions.

Uses scikit-learn metrics directly (not the experiment code), checks manifest
hashes against the files on disk, and checks that the v2 ablation reproduces the
historical ablation where the two designs coincide. Writes verification.json.

    code/.venv/Scripts/python.exe -B experiments/v2/verify_v2.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from manifest import sha256  # noqa: E402

RES = HERE / "results"
OLD_ABL = HERE.parent / "ablation" / "results" / "full" / "ablation_results.csv"
TOL = 1e-9


def check_manifest(path: Path) -> dict:
    m = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for name, h in m["outputs"].items():
        f = path.parent / name
        out[name] = f.exists() and sha256(f) == h
    return {"outputs_hash_equal": out, "all": all(out.values())}


def bin_f1(y, p):
    return f1_score(y, p, average="macro", labels=[0, 1], zero_division=0)


def crosslog(name: str) -> dict:
    d = json.loads((RES / "cross_log" / f"{name}.json").read_text(encoding="utf-8"))
    p = pd.read_parquet(RES / "cross_log" / f"{name}_predictions.parquet")
    checks, n = [], 0
    blocks = ({"all": d["by_condition_seed"]} if name == "primary"
              else {k: v["by_condition_seed"] for k, v in d["folds"].items()})
    for fold, res in blocks.items():
        g = p if fold == "all" else p[p["capture"] == fold]
        for c, by_seed in res.items():
            for s, m in by_seed.items():
                got = bin_f1(g["y"], g[f"pred_{c}_s{s}"])
                n += 1
                if abs(got - m["macro_f1"]) > TOL:
                    checks.append(f"{fold} {c} s{s}: {got} vs {m['macro_f1']}")
    maj_zero = bool(all((p[c] == 0).all() for c in p.columns if c.startswith("pred_MAJ")))
    return {"values_checked": n, "mismatches": checks, "majority_baseline_all_benign": maj_zero,
            "manifest": check_manifest(RES / "cross_log" / f"manifest_{name}.json")}


def ablation(design: str) -> dict:
    d = json.loads((RES / "ablation" / f"{design}_metrics.json").read_text(encoding="utf-8"))
    p = pd.read_parquet(RES / "ablation" / f"{design}_predictions.parquet")
    bad, n = [], 0
    for fold, fv in d["folds"].items():
        g = p if design == "runB" else p[p["fold"] == fold]
        y = g["label"].astype(str).to_numpy()
        for key, m in fv["runs"].items():
            name, seed = key.split("|")
            q = g[f"pred_{name}_s{seed}"].astype(str).to_numpy()
            labels = sorted(set(y) | set(q))
            f1 = f1_score(y, q, labels=labels, average="macro", zero_division=0)
            ben = y == "benign"
            fpr = float(((q != "benign") & ben).sum() / ben.sum()) if ben.any() else None
            cm = confusion_matrix(y, q, labels=m["classes"]).tolist()
            n += 1
            if abs(f1 - m["f1_macro"]) > TOL or cm != m["confusion_matrix"] or \
                    (fpr is not None and abs(fpr - m["fpr"]) > TOL):
                bad.append(f"{fold} {key}")
    out = {"runs_checked": n, "mismatches": bad,
           "manifest": check_manifest(RES / "ablation" / f"manifest_{design}.json")}
    if design == "runB" and OLD_ABL.exists():
        old = pd.read_csv(OLD_ABL)
        old = old[old["subset"] == "all"]
        rep = {}
        for name, w in (("event_only", 0), ("event_plus_incident", 300), ("incident_only", 300)):
            for seed in d["seeds"]:
                o = old[(old["feature_set"] == name) & (old["window_s"] == w) & (old["seed"] == seed)]
                new = d["folds"]["runB"]["runs"].get(f"{name}|{seed}")
                if len(o) and new:
                    rep[f"{name}|{seed}"] = {"historical": float(o["f1_macro"].iloc[0]),
                                             "v2": new["f1_macro"],
                                             "equal": abs(float(o["f1_macro"].iloc[0]) - new["f1_macro"]) < TOL}
        out["reproduces_historical_ablation"] = rep
    return out


def main() -> None:
    out = {}
    for name in ("primary", "loco"):
        if (RES / "cross_log" / f"{name}.json").exists():
            out[f"cross_log_{name}"] = crosslog(name)
    for design in ("runB", "loso"):
        if (RES / "ablation" / f"{design}_metrics.json").exists():
            out[f"ablation_{design}"] = ablation(design)
    ok = all(not v["mismatches"] and v["manifest"]["all"] for v in out.values())
    rep = out.get("ablation_runB", {}).get("reproduces_historical_ablation", {})
    out["all_ok"] = ok and all(r["equal"] for r in rep.values())
    (RES / "verification.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2)[:3000])


if __name__ == "__main__":
    main()
