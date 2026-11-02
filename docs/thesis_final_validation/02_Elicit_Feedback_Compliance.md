# 02 — Elicit Feedback Compliance

Each comment from the Elicit review is checked against code and artifacts. **Status** is one of:
- **Addressed**: verified in this phase.
- **Addressed with limitation**: correct as implemented, but a limitation must be stated in the thesis.
- **Partly addressed**: part of the requirement is met.
- **Not addressed**: the requirement is not met.

Abbreviations are as in 01 §1. Code line numbers refer to `submission/code/`.

## Summary

| # | Elicit comment | Status | Outstanding action |
|---|---|---|---|
| A1 | `label_entropy` uses ground-truth labels | **Addressed** (it leaked in Phases 1–3; fixed in Phase 4) | State the fix in the methodology; cite only Run B |
| A2 | Other features for target leakage | **Addressed with limitation** (dataset fingerprint) | State the limitation |
| A3 | Preprocessing or feature selection fitted on test data | **Addressed** | None |
| B1 | Exact duplicates and overlapping feature vectors | **Addressed with limitation** | Report the duplicate figures |
| B2 | Split prevents inappropriate information sharing | **Addressed with limitation** (incident-level split, same captures) | State the limitation |
| B3 | Remaining generalisation limits | **Addressed with limitation**: temporal hold-out run (Run T) confirms the result; no capture-held-out test | State that the evaluation is within-capture |
| C1 | Confusion matrices and FPR | **Addressed** | None |
| C2 | Reconcile models, predictions, reports, configs | **Addressed** | None |
| C3 | Which results belong to which run | **Addressed** | Use the run table in 01 §2 |
| S3.1 | Three-way model comparison | **Addressed** (the third model is a diagnostic) | Decide how to present the enriched model |
| S3.2 | Same held-out events, consistent metrics | **Addressed** | None |
| S3.3 | Mixed-label incidents | **Addressed** | Report the figures |
| S3.4 | Capture- or scenario-level split | **Partly addressed**: capture-level is infeasible for the baseline design; temporal split done (Run T) | See B3 |
| S4 | Cross-source correlation | **Not demonstrated** (infeasible with the current data) | Report as a limitation; see 06 §3 |

---

## A. Target leakage

### A1 — `label_entropy`
- **How it is calculated:** `correlate.py:279-288`. It is the Shannon entropy of the ground-truth label counts within each incident, so it is label-derived.
- **History:** in the original code and up to Phase 3 it was a model input. It appears in `backups/code_before_phase1/pipeline/correlate.py:88` and in `backups/code_before_phase4/models/rf_integrated_features.csv`, which lists 8 features including `label_entropy`. Elicit's concern was therefore justified for those versions. Their results (archived Run A: integrated F1 0.8110; pre-Phase-4: F1 0.8048) are invalid.
- **Now:** `label_entropy`, `label_purity`, `n_labels` and `label_counts` exist only in the diagnostics table (`correlate.py:60-64`, `DIAGNOSTIC_COLUMNS`). The model inputs are the fixed whitelist `INCIDENT_FEATURES` (`correlate.py:54`). `feature_matrix` (`detect.py:73`) selects exactly those columns, and a unit test asserts that `label_entropy` is not in the incident table (`tests/test_correlate.py`).
- **Verified 2026-11-02 (VR V3, V4):**
  - The saved model `rf_integrated.joblib` (SHA-256 `0a5649…3e33`) has `feature_names_in_` = `n_events, n_sources, n_src_ips, n_dst_ips, span_s, events_per_s, cross_source`.
  - Label-derived features: none.
  - The incident table's only label-derived columns are the targets `label` and `is_attack`.
- **Status: Addressed.**

### A2 — Other features
- **Event features:** the 20 features are listed in 03 §4. None overlaps an identifier, timestamp, label or excluded column (VR V4 `event_features_overlap_identifiers_or_labels` = []).
- **Columns excluded as leakage:** 14 columns, including Bot-IoT `attack`, `category`, `subcategory`, `pkSeqID`, `seq`, the MAC/OUI fields and the `ts_first`/`ts_last`/`ts_end` timestamps (`config.py:98`; FP rows marked `excluded`).
- **Incident features:** `n_events`, `span_s` and `events_per_s` are computed from timestamps and counts only, without labels (`correlate.py:273-277`).
- **Remaining limitation, not label leakage but a shortcut:**
  - **Dataset fingerprint:** missing-value patterns identify the dataset perfectly. `stddev` is missing (sentinel -1) for 100% of IoT-23 events and 0% of Bot-IoT events, and `missed_bytes` is the reverse (VR V4 `dataset_fingerprint_missingness`). Since `dos` is almost entirely Bot-IoT, a pooled model can partly learn "which dataset" rather than "which behaviour". This does not affect the fragmented baseline, which never mixes datasets within one model, but it inflates the pooled and enriched diagnostics.
  - **Port numbers:** `sport` and `dport` are features. They are legitimate traffic attributes, but within one capture they can act as identifiers of a specific attack tool.
- **Status: Addressed with limitation.**

### A3 — Fitting on test data
- **Split before fitting:** the split is assigned before any fitting (`preprocess._prepare` → `assign_split`, `preprocess.py:94`).
- **Train rows only:** every statistic (column roles, label vocabulary, min/max, moments, categorical vocabularies, redundancy matrix) uses train rows only. `fit` filters `split == "train"` in both passes (`preprocess.py:219`, `:272`).
- **Applied to all rows:** `transform` then applies the train-fitted values to every row (`preprocess.py:373`).
- **Label-free selection:** feature selection (`FEATURE_SELECTION = "redundancy"`, `config.py:119`) uses feature-to-feature correlations only. The label correlation in FP column `abs_corr_with_label` is recorded but not used.
- **Model fitting:** RF training samples are drawn from train events and incidents only (`detect.scan_events`, `detect.py:326`; `train_integrated`, `detect.py:485`). Cross-validation runs on training data only, and no hyperparameters were tuned (one fixed configuration, R `model_config`).
- **Status: Addressed.**

## B. Train/test independence

### B1 — Exact duplicates and overlapping vectors (VR V5)

| Check | Result |
|---|---|
| Test events whose exact 20-feature vector occurs in train | **13.54%** (229,189 of 1,692,332). benign 86.76%, recon 27.40%, c2 3.17%, dos 2.91%, malware 0% |
| Distinct feature vectors among test events | 1,550,563 (91.6% of test events) |
| Vectors that occur with more than one label anywhere | 18 vectors; 0.0008% of test events |
| Test events whose conversation key (source, src IP, dst IP, protocol) also occurs in train, in another 300 s window | **23.88%**. c2 99.94%, malware 65.57%, recon 49.25%, dos 18.96%, benign 6.66% |
| Test events whose (source, src IP) occurs in train | 84.97% |
| Test incidents whose 7-feature incident vector occurs among train incidents | **98.28%**. benign 99.17%, recon 97.05%, malware 38.46%, dos 7.69%, c2 6.32% |

**Readings:**
- Most benign duplicates are trivial flows that recur, such as DNS and multicast. Removing all duplicate test events leaves the direction of the result unchanged: on the 1,463,143 novel events, macro F1 is 0.9910 for the fragmented baseline and 0.7140 for the integrated model, and FPR is 0.0346 vs 0.7646 (R `diagnostics.duplicates.novel_only_metrics`).
- The 98.28% incident-vector overlap is not leakage. It shows that the incident features are too coarse to tell incidents apart (see 04 §5).
- The split is by correlation group. A long-running conversation is cut into 300 s windows, and its windows fall independently into train or test. This adjacency, 99.94% for c2, makes the test set easier than unseen traffic would be.

**Status: Addressed with limitation.**

### B2 — Split design
- **How the split is made:** a deterministic blake2b hash of the Stage 3 correlation-group key assigns 25% of groups to test (`preprocess.py:94-124`; `config.py:123`).
- **No incident on both sides:** 0 incidents have events in both train and test (R `split.n_mixed_incidents`; recomputed from the diagnostics table: VR V5 `n_mixed_incidents_from_diagnostics` = 0).
- **Both conditions see the same split:** the split is computed once in Stage 2 and used by both conditions.
- **Interleaved in time:** within every capture, train and test events are interleaved over the whole recording (VR V5 `time_interleaving_by_source`).
- **Uneven test share:** the hash is on groups, not events, so very large groups make the test share uneven: 40.2% of events and 24.9% of incidents. Per source the test share ranges from 7.5% (Capture-34-1) to 75.3% (data_36).
- **Status: Addressed with limitation.** The split prevents incident-level sharing, but not same-capture, same-host or adjacent-window similarity.

### B3 — Generalisation limitations still open
- **Same captures:** train and test come from the same 13 captures. The scores do not estimate performance on a new network or a new device.
- **No capture-held-out or temporal-held-out test:** neither exists. 06 §2 gives a feasibility assessment.
  - A capture-held-out test is **incompatible with the fragmented baseline by design**: one model per capture cannot predict a capture it never saw.
  - A per-capture temporal split is feasible (TS).
- **Single run:** one seed and one configuration.
- **Run T (2026-11-01 UTC, approved):** per source, test = events after the source's 75th time percentile. Every test event is later than every training event, and 0 incidents cross the cut.
  - **Fragmented:** macro F1 0.9992, FPR 0.0044.
  - **Integrated:** macro F1 0.7711, FPR 0.0965.

  The direction of the main result is unchanged (`supplementary_temporal/RESULTS.md`).
- **Status: Addressed with limitation.** The temporal hold-out confirms the result. Evaluation remains within-capture.

## C. Experimental results

### C1 — Confusion matrices and FPR (VR V1)
- **Recomputed from the prediction CSVs:** accuracy, macro precision, macro recall, macro F1, FPR, FNR and the full 5×5 confusion matrix were recomputed for all four models. All match R to within 1e-12, and all confusion matrices match exactly.
- **FPR from first principles:** it was also recalculated from its definition, independently of `evaluate_split`:

| Model | FP | Benign test events | FPR | FN | Attack test events | FNR |
|---|---|---|---|---|---|---|
| Fragmented | 566 | 122,807 | 0.004609 | 231 | 1,569,525 | 0.000147 |
| Integrated | 12,540 | 122,807 | 0.102111 | 5,406 | 1,569,525 | 0.003444 |
| Pooled (diagnostic) | 479 | 122,807 | 0.003900 | 172 | 1,569,525 | 0.000110 |
| Enriched (diagnostic) | 1,419 | 122,807 | 0.011555 | 81 | 1,569,525 | 0.000052 |

- **Definitions:** FP = benign event predicted as any attack class. FN = attack event predicted benign (`detect.py:204-257`).
- **Original bug fixed:** the original FPR bug (Run A defect 3: numerator counted false negatives, denominator was all samples) is no longer present.
- **Status: Addressed.**

### C2 — Reconciliation
- **Prediction files:** `fragmented_event_predictions.csv`, `integrated_event_predictions.csv` and `diagnostic_event_predictions.csv` have identical `event_id` order and identical labels. There are 1,692,332 unique ids, all with split = test (VR V2).
- **Model artifact:** the saved integrated model re-predicts all 175,489 test incidents. Propagating those predictions reproduces `integrated_event_predictions.csv` exactly (VR V3), and the demo test suite confirms the same independently (175,489/175,489 agree).
- **Configuration:** 300 trees, depth 24, min_samples_leaf 2, `balanced_subsample`, seed 42 (R `model_config`), matching the model object (VR V3: 300 estimators, max_depth 24). The feature list file equals `INCIDENT_FEATURES`.
- **Run B vs Run C:** they agree apart from timing (01 §2).
- **Status: Addressed.**

### C3 — Which results belong to which run
See 01 §2. Cite **Run B** only. The archived Run A and the pre-Phase-4 results are invalid. **Status: Addressed.**

## Step 3 — Fair model comparison

### S3.1 — The three models

| Required model | Implemented as | Thesis condition? | Evidence |
|---|---|---|---|
| 1. Fragmented event-level RF | 13 per-source models (11 RF + 2 constant predictors for single-class honeypot captures), 20 event features | Yes (baseline) | `detect.py:401`; R `fragmented` |
| 2. Integrated incident-level RF, predictions mapped to events | 1 RF on 7 incident features; each test incident's prediction propagated to its test events | Yes (proposed) | `detect.py:485`; R `integrated` |
| 3. Event + incident-context RF | 1 pooled RF on 20 event features + `n_events`, `span_s`, `events_per_s` of the event's incident | **Diagnostic only** | `detect.py:47`, `:549`, `:637`; R `diagnostics.enriched_event_model` |

Two caveats for presenting model 3:
- Model 3 is **pooled** (one model over all sources), not per-source. The like-for-like reference for it is the pooled event model (R `diagnostics.pooled_event_model`), not the fragmented baseline.
- Its extra information over the pooled model is the incident context. Its effect is small and mixed: macro F1 0.9944 → 0.9961, but FPR 0.0039 → 0.0116 (04 §3).

**Status: Addressed.** The comparison exists. Its role (diagnostic vs condition) is your decision; see 07.

### S3.2 — Same events, same metrics
- **Same events, scored together:** all four models are scored on the identical 1,692,332 test events (VR V2), and `run_stage4` raises an error if the indexes differ (`detect.py:600-602`).
- **Same metric code:** metrics come from one function, `evaluate_split`. The macro label set is the union of true and predicted classes, identical (5 classes) for all models.
- **Training sets differ by design:**
  - fragmented: 408,412 events
  - integrated: 120,825 incidents
  - pooled/enriched: 196,406 events
- **Status: Addressed.**

### S3.3 — Mixed-label incidents (VR V6)
- **Few mixed incidents:** 111 of 704,090 incidents (1,846 events) contain more than one label. 18 of them are test incidents, with 166 test events. Most common: `benign:1;recon:1` (37 incidents).
- **Handling:** the incident target is the majority label (ties → benign, then alphabetical; `correlate.py:165`). The prediction is propagated to all member events, and every event is scored against its **own** label, so mixing costs accuracy rather than hiding errors.
- **Cost of mixing:** only 35 test events differ from their incident's majority label.
- **Propagation ceiling (new):** if every test incident were predicted as its true majority label, event-level macro F1 would be **0.9989**, FPR 0.00015 and accuracy 0.99998. Mixed labels therefore set no meaningful ceiling. The integrated model's loss (F1 0.8341) comes from the incident classifier, not from correlation merging different classes.
- **Status: Addressed.**

### S3.4 — Capture- or scenario-level split
- **Not done.** The split is by correlation group within captures.
- **Feasibility (V11, TS):**
  - **Capture-held-out:** incompatible with the fragmented baseline, and infeasible for `malware`. Malware events occur in Capture-3-1 (5,962 events) and Capture-42-1 (3 events) only.
  - **Pairwise held-out:** possible for dos (data_10 → data_36), recon (Capture-1-1 ↔ Capture-3-1 ↔ data_1) and c2 (Capture-8-1 ↔ Capture-34-1).
  - **Per-capture temporal split (first 75% of time → train, last 25% → test):** every class keeps test events in aggregate (benign 125,218; c2 4,270; dos 503,405; malware 1,334; recon 418,620). Six small source/class cells have no test events, for example c2 in Capture-20-1 and malware in Capture-42-1.
- **Status: Partly addressed.** The temporal split was implemented in a code copy and run as Run T after your approval (06 §2; `supplementary_temporal/RESULTS.md`). A capture-held-out split remains infeasible for the fragmented design.

## Step 4 — Cross-source correlation (VR V8, V9, V10)

| Level | Demonstrated? | Evidence |
|---|---|---|
| Within one capture | **Yes** | 4,211,383 events → 704,090 incidents; alert reduction 83.28% (IoT-23 42.09%, Bot-IoT 99.91%) |
| Across log types | **No** | Only one log type per dataset: Zeek `conn.log.labeled` (IoT-23) and Argus flow CSV (Bot-IoT). The published IoT-23 `bro/` folders contain only `conn.log.labeled` (checked for Captures 34-1 and 8-1) |
| Across independent IoT sources | **No** | 0 incidents with more than 1 source (R `alert_reduction.cross_source_incidents`) |

**Correlation rules:** only rule R1 (src IP, dst IP, protocol) ever fired. Rules R2/R3 (one IP missing) and R0 (singleton) never fired, because every record has both IPs and a timestamp.

**Would a global correlation scope help?** No (new check). With the source removed from the correlation key, **0** keys span two sources, even though:
- two pairs of captures overlap in time: Capture-3-1 with data_1 (130,047 s) and Capture-42-1 with Capture-44-1 (6,541 s);
- many captures share IP addresses (VR V9 `pairs_sharing_ip_addresses`).

The shared addresses are mostly public resolvers, multicast and **coincidental private addresses**. For example, 192.168.100.1 appears in both IoT-23 and Bot-IoT, which are different networks. A global scope would therefore risk false links, and keeping the source in the key (`CORRELATION_SCOPE = "source"`) is the correct choice for this data.

**Conn + DNS feasibility:**
- **What the logs contain:** IoT-23 conn logs contain 5,143 DNS connection records (0.42%), all labelled benign. Bot-IoT data_1 has 1,285 port-53 flows. Conn records carry no query name or answer, so a DNS lookup cannot be linked to the connection it resolved.
- **What is published:** pcaps are available, for example Capture-34-1: 120 MB pcap plus `suricata/` and `.dnstop` files, listing checked 2026-11-02. Running Zeek on a pcap would produce `dns.log` for a cross-log-type experiment.
- **Assessment:** 06 §3.

**Status: Not demonstrated; report it as a limitation.** No experiment was implemented.
