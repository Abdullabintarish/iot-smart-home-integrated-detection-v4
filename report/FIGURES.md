# Figure captions

All figures were drawn by `pipeline/reporting.py` (run via `make_report.py`)
from `metrics/stage5_report.json` (a byte-identical copy of
`code/results/stage5_report.json`) or, for the two terminal figures, from the
run transcripts in `transcripts/`. The figure list is in `figures.json`.
Each value quoted below was checked against the figure image and against the
JSON path given in brackets. Values are rounded to the precision shown in the
figure; the JSON holds the full values.

"Test events" always means the 1,692,332 held-out events on which both
conditions are scored [`fragmented.n_test`, `integrated.n_test`].

---

## Figure 1 - `fig_terminal_stage1.png`

**Stage 1 collection transcript.** Rendering of `transcripts/stage1_run.log`:
`stage1_collect.py --root data/raw_combined` reads 13 source files (10 IoT-23
Zeek `conn.log.labeled` captures and 3 Bot-IoT CSV files) and lists, per
source, the number of rows read, the read time and the mapped class counts.
Total: 4,211,383 rows staged in 26 shards; peak RSS 556 MB; runtime 20 s.

Source: `transcripts/stage1_run.log` (not the JSON). The total of 4,211,383
equals `split.n_events` in `stage5_report.json`.

## Figure 2 - `fig_terminal_run.png`

**Stages 2-5 transcript.** Rendering of `transcripts/run_pipeline_run.log`
(`run_pipeline.py`): Stage 2 keeps 20 features and drops 6; Stage 3 groups
4,211,383 events into 704,090 incidents (alert reduction 0.8328); Stage 4
trains and scores both conditions on the same 1,692,332 held-out events
(baseline accuracy 0.9995, macro F1 0.9955, FPR 0.0046, FNR 0.0001;
integrated accuracy 0.9735, macro F1 0.8341, FPR 0.1021, FNR 0.0034);
Stage 5 prints alert reduction per dataset, robustness checks, the
clustered bootstrap interval of the macro-F1 difference (-0.1614
[-0.2055, -0.1280]) and the summary block. Total pipeline time 311.1 s,
peak RSS 3819 MB. The five scikit-learn "A single label was found" warnings
come from per-source evaluations in which the true and the predicted labels
are a single class: the fragmented per-source evaluation of
CTU-Honeypot-Capture-4-1, CTU-Honeypot-Capture-5-1,
CTU-IoT-Malware-Capture-42-1 and CTU-IoT-Malware-Capture-44-1, plus the
integrated per-source evaluation of CTU-IoT-Malware-Capture-44-1.
scikit-learn warns on any 1 x 1 confusion matrix; the metrics are still
correct (checked in Phase 4 validation).

Source: `transcripts/run_pipeline_run.log`. The metric values printed there
match `fragmented.*`, `integrated.*`, `alert_reduction.*` and
`bootstrap.difference.f1_macro` in `stage5_report.json`.

Note: the "strongest:" line in the Stage 2 output lists each feature's
absolute correlation with the class label for information only; feature
selection in this run used redundancy and constant-feature removal
(`FEATURE_SELECTION: "redundancy"` in `metrics/run_manifest.json`), not this
correlation.

## Figure 3 - `fig_metrics_comparison.png`

**Detection performance, fragmented baseline vs integrated condition, on
the held-out test events.** Grouped bars for accuracy, macro precision,
macro recall, macro F1, false-positive rate and false-negative rate (the
last two: lower is better). The integrated condition scores worse than the
baseline on all six metrics.

| Metric | Fragmented | Integrated | JSON path |
|---|---|---|---|
| Accuracy | 0.999 | 0.973 | `fragmented.accuracy` = 0.99946; `integrated.accuracy` = 0.97347 |
| Precision (macro) | 0.992 | 0.795 | `*.precision_macro` = 0.99218 / 0.79497 |
| Recall (macro) | 0.999 | 0.903 | `*.recall_macro` = 0.99886 / 0.90325 |
| F1 (macro) | 0.995 | 0.834 | `*.f1_macro` = 0.99545 / 0.83410 |
| FPR | 0.005 | 0.102 | `*.fpr` = 0.00461 / 0.10211 |
| FNR | 0.000 | 0.003 | `*.fnr` = 0.00015 / 0.00344 |

## Figure 4 - `fig_per_class_f1.png`

**Per-class F1 on the held-out test events.** For every class the
integrated condition has a lower F1 than the baseline; the largest gaps are
for malware and c2, the two smallest classes.

| Class | Test events | F1 fragmented | F1 integrated |
|---|---|---|---|
| benign | 122,807 | 0.997 | 0.925 |
| c2 | 3,283 | 0.982 | 0.739 |
| dos | 1,250,540 | 1.000 | 0.990 |
| malware | 1,278 | 1.000 | 0.587 |
| recon | 314,424 | 0.999 | 0.929 |

JSON paths: `fragmented.per_class.<class>.f1`,
`integrated.per_class.<class>.f1`, support from
`fragmented.per_class.<class>.support`.

## Figure 5 - `fig_confusion_fragmented.png`

**Confusion matrix of the fragmented baseline** (event counts; row-normalised
share in brackets; rows = actual class, columns = predicted class, order
benign, c2, dos, malware, recon). Off-diagonal counts: benign predicted as
dos 48 and as recon 518; dos predicted as benign 3 and as recon 1; recon
predicted as benign 228 and as c2 121. Diagonal: 122,241 / 3,283 /
1,250,536 / 1,278 / 314,075.

JSON path: `fragmented.confusion_matrix` (class order `fragmented.classes`).
The 566 benign events predicted as an attack (48 + 518) give
FPR = 566 / 122,807 = 0.0046 [`fragmented.binary_counts.false_positive`,
`fragmented.binary_counts.benign`, `fragmented.fpr`].

## Figure 6 - `fig_confusion_integrated.png`

**Confusion matrix of the integrated condition** (incident predictions
propagated to member events; same layout as Figure 5). Off-diagonal cells
(actual -> predicted) in descending order: recon -> dos 25,014;
benign -> recon 10,951; recon -> benign 5,370; benign -> c2 1,262;
recon -> c2 659; recon -> malware 647; benign -> malware 291;
dos -> recon 228; malware -> c2 149; c2 -> malware 131;
malware -> recon 125; benign -> dos 36; malware -> benign 29;
c2 -> benign 6; c2 -> recon 6; dos -> benign 1 (all others 0).
Diagonal: 110,267 / 3,140 / 1,250,311 / 975 / 282,734.

JSON path: `integrated.confusion_matrix`. Benign events predicted as an
attack: 12,540 of 122,807, FPR 0.1021
[`integrated.binary_counts.false_positive`, `integrated.fpr`].

## Figure 7 - `fig_importance_integrated.png`

**Random Forest (Gini) feature importance of the integrated model.** Only
three of the seven incident features are used: span_s 0.361,
events_per_s 0.334, n_events 0.305. The other four (n_src_ips, n_sources,
n_dst_ips, cross_source) have importance 0.0 - the forest never splits on
them, consistent with their being constant in the training sample (every
incident is formed within one source capture by the (src_ip, dst_ip,
protocol) rule, so each has one source, one source IP and one destination
IP, and no incident is cross-source).

JSON path: `integrated.feature_importance`.

## Figure 8 - `fig_alert_reduction.png`

**Overall alert reduction by Stage 3 correlation.** 4,211,383 raw events
(alerts) are grouped into 704,090 incidents: a reduction of 83.3%
(0.8328), mean 5.98 events per incident. This overall figure is dominated by
Bot-IoT (see Figure 9). Correlation is within each source capture; 0
incidents span more than one source.

JSON paths: `alert_reduction.raw_alerts`, `alert_reduction.unified_incidents`,
`alert_reduction.alert_reduction` (0.8328126413579577),
`alert_reduction.mean_alerts_per_incident`,
`alert_reduction.cross_source_incidents`.

## Figure 9 - `fig_alert_reduction_by_dataset.png`

**Alert reduction per dataset family (log scale).** Bot-IoT: 3,000,000
events into 2,619 incidents (99.91% reduction). IoT-23: 1,211,383 events into
701,471 incidents (42.09% reduction). The overall 83.28% therefore mostly
reflects the very large Bot-IoT flood and scan incidents.

JSON paths: `alert_reduction_by_dataset.per_dataset.Bot-IoT.*` (alert_reduction
0.999127) and `alert_reduction_by_dataset.per_dataset.IoT-23.*`
(alert_reduction 0.4209337591826863).
