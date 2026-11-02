# 05 — Cybersecurity Risk Mitigation Contribution

This document relates the verified findings (04) to the thesis title and its objectives (Thesis Part 1, §1.4). It does not change the title or RQ1. "Demonstrated" means directly measured in Run B; "conceptual" means argued or designed but not measured.

## 1. Five concepts that must be kept apart

| Concept | Meaning in this thesis | What the project did | Status |
|---|---|---|---|
| **Integrated information management** | Collecting heterogeneous logs into one normalised structure | 13 sources from two datasets with different schemas (Zeek conn logs, Argus flows) mapped to one canonical schema and one label vocabulary; one train-fitted normalisation | **Demonstrated** (implementation; unit-tested) |
| **Event correlation** | Grouping related events into incidents by shared attributes and time | Rule-based correlation (src IP, dst IP, protocol, 300 s window), within each capture | **Demonstrated within captures**; across log types and across sources **not demonstrated** |
| **Cyberattack detection** | Classifying traffic as benign or a specific attack class | Random Forest under two monitoring conditions on identical held-out events | **Demonstrated and measured**: the integrated condition is *less* accurate (macro F1 0.8341 vs 0.9955; FPR 0.1021 vs 0.0046) |
| **Security visibility** | The analyst's ability to see what is happening, as a whole | Incidents compress the event stream; the demo app shows events, incidents and predictions | **Partly**: workload reduction (alert volume) is measured; visibility itself (analyst understanding, situational awareness) is **not measured** |
| **Cybersecurity risk mitigation** | Reducing the likelihood or impact of harm | No response, blocking, containment or analyst study was performed | **Conceptual only** |

## 2. What the results support

1. **A working integration framework.** A reproducible, streaming five-stage pipeline integrates two public IoT datasets with different log formats into one schema, with leakage-controlled preprocessing. Evidence: code, 94 unit tests, and two byte-identical runs on different hardware (01 §2).
2. **Alert volume reduction through correlation.** 4,211,383 events → 704,090 incidents (83.28%), of which IoT-23 contributes 42.09% and Bot-IoT 99.91%. Fewer items to review is a plausible *precondition* for faster triage; it is not itself shown to reduce risk.
3. **An honest, negative detection result.** Under a fair comparison (same events, same RF, same metrics), detection on incident summaries is worse than per-source event detection. The difference is robust across four checks.
4. **A diagnosis of why.** The detection loss comes from coarse incident features, not from correlation merging classes:
   - propagation ceiling F1 0.9989;
   - 111 mixed-label incidents;
   - all false positives in multi-event benign incidents.

   This identifies what an integrated detector must preserve, namely event-level behavioural content. That is a methodological contribution for designing integrated monitoring.
5. **A validated evaluation protocol.** It includes the following, all of which the original implementation lacked (Run A defects):
   - a grouped split with 0 incidents straddling train and test;
   - train-only fitting;
   - one test set for all models;
   - incident-clustered bootstrap;
   - duplicate-vector analysis;
   - leakage audit.

## 3. Mapping to the thesis objectives (§1.4)

| Objective | Evidence | Status |
|---|---|---|
| Analyse distributed logs and alerts in IoT smart home environments | Inventory of 13 captures, class composition, schema differences (03 §2) | Met. The data are public research captures (honeypot, lab and testbed), not live homes |
| Establish a fragmented baseline | 13 per-source models (03 §7) | Met |
| Design a unified information management framework | Stages 1–3 | Met |
| Implement and evaluate it | Run B, verified twice | Met |
| Compare using defined metrics | 04 §1–4 | Met. The comparison favours the baseline on detection metrics and the framework on alert volume |

## 4. Claims the thesis must **not** make

The following were not measured. Each would need a new study.

- That the framework **blocks, prevents or contains** attacks. There is no response component.
- That it **reduces incident response time** or analyst workload in practice. Alert counts were measured; analyst time was not.
- That it **reduces real-world cybersecurity risk** in smart homes. No deployment, risk model or impact measurement was done.
- That integration **improves detection accuracy or lowers false positives**. Both moved in the opposite direction.
- That it achieves **cross-source** correlation or **cross-source visibility**. There were 0 cross-source incidents.
- That results generalise to **unseen networks or devices**. Training and test share captures (06 §1).
- That it detects **botnet**, brute-force or theft classes. None occurs in the data.
- That it works in **real time**. Processing was an offline batch.

## 5. Defensible wording for the risk-mitigation contribution

> The framework contributes to cybersecurity risk mitigation *indirectly* and *conditionally*. Correlating distributed IoT flow logs into incidents reduced the number of items requiring review by 83.28% overall (42.09% for IoT-23 traffic). This addresses the alert-overload problem identified in the literature. However, in this experiment, detecting threats from incident-level summaries was less accurate than detecting them from isolated per-source event logs (macro F1 0.834 vs 0.996; false-positive rate 10.2% vs 0.5%). Integration therefore supports risk mitigation through alert consolidation only if the integrated representation keeps event-level behavioural detail. Whether consolidation shortens response or reduces harm was not measured.

The figures are from Run B; see 04 §1 and §6.
