# Chapter 3: Methodology

> **Drafting notes (delete before submission).**
> - This chapter replaces "Chapter 3: Proposed Methodology" of Thesis Part 1 (submitted 22/05/2026). It keeps Part 1's section order (3.1 Research Approach, 3.2 Framework, 3.3 Dataset Selection, 3.4 Tools and Technologies, 3.5 Evaluation Metrics) and adds the sections the final thesis needs. It is written in the past tense because it describes what was done.
> - Evidence paths are relative to the repository root (`submission/`). Paths that start with `../thesis_final_validation/` are in the sibling folder, outside the Git repository.
> - `[CITE: …]` marks where an external academic citation is needed. No reference has been invented.

## 3.1 Research Approach

This research used an experimental, quantitative approach. It examined RQ1 from Thesis Part 1 §1.3:

> **RQ1:** How does the integration and correlation of distributed IoT logs and alerts affect cybersecurity threat detection accuracy in IoT-enabled smart home networks?

As planned in Part 1 §3.1, the study compares two monitoring conditions on the same held-out data:

1. **Fragmented monitoring (baseline).** Each log source is monitored in isolation. One Random Forest is trained per source on that source's event (flow) records.
2. **Integrated monitoring (proposed framework).** All sources are normalised into one schema and correlated into incidents. One Random Forest is trained on incident-level features. Its prediction for each incident is assigned to every event in that incident.

Both conditions use the same Random Forest configuration, the same test events and the same metric code. Any difference in results can therefore be attributed to the monitoring condition, not to the classifier or the test data (evidence: `docs/thesis_final_validation/03_Final_Experimental_Methodology.md` §1).

### 3.1.1 Primary experiment and supplementary analyses

The thesis distinguishes one primary experiment from four supplementary analyses. The primary experiment answers RQ1. The supplementary analyses test whether its result holds and explain why it occurs. They do not replace it.

| ID | Analysis | Role | Question addressed | Evidence folder |
|---|---|---|---|---|
| **Run B** | Main detection comparison | **Primary** | Does integration and correlation change detection performance? | `metrics/`, `predictions/`, `report/` |
| Run C | Independent reproduction of Run B | Validation | Is Run B reproducible on different hardware? | `code/results/` (byte-identical predictions) |
| Run T | Temporal hold-out | Supplementary | Does the result hold when test data are strictly later in time? | `../thesis_final_validation/supplementary_temporal/` |
| Ablation | Controlled feature ablation | Supplementary | With everything else held constant, what does incident context change? | `experiments/ablation/results/full/` |
| Cross-log | Cross-log-type correlation (connection + DNS + IDS alerts) | Supplementary | Does correlating different *log types* help detection on unseen networks? | `experiments/cross_log/results/` |

The cross-log experiment was designed after the primary result was known. Its purpose was to address limitation L1 (no cross-log-type correlation in the primary experiment; `docs/thesis_final_validation/06_Research_Gaps_and_Limitations.md` §1). Its design was fixed in writing before any model was trained (`experiments/PLAN.md` §4).

## 3.2 Implemented Framework

The five-stage framework proposed in Part 1 §3.2 was implemented as a Python pipeline. Table 3.1 maps each Part 1 stage to its implementation.

**Table 3.1 — Part 1 framework stages and their implementation**

| Part 1 stage | Implementation | Code | Status |
|---|---|---|---|
| Stage 1: Collection of logs and alerts | 13 source files streamed into 26 Parquet shards with a canonical schema; each record keeps its source (capture) name | `code/stage1_collect.py`, `code/pipeline/ingest.py` | Implemented |
| Stage 2: Preprocessing and log normalisation | Split assignment, cleaning, train-only fitting, MinMax scaling, label encoding, redundancy-based feature selection | `code/pipeline/preprocess.py`, `code/pipeline/config.py` | Implemented |
| Stage 3: Event correlation and information integration | Rule-based grouping of events into incidents (shared IPs, protocol, 300 s window) | `code/pipeline/correlate.py` | Implemented **within** each source; see §3.5 |
| Stage 4: Threat detection and analysis | Random Forest for both monitoring conditions plus two diagnostic models | `code/pipeline/detect.py` | Implemented |
| Stage 5: Cybersecurity risk mitigation | Comparison of the two conditions, alert reduction, robustness checks, bootstrap intervals | `code/pipeline/evaluate.py`, `code/run_pipeline.py` | Implemented as **evaluation**; no response or blocking component |

## 3.3 Dataset Selection

### 3.3.1 Datasets used

As planned in Part 1 §3.3, two public IoT security datasets were used [CITE: IoT-23, Garcia, Parmisano & Erquiaga, 2020, Zenodo DOI 10.5281/zenodo.4743746] [CITE: Bot-IoT, Koroniotis et al., 2019].

- **IoT-23:** ten captures (two honeypot captures and eight malware captures). The input is the labelled Zeek connection log (`conn.log.labeled`) of each capture.
- **Bot-IoT:** three CSV files of 1,000,000 Argus flow records each (`data_1`, `data_10`, `data_36`), taken from a Kaggle redistribution.

Each capture file is treated as one distributed **source**. This reproduces the fragmented, multi-source monitoring conditions described in Part 1 §3.2, Stage 1. Each flow record is one security **event**.

**Table 3.2 — Sources, events and classes** (evidence: `docs/thesis_final_validation/03_Final_Experimental_Methodology.md` §2; `metrics/stage5_report.json`)

| Dataset | Sources | Events | Class composition (events) |
|---|---|---|---|
| IoT-23 | 10 captures (Honeypot 4-1, 5-1; Malware 1-1, 3-1, 8-1, 20-1, 21-1, 34-1, 42-1, 44-1) | 1,211,383 | benign, recon, c2, malware, dos |
| Bot-IoT | 3 files (data_1, data_10, data_36) | 3,000,000 | recon, dos, benign |
| **Total** | **13** | **4,211,383** | benign 492,891; recon 1,683,191; dos 2,014,334; c2 15,002; malware 5,965 |

The SHA-256 hashes of all 13 raw files are recorded in `metrics/run_manifest.json`. They were identical in Runs B and C.

### 3.3.2 Label mapping

Labels were mapped to five classes (`code/pipeline/ingest.py`):

- **IoT-23 detailed labels:** `C&C*` → c2; `DDoS` → dos; `PartOfAHorizontalPortScan` → recon; `Okiru`, `FileDownload` and `Attack` → malware. Record-level labels take precedence over the file name.
- **Bot-IoT `category` column:** DoS and DDoS → dos; Reconnaissance → recon; Normal → benign.

The classes botnet, brute-force and theft are in the label vocabulary, but no event in the data carries them. Part 1 §1.5 lists "botnet activity detection" in scope. In the data, botnet behaviour appears as C&C, scanning and DoS traffic, not as a separate class.

### 3.3.3 Deviation from the Part 1 dataset plan

Part 1 §3.3 described IoT-23 as 20 malicious and 3 benign captures. Only the ten captures listed above were used. They were selected because their labelled connection logs could be processed on one workstation. Larger captures (several gigabytes each) were not used. [Author to confirm and state the selection rationale in your own words.]

## 3.4 Data Preprocessing and Normalisation

Preprocessing followed Part 1 §3.2, Stage 2. To prevent information leaking from test to training data, every step was learned on **training rows only** (`code/pipeline/preprocess.py`; `docs/thesis_final_validation/03_Final_Experimental_Methodology.md` §4).

1. **Split first.** The train/test split (§3.8) was assigned on raw rows before anything was learned.
2. **Cleaning.** All-empty rows were dropped, then exact duplicate rows within a chunk. No duplicates were found.
3. **Leakage control.** Identifier and noise columns were removed, together with 14 leakage columns (`code/pipeline/config.py`): `ts_first`, `ts_last`, `ts_end`, `attack`, `pkSeqID`, `seq`, `smac`, `dmac`, `soui`, `doui`, `sco`, `dco`, `category` and `subcategory`.
4. **Learned on training rows:**
   - each column's role (numeric if at least 90% of non-null values parse);
   - global minimum and maximum of each numeric column;
   - the vocabulary of each categorical column.
5. **Transformation:**
   - **Numeric columns:** MinMax-scaled using the training range. Test values may therefore fall outside [0, 1]. Missing values become −1.
   - **Categorical columns:** label-encoded. Values not seen in training become −1.
6. **Feature selection** (`FEATURE_SELECTION = "redundancy"`):
   - Constant features were dropped.
   - A numeric feature was also dropped if |Pearson r| ≥ 0.95 with a feature already kept.
   - Labels were not used for selection.
   - Result: 26 candidates → **20 event features**: `sport, dport, proto, app, duration, conn_state, missed_bytes, history, bwd_pkts, bwd_ip_bytes, bytes, flgs, state, stddev, sum, min, max, rate, srate, drate`.

Part 1 planned "correlation analysis" for feature selection. This was implemented as the redundancy filter above, which uses correlations between features rather than correlation with the label.

## 3.5 Event Correlation Rules

Event correlation implements Part 1 §3.2, Stage 3 (`code/pipeline/correlate.py`). Events are grouped into **incidents** by rules applied in order; the first applicable rule wins:

| Rule | Key |
|---|---|
| R1 | (source IP, destination IP, protocol) |
| R2 | (source IP, protocol) |
| R3 | (destination IP, protocol) |
| R0 | singleton (no timestamp or no IP address) |

Matching settings:

- **Time window:** a tumbling 300-second window, `floor(ts / 300)`.
- **Scope:** the source (capture name) is part of the key, so an incident never spans two sources.
- **Missing protocol:** keyed as "unknown".

For each incident, seven features are computed: `n_events`, `span_s`, `events_per_s`, `n_sources`, `n_src_ips`, `n_dst_ips` and `cross_source`.

**Alert reduction** is defined as 1 − (incidents / events). Incident identifiers are a pure function of the key, and partial aggregates are merged across chunks. The result is therefore independent of chunk size (unit test `code/tests/test_correlate.py`).

**Consequence of the design.** Because R1 keys on one (source IP, destination IP) pair and the scope includes the source, four of the seven incident features (`n_sources`, `n_src_ips`, `n_dst_ips`, `cross_source`) are constant at 1. This is a property of the method, not a coding error. It is analysed in Chapter 5.

## 3.6 Fragmented Baseline

The fragmented baseline represents isolated, per-source monitoring (Part 1 §3.1):

- One Random Forest per source, trained on that source's 20 event features.
- Two honeypot captures (4-1, 5-1) contain only benign traffic. A classifier cannot be trained on one class, so these sources are assigned a constant "benign" predictor.
- Result: 11 Random Forests plus 2 constant predictors, trained on 408,412 events in total.

(Evidence: `docs/thesis_final_validation/03_Final_Experimental_Methodology.md` §7; `metrics/stage5_report.json` → `fragmented`.)

## 3.7 Integrated Incident-Level Model

The integrated condition represents the proposed framework:

- One Random Forest trained on incident features. It was trained on 120,825 training incidents: benign 60,000; recon 60,000; c2 561; malware 238; dos 26.
- Each test incident is classified, and the prediction is assigned to every event of that incident. Both conditions are therefore scored on the same events.

Two **diagnostic** models were scored on the same events. They are not thesis conditions; they help explain the result:

- **Pooled event model:** one Random Forest on the 20 event features of all sources.
- **Enriched event model:** the 20 event features plus the incident features `n_events`, `span_s` and `events_per_s`.

A **propagation ceiling** is also computed: each event receives its incident's true majority label. This is the best score any incident-level classifier could reach (`../thesis_final_validation/verification/verification_results.json`).

### 3.7.1 Shared Random Forest configuration

All models use the same scikit-learn Random Forest configuration (`code/pipeline/detect.py`; `metrics/stage5_report.json` → `model_config`):

| Parameter | Value |
|---|---|
| Trees | 300 |
| Maximum depth | 24 |
| Minimum samples per leaf | 2 |
| Class weight | `balanced_subsample` |
| Bootstrap | yes |
| Random state | 42 |
| Training sample | stratified reservoir sample, at most 60,000 rows per class, from training rows only |

No hyperparameter search was performed. Random Forest was chosen as planned in Part 1 §3.2, Stage 4 [CITE: Breiman, 2001].

**Features excluded from all models:** `ts`, `src_ip`, `dst_ip`, `source`, `incident_id`, `corr_rule`, `split`, `label`, `is_attack` and `event_id`. This is enforced in code by `check_features` in `code/pipeline/detect.py`.

## 3.8 Train/Test Splitting

Part 1 §3.2 planned stratified cross-validation. Events from the same incident are strongly related, so a random event-level split would place related events on both sides. The final design therefore used a **grouped split**:

- The Stage 3 correlation key (source, rule, source IP, destination IP, protocol, `floor(ts/300)`) is hashed with BLAKE2b.
- Groups whose hash falls below 0.25 × 2⁶⁴ go to **test** (`code/pipeline/preprocess.py`; `code/pipeline/config.py`).
- Because the same key defines incidents, no incident has events on both sides (0 mixed incidents).

**Table 3.3 — Split sizes (Run B)**

| | Train | Test |
|---|---|---|
| Incidents | 528,601 | 175,489 |
| Events | 2,519,051 | 1,692,332 |

**Test events by class:** benign 122,807; c2 3,283; dos 1,250,540; malware 1,278; recon 314,424.

Five-fold cross-validation on training data was used only as a robustness estimate, not for model selection:

- **Fragmented:** per-source `StratifiedGroupKFold` with incidents as groups.
- **Integrated:** `StratifiedKFold` over training incidents.

**What the split is not.** It is neither a capture-level nor a temporal split. Train and test are interleaved in time inside every capture. This is why Run T (§3.11.1) and the capture-held-out design of the cross-log experiment (§3.11.3) were added.

## 3.9 Evaluation Metrics

The metrics follow Part 1 §3.5. All are computed on the same 1,692,332 test events by `detect.evaluate_split` (`code/pipeline/detect.py`):

| Metric | Definition used |
|---|---|
| Accuracy | correct / all test events |
| Precision, recall, F1 (macro) | unweighted mean over the five classes [CITE: standard definition, e.g. Sokolova & Lapalme, 2009] |
| False-positive rate (FPR) | benign events predicted as any attack class / benign events |
| False-negative rate (FNR) | attack events predicted benign / attack events |
| Confusion matrix | rows = true class, columns = predicted (benign, c2, dos, malware, recon) |
| Alert reduction | 1 − incidents / events; overall, per dataset and per source |
| Processing time | training time, prediction time per event, Stage 3 runtime |

**Choice of headline metric.** Macro F1 is the main detection metric because the classes are highly imbalanced (dos is 73.9% of test events, malware 0.08%). Accuracy is reported but is dominated by a few very large DoS incidents.

**Uncertainty.** An incident-clustered percentile bootstrap was used: 1,000 replicates, RNG seed 42, 95% interval, resampling test incidents. It describes variability. It is not a significance test, and because incidents within a capture are not independent, it is likely too narrow.

**Robustness subsets:**

- events in incidents of at most 10,000 events;
- one majority vote per incident;
- events whose feature vector does not occur in training ("novel vectors").

## 3.10 Validation and Reproducibility Procedures

| Procedure | What it establishes | Evidence |
|---|---|---|
| Unit tests (94) | Correctness of ingestion, preprocessing, correlation, detection, evaluation and reporting | `code/tests/`; `REPRODUCIBILITY_CHECKLIST.md` |
| Independent rerun (Run C) on different hardware | Reproducibility: prediction CSVs byte-identical to Run B; only timings differ | `code/results/`; `predictions/`; `docs/thesis_final_validation/01_Completed_Phases_Review.md` |
| Dataset hashing | Same input data in every run | `metrics/run_manifest.json` |
| Leakage audit | No identifiers or label-derived columns in any model | `code/pipeline/detect.py` (`check_features`); `docs/thesis_final_validation/03_Final_Experimental_Methodology.md` §4 |
| Read-only evidence verification | Recomputes the reported checks (V1–V12) from saved artifacts | `../thesis_final_validation/verification/verify_evidence.py`, `verification_results.json` |
| Pinned environment | Python 3.15.0; numpy 2.5.3; pandas 3.0.6; pyarrow 26.0.0; scikit-learn 1.9.1; matplotlib 3.11.2; joblib 1.6.0; dpkt 1.9.8 | `code/requirements.txt` |
| Integrity check of supplementary work | SHA-256 of 30,615 protected files before and after the supplementary experiments: 0 differences | `experiments/_integrity/` |

## 3.11 Supplementary Experimental Protocols

### 3.11.1 Temporal hold-out (Run T)

- **Purpose:** to test whether the Run B result depends on interleaving train and test windows in time.
- **Design:** within each source, events after that source's 75th time percentile go to test, and the rest go to train. The split side is added to the correlation key, so no incident crosses the cut.
- **Execution:** run in a copy of the code with a `--split temporal` option; the default behaviour was unchanged. Everything else was as in Run B.

(Evidence: `../thesis_final_validation/supplementary_temporal/RESULTS.md` §1–2.)

### 3.11.2 Controlled ablation

- **Purpose:** to isolate the effect of incident context with everything else held constant.
- **Data:** the Run B processed events and the same 1,692,332 test events (`experiments/ablation/run_ablation.py`).
- **Model:** one pooled Random Forest with the thesis settings. The training sample is the same for every feature set within a seed.
- **Feature sets:**
  - `event_only`: the 20 Run B event features;
  - `incident_only`: `n_events`, `span_s`, `events_per_s`;
  - `event_plus_incident`: both of the above;
  - `shared_event` and `shared_plus_incident`: the same, restricted to the 11 event features present in both datasets, which removes the dataset fingerprint in missing values.
- **Windows:** 60, 150, 300, 600 and 900 s. Windows of 600 and 900 s are cut at the partition boundary and flagged `window_cut`.
- **Seeds:** 42, 1, 2, 3, 4.
- **Paired bootstrap:** incident-clustered, 1,000 replicates.
- **Data gate before the full run:** 704,090 groups at 300 s and 1,463,143 novel test events. Both had to match Run B.

### 3.11.3 Cross-log-type correlation

This experiment addresses the main design limitation of Run B: Run B correlates only one log type per source.

**Data and sensors.** The original IoT-23 packet captures (pcaps) were re-processed:

- Zeek 9.0.1 with Community ID logging produced `conn.log` and `dns.log`.
- Suricata 7.0.3 with one fixed, hashed ET Open ruleset (52,803 enabled rules) produced IDS alerts (`eve.json`).

Three log types are therefore available for the same traffic [CITE: Zeek] [CITE: Suricata] [CITE: Community ID specification]. Evidence: `experiments/RUN_LOG.md` §4.1–4.2; `experiments/cross_log/tools/run_sensors.sh`.

**Label transfer.** The new connection records carry no labels. Each new record was matched to an IoT-23 labelled record by Community ID plus start time within 1.0 s, one-to-one, closest first (`experiments/cross_log/src/label_match.py`).

**Linking.** Records were linked into incidents in two steps (`experiments/cross_log/src/linking.py`):

1. by Community ID (a connection, its DNS rows and its alerts);
2. by capture, local host and a 300 s tumbling window.

**Gate.** A capture could enter the detection experiment only if it met all three conditions, fixed before any results:

- both benign and attack traffic present;
- label-match rate of at least 90%;
- at least one incident containing two or more log types.

**Design** (fixed in `experiments/PLAN.md` §4 before training):

- **Split:** capture-held-out. Train on captures 1-1, 3-1, 20-1 and 42-1. Test on 8-1, 21-1 and 34-1, which are networks never seen in training.
- **Target:** binary, malicious versus benign.
- **Unit:** one connection record.
- **Feature conditions:**

| Condition | Features |
|---|---|
| A | connection features only |
| B | A plus DNS activity of the same local host in [ts − 300 s, ts] |
| C | A plus IDS alerts of the same local host in [ts − 300 s, ts] |
| D | A plus B plus C |

Only information available at or before the connection's start time is used. IP addresses, ports of origin, identifiers, timestamps and capture names are excluded (`experiments/cross_log/src/experiment.py`, `check_no_forbidden`).

- **Model:** the thesis Random Forest settings.
- **Seeds:** 42, 1, 2, 3, 4.
- **Metrics:** macro F1, FPR, FNR, per-class detection rate, FPR on benign rows not seen in training, and an incident-clustered bootstrap.

**Robustness analyses.** Analyses R0–R5 were specified before they were run (`experiments/PLAN.md` §4b):

| ID | Analysis |
|---|---|
| R0 | cache reproduction |
| R1 | 20 seeds with a Wilcoxon signed-rank test |
| R2 | two-level bootstrap over seeds and incidents |
| R3 | leave-one-capture-out |
| R4 | context windows anchored at connection end |
| R5 | 60 s and 900 s windows |

**Note on the metric.** The cross-log macro F1 is a **binary** macro F1. It is not comparable to the five-class macro F1 of Run B.

## 3.12 Summary of Deviations from the Part 1 Plan

| Part 1 plan | What was done | Reason |
|---|---|---|
| Stratified cross-validation for evaluation (§3.2, Stage 4) | Grouped hash split by correlation key; CV only as a robustness estimate | Prevents related events of one incident appearing in both train and test |
| Correlation "across distributed sources" (§3.2, Stage 3) | Correlation within each source in Run B; cross-log-type correlation in a supplementary experiment | The two datasets are independent recordings; no host or time overlaps between sources (0 cross-source incidents) |
| Wireshark for packet inspection (§3.4) | Zeek, Suricata and dpkt were used for packet-level processing in the cross-log experiment | Scriptable and reproducible processing of pcaps. [Author to confirm whether Wireshark was used informally.] |
| Wazuh / SIEM component (§2.5) | Not implemented; offline Python pipeline | Scope and time. The study measures detection, not SIEM deployment |
| Botnet as a detection class (§1.5) | Botnet traffic appears as c2, recon and dos classes | No event in the data is labelled "botnet" |
| Processing time as a metric (§3.5) | Measured (training, prediction, correlation time) | As planned |
