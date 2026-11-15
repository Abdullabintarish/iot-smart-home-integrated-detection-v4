# Run log — reviewer analyses (experiments/review/)

All times are UTC (machine local time is UTC+4; the script logs print local time).

## 1. Environment

| Item | Value |
|---|---|
| Machine | AMD Ryzen 7 7800X3D (16 logical CPUs), 31.2 GB RAM, Windows 11 Pro 10.0.26300 |
| Python | 3.15.0 (`code/.venv`, the project venv used for the ablation) |
| Packages | numpy 2.5.3, pandas 3.0.6, scikit-learn 1.9.1, pyarrow 26.0.0 |
| Git HEAD at start | `9f8cda88709a5104a1c71a182bb76134ca8f8bfe` (clean apart from untracked `experiments/review/`) |
| Session start | 2026-11-15 16:35 UTC |
| Flags | `PYTHONPATH=code`, `PYTHONDONTWRITEBYTECODE=1`, `python -B` (no `__pycache__` written in `code/`) |

## 2. Protected files

Nothing was written outside `experiments/review/`. Run B, Run C, Run T,
`results/`, `models/`, `predictions/`, `metrics/`, `code/`, `experiments/ablation`,
`v2` and `v3` were only read.

- Before the runs, SHA-256 of 68 protected files (ablation `results/full`,
  Run T `results/` and `stage3_events`, Run B `code/data/processed/stage3_events`
  and feature plan, `metrics/`, `predictions/`, `code/results/`, `code/models/`):
  `results/protected_sha256_before.txt`.
- After the runs: `results/protected_sha256_after.txt`; comparison in §6.

## 3. Files

| File | Purpose |
|---|---|
| `permuted_context.py` | Analysis 1. Imports `experiments/ablation/run_ablation.py` unchanged and reuses its loader, incident context, training sample, RF fit, scoring and bootstrap |
| `boundary_sensitivity.py` | Analysis 2. Reads Run T events and saved predictions; no training |
| `tests/test_review.py` | 11 synthetic unit tests (shuffle, reproduction gate, boundary detection) |
| `results/permuted_context/` | `review_results.csv` (every run × subset), `review_summary.csv`, `review_table.md`, `bootstrap.json`, `checks.json`, `run.log` |
| `results/boundary/` | `boundary_metrics.csv`, `boundary_counts.json`, `per_class.json`, `checks.json`, `run.log` |
| `RESULTS.md` | Tables and the source file of every number |

## 4. Tests

```
cd experiments/review
PYTHONPATH=<submission>/code ../../code/.venv/Scripts/python.exe -B -m unittest discover -s tests
```

16:35 UTC: **11 tests OK** (also run after the per-class change to the boundary
script at 16:38 UTC: 11 OK).

Shuffle tests: distribution kept per (partition, source) stratum as a multiset
of whole rows; rows move whole and keep dtypes; link broken (< 20% of events
keep their own row; > 90% of multi-event incidents no longer have a constant
context); train and test shuffled separately (no row crosses partitions, and
changing train rows leaves the shuffled test rows unchanged); class-blind
(labels are not an input) and seeded; a label planted in the context is
destroyed by the shuffle. End-to-end: the reproduction gate passes against a
matching saved ablation and returns exit code 2 (no bootstrap written) against
a perturbed one.

Boundary tests: a group with train and test events in the same 300 s bucket
is flagged on both sides; train-only, test-only, other-source and
uncorrelatable rows are not; the secondary (bucket-free) definition flags the
later bucket of the same flow; end-to-end on a fake Run T folder.

## 5. Runs

### 5.1 Analysis 2 — Run T boundary sensitivity

```
PYTHONPATH=code code/.venv/Scripts/python.exe -B -u experiments/review/boundary_sensitivity.py
```

- First run 16:36:07–16:37:08 UTC, exit 0. Rerun 16:38 UTC, exit 0, after adding
  `per_class.json` (per-class F1 and confusion matrices). The numbers in
  `boundary_metrics.csv` were identical in both runs; only the extra file is new.
- Inputs: `../thesis_final_validation/supplementary_temporal/code/data/processed/stage3_events/*.parquet`
  (18 files), `.../results/{fragmented,integrated}_event_predictions.csv`,
  `.../results/stage5_report.json`. Found at the location named in
  `docs/thesis_final_validation/01_Completed_Phases_Review.md`; not BLOCKED.
- Checks (`results/boundary/checks.json`), all passed:
  - 4,211,383 events, 1,052,847 test (= Run T RESULTS.md).
  - Prediction rows line up with the event table (event_id = stream position,
    as in `pipeline.detect.scan_events`): source, incident_id, split and label
    agree on every row, for both conditions.
  - Recomputed all-event metrics equal `stage5_report.json` (tolerance 1e-12)
    for fragmented and integrated.
  - Split-free groups + singletons = 704,090 (= Run B incidents); with the split
    side = 704,151 (= Run T incidents). So exactly 61 groups were cut.
- Seeds: none (no randomness).

### 5.2 Analysis 1 — permuted-context control

```
PYTHONPATH=code code/.venv/Scripts/python.exe -B -u experiments/review/permuted_context.py
```

Defaults: windows 60 150 300 600 900; seeds 42 1 2 3 4; 300 trees,
max_depth 24, `MIN_SAMPLES_LEAF` and `CLASS_WEIGHT` from `pipeline.detect`
(via `run_ablation.fit_predict`); 60,000 training events per class per seed
(`run_ablation.sample_train`, seed = model seed; 196,406 training events);
n_jobs 15; bootstrap 1,000 replicates, seed 42, clustered on Run B incident_id.
Shuffle seed = model seed.

- Run 16:36:06–16:58:48 UTC (22.7 min), exit 0, one attempt. No warnings in
  `results/permuted_context/run.log`.
- Checks (`results/permuted_context/checks.json`): 4,211,383 events; 1,692,332
  test; 1,463,143 novel test vectors; 704,090 groups at 300 s; 196,406
  training events for every seed (all equal the original ablation's `checks.json`).
- **Reproduction gate passed** (16:37:13 UTC): seed 42 `event_only` and
  `event_plus_incident` (300 s) matched `experiments/ablation/results/full/ablation_results.csv`
  in all 5 subsets and all metrics plus `n` and `n_train` (tolerance 1e-12).
- After the run, all 30 rerun `event_only` / `event_plus_incident` runs
  (150 rows) were compared with the original: **all match**
  (`results/permuted_context/full_reproduction.json`).
- Permutation: the distribution was kept in all 25 (window, seed) shuffles. 18.1%–33.9% of
  test events keep identical values (ties); reported in RESULTS.md §1c.
- Bootstrap: windows 60–900 s, seed-42 predictions, 1,000 replicates,
  bootstrap seed 42, `run_ablation.paired_bootstrap` unchanged.

### 5.3 Post-run verification

- 16:59 UTC: protected hashes recomputed (`results/protected_sha256_after.txt`):
  **68/68 identical** to the pre-run list.
- `git status`: the only change is untracked `experiments/review/`. No `__pycache__`
  was created in `code/`.

## 6. Decisions

| # | Decision | Reason |
|---|---|---|
| D1 | `permuted_context.py` imports `run_ablation.py` from `experiments/ablation/` rather than copying it | Guarantees identical RF settings, sampling, scoring and bootstrap; the original file is unchanged (hash in before/after list) |
| D2 | Shuffle the three incident columns together as whole rows | Keeps their joint distribution, not only the marginals |
| D3 | Strata = (split, source) over **all** events of a partition, before the training sample is drawn | "Within each partition and within each class-blind source"; separate strata make train and test shuffles independent |
| D4 | One `default_rng(model seed)` per shuffle; order of strata fixed by sorting | Shuffle seed = model seed, reproducible |
| D5 | Subsets of the permuted condition use the **true** incident sizes | The subsets then contain the same events as `event_plus_incident` |
| D6 | `event_only` and `event_plus_incident` were re-run for all seeds and windows, not taken from the saved CSV | Gives the bootstrap its predictions and extends the reproduction check to all 30 runs |
| D7 | Bootstrap at every window (seed 42), not only 300 s | The original ablation bootstrapped 300 s only; all windows are reported so none is selected |
| D8 | Boundary = split-free correlation key (with the 300 s bucket) seen in both train and test | This is exactly what Run T split in two (704,151 − 704,090 = 61 groups) |
| D9 | A broader bucket-free flow definition is reported as **secondary** | Shows how much the answer depends on the definition; not used for headline numbers |
| D10 | Also report a "boundary groups only" row and per-class F1 | Removing the boundary groups changes the class mix (DoS 503,405 → 12,047), and per-class F1 is needed to read the macro-F1 change |
| D11 | Run T read in place, read-only, from `../thesis_final_validation/` (outside the repository) | Instruction: use saved predictions, do not retrain; Run T data are not committed |
| D12 | Commit only `experiments/review/` (scripts, tests, results, logs); no data, pcaps or venv | Instruction. Result files are small CSV/JSON (largest is `review_results.csv`) |

## 7. Unfavourable results (also in RESULTS.md)

- Most of the FPR increase from incident features (0.38% → about 1.0%) is present
  with **permuted** context. Only +0.07 to +0.24 pp is due to the correct link.
- Permuted context lowers macro F1 against `event_only` at 300, 600 and 900 s.
- The 600 s interval for true − permuted F1 includes 0.
- The shuffle cannot break the link for 18%–34% of events (tied values).
- In Run T, excluding boundary groups **lowers** integrated macro F1
  (0.7711 → 0.6994). The 12,047 DoS events left are all mispredicted (DoS F1 0.0),
  and FPR is unchanged.
