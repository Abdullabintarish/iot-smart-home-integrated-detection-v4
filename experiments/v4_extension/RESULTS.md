# v4 extension — results

Two experiments that extend the thesis, run 2026-11-16 UTC on the existing data only. Every
number comes from the file named under its table. Commands, versions, seeds and deviations
are in `RUN_LOG.md`, and the feature definitions are in `FEATURES.md`.

Comparability with the Run B ablation was checked before anything else ran:
- **Gate:** seed 42 `incident_thin`, `event_only` and `event_plus_thin` reproduced
  `experiments/ablation/results/full/ablation_results.csv` exactly. Afterwards, all 75
  compared rows (3 conditions × 5 seeds × 5 subsets) matched at tolerance 1e-12
  (`results/e1/runb_checks.json`).
- **LOSO baseline:** `event_only` matches v3 `rf_event_only` in all 65 fold × seed runs
  (`results/e1/loso/loso_stats.json`).

Abbreviations:
- **F1:** macro F1 over the five classes.
- **FPR:** benign events predicted as any attack class / benign events.
- **FNR:** attack events predicted benign / attack events.
- **MEB FPR:** FPR on benign test events whose 300 s group has more than one event (16,428 events).
- **Novel FPR:** FPR on test events whose 20-feature event vector never occurs in training
  (1,463,143 events; same definition as the ablation).

---

## E1 — Richer incident summaries

**Setup.**
- **Data and model:** same Run B split, 1,692,332 test events, 196,406 training events per seed,
  RF with 300 trees and depth 24, seeds 42, 1, 2, 3, 4.
- **Rich features:** 77 label-free group summaries computed within each partition
  (`FEATURES.md`).

### E1a. All conditions at 300 s (mean ± SD over 5 seeds)

| Condition | Features | Macro F1 | Accuracy | FPR | FNR | MEB FPR | Novel FPR |
|---|---|---|---|---|---|---|---|
| incident_thin | 3 | 0.8566 ± 0.0035 | 0.9886 | 9.16% ± 0.03% | 0.429% | 68.45% | 68.59% |
| incident_rich | 77 | **0.9816 ± 0.0006** | 0.9928 | **8.84% ± 0.01%** | 0.075% | 64.42% | 65.86% |
| event_only | 20 | 0.9952 ± 0.0012 | 0.9996 | 0.38% ± 0.05% | 0.012% | 2.59% | 2.81% |
| event_plus_thin | 23 | 0.9964 ± 0.0003 | 0.9991 | 1.14% ± 0.02% | 0.010% | 8.12% | 8.41% |
| event_plus_rich | 97 | 0.9952 ± 0.0002 | 0.9988 | 1.44% ± 0.01% | 0.011% | 10.38% | 10.71% |
| event_plus_rich_permuted | 97 | 0.9785 ± 0.0022 | 0.9983 | 1.73% ± 0.01% | 0.012% | 12.22% | 12.71% |

Source: `results/e1/runb_summary.csv` (subsets `all`, `multi_event_benign`, `novel_vector`; SDs for
every column are in the file). Per-run rows: `runb_results.csv`. Predictions:
`results/e1/preds/runb_w300_<condition>_s<seed>.parquet`, row order in `runb_test_rows.parquet`.
The three reproduced conditions equal the ablation (incident_only / event_only / event_plus_incident).

**Note on 76.33%.** The 76.33% quoted in the brief is the MEB FPR of the Run B **integrated
model** (`predictions/integrated_event_predictions.csv`; recomputed in `results/e2/checks.json`).
The thin three-feature RF in the ablation (`incident_thin` here) has 68.45%. Both are reported.

### E1b. Per-class F1 at 300 s (mean over 5 seeds)

| Condition | benign | c2 | dos | malware | recon |
|---|---|---|---|---|---|
| incident_thin | 0.9254 | 0.8136 | 0.9999 | 0.5724 | 0.9719 |
| incident_rich | 0.9490 | 0.9934 | 1.0000 | 0.9848 | 0.9810 |
| event_only | 0.9974 | 0.9794 | 1.0000 | 1.0000 | 0.9991 |
| event_plus_thin | 0.9936 | 0.9938 | 1.0000 | 0.9970 | 0.9975 |
| event_plus_rich | 0.9921 | 0.9950 | 1.0000 | 0.9923 | 0.9968 |
| event_plus_rich_permuted | 0.9905 | 0.9081 | 1.0000 | 0.9980 | 0.9958 |

Source: `results/e1/runb_per_class_summary.csv` (SD and support included; per seed in `runb_per_class.csv`).

### E1c. Incident-clustered paired bootstrap (seed 42, 1,000 replicates, bootstrap seed 42, clusters = Run B incident_id)

| Difference | ΔF1 (point) | ΔF1 95% interval | ΔFPR (point) | ΔFPR 95% interval |
|---|---|---|---|---|
| incident_rich − incident_thin | +0.1243 | [+0.0945, +0.1612] | −0.31 pp | [−0.62, −0.03] pp |
| incident_rich − event_only | −0.0132 | [−0.0173, −0.0094] | +8.41 pp | [+8.12, +8.70] pp |
| event_plus_rich − event_only | +0.0001 | [−0.0035, +0.0036] | +1.01 pp | [+0.90, +1.13] pp |
| event_plus_rich − event_plus_rich_permuted | +0.0126 | [+0.0081, +0.0195] | −0.28 pp | [−0.33, −0.23] pp |

Source: `results/e1/runb_bootstrap.json`. pp = percentage points.

### E1d. Window sensitivity (5 seeds)

| Window (s) | Condition | Macro F1 | FPR | MEB FPR | Novel FPR |
|---|---|---|---|---|---|
| 60 | incident_rich | 0.9807 ± 0.0004 | 8.84% ± 0.01% | 81.64% | 65.87% |
| 300 | incident_rich | 0.9816 ± 0.0006 | 8.84% ± 0.01% | 64.42% | 65.86% |
| 900 | incident_rich | 0.9812 ± 0.0009 | 8.84% ± 0.01% | 63.40% | 65.83% |
| 60 | event_plus_rich | 0.9952 ± 0.0002 | 1.43% ± 0.01% | 13.14% | 10.65% |
| 300 | event_plus_rich | 0.9952 ± 0.0002 | 1.44% ± 0.01% | 10.38% | 10.71% |
| 900 | event_plus_rich | 0.9955 ± 0.0004 | 1.44% ± 0.01% | 10.19% | 10.68% |

Source: `results/e1/runb_summary.csv`. The MEB subset depends on the window (12,125 / 16,428 / 16,725 events).
The 900 s groups are cut at the Run B partition boundary, as in the ablation.

### E1e. Leave-one-source-out (RF, 300 s, 5 seeds; seed-mean per held-out source)

| Held-out source | F1 event_only | F1 incident_rich | F1 event_plus_rich | FPR event_only | FPR incident_rich | FPR event_plus_rich |
|---|---|---|---|---|---|---|
| CTU-Honeypot-Capture-4-1 | 0.4661 | 0.2885 | 0.4320 | 0.27% | 16.42% | 0.71% |
| CTU-Honeypot-Capture-5-1 | 0.2320 | 0.2362 | 0.2382 | 13.38% | 10.45% | 9.01% |
| CTU-IoT-Malware-Capture-1-1 | 0.3930 | 0.4701 | 0.4728 | 8.95% | 9.07% | 9.16% |
| CTU-IoT-Malware-Capture-20-1 | 0.8036 | 0.9332 | 1.0000 | 0.00% | 0.09% | 0.00% |
| CTU-IoT-Malware-Capture-21-1 | 0.5553 | 0.9332 | 1.0000 | 0.00% | 0.10% | 0.00% |
| CTU-IoT-Malware-Capture-3-1 | 0.3959 | 0.3832 | 0.2684 | 56.86% | 50.79% | 56.59% |
| CTU-IoT-Malware-Capture-34-1 | 0.0302 | 0.0701 | 0.1169 | 4.87% | 2.95% | 3.39% |
| CTU-IoT-Malware-Capture-42-1 | 0.2517 | 0.1791 | 0.1786 | 34.17% | 44.11% | 44.36% |
| CTU-IoT-Malware-Capture-44-1 | 0.3004 | 0.4438 | 0.4119 | 0.47% | 0.66% | 0.47% |
| CTU-IoT-Malware-Capture-8-1 | 0.3469 | 0.6666 | 0.6666 | 0.00% | 0.00% | 0.00% |
| data_1 | 0.0189 | 0.1660 | 0.1652 | 86.62% | 22.12% | 50.95% |
| data_10 | 0.5689 | 0.5777 | 0.5662 | 10.00% | 6.00% | 2.67% |
| data_36 | 0.4743 | 0.8690 | 0.8111 | 6.45% | 0.00% | 0.00% |
| **Mean** | **0.3721** | **0.4782** | **0.4868** | **17.08%** | **12.52%** | **13.64%** |

| Comparison (13 sources) | Mean Δ | Sources +/− | Sign-flip p | Holm p |
|---|---|---|---|---|
| F1: incident_rich − event_only | +0.1061 | 10 / 3 | 0.0481 | 0.0649 |
| F1: event_plus_rich − event_only | +0.1147 | 9 / 4 | 0.0325 | 0.0649 |
| FPR: incident_rich − event_only | −4.56 pp | 6 / 6 (1 tie) | 0.5859 | 0.5859 |
| FPR: event_plus_rich − event_only | −3.44 pp | 3 / 6 (4 ties) | 0.2773 | 0.5547 |

Source: `results/e1/loso/loso_per_source.csv`, `loso_stats.json` (exact two-sided sign-flip, Holm over the two
comparisons per metric; same functions as `experiments/v3/stats_v3.py`). Per run: `loso_results.csv`. Predictions:
`loso/preds/`. Macro F1 in LOSO is averaged over the classes present in true or predicted labels, so it is
low when a held-out source has one or two classes.

### E1f. Top-20 importances for incident_rich (300 s)

These are **RF impurity (MDI) importances**, mean ± SD over the 5 seeds. Permutation importance
was not used: it would need 77 features × repeated predictions on 1.69 M events. MDI favours
continuous, high-cardinality features.

| # | Feature | Importance | # | Feature | Importance |
|---|---|---|---|---|---|
| 1 | duration_sum | 0.0670 ± 0.0063 | 11 | conn_state_share_10 | 0.0357 ± 0.0042 |
| 2 | duration_median | 0.0640 ± 0.0041 | 12 | proto_share_4 | 0.0354 ± 0.0038 |
| 3 | n_distinct_src_port | 0.0535 ± 0.0040 | 13 | duration_max | 0.0350 ± 0.0040 |
| 4 | n_events | 0.0527 ± 0.0040 | 14 | bytes_sum | 0.0324 ± 0.0004 |
| 5 | app_share_6 | 0.0502 ± 0.0031 | 15 | duration_min | 0.0292 ± 0.0018 |
| 6 | bwd_pkts_mean | 0.0495 ± 0.0029 | 16 | bwd_pkts_sum | 0.0290 ± 0.0041 |
| 7 | bwd_pkts_median | 0.0467 ± 0.0058 | 17 | flgs_share_10 | 0.0258 ± 0.0038 |
| 8 | events_per_s | 0.0458 ± 0.0063 | 18 | bwd_pkts_max | 0.0219 ± 0.0031 |
| 9 | duration_mean | 0.0457 ± 0.0048 | 19 | bwd_pkts_min | 0.0208 ± 0.0036 |
| 10 | span_s | 0.0452 ± 0.0029 | 20 | proto_share_5 | 0.0197 ± 0.0022 |

Source: `results/e1/importance_incident_rich_top20.csv` (all features and seeds: `importance_incident_rich_all.csv`).

---

## E2 — Detect first, correlate afterwards (alert-workload **proxy**)

All of E2 is a **proxy for analyst workload**: it counts alerts. No analyst was involved, and
grouping is retrospective and offline.

**Inputs.** Saved predictions on the same 1,692,332 Run B test events, with no retraining:
- `predictions/fragmented_event_predictions.csv` (A, C) and `predictions/integrated_event_predictions.csv` (B).
- As a second event-level source, the seed-42 ablation predictions regenerated in E1, which
  reproduce the ablation exactly (`event_only`, `event_plus_thin`).

**Ground truth.** An attack incident is a Run B incident with at least one attack event: 64,243 of
175,489 test incidents. It is *detected* if at least one of its attack events is inside an alert.

**Delays.** Measured from the first attack event of a true incident to its first alert:
- **A:** time of the first alerted attack event.
- **B:** time of the incident's last event (the incident summary needs the finished group).
- **C open:** the alert group opens at its first member. This equals A by construction (checked).
- **C closed:** time of the alert group's last member event.

The closed delays use later records. They are retrospective, not online latencies.

### E2a. Designs on the fragmented baseline's event decisions

| Design | Alerts to review | False-alarm alerts (share) | Attack incidents detected / missed | Event macro F1 | Event FPR | Delay median / p90 (s) |
|---|---|---|---|---|---|---|
| A — one alert per predicted-attack event | 1,569,860 | 566 (0.04%) | 64,221 / 22 | 0.9955 | 0.46% | 0.0 / 0.0 |
| B — integrated, one alert per predicted-attack incident | **62,543** | 3,661 (5.85%) | 58,882 / **5,361** | 0.8341 | 10.21% | 15.03 / 15.04 (closed) |
| C — detect then correlate, 60 s | 76,772 | 482 (0.63%) | 64,221 / 22 | 0.9955 | 0.46% | 0.0 / 0.0 open; 15.03 / 15.04 closed |
| C — detect then correlate, 300 s | **64,700** | 479 (0.74%) | 64,221 / 22 | 0.9955 | 0.46% | 0.0 / 0.0 open; 15.03 / 15.04 closed |
| C — detect then correlate, 900 s | 64,152 | 479 (0.75%) | 64,221 / 22 | 0.9955 | 0.46% | 0.0 / 0.0 open; 15.03 / 15.04 closed |

### E2b. Same designs on the ablation's seed-42 event predictions

| Design | Alerts | False-alarm alerts (share) | Detected / missed | Event macro F1 | Event FPR |
|---|---|---|---|---|---|
| A — event_only | 1,569,867 | 517 (0.03%) | 64,215 / 28 | 0.9949 | 0.42% |
| C — event_only, 60 / 300 / 900 s | 76,586 / 64,494 / 63,946 | 306 / 279 / 279 | 64,215 / 28 | 0.9949 | 0.42% |
| A — event_plus_thin | 1,570,716 | 1,386 (0.09%) | 64,191 / 52 | 0.9964 | 1.13% |
| C — event_plus_thin, 60 / 300 / 900 s | 76,841 / 64,698 / 64,147 | 586 / 507 / 503 | 64,191 / 52 | 0.9964 | 1.13% |

Source for E2a and E2b: `results/e2/alert_workload.csv` (all rows, including p90 and max delays and alerted-event counts).

**Checks** (`results/e2/checks.json`):
- C's event macro F1, FPR, FNR and accuracy equal A's for all three prediction sources.
- C-open delays equal A's.
- The integrated prediction is constant within every incident.

Per-event predictions with labels and timestamps are in `results/e2/e2_events.parquet`.
The alert-group ids are rebuilt by `run_alert_workload.py` and are not committed (about 65 MB).

**Why the closed delay is about 15 s at every window.** Most attack incidents are 2–3 connection attempts
spaced 7 s or 15 s apart (median span 15.03 s; 32,313 of 64,243 incidents span 15.03 s; median 3 events).
A group alert that waits for its last event therefore arrives about 15 s after the first attack event,
whatever the window.

Figures (300 dpi):
- `results/figures/e1_f1_fpr_by_condition.png` (the F1 axis starts at 0.80)
- `results/figures/e2_alerts_by_design.png` (alert axis is logarithmic)

---

## What changed and what did not (plain English)

- **Richer incident summaries recover most of the lost detection, but not the false alarms.**
  - Incident-only macro F1 rises from 0.857 to 0.982 (+0.124, interval excludes 0). Malware and
    c2 F1 rise the most (0.57 → 0.98 and 0.81 → 0.99).
  - FPR barely moves: 9.16% → 8.84%. False alarms on benign events in multi-event groups stay
    near 64%, and on novel vectors near 66%.
  - Incident summaries alone are still clearly worse than event features alone: F1 −0.013 and
    FPR +8.4 pp, both intervals exclude 0.
- **Adding rich summaries to event features does not improve the event detector.**
  - Macro F1 is unchanged (0.9952 vs 0.9952; interval [−0.0035, +0.0036]).
  - FPR rises from 0.38% to 1.44% (+1.0 pp, interval excludes 0). This is worse than adding the
    thin summary (1.14%).
  - Shuffling the rich rows lowers F1 to 0.9785 (c2 F1 0.91). So the model does use the correct
    incident link, but the link does not add anything beyond the event features.
- **Window length (60 / 300 / 900 s) changes almost nothing** for either condition, except the MEB
  subset itself.
- **Across sources (leave-one-source-out) all models transfer poorly.**
  - Mean macro F1 is 0.37–0.49.
  - Rich summaries raise mean F1 by about 0.11 over event features. The raw sign-flip p-values
    are 0.048 and 0.032, but neither survives Holm correction (both 0.065).
  - The FPR differences are not significant. They are driven by a few sources: data_1 falls from
    87% to 22–51%, while Honeypot-4 rises to 16% for incident-only.
- **Detect-then-correlate gives the alert reduction without losing event accuracy, on this
  proxy.**
  - At 300 s, C reduces the fragmented baseline's 1,569,860 alerts to 64,700 (−95.9%). That is
    3% more alerts than the integrated design's 62,543.
  - C keeps the fragmented baseline's event-level F1 (0.9955) and FPR (0.46%).
  - C misses 22 attack incidents instead of 5,361.
  - C has 479 false-alarm alerts instead of 3,661.
  - Alerts that close a group still arrive about 15 s after the first attack event.

## Limitations

- **Same lab captures.** All data come from the IoT-23 and Bot-IoT captures used throughout the thesis.
  No new network, devices or attacks were tested.
- **Within-capture split.** The Run B split interleaves train and test inside each capture, so the
  Run B numbers are optimistic. LOSO shows how much worse transfer to an unseen source is.
- **Offline grouping.** Incident features and alert groups are built after the fact from complete
  records. The closed delays use records that would not be available at alert time in a live system.
- **Proxy, not workload.** E2 counts alerts. It does not measure the time or effort of real analysts,
  alert triage quality, or how analysts would treat grouped alerts.
- **No independent distributed sensors.** Every group is within one source capture (one log type per
  capture). Correlation across independent sensors or log types is not tested here.
- **Other limits.**
  - Five seeds; the bootstrap uses seed 42 only.
  - MDI importances, not permutation.
  - Two rich features (`n_distinct_dst_ip`, `n_distinct_proto`) are constant in this data.
  - Absent-field codes were inferred (`FEATURES.md`).
