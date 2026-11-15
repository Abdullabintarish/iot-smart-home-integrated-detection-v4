"""v3 cross-log expansion (PLAN_V3.md §B). Reuses cross_log/src and v2 code unchanged.

New captures live in experiments/v3/cross_log/{pcaps,sensor_out,results}; the
original cross_log folders are only read. Steps:

  stage3 <capture>   label transfer, linking and gate (cross_log/src/run_stage3.py)
  cache              feature cache for every gated + original capture, one
                     alert-category vocabulary over all of them, written to
                     v3/cross_log/robust_cache
  cachecheck         original captures' rebuilt cache == cross_log/results/robust_cache
                     on every shared column
  primary            pre-registered test captures; training = original four + new
  loco               leave-one-capture-out over all captures passing the gate

    code/.venv/Scripts/python.exe -B experiments/v3/xl_v3.py stage3 CTU-IoT-Malware-Capture-36-1
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
OLD = EXP / "cross_log"
NEW = HERE / "cross_log"
sys.path.insert(0, str(OLD / "src"))
sys.path.insert(0, str(EXP / "v2"))
import build_feature_cache as BFC  # noqa: E402
import cross_log_v2 as XV  # noqa: E402
import robustness as R  # noqa: E402
import run_stage3 as S3  # noqa: E402
from experiment import RF_PARAMS, TRAIN_BUDGET_PER_CLASS  # noqa: E402
from features import CONN_CATEGORICAL, CONN_NUMERIC  # noqa: E402
from manifest import write_manifest  # noqa: E402
from run_stage4 import TEST, TRAIN  # noqa: E402

CACHE = NEW / "robust_cache"
OUT = HERE / "results" / "cross_log"
NEW_CAPTURES = ("CTU-IoT-Malware-Capture-36-1", "CTU-IoT-Malware-Capture-7-1")
VARIANT = "start_300"


def root_of(capture: str) -> Path:
    return NEW if capture in NEW_CAPTURES else OLD


def gate(capture: str) -> dict:
    return json.loads((root_of(capture) / "results" / f"stage3_{capture}.json").read_text())["gate"]


def all_captures() -> list[str]:
    old = sorted(p.stem.replace("stage3_", "") for p in (OLD / "results").glob("stage3_CTU-*.json"))
    new = [c for c in NEW_CAPTURES if (NEW / "results" / f"stage3_{c}.json").exists()]
    return sorted(old + new)


def gated() -> list[str]:
    return [c for c in all_captures() if gate(c)["pass"]]


# --------------------------------------------------------------------------
def stage3(capture: str) -> None:
    """Original Stage 3 with only the Zeek reader swapped for the lean one
    (lean_io.py; equality with the original reader in results/lean_io_check.json)."""
    import lean_io
    S3.ROOT = NEW
    S3.read_zeek_tsv = lean_io.read_zeek_tsv
    S3.main(capture)


def cache() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    caps = all_captures()
    alerts = {}
    for c in caps:
        BFC.ROOT = root_of(c)
        alerts.update(BFC.all_alerts([c]))
    cats = sorted({c for a in alerts.values() if len(a) for c in a["category"].fillna("none")})
    counts = {c: (a["category"].fillna("none").value_counts().to_dict() if len(a) else {})
              for c, a in alerts.items()}
    (CACHE / "alert_categories.json").write_text(
        json.dumps({"categories": cats, "counts_by_capture": counts}, indent=2))
    for c in caps:
        BFC.ROOT = root_of(c)
        t = BFC.build(c, alerts[c], cats)
        t.to_parquet(CACHE / f"{c}.parquet")
        print(c, len(t), t.shape[1], flush=True)


def cachecheck() -> dict:
    out = {}
    for p in sorted((OLD / "results" / "robust_cache").glob("CTU-*.parquet")):
        old = pd.read_parquet(p)
        new = pd.read_parquet(CACHE / p.name, columns=list(old.columns))
        out[p.stem] = bool(old.equals(new))
    (OUT.mkdir(parents=True, exist_ok=True))
    (OUT / "cachecheck.json").write_text(json.dumps(out, indent=2))
    print(out)
    return out


# --------------------------------------------------------------------------
# Memory-lean loading: only the columns of the pre-registered variant
# --------------------------------------------------------------------------
def _load(capture: str) -> pd.DataFrame:
    import pyarrow.parquet as pq
    names = pq.ParquetFile(CACHE / f"{capture}.parquet").schema_arrow.names
    keep = (list(CONN_NUMERIC) + list(CONN_CATEGORICAL) + ["capture", "incident_id", "cls", "y"]
            + [n for n in names if n.startswith(f"{VARIANT}|")])
    return pd.read_parquet(CACHE / f"{capture}.parquet", columns=keep)


def _setup() -> None:
    R.CACHE = CACHE
    R.load = _load


def _save(name, obj, preds, inputs, config):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(obj, indent=2), encoding="utf-8")
    preds.to_parquet(OUT / f"{name}_predictions.parquet")
    write_manifest(OUT / f"manifest_{name}.json", f"crosslog_v3_{name}",
                   inputs=[CACHE / f"{c}.parquet" for c in inputs] + [CACHE / "alert_categories.json"],
                   config={"rf_params": RF_PARAMS, "budget_per_class": TRAIN_BUDGET_PER_CLASS,
                           "variant": VARIANT, "plan": "experiments/v3/PLAN_V3.md §B", **config},
                   seeds=XV.SEEDS, outputs=[OUT / f"{name}.json", OUT / f"{name}_predictions.parquet"])


def primary() -> None:
    _setup()
    added = [c for c in NEW_CAPTURES if c in gated()]
    train = list(TRAIN) + added
    R.log(f"v3 primary: train {train}, test {TEST}")
    tr, te, ac = R.split(train, TEST)
    res, preds, samples = XV.run(tr, te, ac)
    _save("primary_augmented",
          {"train": train, "test": list(TEST), "added_training_captures": added, "seeds": list(XV.SEEDS),
           "train_classes": tr["cls"].value_counts().to_dict(),
           "test_classes": te["cls"].value_counts().to_dict(),
           "train_sample_classes_by_seed": samples,
           "context_availability_test": XV.context_availability(te, ac),
           "by_condition_seed": res, "summary": XV.summarise(res, XV.SEEDS),
           "per_capture": XV.per_capture(preds, XV.SEEDS)},
          preds, train + list(TEST), {"train": train, "test": list(TEST)})


def loco() -> None:
    _setup()
    caps = gated()
    excluded = {c: gate(c) for c in all_captures() if c not in caps}
    R.log(f"v3 leave-one-capture-out over {len(caps)} captures; excluded {list(excluded)}")
    folds, parts = {}, []
    for held in caps:
        train_caps = [c for c in caps if c != held]
        tr, te, ac = R.split(train_caps, [held])
        R.log(f"  fold {held}: train {len(tr):,}, test {len(te):,}")
        res, preds, samples = XV.run(tr, te, ac)
        folds[held] = {"n_test": int(len(te)), "test_classes": te["cls"].value_counts().to_dict(),
                       "train_classes": tr["cls"].value_counts().to_dict(),
                       "train_sample_classes_by_seed": samples,
                       "context_availability_test": XV.context_availability(te, ac)[held],
                       "test_attack_classes_unseen_in_train": sorted(set(te["cls"]) - set(tr["cls"])),
                       "by_condition_seed": res, "summary": XV.summarise(res, XV.SEEDS)}
        parts.append(preds)
        del tr, te
    preds = pd.concat(parts, ignore_index=True)
    fold_diff = {}
    pairs = [(c, "A") for c in ("B", "C", "D", "Z", "P")] + [(c, r) for c in "BCD" for r in "ZP"]
    for c, ref in pairs:
        d = np.array([folds[f]["summary"][f"{c}_minus_{ref}"]["mean"] for f in caps])
        fold_diff[f"{c}_minus_{ref}"] = {"per_fold": dict(zip(caps, d.round(6).tolist())),
                                         "folds_positive": int((d > 0).sum()),
                                         "folds_negative": int((d < 0).sum()), "n_folds": len(caps)}
    _save("loco", {"captures": caps, "excluded_by_gate": excluded, "seeds": list(XV.SEEDS),
                   "folds": folds, "fold_level_differences": fold_diff},
          preds, caps, {"captures": caps})


if __name__ == "__main__":
    step, *args = sys.argv[1:]
    {"stage3": lambda: [stage3(c) for c in args], "cache": cache, "cachecheck": cachecheck,
     "primary": primary, "loco": loco}[step]()
