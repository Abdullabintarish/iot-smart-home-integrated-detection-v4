# Research Demonstration Lab

A local Streamlit application that presents the **verified results** of the thesis
experiment *Integrated Information Management for Cybersecurity Risk Mitigation in
IoT-Enabled Smart Home Networks*. It compares the fragmented per-source baseline and
the integrated incident-correlation condition (Random Forest, IoT-23 + Bot-IoT).

What the lab is, and what it is not:

- **Read-only.** The lab only reads the saved outputs of a completed `run_all.ps1`
  run. It does not retrain any model, does not rerun any pipeline stage and never
  changes `results\`, `data\` or `models\`. The only files it writes are the derived,
  rebuildable cache in `demo\cache\`.
- **Replay, not simulation.** The "Recorded Attack Replay" page steps through
  historical dataset records that are already on disk. No network traffic is
  generated, captured or sent.
- **Live inference only where it is honest.** The saved integrated model
  (`models\rf_integrated.joblib`) is loaded read-only to show class scores for one
  incident and to check that it reproduces the saved predictions. The per-source
  baseline models were not saved, so the lab shows baseline *predictions* only, with
  no baseline confidence.
- **Results as recorded.** The integrated condition scored lower than the fragmented
  baseline on all six headline metrics (accuracy, macro precision, macro recall,
  macro F1, FPR, FNR). The lab shows this as it is.

All paths below are relative to the `code` folder unless stated otherwise. The demo
folder is `code\demo\`.

---

## 1. Prerequisites

1. **A completed pipeline run.** `run_all.ps1` (see `submission\README.txt`, section 5)
   must have finished so that these exist:
   - `results\stage5_report.json`, `results\run_manifest.json`
   - `results\fragmented_event_predictions.csv`, `results\integrated_event_predictions.csv`,
     `results\diagnostic_event_predictions.csv`
   - `data\interim\shard_*.parquet` (Stage 1 staged records)
   - `data\processed\stage2\*.parquet`, `data\processed\stage2_feature_plan.csv`
   - `data\processed\stage3_events\*.parquet`,
     `data\processed\stage3_incidents\incidents_0000.parquet`,
     `data\processed\stage3_incident_diagnostics\diagnostics_0000.parquet`
   - `models\rf_integrated.joblib`, `models\rf_integrated_features.csv`

   `run_demo.ps1` and every page check this list and stop with the list of missing
   files if anything is absent.
2. **Raw data (optional, for the raw-file checks only).** The "Verify against raw file"
   button (Replay page) and "Re-hash the raw files now and compare" (Evidence page,
   "Artefacts & figures" tab) read the original files in `data\raw_combined\`
   (10 IoT-23 `conn.log.labeled` files and `data_1.csv`, `data_10.csv`, `data_36.csv`).
   They are *not* in the launcher's required list: without them the lab starts and
   every other view works, but those two actions fail.
3. **Windows PowerShell 5.1** and **Python 3.15** (64-bit), the same Python version as
   the research environment, so the saved model loads with the pinned scikit-learn.
4. A web browser (the launcher opens the default browser). No internet connection is
   needed once the environment is installed.

## 2. Install the demo environment (once)

The demo has its **own** virtual environment, `demo\.venv`. Never install the demo
packages into `code\.venv`, the verified research environment.

From the demo folder:

```powershell
cd <bundle>\code\demo
py -3.15 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-demo.txt
```

`requirements-demo.txt` reuses the research pins unchanged (`-r ../requirements.txt`:
numpy, pandas, pyarrow, scikit-learn, joblib, ...) and adds `streamlit==1.66.0` and
`altair==6.3.0`.

**Keep the project in a short folder path** (for example `C:\thesis\code`). pip can fail
with `[WinError 206] The filename or extension is too long` when a virtual environment
sits in a deep folder (Windows' 260-character path limit). A short path, or enabling
Windows long-path support, avoids it. This is the same issue described for the research
environment in `submission\README.txt`, section 4.

## 3. Launch

From the demo folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_demo.ps1
```

Optional parameter: `-Port <n>` (default `8501`), for example
`powershell -NoProfile -ExecutionPolicy Bypass -File .\run_demo.ps1 -Port 8502`.

What `run_demo.ps1` does, in order:

1. Checks that the verified evidence listed in section 1 exists; if not, prints the
   missing files and the `run_all.ps1` command, and exits (exit code 2).
2. Checks that `demo\.venv\Scripts\python.exe` exists and can import streamlit, altair,
   sklearn and pyarrow; if not, prints the install commands and exits (exit code 2).
3. Runs `build_cache.py --check`. If the derived cache is missing or stale it runs
   `build_cache.py` to (re)build `demo\cache\`.
4. Runs `verify_live_inference.py` on every launch (live prediction of the saved
   integrated model on every test incident, compared with the saved predictions;
   about 2 s), so the check always refers to the current outputs. Then it stops with a
   clear message if the port is already in use.
5. Starts Streamlit headless on `localhost` only (`--server.headless true
   --server.address localhost --server.port <Port>`). Headless mode avoids Streamlit's
   first-start e-mail prompt and its `~\.streamlit\credentials.toml`.
6. Polls `http://127.0.0.1:<Port>/_stcore/health` for up to about 60 s; when the server
   answers it prints `Research Demonstration Lab running at http://localhost:<Port>  (Ctrl+C to stop)`
   and opens that URL in the default browser.
7. Waits until Streamlit exits.

`demo\.streamlit\config.toml` sets the dark theme, `gatherUsageStats = false`
(no telemetry), `address = "localhost"` and `fileWatcherType = "none"`.

### Manual alternative

From the demo folder, after the cache exists (section 5):

```powershell
.venv\Scripts\python.exe -m streamlit run app.py
```

then open `http://localhost:8501`. Add `--server.headless true` to avoid the first-start
e-mail prompt that non-headless Streamlit shows (the launcher always uses it):

```powershell
.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.port 8501
```

If the cache is missing or stale, every page shows a red message and a
**"Build / rebuild derived cache now"** button instead of its content.

## 4. Stop

Press **Ctrl+C** in the PowerShell window that runs the launcher (or Streamlit). Closing
the browser tab does not stop the server. If a server is left running in the
background, find and stop it:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8501 | Select-Object OwningProcess
Stop-Process -Id <OwningProcess>
```

## 5. The derived cache (`demo\cache\`)

`build_cache.py` reads only `results\*_event_predictions.csv`, `data\interim` and
`data\processed\stage2`, and writes only:

| File | Content |
|---|---|
| `cache\predictions.parquet` | the three prediction CSVs joined by `event_id` (after checking they describe identical events, all `split = test`) |
| `cache\meta.json` | source index, label counts per capture, protocol code map, time ranges, Bot-IoT category counts (all derived from `data\interim` / `stage2`) |
| `cache\cache_manifest.json` | size, mtime and SHA-256 of every input and output, so a changed input marks the cache stale |
| `cache\live_inference_check.json` | written by `verify_live_inference.py` (not by `build_cache.py`) |

Commands, from the demo folder:

```powershell
.venv\Scripts\python.exe build_cache.py --check          # prints ok / missing / stale (+ reasons)
.venv\Scripts\python.exe build_cache.py --check --deep   # also re-hashes every input
.venv\Scripts\python.exe build_cache.py                  # (re)build the cache
.venv\Scripts\python.exe verify_live_inference.py        # (re)write cache\live_inference_check.json
```

The cache is derived and safe to delete; the launcher or the in-app button rebuilds it.
`cache_manifest.json` records a build time of 2.24 s for the current cache.

The sidebar shows the cache state ("Derived cache: ✓ ok"), the run timestamp and the
code snapshot id from `results\run_manifest.json`.

## 6. Demonstrating without rerunning the experiment

The lab is designed for exactly this. Every page reads files that `run_all.ps1` already
wrote; nothing on any page triggers Stage 1-5 code, model training or cross-validation.
Concretely:

- headline metrics, confusion matrices, per-class and per-capture values, robustness
  checks, bootstrap intervals, alert reduction and limitations come from
  `results\stage5_report.json` and `results\run_manifest.json`;
- per-event predictions come from the three `results\*_event_predictions.csv` files
  (via `cache\predictions.parquet`);
- records, splits and incident memberships come from `data\interim`,
  `data\processed\stage2`, `data\processed\stage3_*`;
- the only computation on a model is `predict_proba` / `predict` of the saved
  integrated model, which is deterministic and does not change it;
- values the lab recomputes (alert reduction per capture, metrics from the confusion
  matrix, outcome counts, incident membership) are shown next to the stored value
  with a ✓/✗ check, so the demonstration also verifies the stored results.

To demonstrate on another machine, copy the whole `code` folder (with `results\`,
`data\interim`, `data\processed`, `models\`, and `data\raw_combined` if the raw-file
checks are wanted), create `demo\.venv` (section 2) and launch (section 3). The lab
needs no network connection.

Note: the lab displays the run in the `code\results\` folder of the machine it runs on.
Timing fields (training and prediction times) differ slightly between runs of the same
code; the metric values and prediction files do not (see `submission\README.txt`,
section 11).

## 7. Page by page

The sidebar lists the five pages in this order. Colours: blue = fragmented baseline,
orange = integrated condition. Under most blocks a grey "Source:" caption names the
file and JSON path each value was read from.

### 7.1 Research Overview (default page)

Research question (RQ1), the two conditions, "Corpus at a glance" (source captures,
flow records, correlated incidents, held-out test events, test incidents), the
"Datasets" table (each capture's first `event_id`, staged record count, raw file, size,
SHA-256 prefix, origin, and a check that staged count = report count), the headline
detection table with a derived "better" column and verdict sentence, score and
error-rate bar charts on separate scales, "Alert reduction through correlation"
(overall and per dataset) and "Limitations".

Reads: `results\stage5_report.json` (split, fragmented, integrated, comparison,
alert_reduction_by_dataset, robustness, diagnostics.duplicates, model_config,
bootstrap), `results\run_manifest.json` (datasets, config), `data\interim` (source
index), `cache\meta.json` (label and Bot-IoT category counts), the `models\` listing.

### 7.2 Recorded Attack Replay

Banner: "Replay of historical dataset records — no traffic is generated or sent."
Controls: **Threat category (classes present in the data)**,
**Capture containing '<class>' events**, **Rows per window** (50/100/200),
**Replay speed (events / s)** (0.5/1.0/2.0/4.0), **Start at event # (0 … n−1)** with
**Jump to event #**, **Start time (UTC)** slider with
**Jump to first event at/after this time**, and **Play/Pause**, **Step back**,
**Step forward**. The "Current event k of n" card shows dataset family, capture,
`event_id`, record in original file, UTC and epoch timestamp, IPs and ports, protocol,
ground-truth label, split and `incident_id`; the expander lists all non-null staged
columns. **Verify against raw file** reads the original raw line (bounded read), passes
it through the same Stage 1 functions, and shows a ✓/✗ line, the raw file with physical
line number and data record, the raw text, and a field-by-field comparison table.
Charts: events in the current window (time vs replay position) and all events of the
selection (dashed line = current event).

Identifier mapping: `event_id` = 0-based position in the event stream (the same row in
`data\interim`, `data\processed\stage2` and `data\processed\stage3_events`);
record in original file = `event_id` − first `event_id` of the capture = 0-based data
record of the raw file (Zeek: n-th non-comment, non-blank line; Bot-IoT CSV: n-th
non-blank row after the header). At most 5,000 rows are read per selection.

Reads: `data\interim\shard_*.parquet`, `data\processed\stage2` (split),
`data\processed\stage3_events` (incident_id), `cache\meta.json` (label counts),
`data\raw_combined\...` (only on "Verify against raw file").

### 7.3 Event Correlation Explorer

States rule R1 (`R1_pair_proto`): same source capture, `src_ip`, `dst_ip` and protocol
in the same tumbling 300 s window, i.e. the same bucket `floor(ts / 300)`; scope
"source". Controls: **Capture**, **Choose an incident** (Largest incidents /
Random sample (seed 42) / By label / Paste an incident_id), then **Incident (N listed)**,
**Incident (majority) label** (By label mode) or **incident_id (16 hex characters)**
(paste mode). Shows member count, span, majority label, test/train members, the
"Correlation key" card (rule, IPs, protocol code and name, window bucket, window
start/end, first/last timestamp), the 7 incident features the integrated model uses,
label diagnostics (marked as *not* model features), a **Membership check** (✓ when all
members share capture, IPs, protocol and window bucket and the counts match the
incident tables; details in **Check details**), a timeline stacked by ground-truth
label, the member table (**Member page**, 200 rows each; at most the first 5,000
members by timestamp are listed), and the **Alert reduction** table per capture, per
dataset and overall, each recomputed from `stage3_incidents` with a ✓.

Reads: `results\run_manifest.json` (CORRELATION_WINDOW_S, CORRELATION_SCOPE,
CORRELATION_RULES), `data\processed\stage3_incidents\incidents_0000.parquet`,
`data\processed\stage3_incident_diagnostics\diagnostics_0000.parquet`,
`data\processed\stage3_events`, `cache\meta.json` (protocol names),
`results\stage5_report.json` (alert_reduction_by_dataset).

### 7.4 Random Forest Detection Comparison

Tab **Thesis conditions**: filters **Capture**, **True class**, **Outcome**
(both correct / baseline wrong only / integrated wrong only / both wrong); four outcome
counts for the chosen capture and class; **Consistency with the confusion matrices
(all test events)** expander; paginated table (**Rows per page**, **Page**); then
**Inspect an event from this page** or **… or type any test event_id**. The event view
has three cards: the staged raw record, the fragmented baseline (prediction ✓/✗ and its
20 Stage 2 event features; a note that baseline confidence is not available) and the
integrated condition (prediction ✓/✗, incident, the 7 incident features, a
**Model confidence (live inference with the saved integrated model)** bar chart, a
check that the live argmax equals the saved prediction, and the result of
`verify_live_inference.py`). Expander: **Incident diagnostics (label-derived; not model
features)**.

Tab **Diagnostic models (not thesis conditions)**: the pooled and enriched event
models (diagnostic ablations, reported separately) and their predictions for one event
(**Test event_id (defaults to the event inspected in the first tab)**).

Reads: `cache\predictions.parquet` (from the three `results\*_event_predictions.csv`),
`results\stage5_report.json` (confusion matrices, diagnostics), `data\interim`,
`data\processed\stage2`, `data\processed\stage2_feature_plan.csv`,
`data\processed\stage3_incidents` and `..._diagnostics`, `models\rf_integrated.joblib`,
`models\rf_integrated_features.csv`, `cache\live_inference_check.json`.

### 7.5 Research Evidence Explorer

Tabs: **Metrics** (headline table with JSON paths; training/inference and
cross-validation fields; integrated model at incident level), **Confusion matrices**
(both conditions, counts and row %), **From matrix to metrics** (choose **Condition** and
**Class**; TP/FP/FN/TN, precision/recall/F1 formulas, and a live check of every metric
computed from the matrix against the JSON), **Per class / per capture**,
**Robustness & bootstrap** (small-incidents and majority-vote checks; clustered
bootstrap intervals with a "difference CI excludes 0" column and the note that this is
not a hypothesis test), **Alert reduction**, **Diagnostics** (pooled / enriched models;
train/test duplicates and novel-only metrics), **Limitations**,
**Artefacts & figures** (toggle **Compute SHA-256 of all artefacts**; manifest hashes of
the raw files and the button **Re-hash the raw files now and compare (reads every raw
file once)**; figures `results\report\fig_*.png`; `REPORT.md` verbatim; tails of the run
transcripts).

Reads: `results\stage5_report.json`, `results\run_manifest.json`, `results\report\`,
`results\transcripts\*.log`, all artefacts (for hashing, on request) and
`data\raw_combined\` (re-hash, on request).

## 8. Tests

48 unit tests (identifier mapping, incident membership, predictions and outcome
consistency, live inference, UTC charts, page smoke tests with a Streamlit stub and with
Streamlit's AppTest, and a guard that nothing outside `demo\` is created, changed or
deleted). From the demo folder:

```powershell
.venv\Scripts\python.exe -B -m unittest discover -s tests
```

Run them with `demo\.venv` (tests that need Streamlit are skipped under another
interpreter). They build the cache if it is missing or stale and run the live-inference
comparison on all test incidents. Two tests in `tests\test_evidence_mapping.py`
(raw line agrees with staged record; raw record count equals staged count) read
`data\raw_combined\` and fail, rather than skip, if the raw data is absent. Expected
ending: `Ran 48 tests ... OK`. Messages
"missing ScriptRunContext! This warning can be ignored when running in bare mode." are
normal.

## 9. Screenshots

`screenshots\1_overview.png` … `5_evidence.png` show the five pages. To recapture them,
from the demo folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\capture_screenshots.ps1
```

Parameters: `-Port` (Streamlit, default 8599), `-CdpPort` (Edge DevTools, default 9222),
`-Edge` (path to `msedge.exe`, default
`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`). The script refuses to
start if either port is in use, starts its own headless Streamlit and headless Edge,
runs `tools\cdp_screenshot.py` (waits until each page has rendered, then captures the
full page at 1500 px width), overwrites the five PNG files, and stops only the two
processes it started. Edge's throwaway profile is left in
`cache\edge_profile_<CdpPort>\`; it can be deleted.

## 10. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Launcher prints "Verified evidence is missing:" | `run_all.ps1` has not been run (or was interrupted). Run it from the code folder, then relaunch. |
| Launcher prints "demo\.venv not found" or "lacks the demo packages" | Create / install the demo environment (section 2). |
| Page shows "Derived demo cache is stale: input changed since cache build: ..." | A new `run_all.ps1` replaced inputs. Click **Build / rebuild derived cache now**, or run `build_cache.py`, or simply relaunch with `run_demo.ps1` (it rebuilds a stale cache). |
| After a new `run_all.ps1`, the Detection page says "Run verify_live_inference.py to check live vs saved predictions on all test incidents." | The live check is tied to the model's SHA-256; the model changed. `run_demo.ps1` re-runs `verify_live_inference.py` on every launch, so relaunching fixes it; when starting Streamlit manually, run `.venv\Scripts\python.exe verify_live_inference.py` first. |
| Launcher stops with "Port 8501 is already in use" | Another program (often an earlier demo) listens on 8501. Stop it (section 4) or use `.\run_demo.ps1 -Port 8502`. |
| "Verify against raw file" or "Re-hash the raw files" fails, or a raw file shows `missing` | `data\raw_combined\` is absent or incomplete. Restore the raw files (layout in `submission\README.txt`, section 3). The rest of the lab is unaffected. |
| A raw-hash check shows ✗ | The raw file differs from the hash recorded in `results\run_manifest.json` before Stage 1: it is not the file the run used. |
| The first visit to a page is slow | Each page loads its data once per server session and then caches it ("Loading saved per-event predictions ...", "Loading the saved integrated model (read-only) ..."). Visit every page once before an audience arrives. The **Compute SHA-256 of all artefacts** toggle and the raw re-hash read large files and take noticeably longer; run them only on request. |
| pip fails with `[WinError 206]` | Path too long; move the project to a short path (section 2). |
| Times in the charts look shifted | All timestamps are shown in UTC on purpose (axis titles say "time (UTC)"). |

## 11. Files in the demo folder

| File | Role |
|---|---|
| `app.py` | entry point, page navigation |
| `pages\1_overview.py` … `pages\5_evidence.py` | the five pages |
| `evidence.py` | all read-only evidence access (no Streamlit import) |
| `ui.py` | styling, cached accessors, charts, limitations text |
| `build_cache.py` | builds / checks `cache\` |
| `verify_live_inference.py` | live vs saved integrated predictions on all test incidents |
| `run_demo.ps1` | launcher |
| `requirements-demo.txt` | demo environment (research pins + streamlit, altair) |
| `.streamlit\config.toml` | theme, no telemetry, localhost only |
| `tools\capture_screenshots.ps1`, `tools\cdp_screenshot.py` | screenshot capture |
| `tests\` | 48 unit tests |
| `screenshots\` | page screenshots |
| `SUPERVISOR_DEMO_GUIDE.md` | timed demonstration scripts, expected questions, checklist |

---

## Ledger: numbers in this document

| Value | Meaning | Source |
|---|---|---|
| 6 headline metrics, integrated lower on all six | accuracy, macro precision/recall/F1, FPR, FNR | `results\stage5_report.json` → `comparison[*].better` (all "fragmented") |
| 300 s, scope "source", rule R1_pair_proto | correlation window, scope, rule | `results\run_manifest.json` → `config.pipeline.config.CORRELATION_WINDOW_S`, `CORRELATION_SCOPE`, `CORRELATION_RULES` |
| 10 IoT-23 files + 3 Bot-IoT files | raw data files | `results\run_manifest.json` → `datasets.files` |
| 20 event features / 7 incident features | baseline / integrated features | `results\stage5_report.json` → `fragmented.n_features`, `integrated.n_features` |
| 2.24 s | build time of the current derived cache | `demo\cache\cache_manifest.json` → `build_seconds` |
| 48 tests | demo test suite | test run of 2026-10-16 (`Ran 48 tests in 34.665s`, `OK`), command in section 8 |
| 5,000 rows; 200 rows per member page | display caps | `evidence.py` (`MAX_SELECTION`), `pages\3_correlation.py` (`PAGE`) |
| 8501 / 8599 / 9222 | default ports | `run_demo.ps1`, `tools\capture_screenshots.ps1` |
| about 60 s | launcher health-check limit (120 polls x 0.5 s) | `run_demo.ps1` |
