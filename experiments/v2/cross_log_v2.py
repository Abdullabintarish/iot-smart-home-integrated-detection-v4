"""P1 (audit 2026-11-03): cross-log v2 with class-stratified sampling and controls.

Corrects audit defect D1 (training sample stratified on binary y, leaving 1-5
c2 rows per seed) and tests D2 (gains on captures that have no context).
Nothing in experiments/cross_log is changed; the feature cache, split helpers,
Random Forest settings and Preprocessor are imported from there unchanged.

Conditions (same sample, same RF, same test rows per seed; only columns differ)
  A    connection features
  B    A + DNS context            C   A + alert context     D   A + DNS + alerts
  Z    A + the 17 D context columns set to 0 (column-count control)
  P    A + the D context columns permuted within each capture, jointly per row
       (keeps each capture's context distribution, breaks the row link)
  MAJ  always benign              STR  random, P(malicious) = training share

Designs
  primary  pre-registered split (train 1-1 3-1 20-1 42-1; test 8-1 21-1 34-1)
  loco     leave-one-capture-out over the captures used by R3

    code/.venv/Scripts/python.exe -B experiments/v2/cross_log_v2.py [primary] [loco]

Writes experiments/v2/results/cross_log/<design>.json, <design>_predictions.parquet
and manifest_<design>.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "cross_log" / "src"))
from sklearn.ensemble import RandomForestClassifier  # noqa: E402

import robustness as R  # noqa: E402
from experiment import (RF_PARAMS, TRAIN_BUDGET_PER_CLASS,  # noqa: E402
                        check_no_forbidden, metrics)
from features import DNS_FEATURES, Preprocessor  # noqa: E402
from manifest import write_manifest  # noqa: E402
from run_stage4 import TEST, TRAIN  # noqa: E402

OUT = HERE / "results" / "cross_log"
SEEDS = (42, 1, 2, 3, 4)
MODEL_CONDS = ("A", "B", "C", "D", "Z", "P")
ALL_CONDS = MODEL_CONDS + ("MAJ", "STR")


def class_stratified_sample(train: pd.DataFrame, seed: int,
                            budget: int = TRAIN_BUDGET_PER_CLASS) -> pd.DataFrame:
    """At most ``budget`` rows per thesis class (as code/pipeline/detect.py)."""
    parts = [g.sample(n=min(budget, len(g)), random_state=seed)
             for _, g in train.groupby("cls", sort=True)]
    return pd.concat(parts).sort_index()


def context_columns(alert_cols: list[str]) -> list[str]:
    return list(DNS_FEATURES) + list(alert_cols)


def add_controls(df: pd.DataFrame, ctx: list[str], seed: int) -> pd.DataFrame:
    """Zero (z_*) and within-capture permuted (p_*) copies of the context columns."""
    out = df.copy()
    for c in ctx:
        out[f"z_{c}"] = 0.0
    rng = np.random.default_rng(seed)
    perm = np.arange(len(out))
    cap = out["capture"].to_numpy()
    for k in pd.unique(cap):
        idx = np.flatnonzero(cap == k)
        perm[idx] = idx[rng.permutation(len(idx))]
    vals = out[ctx].to_numpy()[perm]
    for i, c in enumerate(ctx):
        out[f"p_{c}"] = vals[:, i]
    return out


def condition_columns(alert_cols: list[str]) -> dict[str, tuple[list[str], list[str]]]:
    cd = R.conditions(alert_cols)
    num_a, cat = cd["A"]
    ctx = context_columns(alert_cols)
    cd["Z"] = (num_a + [f"z_{c}" for c in ctx], cat)
    cd["P"] = (num_a + [f"p_{c}" for c in ctx], cat)
    return cd


def context_availability(df: pd.DataFrame, alert_cols: list[str]) -> dict:
    out = {}
    for k, g in df.groupby("capture", sort=True):
        out[k] = {"rows": int(len(g)),
                  "share_rows_dns_nonzero": float((g[list(DNS_FEATURES)] != 0).any(axis=1).mean()),
                  "share_rows_alert_nonzero": float((g[alert_cols] != 0).any(axis=1).mean())}
    return out


def run(train, test, alert_cols, seeds=SEEDS):
    cd = condition_columns(alert_cols)
    ctx = context_columns(alert_cols)
    for num, cat in cd.values():
        check_no_forbidden(num + cat)
    y = test["y"].to_numpy()
    cls = test["cls"].to_numpy()
    preds = pd.DataFrame({"incident_id": test["incident_id"].to_numpy(),
                          "capture": test["capture"].to_numpy(), "cls": cls, "y": y})
    res = {c: {} for c in ALL_CONDS}
    samples = {}
    for seed in seeds:
        tr = add_controls(class_stratified_sample(train, seed), ctx, seed)
        te = add_controls(test, ctx, seed + 10_000)
        samples[str(seed)] = tr["cls"].value_counts().to_dict()
        for c in MODEL_CONDS:
            num, cat = cd[c]
            pre = Preprocessor().fit(tr, num, cat)
            rf = RandomForestClassifier(random_state=seed, **RF_PARAMS)
            rf.fit(pre.transform(tr), tr["y"].to_numpy())
            p = rf.predict(pre.transform(te)).astype("int8")
            preds[f"pred_{c}_s{seed}"] = p
            res[c][str(seed)] = metrics(y, p, cls)
        preds[f"pred_MAJ_s{seed}"] = np.zeros(len(y), dtype="int8")
        share = float(tr["y"].mean())
        preds[f"pred_STR_s{seed}"] = (np.random.default_rng(seed).random(len(y)) < share).astype("int8")
        for c in ("MAJ", "STR"):
            res[c][str(seed)] = metrics(y, preds[f"pred_{c}_s{seed}"].to_numpy(), cls)
        R.log("   seed %d: %s" % (seed, " ".join(
            f"{c}={res[c][str(seed)]['macro_f1']:.4f}" for c in ALL_CONDS)))
    return res, preds, samples


def summarise(res, seeds):
    s = R.summarise(res, seeds, ALL_CONDS)
    for c in ("B", "C", "D"):
        for ctrl in ("Z", "P"):
            d = np.array([res[c][str(k)]["macro_f1"] - res[ctrl][str(k)]["macro_f1"] for k in seeds])
            s[f"{c}_minus_{ctrl}"] = {"mean": float(d.mean()), "per_seed": d.round(6).tolist(),
                                      "seeds_positive": int((d > 0).sum()),
                                      "seeds_negative": int((d < 0).sum())}
    return s


def per_capture(preds, seeds, conds=ALL_CONDS):
    out = {}
    for k, g in preds.groupby("capture", sort=True):
        y = g["y"].to_numpy()
        out[k] = {c: {"macro_f1_mean": float(np.mean([metrics(y, g[f"pred_{c}_s{s}"].to_numpy(),
                                                                g["cls"].to_numpy())["macro_f1"]
                                                        for s in seeds])),
                      "attack_detection_mean": float(np.mean([(g[f"pred_{c}_s{s}"].to_numpy()[y == 1] == 1).mean()
                                                              for s in seeds])) if (y == 1).any() else None,
                      "fpr_mean": float(np.mean([(g[f"pred_{c}_s{s}"].to_numpy()[y == 0] == 1).mean()
                                                 for s in seeds])) if (y == 0).any() else None}
                  for c in conds}
    return out


def save(name, obj, preds):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(obj, indent=2), encoding="utf-8")
    preds.to_parquet(OUT / f"{name}_predictions.parquet")


def primary():
    R.log("v2 primary split")
    tr, te, ac = R.split(TRAIN, TEST)
    res, preds, samples = run(tr, te, ac)
    save("primary", {"train": TRAIN, "test": TEST, "seeds": list(SEEDS),
                     "sampling": "per thesis class, <= %d rows" % TRAIN_BUDGET_PER_CLASS,
                     "train_classes": tr["cls"].value_counts().to_dict(),
                     "test_classes": te["cls"].value_counts().to_dict(),
                     "train_sample_classes_by_seed": samples,
                     "context_columns": context_columns(ac),
                     "context_availability_test": context_availability(te, ac),
                     "by_condition_seed": res, "summary": summarise(res, SEEDS),
                     "per_capture": per_capture(preds, SEEDS)}, preds)
    write_manifest(OUT / "manifest_primary.json", "crosslog_v2_primary",
                   inputs=[R.CACHE / f"{c}.parquet" for c in TRAIN + TEST] + [R.CACHE / "alert_categories.json"],
                   config={"rf_params": RF_PARAMS, "budget_per_class": TRAIN_BUDGET_PER_CLASS,
                           "conditions": {k: v for k, v in condition_columns(ac).items()},
                           "train": TRAIN, "test": TEST, "variant": "start_300"},
                   seeds=SEEDS, outputs=[OUT / "primary.json", OUT / "primary_predictions.parquet"])


def loco():
    caps = R.cached_captures()
    R.log(f"v2 leave-one-capture-out over {len(caps)} captures")
    folds, all_preds = {}, []
    for held in caps:
        train_caps = [c for c in caps if c != held]
        tr, te, ac = R.split(train_caps, [held])
        R.log(f"  fold {held}: train {len(tr):,}, test {len(te):,}")
        res, preds, samples = run(tr, te, ac)
        folds[held] = {"n_test": int(len(te)), "test_classes": te["cls"].value_counts().to_dict(),
                       "train_classes": tr["cls"].value_counts().to_dict(),
                       "train_sample_classes_by_seed": samples,
                       "context_availability_test": context_availability(te, ac)[held],
                       "test_attack_classes_unseen_in_train": sorted(
                           set(te["cls"]) - set(tr["cls"])),
                       "by_condition_seed": res, "summary": summarise(res, SEEDS)}
        all_preds.append(preds)
        R._loaded.clear()
    preds = pd.concat(all_preds, ignore_index=True)
    fold_diff = {}
    for c, ref in [(c, r) for c in ("B", "C", "D", "Z", "P") for r in ("A",)] + \
                  [(c, r) for c in ("B", "C", "D") for r in ("Z", "P")]:
        d = np.array([folds[f]["summary"][f"{c}_minus_{ref}"]["mean"] for f in caps])
        fold_diff[f"{c}_minus_{ref}"] = {"per_fold": dict(zip(caps, d.round(6).tolist())),
                                         "folds_positive": int((d > 0).sum()),
                                         "folds_negative": int((d < 0).sum()), "n_folds": len(caps)}
    save("loco", {"captures": caps, "seeds": list(SEEDS), "folds": folds,
                  "fold_level_differences": fold_diff}, preds)
    write_manifest(OUT / "manifest_loco.json", "crosslog_v2_loco",
                   inputs=[R.CACHE / f"{c}.parquet" for c in caps] + [R.CACHE / "alert_categories.json"],
                   config={"rf_params": RF_PARAMS, "budget_per_class": TRAIN_BUDGET_PER_CLASS,
                           "captures": caps, "variant": "start_300",
                           "conditions": list(ALL_CONDS)},
                   seeds=SEEDS, outputs=[OUT / "loco.json", OUT / "loco_predictions.parquet"])


STEPS = {"primary": primary, "loco": loco}

if __name__ == "__main__":
    for k in (sys.argv[1:] or list(STEPS)):
        STEPS[k]()
    R.log("done")
