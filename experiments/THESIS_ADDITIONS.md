# Proposed thesis additions

> **Additional analysis, pending supervisor approval.**
> Nothing here has been inserted into the thesis. Every number names its source
> file; paths are relative to `submission/experiments/`. Commands, versions and
> hashes are in `RUN_LOG.md`.

Two supplementary analyses are proposed:

- **A. Controlled feature ablation** on the Run B data: what incident context
  adds when everything else is held constant.
- **B. Cross-log correlation**: whether linking connection logs, DNS logs and
  IDS alerts improves detection on unseen captures.

---

## A. Controlled feature ablation

### A.1 Methods (proposed text)

To isolate the effect of incident context, a controlled ablation was run on the
saved Run B data (4,211,383 events; the same 1,692,332 held-out test events).
Every feature set used the same pooled Random Forest settings as Run B (300
trees, max_depth 24, min_samples_leaf 2, class_weight balanced_subsample), the
same training sample per seed (at most 60,000 events per class) and the same
test events; only the input features changed. Five feature sets were compared:
the 20 Run B event features (event_only); the three incident features
n_events, span_s and events_per_s (incident_only); both together
(event_plus_incident); and versions restricted to the 11 event features present
in both datasets (shared_event, shared_plus_incident), which remove the
dataset fingerprint carried by missing values. Incident features were computed
with the pipeline's own correlation key at windows of 60, 150, 300, 600 and
900 s, inside each partition so that no incident crosses train and test.
Windows of 600 and 900 s are cut at the partition boundary. Each configuration
was run with seeds 42, 1, 2, 3 and 4. Before the full run, a check confirmed
that the saved data reproduce Run B: 704,090 incidents at 300 s and 1,463,143
test events with a feature vector not seen in training
(`ablation/results/quick_check/checks.json`).

### A.2 Results

Table A1 — Macro F1 and FPR, mean ± SD over 5 seeds, all 1,692,332 test
events. Source: `ablation/results/full/ablation_summary.csv` (subset `all`),
`thesis_table.md`.

| Window (s) | Feature set | Macro F1 | FPR | Window cut |
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

Table A2 — Paired incident-clustered bootstrap, 300 s, seed 42, 1,000
replicates, 95% percentile intervals. Source:
`ablation/results/full/bootstrap.json`.

| Comparison | Macro F1 difference | FPR difference |
|---|---|---|
| incident_only − event_only | [−0.1761, −0.1072] | [+0.0836, +0.0909] |
| event_plus_incident − event_only | [−0.0014, +0.0048] | [+0.0060, +0.0081] |
| shared_plus_incident − shared_event | [−0.0021, +0.0016] | [+0.0080, +0.0099] |

Table A3 — Test events whose feature vector does not occur in training
(n = 1,463,143), 300 s, mean over 5 seeds. Source: `ablation_summary.csv`,
subset `novel_vector`.

| Feature set | Macro F1 | FPR |
|---|---|---|
| event_only | 0.9917 | 2.81% |
| shared_event | 0.9954 | 1.48% |
| incident_only | 0.7521 | 68.59% |
| event_plus_incident | 0.9880 | 8.41% |
| shared_plus_incident | 0.9903 | 7.11% |

### A.3 Interpretation (proposed)

With the model, sample and test events held fixed, adding incident context to
the event features does not change macro F1 (the 300 s interval for the
difference includes zero) but raises the false-positive rate, from 0.38% to
1.14% at 300 s (interval for the FPR difference [+0.60, +0.81] percentage
points), and the increase is larger on test events with novel feature vectors.
Incident features alone score much lower than event features alone at every
window. This supports, under controlled conditions, the Run B conclusion that
within-capture incident context did not improve detection, and it locates the
cost in benign events that belong to multi-event incidents
(`ablation_summary.csv`, subset `multi_event_benign`: FPR 8.1% for
event_plus_incident vs 2.6% for event_only at 300 s). The result is stable
across windows and seeds.

These numbers are not directly comparable with the Run B headline figures: the
ablation uses one pooled model on events, while Run B's baseline uses 13
per-source models and Run B's integrated model is trained on incidents.

---

## B. Cross-log correlation

> **Scope.** This tests correlation **across log types** (Zeek connection logs,
> Zeek DNS logs and Suricata alerts) produced from the **same** packet capture.
> It does **not** test independent device, gateway and cloud sensors.

### B.1 Methods (proposed text)

Seven IoT-23 captures already used in the thesis (CTU-IoT-Malware-Capture-1-1,
3-1, 8-1, 20-1, 21-1, 34-1 and 42-1) were re-processed from their original
packet captures. Zeek 9.0.1 produced connection and DNS logs and Suricata 7.0.3
produced alerts with one fixed Emerging Threats Open ruleset (52,803 enabled
rules; tarball SHA-256 d5330ebe…, newest rule dated 2026-10-30), used
unchanged for all captures. Community ID was enabled in both tools. New
connection records were labelled by matching them to the published IoT-23
labelled connection logs on Community ID and start time (within 1 s,
one-to-one), and labels were mapped to the thesis classes with the thesis's own
mapping. Records were linked first by Community ID (a connection, its DNS
records and its alerts) and then by local host within the same 300-second
window.

Four conditions were compared on the same capture-held-out test set (captures
8-1, 21-1 and 34-1; training captures 1-1, 3-1, 20-1 and 42-1), with the same
training sample per seed, the thesis's Random Forest settings and seeds 42, 1,
2, 3 and 4: connection features only (A); plus DNS features (B: query count,
unique domains, NXDOMAIN count, mean query length); plus alert features (C:
alert count, highest severity, counts per alert category); and all three (D).
DNS and alert features use only records of the same host in the 300 seconds up
to and including each connection's start time. Labels, IP addresses, ports of
the originator and timestamps were never features. Preprocessing was fitted on
training data only. The split, features and metrics were fixed before training
(`PLAN.md` §4). The target is binary (malicious vs benign), because the attack
classes are not shared across captures.

### B.2 Results

Table B1 — Record generation, label matching and linking per capture. Source:
`cross_log/results/stage3_<capture>.json`.

| Capture | Zeek conn | Matched to labels | Match rate | DNS | Alerts | Incidents | With ≥ 2 record types |
|---|---|---|---|---|---|---|---|
| 1-1 | 1,008,748 | 1,008,748 | 100.00% | 19 | 41 | 1,352 | 21 |
| 3-1 | 156,103 | 156,103 | 100.00% | 12 | 50,529 | 429 | 2 |
| 8-1 | 10,403 | 10,403 | 100.00% | 0 | 0 | 278 | 0 |
| 20-1 | 3,209 | 3,209 | 100.00% | 808 | 0 | 24 | 23 |
| 21-1 | 3,286 | 3,286 | 100.00% | 2,578 | 0 | 58 | 56 |
| 34-1 | 8,990 | 8,988 | 99.98% | 348 | 7,877 | 165 | 15 |
| 42-1 | 4,426 | 4,426 | 100.00% | 1,841 | 2,019 | 37 | 35 |

Only one incident (in 42-1) contains all three record types. The pilot capture
8-1 contains no DNS and raises no alert, so it has no cross-source incident.

Table B2 — Conditions A–D on the capture-held-out test set (22,677 connection
records: 14,942 c2, 7,376 benign, 237 dos, 122 recon). Mean over 5 seeds.
Source: `cross_log/results/stage4_results.json`.

| Condition | Macro F1 (mean ± SD) | FPR | FNR | FPR on unseen benign (n = 1,964) |
|---|---|---|---|---|
| A conn | 0.3346 ± 0.1973 | 0.27% | 89.12% | 1.03% |
| B conn + DNS | 0.5016 ± 0.1688 | 0.43% | 70.61% | 1.63% |
| C conn + alerts | 0.3164 ± 0.1564 | 0.28% | 91.80% | 1.03% |
| D conn + DNS + alerts | 0.6187 ± 0.1355 | 0.46% | 55.61% | 1.68% |

Table B3 — Paired difference in macro F1 against A, per seed (42, 1, 2, 3, 4),
and incident-clustered bootstrap interval for the seed-42 models (501 test
incidents, 1,000 replicates). Source: `stage4_results.json`,
`stage4_bootstrap.json`.

| Comparison | Per-seed differences | 95% interval (seed 42) |
|---|---|---|
| B − A | +0.109, +0.103, +0.341, +0.222, +0.061 | [+0.007, +0.228] |
| C − A | +0.000, +0.001, +0.000, −0.000, −0.092 | [−0.000, +0.000] |
| D − A | +0.343, +0.339, +0.239, +0.339, +0.160 | [+0.283, +0.413] |

Table B4 — Detection rate per true class (benign: share kept benign), mean ±
SD over 5 seeds. Source: `stage4_results.json`.

| Class (n) | A | B | C | D |
|---|---|---|---|---|
| benign (7,376) | 0.997 ± 0.000 | 0.996 ± 0.002 | 0.997 ± 0.000 | 0.995 ± 0.002 |
| c2 (14,942) | 0.111 ± 0.246 | 0.300 ± 0.230 | 0.083 ± 0.185 | 0.454 ± 0.206 |
| dos (237) | 0.021 ± 0.000 | 0.027 ± 0.013 | 0.021 ± 0.000 | 0.039 ± 0.016 |
| recon (122) | 0.023 ± 0.014 | 0.023 ± 0.015 | 0.025 ± 0.014 | 0.026 ± 0.015 |

### B.3 Interpretation (proposed)

On captures not seen in training, all four conditions detect few attacks: the
false-negative rate is between 56% and 92%, while false positives stay below
0.5%. The training captures contain mostly port-scan attacks and the test
captures mostly command-and-control traffic, so this is a hard transfer
setting. Within it, adding DNS context improved macro F1 in every seed, and
adding DNS and alert context together gave the largest improvement in every
seed (D − A between +0.16 and +0.34). Alert context on its own did not help.
The gains come mainly from detecting more c2 connections; DDoS and port-scan
connections in the test captures remained almost entirely undetected.
Performance depends strongly on the seed (seed 4 differs markedly from the
others), and the bootstrap interval covers only the seed-42 models, so the
size of the improvement is uncertain even though its direction is consistent.

### B.4 Limitations

1. Log types from one capture point (Zeek and Suricata see the same packets),
   not independent device, gateway and cloud sensors.
2. Record granularity differs from IoT-23 in one capture. In 34-1, IoT-23's
   log has one row per packet (14,159 rows) for a single DDoS flow; Zeek 9.0.1
   and, checked separately, Bro 2.6.4 both record it as 6 connections. Only
   237 of 14,394 DDoS rows therefore enter the test set (labelled-row coverage
   38.8% for 34-1; 100% for the other captures). This is not a Zeek-version
   effect; its cause in IoT-23's processing is unknown. Source:
   `cross_log/results/old_zeek_check_34-1.json`, `RUN_LOG.md` §4.6.
3. Alerts: only alerts at or before a connection's start are used, so an alert
   raised later in the same connection is not used. Three of seven captures
   produce no alert at all.
4. The ET Open ruleset (2026) postdates the 2018–2019 captures.
5. Binary target; DDoS occurs only in test capture 34-1, with no training
   support. Training c2 support is only 35 rows.
6. Seven captures from one laboratory, each with one infected device; high
   seed variance; bootstrap intervals for seed 42 only.
7. Capture 42-1's pcap ends in a truncated packet; a byte-exact copy without
   the final 61 bytes was used.
8. Pilot capture 8-1 failed the cross-source gate; Stage 4 proceeded on the
   second fallback capture (20-1), as the protocol allowed.
