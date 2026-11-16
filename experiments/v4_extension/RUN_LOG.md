# Run log — v4 extension (E1 rich incident summaries, E2 alert-workload proxy)

All times UTC (the scripts print machine local time, UTC+4).

## 1. Environment

| Item | Value |
|---|---|
| Machine | AMD Ryzen 7 7800X3D (16 logical CPUs), 31.2 GB RAM, Windows 11 Pro 10.0.26300 |
| Python | 3.15.0, project venv `code/.venv` |
| Packages | numpy 2.5.3, pandas 3.0.6, scikit-learn 1.9.1, pyarrow 26.0.0, scipy 1.18.1, matplotlib 3.11.2 |
| Git HEAD at start | `3fde77c` (clean; only untracked `experiments/v4_extension/`) |
| Flags | `PYTHONPATH=code`, `PYTHONDONTWRITEBYTECODE=1`, `python -B` |
| RF | 300 trees, max_depth 24, min_samples_leaf 2, class_weight balanced_subsample, bootstrap, n_jobs 15 (`run_ablation.fit_predict`, unchanged) |
| Training sample | 60,000 per class per seed (`run_ablation.sample_train`), 196,406 events; seed = model seed |
| Seeds | 42, 1, 2, 3, 4 (bootstrap seed 42, 1,000 replicates, clusters = Run B incident_id) |
| Window | 300 s; sensitivity 60 s and 900 s |

## 2. Reused code (imported unchanged, nothing copied or edited)

- `experiments/ablation/run_ablation.py`: `load_events`, `incident_context`, `shared_features`,
  `sample_train`, `fit_predict`, `score`, `paired_bootstrap`, `markdown`; `correlation_key`
  and `evaluate_split` through it.
- `experiments/review/permuted_context.py`: `permute_context`, `compare_to_original`.
- `experiments/v3/stats_v3.py`: `sign_flip_p`, `holm`.

No shared helper needed changing, so nothing was copied.

## 3. Tests

```
cd experiments/v4_extension
PYTHONPATH=<submission>/code ../../code/.venv/Scripts/python.exe -B -m unittest discover -s tests
```

About 04:58 UTC: 8 feature tests OK (after fixing a read-only-array error in the first
attempt; code fix only, no design change). About 05:08 UTC, with the E2 tests added:
**11 tests OK.** Rerun before the final commit: 11 OK.

`test_rich_features.py` (8 tests):
- Hand-computed values for a 3-event group: counts, distinct ports, all six statistics with the
  sentinel ignored, category shares.
- The same key in train and test gives two groups, and no group spans two splits.
- Sentinel and `__NA__` codes are treated as missing.
- The top-share rule applies above the category limit.
- Categories come from training events only.
- Label-free: identical output with any label value or no label column; asking for `label` as a
  feature raises an error.
- The thin part equals `incident_context`.

`test_alert_workload.py` (3 tests):
- Hand-checked alert counts, false alarms, detected/missed incidents and delays for A and C.
- C's event metrics equal A's.
- Grouping does not depend on labels.

## 4. Runs

### 4.1 E1

```
PYTHONPATH=code code/.venv/Scripts/python.exe -B -u experiments/v4_extension/run_rich_incident.py runb windows loso
```

- **Runtime:** one attempt, 05:00:25–05:40:32 UTC, exit 0. Log: `results/e1/run.log`.
- **Gate (05:02:08):** seed 42 `incident_thin`, `event_only` and `event_plus_thin` reproduced
  the saved ablation (`incident_only` w300, `event_only` w0, `event_plus_incident` w300) in all
  subsets and metrics, tolerance 1e-12. After all seeds: 75/75 rows match
  (`results/e1/runb_checks.json` → `gate_seed42`, `gate_all_seeds`).
- **Other checks:**
  - 4,211,383 events, 1,692,332 test, 1,463,143 novel vectors, 704,090 groups at 300 s.
  - 77 rich features. The thin columns inside the rich set equal `incident_context` exactly.
  - Recovered `__NA__` codes: app 1, conn_state 13, history 200, flgs 0, state 10.
- **Phases:** Run B conditions and bootstrap until 05:15:39; windows 05:15:39–05:23:30;
  LOSO 05:23:30–05:40:32.
- **LOSO baseline:** `event_only` matches v3 `rf_event_only` macro F1 in 65/65 fold × seed runs
  (`results/e1/loso/loso_stats.json`).
- **Warnings:** 5 scikit-learn `UserWarning: A single label was found` lines, from single-class
  subsets (benign-only). They are the same kind as in the original ablation log and harmless.

### 4.2 E2

```
PYTHONPATH=code code/.venv/Scripts/python.exe -B -u experiments/v4_extension/run_alert_workload.py
```

- **Runtime:** one attempt, 05:02:24–05:06:33 UTC, exit 0. Log: `results/e2/run.log`.
- **Timing of the run:** it ran while E1 was training, after the E1 gate had written the seed-42
  `event_only` and `event_plus_thin` predictions it reads. E2 is deterministic and does not train,
  so the overlap only affects run time.
- **Checks (`results/e2/checks.json`):**
  - 1,692,332 test events; 175,489 true incidents, of which 64,243 are attack incidents.
  - C equals A on event metrics and on open delay, for every prediction source.
  - The integrated prediction is constant within each incident.

### 4.3 Figures

```
code/.venv/Scripts/python.exe -B experiments/v4_extension/make_figures.py
```

Run at 05:08 (E2 figure only, E1 not finished) and at 05:41 (both). Output: `results/figures/*.png`, 300 dpi.

### 4.4 Protected files

- **Tracked files:** `git status` / `git diff` show no change to `experiments/v2`, `v3`,
  `ablation`, `review`, `predictions/`, `metrics/` or `code/`.
- **Untracked inputs:** SHA-256 of 53 files (Run T results and events, Run B
  `code/data/processed/stage3_events` and feature plan, `code/results`, `code/models`).
  Before: `results/untracked_inputs_sha256_before.txt`; after:
  `results/untracked_inputs_sha256_after.txt`. **Identical.**
- **No downloads.** Nothing was downloaded.

## 5. Decisions and deviations

All of these were fixed before results were seen, unless stated otherwise. No design change was made after seeing results.

| # | Decision / deviation | Reason |
|---|---|---|
| D1 | Rich features use the 11 `shared_features` plus `dst_ip` (distinct count) | Brief: shared features so both datasets have them |
| D2 | Categorical `__NA__` codes recovered label-free as the one code a whole dataset carries, and treated as missing like −1 | Stage 2 did not save its vocabulary; an absent field is a missing value, not a category |
| D3 | Per-category shares when ≤ 16 training categories, otherwise top share + distinct count (only `history`, 200 categories) | "Too many categories" rule from the brief; limit fixed before any run |
| D4 | Ports get distinct counts only; duration, bwd_pkts and bytes get the six statistics; std with ddof 0 | Ports are identifiers; ddof 0 gives 0 for single-event groups instead of NaN |
| D5 | Category columns are the codes seen in Run B **training** events; the same set is used for windows and LOSO | No test-derived column choice for the Run B design. For LOSO this set includes training-split events of the held-out source. It only fixes which columns exist (no labels, no values) |
| D6 | LOSO context built with split = "all", as `experiments/v3/transfer_v3.py` does | Folds are whole sources and the key contains the source, so no group crosses train and test |
| D7 | `event_plus_rich_permuted` uses `permute_context` (whole rows, within split × source, seed = model seed) | Brief; same procedure as experiments/review |
| D8 | MEB subset = benign test events in a group of more than 1 event at the run's window (ablation definition) | Comparability with the ablation |
| D9 | Importances are RF impurity (MDI), mean over 5 seeds, not permutation | Permutation on 1.69 M events × 77 features is too slow (brief allows MDI if stated) |
| D10 | **Deviation:** the "Run B ablation predictions" for E2 were never saved by the ablation. E2 uses the seed-42 `event_only` and `event_plus_thin` predictions regenerated in E1, which reproduce the ablation exactly (gate) | Only way to use ablation predictions without changing experiments/ablation |
| D11 | E2 delay conventions: A = first alerted attack event; B = incident's last event; C open (= A) and C closed (group's last member) | Defined in the script docstring before running; closed delays are retrospective |
| D12 | **Deviation (storage only):** E2 alert-group id files (`results/e2/groups_*.parquet`, about 65 MB) are kept locally and gitignored | `run_alert_workload.py` rebuilds them exactly; the per-event predictions needed are committed in `e2_events.parquet` |
| D13 | **Observed, not changed:** `n_distinct_dst_ip` and `n_distinct_proto` are constant (1) on the real data, because every group uses the (src, dst, proto) rule | Kept as specified; documented in FEATURES.md |
| D14 | **Observed, not changed:** the 76.33% MEB FPR in the brief is the Run B integrated model's; the ablation's thin RF has 68.45% | Both reported in RESULTS.md |

## 6. Commits

- `197e49e`: feature code, tests, E2 runner and results, figure script (pushed before E1 finished).
- Next commit: E1 results, RESULTS.md, RUN_LOG.md, figures.
