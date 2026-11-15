# Thesis Figures and Tables Index

This index lists every figure and table used in Chapters 3–6, with the repository file that supports it.

- Paths are relative to `submission/`.
- `../thesis_final_validation/` is the sibling folder, outside the Git repository.

**Status codes:**

- **P**: primary experiment (Run B).
- **V**: validation (Run C, verification).
- **S**: supplementary analysis.
- **D**: derived read-only from saved outputs for this package.

## Figures

| No. | Title | File | Source data | Status |
|---|---|---|---|---|
| 4.1 | Research Overview page of the demonstration app | `code/demo/screenshots/` (choose one) | `results/stage5_report.json` | P |
| — | Stage 1 collection transcript (optional, appendix) | `report/fig_terminal_stage1.png` | `transcripts/stage1_run.log` | P |
| — | Stages 2–5 transcript (optional, appendix) | `report/fig_terminal_run.png` | `transcripts/run_pipeline_run.log` | P |
| 5.1 | Detection metrics, fragmented vs integrated | `report/fig_metrics_comparison.png` | `metrics/stage5_report.json` | P |
| 5.2 | Per-class F1 | `report/fig_per_class_f1.png` | `metrics/stage5_report.json` | P |
| 5.3 | Confusion matrix, fragmented baseline | `report/fig_confusion_fragmented.png` | `metrics/stage5_report.json` | P |
| 5.4 | Confusion matrix, integrated | `report/fig_confusion_integrated.png` | `metrics/stage5_report.json` | P |
| 5.5 | Alert reduction, overall | `report/fig_alert_reduction.png` | `metrics/stage5_report.json` → `alert_reduction` | P |
| 5.6 | Alert reduction by dataset | `report/fig_alert_reduction_by_dataset.png` | `metrics/stage5_report.json` | P |
| 5.x | Integrated feature importance (optional, supports §5.3) | `report/fig_importance_integrated.png` | `metrics/stage5_report.json` | P |
| 5.7 | Ablation: macro F1 and FPR by feature set and window | `experiments/thesis_report/fig_2_ablation.png` | `experiments/ablation/results/full/ablation_summary.csv` | S |
| 5.8 | Cross-log macro F1 per seed and condition | `experiments/thesis_report/fig_3_crosslog_seeds.png` | `experiments/cross_log/results/stage4_results.json` | S |
| 5.y | Run B vs Run T (optional) | `experiments/thesis_report/fig_1_runB_runT.png` | `metrics/stage5_report.json`; `../thesis_final_validation/supplementary_temporal/code/results/stage5_report.json` | S |

Captions and value checks for the nine `report/` figures are in `report/FIGURES.md`.

## Tables

| No. | Title | Chapter | Source file(s) | Status |
|---|---|---|---|---|
| 3.1 | Part 1 framework stages and their implementation | 3 | `code/`; `docs/thesis_final_validation/03_Final_Experimental_Methodology.md` §3 | P |
| 3.2 | Sources, events and classes | 3 | `docs/thesis_final_validation/03_Final_Experimental_Methodology.md` §2; `metrics/run_manifest.json` | P |
| 3.3 | Split sizes | 3 | `metrics/stage5_report.json` → `split` | P |
| (§3.5) | Correlation rules | 3 | `code/pipeline/correlate.py` | P |
| (§3.7.1) | Random Forest configuration | 3 | `code/pipeline/detect.py`; `metrics/stage5_report.json` → `model_config` | P |
| (§3.10) | Validation and reproducibility procedures | 3 | `REPRODUCIBILITY_CHECKLIST.md`; `experiments/_integrity/` | V |
| (§3.12) | Deviations from Part 1 | 3 | Thesis Part 1 §3; this package | — |
| 4.1 | Software used | 4 | `code/requirements.txt`; `experiments/RUN_LOG.md` §0, §4 | P/S |
| 4.2 | Pipeline modules | 4 | `code/` | P |
| 4.3 | Application pages | 4 | `experiments/lab/app.py`; `code/demo/README_DEMO.md` | — |
| 4.4 | Run T code changes | 4 | `../thesis_final_validation/supplementary_temporal/RESULTS.md` §1 | S |
| 4.5 | Cross-log components | 4 | `experiments/cross_log/` | S |
| (§4.10) | Test and integrity summary | 4 | `experiments/RUN_LOG.md` §8–9 | V |
| 5.1 | Headline comparison | 5 | `metrics/stage5_report.json`; `metrics/baseline_vs_integrated.csv` | P |
| 5.2 | Per-class F1 | 5 | `metrics/stage5_report.json` | P |
| 5.3 | Confusion matrix, fragmented | 5 | `metrics/stage5_report.json` | P |
| 5.4 | Confusion matrix, integrated | 5 | `metrics/stage5_report.json` | P |
| 5.5 | Model comparison including diagnostics | 5 | `metrics/stage5_report.json`; `../thesis_final_validation/verification/verification_results.json` | P/V |
| 5.6 | Robustness checks, Run B | 5 | `metrics/stage5_report.json` → `robustness`, `diagnostics.duplicates.novel_only_metrics` | P |
| 5.7 | Alert reduction | 5 | `metrics/stage5_report.json` → `alert_reduction`, `alert_reduction_by_dataset`; `metrics/stage3_alert_stats.csv` | P |
| 5.8 | Run T vs Run B | 5 | `../thesis_final_validation/supplementary_temporal/RESULTS.md` | S |
| 5.9 | Ablation results | 5 | `experiments/ablation/results/full/thesis_table.md` | S |
| 5.10 | Ablation paired bootstrap | 5 | `experiments/ablation/results/full/bootstrap.json` | S |
| 5.11 | Ablation FPR on multi-event benign incidents | 5 | `experiments/ablation/results/full/ablation_summary.csv` (subset `multi_event_benign`) | S |
| 5.12 | Cross-log Stage 3 per capture | 5 | `experiments/cross_log/results/stage3_*.json` | S |
| 5.13 | Cross-log primary result | 5 | `experiments/cross_log/results/stage4_results.json` | S |
| 5.14 | Cross-log robustness | 5 | `experiments/cross_log/results/robustness/R0–R5` | S |
| 5.15 | Cross-log macro F1 with and without 8-1 | 5 | `thesis_writing_package/evidence/crosslog_breakdown.json` | D |
| 5.16 | Leave-one-capture-out per fold | 5 | `experiments/cross_log/results/robustness/R3_leave_one_capture_out.json`; `crosslog_breakdown.json` | S/D |
| 6.1 | Objectives achieved | 6 | Chapters 3–5 | — |

## Tables not to reuse without a caveat

| Item | Caveat |
|---|---|
| Any table in `experiments/cross_log/results/superseded_2026-11-03_alert_timestamp_bug/` | Superseded by a corrected rerun. Do not cite |
| Cross-log interpretation in `experiments/THESIS_ADDITIONS.md` and `experiments/thesis_report/Thesis_Experiments_Report.*` | The numbers are correct, but the interpretation is more favourable than §5.8.4 supports |
| Accuracy figures for Run T | Affected by the cut artefact in Bot-IoT DoS (Ch. 5 §5.6) |
| Overall alert reduction (83.28%) on its own | Always report it next to the IoT-23 figure (42.09%) |
