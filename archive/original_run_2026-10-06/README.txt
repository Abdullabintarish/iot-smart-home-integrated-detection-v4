# Integrated Information Management for Cybersecurity Risk Mitigation
## IoT-Enabled Smart Home Networks — Experimental Results

Implemented from thesis section 3.2. Five stages — collection, preprocessing
and log normalisation, event correlation, threat detection, and risk
mitigation assessment — run under two monitoring conditions (fragmented
baseline vs integrated framework) on 13 real public data sources totalling
4,211,383 network flows.

## Headline result

- **83.3% alert consolidation**: 4,211,383 raw alerts -> 704,187 unified
  incidents (6.0 alerts per incident).
- **Accuracy**: 0.9989 (fragmented) -> 0.9369 (integrated), -6.19 pp.
- **F1 macro**: 0.9991 -> 0.8110, -18.81 pp.
- **False-positive rate**: 0.0000 -> 0.0444.
- **Cross-validation** (5-fold, macro F1): baseline 0.9323 +/- 0.0775,
  integrated 0.8210 +/- 0.0190.
- **Training time**: baseline 52.2 s on 30 features; integrated 15.8 s on 8.

The accuracy drop is the cost of consolidation, not a detection failure:
incidents are coarser than events, so one wrong incident label covers the
~6 flows it merged. Both conditions use an identical Random Forest and
identical metrics.

## Reproducibility

The full pipeline was run twice on identical inputs. Every metric was
identical between runs; only wall-clock timings differed. The figures in
`report/` are generated directly from the run artefacts.

## How to verify

Full run — ~11 minutes, exit 0, peak RSS 1.6 GB. Regenerates every artifact
below, including the two terminal screenshots, from the data sources:

    cd code
    python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
    ./run_all.sh data/raw_combined      # or: --skip-cv for a fast run

Pre-flight check only (no run needed):

    .venv/bin/python check_sources.py data/raw_combined

The venv must sit alongside `run_all.sh`, which resolves its interpreter as
`.venv/bin/python` relative to the working directory.

## What is in this bundle

    report/                     REPORT.md + 7 figures (see below)
    metrics/stage5_summary.txt  headline numbers, plain text
    metrics/stage5_report.json  machine-readable metrics
    metrics/baseline_vs_integrated.csv
    predictions/integrated_event_predictions.csv
    transcripts/                terminal transcripts of the verified run
    code/                       the pipeline, its drivers, requirements.txt

### Figures

- `fig_terminal_stage1.png` — collection stage: 13 sources loading
- `fig_terminal_run.png`    — full pipeline end to end
- `fig_alert_reduction.png` — 4.2M alerts -> 704k incidents
- `fig_metrics_comparison.png` — both conditions side by side
- `fig_confusion_fragmented.png` / `fig_confusion_integrated.png`
- `fig_importance_integrated.png` — feature importances

## Data sources (all public, named in thesis section 3.3)

- **IoT-23** (CTU): 10 captures, Zeek `conn.log.labeled` —
  CTU-Honeypot-Capture-{4,5}-1 and
  CTU-IoT-Malware-Capture-{1,3,8,20,21,34,42,44}-1.
- **Bot-IoT** (Kaggle, `vigneshvenkateswaran/bot-iot`): 3 of 75 files,
  630 MB — `data_1.csv` (reconnaissance), `data_10.csv` (DoS),
  `data_36.csv` (DDoS), per the scenarios named in section 3.3.

Raw data is not included (602 MB); `run_all.sh` stages it from
`data/raw_combined/` if you have it, or fetch it from the sources above.

## Methodological caveats

Stated up front in `report/REPORT.md`, section 6. The main ones:

- Per-source models are trained and tested on the same capture, so
  per-source accuracy is optimistic; cross-validation partially corrects
  this.
- Two benign honeypot captures score 1.0 accuracy with 0.0 F1 — they
  contain only benign flows, so their models cannot recognise attacks
  they never saw. That is the fragmented-monitoring limitation the
  framework addresses, not a bug.
- Correlation is time-windowed at 300 s and the captures were recorded
  months apart, so no incident spans two data sources here. Live
  deployment with simultaneous feeds is where cross-source consolidation
  materialises.
- Fragmented metrics are event-level; integrated metrics are
  incident-level, the unit its model operates on.
- The `dos` class covers both DoS and DDoS ground truth: the ingest layer
  harmonises vendor labels to a shared vocabulary, and separating
  distributed from single-source flooding needs rate and entropy features
  outside this feature plan.
