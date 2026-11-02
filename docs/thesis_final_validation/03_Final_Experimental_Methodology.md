# 03 — Final Experimental Methodology (as executed)

This describes the method exactly as it produced Run B (2026-10-16). Run C (2026-10-21) reproduced it. Code references are to `submission/code/`, and abbreviations are as in 01 §1. Nothing here is a proposed change.

## 1. Design

A controlled comparison of two monitoring conditions on **one** held-out set of events:

- **Fragmented baseline:** each source is monitored in isolation. There is one Random Forest per source, trained on that source's event (flow) features.
- **Integrated condition:** all sources are normalised into one schema (Stage 2) and events are correlated into incidents (Stage 3). One Random Forest is trained on incident features. Each test incident's prediction is assigned to every one of its test events.

Both conditions use the same RF configuration, the same test events and the same metric code. Diagnostic models (pooled event model, enriched event model) are scored on the same events but are **not** thesis conditions.

## 2. Datasets and capture inventory

Unit of "source" = one capture file. Each flow record = one security event (alert). Events and incidents are from VR V11 and R `alert_reduction_by_dataset.per_source`; test shares are from VR V5.

| Source | Dataset | Raw file (bytes) | Events | Classes (events) | Incidents | Alert reduction | Test share of events |
|---|---|---|---|---|---|---|---|
| CTU-Honeypot-Capture-4-1 | IoT-23 | 61,653 | 452 | benign 452 | 339 | 25.00% | 29.0% |
| CTU-Honeypot-Capture-5-1 | IoT-23 | 182,147 | 1,374 | benign 1,374 | 705 | 48.69% | 28.4% |
| CTU-IoT-Malware-Capture-1-1 | IoT-23 | 148,305,428 | 1,008,748 | benign 469,275; recon 539,465; c2 8 | 627,108 | 37.83% | 25.0% |
| CTU-IoT-Malware-Capture-3-1 | IoT-23 | 24,383,537 | 156,103 | recon 145,597; malware 5,962; benign 4,536; c2 8 | 67,899 | 56.50% | 24.6% |
| CTU-IoT-Malware-Capture-8-1 | IoT-23 | 1,431,000 | 10,403 | c2 8,222; benign 2,181 | 1,558 | 85.02% | 25.3% |
| CTU-IoT-Malware-Capture-20-1 | IoT-23 | 419,604 | 3,209 | benign 3,193; c2 16 | 1,109 | 65.44% | 25.4% |
| CTU-IoT-Malware-Capture-21-1 | IoT-23 | 428,943 | 3,286 | benign 3,272; c2 14 | 1,102 | 66.46% | 30.6% |
| CTU-IoT-Malware-Capture-34-1 | IoT-23 | 2,926,718 | 23,145 | dos 14,394; c2 6,706; benign 1,923; recon 122 | 1,005 | 95.66% | 7.5% |
| CTU-IoT-Malware-Capture-42-1 | IoT-23 | 585,829 | 4,426 | benign 4,420; c2 3; malware 3 | 518 | 88.30% | 24.2% |
| CTU-IoT-Malware-Capture-44-1 | IoT-23 | 31,179 | 237 | benign 211; c2 25; dos 1 | 128 | 45.99% | 22.4% |
| data_1 | Bot-IoT | 218,326,470 | 1,000,000 | recon 998,007; benign 1,993 | 2,564 | 99.74% | 14.3% |
| data_10 | Bot-IoT | 203,190,430 | 1,000,000 | dos 999,970; benign 30 | 32 | 99.997% | 49.8% |
| data_36 | Bot-IoT | 208,600,538 | 1,000,000 | dos 999,969; benign 31 | 23 | 99.998% | 75.3% |
| **Total** | | | **4,211,383** | benign 492,891; recon 1,683,191; dos 2,014,334; c2 15,002; malware 5,965 | **704,090** | **83.28%** | **40.2%** |

**Provenance:**
- IoT-23 conn logs are from `https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset/IndividualScenarios/<capture>/bro/conn.log.labeled`.
- The Bot-IoT files are from the Kaggle redistribution `vigneshvenkateswaran/bot-iot`.
- SHA-256 hashes of all 13 files are in M `datasets` and are identical in Runs B and C.

**Log types:** one per dataset. IoT-23 uses Zeek connection logs; Bot-IoT uses Argus flow records (CSV). No pcap, DNS, HTTP or IDS-alert log was processed.

**Label mapping** (`pipeline/ingest.py`):
- **IoT-23 detailed labels:** `C&C*` → c2, `DDoS` → dos, `PartOfAHorizontalPortScan` → recon, and `Okiru`/`FileDownload`/`Attack` → malware (lines 158–167, 480–511). Record-level labels take precedence over the filename.
- **Bot-IoT:** the `category` column, with DoS and DDoS → dos, Reconnaissance → recon and Normal → benign (lines 322–338).
- **Classes evaluated:** benign, c2, dos, malware, recon. The classes botnet, bruteforce and theft are in the vocabulary but occur in no event.

## 3. Pipeline stages

| Stage | Code | What it does |
|---|---|---|
| 1 Collection | `stage1_collect.py`, `pipeline/ingest.py` | Streams the 13 files into 26 Parquet shards with a canonical schema, keeping `source` = capture name (20.0 s in Run B) |
| 2 Preprocessing | `pipeline/preprocess.py` | Split assignment → clean → fit on train rows → transform all rows (§4, §5) |
| 3 Correlation | `pipeline/correlate.py` | Events → incidents (§6) (92.2 s in Run B) |
| 4 Detection | `pipeline/detect.py` | Trains and scores both conditions and the diagnostics (§7) |
| 5 Evaluation | `pipeline/evaluate.py`, `run_pipeline.py` | Comparison table, alert reduction, robustness checks, clustered bootstrap (§8) |

## 4. Preprocessing and features

**Order of operations:**
1. Assign the split on raw rows (§5).
2. Drop all-empty rows, then exact duplicate rows within a chunk (none found).
3. Drop identifier/noise columns and 14 leakage columns (`config.py:98`): `ts_first`, `ts_last`, `ts_end`, `attack`, `pkSeqID`, `seq`, `smac`, `dmac`, `soui`, `doui`, `sco`, `dco`, `category`, `subcategory`.
4. Learn on train rows only:
   - column role (numeric if ≥ 90% of non-null values parse);
   - global min/max;
   - categorical vocabularies;
   - moment matrices.
5. Transform:
   - **numeric columns:** MinMax with the train range, so test values may fall outside [0, 1]; missing values become -1;
   - **categorical columns:** label-encoded, with values unseen in training mapped to -1.

**Feature selection** (`FEATURE_SELECTION = "redundancy"`): constant features are dropped. A numeric feature is also dropped if |Pearson r| ≥ 0.95 with a feature already kept, processing features in order of fewest missing values first, then by name. Labels are not used.
- **Result:** 26 candidates → **20 kept**.
- **Dropped as redundant:** `fwd_bytes` (with `bytes`, r = 0.9943), `bwd_bytes` (with `bwd_pkts`, 0.9963), `fwd_pkts` (with `bytes`, 0.9946), `fwd_ip_bytes` (with `bytes`, 1.0000), `pkts` (with `bytes`, 0.9949) and `mean` (with `max`, 0.9773).

**Event features (20)** (FP; R `fragmented.features`):
`sport, dport, proto, app, duration, conn_state, missed_bytes, history, bwd_pkts, bwd_ip_bytes, bytes, flgs, state, stddev, sum, min, max, rate, srate, drate`
- Zeek-only: `app`, `conn_state`, `missed_bytes`, `history`, `bwd_ip_bytes`.
- Argus-only: `flgs`, `state`, `stddev`, `sum`, `min`, `max`, `rate`, `srate`, `drate`.
- Shared by both: `sport`, `dport`, `proto`, `duration`, `bwd_pkts`, `bytes`.

**Incident features (7)** (`correlate.py:54`):

| Feature | Definition | Distinct values in train |
|---|---|---|
| `n_events` | events in the incident | 292 |
| `span_s` | last − first timestamp (bounded by the 300 s window) | 27,274 |
| `events_per_s` | n_events / span_s (0 if span = 0) | 27,377 |
| `n_sources` | distinct sources | **1 (constant)** |
| `n_src_ips` | distinct source IPs | **1 (constant)** |
| `n_dst_ips` | distinct destination IPs | **1 (constant)** |
| `cross_source` | equals `n_sources` | **1 (constant)** |

The four constants follow from the design: rule R1 keys on one (src IP, dst IP) pair, and the correlation scope keys on one source (VR V4).

**Excluded from all models:** `ts`, `src_ip`, `dst_ip`, `source`, `incident_id`, `corr_rule`, `split`, `label`, `is_attack`, `event_id` (`detect.py:44`, enforced by `check_features`). Label statistics (`label_entropy`, `label_purity`, `n_labels`, `label_counts`) exist only in the diagnostics table.

## 5. Training/testing split

- **What is hashed:** the Stage 3 correlation-group key (source, rule, src IP, dst IP, protocol, floor(ts / 300)) is hashed with blake2b. Groups whose hash falls below 0.25 × 2⁶⁴ go to **test** (`preprocess.py:94-124`, `config.py:123`). The same key defines incidents, so no incident is on both sides (0 mixed).
- **Result:**

| | Train | Test |
|---|---|---|
| Incidents | 528,601 | 175,489 |
| Events | 2,519,051 | 1,692,332 |

- **Test events by class:** benign 122,807; c2 3,283; dos 1,250,540; malware 1,278; recon 314,424.
- **Test incidents by class:** benign 111,257; recon 63,980; c2 174; malware 65; dos 13.
- **What the split is not:** it is neither a capture-level nor a temporal split. Train and test are interleaved in time inside every capture (VR V5).

## 6. Event correlation

Rules, applied in order with the first applicable rule winning (`correlate.py:96-131`):
- **R1:** (src IP, dst IP, protocol)
- **R2:** (src IP, protocol)
- **R3:** (dst IP, protocol)
- **R0:** singleton (no timestamp, or no IP at all)

Matching settings:
- **Window:** a tumbling 300 s window (`floor(ts / 300)`).
- **Scope:** `source`, so the capture name is part of the key.
- **Missing or unseen protocol:** keyed as "unknown".

**Outcome:** all 4,211,383 events matched rule R1. R0, R2 and R3 never fired (VR V8). There are 704,090 incidents, and alert reduction = 1 − incidents / events = 83.28%.

Incident ids are a pure function of the key, and partial aggregates are merged across chunks. The result therefore does not depend on chunk size (unit-tested in `tests/test_correlate.py`).

## 7. Models

Shared Random Forest configuration (R `model_config`, `detect.py:149-158`): 300 trees, max_depth 24, min_samples_leaf 2, `class_weight = balanced_subsample`, bootstrap, `random_state = 42`. There was no hyperparameter search.

**Training samples:** a stratified reservoir sample of at most 60,000 rows per class, drawn from train rows only.

| Model | Role | Unit | Features | Training rows |
|---|---|---|---|---|
| Fragmented | Condition (baseline) | event | 20 event | 408,412 events across 13 per-source models (11 RF; Capture-4-1 and 5-1 are single-class → constant "benign") |
| Integrated | Condition (proposed) | incident → events | 7 incident | 120,825 incidents (benign 60,000; recon 60,000; c2 561; malware 238; dos 26) |
| Pooled event model | Diagnostic | event | 20 event | 196,406 events |
| Enriched event model | Diagnostic | event | 20 event + incident `n_events`, `span_s`, `events_per_s` | 196,406 events |

**Cross-validation:** 5 folds on training data only, used as a robustness estimate and not for model selection.
- **Fragmented:** per-source `StratifiedGroupKFold` with incidents as groups. This was possible for 6 of 13 sources; folds were pooled across sources.
- **Integrated:** `StratifiedKFold` over training incidents.

## 8. Metrics

All metrics are computed on the 1,692,332 test events by `detect.evaluate_split`:
- **Accuracy.**
- **Macro precision, recall and F1** over the union of true and predicted classes (5 classes for every model).
- **FPR** = benign events predicted as any attack class / benign events.
- **FNR** = attack events predicted benign / attack events.
- **Confusion matrix** with rows = true and columns = predicted, in class order benign, c2, dos, malware, recon.

Secondary measures:
- **Incident-level metrics:** one row per test incident, scored against the majority label.
- **Alert reduction:** 1 − incidents / events, overall, per dataset and per source.
- **Processing time:** step runtimes and train/predict time per condition.

Robustness:
- events in incidents of at most 10,000 events;
- one majority vote per incident;
- novel-vector-only events;
- an **incident-clustered bootstrap** (1,000 replicates, seed 42, 95% percentile interval). It is not a significance test, and it treats incidents as independent.

## 9. Reproducibility instructions

The full procedure is in `submission/README.txt` §3–6 and `submission/REPRODUCIBILITY_CHECKLIST.md`. In short:

1. **Install Python 3.15.0** (64-bit, python.org). From `submission/code/`:
   `py -3.15 -m venv .venv` → `.venv\Scripts\python.exe -m pip install -r requirements.txt`. The pinned versions are numpy 2.5.3, pandas 3.0.6, pyarrow 26.0.0, scikit-learn 1.9.1, matplotlib 3.11.2, joblib 1.6.0 and dpkt 1.9.8.
2. **Place the 13 raw files** under `data\raw_combined\` (layout in README §3), and compare their SHA-256 hashes with M `datasets`.
3. **Run the tests:** `.venv\Scripts\python.exe -m unittest discover -s tests`. Expect 94 tests, OK.
4. **Run the pipeline:** `powershell -NoProfile -ExecutionPolicy Bypass -File .\run_all.ps1 data/raw_combined`.
   - **Warning:** this first empties `data\interim`, `data\processed`, `results` and `models`.
   - It takes about 6 minutes and about 4 GB of RAM.
5. **Expected outcome:** the prediction CSVs are byte-identical to `submission/predictions/`; in `stage5_report.json` only timings differ. This was confirmed twice, on two different machines (Runs B and C).
6. **Supplementary temporal hold-out (Run T):** `bash thesis_final_validation/supplementary_temporal/run_temporal.sh`. It runs the extended copy with `--split temporal`, writes only under that folder and takes about 9 minutes. The method is in `supplementary_temporal/RESULTS.md` §1.
7. **Check this phase's evidence:** `submission\code\.venv\Scripts\python.exe -I thesis_final_validation\verification\verify_evidence.py` reproduces VR in about 2 minutes. It is read-only.
