# Chapter 5: Results and Discussion

> **Drafting notes (delete before submission).**
> - Every number in this chapter is copied from a result file named next to it. Nothing was recomputed with new models.
> - §5.8.4 and Table 5.16 use a read-only re-tabulation of saved predictions: `thesis_writing_package/evidence/crosslog_breakdown.py`, with output in `crosslog_breakdown.json`. No model was trained for it.
> - Paths are relative to the repository root (`submission/`).
> - `[CITE: …]` marks where an external citation is needed.

## 5.1 Main Detection Results (Run B, primary experiment)

Both conditions were scored on the same 1,692,332 held-out events.

**Table 5.1 — Headline comparison** (evidence: `metrics/stage5_report.json` → `fragmented`, `integrated`, `bootstrap.difference`; `metrics/baseline_vs_integrated.csv`; `docs/thesis_final_validation/04_Verified_Results_and_Analysis.md` §1)

| Metric | Fragmented baseline | Integrated | Difference (I − F) | Bootstrap 95% interval of difference |
|---|---|---|---|---|
| Accuracy | 0.9995 | 0.9735 | −0.0260 | [−0.0895, −0.0079] |
| Precision (macro) | 0.9922 | 0.7950 | −0.1972 | — |
| Recall (macro) | 0.9989 | 0.9033 | −0.0956 | — |
| **F1 (macro)** | **0.9955** | **0.8341** | **−0.1614** | **[−0.2055, −0.1280]** |
| FPR | 0.0046 (566 / 122,807) | 0.1021 (12,540 / 122,807) | +0.0975 | [+0.0925, +0.1027] |
| FNR | 0.0001 (231 / 1,569,525) | 0.0034 (5,406 / 1,569,525) | +0.0033 | [+0.0018, +0.0097] |

**The fragmented baseline outperformed the integrated condition on all six metrics.** The bootstrap intervals of the differences exclude zero. These intervals treat incidents as independent and are likely too narrow (§5.9), so they describe variability; they are not significance tests.

[Insert Figure 5.1: `report/fig_metrics_comparison.png`]

**Table 5.2 — Per-class F1** (evidence: `metrics/stage5_report.json`; `docs/thesis_final_validation/04_Verified_Results_and_Analysis.md` §3)

| Class | Test events | Fragmented | Integrated |
|---|---|---|---|
| benign | 122,807 | 0.9968 | 0.9247 |
| c2 | 3,283 | 0.9819 | 0.7394 |
| dos | 1,250,540 | 1.0000 | 0.9900 |
| malware | 1,278 | 1.0000 | 0.5870 |
| recon | 314,424 | 0.9986 | 0.9293 |

[Insert Figure 5.2: `report/fig_per_class_f1.png`]

The largest losses are in the small classes, malware and c2. These classes had only 238 and 561 training incidents in the integrated condition.

## 5.2 Confusion Matrices

Rows are true classes and columns are predicted classes, in the order benign, c2, dos, malware, recon. (Evidence: `metrics/stage5_report.json`; `report/fig_confusion_fragmented.png`; `report/fig_confusion_integrated.png`.)

**Table 5.3 — Fragmented baseline**

| true \ pred | benign | c2 | dos | malware | recon |
|---|---|---|---|---|---|
| benign | 122,241 | 0 | 48 | 0 | 518 |
| c2 | 0 | 3,283 | 0 | 0 | 0 |
| dos | 3 | 0 | 1,250,536 | 0 | 1 |
| malware | 0 | 0 | 0 | 1,278 | 0 |
| recon | 228 | 121 | 0 | 0 | 314,075 |

**Table 5.4 — Integrated condition (incident prediction assigned to events)**

| true \ pred | benign | c2 | dos | malware | recon |
|---|---|---|---|---|---|
| benign | 110,267 | 1,262 | 36 | 291 | 10,951 |
| c2 | 6 | 3,140 | 0 | 131 | 6 |
| dos | 1 | 0 | 1,250,311 | 0 | 228 |
| malware | 29 | 149 | 0 | 975 | 125 |
| recon | 5,370 | 659 | 25,014 | 647 | 282,734 |

[Insert Figures 5.3 and 5.4: `report/fig_confusion_fragmented.png`, `report/fig_confusion_integrated.png`]

The integrated errors are concentrated in three cells:

1. **benign → recon (10,951 events).** This cell holds most of the 12,540 false positives.
2. **recon → dos (25,014 events).** Almost all come from one 24,385-event recon incident in Bot-IoT `data_1` that was predicted as dos.
3. **recon → benign (5,370 events).**

At incident level (175,489 test incidents), the integrated condition reached accuracy 0.9480, macro F1 0.7017, FPR 0.0330 and FNR 0.0834 (`docs/thesis_final_validation/04_Verified_Results_and_Analysis.md` §2).

## 5.3 Why the Integrated Condition Under-performed

The diagnostics locate the cause in the **incident representation**, not in the act of correlating events.

**Table 5.5 — Model comparison including diagnostics** (evidence: `metrics/stage5_report.json`; `docs/thesis_final_validation/04_Verified_Results_and_Analysis.md` §3; `../thesis_final_validation/verification/verification_results.json`)

| Model | Role | Features | Macro F1 | FPR |
|---|---|---|---|---|
| Fragmented (13 per-source) | Condition | 20 event | 0.9955 | 0.0046 |
| Integrated (incident → event) | Condition | 7 incident | 0.8341 | 0.1021 |
| Pooled event model | Diagnostic | 20 event | 0.9944 | 0.0039 |
| Enriched (event + incident context) | Diagnostic | 23 | 0.9961 | 0.0116 |
| Propagation ceiling | Upper bound | — | 0.9989 | 0.00015 |

Four observations follow from these figures:

1. **Correlation does not mix classes.** If every incident were labelled correctly, assigning its label to its events would give macro F1 0.9989. Only 111 incidents (166 test events) contain more than one label.
2. **Only three incident features vary.** `n_sources`, `n_src_ips`, `n_dst_ips` and `cross_source` are always 1 by construction (§3.5). Feature importance is spread across the other three: `span_s` 0.361, `events_per_s` 0.334, `n_events` 0.305 (`report/fig_importance_integrated.png`).
3. **Single-event incidents collapse to one feature vector.** The vector (n_events = 1, span = 0, rate = 0) belongs to 320,638 benign and 15,923 recon training incidents. As a result:
   - **Single-event incidents:** 0 of 106,379 benign test events in these incidents were false positives.
   - **Multi-event incidents:** 12,540 of 16,428 benign test events in these incidents were misclassified (FPR 0.763).

   Every integrated false positive therefore comes from a multi-event benign incident whose (count, span, rate) profile resembles scanning.
4. **Isolation per source is not what limits the baseline.** Pooling all sources into one event-level model changes macro F1 only slightly (0.9955 → 0.9944).

(Evidence for 1–4: `docs/thesis_final_validation/04_Verified_Results_and_Analysis.md` §5; verification checks V3, V4 and V12 in `../thesis_final_validation/verification/verification_results.json`.)

## 5.4 Robustness of the Main Result

**Table 5.6 — Robustness checks, Run B** (evidence: `metrics/stage5_report.json` → `robustness.small_incidents`, `robustness.incident_majority_vote`, `diagnostics.duplicates.novel_only_metrics`)

| Check | Events | Fragmented F1 | Integrated F1 | Fragmented FPR | Integrated FPR |
|---|---|---|---|---|---|
| All test events | 1,692,332 | 0.9955 | 0.8341 | 0.0046 | 0.1021 |
| Incidents ≤ 10,000 events | 363,035 | 0.9755 | 0.6472 | 0.0046 | 0.1021 |
| One majority vote per incident | 175,489 incidents | 0.9504 | 0.7017 | 0.0006 | 0.0330 |
| Feature vector not seen in training | 1,463,143 | 0.9910 | 0.7140 | 0.0346 | 0.7646 |

All four checks agree in direction.

Five-fold cross-validation on training data gave 0.9992 ± 0.0003 for the fragmented models and 0.7681 ± 0.0283 for the integrated model. These estimates cover different units and are not compared directly.

**Effect of very large incidents.** The seven largest test incidents contain 78.55% of test events: five Bot-IoT DoS conversations and two recon conversations. Event-level accuracy is therefore driven mostly by a few floods. This is why macro F1 is the headline metric.

## 5.5 Event-Record Consolidation (Alert Reduction)

**Table 5.7 — Events, incidents and alert reduction** (evidence: `metrics/stage5_report.json` → `alert_reduction`, `alert_reduction_by_dataset`; `metrics/stage3_alert_stats.csv`)

| | Events | Incidents | Alert reduction | Mean events per incident |
|---|---|---|---|---|
| IoT-23 (10 captures) | 1,211,383 | 701,471 | 42.09% | 1.73 |
| Bot-IoT (3 files) | 3,000,000 | 2,619 | 99.91% | 1,145.5 |
| **Overall** | **4,211,383** | **704,090** | **83.28%** | **5.98** |

[Insert Figures 5.5 and 5.6: `report/fig_alert_reduction.png`, `report/fig_alert_reduction_by_dataset.png`]

**Reading.** Correlation reduced the number of items to review by 83.28% overall. This figure is dominated by Bot-IoT floods, in which a single conversation produces hundreds of thousands of flow records. For the more realistic IoT-23 traffic the reduction was 42.09%. Per source, it ranged from 25.00% (Honeypot 4-1) to 99.998% (`data_36`).

No incident combined two sources (0 cross-source incidents). The overall figure should only be reported next to the per-dataset figures.

**Processing time.**

- The integrated model trained faster than the fragmented models (1.70 s vs 7.25 s) and predicted faster (0.34 µs vs 1.55 µs per event).
- However, it needs the correlation stage first, which took 92.2 s.
- No end-to-end efficiency gain is shown (`docs/thesis_final_validation/04_Verified_Results_and_Analysis.md` §7).

## 5.6 Temporal Validation (Run T)

In Run T every test event is later in time than every training event of its source.

**Table 5.8 — Run T vs Run B** (evidence: `../thesis_final_validation/supplementary_temporal/RESULTS.md` §3; `../thesis_final_validation/supplementary_temporal/code/results/stage5_report.json`)

| Metric | Run T fragmented | Run T integrated | Run B fragmented | Run B integrated |
|---|---|---|---|---|
| Test events | 1,052,847 | 1,052,847 | 1,692,332 | 1,692,332 |
| Accuracy | 0.9993 | 0.7155 | 0.9995 | 0.9735 |
| Macro F1 | 0.9992 | 0.7711 | 0.9955 | 0.8341 |
| FPR | 0.0044 | 0.0965 | 0.0046 | 0.1021 |
| FNR | 0.0002 | 0.0040 | 0.0001 | 0.0034 |

The bootstrap 95% interval of the Run T macro-F1 difference (integrated − fragmented) is [−0.3527, −0.1416].

**Findings:**

1. **The direction of the main result holds.** The comparison does not depend on interleaving training and test windows.
2. **The integrated FPR is almost unchanged** (0.1021 → 0.0965), with the same mechanism: 10,973 benign events predicted recon.
3. **The larger accuracy drop is partly an artefact of the cut.**
   - 282,900 Bot-IoT DoS test events were predicted recon.
   - Each Bot-IoT DoS file lasts only 105–202 s, so the cut truncates each flood conversation.
   - The test-side incidents are therefore short tails. Their median span is 1.4 s vs 61.8 s in training (data_10), and 0.1 s vs 34.0 s (data_36).

   For this reason, macro F1 and FPR are the more informative measures for Run T.
4. **Event features generalise forward in time; incident summaries do not.** The enriched diagnostic stayed close to the baseline (macro F1 0.9963).

## 5.7 Controlled Ablation

The ablation keeps the model, the training sample and the test events fixed, and changes only the input features.

**Data check.** The gate matched Run B exactly: 704,090 groups and 1,463,143 novel events (`experiments/ablation/results/full/checks.json`).

**Table 5.9 — Ablation results, 5 seeds** (evidence: `experiments/ablation/results/full/thesis_table.md`, `ablation_summary.csv`)

| Window (s) | Feature set | Macro F1 (mean ± SD) | FPR (mean ± SD) | Window cut |
|---|---|---|---|---|
| — | event_only | 0.9952 ± 0.0012 | 0.38% ± 0.05% | no |
| — | shared_event | 0.9977 ± 0.0002 | 0.20% ± 0.02% | no |
| 60 | event_plus_incident | 0.9965 ± 0.0003 | 1.18% ± 0.02% | no |
| 60 | incident_only | 0.7141 ± 0.0229 | 8.90% ± 0.01% | no |
| 150 | event_plus_incident | 0.9966 ± 0.0003 | 1.13% ± 0.01% | no |
| 150 | incident_only | 0.8110 ± 0.0051 | 9.37% ± 0.01% | no |
| **300** | **event_plus_incident** | **0.9964 ± 0.0003** | **1.14% ± 0.02%** | no |
| **300** | **incident_only** | **0.8566 ± 0.0035** | **9.16% ± 0.03%** | no |
| 300 | shared_plus_incident | 0.9971 ± 0.0005 | 0.96% ± 0.10% | no |
| 600 | event_plus_incident | 0.9950 ± 0.0001 | 1.18% ± 0.01% | yes |
| 600 | incident_only | 0.8465 ± 0.0071 | 9.31% ± 0.03% | yes |
| 900 | event_plus_incident | 0.9949 ± 0.0004 | 1.18% ± 0.01% | yes |
| 900 | incident_only | 0.8481 ± 0.0048 | 9.52% ± 0.05% | yes |

The full table, with `shared_plus_incident` at every window, is in `experiments/ablation/results/full/thesis_table.md`.

**Table 5.10 — Paired bootstrap of differences, 300 s** (evidence: `experiments/ablation/results/full/bootstrap.json`; incident-clustered, 1,000 replicates)

| Comparison | Macro-F1 difference, 95% interval | FPR difference, 95% interval |
|---|---|---|
| incident_only − event_only | [−0.1761, −0.1072] | [+0.0836, +0.0909] |
| event_plus_incident − event_only | [−0.0014, +0.0048] | [+0.0060, +0.0081] |
| shared_plus_incident − shared_event | [−0.0021, +0.0016] | [+0.0080, +0.0099] |

**Where the extra false positives occur.** Table 5.11 restricts the comparison to benign test events inside multi-event incidents (16,428 events), using the same `ablation_summary.csv`.

**Table 5.11 — FPR on benign events in multi-event incidents, 300 s, 5 seeds**

| Feature set | FPR |
|---|---|
| event_only | 2.59% |
| event_plus_incident | 8.12% |
| incident_only | 68.45% |

[Insert Figure 5.7: `experiments/thesis_report/fig_2_ablation.png`]

**Findings:**

1. **Replacing event features with incident features causes the Run B loss.** With the classifier, training sample and test set held fixed, `incident_only` loses 0.11–0.18 macro F1 and raises the FPR by about 8–9 percentage points. This isolates the mechanism found in §5.3.
2. **Adding incident context to event features does not improve detection.** The macro-F1 interval includes zero. The FPR roughly triples (0.38% → 1.14%) at every window and in every seed, and the increase is concentrated in multi-event benign incidents.
3. **The result is not caused by the dataset fingerprint.** The `shared_*` feature sets, which remove dataset-specific columns, show the same pattern.
4. **Window length matters for `incident_only` but not for the conclusion.** Its macro F1 rises from 0.714 (60 s) to 0.857 (300 s) and then levels off. It never approaches the event-level models.

## 5.8 Cross-Log Correlation Findings

The cross-log experiment tests a form of integration that Run B could not test: correlating **different log types** (connection logs, DNS logs and IDS alerts) produced from the same network traffic. It evaluates them on **networks not seen in training**.

### 5.8.1 Stage 3: Linking and label transfer

**Table 5.12 — Stage 3 results per capture** (evidence: `experiments/cross_log/results/stage3_CTU-IoT-Malware-Capture-<id>.json`; `experiments/RUN_LOG.md` §4.5, §5.4)

| Capture | Conn records | Match rate | DNS | Alerts | Incidents | Incidents with ≥ 2 log types | Gate |
|---|---|---|---|---|---|---|---|
| 8-1 | 10,403 | 1.0000 | 0 | 0 | 278 | 0 | fail |
| 20-1 | 3,209 | 1.0000 | 808 | 0 | 24 | 23 | pass |
| 42-1 | 4,426 | 1.0000 | 1,841 | 2,019 | 41 | 39 | pass |
| 21-1 | 3,286 | 1.0000 | 2,578 | 0 | 58 | 56 | pass |
| 3-1 | 156,103 | 1.0000 | 12 | 50,529 | 428 | 235 | pass |
| 34-1 | 8,990 | 0.9998 | 348 | 7,877 | 165 | 159 | pass |
| 1-1 | 1,008,748 | 1.0000 | 19 | 41 | 1,350 | 59 | pass |
| 48-1 (R3 only) | 3,394,338 | 1.0000 | 24 | 28 | 121 | 8 | pass |
| 49-1 | 6,022,729 | 0.8984 | 44 | 1,394 | 100 | 98 | **fail (excluded)** |

**Findings:**

- **Cross-log linking was achieved.** Across the seven design captures, 571 of 2,344 incidents combine at least two log types. 42 incidents contain all three types (29 in 42-1 and 13 in 34-1).
- **Label transfer was nearly exact.** Every gate-passing capture matched at least 99.98% of its new connection records to IoT-23 labels.

**Data limitation in 34-1.** Only 237 of 14,394 labelled DDoS rows have a counterpart. IoT-23's published log records one flood flow as 14,159 one-packet rows. Neither Bro 2.6.4 nor Zeek 9.0.1 reproduces that from the published pcap (`experiments/RUN_LOG.md` §4.6).

### 5.8.2 Primary result (capture-held-out, design fixed in advance)

**Data:**

- **Training:** 1,172,486 rows from captures 1-1, 3-1, 20-1 and 42-1 (recon 685,062; benign 481,424; malware 5,965; **c2 35**).
- **Test:** 22,677 rows from captures 8-1, 21-1 and 34-1 (**c2 14,942**; benign 7,376; dos 237; recon 122).

**Table 5.13 — Cross-log primary result, 5 seeds** (evidence: `experiments/cross_log/results/stage4_results.json`; `experiments/RUN_LOG.md` §5.2)

| Condition | Macro F1 (mean ± SD) | FPR | FNR | FPR on unseen benign (n = 1,964) |
|---|---|---|---|---|
| A — connection | 0.3346 ± 0.1973 | 0.27% | 89.12% | 1.03% |
| B — + DNS | 0.5016 ± 0.1688 | 0.43% | 70.61% | 1.63% |
| C — + alerts | 0.4161 ± 0.1627 | 0.19% | 81.10% | 0.39% |
| D — + DNS + alerts | 0.5865 ± 0.1533 | 0.92% | 59.76% | 1.72% |

[Insert Figure 5.8: `experiments/thesis_report/fig_3_crosslog_seeds.png`]

**Per-class detection rate (mean over seeds):**

| Class | A | B | C | D |
|---|---|---|---|---|
| c2 | 0.111 | 0.300 | 0.193 | 0.412 |
| dos (237 rows) | ≤ 0.03 | ≤ 0.03 | ≤ 0.03 | ≤ 0.03 |
| recon (122 rows) | ≤ 0.03 | ≤ 0.03 | ≤ 0.03 | ≤ 0.03 |

DoS and recon were almost never detected under any condition.

### 5.8.3 Robustness analyses

**Table 5.14 — Cross-log robustness** (evidence: `experiments/cross_log/results/robustness/R0_reproduction.json`, `R1_20_seeds.json`, `R2_two_level_bootstrap.json`, `R4_connection_end.json`, `R5_windows.json`, `R3_leave_one_capture_out.json`)

| Analysis | B − A | C − A | D − A |
|---|---|---|---|
| R0: cache reproduces primary seed-42 predictions | identical | identical | identical |
| R1: 20 seeds, mean difference (seeds > 0) | +0.223 (20/20) | +0.110 (18/20) | +0.268 (20/20) |
| R1: Wilcoxon signed-rank, two-sided p | 1.9 × 10⁻⁶ | 1.9 × 10⁻⁵ | 1.9 × 10⁻⁶ |
| R2: bootstrap over seeds and incidents, 95% interval | [+0.063, +0.350] | [−0.001, +0.150] | [+0.150, +0.367] |
| R4: windows anchored at connection end | +0.243 (5/5) | +0.054 (3/5) | +0.237 (5/5) |
| R5: 60 s window | +0.289 (5/5) | +0.152 (5/5) | +0.316 (5/5) |
| R5: 900 s window | +0.164 (5/5) | +0.054 (2/5) | +0.226 (5/5) |
| R3: leave-one-capture-out, folds > 0 (of 8) | 5 | 6 | 6 |
| R3: pooled over all folds, mean difference | −0.009 | +0.023 | +0.029 |

On the fixed split, the ordering D > A and B > A is stable across seeds, windows and window anchoring. The R3 per-fold results are in Table 5.16.

### 5.8.4 Critical assessment of the cross-log result

A closer reading of the saved predictions shows that the result in Tables 5.13 and 5.14 must be interpreted with care. All figures below are from `thesis_writing_package/evidence/crosslog_breakdown.json`.

**(a) Condition A is close to a trivial classifier.**

- Predicting every test row as benign gives a binary macro F1 of **0.2454**.
- In four of five seeds, condition A scored 0.2460–0.2469 (FNR ≈ 0.999). It flagged almost no attacks.
- In seed 4 it scored 0.6876.

The cause is the data: the training captures contain **35** C&C rows, but 97.7% of the attack rows in the test set are C&C (14,942 of 15,301). Part of the large seed-to-seed variance (SD ≈ 0.2) comes from whether a given training sample happens to separate this pattern.

**(b) Gains on capture 8-1 cannot come from DNS or alert content.**

- Capture 8-1 has **no DNS records and no alerts**. All of its context features are exactly zero (`8-1_nonzero_context_values` = 0).
- Yet C&C detection in 8-1 changes with the condition: A 0.20, B 0.30, C 0.35, D 0.40, as means over seeds. The per-seed values are quantised at 0, 0.25 and 1.0.
- 8-1 contributes 45.9% of test rows and 55.0% of test C&C rows.

The model has learned something about the **absence** of context (in training, hosts with DNS and alert activity are mostly benign), and the extra columns change the trees grown by the Random Forest. Neither effect is evidence that correlating DNS or alert content helps.

**Table 5.15 — Macro F1 with and without capture 8-1 (mean of 5 seeds)**

| Test rows | A | B | C | D |
|---|---|---|---|---|
| All three test captures | 0.3346 | 0.5016 | 0.4161 | 0.5865 |
| Without 8-1 (21-1, 34-1) | 0.2998 | 0.5512 | 0.2991 | 0.6350 |
| 8-1 only (no DNS, no alerts) | 0.3387 | 0.4322 | 0.4789 | 0.5257 |

**(c) Alert features help only where alerts are absent.** In leave-one-capture-out (Table 5.16), C − A is about +0.14 to +0.15 on the three folds whose test capture has **zero** alerts (8-1, 20-1, 21-1). On the five folds whose test capture does have alerts, C − A ranges from −0.145 to +0.056. The evidence therefore does not support a benefit from IDS-alert content.

**Table 5.16 — Leave-one-capture-out, mean macro F1 over 5 seeds** (evidence: `experiments/cross_log/results/robustness/R3_leave_one_capture_out.json`; re-tabulated in `crosslog_breakdown.json`)

| Held-out capture | DNS in test capture | Alerts in test capture | A | B | C | D | B − A | C − A | D − A |
|---|---|---|---|---|---|---|---|---|---|
| 1-1 | 19 | 41 | 0.891 | 0.868 | 0.946 | 0.946 | −0.023 | +0.056 | +0.056 |
| 3-1 | 12 | 50,529 | 0.517 | 0.518 | 0.522 | 0.519 | +0.001 | +0.004 | +0.001 |
| 8-1 | **0** | **0** | 0.173 | 0.360 | 0.314 | 0.360 | +0.187 | +0.140 | +0.187 |
| 20-1 | 808 | **0** | 0.543 | 0.653 | 0.692 | 0.719 | +0.110 | +0.149 | +0.176 |
| 21-1 | 2,578 | **0** | 0.606 | 0.773 | 0.754 | 0.898 | +0.167 | +0.149 | +0.293 |
| 34-1 | 348 | 7,877 | 0.175 | 0.483 | 0.187 | 0.330 | +0.308 | +0.012 | +0.155 |
| 42-1 | 1,841 | 2,019 | 0.398 | 0.357 | 0.358 | 0.358 | −0.041 | −0.039 | −0.040 |
| 48-1 | 24 | 28 | 0.997 | 0.996 | 0.852 | 0.976 | −0.001 | −0.145 | −0.021 |

**(d) The clearest content-based evidence is DNS on capture 34-1.**

- Capture 34-1 has 348 DNS records. Adding DNS context raised C&C detection there from 0.001 (A) to 0.30 (B) on average, and to 0.42 with all logs (D).
- In leave-one-capture-out, B − A on the 34-1 fold is +0.31.
- DNS context also helped on the 20-1 and 21-1 folds, which have DNS but no alerts.
- However, it reduced macro F1 on the 42-1 fold, which has the second-largest DNS volume (1,841 records).

**(e) The cost in false alarms is small but consistent.** Condition D raised the FPR from 0.27% to 0.92%, and the FPR on unseen benign rows from 1.03% to 1.72%.

**Defensible statement of the cross-log finding.** On networks not seen in training, adding context from other log types to connection records changed detection substantially. On average it improved detection, most clearly with DNS. However:

- absolute detection remained low (macro F1 ≤ 0.59; most C&C missed);
- the improvement was not consistent across held-out networks;
- part of the measured gain cannot be attributed to the content of the correlated logs.

The experiment shows that cross-log correlation is *feasible* and *can* add useful information, especially DNS. It does not establish that cross-log correlation reliably improves detection.

**Earlier write-ups.** This assessment is more cautious than `experiments/THESIS_ADDITIONS.md` and `experiments/thesis_report/Thesis_Experiments_Report.docx`, which describe the improvement as occurring "on most unseen networks". The thesis should use the wording above.

## 5.9 Statistical Uncertainty

| Experiment | Uncertainty available | Limitation |
|---|---|---|
| Run B | Incident-clustered bootstrap of the difference (1,000 replicates) | One seed; incidents within a capture are not independent, so intervals are likely too narrow |
| Run T | Same bootstrap | Same |
| Ablation | 5 seeds (mean ± SD) and a paired incident-clustered bootstrap | One train/test split |
| Cross-log | 5 seeds (primary); 20 seeds with a Wilcoxon test (R1); two-level bootstrap over seeds and incidents (R2); 8-fold leave-one-capture-out (R3) | 7–8 captures, each with one infected device; very high seed variance; the effects in §5.8.4 are not captured by these intervals |

A capture-level (hierarchical) bootstrap was not possible for Run B: it would have only 13 clusters.

## 5.10 Reasons for the Differences in Performance

Across the four experiments, the evidence points to one consistent explanation:

1. **What is lost is event-level behavioural detail.**
   - The integrated model sees only counts, spans and rates.
   - When these replace ports, bytes, flags and states, detection degrades: Run B, Run T and the ablation's `incident_only` set all show this.
   - When incident context is *added* to event features, macro F1 does not change but false positives rise: the ablation's `event_plus_incident` set and the enriched diagnostic both show this.
2. **Within-source correlation adds little new information.**
   - Run B incidents group events that share the same IP pair within 300 s.
   - Their summary describes volume and timing, which the event features largely already capture.
   - Benign multi-event activity has volume and timing profiles similar to scanning, which explains the benign → recon errors.
3. **Different log types can add new information, but the evidence is limited.** DNS activity is information a connection record does not contain, and it helped on some unseen networks. The small number of captures, the near-absence of C&C training data and the confounding in §5.8.4 limit what can be concluded.
4. **Correlation itself is sound.**
   - The propagation ceiling (0.9989) shows that grouping events loses almost nothing when incidents are labelled correctly.
   - The cross-log linking reached 99.98–100% label-match rates.

## 5.11 Methodological Limitations

The full list, with severity and evidence, is in `Academic_Limitations.md`. The limitations that most constrain the conclusions are:

- **No independent multi-source data.**
  - Run B correlates within each source (0 cross-source incidents).
  - The cross-log experiment correlates log types derived from one packet capture. These are not independent device, gateway and cloud sensors.
- **Research datasets, not live smart homes.** IoT-23 and Bot-IoT are captured in a laboratory, honeypot or testbed. Each IoT-23 malware capture contains one infected device.
- **Within-capture evaluation in Run B and Run T.** Only the cross-log experiment tests unseen networks, and it does so with 7–8 small captures.
- **Class coverage.** There are no botnet, brute-force or theft classes, and DoS and DDoS are merged. Malware occurs in two captures, and the cross-log training data contain 35 C&C rows.
- **Risk mitigation was not measured directly.** No response, containment, analyst-time or risk-model outcome was measured.

## 5.12 Implications for Cybersecurity Risk Mitigation

The results support three practical implications for monitoring IoT smart homes. They are conditional and indirect; no risk reduction was measured.

1. **Correlation reduces alert volume.** Fewer items to review addresses the alert-overload problem identified in the literature (Part 1 §2.4, fourth gap) [CITE: Albasheer et al., 2022] [CITE: Maosa et al., 2024]. The reduction was 42.09% on IoT-23 traffic and 83.28% overall.
2. **Correlation should not replace event-level detection.** A monitoring design that classifies only incident summaries would have produced about 22 times more false positives in this experiment (FPR 10.21% vs 0.46%). This would increase analyst load rather than reduce it. The safer design keeps event-level detection and uses correlation to group, prioritise and present the alerts.
3. **Cross-log-type context is the promising direction.** DNS context improved detection of C&C traffic on some unseen networks. In a smart home, a gateway could plausibly record such context alongside connection logs [CITE: needed]. This needs confirmation on independent, simultaneously recorded multi-sensor data before it can be recommended.

## 5.13 Answer to the Research Question

> **RQ1:** How does the integration and correlation of distributed IoT logs and alerts affect cybersecurity threat detection accuracy in IoT-enabled smart home networks?

The experiments together answer RQ1 as follows:

1. **Integration through incident summaries lowers detection accuracy.** In the primary experiment, correlating flow events into incidents and detecting threats from incident features was **less accurate** than per-source event-level detection:
   - macro F1: 0.8341 vs 0.9955;
   - FPR: 10.21% vs 0.46%.

   The direction held under a temporal hold-out (Run T: 0.7711 vs 0.9992).
2. **The cause is the representation, not correlation.** The controlled ablation showed that the loss comes from replacing event features with incident features (−0.11 to −0.18 macro F1).
3. **Adding incident context to event features does not improve accuracy.** Macro F1 was unchanged, and the false-positive rate roughly tripled.
4. **Integration does consolidate alerts substantially.** The alert reduction was 83.28% overall and 42.09% on IoT-23.
5. **Correlation across different log types can add information on unseen networks.** On average, adding DNS and alert context raised macro F1 (from 0.335 to 0.586), mainly through DNS context. However, the effect varied between networks, absolute detection stayed low, and part of the gain could not be attributed to the correlated log content.

**Overall answer.** In this study, the effect of integration on detection accuracy depended on *what* was integrated:

- summarising events of the same log type **reduced** accuracy;
- adding the same-log-type summary to event features **did not improve** accuracy and increased false alarms;
- adding information from **other log types** showed **potential** to improve accuracy, which could not be fully confirmed with the available data.

Integration reliably reduced the volume of alerts to be reviewed.
