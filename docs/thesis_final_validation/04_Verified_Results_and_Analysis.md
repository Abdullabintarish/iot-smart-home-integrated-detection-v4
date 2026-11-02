# 04 — Verified Results and Analysis

**Provenance labels:**
- **[B]** — previously reported in Run B (R, `submission/metrics/stage5_report.json`) and re-verified in this phase (VR V1).
- **[V]** — new in this phase, derived read-only from Run B/C artifacts (VR, `thesis_final_validation/verification/verification_results.json`).
- **[T]** — new supplementary temporal hold-out run, approved and run 2026-11-01 UTC in a code copy (`supplementary_temporal/`). It is a robustness check, not the primary result.

No model of Run B was retrained.

## 1. Headline comparison (1,692,332 identical held-out events) [B]

| Metric | Fragmented baseline | Integrated | Difference (I − F) | Clustered-bootstrap 95% interval of difference |
|---|---|---|---|---|
| Accuracy | 0.9995 | 0.9735 | −0.0260 | [−0.0895, −0.0079] |
| Precision (macro) | 0.9922 | 0.7950 | −0.1972 | — |
| Recall (macro) | 0.9989 | 0.9033 | −0.0956 | — |
| F1 (macro) | 0.9955 | 0.8341 | −0.1614 | [−0.2055, −0.1280] |
| FPR | 0.0046 (566 / 122,807) | 0.1021 (12,540 / 122,807) | +0.0975 | [+0.0925, +0.1027] |
| FNR | 0.0001 (231 / 1,569,525) | 0.0034 (5,406 / 1,569,525) | +0.0033 | [+0.0018, +0.0097] |

The integrated condition is worse on every metric. The bootstrap intervals (R `bootstrap.difference`) exclude zero, but they treat incidents as independent and are likely too narrow (06 §1). They describe variability; they are not significance tests.

## 2. Confusion matrices (rows = true, columns = predicted) [B, recomputed V1]

Class order: benign, c2, dos, malware, recon.

**Fragmented baseline**

| true \ pred | benign | c2 | dos | malware | recon |
|---|---|---|---|---|---|
| benign | 122,241 | 0 | 48 | 0 | 518 |
| c2 | 0 | 3,283 | 0 | 0 | 0 |
| dos | 3 | 0 | 1,250,536 | 0 | 1 |
| malware | 0 | 0 | 0 | 1,278 | 0 |
| recon | 228 | 121 | 0 | 0 | 314,075 |

**Integrated (incident prediction propagated to events)**

| true \ pred | benign | c2 | dos | malware | recon |
|---|---|---|---|---|---|
| benign | 110,267 | 1,262 | 36 | 291 | 10,951 |
| c2 | 6 | 3,140 | 0 | 131 | 6 |
| dos | 1 | 0 | 1,250,311 | 0 | 228 |
| malware | 29 | 149 | 0 | 975 | 125 |
| recon | 5,370 | 659 | 25,014 | 647 | 282,734 |

The dominant integrated errors are:
- **benign → recon:** 10,951 events, most of the 12,540 false positives;
- **recon → dos:** 25,014 events, one 24,385-event data_1 incident predicted dos (VR V7);
- **recon → benign:** 5,370 events.

**Integrated, incident level (175,489 test incidents)** [B]: accuracy 0.9480, macro F1 0.7017, FPR 0.0330, FNR 0.0834.

| true \ pred | benign | c2 | dos | malware | recon |
|---|---|---|---|---|---|
| benign | 107,586 | 34 | 10 | 24 | 3,603 |
| c2 | 5 | 165 | 0 | 3 | 1 |
| dos | 1 | 0 | 9 | 0 | 3 |
| malware | 26 | 3 | 0 | 31 | 5 |
| recon | 5,328 | 33 | 13 | 27 | 58,579 |

## 3. Model comparison including the diagnostics [B]

| Model | Role | Features | Accuracy | Macro P | Macro R | Macro F1 | FPR | FNR |
|---|---|---|---|---|---|---|---|---|
| Fragmented (13 per-source) | Condition | 20 event | 0.9995 | 0.9922 | 0.9989 | 0.9955 | 0.0046 | 0.00015 |
| Integrated (incident → event) | Condition | 7 incident | 0.9735 | 0.7950 | 0.9033 | 0.8341 | 0.1021 | 0.0034 |
| Pooled event model | Diagnostic | 20 event | 0.9996 | 0.9901 | 0.9989 | 0.9944 | 0.0039 | 0.00011 |
| Enriched (event + incident context) | Diagnostic | 23 | 0.9991 | 0.9947 | 0.9975 | 0.9961 | 0.0116 | 0.00005 |
| *Propagation ceiling* [V] | Upper bound, not a model | — | 0.99998 | 0.9978 | 0.99996 | 0.9989 | 0.00015 | 0.000007 |

**Per-class F1** [B]:

| Class | Test events | Fragmented | Integrated | Pooled | Enriched |
|---|---|---|---|---|---|
| benign | 122,807 | 0.9968 | 0.9247 | 0.9973 | 0.9939 |
| c2 | 3,283 | 0.9819 | 0.7394 | 0.9753 | 0.9933 |
| dos | 1,250,540 | 1.0000 | 0.9900 | 1.0000 | 1.0000 |
| malware | 1,278 | 1.0000 | 0.5870 | 1.0000 | 0.9957 |
| recon | 314,424 | 0.9986 | 0.9293 | 0.9992 | 0.9976 |

**Readings:**
- **Fragmented vs pooled** (F1 0.9955 vs 0.9944): with event features, pooling the sources into one model changes little. Isolation per source is not what limits the baseline.
- **Pooled vs enriched** (F1 0.9944 → 0.9961; FPR 0.0039 → 0.0116): adding incident context to event features gives a small macro-F1 gain, driven by c2 (0.9753 → 0.9933), but it **triples** the FPR. The net effect of incident context is mixed, not a clear improvement.
- **Integrated vs ceiling** (0.8341 vs 0.9989): correlating events into incidents loses almost nothing when incidents are labelled correctly. The loss comes from classifying incidents with only three informative features.

## 4. Robustness checks [B]

| Check | Events | Fragmented F1 | Integrated F1 | Fragmented FPR | Integrated FPR |
|---|---|---|---|---|---|
| All test events | 1,692,332 | 0.9955 | 0.8341 | 0.0046 | 0.1021 |
| Incidents ≤ 10,000 events (7 incidents removed) | 363,035 | 0.9755 | 0.6472 | 0.0046 | 0.1021 |
| One majority vote per incident | 175,489 incidents | 0.9504 | 0.7017 | 0.0006 | 0.0330 |
| Events with a feature vector not seen in training | 1,463,143 | 0.9910 | 0.7140 | 0.0346 | 0.7646 |

**Cross-validation on training data** [B]:
- **Fragmented:** 0.9992 ± 0.0003 (6 of 13 sources eligible).
- **Integrated:** 0.7681 ± 0.0283.

These estimates cover different units and are not compared directly.

All four checks agree in direction with §1.

**Effect of incident size** [V]: the 7 largest test incidents hold **78.55%** of test events. They are five DoS/DDoS conversations of 230,519 to 271,637 events and two data_1 recon conversations of 54,612 and 24,385 events (VR V7). Event-level accuracy is therefore driven mostly by a handful of Bot-IoT floods, and macro F1 and per-class figures are the more informative measures.

## 5. Why the integrated model under-performs [V]

1. **Only three features vary.** `n_sources`, `n_src_ips`, `n_dst_ips` and `cross_source` are always 1 (VR V4). Feature importance confirms it: `span_s` 0.361, `events_per_s` 0.334, `n_events` 0.305, and 0 for the other four (VR V3).
2. **Single-event incidents collapse onto one vector.** The training vector (n_events = 1, span = 0, rate = 0) belongs to 320,638 benign and 15,923 recon incidents (plus 82 malware, 15 c2 and 1 dos). 95.6% of benign training incidents are single-event, against 8.3% of recon (VR V12). The model predicts benign for this vector, so:
   - benign test events in single-event incidents: **0** false positives out of 106,379;
   - benign test events in **multi-event** incidents: **12,540 of 16,428** misclassified, an FPR of 0.763. **All** integrated false positives come from multi-event benign incidents, whose (count, span, rate) profile resembles scanning; for example, vectors with 3 events over about 15 s occur about 11× more often as recon than as benign.
3. **Small attack classes** in the integrated training data: 26 dos, 238 malware and 561 c2 incidents. Test incidents: 13, 65 and 174.
4. **No flow content.** The integrated model never sees ports, bytes or flags, which the baseline uses.

Correlation itself is not the cause: mixed-label incidents are negligible (111 incidents; 166 test events), and the propagation ceiling is F1 0.9989.

## 6. Event, incident and correlation statistics [B]

| | Events | Incidents | Alert reduction | Mean events / incident |
|---|---|---|---|---|
| IoT-23 (10 captures) | 1,211,383 | 701,471 | 42.09% | 1.73 |
| Bot-IoT (3 files) | 3,000,000 | 2,619 | 99.91% | 1,145.5 |
| **Overall** | **4,211,383** | **704,090** | **83.28%** | **5.98** |

- **Spread across captures:** per-source reduction ranges from 25.0% (Capture-4-1) to 99.998% (data_36); see 03 §2.
- **Cross-source incidents:** 0.
- **Correlation rule:** R1 only.
- **Training/test incidents:** 528,601 / 175,489, with 0 mixed.

**Reading:** the 83.28% headline is dominated by Bot-IoT floods, in which one conversation produces hundreds of thousands of flow records. For the more realistic IoT-23 traffic the reduction is 42.09%. Report the overall figure only next to the per-dataset figures.

## 7. Processing time (Run B, Intel i7-14700KF, 28 logical cores) [B]

| Item | Fragmented | Integrated |
|---|---|---|
| Model training | 7.2547 s (11 RF) | 1.6999 s (1 RF) |
| Prediction per event | 1.5527 µs | 0.3378 µs |
| Extra pipeline stage | — | Stage 3 correlation 92.2 s (all events) |

Full run: 338.3 s, peak RSS 3,819 MB.

Run C, on an AMD Ryzen 7 7800X3D: training 7.8037 s / 1.7572 s and a total of 374.6 s. Its timings differ, but every prediction is identical.

**Reading:** the integrated model trains and predicts faster, but only after a correlation stage that costs more than both trainings combined. No end-to-end efficiency gain is shown.

## 8. Supplementary temporal hold-out (Run T) [T]

Approved and run in a code copy. Full details are in `supplementary_temporal/RESULTS.md`.

**Split:** per source, test = events after the source's 75th time percentile (1,052,847 test events, all 5 classes). Every test event is later than every training event, and 0 incidents cross the cut.

| Metric | Fragmented | Integrated | Run B fragmented | Run B integrated |
|---|---|---|---|---|
| Accuracy | 0.9993 | 0.7155 | 0.9995 | 0.9735 |
| F1 (macro) | 0.9992 | 0.7711 | 0.9955 | 0.8341 |
| FPR | 0.0044 | 0.0965 | 0.0046 | 0.1021 |
| FNR | 0.0002 | 0.0040 | 0.0001 | 0.0034 |

The bootstrap 95% interval for the macro-F1 difference is [−0.3527, −0.1416].

**Readings:**
- **Same direction, same false-positive mechanism:** the direction of the result holds, and FPR stays close to its Run B value, driven by benign → recon.
- **Bigger accuracy drop:** this comes mainly from Bot-IoT DoS. 282,900 dos test events are predicted recon, because the cut truncates the short Bot-IoT flood conversations into test-side tails of 0.1–1.4 s median span.
- **Report accuracy with this caveat.** Macro F1 and FPR are the more reliable comparison here.

## 9. Interpretation for RQ1

In this experiment, integration and correlation **reduced alert volume** (83.28% overall; 42.09% on IoT-23) but **lowered threat-detection accuracy** compared with fragmented per-source monitoring:
- macro F1: −0.161;
- FPR: +0.098.

The result is consistent across all robustness checks, and under a strict temporal hold-out (Run T: macro F1 0.9992 vs 0.7711).

The diagnostics locate the cause in the **incident representation**, not in correlation itself:
- correctly labelled incidents would lose almost nothing (ceiling F1 0.9989);
- incident context added to event features changes detection only slightly, in mixed directions.

Within this experiment's limits (06), the evidence answers RQ1 this way: correlating distributed IoT logs into incidents can greatly reduce the number of items to review. But replacing event-level detail with coarse incident summaries degrades detection, especially false positives on benign traffic. The detection benefit of integration depends on incident features carrying behavioural content.
