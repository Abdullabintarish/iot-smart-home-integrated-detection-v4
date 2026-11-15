# Chapter 6: Conclusion and Future Work

> **Drafting notes (delete before submission).**
> - The numbers below are summarised from Chapter 5, where each one is linked to its result file.
> - `[CITE: …]` marks where an external citation is needed.

## 6.1 Summary of the Research

This thesis investigated how the integration and correlation of distributed IoT logs and alerts affect cybersecurity threat detection accuracy in IoT-enabled smart home networks (RQ1).

A five-stage framework was implemented as a reproducible Python pipeline: collection, preprocessing and normalisation, event correlation, threat detection, and evaluation. It processed 4,211,383 flow events from 13 sources in two public datasets (IoT-23 and Bot-IoT). The integrated framework was compared with a fragmented per-source baseline under identical conditions.

The primary result was then tested by three further experiments:

- a temporal hold-out;
- a controlled feature ablation;
- a cross-log-type correlation experiment on networks not seen in training.

## 6.2 Research Objectives Achieved

**Table 6.1 — Objectives from Thesis Part 1 §1.4**

| Objective | Outcome | Where shown |
|---|---|---|
| Analyse distributed logs and alerts generated in IoT-enabled smart home environments | 13 sources and two log formats (Zeek connection logs, Argus flows) analysed; three log types (connection, DNS, IDS alerts) produced from IoT-23 packet captures | Ch. 3 §3.3; Ch. 5 §5.8.1 |
| Establish a baseline fragmented monitoring model | 13 per-source models (11 Random Forests + 2 constant predictors) | Ch. 3 §3.6 |
| Design a unified information management framework | Canonical schema, train-only normalisation, rule-based correlation into incidents; extended to cross-log-type linking with Community ID | Ch. 3 §3.2–3.5, §3.11.3 |
| Implement and evaluate the proposed framework | Implemented, unit-tested (94 tests) and reproduced byte-for-byte on a second machine | Ch. 4 |
| Compare performance using defined evaluation metrics | Accuracy, macro precision, recall and F1, FPR, FNR, confusion matrices, alert reduction, processing time, bootstrap intervals | Ch. 5 |

All five objectives were met. The comparison did **not** confirm the expected improvement in detection accuracy (Part 1 §1.6).

## 6.3 Main Experimental Findings

1. **Primary comparison (Run B).** The fragmented baseline outperformed the integrated incident-level model on every metric:
   - macro F1: 0.9955 vs 0.8341;
   - false-positive rate: 0.46% vs 10.21%.
2. **Alert consolidation.** Correlation reduced the number of items to review by 83.28% overall, and by 42.09% for IoT-23 traffic.
3. **Temporal validation (Run T).** The result held when the test data were strictly later in time (macro F1 0.9992 vs 0.7711).
4. **Diagnosis.** The loss comes from the coarse incident representation, not from correlation:
   - correctly labelled incidents would lose almost nothing (ceiling macro F1 0.9989);
   - all integrated false positives came from benign multi-event incidents whose count, span and rate resemble scanning.
5. **Controlled ablation.** With everything else fixed:
   - incident features alone lost 0.11–0.18 macro F1;
   - adding incident features to event features left macro F1 unchanged and roughly tripled the FPR (0.38% → 1.14%).
6. **Cross-log correlation.** Connection, DNS and IDS-alert records were linked successfully (571 of 2,344 incidents combine at least two log types). On unseen networks:
   - adding DNS and alert context raised mean macro F1 from 0.335 to 0.586;
   - the effect varied between networks, and absolute detection remained low;
   - part of the gain could not be attributed to the correlated log content.

   DNS context provided the clearest evidence of useful cross-log information.

## 6.4 Contributions

1. **A reproducible integrated monitoring pipeline** for public IoT datasets. It provides a canonical schema, leakage-controlled preprocessing, deterministic rule-based correlation and a fair comparison protocol. Its predictions were reproduced byte-for-byte on different hardware.
2. **A controlled, negative result with its explanation.** Under a fair comparison, detecting threats from incident summaries was less accurate than event-level detection. The study locates the cause in the representation, not in correlation. This identifies what an integrated detector must preserve: event-level behavioural content.
3. **Separation of two benefits that are often treated as one.** Alert-volume reduction and detection accuracy moved in opposite directions. Integrated monitoring therefore needs to be evaluated on both, not on one alone [CITE: literature that reports both together, e.g. Maosa et al., 2024].
4. **A cross-log-type correlation method for IoT-23.**
   - Community ID linking of Zeek connection and DNS logs with Suricata alerts;
   - label transfer at 99.98–100% match rates;
   - a capture-held-out evaluation, pre-specified before training.

   This extends the use of IoT-23 beyond its published connection logs.
5. **A transparent evaluation record.** It includes pre-specified designs, robustness analyses, a documented and corrected software defect, integrity checks of all existing results, and a mapping from every reported number to its source file.

## 6.5 Limitations

The main limitations are summarised here. Details and evidence are in `Academic_Limitations.md`.

- **No independent multi-source data.** Correlation was within each source in Run B, and across log types derived from one packet capture in the cross-log experiment.
- **Research datasets.** The data are laboratory, honeypot and testbed captures, not live smart homes.
- **Limited test of unseen networks.** Only the cross-log experiment tested unseen networks, with 7–8 small captures and only 35 C&C training rows.
- **Limited class coverage.** There are no botnet, brute-force or theft classes.
- **Limited statistics.** Run B used one seed and one configuration, and its bootstrap intervals are likely too narrow.
- **Offline processing.** There is no SIEM or real-time component.
- **Risk mitigation was not measured directly.**

## 6.6 Relationship to Cybersecurity Risk Mitigation

The thesis title refers to risk mitigation. The study supports it **indirectly and conditionally**.

- **What correlation offers.** Correlation can reduce the number of items an analyst must review, which addresses the alert-overload problem identified in the literature.
- **The condition.** This only supports risk mitigation if the detection component keeps event-level behavioural detail. A monitoring design that classifies only incident summaries would have produced about 22 times more false positives in this experiment, which works against mitigation.
- **The recommended design** for IoT smart home monitoring is therefore:
  - detect threats at event level;
  - use correlation to group, prioritise and present the results;
  - add context from other log types, such as DNS, where it is available.
- **What was not measured.** Whether this design shortens response time or reduces harm was not measured. That remains a question for future work.

## 6.7 Recommendations for Future Work

1. **Simultaneously recorded multi-sensor data.** Build or use a smart-home testbed in which device, gateway, IDS and cloud logs observe the same hosts at the same time. This would allow true cross-source correlation [CITE: candidate datasets or testbeds].
2. **Behaviour-rich incident features.** Aggregate event-level content per incident, such as port, byte and flag statistics and service mix. An alternative is to make the event + context design the integrated condition, evaluated per source.
3. **More networks and more attack data for unseen-network evaluation.**
   - Use more IoT-23 captures, and other datasets with harmonised features.
   - Include enough C&C traffic in training.
   - Use capture-level (hierarchical) resampling.
4. **Controls for absence-of-context effects.** In cross-log experiments, add a placebo condition with constant or permuted context columns, and report results separately for networks with and without each log type.
5. **Operational outcomes.** Measure analyst triage time and workload with incident and event views (a user study), and link detection outcomes to a risk model (likelihood × impact) [CITE: risk assessment standard, e.g. NIST SP 800-30].
6. **Real-time integration.** Implement streaming correlation in a SIEM, as envisaged in the literature review (for example Wazuh [CITE: Manzoor et al., 2024]), and measure latency and resource use on gateway-class hardware.
7. **Wider class coverage.** Include brute-force, botnet propagation and data-theft scenarios, and keep DoS and DDoS separate.

## 6.8 Concluding Remarks

This thesis set out to show that integrating and correlating distributed IoT logs improves threat detection. The evidence did not confirm this for the form of integration first proposed, namely detecting threats from incident summaries. That approach consolidated alerts substantially but detected threats less accurately than isolated event-level monitoring.

The supplementary experiments explained why, and pointed to a more promising direction: correlating different *types* of log while keeping event-level detail. This direction could not yet be confirmed.

The main value of the work lies in a reproducible framework, a fair and transparent evaluation, and a clear account of when integration helps and when it does not.
