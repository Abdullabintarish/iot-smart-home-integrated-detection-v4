# Technical audit (Phases 1–2, read-only), 2026-11-03

**Scope.** Every finding below was checked against the code or the saved outputs. Nothing was retrained and no existing file was changed.

**Evidence scripts:**

- `experiments/audit/audit_checks.py` → `audit_checks.json`
- `thesis_writing_package/evidence/crosslog_breakdown.py` → `crosslog_breakdown.json`

Paths are relative to `submission/`.

## 0. What was run

| Check | Result |
|---|---|
| Thesis pipeline tests (`code/tests`) | 94 / 94 OK |
| Demo tests (`code/demo/tests`) | OK. The live integrated model reproduces 175,489 / 175,489 saved incident predictions |
| Ablation tests | 6 / 6 OK |
| Cross-log tests | 14 / 14 OK |
| Run B metrics recomputed from `predictions/*.csv` | Macro F1, FPR, FNR and the full confusion matrices equal `metrics/stage5_report.json`, for both conditions |
| Run T metrics recomputed from its prediction CSVs | Equal to its `stage5_report.json` |
| Cross-log macro F1 recomputed from `stage4_predictions.parquet` | 20 / 20 (condition, seed) values equal |

## 1. Confirmed defects and inconsistencies

| ID | Severity | File / function | Evidence | Impact | Proposed correction |
|---|---|---|---|---|---|
| D1 | **High** | `experiments/cross_log/src/experiment.py` → `train_sample` (also used by `robustness.py`) | Samples ≤ 60,000 rows per **binary** target. The thesis pipeline samples per **class** (`code/pipeline/detect.py` → `stratified_sample`, `sample_stream`). Training holds 35 c2 and 5,965 malware rows. Each seed's sample contains only **1–5 c2** and about 500 malware rows out of 120,000 (`audit_checks.json` → `crosslog_train_sample`). The test attacks are 97.7% c2 | Condition A is near the all-benign score in 4 of 5 seeds. The large seed variance (SD ≈ 0.2) is mostly sampling luck. Comparisons A–D are made on an almost unlearnable task | Add `stratify="cls"` (≤ 60,000 per thesis class; all c2 and malware rows kept). Keep `"y"` as the default so the historical run still reproduces. Rerun as a new, versioned experiment |
| D2 | **High** (validity) | `experiment.run` (conditions A–D) | Capture 8-1 has 0 DNS and 0 alerts; all its context columns are 0. Yet its predictions change between conditions. In leave-one-capture-out, C − A ≈ +0.14 only on the folds whose test capture has 0 alerts (`crosslog_breakdown.json`) | Part of the reported B/C/D gain is not information gain. Two likely mechanisms: extra columns change `max_features="sqrt"` candidate sets, and "no context" is associated with attacks in training | Add negative controls with the same column count: (i) A + constant-zero columns; (ii) A + context features permuted within each capture. Report results separately for captures with and without each log type |
| D3 | Medium | `experiments/ablation/run_ablation.py` | Writes only metric tables. There are no predictions, no per-class precision/recall, no confusion matrices and no per-capture metrics | Ablation numbers cannot be recomputed independently, and Phase 3.3 outputs are missing | Save per-event predictions (Parquet) for the 300 s runs; derive all tables from them |

No coding error was found in the Run B or Run T pipelines. All their reported numbers were reproduced from the saved predictions.

## 2. Leakage audit (Phase 2)

### 2.1 Target leakage: none found

| Check | Evidence | Status |
|---|---|---|
| Labels or label statistics as features | `INCIDENT_FEATURES` whitelist (`correlate.py:54`). `label_entropy`, `label_purity`, `label_counts` exist only in `DIAGNOSTIC_COLUMNS`. Tests: `test_no_label_statistic_in_incident_features`, `test_label_statistics_go_to_diagnostics` | OK |
| Identifiers as features | `check_features` (`detect.py:55`), `NON_FEATURES`. Cross-log: `FORBIDDEN` plus `check_no_forbidden` (tested) | OK |
| Raw label and leakage columns | `LEAKAGE_COLUMNS` (`config.py:98`) dropped before fitting. Test: `test_label_source_columns_never_features` | OK |
| Feature selection uses labels | `FEATURE_SELECTION = "redundancy"` (feature–feature correlation only), fitted on train rows | OK |
| Preprocessing fitted before split | `assign_split` runs before cleaning and fitting; `fit` keeps `split == "train"` only. Test: `test_fit_ignores_test_rows` | OK |
| Cross-log preprocessing | `Preprocessor` fitted per seed on the training sample; alert categories from training captures only. Test: `test_preprocessor_fit_on_train_only` | OK |
| Training touches test labels | Fragmented: per-source train reservoirs. Integrated: `train_incidents` excludes test ids. Test: `test_cv_uses_train_split_only_and_groups` | OK |

### 2.2 Train/test independence

| Check | Evidence | Status |
|---|---|---|
| Incidents spanning the split | 0 mixed incidents. Test: `test_no_incident_spans_both_splits` | OK |
| Exact duplicate feature vectors | 13.54% of Run B test events (benign 86.76%) have an exact training duplicate (verification V5) | Known. Reported via the novel-vector subset |
| Capture or conversation overlap | Run B and Run T are within-capture. 23.88% of test events share a conversation with training events (c2 99.94%) | **High, not resolved.** Run B and Run T do not measure generalisation to unseen networks |
| Cross-log | Capture-held-out; incident ids disjoint (`run_stage4.py:57`). 73% of test benign rows have a condition-A vector that also occurs in training (5,412 of 7,376) | OK; repetitiveness reported |

### 2.3 Temporal availability

| Feature | Uses information after the event? | Status |
|---|---|---|
| Run B integrated (`n_events`, `span_s`, `events_per_s`) | **Yes.** Computed over the completed 300 s incident, so a test event's incident includes later events | Offline completed-window correlation only. It must not be described as real-time detection. Not stated explicitly in the docs |
| Enriched diagnostic and ablation `*_plus_incident` | **Yes** (same completed-window context) | Same |
| Cross-log DNS and alert context | No. Window `[ts − w, ts]` (`features._window_bounds`, `side="right"`) | Causal. Records stamped exactly at `ts` are included; no test covers this boundary |

## 3. Methodological weaknesses

| ID | Severity | Issue | Evidence | Proposed resolution |
|---|---|---|---|---|
| M1 | **High** | Main comparison is untested on unseen captures | Run B and Run T are within-capture. On unseen captures, connection features alone (cross-log A) were near-trivial, so the 0.99 event-level F1 is a within-capture figure | Capture-held-out controlled comparison on the Run B data (§4, P2). Fragmented per-source models are undefined for an unseen capture; report that explicitly |
| M2 | **High** | Ephemeral source port (`sport`) is a feature; ports are MinMax-scaled as numbers | `sport` is in the top-4 importances of 7 per-source models (1-1, 8-1, 20-1, 21-1, 34-1, 42-1, 44-1; up to 0.21; `audit_checks.json`). With a within-capture split this can act as a shortcut that favours the event-level baseline | Sensitivity feature set `event_no_sport` in P2 and P4 |
| M3 | Medium | Representation vs model-scope confound | Partly resolved already: fragmented 0.9955 vs pooled 0.9944 vs ablation `event_only` 0.9952 ± 0.0012, so per-source vs global matters little. Not resolved: these were not compared on the same events with per-class P/R and per-capture metrics, and the fragmented models were run with one seed only | P4 (ablation rerun with saved predictions, per-class and per-capture tables) |
| M4 | Medium | Completed-window incident context presented without the offline caveat | §2.3 | Document the caveat. Optionally add a causal context variant in P4 (`n_events_so_far`, `span_so_far` within the window) |
| M5 | Medium | Cross-log lacks simple baselines | No majority-class or all-attack baseline is reported | Add a dummy majority baseline and a stratified-random baseline in P1 |
| M6 | Medium | Bootstrap ignores capture-level dependence | Run B bootstrap resamples incidents; 13 captures are too few for a capture-level bootstrap | Report per-capture results and sign counts from leave-one-capture-out (P1, P2) rather than pooled intervals alone |
| M7 | Low | Class coverage | No botnet, brute-force or theft classes; malware only in 3-1 (5,962) and 42-1 (3); dos only in 34-1, 44-1 (1 row) and Bot-IoT | Report unsupported folds and classes explicitly in P2 |

## 4. Prioritised correction plan (needs approval)

New code goes in `experiments/v2/` (or via opt-in parameters on existing functions). Default behaviour is unchanged, and all historical outputs are preserved.

Each new run writes a manifest containing:

- run id;
- git commit;
- input file SHA-256;
- configuration;
- feature lists;
- seeds;
- split definition;
- model parameters;

plus its predictions, metrics, confusion matrices and log.

| ID | Correction | Addresses | Cost (estimate) |
|---|---|---|---|
| P1 | **Cross-log v2.** Class-stratified sampling; conditions A–D plus two negative controls (zero columns, permuted context) plus majority and stratified baselines; primary split (5 seeds) and leave-one-capture-out (8 folds × 5 seeds); per-capture tables split by context availability. Uses the existing feature cache, so sensors are not rerun | D1, D2, M5, M6 | ~1 h compute |
| P2 | **Capture-held-out controlled comparison on the Run B data.** Pooled RF with `event_only`, `event_no_sport`, `incident_only`, `event_plus_incident` (300 s); leave-one-source-out over the 13 sources (or the IoT-23 captures only); 3–5 seeds; 5-class and binary metrics; unsupported classes per fold reported | M1, M2, M7 | ~1–1.5 h |
| P3 | **Automated tests**: cross-log sampling class coverage; negative-control invariance; `label_match` non-matches (tolerance, CID, duplicates); `local_host` both-private case; causal window boundary at exactly `ts`; manifest completeness; metric recomputation from saved predictions for every new run | Phase 7 gaps | small |
| P4 | **Ablation v2 at 300 s** with saved predictions, per-class P/R, confusion matrices and per-capture metrics, plus `event_no_sport` and an optional causal-context set; 5 seeds; same Run B split | D3, M2, M3, M4 | ~15 min |
| P5 | **Independent verification script** that recomputes every new table from saved predictions | Phase 8 | small |

Not proposed:

- Rerunning Run B or Run T: they are reproduced exactly.
- Hyperparameter tuning: it would not answer RQ1.
- New datasets.

## 5. Preliminary ratings (current state, before any correction)

These scores will be revised after the approved corrections run.

| Category | Score | Main reason |
|---|---|---|
| Python code quality | 82 | Modular, streaming, whitelists, 162 tests. Cross-log sampling diverges from the thesis discipline |
| Dataset processing accuracy | 85 | Label mapping tested; 99.98–100% label transfer. 34-1 DDoS coverage mismatch is documented |
| Event correlation correctness | 85 | Deterministic, chunk-independent, boundary tests. Within-source only by design |
| Data leakage prevention | 80 | No target or preprocessing leakage found. Within-capture overlap and `sport` shortcut risk remain |
| Experimental fairness | 68 | Same events, same RF, same metrics. Unit and training-set differences; no capture-held-out version of the main comparison |
| ML methodology | 70 | Sound for a fixed split. One seed in Run B; generalisation untested for the main comparison |
| Cross-log correlation validity | 45 | Linking is sound, but the detection comparison is confounded (D1, D2) |
| Statistical robustness | 62 | Bootstraps and seeds exist; capture-level dependence not handled |
| Reproducibility | 88 | Byte-identical rerun; hashes; recomputation matches. Ablation predictions not saved |
| **Overall scientific reliability** | **70** | The primary negative result is solid within its scope; generalisation and cross-log claims are not yet defensible |

## 6. Final ratings after corrections P1–P5

Every correction ran and was verified independently (`v2/results/verification.json`, `all_ok`). The results are in `experiments/v2/RESULTS_V2.md`.

The ratings below score how reliable the study's evidence is now. They do not measure how favourable its results are.

| Category | Before | After | Reason for the change |
|---|---|---|---|
| Python code quality | 82 | 85 | Cross-log sampling matches the thesis discipline in v2; run manifests; 15 new tests |
| Dataset processing accuracy | 85 | 85 | Unchanged. Label-match edge cases are now tested |
| Event correlation correctness | 85 | 87 | Causal variant implemented and tested |
| Data leakage prevention | 80 | 86 | `sport` shortcut quantified (within-capture effect −0.0015; it hurts transfer). The look-ahead effect on FPR has been ruled out |
| Experimental fairness | 68 | 78 | Same-model comparison on unseen sources. Fragmented per-source models remain undefined there |
| ML methodology | 70 | 78 | Leave-one-source-out and leave-one-capture-out designs; 3–5 seeds; per-class and per-source results saved |
| Cross-log correlation validity | 45 | 68 | D1 fixed, D2 tested with controls and baselines. The result is narrow, and only 35 C&C training rows exist |
| Statistical robustness | 62 | 72 | Fold-level sign counts and seed spread reported. Few captures limit inference |
| Reproducibility | 88 | 93 | Every v2 number recomputes from saved predictions; hashes match; the historical ablation is reproduced exactly |
| **Overall scientific reliability** | **70** | **79** | The conclusions are now stated within their tested scope |

**Remaining limits that no correction can remove:**

- 13 sources and only 35 C&C training rows for cross-log.
- No botnet, brute-force or theft classes.
- One sensor vantage point.
- Offline evaluation only.
- Ratings cannot exceed about 80 without new data.

## 7. Ratings after v3 (steps 2–6, 2026-11-04)

All v3 runs were verified: `v3/results/verification.json`, `all_ok`. The results are in `v3/RESULTS_V3.md` and the log in `RUN_LOG.md` §12.

As in §6, the ratings score how reliable the evidence is, not how favourable it is. Several v3 results are unfavourable or null, and they are scored as evidence like any other.

| Category | v2 | v3 | Reason for the change |
|---|---|---|---|
| Python code quality | 85 | 86 | Lean reader checked against the original on 26 logs; generated tables; 12 v3 tests |
| Dataset processing accuracy | 85 | 86 | Two more captures with 1.0 label match; cache rebuild identical for the 9 old captures |
| Event correlation correctness | 87 | 87 | Unchanged |
| Data leakage prevention | 86 | 87 | The `loso` baseline uses no held-out labels, which a test asserts |
| Experimental fairness | 78 | 85 | The fragmented baseline is now defined on unseen sources by a pre-registered rule; the same samples are used across three model families |
| ML methodology | 78 | 84 | RF, HGB and LR; 5 seeds in both designs; stronger, class-imbalance-aware metrics |
| Cross-log correlation validity | 68 | 70 | C&C training rows rise from 35 to 21,501 and the leave-one-capture-out set from 8 to 9 folds. The new captures are single-family and alert-poor, so they add little evidence about context |
| Statistical robustness | 72 | 80 | Pre-registered exact paired tests with Holm correction, Wilcoxon and an incident-clustered bootstrap. n = 13 sources and n = 5 seeds still limit power |
| Reproducibility | 93 | 94 | 9,615 v3 values recompute exactly; manifests, hashes and an integrity check over 30,615 files |
| **Overall scientific reliability** | **79** | **83** | Every claim now has a fair comparison and a stated test. Most generalisation claims are directional only, and this is stated rather than overstated |

**What v3 changes in the conclusions:**

- **"Unified beats fragmented" on unseen sources** is supported in direction (macro F1 0.372 against 0.296) but not after Holm correction.
- **The FPR increase from incident context is specific to RF.** HGB and LR show the opposite direction.
- **The C&C data shortage was not why 8-1 scored poorly.**

**Remaining limits:**

- Only 13 sources and 9 cross-log folds that pass the gate.
- The new captures are dominated by Okiru.
- One sensor vantage point; offline evaluation only.
- No tuning study, by design.
