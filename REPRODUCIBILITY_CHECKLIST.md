# Reproducibility checklist

Integrated Information Management for Cybersecurity Risk Mitigation in
IoT-Enabled Smart Home Networks — experimental implementation.

Work through the steps in order. Each step names the file or command that
proves it. Section numbers refer to `README.txt`.

## A. Environment

- [ ] Windows 10/11, 64-bit; about 4 GB free RAM and 3 GB free disk
      (README §6). The reported run used Windows 11 Pro build 26200,
      i7-14700KF, 32 GB RAM.
- [ ] Python 3.15.0, 64-bit, from python.org (README §4).
- [ ] The bundle sits in a short folder path such as `C:\thesis\`
      (README §4: pip fails with WinError 206 in deep paths).
- [ ] `cd code`, then `py -3.15 -m venv .venv`.
- [ ] `.venv\Scripts\python.exe -m pip install -r requirements.txt`
      finishes without errors.
- [ ] Optional: `.venv\Scripts\python.exe -m pip freeze` matches
      `metrics\run_manifest.json` → `pip_freeze`.

## B. Data (not included: about 771 MB)

- [ ] 10 IoT-23 Zeek logs saved as
      `code\data\raw_combined\<capture>\bro\conn.log.labeled`
      (URLs in README §3).
- [ ] Bot-IoT `data_1.csv`, `data_10.csv`, `data_36.csv` saved directly in
      `code\data\raw_combined\` (README §3; the file order matters).
- [ ] The SHA-256 of each of the 13 files matches
      `metrics\run_manifest.json` → `datasets`.
- [ ] `.venv\Scripts\python.exe check_sources.py data/raw_combined` reports
      all 13 files "ok" and exits with code 0.

## C. Tests

- [ ] `.venv\Scripts\python.exe -m unittest discover -s tests` reports
      `Ran 94 tests ... OK`.

## D. Full run

- [ ] Copy any earlier `code\results\` elsewhere first: `run_all.ps1`
      deletes `data\interim`, `data\processed`, `results` and `models`
      before it runs (README §5).
- [ ] `powershell -NoProfile -ExecutionPolicy Bypass -File .\run_all.ps1 data/raw_combined`
      ends with exit code 0, in about 6 minutes on the reference machine.
- [ ] `code\results\transcripts\` holds run_all.log and one log per step.

## E. Compare with the submitted evidence

- [ ] The new `code\results\fragmented_event_predictions.csv`,
      `integrated_event_predictions.csv` and
      `diagnostic_event_predictions.csv` have the same SHA-256 as
      `predictions\` in this bundle (see `CHECKSUMS.sha256`). On the
      reference machine they were byte-identical (README §11).
- [ ] `code\results\baseline_vs_integrated.csv` equals
      `metrics\baseline_vs_integrated.csv`.
- [ ] The metrics in `code\results\stage5_report.json` equal
      `metrics\stage5_report.json`; only timing fields may differ.
- [ ] `code\results\report\REPORT.md` reports the same values as
      `report\REPORT.md`.

Results can differ on other hardware, operating systems or library versions
(for example floating-point or thread-scheduling differences). The fixed seed
(`random_state` 42) makes the run deterministic on the reference
configuration only.

## F. Verification record (2026-10-16, final code version)

| Check | Result |
|---|---|
| Clean virtual environment from requirements.txt | identical pip freeze to the reported run |
| Unit tests (clean environment) | 94 / 94 passed |
| Smoke test (6,000 lines per raw file, run_all.ps1) | all 5 stages, all outputs and figures, exit 0, 56 s |
| Full regeneration (fresh copy, clean environment) | exit 0, 385.6 s; all three prediction CSVs, comparison CSV, feature plan and alert stats byte-identical; JSON differs in timing values only |
| Secrets scan | no credentials, keys or tokens; logs contain generic local paths (`C:\Users\user\...`) |
| Bundle checksums | `CHECKSUMS.sha256`, and `FILE_MANIFEST.csv` for the whole ZIP |

## G. Known limits of reproducibility

- `run_all.sh` (Linux/macOS) has not been tested in this revision.
- Kaggle may require a login to download the Bot-IoT files.
- The code hashes in `metrics\run_manifest.json` predate four small edits made
  after the run (README §8). The full regeneration in §F was done with the
  final code.
