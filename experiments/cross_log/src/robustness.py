"""Robustness analyses for the cross-log experiment (added after the primary run).

The primary analysis (run_stage4.py, PLAN.md section 4) is not changed. These
analyses test whether its findings hold:

  R0  reproduction: the primary seed-42 run rebuilt from the feature cache
      must give identical predictions (validates cache and code)
  R1  primary split, 20 seeds
  R2  two-level bootstrap over seeds and incidents (R1 predictions)
  R3  leave-one-capture-out over all cached captures, 5 seeds
  R4  features anchored at connection end instead of start, primary split
  R5  correlation window 60 s and 900 s instead of 300 s, primary split

    python robustness.py [R0 R1 ...]      (default: all, in order)

Writes results/robustness/<name>.json (+ predictions parquet where useful).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

import common  # noqa: F401
from experiment import RF_PARAMS, metrics, train_sample
from features import CONN_CATEGORICAL, CONN_NUMERIC, DNS_FEATURES, Preprocessor
from run_stage4 import TEST, TRAIN

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "results" / "robust_cache"
OUT = ROOT / "results" / "robustness"
SEEDS5 = (42, 1, 2, 3, 4)
SEEDS20 = (42,) + tuple(range(1, 20))
CONDS = "ABCD"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
_loaded: dict[str, pd.DataFrame] = {}


def load(capture: str) -> pd.DataFrame:
    if capture not in _loaded:
        _loaded[capture] = pd.read_parquet(CACHE / f"{capture}.parquet")
    return _loaded[capture]


def cached_captures() -> list[str]:
    """Captures for R3: the seven of the primary analysis, plus any added capture
    that passed the Stage 3 gate (PLAN.md section 4b)."""
    primary = set(TRAIN) | set(TEST)
    keep = []
    for p in sorted(CACHE.glob("CTU-*.parquet")):
        gate = json.loads((ROOT / "results" / f"stage3_{p.stem}.json").read_text())["gate"]
        if p.stem in primary or gate["pass"]:
            keep.append(p.stem)
        else:
            log(f"R3 excludes {p.stem}: Stage 3 gate failed {gate}")
    return keep


def top_categories(train_caps: list[str], k: int = 10) -> list[str]:
    """Top-k alert categories of the training captures (ties: name order)."""
    counts = json.loads((CACHE / "alert_categories.json").read_text())["counts_by_capture"]
    tot: dict[str, int] = {}
    for c in train_caps:
        for cat, n in counts.get(c, {}).items():
            tot[cat] = tot.get(cat, 0) + n
    return [c for c, _ in sorted(tot.items(), key=lambda kv: (-kv[1], kv[0]))][:k]


def view(df: pd.DataFrame, variant: str, cats: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """Feature table in the primary column layout for one variant and vocabulary."""
    out = df[list(CONN_NUMERIC) + list(CONN_CATEGORICAL)
             + ["capture", "incident_id", "cls", "y"]].copy()
    for f in DNS_FEATURES:
        out[f] = df[f"{variant}|{f}"]
    out["alert_count"] = df[f"{variant}|alert_count"]
    out["alert_max_severity"] = df[f"{variant}|alert_max_severity"]
    cat_cols = [c for c in df.columns if c.startswith(f"{variant}|alert_cat|")]
    kept = []
    for i, c in enumerate(cats):
        col = f"{variant}|alert_cat|{c}"
        out[f"alert_cat_{i}"] = df[col] if col in df.columns else 0.0
        kept.append(col)
    out["alert_cat_other"] = df[[c for c in cat_cols if c not in kept]].sum(axis=1) \
        if len(cat_cols) > len(kept) else 0.0
    alert_cols = (["alert_count", "alert_max_severity"]
                  + [f"alert_cat_{i}" for i in range(len(cats))] + ["alert_cat_other"])
    return out, alert_cols


def split(train_caps, test_caps, variant="start_300"):
    cats = top_categories(train_caps)
    tr = pd.concat([view(load(c), variant, cats)[0] for c in train_caps], ignore_index=True)
    te_parts = [view(load(c), variant, cats) for c in test_caps]
    te = pd.concat([p[0] for p in te_parts], ignore_index=True)
    return tr, te, te_parts[0][1]


def conditions(alert_cols):
    num = list(CONN_NUMERIC)
    cat = list(CONN_CATEGORICAL)
    return {"A": (num, cat), "B": (num + list(DNS_FEATURES), cat),
            "C": (num + alert_cols, cat), "D": (num + list(DNS_FEATURES) + alert_cols, cat)}


def row_hash(X: np.ndarray) -> np.ndarray:
    return pd.util.hash_pandas_object(pd.DataFrame(X), index=False).to_numpy()


# --------------------------------------------------------------------------
# Core runner (same model, sample and preprocessing as experiment.run)
# --------------------------------------------------------------------------
def run(train, test, alert_cols, seeds, conds=CONDS):
    cd = conditions(alert_cols)
    preds = pd.DataFrame({"incident_id": test["incident_id"].to_numpy(),
                          "capture": test["capture"].to_numpy(),
                          "cls": test["cls"].to_numpy(), "y": test["y"].to_numpy()})
    pa = Preprocessor().fit(train, *cd["A"])
    novel = ~np.isin(row_hash(pa.transform(test)), row_hash(pa.transform(train)))
    preds["novel_vector"] = novel
    res = {c: {} for c in conds}
    y = test["y"].to_numpy()
    for seed in seeds:
        tr = train_sample(train, seed)
        for c in conds:
            num, cat = cd[c]
            pre = Preprocessor().fit(tr, num, cat)
            rf = RandomForestClassifier(random_state=seed, **RF_PARAMS)
            rf.fit(pre.transform(tr), tr["y"].to_numpy())
            p = rf.predict(pre.transform(test))
            preds[f"pred_{c}_s{seed}"] = p.astype("int8")
            m = metrics(y, p, test["cls"].to_numpy())
            nb = novel & (y == 0)
            m["fpr_unseen_benign"] = float((p[nb] == 1).mean()) if nb.any() else None
            m["n_unseen_benign"] = int(nb.sum())
            res[c][str(seed)] = m
        log(f"   seed {seed}: " + " ".join(f"{c}={res[c][str(seed)]['macro_f1']:.4f}" for c in conds))
    return res, preds


def summarise(res, seeds, conds=CONDS):
    out = {}
    for c in conds:
        f = np.array([res[c][str(s)]["macro_f1"] for s in seeds])
        g = lambda k: [res[c][str(s)][k] for s in seeds if res[c][str(s)].get(k) is not None]  # noqa: E731
        out[c] = {"macro_f1_mean": float(f.mean()), "macro_f1_sd": float(f.std(ddof=1)) if len(f) > 1 else 0.0,
                  "macro_f1_min": float(f.min()), "macro_f1_max": float(f.max()),
                  "fpr_mean": float(np.mean(g("fpr"))) if g("fpr") else None,
                  "fnr_mean": float(np.mean(g("fnr"))) if g("fnr") else None,
                  "fpr_unseen_benign_mean": float(np.mean(g("fpr_unseen_benign"))) if g("fpr_unseen_benign") else None}
    if "A" in conds:
        for c in [x for x in conds if x != "A"]:
            d = np.array([res[c][str(s)]["macro_f1"] - res["A"][str(s)]["macro_f1"] for s in seeds])
            entry = {"mean": float(d.mean()), "per_seed": d.round(6).tolist(),
                     "seeds_positive": int((d > 0).sum()), "seeds_negative": int((d < 0).sum()),
                     "n_seeds": len(seeds)}
            if len(seeds) >= 6 and np.any(d != 0):
                entry["wilcoxon_p_two_sided"] = float(wilcoxon(d).pvalue)
            out[f"{c}_minus_A"] = entry
    return out


def save(name, obj, preds=None):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(obj, indent=2))
    if preds is not None:
        preds.to_parquet(OUT / f"{name}_predictions.parquet")


# --------------------------------------------------------------------------
# Analyses
# --------------------------------------------------------------------------
def r0():
    log("R0 reproduce primary seed 42 from cache")
    tr, te, ac = split(TRAIN, TEST)
    _, preds = run(tr, te, ac, (42,))
    prim = pd.read_parquet(ROOT / "results" / "stage4_predictions.parquet")
    same = {c: bool((prim[f"pred_{c}_s42"].to_numpy() == preds[f"pred_{c}_s42"].to_numpy()).all())
            for c in CONDS}
    novel_same = bool((prim["novel_vector"].to_numpy() == preds["novel_vector"].to_numpy()).all())
    out = {"rows_primary": int(len(prim)), "rows_cache": int(len(preds)),
           "identical_predictions": same, "identical_novel_flags": novel_same}
    save("R0_reproduction", out)
    log(f"R0 {out}")
    if not all(same.values()):
        raise SystemExit("R0 failed: cache does not reproduce the primary run")


def r1():
    log("R1 primary split, 20 seeds")
    tr, te, ac = split(TRAIN, TEST)
    res, preds = run(tr, te, ac, SEEDS20)
    save("R1_20_seeds", {"seeds": list(SEEDS20), "by_condition_seed": res,
                         "summary": summarise(res, SEEDS20)}, preds)


def r2(reps=2000, rng_seed=42):
    log("R2 two-level bootstrap (seeds x incidents)")
    preds = pd.read_parquet(OUT / "R1_20_seeds_predictions.parquet")
    codes, uniq = pd.factorize(preds["incident_id"])
    rows_by = pd.Series(np.arange(len(preds))).groupby(codes).apply(np.array).to_list()
    y = preds["y"].to_numpy()
    rng = np.random.default_rng(rng_seed)
    draws = {k: [] for k in ["A", "B", "C", "D", "B-A", "C-A", "D-A"]}
    for _ in range(reps):
        s = SEEDS20[rng.integers(len(SEEDS20))]
        idx = np.concatenate([rows_by[i] for i in rng.integers(0, len(uniq), len(uniq))])
        f = {c: f1_score(y[idx], preds[f"pred_{c}_s{s}"].to_numpy()[idx], average="macro",
                         labels=[0, 1], zero_division=0) for c in CONDS}
        for c in CONDS:
            draws[c].append(f[c])
        for c in "BCD":
            draws[f"{c}-A"].append(f[c] - f["A"])
    out = {"reps": reps, "rng_seed": rng_seed, "clusters": int(len(uniq)), "seeds": list(SEEDS20)}
    for k, v in draws.items():
        a = np.array(v)
        out[k] = {"ci95": [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))],
                  "share_above_zero": float((a > 0).mean()) if "-" in k else None}
    save("R2_two_level_bootstrap", out)
    log(f"R2 D-A {out['D-A']['ci95']}  B-A {out['B-A']['ci95']}  C-A {out['C-A']['ci95']}")


def r3():
    caps = cached_captures()
    log(f"R3 leave-one-capture-out over {len(caps)} captures, 5 seeds")
    folds, all_preds = {}, []
    for held in caps:
        train_caps = [c for c in caps if c != held]
        tr, te, ac = split(train_caps, [held])
        log(f"  fold {held}: train {len(tr):,}, test {len(te):,}")
        res, preds = run(tr, te, ac, SEEDS5)
        folds[held] = {"n_test": int(len(te)), "test_classes": te["cls"].value_counts().to_dict(),
                       "train_classes": tr["cls"].value_counts().to_dict(),
                       "alert_categories": top_categories(train_caps),
                       "by_condition_seed": res, "summary": summarise(res, SEEDS5)}
        all_preds.append(preds)
        _loaded.clear()
        save("R3_partial_folds", {"captures_done": list(folds), "folds": folds})
    preds = pd.concat(all_preds, ignore_index=True)
    pooled = {}
    y = preds["y"].to_numpy()
    nb = preds["novel_vector"].to_numpy() & (y == 0)
    for s in SEEDS5:
        pooled[str(s)] = {}
        for c in CONDS:
            p = preds[f"pred_{c}_s{s}"].to_numpy()
            m = metrics(y, p, preds["cls"].to_numpy())
            m["fpr_unseen_benign"] = float((p[nb] == 1).mean()) if nb.any() else None
            pooled[str(s)][c] = m
    pooled_res = {c: {str(s): pooled[str(s)][c] for s in SEEDS5} for c in CONDS}
    # Fold-level paired comparison: mean over seeds per fold, then D-A etc. per fold.
    fold_diff = {}
    for c in "BCD":
        d = [folds[f]["summary"][f"{c}_minus_A"]["mean"] for f in caps]
        fold_diff[f"{c}_minus_A"] = {"per_fold": dict(zip(caps, np.round(d, 6).tolist())),
                                     "folds_positive": int(np.sum(np.array(d) > 0)),
                                     "folds_negative": int(np.sum(np.array(d) < 0)),
                                     "n_folds": len(caps)}
    save("R3_leave_one_capture_out", {"captures": caps, "seeds": list(SEEDS5), "folds": folds,
                                      "pooled_summary": summarise(pooled_res, SEEDS5),
                                      "fold_level_differences": fold_diff}, preds)


def r4():
    log("R4 features anchored at connection end")
    tr, te, ac = split(TRAIN, TEST, "end_300")
    res, preds = run(tr, te, ac, SEEDS5)
    save("R4_connection_end", {"variant": "end_300", "seeds": list(SEEDS5),
                               "by_condition_seed": res, "summary": summarise(res, SEEDS5)}, preds)


def r5():
    out = {}
    for v in ("start_60", "start_900"):
        log(f"R5 window variant {v}")
        tr, te, ac = split(TRAIN, TEST, v)
        res, _ = run(tr, te, ac, SEEDS5)
        out[v] = {"by_condition_seed": res, "summary": summarise(res, SEEDS5)}
    save("R5_windows", {"seeds": list(SEEDS5), "variants": out})


STEPS = {"R0": r0, "R1": r1, "R2": r2, "R3": r3, "R4": r4, "R5": r5}

if __name__ == "__main__":
    for k in (sys.argv[1:] or list(STEPS)):
        STEPS[k]()
    log("done")
