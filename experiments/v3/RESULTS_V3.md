# v3 results: fair transfer study and cross-log expansion

**Scope.** Steps 2–6 of the post-audit plan. The design was pre-registered in `PLAN_V3.md` before any v3 result was seen.

- Every number here comes from files in `v3/results/`.
- The tables in `results/tables.md` are generated from those files by `report_v3.py`.
- Every value is recomputed independently by `verify_v3.py` (→ `results/verification.json`).
- Nothing outside `experiments/v3/` was changed. Step 1 (thesis writing) was skipped, as requested.

## 1. What was run

| Part | Design | Seeds | Outputs |
|---|---|---|---|
| Transfer `runB` | Run B train/test split, 13 sources, 4.21 M events | 42, 1, 2, 3, 4 | `results/transfer/runB/` |
| Transfer `loso` | Leave-one-source-out, 13 folds | 42, 1, 2, 3, 4 | `results/transfer/loso/` |
| Statistics | Pre-registered paired tests | — | `results/transfer/stats.json` |
| Cross-log `primary_augmented` | Original training captures plus 36-1 and 7-1; pre-registered test captures 8-1, 21-1, 34-1 | 42, 1, 2, 3, 4 | `results/cross_log/primary_augmented*.json/parquet` |
| Cross-log `loco` | Leave-one-capture-out over the 9 captures that pass the gate | 42, 1, 2, 3, 4 | `results/cross_log/loco*` |

**Transfer models:**

- RF: thesis settings;
- HGB: library defaults with balanced class weights;
- LR: one-hot encoding plus symlog and standard scaling, balanced class weights.

Each model is run on three feature sets: `event_only`, `incident_only` and `event_plus_incident`. Nothing was tuned on test data.

**Source-specific (fragmented) baseline:**

- `runB`: each source's own RF predicts that source's own test rows.
- `loso`: the held-out source has no model of its own, so the other 12 source models are combined by a rule fixed in advance. No held-out label is used anywhere.
  - `frag_soft` (primary rule): average the probabilities.
  - `frag_union`: alert if any model alerts.

**Metrics.** All original metrics are kept. The added metrics are:

- macro F1 over the classes present in the test labels;
- balanced accuracy;
- MCC;
- binary F1;
- binary PR-AUC and ROC-AUC;
- macro PR-AUC over the classes present.

## 2. Transfer study: results

### 2.1 Within the Run B split (5-seed mean ± sd)

| Run | Macro F1 | MCC | Binary PR-AUC | FPR | FNR |
|---|---|---|---|---|---|
| frag (source-specific RF) | 0.9955 ± 0.0000 | 0.9988 | 1.0000 | 0.0045 | 0.0001 |
| RF event_only | 0.9952 ± 0.0012 | 0.9990 | 1.0000 | 0.0038 | 0.0001 |
| RF incident_only | 0.8566 ± 0.0035 | 0.9726 | 0.9994 | 0.0916 | 0.0043 |
| RF event_plus_incident | 0.9964 ± 0.0003 | 0.9977 | 1.0000 | 0.0114 | 0.0001 |
| HGB event_only | 0.9976 ± 0.0003 | 0.9987 | 1.0000 | 0.0036 | 0.0003 |
| HGB incident_only | 0.7656 ± **0.1804** | 0.8397 | 0.9974 | 0.1022 | 0.0039 |
| HGB event_plus_incident | **0.9990 ± 0.0002** | 0.9991 | 1.0000 | **0.0025** | 0.0002 |
| LR event_only | 0.6719 ± 0.0022 | 0.7287 | 0.9999 | 0.0396 | 0.0052 |
| LR incident_only | 0.6452 ± 0.0005 | 0.9102 | 0.9988 | 0.1271 | 0.0034 |
| LR event_plus_incident | 0.9650 ± 0.0091 | 0.9833 | 0.9999 | 0.0304 | 0.0009 |

**Paired tests (seed level, n = 5).** The smallest attainable two-sided p is 0.0625, so no seed-level comparison can reach p < 0.05. That is why the incident-clustered bootstrap on seed 42 is also reported.

| Comparison (X − Y) | Δ macro F1 | Seeds +/− | Bootstrap 95% CI for Δ F1 | Δ FPR | Bootstrap 95% CI for Δ FPR |
|---|---|---|---|---|---|
| frag − RF event_only | +0.0003 | 4/1 | [−0.0076, +0.0062] | +0.0008 | [−0.0009, +0.0007] |
| RF incident_only − frag | −0.1388 | 0/5 | [−0.178, −0.108] | +0.0870 | [+0.084, +0.091] |
| RF incident_only − RF event_only | −0.1385 | 0/5 | [−0.176, −0.107] | +0.0878 | [+0.084, +0.091] |
| RF event_plus_incident − RF event_only | +0.0012 | 4/1 | [−0.0014, +0.0048] | **+0.0076** | [+0.0060, +0.0081] |
| HGB incident_only − HGB event_only | −0.2320 | 0/5 | [−0.678, −0.464] (seed 42) | +0.0986 | [+0.125, +0.136] |
| HGB event_plus_incident − HGB event_only | +0.0014 | 5/0 | [+0.0007, +0.0025] | **−0.0011** | [−0.0016, −0.0001] |
| LR incident_only − LR event_only | −0.0267 | 0/5 | [−0.056, +0.019] | +0.0875 | [+0.084, +0.093] |
| LR event_plus_incident − LR event_only | +0.2931 | 5/0 | [+0.274, +0.356] | −0.0092 | [−0.0096, −0.0074] |

### 2.2 On unseen sources (leave-one-source-out; mean over 13 held-out sources of the 5-seed mean)

| Run | Macro F1 | F1 over present classes | Balanced accuracy | MCC | Binary PR-AUC (n = 11) | FPR | FNR (n = 11) |
|---|---|---|---|---|---|---|---|
| frag_soft | 0.296 | 0.311 | 0.493 | 0.008 | 0.892 | 0.021 | **0.985** |
| frag_union | 0.091 | 0.118 | 0.160 | 0.118 | 0.831 | **1.000** | 0.000 |
| RF event_only | 0.372 | 0.553 | 0.581 | 0.261 | 0.887 | 0.171 | 0.340 |
| RF incident_only | 0.248 | 0.460 | 0.513 | 0.157 | 0.720 | 0.235 | 0.257 |
| RF event_plus_incident | **0.441** | 0.621 | 0.655 | 0.312 | **0.894** | 0.134 | 0.204 |
| HGB event_only | 0.302 | 0.458 | 0.505 | 0.139 | 0.775 | 0.230 | 0.479 |
| HGB incident_only | 0.265 | 0.474 | 0.517 | 0.136 | 0.675 | 0.273 | 0.239 |
| HGB event_plus_incident | 0.356 | 0.515 | 0.589 | 0.155 | 0.862 | 0.158 | 0.413 |
| LR event_only | 0.307 | 0.538 | 0.559 | 0.265 | 0.883 | 0.230 | 0.107 |
| LR incident_only | 0.203 | 0.421 | 0.412 | 0.058 | 0.619 | 0.461 | 0.122 |
| LR event_plus_incident | 0.409 | **0.665** | **0.725** | **0.394** | 0.883 | 0.140 | 0.117 |

Two held-out sources, honeypots 4-1 and 5-1, are benign only. Binary PR-AUC and FNR are therefore defined on 11 folds. On those two folds, a model that never alerts scores a macro F1 of 1.0, which inflates `frag_soft`'s macro F1. The per-source table is in `results/tables.md`.

**Paired tests on the primary metric, macro F1.** The unit is the held-out source (n = 13). Holm correction is over the 8 comparisons.

| Comparison (X − Y) | Mean Δ | Sources +/− | p (sign-flip) | p Holm | p Wilcoxon |
|---|---|---|---|---|---|
| frag_soft − RF event_only | −0.076 | 5/8 | 0.434 | 1.000 | 0.305 |
| RF incident_only − frag_soft | −0.048 | 7/5 | 0.635 | 1.000 | 0.910 |
| RF incident_only − RF event_only | −0.124 | 4/9 | 0.054 | 0.381 | 0.068 |
| RF event_plus_incident − RF event_only | +0.069 | 9/4 | 0.100 | 0.598 | 0.110 |
| HGB incident_only − HGB event_only | −0.038 | 6/7 | 0.568 | 1.000 | 0.588 |
| HGB event_plus_incident − HGB event_only | +0.054 | **11/1** | 0.013 | 0.106 | 0.009 |
| LR incident_only − LR event_only | −0.105 | 4/9 | 0.206 | 0.824 | 0.273 |
| LR event_plus_incident − LR event_only | +0.101 | **11/2** | 0.124 | 0.619 | 0.027 |

**Secondary metrics, Holm-corrected:**

- **FPR.** `frag_soft` − RF `event_only` = −0.150 (0/10 sources higher; p Holm = 0.016). RF `incident_only` − `frag_soft` = +0.214 (p Holm = 0.016). These are the only Holm-significant results in the transfer study. They reflect the fact that `frag_soft` almost never alerts on an unseen source (FNR 0.985).
- **Macro F1 over present classes.** `frag_soft` − RF `event_only` = −0.242 (4/9 sources; p = 0.007, p Holm = 0.055).
- All other secondary-metric comparisons have p Holm ≥ 0.28. The full tables are in `results/tables.md`.

### 2.3 What the transfer study supports

1. **The fair source-specific baseline does not generalise to unseen sources.** No held-out label is used.
   - The probability average almost never alerts: FNR 0.985, MCC 0.008.
   - The SOC-style union alerts on every benign event: FPR 1.0.
   - The pooled RF has a higher macro F1 (0.372 against 0.296) and a much higher F1 over present classes, but neither difference survives Holm correction. On the primary metric, the "unified beats fragmented" claim is therefore **directionally supported but not statistically established** on unseen sources.
   - Within the Run B split the two are equivalent: Δ = +0.0003, CI [−0.008, +0.006].
2. **Incident-only features are worse than event features in every model and design.**
   - Run B split: 0/5 seeds favour incident-only for every model. The bootstrap CI excludes 0 for RF and HGB but not for LR.
   - Unseen sources: 4/9 or 6/7 sources favour incident-only, depending on the model, so the result is not significant there.
3. **Adding incident context to event features helps all three model families on unseen sources.** The gain appears on 9 to 11 of the 13 sources, but **no gain survives Holm correction**; the strongest is HGB at p Holm = 0.106. Within the Run B split the gain is tiny for RF and HGB (+0.001) and large only for LR (+0.29), whose event-only model is weak.
4. **The false-positive effect of incident context depends on the model.**
   - Within the Run B split it raises FPR for RF (+0.0076, CI excludes 0) but lowers it for HGB (−0.0011, CI excludes 0) and for LR (−0.0092).
   - On unseen sources FPR is lower with context for all three models (not significant).
   - "Incident context raises false positives" is therefore an RF-specific finding, not a general one.
5. **Generalisation is weak overall.** Every model loses 0.55–0.70 macro F1 between the Run B split and unseen sources. HGB `incident_only` is unstable across seeds (sd 0.18).

## 3. Cross-log expansion: results

**Candidates.** The selection table is in `RUN_LOG.md` §12.

- Selected: 36-1 (15,688 C&C records) and 7-1 (5,778 C&C records, plus DoS).
- Both were processed with the same Zeek 9.0.1, Suricata 7.0.3 and ET Open rules (`all.rules` sha256 84530843…).
- Both pass the Stage 3 gate:
  - label match rate 1.0 (13,645,098 / 13,645,098 and 11,454,714 / 11,454,714 records);
  - benign and attack traffic both present;
  - 38 and 36 cross-source incidents.
- Suricata raised 2 and 36 alerts, all in the "Misc Attack" category.

**Class balance.** Both captures are extremely imbalanced:

| Capture | Okiru malware | C&C | Benign | DoS |
|---|---|---|---|---|
| 36-1 | 99.87% | 0.11% | 2,663 records | — |
| 7-1 | 98.9% | 5,778 records | 75,955 records | 39,584 records |

The cache rebuilt for the 9 old captures equals the original `cross_log/results/robust_cache` on every shared column (`results/cross_log/cachecheck.json`).

### 3.1 Primary split, with the C&C captures added to training

Training C&C records rise from 35 (v2) to 21,501. The table shows binary macro F1 over 5 seeds.

| | A (conn) | B (+DNS) | C (+alerts) | D (+both) | Z (zeros) | P (permuted) | MAJ | STR |
|---|---|---|---|---|---|---|---|---|
| v3 mean | 0.454 | **0.669** | 0.471 | 0.506 | 0.455 | 0.468 | 0.245 | 0.493 |
| v2 mean | 0.444 | 0.593 | 0.460 | 0.565 | 0.444 | 0.448 | 0.245 | 0.487 |

**Paired differences, all 5/0 seeds:**

- B − A = +0.214;
- B − P = +0.201;
- D − A = +0.052.

**Alerts are no better than their permuted control:** C − P = +0.003 (2/3 seeds).

**Per test capture (v3):**

| Capture | A | B | Note |
|---|---|---|---|
| 21-1 | 0.993 | 0.990 | |
| 34-1 | 0.213 | 0.688 | All of the B gain comes from here |
| 8-1 | 0.518 | 0.526 | C&C only; v2 was A 0.526 |

- **Adding 21,501 C&C training records did not improve the C&C test capture 8-1.** The 35-row limitation was therefore not why 8-1 scored poorly.
- Connection-only features (A) still score below the stratified random baseline STR (0.454 against 0.493).

### 3.2 Leave-one-capture-out (9 captures that pass the gate; 49-1 and 8-1 are excluded by the gate, as in v2)

| Held-out | n | A | B | C | D | P |
|---|---|---|---|---|---|---|
| 1-1 | 1,008,748 | 0.408 | 0.379 | 0.408 | 0.408 | 0.416 |
| 20-1 | 3,209 | 0.980 | 0.983 | 1.000 | 1.000 | 0.881 |
| 21-1 | 3,286 | 0.996 | 1.000 | 0.986 | 0.986 | 0.980 |
| 3-1 | 156,103 | 0.513 | 0.519 | 0.439 | 0.521 | 0.523 |
| 34-1 | 8,988 | 0.209 | **0.678** | 0.307 | 0.397 | 0.212 |
| 36-1 (new) | 13,645,098 | 0.999 | 1.000 | 0.999 | 1.000 | 0.920 |
| 42-1 | 4,426 | 0.398 | 0.357 | 0.357 | 0.357 | 0.361 |
| 48-1 | 3,394,338 | 0.998 | 0.998 | 0.936 | 0.998 | 0.997 |
| 7-1 (new) | 11,454,714 | 0.870 | 0.870 | 0.870 | 0.870 | 0.867 |

**Folds where the context condition beats the reference (+), loses (−) or ties:**

| Difference | v3 (+ / − of 9) | v2 (+ / − of 8) |
|---|---|---|
| B − A | 5 / 4 | 3 / 4 |
| C − A | 4 / 5 | 3 / 4 |
| D − A | 6 / 3 | 4 / 3 |
| C − P | 5 / 4 | 4 / 3 |

Apart from 34-1 (B − A = +0.469, D − A = +0.188), every per-fold difference is at most ±0.08. On the two new captures, all differences are ≤ 0.003: the binary task there is almost trivial (36-1) or saturated (7-1), whatever the context.

### 3.3 What the cross-log expansion supports

The v2 conclusion stands with 9 folds instead of 8:

- Log context helps on one capture type, 34-1, with DNS context.
- It does not help consistently across captures.
- Suricata alert context is no better than its permuted control.

The two new captures add test volume but little information about context. Each is dominated by a single attack family, and Suricata raised almost no alerts on them.

## 4. Verification and reproducibility

The verification outcome is in `results/verification.json`; see `RUN_LOG.md` §12 for the final status.

- **Transfer:**
  - 550 (Run B split) and 7,865 (leave-one-source-out) metric values are recomputed with scikit-learn from the saved predictions and probabilities: 0 mismatches.
  - All p-values are recomputed with a separate bit-table implementation: 0 mismatches.
  - Manifest hashes match the files on disk.
  - RF `event_only`, `incident_only` and `event_plus_incident` on the Run B split reproduce the historical ablation exactly for all 15 seed and feature-set pairs.
- **Cross-log:** binary macro F1, FPR and FNR are recomputed for every fold, condition and seed of both cross-log runs, and the manifest hashes are checked.
- **Lean Zeek reader** (`lean_io.py`, used only for Stage 3 on the new captures): it returns identical frames to the original reader on all 26 old conn, DNS and labelled logs (`results/lean_io_check.json`).
- **Tests:** v3 12, v2 15, cross-log 14, ablation 6, thesis 94, all OK.
