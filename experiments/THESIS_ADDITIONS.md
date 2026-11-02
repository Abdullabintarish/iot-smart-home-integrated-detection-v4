# Thesis additions

The full write-up for the thesis, with methods, results, figures, limitations
and the source file of every number, is the report:

- `thesis_report/Thesis_Experiments_Report.docx` (Word)
- `thesis_report/Thesis_Experiments_Report.pdf`

It is generated from the result files by `thesis_report/build_content.py` and
`build_docx.js`. This page summarises the two supplementary experiments.
Commands, versions, hashes and decisions are in `RUN_LOG.md`.

**Correction (2026-11-03).** An earlier version of this page reported
cross-log results from a run with an alert-timestamp bug (`RUN_LOG.md` §5.1).
Those numbers are superseded. In particular, the earlier statement that
"alert context alone does not help" was caused by the bug.

## A. Controlled ablation (Run B data)

One pooled Random Forest, the same training sample per seed and the same
1,692,332 Run B test events; only the features change. Data check:
704,090 incidents at 300 s and 1,463,143 novel-vector test events, as in Run B.

| Feature set (300 s) | Macro F1 (5 seeds) | FPR |
|---|---|---|
| Event features only | 0.9952 ± 0.0012 | 0.38% ± 0.05% |
| Event + incident features | 0.9964 ± 0.0003 | 1.14% ± 0.02% |
| Incident features only | 0.8566 ± 0.0035 | 9.16% ± 0.03% |

Bootstrap (seed 42): event + incident − event only, macro F1 [−0.0014, +0.0048],
FPR [+0.0060, +0.0081]. Incident context leaves macro F1 unchanged and roughly
triples the false-positive rate, at every window (60–900 s) and seed.
Source: `ablation/results/full/`.

## B. Cross-log correlation (Zeek conn + DNS, Suricata alerts)

Scope: log types from the same packet capture, not independent device,
gateway and cloud sensors. Seven IoT-23 captures; capture-held-out test
(8-1, 21-1, 34-1); design fixed in `PLAN.md` §4.

| Condition | Macro F1 (5 seeds) | Attacks missed | False alarms |
|---|---|---|---|
| A connection | 0.335 ± 0.197 | 89.1% | 0.27% |
| B + DNS | 0.502 ± 0.169 | 70.6% | 0.43% |
| C + alerts | 0.416 ± 0.163 | 81.1% | 0.19% |
| D + DNS + alerts | 0.586 ± 0.153 | 59.8% | 0.92% |

Robustness (`PLAN.md` §4b, `cross_log/results/robustness/`):

- 20 seeds: D > A and B > A in 20/20 seeds, C > A in 18/20.
- Bootstrap over seeds and incidents: D − A [+0.150, +0.367], B − A
  [+0.063, +0.350], C − A [−0.001, +0.150].
- Windows anchored at connection end, and 60 s / 900 s windows: D > A and
  B > A in every seed.
- Leave-one-capture-out (7 captures + 48-1; 49-1 excluded by the pre-set
  match-rate gate): D > A on 6 of 8 held-out captures, slightly worse on 42-1
  and 48-1.

Reading: linking DNS logs and alerts to connection records improves detection
on most unseen networks, most strongly when all three are combined, at the
cost of a small rise in false alarms. The gain varies by network and is not
universal. Absolute detection on unseen networks remains limited.

## Limitations

Same-capture log types; seven to eight captures with one infected device each;
large seed-to-seed variation; a 2026 ruleset on 2018–2019 traffic; binary
target; in 34-1 only 237 of 14,394 DDoS rows are covered because IoT-23 logs
one flood flow per packet (`RUN_LOG.md` §4.6).
