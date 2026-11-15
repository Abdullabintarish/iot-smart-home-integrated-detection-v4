# Corrections after the technical audit (v2), 2026-11-03

This file reports the corrections P1–P5 proposed in `experiments/audit/TECHNICAL_AUDIT.md` §4.

**What was and was not changed:**

- Every result in this file comes from new, versioned runs under `experiments/v2/`.
- No earlier file was changed or rerun. Run B, Run C and Run T, `experiments/ablation` and `experiments/cross_log` are untouched.
- Every value can be recomputed from the saved predictions with `verify_v2.py` (§5).

**Scope and conventions:**

- All runs use the Random Forest settings of the thesis: 300 trees, depth 24, `min_samples_leaf` 2, `balanced_subsample`, at most 60,000 training rows per class.
- Ablation macro F1 follows the thesis definition: the five classes, macro-averaged over the union of true and predicted labels.
- Cross-log macro F1 is binary.

| Item | Files |
|---|---|
| P1 Cross-log v2 | `cross_log_v2.py`; `results/cross_log/{primary,loco}.json`, `*_predictions.parquet`, `manifest_*.json`, `run.log` |
| P2 + P4 Ablation v2 | `ablation_v2.py`; `results/ablation/{runB,loso}_metrics.json`, `*_predictions.parquet`, `manifest_*.json`, `run.log` |
| P3 Tests | `tests/test_v2.py` (15 tests) |
| P5 Verification | `verify_v2.py` → `results/verification.json` |

## 1. P1: Cross-log with class-stratified sampling and controls

**Fix for D1.** Training samples are now drawn per thesis class, as in `code/pipeline/detect.py`. All 35 C&C rows and all 5,965 malware rows in the training captures are kept in every seed; previously each seed kept 1–5 C&C rows. Only 35 C&C rows exist in the four training captures, so this is a limitation of the data that sampling cannot fix.

**Conditions:**

| Condition | Inputs |
|---|---|
| A | Connection features |
| B | A + DNS context |
| C | A + alert context |
| D | A + DNS + alert context |
| Z (control) | A + the 17 context columns set to zero |
| P (control) | A + the context columns shuffled within each capture. Each capture keeps its context distribution, but the link between context and connection is broken |
| MAJ (baseline) | Always predicts benign |
| STR (baseline) | Predicts malicious at random, at the training share |

### 1.1 Primary pre-registered split (5 seeds)

| Condition | Macro F1 mean ± SD | FPR | FNR |
|---|---|---|---|
| A | 0.444 ± 0.136 | 0.005 | 0.782 |
| B | 0.593 ± 0.176 | 0.005 | 0.585 |
| C | 0.460 ± 0.131 | 0.004 | 0.765 |
| D | 0.565 ± 0.111 | 0.008 | 0.632 |
| Z | 0.444 ± 0.136 | 0.005 | 0.782 |
| P | 0.448 ± 0.145 | 0.004 | 0.777 |
| MAJ | 0.245 | 0 | 1 |
| STR | 0.487 ± 0.003 | 0.525 | 0.478 |

| Difference | Mean | Seeds positive / negative |
|---|---|---|
| B − A | +0.149 | 4 / 1 |
| B − P | +0.145 | 4 / 1 |
| C − A | +0.016 | 5 / 0 |
| C − P | +0.012 | 4 / 1 |
| D − A | +0.121 | 5 / 0 |
| D − P | +0.117 | 5 / 0 |
| Z − A | +0.0001 | — |

**Interpretation:**

- The column-count confound suspected in D2 does not exist: Z ≈ A.
- On this split, the DNS gain is tied to individual connections. The permuted control P gains almost nothing, so the gain is not a capture-level artefact.
- Alert context adds little.
- Condition A scores below the stratified random baseline on macro F1. It reaches its low FPR by missing 78% of attacks.

Per-capture attack detection, mean of 5 seeds:

| Capture | A | B | D |
|---|---|---|---|
| 34-1 | 0.004 | 0.507 | 0.330 |
| 8-1 | 0.400 | 0.335 | 0.400 |
| 21-1 | 1.0 | 1.0 | 1.0 |

### 1.2 Leave-one-capture-out (8 captures × 5 seeds)

| Held-out capture | Rows with DNS / alert context | A | B | C | D | P | STR |
|---|---|---|---|---|---|---|---|
| 1-1 | 1% / 3% | 0.954 | 0.897 | 0.953 | 0.953 | 0.935 | 0.465 |
| 20-1 | 28% / 0% | 0.997 | 0.976 | 1.000 | 1.000 | 0.896 | 0.297 |
| 21-1 | 76% / 0% | 0.972 | 0.983 | 0.983 | 0.983 | 0.949 | 0.295 |
| 3-1 | 0% / 93% | 0.519 | 0.520 | 0.517 | 0.520 | 0.520 | 0.386 |
| 34-1 | 12% / 100% | 0.178 | 0.563 | 0.268 | 0.376 | 0.180 | 0.468 |
| 42-1 | 91% / 85% | 0.398 | 0.357 | 0.357 | 0.357 | 0.361 | 0.294 |
| 48-1 | 2% / 6% | 0.998 | 0.998 | 0.737 | 0.997 | 0.998 | 0.366 |
| 8-1 | 0% / 0% | 0.407 | 0.407 | 0.407 | 0.407 | 0.407 | 0.470 |

Fold-level differences (seed means). Rows marked "+, −" give the number of folds where the difference is positive and negative; one fold (8-1) is exactly 0 throughout.

| | B − A | C − A | D − A | B − P | D − P |
|---|---|---|---|---|---|
| Folds +, − | 3, 4 | 3, 4 | 4, 3 | 4, 3 | 5, 2 |

**Interpretation:**

- With correct sampling, all conditions score identically on 8-1, which has no context. The 8-1 "gain" reported earlier was a sampling artefact (D1), not information.
- Only one held-out capture, 34-1, shows a large benefit from context: B − A = +0.385 and D − A = +0.197.
- On the other folds the effect is small, and often negative. For example, B − A is −0.057 on 1-1, and C − A is −0.261 on 48-1.
- Connection features alone transfer well to 1-1, 20-1, 21-1 and 48-1, and poorly to 3-1, 8-1, 34-1 and 42-1.

**Cross-log conclusion.** DNS context can add real, connection-level information. In this data, it produced a large gain on one of eight unseen networks and no consistent gain overall. There is no reliable benefit from IDS-alert context. The evidence for a general improvement from cross-log correlation is therefore weak.

## 2. P4: Ablation v2 on the Run B split (300 s, 5 seeds, predictions saved)

| Feature set | Macro F1 mean (SD) | FPR | FNR |
|---|---|---|---|
| `event_only` | 0.9952 (0.0012) | 0.38% | 0.01% |
| `event_no_sport` | 0.9937 (0.0003) | 0.36% | 0.01% |
| `incident_only` | 0.8566 (0.0035) | 9.16% | 0.43% |
| `event_plus_incident` (completed window) | 0.9964 (0.0003) | 1.14% | 0.01% |
| `event_plus_causal` (earlier events only) | 0.9957 (0.0006) | 1.17% | 0.02% |

**Findings:**

- **Reproduction.** `event_only`, `incident_only` and `event_plus_incident` reproduce the historical ablation exactly, seed by seed (§5).
- **Per-class recall, seed 42, `event_only`:**

  | Class | Recall |
  |---|---|
  | benign | 0.9958 |
  | c2 | 0.9991 |
  | dos | 1.0 |
  | malware | 1.0 |
  | recon | 0.9994 |

  Confusion matrices and per-source metrics for every run are in `runB_metrics.json`.
- **Source port (M2).** In the pooled model `sport` has importance 0.029. Removing it costs 0.0015 macro F1 within the Run B split. Within-capture, the conclusions do not depend on `sport`.
- **Causal context (M4).** Context computed from earlier events only behaves like completed-window context: the FPR rises from 0.38% to 1.17%. The FPR increase from incident context is therefore not caused by look-ahead.

## 3. P2: Leave-one-source-out (13 sources × 3 seeds)

**Design:**

- The training pool is all events of the other 12 sources; the test set is every event of the held-out source.
- The per-source fragmented baseline cannot be applied to a source it was not trained on, so it is not run here.
- The inputs are the Run B preprocessed events. Their scaling is a monotone transform, which does not affect a Random Forest. Categorical codes that were unseen in Run B training are −1.

Mean macro F1 over the 13 held-out sources (five-class):

| Feature set | Mean macro F1 | Folds better / worse than `event_only` |
|---|---|---|
| `event_only` | 0.375 | — |
| `event_no_sport` | 0.410 | 9 / 4 |
| `incident_only` | 0.251 | 4 / 9 |
| `event_plus_incident` | 0.446 | 9 / 4 |
| `event_plus_causal` | 0.429 | 10 / 2 |

Per-source values, including FPR, binary attack detection and the test classes absent from training, are in `loso_metrics.json`.

**Interpretation:**

- **M1: the main result does not transfer to unseen sources.** The 0.995 macro F1 of event-level detection is a within-capture figure. On unseen sources, five-class macro F1 falls to 0.02–0.80 depending on the source.
- **Binary detection holds up better than class assignment.** Binary attack detection is ≥ 0.95 on 1-1, data_1, data_10 and data_36. It is 0.003 on 34-1 and 0.44–0.85 elsewhere.
- **Incident-only detection is worse here too.** It is worse than event-level detection on unseen sources (9 of 13 folds), as it was within captures. The negative answer for incident summaries holds in both settings.
- **Incident context helps under transfer.** Adding it to event features helps on unseen sources (9 of 13 folds, +0.07 mean macro F1), whereas within captures it only raised the FPR. Causal context gives a similar gain (10 of 2 folds). This is a new, mixed finding: incident context may support generalisation even though it adds nothing within captures.
- **Removing `sport` helps on unseen sources** (9 of 13 folds, +0.036). This is consistent with `sport` acting as a mild capture-specific shortcut.
- **Class coverage.** No held-out source has an attack class that is completely absent from the other sources.

## 4. P3: Tests

`tests/test_v2.py`, 15 tests on synthetic data, all passing. They cover:

- class-stratified sampling keeps rare classes, and the historical binary sampler can lose them;
- the zero and permuted controls (zero columns; permutation stays within a capture, moves rows jointly and leaves the original columns unchanged);
- the causal-window boundary (a record exactly at `ts` is included);
- `local_host` in all four private/public cases;
- label-match edge cases (tolerance boundary, different Community ID, duplicate labelled rows);
- causal incident context (uses earlier events only; unchanged when later events are removed);
- the `sport`-free feature set;
- manifest fields and SHA-256 hashes.

## 5. P5: Independent verification

`verify_v2.py` recomputes every reported metric from the saved predictions with scikit-learn, independently of the experiment code. It also re-hashes every output listed in each manifest and compares the v2 ablation with the historical ablation where the two designs coincide. The result is in `results/verification.json` The outcome is `all_ok = true` (`RUN_LOG.md` §11).
