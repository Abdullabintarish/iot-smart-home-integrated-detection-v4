"""End-to-end runner for the five-stage IoT monitoring pipeline.

    python run_pipeline.py [--staged data/interim] [--skip-cv] [--n-jobs 3]

Stages, in order:
  1. ingest      -> data/interim/*.parquet      (streamed from pcap/csv)
  2. preprocess  -> data/processed/stage2/*     (clean + normalise + select)
  3. correlate   -> data/processed/stage3_*     (incidents + alert stats)
  4. detect      -> models/rf_*.joblib          (Random Forest, both conditions)
  5. evaluate    -> results/*                   (baseline vs integrated, alert
                                                 reduction per dataset,
                                                 robustness checks, clustered
                                                 bootstrap CIs; per-event
                                                 predictions incl. diagnostics)

Both conditions are scored on the identical held-out set - every Stage 2
"test" event - so the Stage 5 comparison is like-for-like. Stage 4 holds the
test events plus bounded training samples in memory; other stages stream.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from pipeline import config as C
from pipeline.correlate import correlate_stream
from pipeline.correlate import INCIDENT_FEATURES
from pipeline.detect import event_features, run_stage4
from pipeline.evaluate import (alert_reduction_by_dataset,
                               alert_reduction_summary, cluster_bootstrap,
                               robustness, save_report)
from pipeline.io_utils import iter_parquet_dir, peak_rss_mb
from pipeline.preprocess import preprocess


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--staged", type=Path, default=C.DATA_INT,
                    help="directory of Stage 1 parquet shards")
    ap.add_argument("--skip-cv", action="store_true",
                    help="skip stratified cross-validation (faster)")
    ap.add_argument("--n-jobs", type=int, default=0,
                    help="override sklearn n_jobs (default: cpu_count-1)")
    args = ap.parse_args()

    if args.n_jobs:
        C.BUDGET.n_jobs = args.n_jobs

    t_start = time.perf_counter()
    C.RESULTS.mkdir(parents=True, exist_ok=True)

    log("STAGE 2 - preprocessing and log normalisation")
    t = time.perf_counter()
    plan, _ = preprocess(args.staged)
    log(f"  kept {len(plan.kept)} features, dropped {len(plan.dropped)} "
        f"in {time.perf_counter() - t:.1f}s")
    top = sorted(plan.correlations.items(), key=lambda kv: -kv[1])[:8]
    log("  strongest: " + ", ".join(f"{k}={v:.3f}" for k, v in top))

    log("STAGE 3 - event correlation and information integration")
    t = time.perf_counter()
    stage2 = C.DATA_OUT / "stage2"
    incidents, alert_stats = correlate_stream(
        iter_parquet_dir(stage2, batch_size=C.BUDGET.csv_chunksize))
    raw_event_total = int(alert_stats["raw_events"].sum()) \
        if not alert_stats.empty else 0
    if raw_event_total:
        # Incidents are merged across chunks, so this is the corpus figure.
        log(f"  {raw_event_total:,} events -> {len(incidents):,} incidents, "
            f"alert reduction {1 - len(incidents) / raw_event_total:.4f} "
            f"in {time.perf_counter() - t:.1f}s")

    log("STAGE 4 - detection: both conditions on the same held-out test events")
    t = time.perf_counter()
    features = event_features()
    log(f"  event features ({len(features)}): {', '.join(features)}")
    log(f"  incident features ({len(INCIDENT_FEATURES)}): "
        f"{', '.join(INCIDENT_FEATURES)}")
    stage4, preds = run_stage4(
        iter_parquet_dir(C.DATA_OUT / "stage3_events",
                         batch_size=C.BUDGET.csv_chunksize),
        incidents, features, do_cv=not args.skip_cv)
    frag, integ = stage4["fragmented"], stage4["integrated"]
    sp = stage4["split"]
    log(f"  split: {sp['n_train_incidents']:,} train / {sp['n_test_incidents']:,} "
        f"test incidents, {sp['n_mixed_incidents']} mixed; "
        f"{frag['n_test']:,} held-out events")
    for name, r in (("4a BASELINE fragmented (one model per source)", frag),
                    ("4b INTEGRATED (one model over incidents)", integ)):
        log(f"  {name}: accuracy={r['accuracy']:.4f} f1={r['f1_macro']:.4f} "
            f"fpr={r['fpr']:.4f} fnr={r['fnr']:.4f} "
            f"cv_f1={r.get('cv_f1_mean', float('nan')):.4f}"
            f"+-{r.get('cv_f1_std', float('nan')):.4f} "
            f"train={r['train_time_s']}s predict={r['predict_time_s']}s")
    inc = stage4["integrated_incident_level"]
    log(f"  incident-level (secondary): accuracy={inc['accuracy']:.4f} "
        f"f1={inc['f1_macro']:.4f} on {inc['n_samples']:,} test incidents")
    for k, d in stage4.get("diagnostics", {}).items():
        if isinstance(d, dict) and "f1_macro" in d:
            log(f"  diagnostic {k}: accuracy={d['accuracy']:.4f} "
                f"f1={d['f1_macro']:.4f} fpr={d['fpr']:.4f} fnr={d['fnr']:.4f}")
    log(f"  stage 4 total {time.perf_counter() - t:.1f}s")

    log("STAGE 5 - risk mitigation assessment")
    reduction = alert_reduction_summary(preds, incidents)
    # Compare like with like: incidents come from the FULL event stream, so
    # the raw-alert count must come from Stage 3's per-chunk statistics too.
    if raw_event_total:
        n_inc = reduction.get("unified_incidents", 0)
        reduction["raw_alerts"] = raw_event_total
        reduction["alert_reduction"] = 1 - (n_inc / max(1, raw_event_total))
        reduction["mean_alerts_per_incident"] = raw_event_total / max(1, n_inc)
    cols = ["event_id", "source", "incident_id", "split", "label"]
    cond_preds = {cond: preds[cols + [f"pred_{cond}"]].rename(
        columns={f"pred_{cond}": "pred"}) for cond in ("fragmented", "integrated")}
    by_dataset = alert_reduction_by_dataset(incidents)
    for name, d in by_dataset["per_dataset"].items():
        log(f"  alert reduction {name}: {d['events']:,} events -> "
            f"{d['incidents']:,} incidents ({d['alert_reduction']:.4f})")
    t = time.perf_counter()
    robust = robustness(cond_preds["fragmented"], cond_preds["integrated"],
                        incidents)
    small = robust["small_incidents"]
    log(f"  robustness (incidents <= {small['max_incident_events']:,} events; "
        f"{small['n_events_excluded']:,} events in "
        f"{small['n_incidents_excluded']} incidents excluded): "
        f"f1 fragmented={small['fragmented'].get('f1_macro', float('nan')):.4f} "
        f"integrated={small['integrated'].get('f1_macro', float('nan')):.4f}")
    vote = robust["incident_majority_vote"]
    log(f"  incident majority vote ({vote['n_incidents']:,} incidents): "
        f"f1 fragmented={vote['fragmented']['f1_macro']:.4f} "
        f"integrated={vote['integrated']['f1_macro']:.4f}")
    boot = cluster_bootstrap(cond_preds["fragmented"], cond_preds["integrated"],
                             n_boot=1000, seed=C.RANDOM_STATE)
    d = boot["difference"]["f1_macro"]
    log(f"  clustered bootstrap ({boot['n_boot']} reps, percentile CI, not a "
        f"significance test): macro F1 difference {d['point']:+.4f} "
        f"[{d['ci_low']:+.4f}, {d['ci_high']:+.4f}] "
        f"in {time.perf_counter() - t:.1f}s")
    extra = {k: v for k, v in stage4.items()
             if k not in ("fragmented", "integrated")}
    extra.update(alert_reduction_by_dataset=by_dataset, robustness=robust,
                 bootstrap=boot)
    save_report(frag, integ, reduction, extra=extra)
    for cond, df in cond_preds.items():
        df.to_csv(C.RESULTS / f"{cond}_event_predictions.csv", index=False)
    diag_cols = [c for c in ("pred_pooled", "pred_enriched") if c in preds]
    if diag_cols:
        preds[["event_id"] + diag_cols + ["label"]].to_csv(
            C.RESULTS / "diagnostic_event_predictions.csv", index=False)
    print()
    print((C.RESULTS / "stage5_summary.txt").read_text())
    log(f"TOTAL {time.perf_counter() - t_start:.1f}s  peak RSS {peak_rss_mb():.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())