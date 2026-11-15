# Research Question Evidence Mapping

> **RQ1** (Thesis Part 1 §1.3): How does the integration and correlation of distributed IoT logs and alerts affect cybersecurity threat detection accuracy in IoT-enabled smart home networks?

This document links each part of the answer to RQ1 to the experiment and file that support it. It also states how strong each piece of evidence is. Paths are relative to `submission/`.

## 1. Answer components

| # | Claim | Experiment | Key numbers | Evidence file(s) | Strength |
|---|---|---|---|---|---|
| C1 | Detecting threats from incident summaries is **less accurate** than per-source event-level detection | Run B (primary) | Macro F1 0.8341 vs 0.9955; FPR 0.1021 vs 0.0046; difference interval [−0.2055, −0.1280] | `metrics/stage5_report.json`; `metrics/baseline_vs_integrated.csv` | **Strong**: fair comparison; reproduced byte-identically (Run C); consistent in all robustness checks |
| C2 | C1 does not depend on interleaving train and test in time | Run T | Macro F1 0.7711 vs 0.9992; FPR 0.0965 vs 0.0044 | `../thesis_final_validation/supplementary_temporal/RESULTS.md`; `.../code/results/stage5_report.json` | **Strong** for direction; accuracy affected by a cut artefact |
| C3 | The loss comes from the incident **representation**, not from correlation | Run B diagnostics | Propagation ceiling F1 0.9989; 4 of 7 incident features constant; all false positives come from multi-event benign incidents | `docs/thesis_final_validation/04_Verified_Results_and_Analysis.md` §5; `../thesis_final_validation/verification/verification_results.json` (V3, V4, V12) | **Strong** (direct measurement) |
| C4 | Replacing event features with incident features causes the loss, with everything else fixed | Ablation | `incident_only` − `event_only`: F1 [−0.176, −0.107], FPR [+0.084, +0.091] | `experiments/ablation/results/full/bootstrap.json`, `thesis_table.md` | **Strong**: controlled design; 5 seeds; 5 windows |
| C5 | Adding incident context to event features does **not** improve accuracy and increases false positives | Ablation; enriched diagnostic | F1 difference [−0.0014, +0.0048]; FPR 0.38% → 1.14%; enriched diagnostic FPR 0.0039 → 0.0116 | `experiments/ablation/results/full/`; `metrics/stage5_report.json` → `diagnostics` | **Strong** for FPR; null for F1 |
| C6 | Correlation substantially **reduces alert volume** | Run B | 83.28% overall; 42.09% IoT-23; 99.91% Bot-IoT | `metrics/stage5_report.json` → `alert_reduction` | **Strong** as a count. Its effect on response or risk was not measured |
| C7 | Different log types (connection, DNS, IDS alerts) from IoT traffic can be linked reliably | Cross-log Stage 3 | Match rates 0.9998–1.0000; 571 of 2,344 incidents with ≥ 2 log types | `experiments/cross_log/results/stage3_*.json` | **Strong** (feasibility) |
| C8 | Adding other-log-type context **can** improve detection on unseen networks, most clearly with DNS | Cross-log Stage 4, R1–R5 | Mean macro F1 A 0.335 → D 0.586; B > A in 20/20 seeds; 34-1 C&C detection 0.001 → 0.30 with DNS | `experiments/cross_log/results/stage4_results.json`; `robustness/` | **Weak to moderate**: see C9 |
| C9 | Part of the cross-log gain is **not** attributable to log content; effects are inconsistent across networks | Read-only re-tabulation of the cross-log predictions | Baseline A ≈ all-benign (0.2454) in 4/5 seeds; 8-1 has no DNS or alerts but gains; alert gains appear only on folds with 0 alerts; D − A negative on 2 of 8 folds | `thesis_writing_package/evidence/crosslog_breakdown.json`; `R3_leave_one_capture_out.json` | **Strong** (direct reading of saved predictions) |
| C10 | The framework is implementable and reproducible | Runs B, C; tests | 94 + 48 + 6 + 14 tests pass; byte-identical predictions on two machines; integrity diff empty | `code/tests/`; `predictions/`; `experiments/_integrity/` | **Strong** |

## 2. Synthesised answer

Integration and correlation affected threat detection accuracy in three ways, depending on what was integrated.

1. **Summarising events of the same log type into incidents reduced accuracy** (C1–C4). The false-positive rate was about 22 times higher.
2. **Adding the same-log-type summary to event features left accuracy unchanged and increased false positives** (C5).
3. **Adding information from different log types showed potential to improve accuracy on unseen networks** (C7–C8). The evidence for this is limited and partly confounded (C9).

Separately, correlation reliably reduced the volume of items to review (C6). This is a benefit for alert management, not for detection accuracy.

## 3. Mapping to Part 1 objectives and expected contributions

| Part 1 item | Supported by | Outcome |
|---|---|---|
| Objective 1: analyse distributed logs and alerts | Ch. 3 §3.3; C7 | Achieved |
| Objective 2: baseline fragmented model | Ch. 3 §3.6; C1 | Achieved |
| Objective 3: unified framework design | Ch. 3 §3.2–3.5 | Achieved |
| Objective 4: implement and evaluate | C10 | Achieved |
| Objective 5: compare with defined metrics | C1–C6 | Achieved |
| Expected contribution: improved visibility | C6, C7 | Partly: workload reduction and cross-log linking were shown; visibility itself was not measured |
| Expected contribution: enhanced detection accuracy | C1, C4, C5, C8, C9 | **Not confirmed** for incident summaries; potential shown for cross-log context |
| Expected contribution: fewer false-positive alerts | C1, C5, C6 | Alert *volume* fell; the false-positive *rate* rose |
| Expected contribution: support for risk mitigation | C6, Ch. 5 §5.12 | Indirect and conditional; not measured |

## 4. Statements the thesis must not make

The evidence does not support the following statements:

- That the integrated incident-level model outperformed the fragmented baseline. It did not, on any metric (C1).
- That integration lowered the false-positive rate. It increased it (C1, C5).
- That cross-log correlation reliably improves detection. The effect is inconsistent and partly confounded (C9).
- That IDS-alert context improves detection. There is no reliable evidence (C9).
- That the framework reduces real-world risk, response time or analyst workload. None of these was measured.
- That the results generalise to live smart homes, or to botnet, brute-force or theft classes. These were not tested.
- That the framework works in real time or across independent sensors. It does not.
