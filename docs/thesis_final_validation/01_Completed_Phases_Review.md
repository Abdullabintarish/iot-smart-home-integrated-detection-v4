# 01 — Completed Phases Review

**Thesis:** Integrated Information Management for Cybersecurity Risk Mitigation in IoT-Enabled Smart Home Networks
**RQ1 (unchanged):** How does the integration and correlation of distributed IoT logs and alerts affect cybersecurity threat detection accuracy in IoT-enabled smart home networks?

Prepared 2026-11-02 for the final validation phase. Nothing in the existing project was modified; this folder is new. All paths are relative to `Thesis_Part1_Reoprt/`.

## 1. Evidence sources and abbreviations

| Abbrev. | File | What it is |
|---|---|---|
| **R** | `submission/metrics/stage5_report.json` | Full results of the verified run (Run B) |
| **M** | `submission/metrics/run_manifest.json` | Host, Python, package versions, SHA-256 of code and data, configuration |
| **FP** | `submission/metrics/stage2_feature_plan.csv` | Per-feature keep/drop decision |
| **AS** | `submission/metrics/stage3_alert_stats.csv` | Correlation statistics per chunk |
| **VR** | `thesis_final_validation/verification/verification_results.json` | Re-derivations and new checks from this phase (sections V1–V12) |
| **VS** | `thesis_final_validation/verification/verify_evidence.py` | The read-only script that produced VR |
| **TS** | `thesis_final_validation/verification/temporal_split_feasibility.csv` | Feasibility check for a temporal split |
| **PTC** | `thesis_review/PROPOSED_THESIS_CHANGES.md` | Earlier review of thesis text against implementation (2026-10-16) |

## 2. Experimental runs and their status

Every result belongs to exactly one run. Only Run B is cited; Run C confirms it.

| Run | Date (UTC) | Location | Status | Use |
|---|---|---|---|---|
| A | 2026-10-06 | `submission/archive/original_run_2026-10-06/` | **Invalid** (8 confirmed defects, see `ARCHIVE_NOTE.txt`) | Traceability only; do not cite |
| Phase runs | 2026-10 | `backups/code_before_phase1…4`, `backups/results_before_phase5` | Superseded intermediate states | Traceability only |
| **B** | **2026-10-16 08:48–08:53** | `submission/metrics/`, `submission/predictions/`, `submission/report/`, `submission/transcripts/` | **Verified — the reported run** | Cite these numbers |
| C | 2026-10-21 16:28–16:35 | `submission/code/results/`, `submission/code/models/`, `submission/code/data/processed/` | Regeneration on a different machine (AMD Ryzen 7 7800X3D vs Intel i7-14700KF in B) | Reproducibility evidence; artifacts used for the new checks |
| V | 2026-11-02 | `thesis_final_validation/verification/` | New read-only checks on Run C artifacts (no retraining) | New evidence in this phase |
| T | 2026-11-01 21:09 UTC | `thesis_final_validation/supplementary_temporal/` | Supplementary temporal hold-out (approved Proposal A), run in a code copy; Run B untouched | Robustness check only; see its `RESULTS.md` |

**Run B and Run C agree (newly verified, 2026-11-02).**
- All three prediction CSVs, `baseline_vs_integrated.csv` and `stage3_alert_stats.csv` are byte-identical.
- In `stage5_report.json`, 39 leaves differ and all 39 are timing values.
- In the feature plan, the keep/drop decisions are identical. The numeric statistics differ by at most 2.9e-14 relative, which is floating-point summation order.
- The pipeline modules (`pipeline/*.py` except `reporting.py`) and all 13 dataset hashes are identical in the two manifests (M vs `submission/code/results/run_manifest.json`).
- `reporting.py`, `check_sources.py`, `requirements.txt` and `run_all.sh` have different hashes. These files do not affect any metric, because the reports are identical apart from timing.

Because C's predictions are identical to B's, the checks in VR (computed on C's artifacts) apply to Run B.

## 3. Phase history (what was done, with evidence)

| Phase | Work | Evidence |
|---|---|---|
| Original build | Five-stage pipeline (collect → preprocess → correlate → detect → evaluate) on IoT-23 + Bot-IoT | `backups/code_before_phase1/` |
| Review of original | 8 defects confirmed: label_entropy leakage; Bot-IoT category/subcategory leakage; wrong FPR formula; timestamp as feature; conditions scored on different test sets; ungrouped random splits; per-chunk normalisation fitted on all rows; label-code-correlation feature selection | `submission/archive/original_run_2026-10-06/ARCHIVE_NOTE.txt` |
| Phase 1–2 | Leakage columns excluded; train-only fitting; global MinMax; redundancy-based feature selection | `backups/code_before_phase2/`, `submission/code/pipeline/preprocess.py`, `pipeline/config.py:98` (`LEAKAGE_COLUMNS`) |
| Phase 3 | Correlation rewritten: chunk-independent incident ids, incident split shared with Stage 2 | `backups/code_before_phase3/`, `pipeline/correlate.py` |
| Phase 4 | label_entropy removed from model inputs (it was still an input before Phase 4: `backups/code_before_phase4/models/rf_integrated_features.csv` lists it); label statistics moved to a diagnostics-only table | `pipeline/correlate.py:52-64` |
| Phase 5 | One held-out test set for both conditions; robustness checks; clustered bootstrap; diagnostics (pooled, enriched, duplicates); tests | `pipeline/detect.py`, `pipeline/evaluate.py`, `submission/code/tests/` |
| Verified run | Run B; clean-environment regeneration byte-identical | `submission/README.txt` §11, `submission/REPRODUCIBILITY_CHECKLIST.md` |
| Thesis-text review | Proposed wording changes; numbers ledger | PTC, `thesis_review/NUMBERS_LEDGER.csv` |
| Demonstration | Read-only Streamlit app; live re-prediction check | `submission/code/demo/`, `README_DEMO.md` |
| Run C | Regeneration on a second machine (Python 3.15.0 reinstalled at the original path, same `.venv`) | `submission/code/results/transcripts/run_all.log` |

## 4. Component status — verified, not assumed

"Verified" means re-checked in this phase against code or artifacts, not taken from an earlier claim.

| Component | Status | Verification in this phase |
|---|---|---|
| IoT-23 ingestion (10 Zeek `conn.log.labeled`) | Complete | Raw files present (`submission/code/data/raw_combined/`); dataset hashes identical in B and C manifests |
| Bot-IoT ingestion (3 Kaggle CSVs) | Complete | As above |
| Stage 2 preprocessing (train-only fit) | Complete | Code read: `preprocess.fit` filters `split == "train"` before every statistic (`preprocess.py:219`, `:272`) |
| Stage 3 correlation | Complete, **within-capture only** | VR V8: all 4,211,383 events grouped by rule R1; VR V9: 0 cross-source incidents |
| Fragmented RF baseline | Complete | VR V1: metrics and confusion matrix recomputed exactly |
| Integrated RF | Complete | VR V3: saved model re-predicts all 175,489 test incidents; event predictions reproduced exactly |
| Event + incident-context RF ("enriched") | Complete (as a diagnostic) | VR V1: metrics recomputed exactly |
| Same held-out events for all models | Complete | VR V2: identical event ids, order and labels in all prediction files |
| Robustness checks, bootstrap | Complete | R `robustness`, `bootstrap` (not recomputed; inputs verified) |
| Unit tests | Pass | 94/94 pipeline tests and 48/48 demo tests, re-run 2026-11-02 |
| Demonstration app | Working | Live inference: 175,489/175,489 incidents agree (demo test run, 2026-11-02) |
| Capture-level split | **Not done** (incompatible with the per-source baseline) | See 02 (B3) and 06 |
| Temporal split | **Done as supplementary Run T** | `supplementary_temporal/RESULTS.md` |
| Cross-source correlation | **Not demonstrated** | See 02 (Step 4) and 05 |

## 5. Discrepancies found in existing documentation

These are minor. None changes a result.

1. `ARCHIVE_NOTE.txt` points to backups under `C:\Users\user\Desktop\final_thesis_2\...`. The project now lives under `C:\Users\user\Desktop\Thesis_Part2_Report\...`, and the backups are at `Thesis_Part1_Reoprt/backups/`.
2. The submission bundle (`submission/metrics`) holds Run B. `submission/code/results` now holds Run C. Their timing values differ: baseline training 7.2547 s (B) vs 7.8037 s (C), and total runtime 338.3 s (B) vs 374.6 s (C). Cite timings only from Run B, with the hardware named.
3. The README describes 4 integrated features as having "zero importance". This phase shows the stronger fact: those 4 features are **constant by construction**, always 1 (VR V4 `incident_feature_ranges_train`). Rule R1 fixes one source and one destination IP per key, and source scoping fixes one capture per key.
