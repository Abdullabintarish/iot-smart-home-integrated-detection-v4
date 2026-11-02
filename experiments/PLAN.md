# Plan — ablation and cross-log experiment

Written 2026-11-02, before any Stage 3/4 output existed. Sections 4 and 5 are
fixed here **before any training**. They must not be changed after results are
seen; any later change is logged in `RUN_LOG.md` with its reason.

All new work is under `experiments/` on Git branch `cross-log-experiment`
(later pushed and merged into `main` at the user's request; see
`RUN_LOG.md` §10).

## 1. Project understanding (Stage 1)

- Thesis pipeline (`code/`): IoT-23 Zeek conn.log (10 captures) + Bot-IoT CSV
  (3 files) → 4,211,383 events → Stage 3 rule-based correlation (same source,
  src IP, dst IP, proto, 300 s tumbling window) → 704,090 incidents. A
  fragmented per-source baseline and an integrated incident model are compared.
- Cited run: **Run B** (`metrics/stage5_report.json`). Run C reproduced it
  (`code/results`). Run T is the temporal hold-out in
  `../thesis_final_validation/supplementary_temporal/`. None of these is touched.
- Known limitation that motivates this work: every incident is within one
  source file (0 cross-source incidents, README §9a). The thesis did not test
  correlation across log *types*.
- Required inputs found: `code/data/processed/stage3_events/` and
  `code/data/processed/stage2_feature_plan.csv` exist. They are under `code/`,
  not at the repository root.

## 2. Stage 2 — ablation

`experiments/Ablation_Package.zip` does not exist, and a search of the whole
C: drive found no file named like `*blation*`. Stage 2 cannot start. It is
recorded as **blocked** and no ablation number is reported. When the package
is supplied, the steps are as in the instructions (unzip to
`experiments/ablation/`, `PYTHONPATH=code`, output to
`experiments/ablation/results/`, unit tests, quick check seed 42 / 300 s, gate
on 704,090 groups and 1,463,143 novel events, then the full ablation).

## 3. Stage 3 — cross-log pilot

- Candidates: IoT-23 captures whose labelled `conn.log` the thesis already
  uses, so the labels are the same files (server copies verified byte-identical
  to `code/data/raw_combined`). Smallest pcap first.
- Pilot capture: **CTU-IoT-Malware-Capture-8-1** (2.0 MB pcap; 2,181 benign and
  8,222 C&C labelled flows). Fallbacks, in order: 42-1 (2.8 MB), 20-1 (3.9 MB),
  21-1 (3.9 MB). 44-1 (1.7 GB pcap) and Honeypot 4-1 (no pcap) are excluded.
- Sensors (`cross_log/tools/run_sensors.sh`, Linux): Zeek ≥ 6 with
  `policy/protocols/conn/community-id-logging` → `conn.log`, `dns.log`;
  Suricata ≥ 7 with the packaged default `suricata.yaml` with only
  `community-id: true` changed → `eve.json`. One ET Open ruleset
  (`emerging.rules.tar.gz` for the installed Suricata version), downloaded once,
  hashed, and never edited; the script refuses to run if its hash changes.
- Label match: Community ID (computed for IoT-23 rows) + start time within
  1.0 s, one-to-one, closest first. Match rate = matched new conn records / all
  new conn records (labelled-row coverage is reported as well).
- Linking: Community ID first (conn + its DNS rows via `uid` + alerts with the
  same Community ID form one flow group, never split), then capture + local
  host + 300 s tumbling bucket of the flow group's first timestamp. Local host
  = the private endpoint, else the originator.
- Gate for Stage 4: benign and attack present, ≥ 90% match rate, and ≥ 1
  incident with ≥ 2 source types. Otherwise try 42-1, then 20-1, then stop.

## 4. Stage 4 — design fixed before training

**Captures and split (capture-held-out).** Seven IoT-23 captures, all used by
the thesis, about 314 MB of pcap in total (well under 50 GB).

| Partition | Captures | Labelled classes (thesis mapping) |
|---|---|---|
| Train | 1-1, 3-1, 20-1, 42-1 | benign, recon, c2, malware |
| Test (final, fixed) | 8-1, 21-1, 34-1 | benign, c2, dos, recon |

Reasoning: test captures each contain benign traffic (for FPR on unseen
benign), and 34-1 adds DDoS, which is absent from training, as an honest
generalisation probe. Each incident is inside one capture, so linked records
are never split between partitions. The test set is not changed after results.

**Unit and target.** One row per Zeek conn record matched to an IoT-23 label.
Target is binary (malicious = 1, benign = 0), because the attack classes are
not shared across all captures. Per-class results are the detection rate for
each true thesis class (`_zeek_label` mapping from `code/pipeline/ingest.py`).

**Features** (only information at or before the conn record's start `ts`):

| Condition | Columns |
|---|---|
| A | conn: duration, orig/resp bytes, missed_bytes, orig/resp pkts, orig/resp IP bytes, responder port; proto, service, conn_state (one-hot, vocabulary from training, max 30 levels + other) |
| B | A + DNS of the same local host in [ts − 300, ts]: query count, unique domains, NXDOMAIN count, mean query length |
| C | A + alerts of the same local host in [ts − 300, ts]: count, highest severity (4 − Suricata severity), counts per top-10 alert category from training alerts + other |
| D | A + B + C features |

Never used: labels, detailed labels, attack names, IP addresses, originator
port, uid, Community ID, raw timestamps, capture name (enforced by
`experiment.check_no_forbidden`, unit-tested). Alerts raised later in the same
flow are not used, because they come after the connection's start time.

**Model.** Thesis Random Forest settings: 300 trees, max_depth 24,
min_samples_leaf 2, class_weight balanced_subsample; at most 60,000 training
rows per class, sampled per seed. Preprocessing (category vocabularies,
missing → −1) is fitted on the training sample only. Same sample, test set and
settings for all four conditions within a seed.

**Seeds.** 42, 1, 2, 3, 4 (model and training sample).

**Evaluation.** Main window 300 s. Report per condition and seed: macro F1,
FPR, FNR, per-class detection rate, and FPR on unseen benign (test benign rows
whose condition-A feature vector does not occur in training). Report
mean ± SD over seeds, and an incident-clustered percentile bootstrap (1,000
replicates, RNG seed 42, seed-42 models) of macro F1 per condition and of
B − A, C − A and D − A.

## 4a. Addendum (2026-11-02, after the runs; no design change)

- Stage 2: the package was later supplied as three files and run as in §2
  (`RUN_LOG.md` §3).
- Stage 3: 8-1 failed the gate (no DNS, no alerts); 42-1 failed on a truncated
  pcap; 20-1 passed. 42-1 was then processed from a byte-exact trimmed copy.
- Stage 4 ran exactly as in §4. Split, features, model, seeds and metrics were
  not changed after results were seen. Deviations in the data (34-1 DDoS
  coverage) are reported in `RUN_LOG.md` §4.5, not corrected.

## 4b. Robustness analyses (added 2026-11-03)

Written after the primary Stage 4 results were seen and **before** any of the
analyses below were run. The primary analysis (§4) and its results are not
changed; these test whether its findings hold. Code: `cross_log/src/robustness.py`.

| ID | Question | Design |
|---|---|---|
| R0 | Is the feature cache correct? | Rebuild the primary seed-42 run from the cache; predictions must be identical |
| R1 | Is the A–D ordering a seed artefact? | Primary split, 20 seeds (42, 1–19); per-seed paired differences, sign counts, Wilcoxon signed-rank test |
| R2 | How wide is the uncertainty when seed variance is included? | Two-level bootstrap on R1: each replicate draws one of the 20 seeds and resamples test incidents; 2,000 replicates |
| R3 | Does it depend on the one train/test split? | Leave-one-capture-out over all captures with Stage 3 output (7, plus 48-1 and 49-1 if they pass the Stage 3 gate), 5 seeds; per-fold and pooled results |
| R4 | Is the "connection start" rule too strict? | DNS / alert windows anchored at connection end (ts + duration), when Zeek writes the record; primary split, 5 seeds |
| R5 | Does the 300 s window matter? | Windows of 60 s and 900 s; primary split, 5 seeds |

Everything else (features, model, sampling, preprocessing, metrics) is as in
§4. Alert categories are the top 10 of each analysis's own training captures.
All results are reported, whichever way they go.

Additional captures for R3: CTU-IoT-Malware-Capture-48-1 (1.1 GB pcap) and
49-1 (1.3 GB pcap), the two smallest remaining IoT-23 malware captures with
pcaps under 1.5 GB. Larger captures (3.5–21 GB pcaps) were not added.

## 4c. Addendum after the robustness runs (2026-11-03)

- An alert-timestamp bug was found while running R0–R5 (`RUN_LOG.md` §5.1).
  After the fix, Stage 3, the primary Stage 4 analysis (§4, unchanged design)
  and R0–R5 were rerun; the earlier outputs are kept as superseded.
- 48-1 passed the Stage 3 gate and was added to R3. 49-1 failed the gate
  (new-record match rate 89.84% < 90%) and was excluded, as fixed in §4b.

## 5. Outputs

- `RUN_LOG.md` — commands, versions, hashes, decisions, failures.
- `THESIS_ADDITIONS.md` — proposed text, labelled *Additional analysis,
  pending supervisor approval*.
- `cross_log/results/` — JSON results; `cross_log/src`, `cross_log/tests`.
- `_integrity/` — SHA-256 baseline and final comparison of existing files.
