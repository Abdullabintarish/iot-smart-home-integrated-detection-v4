# 06 — Research Gaps and Limitations

Severity:
- **High:** limits what RQ1's answer can claim.
- **Medium:** must be stated next to the results.
- **Low:** a reporting detail.

Each item gives its evidence and whether an action is proposed. Proposal A (§2) was approved and run as Run T. Proposal B (§3) is **not implemented**.

## 1. Limitations of the executed experiment

| # | Limitation | Severity | Evidence | Already documented? |
|---|---|---|---|---|
| L1 | **No cross-source or cross-log-type correlation.** Correlation is within each capture only. With the source removed from the key, still 0 keys span two sources: the captures are independent recordings, and their shared IPs are coincidental (for example 192.168.100.1 in both datasets) | High | VR V9; R `alert_reduction.cross_source_incidents` = 0 | Yes (README §9a). The global-scope check is new |
| L2 | **Within-capture evaluation.** Train and test are interleaved in time inside the same captures; 23.88% of test events share a conversation with training events (c2 99.94%); 13.54% have an exact training duplicate (benign 86.76%). Results do not estimate performance on unseen networks or devices. A temporal hold-out (Run T) confirms the direction, but evaluation is still within-capture | High | VR V5; Run T | Partly (README §9e). The conversation overlap and Run T are new |
| L3 | **Coarse incident representation.** 4 of 7 incident features are constant by construction; 98.28% of test incidents have a vector seen in training; the single-event vector is shared by 320,638 benign and 15,923 recon training incidents | High (explains the main result) | VR V4, V5, V12 | Partly (README §9b says "zero importance"). That they are constant, and the collapse analysis, are new |
| L4 | **Large incidents dominate event-level metrics.** 7 incidents hold 78.55% of test events; the test set is 40.2% of events but 24.9% of incidents | Medium | VR V7; R `robustness.small_incidents` | Yes (README §9c) |
| L5 | **Bootstrap treats incidents as independent.** Incidents within one capture share hosts and time, so the intervals are likely too narrow. A source-level bootstrap would have only 13 clusters | Medium | R `bootstrap.note` | Yes (README §9d) |
| L6 | **Dataset fingerprint in missingness.** Argus-only features are missing for 100% of IoT-23 rows and present for 100% of Bot-IoT rows, so pooled models can identify the dataset. This affects the pooled and enriched diagnostics, not the per-source baseline | Medium | VR V4 | **New** |
| L7 | **Small classes.** Integrated training: dos 26, malware 238, c2 561 incidents; test: 13, 65, 174. Malware occurs in 2 captures only (3-1: 5,962 events; 42-1: 3) | Medium | R `integrated.train_class_counts`; VR V11 | Yes (README §9h) |
| L8 | **Class set narrower than the thesis scope.** No botnet, brute-force or theft class. DoS and DDoS are merged | Medium | VR V11 | Yes (README §9f, g) |
| L9 | **Data composition.** IoT-23 events are 56.6% recon, 40.5% benign; Bot-IoT is 99.9% attack with 3 files of 1M records each. The data are research captures (honeypot, lab, testbed), not live smart homes | Medium | 03 §2 | Yes (README §9k) |
| L10 | **One configuration, one seed**; no hyperparameter search | Medium | R `model_config` | Yes (README §9i) |
| L11 | **Unequal training sets** (408,412 events vs 120,825 incidents) and a different training unit for each condition | Low | R | Yes (README §9j) |
| L12 | **Single log type, flow level.** Only Zeek conn logs and Argus flows; no IDS alerts, DNS, HTTP or device logs. "Alert" here means a flow record, not an IDS alert | Medium | 03 §2; IoT-23 `bro/` listing (2026-11-02) | Partly |
| L13 | **Offline batch processing.** No real-time, SIEM (Wazuh) or storage-layer (Elasticsearch/MongoDB) component | Low (for RQ1) | Code | Yes (PTC item 7) |
| L14 | **Outcome measures stop at detection and alert counts.** Response time, analyst effort and risk were not measured | High (for the title's "risk mitigation") | 05 §4 | **New** framing |

## 2. Proposal A: supplementary temporal hold-out evaluation (addresses L2)

**Why:** it is the smallest change that tests generalisation beyond interleaved windows while keeping the fragmented baseline valid. A capture-held-out split is **not** suitable:
- one model per capture cannot predict a capture it never saw, so the baseline would be undefined;
- malware exists in essentially one capture.

**Design:** within each source, events with a timestamp after that source's 75th time percentile go to test, the rest to train.
- **Incidents must not straddle the cut.** The side of the cut has to become part of the correlation key, so an incident crossing the boundary is split into two.
- **Why this is unavoidable:** data_36 lies inside a single 300 s window and data_10 spans two (computed 2026-11-02), so the cut cannot fall between whole incidents.
- **Feasibility** (TS, counted at event level): every class keeps test events (benign 125,218; c2 4,270; dos 503,405; malware 1,334; recon 418,620). Six small source/class cells would have no test events, for example c2 in Capture-20-1 and malware in Capture-42-1.

**Changes required:**
- `preprocess.assign_split`: an optional `temporal` mode, with a per-source cut-off taken from a timestamp pre-pass;
- `correlate.correlation_key`: add the split side to the key;
- a CLI flag;
- unit tests.

The default behaviour is unchanged.

**Run:** in a **copy** of `submission/code`, outputs under `thesis_final_validation/supplementary_temporal/`. `run_all.ps1` empties `results/`, so it must not run in place. It costs about 6 minutes and about 4 GB of RAM. Run B stays the primary result; the temporal run is reported as a robustness check.

**Value:** it shows whether the direction of the main result (fragmented > integrated) holds when the test data are strictly later in time.

**Expected caveat:** an IoT-23 attack phase that starts late can be missing from training.

**Status: done (approved, run 2026-11-01 UTC as Run T).**
- **Result:** the direction of the main result holds (fragmented F1 0.9992, FPR 0.0044 vs integrated F1 0.7711, FPR 0.0965). The expected "cut artefact" appeared, but in Bot-IoT DoS rather than in IoT-23: truncated flood tails were predicted recon.
- **Details:** `supplementary_temporal/RESULTS.md`.

## 3. Proposal B: controlled cross-log-type correlation (conn + DNS) (addresses L1/L12 partly)

**Feasibility with current data: not feasible.**
- Conn records carry no DNS query name or answer. IoT-23 has 5,143 DNS connection records, all benign; Bot-IoT data_1 has 1,285 port-53 flows (VR V10).
- The published IoT-23 `bro/` folders contain only `conn.log.labeled`. This was checked for Captures 34-1 and 8-1 on 2026-11-02.

**Feasible with new data, at moderate effort:**
- The IoT-23 scenario folders publish the original pcaps (for example Capture-34-1: a 120 MB `.pcap`, plus `suricata/` and `.dnstop` files).
- Running Zeek on the pcaps of 2–3 captures with c2 traffic (for example 34-1 and 8-1) would yield `conn.log` and `dns.log` from the same traffic.
- A rule would then link a DNS answer to the next connection from the same host to the resolved IP within the window.

**Obstacles:**
- **Zeek is not installed** on this Windows machine; it would need WSL or Docker.
- **Labels must be transferred.** Regenerated `uid`s will not match the labelled conn log, so labels would have to be moved across by 5-tuple and timestamp.
- **DNS records carry no labels of their own.**
- The `suricata/` folder could provide a third log type (IDS alerts); its contents were not inspected.

**Value to the thesis:**
- It would demonstrate cross-log-type correlation, which the methodology (thesis §3.2 Stage 3) describes.
- It would add behavioural incident features (for example "connection to a freshly resolved domain"), which 04 §5 identifies as the missing ingredient.

**Limitation:** it would still be **one sensor's view** of one capture, not independent distributed sources.

**Status: not implemented. Recommended as future work, or as an optional extension if time permits; needs approval.**

## 4. Future research opportunities

1. **Simultaneously recorded multi-source data.** True cross-source correlation needs a testbed where router, IDS, device and cloud logs observe the same hosts at the same time.
2. **Behaviour-rich incident features.** Aggregate event features per incident (port/byte/flag statistics, service mix). Or adopt the enriched design (event features + incident context) as the integrated condition, evaluated per source to keep the comparison like-for-like.
3. **Evaluation on unseen networks.** Capture- or dataset-held-out testing with harmonised features, so that missingness cannot identify the dataset.
4. **Operational outcomes.** Measure analyst triage time and workload with incident vs event views (a user study), and link detection outcomes to a risk model (likelihood × impact) to address "risk mitigation" directly.
5. **Statistical robustness.** Multiple seeds, and hierarchical (capture-level) resampling with more captures.
6. **Real-time integration.** Streaming correlation in a SIEM pipeline (for example Wazuh), as the thesis literature review envisages.
