# Run log — ablation and cross-log experiment

All new results here are **Additional analysis, pending supervisor approval.**

All times UTC. Working copy: `submission/` (Git repo), branch
`cross-log-experiment` created from `main` at `74cb51c`. The original
instructions said not to push or merge; on 2026-11-02 the user asked for the
branch to be pushed and then merged (§10). Commands run from `submission/`
unless stated otherwise.

## 0. Environment

| Item | Value |
|---|---|
| OS | Windows 11 Pro 10.0.26300; agent session not elevated |
| Disk free at start | 134 GB on C: (limit for this work: 50 GB) |
| Python (Windows) | 3.15.0, existing `code/.venv` used **read-only** with `-B` / `PYTHONDONTWRITEBYTECODE=1`; nothing installed into it |
| Python packages | numpy 2.5.3, pandas 3.0.6, scikit-learn 1.9.1, dpkt 1.9.8, pyarrow 26.0.0 |
| WSL | WSL 2, kernel 6.18.54.1-microsoft-standard-WSL2; distro Ubuntu 24.04.5 LTS |
| Zeek | 9.0.1 (`zeek-lts` from the official OBS repo `security:zeek/xUbuntu_24.04`) |
| Suricata | 7.0.3 RELEASE (Ubuntu `universe`, `1:7.0.3-1build3`) |
| git / curl | 2.55.0.windows.5 / 8.21.0 |

## 1. Protection of existing work

- `git checkout -b cross-log-experiment`.
- `code/data/`, `.venv/` and caches are git-ignored, so a SHA-256 baseline of
  **every** file under `submission/` (except `.git/`, `experiments/`) and
  `../thesis_final_validation/` was taken first:
  `_integrity/baseline_sha256.txt` (30,615 files, 2026-11-02T17:49:22Z).
- `run_all` / `run_pipeline` were never run. The ablation package was **not**
  copied into `code/` (its README suggests that); it runs from
  `experiments/ablation/` with `PYTHONPATH=code`, as the instructions require.
- Thesis modules are imported read-only with bytecode writing disabled.

## 2. Stage 1 — understanding

- Read `README.txt`, `REPRODUCIBILITY_CHECKLIST.md`,
  `docs/thesis_final_validation/*.md`, `code/pipeline/config.py`,
  `correlate.py`, `detect.py`, `ingest.py`.
- `code/data/processed/stage3_events/` (18 parquet files) and
  `code/data/processed/stage2_feature_plan.csv` exist (under `code/`).
- Plan: `PLAN.md`. Stage 4 design fixed there before any training.

## 3. Stage 2 — ablation

### 3.1 Package

First session: `experiments/Ablation_Package.zip` did not exist and a search of
C: found nothing. The user then supplied the package contents as three files
(not as a zip), which were saved verbatim:

| File | SHA-256 |
|---|---|
| `ablation/README_ABLATION.txt` | 9d3b588aedeaca3fec4cec16c68735a149a8122d5726cf89b3c9d870fae35c85 |
| `ablation/run_ablation.py` | c08384f8eda068ce3ba7086494afaa69b1afe6ca867c91e8d16246fb82fad137 |
| `ablation/tests/test_ablation.py` | c66827ef140ee3b11d952be4c41aecc179c33c6e985416a1c57b537095fd73fd |

The package README notes it was tested only on synthetic data and Python 3.13,
and asks that feature sets, windows and seeds be agreed with Dr. Shah before
the full run. The package defaults were used unchanged (5 feature sets,
windows 60/150/300/600/900, seeds 42/1/2/3/4, 300 trees); this was **not**
agreed with Dr. Shah beforehand. All runs are reported below.

### 3.2 Commands

```
cd experiments/ablation
export PYTHONPATH=<submission>\code PYTHONDONTWRITEBYTECODE=1
../../code/.venv/Scripts/python.exe -B -m unittest discover -s tests -v
../../code/.venv/Scripts/python.exe -B run_ablation.py --seeds 42 --windows 300 --out results/quick_check
../../code/.venv/Scripts/python.exe -B run_ablation.py --out results/full
```

| Step | Time | Result |
|---|---|---|
| Unit tests | 18:23:22 | **6 / 6 OK** (one harmless ResourceWarning: unclosed file in the test) |
| Quick check | ~18:24–18:26 | exit 0, 2.7 min; `groups_at_300s` = **704,090** (= `run_b_incidents`), `n_novel` = **1,463,143**. Both match → full run allowed |
| Full run | 18:26:49–18:53:32 | exit 0, 26.7 min, 85 model fits; same gate values in `results/full/checks.json` |

The full run log has 20 scikit-learn `UserWarning: A single label was found in
'y_true' and 'y_pred'`. They come from the benign-only subsets
(`multi_event_benign`, `single_event_benign`) when every prediction there is
also benign. FPR on those subsets is computed directly from counts in
`detect.evaluate_split` and is valid; macro F1 on a benign-only subset is not
meaningful and should not be cited.

### 3.3 Results (`ablation/results/full/`)

Held-out test events: 1,692,332 (Run B test set). Pooled Random Forest, same
training sample per seed for every feature set. Mean ± SD over 5 seeds.

| Window (s) | Feature set | Macro F1 | FPR | Cut |
|---|---|---|---|---|
| — | event_only | 0.9952 ± 0.0012 | 0.38% ± 0.05% | no |
| — | shared_event | 0.9977 ± 0.0002 | 0.20% ± 0.02% | no |
| 60 | incident_only | 0.7141 ± 0.0229 | 8.90% ± 0.01% | no |
| 60 | event_plus_incident | 0.9965 ± 0.0003 | 1.18% ± 0.02% | no |
| 60 | shared_plus_incident | 0.9977 ± 0.0004 | 0.88% ± 0.09% | no |
| 150 | incident_only | 0.8110 ± 0.0051 | 9.37% ± 0.01% | no |
| 150 | event_plus_incident | 0.9966 ± 0.0003 | 1.13% ± 0.01% | no |
| 150 | shared_plus_incident | 0.9974 ± 0.0004 | 0.97% ± 0.12% | no |
| 300 | incident_only | 0.8566 ± 0.0035 | 9.16% ± 0.03% | no |
| 300 | event_plus_incident | 0.9964 ± 0.0003 | 1.14% ± 0.02% | no |
| 300 | shared_plus_incident | 0.9971 ± 0.0005 | 0.96% ± 0.10% | no |
| 600 | incident_only | 0.8465 ± 0.0071 | 9.31% ± 0.03% | yes |
| 600 | event_plus_incident | 0.9950 ± 0.0001 | 1.18% ± 0.01% | yes |
| 600 | shared_plus_incident | 0.9965 ± 0.0008 | 0.94% ± 0.12% | yes |
| 900 | incident_only | 0.8481 ± 0.0048 | 9.52% ± 0.05% | yes |
| 900 | event_plus_incident | 0.9949 ± 0.0004 | 1.18% ± 0.01% | yes |
| 900 | shared_plus_incident | 0.9970 ± 0.0008 | 0.84% ± 0.14% | yes |

Source: `ablation/results/full/thesis_table.md`, `ablation_summary.csv`.
"Cut" = window does not divide 300 s, so incidents are cut at the Run B
partition boundary.

Paired incident-clustered bootstrap, 300 s, seed 42, 1,000 replicates
(`ablation/results/full/bootstrap.json`), 95% percentile intervals:

| Comparison | Macro F1 difference | FPR difference |
|---|---|---|
| incident_only − event_only | [−0.1761, −0.1072] | [+0.0836, +0.0909] |
| event_plus_incident − event_only | [−0.0014, +0.0048] | [+0.0060, +0.0081] |
| shared_plus_incident − shared_event | [−0.0021, +0.0016] | [+0.0080, +0.0099] |

Novel-vector test events (n = 1,463,143), 300 s: event_only F1 0.9917, FPR
2.81%; event_plus_incident F1 0.9880, FPR 8.41%; incident_only F1 0.7521,
FPR 68.59% (`ablation_summary.csv`, subset `novel_vector`).

## 4. Stage 3 — cross-log pilot

### 4.1 Tool setup (WSL)

First session: blocked (no admin; downloading binaries refused by the agent's
permission policy). Second session, after the user ran
`wsl --install -d Ubuntu-24.04` and approved downloads:

```
wsl.exe --install -d Ubuntu-24.04 --no-launch --web-download     # distro was not yet registered
wsl -u root: apt-get install curl gnupg ca-certificates
  echo 'deb http://download.opensuse.org/repositories/security:/zeek/xUbuntu_24.04/ /' > /etc/apt/sources.list.d/security_zeek.list
  curl -fsSL .../security:zeek/xUbuntu_24.04/Release.key | gpg --dearmor > /etc/apt/trusted.gpg.d/security_zeek.gpg
  apt-get install --no-install-recommends zeek-lts suricata
```

### 4.2 Ruleset (fixed for the whole experiment; never edited)

| Item | Value |
|---|---|
| URL | https://rules.emergingthreats.net/open/suricata-7.0.3/emerging.rules.tar.gz |
| Downloaded | 2026-11-02T18:25:23Z |
| Tarball SHA-256 | d5330ebe76cb36cfad3621f2d9c66d0d5894d55a8778dba1f6c21c99a777b035 |
| Concatenated `all.rules` SHA-256 | 84530843118cbed2b534d1c361ac20400146c4e64afd5c9c5112d15e6d7d0aef |
| Version | no version file in tarball; newest rule `updated_at 2026_10_30` |
| Rules | 52,803 enabled (default state) loaded, 0 failed; 19,507 commented out (left disabled) |
| Suricata config | packaged `/etc/suricata/suricata.yaml` with only `community-id: false` → `true`; `-k none`, `--runmode single`; default `HOME_NET` |
| Zeek | `zeek -C -r <pcap> policy/protocols/conn/community-id-logging` |

Files: `cross_log/ruleset/RULESET.txt`, `suricata.yaml`, `suricata.yaml.sha256`.
Per-capture tool versions and pcap hash: `cross_log/sensor_out/<capture>/versions.txt`.

### 4.3 Failures and fixes

| Problem | Fix |
|---|---|
| `run_sensors.sh` stopped silently: `suricata --build-info` has no yaml path; empty `grep` + `pipefail` ended the script | Added `|| true`; fallback `/etc/suricata/suricata.yaml` used |
| 42-1: Zeek `fatal error ... truncated dump file; tried to read 91 captured bytes, only got 45` | `src/trim_pcap.py` wrote a byte-exact prefix of all complete records: 24,484 records kept, 61 trailing bytes (one partial packet) dropped. Copy `2019-01-10-14-34-38-192.168.1.197.trimmed.pcap`, SHA-256 ad1624d71606a0727974488b989871b4f4636ea24628762f57696abd80ae2bf5. Original unchanged. No other pcap was truncated (`results/pcap_trim.json`) |

### 4.4 Captures checked (pilot order 8-1 → 42-1 → 20-1)

| Capture | pcap | Decision |
|---|---|---|
| 44-1 | 1.7 GB | Not used: very large pcap |
| Honeypot 4-1 | none listed | Not used: no pcap |
| Honeypot 5-1 | 364 MB | Not used: benign only |
| 8-1 | 2.0 MB | Pilot. **Gate failed**: 0 DNS records, 0 alerts → 0 cross-source incidents |
| 42-1 | 2.8 MB | Fallback 1. Zeek failed on truncated pcap (fixed later, §4.3) |
| 20-1 | 3.9 MB | Fallback 2. **Gate passed** → Stage 4 allowed |
| 21-1, 3-1, 34-1, 1-1 | 3.9–139 MB | Stage 4 captures (PLAN §4) |

pcap and labelled-log hashes: see §6. Server `conn.log.labeled` files are
byte-identical to the thesis copies in `code/data/raw_combined/`.

### 4.5 Results (`cross_log/results/stage3_<capture>.json`)

| Capture | New conn | Matched | Match rate | Labelled rows covered | DNS | Alerts | Incidents | ≥ 2 types | Gate |
|---|---|---|---|---|---|---|---|---|---|
| 8-1 | 10,403 | 10,403 | 1.0000 | 1.0000 | 0 | 0 | 278 | 0 | **fail** |
| 20-1 | 3,209 | 3,209 | 1.0000 | 1.0000 | 808 | 0 | 24 | 23 | pass |
| 42-1 | 4,426 | 4,426 | 1.0000 | 1.0000 | 1,841 | 2,019 | 37 | 35 | pass |
| 21-1 | 3,286 | 3,286 | 1.0000 | 1.0000 | 2,578 | 0 | 58 | 56 | pass |
| 3-1 | 156,103 | 156,103 | 1.0000 | 1.0000 | 12 | 50,529 | 429 | 2 | pass |
| 34-1 | 8,990 | 8,988 | 0.9998 | **0.3883** | 348 | 7,877 | 165 | 15 | pass |
| 1-1 | 1,008,748 | 1,008,748 | 1.0000 | 1.0000 | 19 | 41 | 1,352 | 21 | pass |

Only one incident (42-1) contains all three record types.

**34-1 coverage.** The IoT-23 log has 23,145 rows; Zeek 9.0.1 writes 8,990.
14,159 of the 14,394 labelled DDoS rows share one Community ID (TCP
192.168.1.195:65279 → 123.59.209.185:80). Every labelled Community ID is present
in the new log. Result: only **237** of 14,394 DDoS rows have a labelled
counterpart. This changes the class make-up of the Stage 4 test set. The cause
was investigated in §4.6 (it is **not** the Zeek version, as first assumed).

### 4.6 Follow-up: 34-1 with an older Zeek (Bro 2.6.4)

Requested by the user after the main runs. Question: does a Zeek of the
generation used for IoT-23 (logs dated 2019) reproduce the 23,145 rows?

- WSL offers no Ubuntu older than 22.04, and the Zeek OBS repository only has
  Zeek 7.0, 8.0 and 9.0 builds, so Bro 2.6.4 was built from source
  (`cross_log/old_zeek/build_bro26.sh`, log `old_zeek/build.log`):
  `https://download.zeek.org/bro-2.6.4.tar.gz`, SHA-256
  a47a9cdcef0ea14d5f70c390ab266f0333063ff96f3869a5f1609581a1d1ceb7;
  GPG: "Good signature from The Zeek Team <info@zeek.org>" (subkey
  E9690B2B7D8AC1A19F921C4AC68B494DF56ACC7E; key fetched from keys.openpgp.org,
  not otherwise certified). Built with gcc-9 9.5.0, OpenSSL 3.0.13, into
  `/opt/bro26` inside the WSL distro (`--disable-broctl --disable-python
  --disable-auxtools --disable-broker-tests`). Build exit 0; `bro version 2.6.4`.
- Run 2026-11-02T19:28:29Z: `bro -C -r <34-1 pcap>` →
  `cross_log/sensor_out_bro26/CTU-IoT-Malware-Capture-34-1/`.
- Comparison: `src/old_zeek_check.py` → `results/old_zeek_check_34-1.json`.

| | IoT-23 log | Bro 2.6.4 | Zeek 9.0.1 |
|---|---|---|---|
| conn records | 23,145 | 8,990 | 8,990 |
| rows identical to IoT-23 (ts, 5-tuple, state, packets) | — | 8,874 | 8,874 |
| DDoS rows covered | 14,394 | 237 | 237 |
| c2 / benign / recon covered | 6,706 / 1,923 / 122 | all | all |

Bro 2.6.4 and Zeek 9.0.1 give the same records. The flow above has exactly
14,159 packets in the pcap (dpkt count) with the same first and last
timestamps as the 14,159 IoT-23 rows. IoT-23 logs one row per packet, each
`conn_state OTH`, `history C`, 0 packets, no duration, no duplicates. Both Zeek
versions log 6 connections of ~5 s each (2,254–2,461 originator packets,
history `HTTTT`). So IoT-23's log treats every packet of this flood as its own
connection, which neither Zeek version reproduces from the published pcap with
default settings; the cause (for example IoT-23's run-time configuration) cannot
be determined from the published files. The earlier explanation (a
Zeek-version difference) was wrong and has been corrected here and in
`THESIS_ADDITIONS.md`. No Stage 3/4 result changes: both versions give the same
records.

Side note for the thesis: Run B's 14,394 DDoS events from 34-1 include these
14,159 per-packet rows of a single flow. Run B's dos class has 2,014,334
events in total (`03_Final_Experimental_Methodology.md`), almost all from
Bot-IoT, so the effect on Run B's figures is small.

Alert categories: 3-1 mostly "Attempted Information Leak" (50,470 of 50,529);
34-1 and 42-1 mostly "Misc activity". 8-1, 20-1 and 21-1 have no alerts.

## 5. Stage 4 — cross-log experiment

Command (18:44:15–18:45:40, exit 0):
```
cd experiments/cross_log
PYTHONDONTWRITEBYTECODE=1 ../../code/.venv/Scripts/python.exe -B src/run_stage4.py
```
Design as fixed in `PLAN.md` §4 (no change after results). Outputs:
`results/stage4_results.json`, `stage4_bootstrap.json`,
`stage4_predictions.parquet`, `stage4_run.log`.

Data: train 1,172,486 rows (recon 685,062; benign 481,424; malware 5,965;
c2 35), test 22,677 rows (c2 14,942; benign 7,376; dos 237; recon 122).
Alert categories fixed from training alerts (7 categories). Test incidents: 501.

| Condition | Macro F1 (mean ± SD) | FPR | FNR | FPR unseen benign (n = 1,964) |
|---|---|---|---|---|
| A conn | 0.3346 ± 0.1973 | 0.0027 | 0.8912 | 0.0103 |
| B conn + DNS | 0.5016 ± 0.1688 | 0.0043 | 0.7061 | 0.0163 |
| C conn + alerts | 0.3164 ± 0.1564 | 0.0028 | 0.9180 | 0.0103 |
| D all | 0.6187 ± 0.1355 | 0.0046 | 0.5561 | 0.0168 |

FPR, FNR and unseen-benign FPR are means over the 5 seeds.

Per-seed macro F1 (seeds 42, 1, 2, 3, 4):
A 0.2461, 0.2460, 0.2462, 0.2469, 0.6876;
B 0.3546, 0.3492, 0.5868, 0.4693, 0.7483;
C 0.2463, 0.2467, 0.2463, 0.2466, 0.5961;
D 0.5893, 0.5850, 0.4852, 0.5859, 0.8480.

Paired per-seed differences in macro F1:
B − A +0.1085, +0.1032, +0.3406, +0.2223, +0.0607 (all positive);
C − A +0.0001, +0.0007, +0.0002, −0.0003, −0.0915;
D − A +0.3432, +0.3390, +0.2390, +0.3390, +0.1604 (all positive).

Incident-clustered bootstrap (seed-42 models only, 501 clusters, 1,000
replicates): A [0.1511, 0.3231], B [0.2023, 0.4731], C [0.1511, 0.3231],
D [0.4743, 0.6676]; B − A [+0.0070, +0.2278]; C − A [−0.0000, +0.0003];
D − A [+0.2831, +0.4127]. These intervals do not include seed variance, which
is large (seed 4 differs strongly from the others).

Per-class detection rate (mean ± SD over seeds; benign = share kept benign):

| Class (n) | A | B | C | D |
|---|---|---|---|---|
| benign (7,376) | 0.9973 ± 0.0002 | 0.9957 ± 0.0022 | 0.9972 ± 0.0002 | 0.9954 ± 0.0022 |
| c2 (14,942) | 0.1109 ± 0.2463 | 0.3004 ± 0.2301 | 0.0834 ± 0.1845 | 0.4537 ± 0.2063 |
| dos (237) | 0.0211 ± 0.0000 | 0.0270 ± 0.0132 | 0.0211 ± 0.0000 | 0.0388 ± 0.0162 |
| recon (122) | 0.0230 ± 0.0135 | 0.0230 ± 0.0147 | 0.0246 ± 0.0142 | 0.0262 ± 0.0147 |

Reading: on unseen captures every condition misses most attacks (training
attacks are mostly recon; test attacks are mostly c2). DNS context helps in
every seed; alert context alone does not; all three together give the largest
gain. Absolute performance is low and seed-dependent.

## 6. Hashes of downloaded data (`cross_log/pcaps/`)

| File | SHA-256 |
|---|---|
| 8-1 `2018-07-31-15-15-09-192.168.100.113.pcap` | 80dcc2602519479ddcde889fa902fee19a76696630811452f8df38888af894f2 |
| 42-1 `2019-01-10-14-34-38-192.168.1.197.pcap` | 7573797f17aae96e3804a3cfb22d531b74c17bbae740de1e14048f89130fba37 |
| 20-1 `2018-10-02-13-12-30-192.168.100.103.pcap` | 4d0a00c33a4bf11228158baddd47c38f702731ea8d75ef1201061fc8bbd878b9 |
| 21-1 `2018-10-03-15-22-32-192.168.100.113.pcap` | 40b6928cedcda03fe5ded8a9994ec007a6d784028f37cbc00bbe3a26a7893023 |
| 3-1 `2018-05-21_capture.pcap` | c674dc0c8d584fa66e6f00c60df973c5fbacad551c850a76d75ec9952641d00b |
| 34-1 `2018-12-21-15-50-14-192.168.1.195.pcap` | 92ec7e2f6658ee4b007d0b816986c46cc0338bc5e2bec6ceaaca566c695e4699 |
| 1-1 `2018-05-09-192.168.100.103.pcap` | 8ebcd17af4e2d20b1cf7ad564760756f457a80b791a0757a2b1a624b2724969c |

Downloaded 2026-11-02 17:50 and 17:54 UTC from
`https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset/IndividualScenarios/`.
The IoT-23 download page states "You need authorization from the Stratosphere
Lab to use these files." The official dataset release on Zenodo
(DOI 10.5281/zenodo.4743746, checked 2026-11-02 via the Zenodo API) is licensed
**CC BY 4.0**, which permits use with attribution. Cite: Garcia, S., Parmisano,
A., & Erquiaga, M. J. (2020). IoT-23: A labeled dataset with malicious and
benign IoT network traffic (Version 1.0.0). Zenodo.

pcap pre-check (dpkt, `results/pcap_precheck.json`): in all 7 captures 100% of
labelled rows have their Community ID among the pcap's flows within its time
range.

## 7. Decisions

| # | Decision | Reason |
|---|---|---|
| D1 | Experiments at `submission/experiments/` | Git repo with README, checklist, code |
| D2 | Existing `.venv` read-only with `-B` | No install needed; no `__pycache__` written into the project |
| D3 | Ablation run from `experiments/ablation/` with `PYTHONPATH=code`, output `--out results/...` | Instructions forbid changing `code/`; the script's default output is `code/results_ablation` |
| D4 | Ablation defaults used unchanged | Instructions: run the full ablation if both checks match |
| D5 | Pilot 8-1, then 42-1, then 20-1 | Smallest pcaps with benign + attack |
| D6 | Label match: Community ID + ≤ 1.0 s, one-to-one | Zeek uids differ per run |
| D7 | Binary target, per-class detection rates | Attack classes not shared across captures |
| D8 | Split train {1-1, 3-1, 20-1, 42-1}, test {8-1, 21-1, 34-1} | Capture-held-out, fixed before training |
| D9 | Window features [ts − 300, ts], same local host | No look-ahead |
| D10 | Trimmed copy of the 42-1 pcap | Zeek cannot read the truncated final record |
| D11 | 34-1 kept as planned despite 38.8% labelled-row coverage | Gate defined on new-record match rate; reported as a limitation, plan not changed after seeing results |
| D12 | 8-1 kept in the Stage 4 test set although it failed the pilot gate | The gate decides whether to proceed; PLAN fixed the test set before results |

## 8. Tests

```
cd experiments/cross_log && ../../code/.venv/Scripts/python.exe -B -m unittest discover -s tests
cd experiments/ablation  && PYTHONPATH=<submission>\code ../../code/.venv/Scripts/python.exe -B -m unittest discover -s tests
```
2026-11-02 ~18:53 UTC: cross-log **13 tests OK** (Community ID 4, label match 2,
linking 1, features / leakage guard 4, end-to-end smoke 1, pcap trim 1);
ablation **6 tests OK**. Thesis's own 94 tests not rerun (code unchanged).

## 9. Final integrity check

Re-hash at 2026-11-02T18:57:05Z (`_integrity/final_sha256.txt`), `diff` with
the baseline: **30,615 files, 0 differences** (`_integrity/diff.txt` empty).
Run B, Run C, Run T, `code/` (incl. `data/processed`, `results`, `models`),
`metrics`, `predictions`, `report` and all thesis documents are unchanged.
`git status`: only `?? experiments/`.
Repeated after the Bro 2.6.4 follow-up (§4.6) at 2026-11-02T19:30:00Z and
after building and test-rendering the combined app (§10) at
2026-11-02T20:26:01Z: 30,615 files, 0 differences both times.

## 10. Presentation, push and merge (user requests after the runs)

| Step | What was done |
|---|---|
| Results page | `report/index.html` (standalone copy); also published as a private claude.ai page |
| Combined app | `lab/app.py`: loads the five original demo pages unchanged from `code/demo/pages/` and adds `lab/pages/6_ablation.py` and `7_cross_log.py`, which read only files under `experiments/`. Run with `code/demo/.venv` (Streamlit 1.66.0), `-B`, headless, `localhost:8501`. All 7 pages rendered without exceptions in Streamlit's `AppTest` |
| Original demo | Started once unchanged on `localhost:8501` (cache check `build_cache.py --check` → ok; the launcher's `verify_live_inference.py` step was skipped because it rewrites a file in `code/demo/cache`) and then replaced by the combined app |
| `.gitignore` | `experiments/.gitignore` excludes pcaps, IoT-23 logs, raw sensor output, the ET Open ruleset, the Bro source tarball and the large per-capture parquet tables (sources and hashes in §4.2, §4.6, §6) |
| Commit | `d5aad70` "Add supplementary ablation and cross-log experiments" (61 files) on `cross-log-experiment` |
| Push | `git push -u origin cross-log-experiment` to the private repo `Abdullabintarish/iot-smart-home-integrated-detection` |
| Merge | Pull request #1 into `main`, merged 2026-11-02T20:42:30Z, merge commit `9a37a62`, at the user's request **before** supervisor sign-off (stated in the PR description). The merge only adds `experiments/`; no existing file changed |

Disk: `experiments/` 1.4 GB; WSL disk image 2.5 GB
(`%LOCALAPPDATA%\wsl\{110a38be-...}\ext4.vhdx`). Total ≈ 3.9 GB.
