# Academic Limitations

This document lists the limitations of the study with their severity and evidence. Paths are relative to `submission/`.

**Severity:**

- **High:** limits what the answer to RQ1 can claim.
- **Medium:** must be stated next to the affected results.
- **Low:** a reporting detail.

L1–L14 are the limitations already recorded for the primary experiment (`docs/thesis_final_validation/06_Research_Gaps_and_Limitations.md`). L15–L23 are added for the supplementary experiments.

## 1. Primary experiment (Run B) and Run T

| # | Limitation | Severity | Evidence |
|---|---|---|---|
| L1 | **No cross-source correlation.** Correlation is within each capture: 0 cross-source incidents, even with the source removed from the key. The captures are independent recordings | High | `metrics/stage5_report.json` → `alert_reduction.cross_source_incidents`; verification V9 |
| L2 | **Within-capture evaluation.** Train and test are interleaved in time within captures. 23.88% of test events share a conversation with training events, and 13.54% have an exact training duplicate. Run T confirms the direction, but is still within-capture | High | Verification V5; Run T |
| L3 | **Coarse incident representation.** 4 of 7 incident features are constant by construction. The single-event vector is shared by 320,638 benign and 15,923 recon training incidents | High (explains the main result) | Verification V4, V12 |
| L4 | **Large incidents dominate event-level metrics.** 7 incidents hold 78.55% of test events | Medium | Verification V7 |
| L5 | **The bootstrap treats incidents as independent.** Intervals are likely too narrow, and a capture-level bootstrap would have only 13 clusters | Medium | `metrics/stage5_report.json` → `bootstrap.note` |
| L6 | **Dataset fingerprint in missing values.** Argus-only features are always missing for IoT-23 rows. This affects the pooled and enriched diagnostics; the ablation's `shared_*` sets control for it | Medium | Verification V4; `experiments/ablation/results/full/` |
| L7 | **Small classes.** Integrated training had dos 26, malware 238 and c2 561 incidents. Malware occurs in 2 captures | Medium | `metrics/stage5_report.json` |
| L8 | **Class set narrower than the thesis scope.** There are no botnet, brute-force or theft classes, and DoS and DDoS are merged | Medium | `code/pipeline/ingest.py` |
| L9 | **Research data, not live smart homes.** The data are honeypot, laboratory and testbed captures. Bot-IoT is 99.9% attack traffic | Medium | `docs/thesis_final_validation/03_Final_Experimental_Methodology.md` §2 |
| L10 | **One configuration and one seed** in Run B and Run T; no hyperparameter search | Medium | `metrics/stage5_report.json` → `model_config` |
| L11 | **Unequal training sets and units** (408,412 events vs 120,825 incidents) | Low | `metrics/stage5_report.json` |
| L12 | **Single log type per source in Run B.** "Alert" means a flow record, not an IDS alert | Medium | `docs/thesis_final_validation/03_Final_Experimental_Methodology.md` §2 |
| L13 | **Offline batch processing.** There is no SIEM, streaming or storage-layer component | Low (for RQ1) | `code/` |
| L14 | **Outcomes stop at detection and alert counts.** Response time, analyst effort and risk were not measured | High (for the title's "risk mitigation") | `docs/thesis_final_validation/05_Cybersecurity_Risk_Mitigation_Contribution.md` §4 |

## 2. Run T specific

| # | Limitation | Severity | Evidence |
|---|---|---|---|
| L15 | **Cut artefact.** The 75th-percentile cut truncates short Bot-IoT flood conversations. As a result, 282,900 DoS test events were predicted recon, which lowers accuracy | Medium | `../thesis_final_validation/supplementary_temporal/RESULTS.md` §4 |

## 3. Controlled ablation

| # | Limitation | Severity | Evidence |
|---|---|---|---|
| L16 | **One train/test split** (the Run B split). Seeds vary only the sample and the model | Medium | `experiments/ablation/run_ablation.py` |
| L17 | **Windows of 600 and 900 s are cut at the partition boundary**, so their incident features are incomplete | Low | `experiments/ablation/results/full/thesis_table.md` (column "Cut") |
| L18 | **Pooled model only.** The ablation uses one pooled Random Forest, not per-source models, so its `event_only` row is not identical to the Run B baseline | Low | `experiments/ablation/run_ablation.py` |

## 4. Cross-log correlation experiment

| # | Limitation | Severity | Evidence |
|---|---|---|---|
| L19 | **Same-capture log types.** Connection, DNS and alert records all come from one packet capture and one vantage point. This is cross-log-type correlation, not correlation between independent device, gateway and cloud sensors | High | `experiments/PLAN.md` §3 |
| L20 | **Near-absent C&C training data and a near-trivial baseline.** Training has 35 C&C rows, while 97.7% of test attacks are C&C. Condition A equals the all-benign score (0.2454) in 4 of 5 seeds. Seed variance is very high (SD ≈ 0.2) | High | `experiments/cross_log/results/stage4_results.json`; `thesis_writing_package/evidence/crosslog_breakdown.json` |
| L21 | **Absence-of-context confound.** Test capture 8-1 has no DNS and no alerts, yet its detection changes with the condition. In leave-one-capture-out, alert features "help" only on folds whose test capture has 0 alerts. Part of the measured gain is therefore not due to the content of the correlated logs. No placebo condition was included in the design | High | `crosslog_breakdown.json` (`8-1_nonzero_context_values`, `r3_folds`) |
| L22 | **Few networks, one infected device each.** There are 7 captures in the primary design and 8 in leave-one-capture-out. Capture 49-1 was excluded by the pre-set 90% match gate (0.8984). The results vary strongly by network, and D − A is negative on 42-1 and 48-1 | Medium | `experiments/cross_log/results/stage3_*.json`; `R3_leave_one_capture_out.json` |
| L23 | **Data and tool mismatches:** | Medium | `experiments/RUN_LOG.md` §4.2, §4.5–4.6, §5.1 |
| | (a) in 34-1, only 237 of 14,394 DDoS rows are covered, because IoT-23 logs one flood flow per packet; | | |
| | (b) a 2026 ruleset was applied to 2018–2019 traffic; | | |
| | (c) the target is binary only; | | |
| | (d) a timestamp defect affected the first run. It was corrected, all analyses were rerun, and the superseded outputs are archived | | |

## 5. Threats to validity (summary for the thesis)

| Type | Main threats | Mitigations used |
|---|---|---|
| **Internal validity** | Leakage between train and test; confounding of features with capture identity; absence-of-context effects (L21) | Grouped split; train-only fitting; leakage guard in code; capture-held-out cross-log design; designs fixed before training; ablation holds everything constant except features |
| **External validity** | Research datasets (L9); one vantage point (L19); few networks (L22); narrow classes (L8) | Two datasets; temporal and capture-held-out evaluations. External validity remains the main open issue |
| **Construct validity** | "Alert" means a flow record in Run B (L12); "risk mitigation" was not measured (L14) | Cross-log experiment adds real IDS alerts; the risk claims are restricted to indirect, conditional statements |
| **Statistical conclusion validity** | One seed in Run B (L10); dependent incidents in the bootstrap (L5); high seed variance in cross-log (L20) | Multiple seeds in the ablation and cross-log experiments; 20-seed Wilcoxon test; two-level bootstrap; leave-one-capture-out |
| **Reliability** | Software defects; environment drift | 162 unit tests in total; byte-identical rerun on second hardware; pinned versions; hashed data and ruleset; integrity check of 30,615 files |
