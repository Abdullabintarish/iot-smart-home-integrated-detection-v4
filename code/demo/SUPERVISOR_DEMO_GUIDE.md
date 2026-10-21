# Supervisor Demonstration Guide - Research Demonstration Lab

This guide contains (a) a 5-minute demonstration script, (b) a 10-minute technical
demonstration script, (c) likely supervisor questions with evidence-backed answers, and
(d) a pre-demo checklist. Installation and launch: `README_DEMO.md` (same folder).

Ground rules for the presenter:

- The lab shows **one verified, recorded run**. Nothing is retrained, no traffic is
  generated, no pipeline stage is rerun.
- The integrated condition scored **lower** than the fragmented baseline on all six
  headline metrics. Say so plainly; do not present alert reduction as a detection gain.
- The bootstrap interval is a percentile interval, **not a significance test**.
- Diagnostic models (pooled, enriched) are **not thesis conditions**.

Widget labels below are quoted exactly as they appear in the app (bold = a control to
click or set). Example identifiers were checked against the data on 2026-10-16 (see the
ledger at the end).

### Example cases used in the scripts

| Case | Identifier | What it shows |
|---|---|---|
| A. C&C connection, both conditions correct | event_id **1201246** (CTU-IoT-Malware-Capture-8-1, raw record 266), incident **e94b4304c1fac1b1** | 16 c2 events in one R1 incident; raw-file check ✓; live score c2 = 1.000 |
| B. Bot-IoT recon scan misclassified by the integrated model | event_id **2064693** (data_1, raw record 853310), incident **a4195a4a38f2b8e9** | one incident of 24,385 recon events predicted `dos`; the baseline predicts `recon` correctly |
| C. Benign false positive of the integrated model | event_id **1211391** (data_1, raw record 8), incident **08b4710976d5f642** | benign, baseline `benign` ✓, integrated `malware` ✗ (scores malware 0.414 vs benign 0.384) |
| D. Baseline wrong only | event_id **20289** (CTU-IoT-Malware-Capture-1-1), incident **b9c44fd791cb7e97** | benign, baseline `recon` ✗, integrated `benign` ✓ |
| E. Giant incident | incident **c764c0a79ec23769** (data_36) | 271,637 dos events in one incident; both conditions predict `dos` for all of them |

Tip: keep these identifiers in a text file so they can be pasted.

---

## (a) 5-minute supervisor demonstration

Start state: app open on **Research Overview**, every page visited once (checklist (d)).

**0:00-1:00 - Research Overview**

- Point at "Research question (RQ1)" and the two coloured condition names (blue =
  fragmented baseline, orange = integrated).
- Point at "Corpus at a glance": 13 source captures / files, 4,211,383 flow records,
  704,090 correlated incidents, 1,692,332 held-out test events, 175,489 test incidents.
- Scroll to "Headline detection results (held-out test events)". Read the macro F1 row
  (0.9955 vs 0.8341) and the FPR row (0.0046 vs 0.1021), then the verdict line:
  "The fragmented baseline scored better on 6 of 6 headline metrics; the integrated
  condition did not score higher on any."
- Say: "Both conditions are scored on the identical held-out events. The integrated
  condition did not improve detection in this experiment."

**1:00-2:00 - Recorded Attack Replay (Case A)**

- Point at the banner "Replay of historical dataset records — no traffic is generated or
  sent."
- **Threat category (classes present in the data)** → `Command and Control (c2)`.
- **Capture containing 'c2' events** → `CTU-IoT-Malware-Capture-8-1  (IoT-23) — 8,222 events`.
- **Start at event # (0 … 8,221)** → `128`, click **Jump to event #**.
- The card reads "Current event 129 of 8,222": event_id 1,201,246, record in original
  file 266, timestamp 2018-07-31T14:45:25.237109Z, 192.168.100.113 : 43388 →
  178.128.185.250 : 50, tcp, label c2, split test, incident_id e94b4304c1fac1b1.
- Click **Verify against raw file**. Point at the ✓ line and the caption
  `data/raw_combined/CTU-IoT-Malware-Capture-8-1/bro/conn.log.labeled, physical line 275
  (data record 266)` and the raw Zeek line ending in `Malicious   C&C`.
- Say: "Every record shown can be traced back to the exact line of the public dataset."

**2:00-3:00 - Event Correlation Explorer (Case A)**

- **Choose an incident** → `Paste an incident_id`; type `e94b4304c1fac1b1` into
  **incident_id (16 hex characters)** and press Enter.
- Point at: Member events 16, Span (s) 272.138, Majority label c2, Test / train events
  16 / 0; in "Correlation key": rule R1_pair_proto, proto `4  = tcp`, window bucket
  5,110,161, window 14:45:00-14:50:00 UTC.
- Point at the green ✓ under "Membership check".
- Scroll to "Alert reduction": `1 − 704,090 / 4,211,383 = 0.832813 (83.28%)`; then the
  `[Bot-IoT total]` row (0.999127) and `[IoT-23 total]` row (0.420934), and
  "Cross-source incidents: 0."
- Say: "Correlation compresses records into incidents, mostly in Bot-IoT. Incidents
  never span two captures, so this run tests within-capture correlation only."

**3:00-4:15 - Random Forest Detection Comparison (Case B)**

- Tab **Thesis conditions**: **Capture** → `data_1`, **True class** → `recon`,
  **Outcome** → `integrated wrong only`.
- Point at the four counts for data_1 / recon: both correct 117,319; baseline wrong only
  204; integrated wrong only 25,322; both wrong 17.
- In **… or type any test event_id** type `2064693` and press Enter.
- Point at the three cards: fragmented prediction = recon ✓; integrated prediction = dos ✗;
  incident a4195a4a38f2b8e9 with n_events 24,385, span_s about 9.46 s.
- Point at "Model confidence (live inference with the saved integrated model)": dos 0.640,
  recon 0.350; and the ✓ line "verify_live_inference.py: live predict agreed with the saved
  prediction on 175,489 of 175,489 test incidents".
- Say: "The integrated model sees only incident-level features such as size, duration and
  rate. This dense scan incident looks like a DoS burst, and one wrong incident prediction
  is copied to all 24,385 member events." Point at the note "Baseline confidence is not
  available" and say why (per-source models not saved).

**4:15-5:00 - Research Evidence Explorer**

- Tab **Robustness & bootstrap**: point at the difference block, macro F1 row:
  point -0.1614, 95% CI -0.2055 to -0.1280, and the caption "it is not a hypothesis test".
- Tab **Limitations**: name three: no cross-source correlation, a few giant incidents
  dominate event-level scores, within-capture evaluation with duplicates.
- Close: "Every number in the app has a Source caption pointing to the JSON path it came
  from; the answer to RQ1 in this experiment is that within-capture correlation reduced
  alerts but lowered detection performance."

---

## (b) 10-minute detailed technical demonstration

**1. Provenance trace, raw line → staged row → event → incident → predictions (0:00-2:30)**

Use Case B.

1. **Recorded Attack Replay**: **Threat category (classes present in the data)** →
   `Reconnaissance (recon)`; **Capture containing 'recon' events** →
   `data_1  (Bot-IoT) — 998,007 events`; **Start at event # (0 … 998,006)** → `851308`;
   **Jump to event #**. Card: "Current event 851,309 of 998,007", event_id 2,064,693,
   record in original file 853,310, 192.168.100.150 : 49731 → 192.168.100.3 : 3306, tcp,
   recon, test, incident_id a4195a4a38f2b8e9.
2. Explain the mapping: event_id is the 0-based position in the event stream, identical
   in `data\interim` (staged row), `data\processed\stage2` (features, split) and
   `data\processed\stage3_events` (incident_id). Record in file = event_id − first
   event_id of data_1 (1,211,383; shown in the Overview "Datasets" table).
3. Click **Verify against raw file**: caption `data/raw_combined/data_1.csv, physical line
   853,312 (data record 853,310)` (line = record + header line + 1-based numbering). The
   table compares every staged column with the raw value after the same Stage 1
   normalisation; the ✓ line says all staged columns agree.
4. **Event Correlation Explorer** → `Paste an incident_id` → `a4195a4a38f2b8e9`: 24,385
   member events, Span (s) 9.461, Majority label recon, Test / train events 24,385 / 0,
   label_purity 1.0000. The member table lists the first 5,000 members by timestamp
   (display cap); the membership check uses all 24,385.
5. **Random Forest Detection Comparison** → type `2064693`: the baseline used the event's
   20 Stage 2 features; the integrated model used the incident's 7 features; predictions
   recon ✓ vs dos ✗.

**2. Correlation rule and window (2:30-3:45)**

- On the Correlation page, read the R1 note: same source capture, src_ip, dst_ip and
  protocol, and the same tumbling 300 s bucket floor(ts / 300); scope "source"; R2/R3
  apply only when an IP is missing.
- Open **Check details**: distinct source / src_ip / dst_ip / proto / window bucket = 1;
  member count = incidents.n_events = diagnostics.n_events; min/max ts = ts_first /
  ts_last; test and train member counts.
- Point out the consequence of a tumbling window: an attack that crosses a 300 s
  boundary becomes two incidents; a dense flood inside one window becomes one very
  large incident.

**3. Alert reduction formula (3:45-4:30)**

- Alert reduction = 1 − incidents / events.
  Overall: 1 − 704,090 / 4,211,383 = 0.832813 (83.28%).
  Bot-IoT: 1 − 2,619 / 3,000,000 = 0.999127 (99.91%).
  IoT-23: 1 − 701,471 / 1,211,383 = 0.420934 (42.09%).
- Mean events per incident: Bot-IoT 1145.48, IoT-23 1.73.
- Each per-capture row carries "recomputed from stage3_incidents" ✓.
- State: this measures how many records collapse into incidents; it is not a
  detection-accuracy metric, and the overall value is dominated by Bot-IoT.

**4. Confusion matrix → metrics (4:30-6:30)**

- **Research Evidence Explorer** → tab **Confusion matrices**: rows = true, columns =
  predicted. Integrated benign row: 110,267 | 1,262 | 36 | 291 | 10,951 (columns benign,
  c2, dos, malware, recon).
- Tab **From matrix to metrics**: **Condition** → `Integrated (correlated incidents)`,
  **Class** → `benign`. TP 110,267, FP 5,406, FN 12,540, TN 1,564,119.
  Precision = 110,267 / (110,267 + 5,406) = 0.953265; recall = 110,267 / (110,267 +
  12,540) = 0.897889.
- Binary rates (benign = negative, every attack class = positive):
  FPR = benign predicted as any attack / all benign = 12,540 / 122,807 = 0.1021
  (fragmented 566 / 122,807 = 0.0046);
  FNR = attack predicted as benign / all attack = 5,406 / 1,569,525 = 0.0034
  (fragmented 231 / 1,569,525 = 0.0001).
- Point at the live consistency table: every value computed from the matrix equals the
  JSON value (✓).
- Accuracy vs macro F1: 1,250,540 of the 1,692,332 test events are dos, and the
  integrated dos F1 is 0.9900, so accuracy stays at 0.9735. Macro F1 weights the five
  classes equally; integrated malware F1 0.5870 and c2 F1 0.7394 pull it to 0.8341.
- **Random Forest Detection Comparison**, expander **Consistency with the confusion
  matrices (all test events)**: both correct 1,647,067 + integrated wrong only 44,346 =
  1,691,413 = trace of the fragmented matrix; both correct + baseline wrong only 360 =
  1,647,427 = trace of the integrated matrix; the four groups (with both wrong 559) sum
  to 1,692,332.

**5. Live inference check (6:30-7:15)**

- On the Detection page (Case B or Case A), point at the model-confidence chart and the
  two ✓ lines: live argmax = saved prediction for this incident; and
  `verify_live_inference.py` agreed on 175,489 of 175,489 test incidents (0 mismatches),
  checked 2026-10-16T13:53:27Z against the model file whose SHA-256 is recorded in
  `demo\cache\live_inference_check.json`.
- Explain: the scores are `predict_proba` of the saved RandomForest = mean of the 300
  trees' class probabilities, a model score, not a calibrated probability.

**6. Robustness and bootstrap (7:15-8:45)**

Tab **Robustness & bootstrap**:

- Small incidents only (incidents with at most 10,000 events; 363,035 test events):
  macro F1 0.9755 vs 0.6472.
- Incident majority vote (one vote per test incident; 175,489 incidents): macro F1
  0.9504 vs 0.7017.
- Clustered bootstrap (test incidents resampled with replacement, both conditions on the
  same draws, n_boot = 1,000, seed 42): macro F1 difference -0.1614, 95% percentile
  interval -0.2055 to -0.1280; accuracy difference interval -0.0895 to -0.0079; FPR
  difference interval 0.0925 to 0.1027.
- State: all checks point the same way; the interval describes resampling spread over
  incidents and is not a hypothesis test. Incidents of the same capture are not
  independent, so the interval is likely too narrow (`submission\README.txt`,
  limitation (d)).

**7. Limitations (8:45-10:00)**

Tab **Limitations** (each item has its source):

- No cross-source correlation: scope "source", 0 cross-source incidents.
- 7 test incidents with more than 10,000 events hold 1,329,297 of 1,692,332 test events
  (78.55%).
- Within-capture evaluation: 13.54% of test events have an exact feature-vector
  duplicate among training events; on the 1,463,143 novel test events macro F1 is 0.9910
  vs 0.7140.
- DoS and DDoS merged into `dos`; classes botnet, bruteforce, theft absent from the data.
- One seed, one configuration (random_state 42, 300 trees, max_depth 24, 60,000 training
  rows per class).
- Baseline models not saved: no live baseline inference and no baseline confidence.

---

## (c) Likely supervisor questions and evidence-backed answers

**Q1. Why is the integrated condition worse?**
The integrated model sees only 7 incident-level features and no flow content (ports,
bytes, flags). Four of them have zero importance (n_sources, n_src_ips, n_dst_ips,
cross_source); importance is span_s 0.3613, events_per_s 0.3337, n_events 0.3050. Its
prediction is copied to every member event, so one wrong incident produces many wrong
events: Case B is a single recon incident of 24,385 events predicted `dos`; in data_1,
25,014 recon test events in 13 incidents were predicted `dos`. Every single-event
incident with span 0 has the same feature vector and therefore the same scores (event 1
on the Detection page and Case D both show benign 0.659, malware 0.239). The integrated
training set is also small for rare classes: 120,825 incidents, of which dos 26,
malware 238, c2 561. The baseline uses 20 event features per source. Show: Detection
page Case B; Evidence → Metrics; Diagnostics tab.

**Q2. Is the 83% alert reduction meaningful?**
It is a real count but must be read per dataset: Bot-IoT 99.91% (3,000,000 events →
2,619 incidents, mean 1145.48 events per incident) and IoT-23 42.09% (1,211,383 →
701,471, mean 1.73). The overall 83.28% is dominated by Bot-IoT. It measures
compression of records into incidents, not detection quality, and it came with lower
detection scores. Show: Correlation page "Alert reduction" table.

**Q3. Why is accuracy high (0.9735) but macro F1 much lower (0.8341)?**
dos makes up 1,250,540 of 1,692,332 test events and the integrated dos F1 is 0.9900, so
accuracy is dominated by one class. Macro F1 averages the five classes equally:
integrated benign 0.9247, c2 0.7394, dos 0.9900, malware 0.5870, recon 0.9293. Show:
Evidence → "Per class / per capture" and "From matrix to metrics".

**Q4. Was there data leakage?**
Measures in the verified run: the train/test split hashes the Stage 3 correlation group
key (source, rule, src_ip, dst_ip, proto, floor(ts/window)), so no incident is split
(n_mixed_incidents = 0); every Stage 2 statistic (encoders, MinMax scaling, feature
selection) is fitted on training rows only (`pipeline\preprocess.py`;
`submission\README.txt` section 1); identifier and label-carrying columns (IPs,
timestamps, MAC addresses, Bot-IoT category / subcategory / attack) are removed
(`run_manifest.json` → `config.pipeline.config.LEAKAGE_COLUMNS`, `ID_COLUMNS`); label
diagnostics such as label_purity / label_entropy are shown in the app but are not model
features. The original run had confirmed leakage defects; it is archived for
traceability in `submission\archive\original_run_2026-10-06\` and must not be cited.
Residual issue, not leakage in the strict sense: evaluation is within-capture and 13.54%
of test events duplicate a training feature vector (see Q11).

**Q5. Why are there no cross-source incidents?**
Correlation scope is "source": the capture is part of the correlation key, and the 13
files are independent recordings, so no incident can link two captures (0
cross-source incidents). The experiment therefore tests within-capture correlation, not
the cross-source correlation described in the thesis design. Show: Overview →
Limitations; Correlation page bottom.

**Q6. Why is there no baseline confidence?**
The 13 per-source baseline models (11 Random Forests plus 2 single-class sources that
predict their one class) were not saved; only their predictions were. `models\` contains
only `rf_integrated.joblib` and `rf_integrated_features.csv`. The app therefore shows
baseline predictions only, with no live baseline inference. Show: Detection page note.

**Q7. What does the model-confidence chart (predict_proba) mean?**
For the saved RandomForest it is the mean of the trees' class-probability estimates for
the incident's feature vector. It is a model score used to rank classes, not a
calibrated probability of being an attack. The bar with the highest score equals the
saved prediction (✓ line under the chart).

**Q8. How reproducible is this?**
`results\run_manifest.json` records Python 3.15.0, the full pip freeze, the SHA-256 of
every code file (snapshot id), the SHA-256 of all 13 raw files, and the configuration
(random_state 42). `submission\README.txt` section 11 reports a full regeneration in a
fresh copy that reproduced every prediction file byte for byte. On 2026-10-16 the three
prediction CSVs in `code\results\` were compared by SHA-256 with `submission\predictions\`
and are identical; `code\results\stage5_report.json` differs from
`submission\metrics\stage5_report.json` only in timing fields. Note that the sidebar
shows the run recorded in `code\results\run_manifest.json` (2026-10-16T13:07:08+00:00),
which is a different run timestamp and code snapshot id from `submission\metrics\run_manifest.json`.
Live inference of the saved model agrees with the saved predictions on 175,489 of
175,489 test incidents. Limitation: one seed, one configuration.

**Q9. Why are DoS and DDoS merged?**
Bot-IoT's DoS and DDoS categories are both mapped to the class `dos` in Stage 1 (the
`BOTIOT_SCENARIOS` are DDoS, DoS, Recon in `run_manifest.json`); no result separates
them. The Overview → Limitations item "DoS and DDoS merged" lists the event counts per
category from the staged data.

**Q10. What about the giant incidents?**
Seven test incidents with more than 10,000 events hold 1,329,297 of the 1,692,332 test
events (78.55%), so event-level scores are dominated by a few incidents (Case E: one
data_36 incident of 271,637 dos events, predicted dos by both conditions). Restricted to
the other 363,035 test events, macro F1 is 0.9755 vs 0.6472; the gap remains. Because
the split is by incident, the test set holds 40.18% of events but 24.92% of incidents
(nominal 25%).

**Q11. Are there duplicates / is evaluation within-capture?**
Yes. Training and test events come from the same captures. 13.54% of test events have an
exact feature-vector duplicate among training events (benign: 86.76%). On the 1,463,143
novel test events, macro F1 is 0.9910 vs 0.7140 and FPR is 0.0346 vs 0.7646. The scores
are not an estimate of performance on unseen networks. Show: Evidence → Diagnostics.

**Q12. Do the diagnostic models show that integration helps?**
No claim is made. They are ablations, not thesis conditions: a pooled event model (macro
F1 0.9944) and the same model with three incident-context features added (enriched,
macro F1 0.9961). The enriched model's macro F1 is close to the baseline's 0.9955 but
its FPR is higher (0.0116 vs 0.0046); these are single-run values without intervals.
They are consistent with the reading in `submission\README.txt` limitation (b) that the
integrated model's lower scores are likely due to its lack of flow-level features; they
do not show that integration improves detection.

**Q13. Is the bootstrap interval a significance test?**
No. It is a 95% percentile interval from an incident-clustered bootstrap (1,000
replicates, seed 42). The macro-F1 difference interval (-0.2055 to -0.1280) lies below
zero, which describes the resampling spread; it is not a p-value, and dependence between
incidents of the same capture probably makes it too narrow.

**Q14. What would improve the integrated condition? (future work, no results)**
Untested directions, stated as future work only: give the incident model flow-content
aggregates (ports, bytes, flags) rather than size and timing alone; evaluate across
captures (train on some captures, test on others) to remove within-capture duplicates;
use data in which the same network is observed by several sources so cross-source
correlation can occur; tune the correlation window or use sliding windows; report
seed variation; save the baseline models. None of these was run.

**Q15. How can I verify any number in the app?**
Every block has a grey "Source:" caption naming the file and JSON path (for example
`results/stage5_report.json → integrated.f1_macro`). Recomputed values are shown with
✓/✗ next to the stored value (alert reduction per capture, metrics from the confusion
matrix, outcome counts vs matrix traces, incident membership, staged vs raw record).
Evidence → "Artefacts & figures" computes SHA-256 of all artefacts on request and can
re-hash the raw files against the manifest. `REPORT.md` and the run transcripts are shown
verbatim.

---

## (d) Pre-demo checklist

- [ ] Launch 10 minutes early from the demo folder:
      `powershell -NoProfile -ExecutionPolicy Bypass -File .\run_demo.ps1`
      (use `-Port 8502` if 8501 is taken).
- [ ] Sidebar shows "Derived cache: ✓ ok".
- [ ] Warm the caches: visit all five pages once; on the Detection page inspect one event
      (loads the predictions and the model); on the Correlation page open one incident;
      on the Replay page click **Verify against raw file** once (confirms the raw data is
      present).
- [ ] Detection page shows the ✓ line "verify_live_inference.py: live predict agreed ...
      175,489 of 175,489 test incidents". If it asks you to run the script, run
      `.venv\Scripts\python.exe verify_live_inference.py` and reload.
- [ ] Have the example identifiers (table at the top) in a text file for pasting.
- [ ] Have open: `README_DEMO.md`, this guide, `code\results\report\REPORT.md`,
      `submission\README.txt`.
- [ ] Offline is fine: the lab needs no network once installed (telemetry is disabled in
      `.streamlit\config.toml`). Disable notifications; set browser zoom so tables are
      readable.
- [ ] Do not toggle **Compute SHA-256 of all artefacts** or click the raw re-hash button
      during the timed demo unless asked; they read large files.
- [ ] Stop with Ctrl+C afterwards.

---

## Ledger: numbers in this guide

Headline and aggregate values (verified files):

| Value | Source |
|---|---|
| 4,211,383 flow records | `results\stage5_report.json` → `split.n_events` |
| 13 sources (10 IoT-23, 3 Bot-IoT) | `stage5_report.json` → `fragmented.n_sources`; `alert_reduction_by_dataset.per_dataset.*.n_sources`; `run_manifest.json` → `datasets.files` |
| 704,090 incidents | `stage5_report.json` → `alert_reduction_by_dataset.overall.incidents` |
| 1,692,332 test events | `stage5_report.json` → `fragmented.n_test`, `fragmented.n_samples` |
| 175,489 test incidents | `stage5_report.json` → `split.n_test_incidents` |
| accuracy 0.9995 / 0.9735; macro precision 0.9922 / 0.7950; macro recall 0.9989 / 0.9033; macro F1 0.9955 / 0.8341; FPR 0.0046 / 0.1021; FNR 0.0001 / 0.0034 | `stage5_report.json` → `fragmented.*`, `integrated.*` (rounded to 4 decimals, as displayed in the app); `comparison[*].better` = fragmented for all six |
| macro F1 difference -0.1614 | `stage5_report.json` → `comparison[3].difference` (-0.16135) |
| FPR counts 566 / 12,540 of 122,807; FNR counts 231 / 5,406 of 1,569,525 | `stage5_report.json` → `fragmented.binary_counts`, `integrated.binary_counts` |
| integrated benign row 110,267 / 1,262 / 36 / 291 / 10,951; TP/FP/FN/TN 110,267 / 5,406 / 12,540 / 1,564,119; traces 1,691,413 and 1,647,427 | `stage5_report.json` → `integrated.confusion_matrix`, `fragmented.confusion_matrix` (FP, FN, TN and traces computed from the matrices) |
| benign precision 0.953265, recall 0.897889 | `stage5_report.json` → `integrated.per_class.benign` |
| per-class integrated F1: benign 0.9247, c2 0.7394, dos 0.9900, malware 0.5870, recon 0.9293; dos support 1,250,540 | `stage5_report.json` → `integrated.per_class` |
| outcomes 1,647,067 / 360 / 44,346 / 559 | computed by the app from the saved predictions (`results\*_event_predictions.csv` via `demo\cache\predictions.parquet`); consistent with the matrix traces above |
| alert reduction 0.832813 (83.28%); Bot-IoT 2,619 / 3,000,000, 0.999127 (99.91%), mean 1145.48; IoT-23 701,471 / 1,211,383, 0.420934 (42.09%), mean 1.73; cross-source 0 | `stage5_report.json` → `alert_reduction_by_dataset.overall`, `.per_dataset` |
| first event_id of data_1 = 1,211,383 | `demo\cache\meta.json` → `sources` (derived from `data\interim`; shown in the Overview "Datasets" table) |
| window 300 s, scope "source", rules R1_pair_proto / R2_src_proto / R3_dst_proto; BOTIOT_SCENARIOS; LEAKAGE_COLUMNS; random_state 42 | `results\run_manifest.json` → `config.pipeline.config` |
| 300 trees, max_depth 24, 60,000 per class | `stage5_report.json` → `model_config` |
| split strategy; n_mixed_incidents 0 | `stage5_report.json` → `split.strategy`, `split.n_mixed_incidents` |
| test share 40.18% of events, 24.92% of incidents | computed: 1,692,332 / 4,211,383 and 175,489 / 704,090 (`split.n_events`, `split.n_test_incidents`, `alert_reduction_by_dataset.overall.incidents`) |
| feature importance span_s 0.3613, events_per_s 0.3337, n_events 0.3050, four features 0.0 | `stage5_report.json` → `integrated.feature_importance` |
| integrated training 120,825 incidents; dos 26, malware 238, c2 561 | `stage5_report.json` → `integrated.n_train`, `integrated.train_class_counts` |
| 11 Random Forests, 13 sources | `stage5_report.json` → `fragmented.n_rf_models`, `fragmented.n_sources` |
| small incidents: max 10,000 events, 7 excluded incidents, 1,329,297 excluded events (78.55%), 363,035 kept, macro F1 0.9755 / 0.6472 | `stage5_report.json` → `robustness.small_incidents` |
| majority vote: 175,489 incidents, macro F1 0.9504 / 0.7017 | `stage5_report.json` → `robustness.incident_majority_vote` |
| bootstrap: n_boot 1,000, seed 42; F1 difference CI -0.2055 / -0.1280; accuracy difference CI -0.0895 / -0.0079; FPR difference CI 0.0925 / 0.1027 | `stage5_report.json` → `bootstrap.*`, `bootstrap.difference.*.ci_low/ci_high` |
| duplicates 13.54% (benign 86.76%); 1,463,143 novel; novel macro F1 0.9910 / 0.7140; novel FPR 0.0346 / 0.7646 | `stage5_report.json` → `diagnostics.duplicates` |
| pooled macro F1 0.9944; enriched macro F1 0.9961, FPR 0.0116 | `stage5_report.json` → `diagnostics.pooled_event_model`, `diagnostics.enriched_event_model` |
| live check 175,489 of 175,489, 0 mismatches, 2026-10-16T13:53:27Z | `demo\cache\live_inference_check.json` |
| run timestamp 2026-10-16T13:07:08+00:00 | `results\run_manifest.json` → `timestamp_utc` |

Example values (checked on 2026-10-16 with the demo's own `evidence.py` functions run in
`demo\.venv`, scratch scripts outside the project; they read
`demo\cache\predictions.parquet` (from `results\*_event_predictions.csv`),
`data\interim`, `data\processed\stage3_*`, `data\raw_combined` and
`models\rf_integrated.joblib`; they are the values the app displays for these
identifiers):

| Identifier | Verified values |
|---|---|
| event 1201246 | CTU-IoT-Malware-Capture-8-1, record 266, 2018-07-31T14:45:25.237109Z, 192.168.100.113:43388 → 178.128.185.250:50, tcp, c2, test; fragmented c2, integrated c2 (both correct); raw line 275, key and all columns match; position 128 of 8,222 c2 events in the replay |
| incident e94b4304c1fac1b1 | 16 events (16 test / 0 train), span_s 272.138, R1_pair_proto, proto 4 = tcp, bucket 5,110,161 (window 14:45:00-14:50:00 UTC), label_purity 1.0, membership check ✓; live scores c2 1.000, all others 0.000 |
| CTU-IoT-Malware-Capture-8-1 | 1,558 incidents (`stage5_report.json` → `alert_reduction_by_dataset.per_source`); all 2,634 test events both correct (`integrated.per_source` accuracy 1.0, `fragmented.per_source` accuracy 1.0) |
| event 2064693 | data_1, record 853,310, 192.168.100.150:49731 → 192.168.100.3:3306, tcp, recon, test; fragmented recon, integrated dos (integrated wrong only); raw line 853,312, key and all columns match; position 851,308 of 998,007 recon events in the replay |
| incident a4195a4a38f2b8e9 | 24,385 events (all test), span_s 9.461, events_per_s 2577.5, label recon (purity 1.0), membership check ✓; live scores dos 0.640, recon 0.350, malware 0.010, benign 0.000, c2 0.000 |
| data_1 / recon outcome counts | both correct 117,319; baseline wrong only 204; integrated wrong only 25,322; both wrong 17 (142,862 test events) |
| data_1 recon predicted dos | 25,014 events in 13 incidents (24,385 of them in a4195a4a38f2b8e9) |
| event 1211391, incident 08b4710976d5f642 | data_1, record 8, benign; fragmented benign, integrated malware; 2 events; live scores malware 0.414, benign 0.384, recon 0.156, c2 0.034, dos 0.013 |
| event 20289, incident b9c44fd791cb7e97 | CTU-IoT-Malware-Capture-1-1, record 18,463, benign; fragmented recon, integrated benign; 1 event, span 0; live scores benign 0.659, malware 0.239, recon 0.058, dos 0.027, c2 0.018 (identical to event 1 in `screenshots\4_detection.png`) |
| incident c764c0a79ec23769 | data_36, 271,637 dos events (all test), the largest incident; both conditions predict dos for all members; live scores dos 0.897, recon 0.103 |
