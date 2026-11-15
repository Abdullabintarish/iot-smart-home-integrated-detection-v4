# v3 plan, fixed before any v3 result was seen (2026-11-03)

This plan covers steps 2–6 of the post-audit recommendation, as requested by the user.

**Ground rules:**

- Everything is new and lives under `experiments/v3/`.
- No earlier result, pipeline output, dashboard or thesis chapter is changed.
- All results are reported, whichever way they go.

## A. Transfer study on the Run B events (steps 2–5)

**Data:** the 4,211,383 Run B preprocessed events in `code/data/processed/stage3_events` (13 sources), with the same 20 event features. The incident context is that of the ablation:

- `n_events`, `span_s` and `events_per_s`;
- computed over a completed 300 s window, with the Run B correlation key.

**Designs.** Both use 5 seeds (42, 1, 2, 3, 4). Each seed fixes the training sample and the model.

| Design | Train | Test | Context groups |
|---|---|---|---|
| `runB` | Run B train split | Run B test split | Cut at the split, as in the ablation |
| `loso` | All events of the other 12 sources | Every event of the held-out source | Not cut |

**Training sample.** `run_ablation.sample_train`: at most 60,000 rows per class from the training pool. The same sample is used for every model and feature set within a seed and fold.

**Pooled models:**

| Model | Settings | Input |
|---|---|---|
| RF | Thesis settings: 300 trees, depth 24, `min_samples_leaf` 2, `balanced_subsample` | Feature matrix as is |
| HGB | `HistGradientBoostingClassifier`: `max_iter` 300, learning rate 0.1, `max_leaf_nodes` 31, `class_weight="balanced"`, no early stopping | Same matrix as RF |
| LR | Multinomial `LogisticRegression` (lbfgs, `max_iter` 1000, `class_weight="balanced"`) | Categorical codes one-hot encoded (unseen → all zero). Numeric features `sign(x)·log1p(\|x\|)` and then standardised, fitted on the training sample |

- Each pooled model is run on three feature sets: `event_only`, `incident_only` and `event_plus_incident`.
- The settings are fixed library defaults or the thesis settings. **No tuning on test data.**

**Source-specific (fragmented) baseline.** One RF per source (thesis settings) on `event_only`, trained only on that source's training rows. A source with a single training class becomes a constant model.

| Design | How the fragmented baseline predicts |
|---|---|
| `runB` | Each source's model predicts its own test rows (the Run B baseline, now with 5 seeds) |
| `loso` | The held-out source has no model of its own, so the 12 models of the other sources are combined by a rule fixed here. No held-out label is used |

The two combination rules for `loso`:

- **`frag_soft` (primary).** Average the 12 class-probability vectors (a class a model never trained on gets 0) and predict the argmax. Attack score = 1 − mean P(benign).
- **`frag_union` (secondary; models a SOC that receives every detector's alerts).** Predict an attack if any model predicts a non-benign class. The class is the attack class with the largest summed probability among the alerting models. Attack score = maximum over models of 1 − P(benign).

**Metrics.** All metrics are computed from the saved predictions and probabilities. Probabilities are stored as float16, and the metrics are computed from those stored values.

- **Original metrics (kept for comparability):** accuracy; macro precision, recall and F1 over the union of true and predicted labels; FPR; FNR; per-class precision, recall and F1; confusion matrix.
- **Added metrics:**
  - macro F1 over the classes present in the test labels;
  - balanced accuracy;
  - Matthews correlation coefficient;
  - binary attack-vs-benign F1;
  - binary PR-AUC (average precision) and ROC-AUC of the attack score;
  - macro one-vs-rest PR-AUC over the classes present.

  A metric whose denominator or class set is empty is reported as null.

**Statistics.**

- **Primary metric:** original macro F1. **Secondary metrics:** macro F1 over present classes, binary PR-AUC and FPR.
- **Comparisons**, each written as X − Y:
  1. `frag` − RF `event_only` (`frag` is `frag_soft` in `loso`)
  2. RF `incident_only` − `frag`
  3. RF `incident_only` − RF `event_only`
  4. RF `event_plus_incident` − RF `event_only`
  5. HGB `incident_only` − HGB `event_only`
  6. HGB `event_plus_incident` − HGB `event_only`
  7. LR `incident_only` − LR `event_only`
  8. LR `event_plus_incident` − LR `event_only`
- **`loso` test:** the unit is the fold (seed-mean metric per held-out source).
  - Exact paired sign-flip permutation test, two-sided.
  - Wilcoxon signed-rank test.
  - Holm correction across the 8 comparisons, separately for each metric.
  - Folds where a metric is null are dropped, and the remaining n is reported.
- **`runB` test:**
  - Seed-level paired differences, sign counts and an exact sign-flip test. With n = 5 the smallest possible p is 0.0625, and this is stated.
  - An incident-clustered paired bootstrap (1,000 replicates) on seed 42 for macro F1 and FPR.
- Descriptive only, not tested: `frag_union` against `frag_soft`, and the models against each other.

**Verification.** An independent script recomputes every metric from the saved files with scikit-learn and recomputes the permutation p-values. It also checks the manifest hashes, and checks that RF `event_only` and RF `incident_only` on `runB` reproduce the historical ablation exactly.

## B. Cross-log expansion (step 6)

Additional IoT-23 captures are added only if all of the following hold:

1. The labelled `conn.log.labeled` is available.
2. The labels contain C&C traffic (the thesis class c2).
3. The pcap fits the disk budget (the project total stays ≤ 50 GB).
4. The capture passes the existing Stage 3 gate (`cross_log/PLAN.md`): benign and attack both present, a new-record label match rate ≥ 0.90, and cross-source incidents present.

**Processing.** Each added capture goes through the same sensors (Zeek 9.0.1, Suricata 7.0.3 with the same ET Open ruleset), the same label transfer and the same feature cache code, writing to new v3 folders.

**Analysis.** The v2 cross-log design (`v2/cross_log_v2.py`: class-stratified sampling, conditions A–D, controls Z and P, baselines MAJ and STR) is repeated on two splits:

- leave-one-capture-out over all captures that pass the gate;
- the primary split with the added C&C captures appended to training. This addresses the 35-row C&C limitation. The test captures stay as pre-registered.
