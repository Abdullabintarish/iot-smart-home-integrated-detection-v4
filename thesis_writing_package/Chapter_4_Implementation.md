# Chapter 4: Implementation and Experimental Design

> **Drafting notes (delete before submission).**
> - This chapter describes what was built and run. It does not describe planned or hypothetical capabilities.
> - Paths are relative to the repository root (`submission/`).
> - `[CITE: …]` marks where an external citation is needed.

## 4.1 Development Environment and Tools

**Table 4.1 — Software used** (evidence: `code/requirements.txt`; `metrics/run_manifest.json`; `experiments/RUN_LOG.md` §0, §4.1–4.2)

| Purpose | Tool and version |
|---|---|
| Language | Python 3.15.0 (64-bit) |
| Data handling | pandas 3.0.6, numpy 2.5.3, pyarrow 26.0.0 |
| Machine learning | scikit-learn 1.9.1, joblib 1.6.0 |
| Figures | matplotlib 3.11.2 |
| Packet parsing | dpkt 1.9.8 |
| Demonstration application | Streamlit 1.66.0 |
| Network sensors (cross-log experiment) | Zeek 9.0.1 (LTS) and Suricata 7.0.3 in WSL Ubuntu 24.04; Bro 2.6.4, built from source for one comparison |
| IDS ruleset | ET Open for Suricata 7.0.3; tarball SHA-256 `d5330ebe…a777b035`; 52,803 enabled rules; never edited |

**Hardware.**

- Run B: Intel i7-14700KF, 28 logical cores.
- Run C: AMD Ryzen 7 7800X3D.
- Run B full pipeline: 338.3 s, peak memory 3,819 MB (`docs/thesis_final_validation/04_Verified_Results_and_Analysis.md` §7).

## 4.2 The Python Research Pipeline

The framework is implemented as a batch pipeline in `code/`. Table 4.2 lists its modules.

**Table 4.2 — Pipeline modules**

| Module | Responsibility |
|---|---|
| `stage1_collect.py`, `pipeline/ingest.py` | Read the 13 raw files in streaming chunks, map columns to a canonical schema, map labels to the five classes, write 26 Parquet shards. Stage 1 took 20.0 s in Run B |
| `pipeline/preprocess.py` | Assign the train/test split, clean, fit the scaler and encoders on training rows, transform all rows, select features, write `data/processed/stage2_feature_plan.csv` |
| `pipeline/correlate.py` | Build correlation keys, aggregate events into incidents, compute incident features. Stage 3 took 92.2 s in Run B |
| `pipeline/detect.py` | Sample training rows, train the fragmented, integrated and diagnostic Random Forests, predict, compute metrics |
| `pipeline/evaluate.py` | Alert reduction, robustness subsets, incident-clustered bootstrap, report JSON |
| `pipeline/reporting.py`, `make_report.py` | Draw the nine report figures from `stage5_report.json` |
| `pipeline/config.py` | All constants: window (300 s), split fraction (0.25), RF settings, leakage columns, sampling budget |
| `run_pipeline.py`, `run_all.ps1` / `run_all.sh` | Run Stages 2–5, or the full sequence |

**Design choices that support validity:**

- **Streaming in chunks.** Memory stays bounded at 4.2 million events.
- **Train-only fitting.** Every learned transformation is fitted after the split, on training rows only.
- **Deterministic incident identifiers.** Each identifier is a function of the correlation key, so the result does not depend on chunk size.
- **One evaluation function.** The same function scores every model.

## 4.3 Event Correlation Implementation

`pipeline/correlate.py` assigns each event a correlation key, applying rules R1 → R2 → R3 → R0 in order:

- the key is (source, rule, IP fields of the rule, protocol, `floor(ts / 300)`);
- events with the same key form an incident;
- partial aggregates (count, first and last timestamp, distinct IPs and sources) are merged across chunks;
- incident features are computed from the merged aggregates.

**Outcome in Run B.** All 4,211,383 events matched rule R1; rules R0, R2 and R3 never fired. The result was 704,090 incidents. The same key is used for the train/test split, so no incident straddles the split (`docs/thesis_final_validation/03_Final_Experimental_Methodology.md` §5–6).

## 4.4 Random Forest Classification

`pipeline/detect.py` trains every model with the configuration in Chapter 3, §3.7.1.

| Model | Unit | Features | Training rows |
|---|---|---|---|
| Fragmented (11 RF + 2 constant) | event | 20 event | 408,412 |
| Integrated | incident → events | 7 incident | 120,825 incidents |
| Pooled event (diagnostic) | event | 20 event | 196,406 |
| Enriched event (diagnostic) | event | 20 event + 3 incident | 196,406 |

**Training samples.** These are drawn by a stratified reservoir sample of at most 60,000 rows per class. Classes with fewer rows are used in full.

**Leakage guard.** Before training, `check_features` refuses any feature list that contains an identifier, a timestamp, an IP address, the source name or a label column.

**Saved model.** The integrated model is saved as `code/models/rf_integrated.joblib`. The per-source baseline models were not saved. Only their predictions are kept (`predictions/fragmented_event_predictions.csv`).

## 4.5 Streamlit Research Demonstration

A local, read-only Streamlit application presents the verified results. It is a demonstration and evidence browser. It is not a monitoring product and does not capture or generate network traffic.

**Launch.**

- Original demo: `code/demo/app.py`; documentation in `code/demo/README_DEMO.md`.
- Combined version: `experiments/lab/app.py`, which adds two pages for the supplementary experiments.

**Table 4.3 — Application pages**

| Page | Content | Data source |
|---|---|---|
| Research Overview | Research question, design, headline results | `results/stage5_report.json` |
| Recorded Attack Replay | Steps through recorded dataset records (replay, not simulation) | Stage 1 shards |
| Event Correlation Explorer | How events are grouped into incidents | Stage 3 events |
| Random Forest Detection Comparison | Fragmented vs integrated metrics and confusion matrices. The saved integrated model is loaded read-only to show class scores for one incident and to confirm it reproduces the saved predictions | Prediction CSVs, `rf_integrated.joblib` |
| Research Evidence Explorer | Links each reported number to its source file | Report and verification files |
| Controlled Ablation | Ablation results by feature set and window | `experiments/ablation/results/full/` |
| Cross-Log Correlation | Cross-log results by condition, seed and capture | `experiments/cross_log/results/` |

**Limits of the application:**

- It retrains nothing.
- It shows baseline predictions but no baseline confidence, because those models were not saved.
- It reports the result as recorded, including that the integrated condition scored lower.

**Testing:**

- 48 demo tests (`code/demo/tests/`).
- All seven pages of the combined app rendered without exceptions under Streamlit's `AppTest` (`experiments/RUN_LOG.md` §10).

[Insert Figure: screenshot of the Research Overview page, from `code/demo/screenshots/`.]

## 4.6 Main Detection Comparison (Run B) and Reproduction (Run C)

**Run B** is the cited run, executed on 2026-10-16:

- Command: `run_all.ps1 data/raw_combined`.
- Steps: Stage 1 collection, then `run_pipeline.py` (Stages 2–5), then `make_report.py`.
- Outputs: `metrics/stage5_report.json`, `metrics/baseline_vs_integrated.csv`, the three prediction CSVs in `predictions/`, and the figures in `report/`.
- Transcripts: `transcripts/`.

**Run C** (2026-10-21) repeated the procedure on a different machine:

- All prediction CSVs were byte-identical to Run B.
- Only the timing fields of the report differed.

This establishes that the primary result is reproducible from the raw data and the code (`docs/thesis_final_validation/01_Completed_Phases_Review.md`; `REPRODUCIBILITY_CHECKLIST.md`).

## 4.7 Temporal Hold-out Experiment (Run T)

Run T was implemented in a copy of the code (`../thesis_final_validation/supplementary_temporal/code/`), so Run B could not be affected.

**Table 4.4 — Changes made for Run T** (evidence: `../thesis_final_validation/supplementary_temporal/RESULTS.md` §1)

| File | Change |
|---|---|
| `pipeline/config.py` | `SPLIT_MODE` option (`incident` default, `temporal`) |
| `pipeline/preprocess.py` | Per-source 75th-percentile time cut-offs; events after the cut-off go to test |
| `pipeline/correlate.py` | In temporal mode the split side is part of the key, so incidents never cross the cut |
| `run_pipeline.py` | `--split {incident,temporal}` |
| `tests/test_temporal_split.py` | Four new tests; 98/98 pass |

**Execution:**

- Run on 2026-11-01 by `run_temporal.sh`; it took about 10 minutes.
- The input-data hashes were identical to Run B.
- The validity checks after the run confirmed:
  - every test event is later than every training event of its source;
  - 0 incidents are mixed between train and test.

## 4.8 Controlled Ablation Experiment

**Script:** `experiments/ablation/run_ablation.py`, with unit tests in `experiments/ablation/tests/test_ablation.py` (6 tests).

**Reuse of the Run B data.** The script reads the Run B processed events (`code/data/processed/stage3_events/`) and the feature plan. It reuses the pipeline's own correlation key, event-feature list, leakage list and evaluation function. It writes only to `experiments/ablation/results/`.

**Procedure:**

1. **Quick check:** seed 42, 300 s window. The data gate passed: 704,090 groups (the Run B incident count) and 1,463,143 novel test events (the Run B value) (`experiments/ablation/results/quick_check/checks.json`).
2. **Full run:** 5 feature sets × up to 5 windows × 5 seeds, plus paired bootstraps. It took 26.7 minutes (`experiments/ablation/results/full/checks.json`, `run.log`).

**Control of confounds:**

- Within a seed, every feature set uses the same sampled training events and the same test events.
- Only the input columns change.
- Incidents are built inside each partition, so the test events and their labels never change.

## 4.9 Cross-Log Correlation Experiment

All code is in `experiments/cross_log/`, and every command, version, hash and decision is recorded in `experiments/RUN_LOG.md`.

**Table 4.5 — Cross-log components**

| Component | File | Function |
|---|---|---|
| Sensor run | `tools/run_sensors.sh` | Runs Zeek (with Community ID) and Suricata on one pcap; refuses to run if the ruleset hash changed; records tool versions per capture |
| pcap repair | `src/trim_pcap.py` | Writes a byte-exact prefix of complete records for a truncated pcap (42-1, 48-1, 49-1); the original is unchanged |
| Community ID | `src/community_id.py` | Community ID v1 computed for IoT-23 labelled rows, unit-tested against reference values |
| Log readers | `src/zeek_io.py` | Read Zeek TSV logs and Suricata `eve.json` |
| Label transfer | `src/label_match.py` | Community ID plus start time within 1.0 s, one-to-one |
| Linking | `src/linking.py` | Community ID groups, then local host plus 300 s window |
| Features | `src/features.py`, `src/build_feature_cache.py` | Causal DNS and alert context in [ts − w, ts] |
| Experiment | `src/experiment.py`, `src/run_stage3.py`, `src/run_stage4.py` | Stage 3 gate per capture; Stage 4 conditions A–D, seeds, metrics, bootstrap |
| Robustness | `src/robustness.py` | R0–R5 |
| Tests | `tests/` | 14 tests (Community ID, pipeline, pcap trimming, timestamp regression) |

**Execution sequence:**

1. **Pilot gate checks, in a fixed order** (8-1 → 42-1 → 20-1):
   - 8-1 failed the gate: it has no DNS and no alerts, so no incident contains two log types.
   - 42-1 failed at first because its pcap was truncated; it was repaired and processed later.
   - 20-1 passed (`experiments/RUN_LOG.md` §4.4).
2. **Stage 3** on all seven design captures. Label-match rates were 0.9998–1.0000. In capture 34-1, however, only 38.8% of the IoT-23 labelled rows have a counterpart: IoT-23's log records one DDoS flood flow as 14,159 one-packet rows. Bro 2.6.4 and Zeek 9.0.1 both write the same 8,990 records, so the difference is not caused by the Zeek version (`experiments/RUN_LOG.md` §4.5–4.6; `experiments/cross_log/results/old_zeek_check_34-1.json`).
3. **Stage 4**, with the design fixed in `experiments/PLAN.md` §4.
4. **Robustness analyses R0–R5.** For R3, capture 48-1 was added because it passed the gate. Capture 49-1 was excluded because its match rate was 0.8984, below the 90% threshold fixed in advance.

**Defect found and corrected.** During the robustness runs, every alert feature was found to be zero:

- **Cause:** pandas 3 parses Suricata timestamps at microsecond resolution, but the reader assumed nanoseconds. Alert times were therefore 1,000 times too small.
- **Fix:** time conversion independent of resolution, plus a regression test (`experiments/cross_log/tests/test_zeek_io.py`).
- **Rerun:** Stage 3, Stage 4 and R0–R5 were all rerun with the unchanged design.
- **Archive:** the superseded outputs are kept in `experiments/cross_log/results/superseded_2026-11-03_alert_timestamp_bug/` with a README (`experiments/RUN_LOG.md` §5.1).
- **Unaffected:** the label matching, the DNS features, the ablation and Runs B, C and T.

## 4.10 Test and Integrity Summary

| Suite | Tests | Result | Evidence |
|---|---|---|---|
| Thesis pipeline | 94 | OK | `code/tests/`; `experiments/RUN_LOG.md` §8 |
| Run T copy | 98 | OK | `../thesis_final_validation/supplementary_temporal/RESULTS.md` |
| Demonstration app | 48 | OK | `code/demo/tests/` |
| Ablation | 6 | OK | `experiments/ablation/tests/` |
| Cross-log | 14 | OK | `experiments/cross_log/tests/` |
| Integrity of existing work | 30,615 files | 0 differences | `experiments/_integrity/diff.txt` |
