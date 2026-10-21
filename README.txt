INTEGRATED INFORMATION MANAGEMENT FOR CYBERSECURITY RISK MITIGATION
IN IoT-ENABLED SMART HOME NETWORKS
Experiment bundle - verified run of 2026-10-16
=====================================================================

Contents of this file
  1. What the experiment compares
  2. Headline results (verified)
  3. Data sources and how to obtain them
  4. Installation on Windows
  5. How to run
  6. Runtime and memory
  7. Linux / macOS
  8. Bundle contents
  9. Methodological limitations
 10. Superseded results (archive)
 11. Final verification
 12. Research Demonstration Lab

Every number in this file is taken from metrics\stage5_report.json,
metrics\run_manifest.json, the Stage 2/3 CSV files in metrics\ or the logs in
transcripts\. Each number and its source is listed in the project folder
thesis_review\NUMBERS_LEDGER.csv (not part of the submission bundle).


1. WHAT THE EXPERIMENT COMPARES
-------------------------------
Research question (thesis section 1.3, unchanged):

  RQ1: How does the integration and correlation of distributed IoT logs and
  alerts affect cybersecurity threat detection accuracy in IoT-enabled smart
  home networks?

Two monitoring conditions are compared, as in thesis section 3.1:

  Fragmented baseline: each data source (each of the 13 source files) is
    handled on its own, with one model per source (13 per-source models)
    trained only on that source's training events, using 20 event (flow)
    features: 11 Random Forests, plus 2 constant predictors for the two
    benign-only honeypot captures (CTU-Honeypot-Capture-4-1 and
    CTU-Honeypot-Capture-5-1), whose training data contain a single class.
    No integration, no correlation.

  Integrated condition: all sources are normalised into one structure
    (Stage 2), events are correlated into incidents (Stage 3), and one Random
    Forest is trained on 7 incident features. Each test incident's predicted
    class is given to all of its member events.

Both conditions use the same Random Forest configuration (300 trees,
max_depth 24, min_samples_leaf 2, class_weight balanced_subsample,
random_state 42, at most 60,000 training rows per class) and are scored on
the same 1,692,332 held-out test events with the same metrics.

Pipeline stages as implemented:
  Stage 1  Collection: 10 IoT-23 Zeek conn.log.labeled captures and 3 Bot-IoT
           CSV files, 4,211,383 flow records. Dataset labels are mapped to
           five shared classes: benign, c2, malware, dos, recon. (Bot-IoT DoS
           and DDoS both become "dos"; IoT-23 C&C labels become "c2";
           PartOfAHorizontalPortScan becomes "recon".)
  Stage 2  Preprocessing: removal of all-empty and duplicate rows (none were
           found); removal of identifier and label-carrying columns (IP
           addresses, timestamps, MAC addresses, Bot-IoT category /
           subcategory / attack columns); label encoding of categorical
           features; MinMax scaling; missing values encoded as -1 rather
           than removed (26.9% of training rows have no duration value,
           all of them IoT-23 rows); feature selection by removal of constant
           features and of redundant features (pairwise |Pearson r| >= 0.95
           between features). 20 of 26 features kept. All of this is fitted
           on training rows only.
  Train/test split: by Stage 3 correlation group, so an incident is never
           split between training and test data. 25% of groups go to test.
  Stage 3  Correlation: rule-based grouping of events with the same source
           capture, source IP, destination IP and protocol within a fixed
           300-second time window.
  Stage 4  Detection: Random Forest per condition as described above.
           5-fold cross-validation on training data only, as a robustness
           estimate (no model selection or tuning was done with it):
           baseline = per-source StratifiedGroupKFold with groups =
           incident, possible for only 6 of the 13 sources (skipped:
           CTU-Honeypot-Capture-4-1, CTU-Honeypot-Capture-5-1,
           CTU-IoT-Malware-Capture-20-1, -21-1, -42-1, -44-1 and data_36,
           which are single-class or have too few incidents per class);
           integrated = StratifiedKFold over training incidents (each
           incident is one row, so the folds are grouped by incident).
  Stage 5  Evaluation: accuracy, macro precision / recall / F1, FPR, FNR,
           alert reduction, processing time; robustness checks; an
           incident-clustered bootstrap interval.


2. HEADLINE RESULTS (VERIFIED)
------------------------------
Held-out test set: 1,692,332 events in 175,489 incidents, identical for both
conditions. Macro averages are over the five classes.

  Metric                  Fragmented   Integrated   Difference
                          (baseline)   (proposed)   (integrated - baseline)
  Accuracy                0.9995       0.9735       -0.0260
  Precision (macro)       0.9922       0.7950       -0.1972
  Recall (macro)          0.9989       0.9033       -0.0956
  F1 (macro)              0.9955       0.8341       -0.1614
  False-positive rate     0.0046       0.1021       +0.0975   (lower is better)
  False-negative rate     0.0001       0.0034       +0.0033   (lower is better)

  FPR = benign test events predicted as any attack class / all benign test
        events (fragmented 566 / 122,807; integrated 12,540 / 122,807).
  FNR = attack test events predicted as benign / all attack test events
        (fragmented 231 / 1,569,525; integrated 5,406 / 1,569,525).

The integrated condition performed WORSE than the fragmented baseline on
every one of these metrics.

Uncertainty: incident-clustered bootstrap, 1,000 replicates, seed 42 (test
incidents resampled with replacement, both conditions on the same draws).
95% percentile interval of the macro-F1 difference (integrated - baseline):
-0.1614 [-0.2055, -0.1280]. The whole interval is below zero. This is a
percentile confidence interval, not a significance test; see limitation (d).

Robustness checks (same direction):
  - Only events in incidents of at most 10,000 events (363,035 test events):
    macro F1 fragmented 0.9755, integrated 0.6472.
  - One vote per test incident (175,489 incidents): macro F1 fragmented
    0.9504, integrated 0.7017.

Alert reduction by Stage 3 correlation (all 4,211,383 events):

  Dataset    Sources   Events      Incidents   Alert reduction
  Bot-IoT    3         3,000,000   2,619       99.91%
  IoT-23     10        1,211,383   701,471     42.09%
  Overall    13        4,211,383   704,090     83.28%

The overall 83.28% is dominated by Bot-IoT. 0 incidents contain events from
more than one source (see limitation (a)).

Processing time (Stage 4 model training): fragmented 7.2547 s (11 forests,
20 features), integrated 1.6999 s (7 features). Prediction time per event:
fragmented 1.5527 microseconds, integrated 0.3378 microseconds.

Full results: report\REPORT.md; figure captions: report\FIGURES.md.


3. DATA SOURCES AND HOW TO OBTAIN THEM
--------------------------------------
The raw data is not included in this bundle. All sources are public.

IoT-23 (Stratosphere Laboratory, CTU Prague) - 10 Zeek connection logs:
  https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset/IndividualScenarios/<capture>/bro/conn.log.labeled
  with <capture> one of:
    CTU-Honeypot-Capture-4-1
    CTU-Honeypot-Capture-5-1
    CTU-IoT-Malware-Capture-1-1
    CTU-IoT-Malware-Capture-3-1
    CTU-IoT-Malware-Capture-8-1
    CTU-IoT-Malware-Capture-20-1
    CTU-IoT-Malware-Capture-21-1
    CTU-IoT-Malware-Capture-34-1
    CTU-IoT-Malware-Capture-42-1
    CTU-IoT-Malware-Capture-44-1

Bot-IoT - 3 CSV files of the Kaggle dataset vigneshvenkateswaran/bot-iot:
    data_1.csv   (reconnaissance)
    data_10.csv  (DoS)
    data_36.csv  (DDoS)
  Download method used in this project: an anonymous HTTPS download of each
  file from
    https://www.kaggle.com/api/v1/datasets/download/vigneshvenkateswaran/bot-iot/<file>
  (for example .../bot-iot/data_1.csv), which returned a zip archive
  containing the CSV; the CSV was extracted into data\raw_combined. Kaggle
  may require a login or API token for this in future.

Required folder layout (relative to code\):
  data\raw_combined\<capture>\bro\conn.log.labeled    (one per IoT-23 capture)
  data\raw_combined\data_1.csv
  data\raw_combined\data_10.csv
  data\raw_combined\data_36.csv

The CSV files must sit directly in data\raw_combined (not in a subfolder).
Stage 1 processes files in sorted path order, and on Windows paths are sorted
case-insensitively; with this layout the order is the 10 CTU-... captures
followed by data_1, data_10, data_36, which is the order of the reported run.
A different layout or platform can change the file order.

File sizes and SHA-256 hashes of all 13 files, taken before the run, are in
metrics\run_manifest.json ("datasets"). Compare them with your copies, for
example:  Get-FileHash data\raw_combined\data_1.csv -Algorithm SHA256


4. INSTALLATION ON WINDOWS
--------------------------
Verified platform: Windows 11 Pro (build 26200), Python 3.15.0 64-bit.
(Edition from the system query Get-CimInstance Win32_OperatingSystem:
"Microsoft Windows 11 Pro 10.0.26200 build 26200"; metrics\run_manifest.json
records the platform as Windows-11-10.0.26200.)

  1. Install Python 3.15 from https://www.python.org (64-bit installer).
  2. In PowerShell, go to the code folder and create a virtual environment
     next to run_all.ps1 (the script expects .venv\Scripts\python.exe there):
        cd <bundle>\code
        py -3.15 -m venv .venv
     (or use the full path to python.exe instead of "py -3.15").
  3. Install the pinned packages:
        .venv\Scripts\python.exe -m pip install -r requirements.txt

  Keep the bundle in a SHORT folder path (for example C:\thesis\code).
  numpy's wheel contains deeply nested files, and pip fails with
  "[WinError 206] The filename or extension is too long" when the virtual
  environment sits in a deep folder (Windows' 260-character path limit).
  This happened during the final verification and was fixed by using a
  short path. Enabling Windows long-path support also avoids it.

Pinned versions: numpy 2.5.3, pandas 3.0.6, pyarrow 26.0.0, scikit-learn
1.9.1, matplotlib 3.11.2, joblib 1.6.0, dpkt 1.9.8. pyarrow 26.0.0 is needed
on Python 3.15 / Windows (25.0.1 has no Windows wheel for Python 3.15). The
complete environment of the reported run (pip freeze) is in
metrics\run_manifest.json.


5. HOW TO RUN
-------------
From the code folder:

  Pre-flight check of the raw files (reads a sample of each file, reports
  labels and whether the correlation columns were found):
     .venv\Scripts\python.exe check_sources.py data/raw_combined
  (give the folder explicitly; the default is data\raw.)

  Unit tests (94 tests):
     .venv\Scripts\python.exe -m unittest discover -s tests

  Full run (this is how the reported results were produced):
     powershell -NoProfile -ExecutionPolicy Bypass -File .\run_all.ps1 data/raw_combined

  Fast run without cross-validation:
     powershell -NoProfile -ExecutionPolicy Bypass -File .\run_all.ps1 data/raw_combined --skip-cv

WARNING: run_all.ps1 first DELETES the contents of data\interim,
data\processed, results and models, so that no file of an earlier run can
mix with the new one. The raw data in data\raw_combined is not touched.
Copy results\ elsewhere first if you want to keep a previous run.

What run_all.ps1 then does:
  1. record_run_info.py  - writes results\run_manifest.json (host, Python and
                           package versions, SHA-256 of code and data files,
                           configuration).
  2. stage1_collect.py   - Stage 1, stages the raw files into data\interim.
  3. run_pipeline.py     - Stages 2 to 5; writes results\stage5_report.json,
                           stage5_summary.txt, baseline_vs_integrated.csv and
                           the three prediction CSV files.
  4. make_report.py      - writes results\report\REPORT.md and the figures.
  Each step's output is written to results\transcripts\<step>_run.log and the
  whole session to results\transcripts\run_all.log.

make_report.py can be re-run on its own after a run. By default it reads
results\transcripts\run_pipeline_run.log and results\transcripts\stage1_run.log
(the files run_all.ps1 writes); use --run-log / --stage1-log to point
elsewhere.


6. RUNTIME AND MEMORY
---------------------
Recorded run (transcripts\run_all.log), on an Intel Core i7-14700KF
(28 logical cores), 31.82 GiB RAM, Windows 11:
  record_run_info     2.2 s
  stage1_collect     20.0 s   (peak RSS 556 MB)
  run_pipeline      312.4 s   (Stages 2-5; peak RSS 3819 MB)
  make_report         3.7 s
  total             338.3 s
Plan for about 4 GB of free memory. Times on other hardware will differ.


7. LINUX / MACOS
----------------
code\run_all.sh is the bash counterpart of run_all.ps1: it performs the same
clean-up (with the same deletion warning), calls record_run_info.py, and
writes the same logs to results/transcripts/. It expects the virtual
environment at code/.venv/bin/python:
     python3 -m venv .venv
     .venv/bin/python -m pip install -r requirements.txt
     ./run_all.sh data/raw_combined
run_all.sh was NOT re-tested in this revision (no bash was available on the
machine used). File ordering on a case-sensitive file system may differ from
Windows (see section 3).


8. BUNDLE CONTENTS
------------------
  README.txt          this file
  REPRODUCIBILITY_CHECKLIST.md  step-by-step checklist; its section F
                      records the final verification (see also section 11
                      of this file)
  FILE_MANIFEST.csv   every file in the submission ZIP with size and SHA-256
  CHECKSUMS.sha256    SHA-256 of every file in report\, metrics\,
                      predictions\ and transcripts\
  report\             REPORT.md, FIGURES.md (captions), figures.json and
                      9 figures (fig_*.png)
  metrics\            stage5_report.json   all metrics (machine-readable)
                      stage5_summary.txt   short text summary
                      baseline_vs_integrated.csv
                      run_manifest.json    environment, code and data hashes
                      stage2_feature_plan.csv  Stage 2 feature decisions
                                               (kept/dropped, reason, scores)
                      stage3_alert_stats.csv   Stage 3 per-chunk event and
                                               incident counts
  predictions\        fragmented_event_predictions.csv
                      integrated_event_predictions.csv
                      diagnostic_event_predictions.csv
                      (one row per held-out test event)
  transcripts\        run_all.log, record_run_info_run.log, stage1_run.log,
                      run_pipeline_run.log, make_report_run.log,
                      make_report_rerun.log
  code\               the pipeline, tests, run_all.ps1, run_all.sh,
                      requirements.txt. In the submission ZIP, code\ holds
                      source files only: code\.venv (virtual environment),
                      code\data (raw and intermediate data, about 1.2 GB),
                      code\results and code\models are NOT included. They
                      are recreated by installing (section 4), downloading the
                      data (section 3) and running run_all.ps1. report\,
                      metrics\, predictions\ and transcripts\ are
                      byte-identical copies of code\results\ from the
                      reported run.
  archive\            superseded results (section 10)

Note on code versions: metrics\run_manifest.json records the SHA-256 of each
code file as it was when the experiment ran. After the run, four files
changed:
  - pipeline\reporting.py: cosmetic report wording; make_report.py was then
    re-run (transcripts\make_report_rerun.log). The current file's SHA-256,
    F1E8ADA8BB5CBAEE9B097128043C4311289DC56F05422344BE7F346546B3C4CB,
    matches the hash recorded in that log. Experiment outputs were not
    changed.
  - requirements.txt: header comment only; the package pins are identical.
  - check_sources.py: final printed message only.
  - run_all.sh: rewritten; it was not used for the run.
code\probe_botiot.py is an optional helper that lists the files of the Kaggle
Bot-IoT dataset through the Kaggle API. It needs the "kaggle" package and a
Kaggle account token, neither of which is included or required; the reported
run did not use it (the files were downloaded over HTTPS, section 3).

report\REPORT.md was generated inside the project, so its closing
"Artefacts" line names project paths (results\..., models\...). In this
bundle those files are in metrics\, predictions\ and transcripts\; models\ is
not included (the trained models are recreated by run_all.ps1). REPORT.md is
left exactly as generated.

The final verification (section 11) re-ran the whole experiment with this
final code version in a fresh copy and a fresh virtual environment; it
reproduced every prediction file byte for byte.

The diagnostic predictions and the "Diagnostic ablations" section of
REPORT.md (a pooled event model and an event model with incident context)
are extra analyses. They are NOT part of the thesis comparison.


9. METHODOLOGICAL LIMITATIONS
-----------------------------
(a) No cross-source correlation. The 13 source files are independent
    recordings made at different times, so no incident can link events from
    two sources (0 cross-source incidents). Correlation happens within each
    capture. The experiment therefore tests within-source correlation, not
    the cross-source correlation described in thesis section 3.2.
(b) Weak incident features. Of the 7 incident features, 4 (n_sources,
    n_src_ips, n_dst_ips, cross_source) have zero importance, so the
    integrated model in effect uses only n_events, span_s and events_per_s.
    It has no access to the flow content (ports, bytes, flags) that the
    baseline uses. This is a likely reason for its lower scores: the
    diagnostic enriched event model, which uses the event features plus
    n_events, span_s and events_per_s, scores close to the baseline
    (macro F1 0.9961).
(c) Very large incidents dominate event-level metrics. The split is by
    incident, so the test set holds 40.2% of events but 24.9% of incidents
    (nominal 25%). 7 test incidents with more than 10,000 events contain
    1,329,297 of the 1,692,332 test events.
(d) The bootstrap treats incidents as independent units. Incidents of the
    same capture share hosts and time, so they are not independent, and the
    interval is likely too narrow. An exploratory source-level resampling
    performed during validation (13 clusters, not saved in results\) gave a
    much wider interval; with only 13 clusters that interval is itself
    unreliable, so no values are given here.
(e) Within-capture evaluation. Training and test events come from the same
    captures. 13.54% of all test events, and 86.76% of benign test events,
    have an exact feature vector that also occurs in the training events.
    On the 1,463,143 test events whose feature vector does not occur in
    training (16,262 of them benign), the FPR is 0.0346 for the fragmented
    baseline and 0.7646 for the integrated condition.
    The scores are not an estimate of performance on unseen networks.
(f) DoS and DDoS are merged into one class "dos"; no result separates them.
(g) Botnet, brute-force and theft classes do not occur in the data used, so
    they are not evaluated (thesis 1.5 and 3.2 name botnet activity).
(h) Small classes. In the integrated training data there are only 26 dos
    incidents and 238 malware incidents (561 c2); test: 13 dos, 65 malware
    and 174 c2 incidents.
(i) One configuration, one seed (random_state 42); no hyperparameter search
    and no repeated runs with other seeds.
(j) Unequal training sets. Both conditions use the same per-class budget, but
    the baseline samples events per source (408,412 training events in
    total) while the integrated model samples incidents (120,825 training
    incidents), so the class make-up of the two training sets differs.
(k) IoT-23 composition. In the 10 IoT-23 captures used, 56.6% of events are
    recon (port scans) and 40.5% benign; c2, dos and malware together are
    under 3%.


10. SUPERSEDED RESULTS (ARCHIVE)
--------------------------------
archive\original_run_2026-10-06\ holds the previous bundle (README, report,
metrics, predictions, transcripts) unchanged. Those results came from the
original code, which had confirmed defects (label leakage through
label_entropy and Bot-IoT category/subcategory columns, a wrong FPR formula,
the timestamp used as a feature, the two conditions scored on different test
sets, ungrouped splits, per-chunk normalisation, invalid feature selection).
They are kept for traceability only and must not be cited. See
archive\original_run_2026-10-06\ARCHIVE_NOTE.txt.


11. FINAL VERIFICATION (2026-10-16)
-----------------------------------
Performed on the machine described in section 6, with the final code version:
  - Clean install: a new virtual environment created from requirements.txt
    alone resolved to exactly the same package versions (pip freeze) as the
    environment of the reported run.
  - Unit tests: 94 tests, all passed, in the clean environment.
  - Smoke test: run_all.ps1 on a small subset (first 6,000 lines of each of
    the 13 raw files) completed all five stages and produced every output
    file and figure (exit code 0, 56 s).
  - Full regeneration: run_all.ps1 on the full data in a fresh copy of the
    code with the clean environment (exit code 0, 385.6 s, peak RSS
    3799 MB). fragmented_event_predictions.csv,
    integrated_event_predictions.csv, diagnostic_event_predictions.csv,
    baseline_vs_integrated.csv, stage2_feature_plan.csv and
    stage3_alert_stats.csv were byte-identical to the files in this bundle;
    in stage5_report.json and stage5_summary.txt only timing values differed.
  - Secrets scan: no credentials, API keys or tokens in the bundle. The logs
    contain local paths of the form C:\Users\user\... (the machine's generic
    account name); they were left unchanged because the logs are evidence.
See REPRODUCIBILITY_CHECKLIST.md for the step-by-step procedure.


12. RESEARCH DEMONSTRATION LAB
------------------------------
code\demo\ contains an optional local Streamlit application, the "Research
Demonstration Lab", that presents the verified results interactively: the
headline comparison, a replay of historical dataset records (no traffic is
generated or sent), the Stage 3 correlation of events into incidents, the
saved per-event predictions of both conditions, and every reported number
with the file and JSON path it comes from.

  - It is read-only. It does not retrain any model and does not rerun any
    pipeline stage. It reads only the verified outputs of a completed
    run_all.ps1 run (code\results, code\data\interim, code\data\processed,
    code\models; code\data\raw_combined for the optional raw-file checks) and
    writes only its derived cache, code\demo\cache.
  - It needs those outputs, which are not part of the submission ZIP
    (section 8): install, download the data and run run_all.ps1 first
    (sections 3 to 5).
  - It has its own virtual environment, code\demo\.venv, separate from the
    research environment code\.venv. From the code\demo folder:
        py -3.15 -m venv .venv
        .venv\Scripts\python.exe -m pip install -r requirements-demo.txt
    (requirements-demo.txt reuses requirements.txt unchanged and adds
    streamlit and altair; keep the path short, see section 4.)
  - Launch, from the code\demo folder:
        powershell -NoProfile -ExecutionPolicy Bypass -File .\run_demo.ps1
    The script checks the evidence, builds the derived cache if needed,
    starts the app on http://localhost:8501 and opens the browser. Stop it
    with Ctrl+C.
  - The app shows the run found in code\results on the machine where it is
    launched; timing values can differ between runs (section 11).

Full instructions: code\demo\README_DEMO.md. Demonstration scripts and
expected questions: code\demo\SUPERVISOR_DEMO_GUIDE.md.
