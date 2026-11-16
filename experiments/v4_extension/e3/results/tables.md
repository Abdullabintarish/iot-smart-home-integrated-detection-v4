## Main table (300 s block)

| Policy | Trigger | Attack prevented | Excl. DoS | Wrongly blocked | Benign hosts | Contained ≥90% | None blocked | Never blocked | Time to block median / p90 (s) | Block actions |
|---|---|---|---|---|---|---|---|---|---|---|
| P1 flow | A/C fragmented | 95.95% | 80.10% | 0.76% (929) | 3 | 58,893 | 4 | 16 | 0.0 / 0.0 | 1,569,860 |
| P1 flow | B integrated | 0.66% | 3.26% | 0.23% (280) | 5 | 92 | 58,783 | 4,781 | 15.0 / 15.0 | 62,543 |
| P1 flow | event_only (s42) | 95.95% | 80.10% | 0.80% (980) | 6 | 58,886 | 9 | 22 | 0.0 / 0.0 | 1,569,867 |
| P1 flow | event_plus_thin (s42) | 95.95% | 80.06% | 0.77% (940) | 4 | 58,886 | 11 | 44 | 0.0 / 0.0 | 1,570,716 |
| P1 flow | oracle (not achievable) | 95.96% | 80.10% | 0.02% (27) | 2 | 58,897 | 0 | 0 | 0.0 / 0.0 | 1,569,525 |
| P1 flow | no response | 0.00% | 0.00% | 0.00% (0) | 0 | 0 | 58,897 | 64,243 | – / – | 0 |
| P2 host | A/C fragmented | 99.98% | 99.91% | 92.60% (113,720) | 17 | 58,896 | 1 | 3 | 0.0 / 0.0 | 1,569,860 |
| P2 host | B integrated | 18.84% | 83.80% | 93.02% (114,229) | 19 | 58,540 | 292 | 5 | 0.0 / 0.0 | 62,543 |
| P2 host | event_only (s42) | 99.98% | 99.90% | 93.15% (114,393) | 17 | 58,891 | 4 | 3 | 0.0 / 0.0 | 1,569,867 |
| P2 host | event_plus_thin (s42) | 99.97% | 99.87% | 92.60% (113,722) | 17 | 58,891 | 5 | 3 | 0.0 / 0.0 | 1,570,716 |
| P2 host | oracle (not achievable) | 99.98% | 99.91% | 92.60% (113,718) | 17 | 58,897 | 0 | 0 | 0.0 / 0.0 | 1,569,525 |
| P2 host | no response | 0.00% | 0.00% | 0.00% (0) | 0 | 0 | 58,897 | 64,243 | – / – | 0 |

## All durations

| Policy | Trigger | Block | Attack prevented | Excl. DoS | Wrongly blocked | Benign hosts | Contained ≥90% | None blocked | Time to block median / p90 (s) | Starts / extensions |
|---|---|---|---|---|---|---|---|---|---|---|
| P1 flow | A/C fragmented | 60 s | 95.95% | 80.09% | 0.76% | 3 | 58,863 | 11 | 0.0 / 0.0 | 63,989 / 1,505,871 |
| P1 flow | A/C fragmented | 300 s | 95.95% | 80.10% | 0.76% | 3 | 58,893 | 4 | 0.0 / 0.0 | 63,940 / 1,505,920 |
| P1 flow | A/C fragmented | 900 s | 95.97% | 80.15% | 0.76% | 3 | 58,893 | 4 | 0.0 / 0.0 | 63,781 / 1,506,079 |
| P1 flow | A/C fragmented | end | 95.98% | 80.24% | 0.76% | 3 | 58,893 | 4 | 0.0 / 0.0 | 63,522 / 1,506,338 |
| P1 flow | B integrated | 60 s | 0.15% | 0.74% | 0.05% | 4 | 2 | 58,792 | 15.0 / 15.0 | 62,541 / 2 |
| P1 flow | B integrated | 300 s | 0.66% | 3.26% | 0.23% | 5 | 92 | 58,783 | 15.0 / 15.0 | 62,492 / 51 |
| P1 flow | B integrated | 900 s | 1.73% | 8.50% | 0.47% | 6 | 250 | 58,642 | 15.0 / 15.0 | 62,309 / 234 |
| P1 flow | B integrated | end | 8.31% | 40.87% | 1.60% | 14 | 486 | 58,411 | 15.0 / 15.0 | 62,020 / 523 |
| P1 flow | event_only (s42) | 60 s | 95.95% | 80.08% | 0.80% | 6 | 58,857 | 15 | 0.0 / 0.0 | 63,781 / 1,506,086 |
| P1 flow | event_only (s42) | 300 s | 95.95% | 80.10% | 0.80% | 6 | 58,886 | 9 | 0.0 / 0.0 | 63,734 / 1,506,133 |
| P1 flow | event_only (s42) | 900 s | 95.96% | 80.15% | 0.80% | 6 | 58,887 | 8 | 0.0 / 0.0 | 63,574 / 1,506,293 |
| P1 flow | event_only (s42) | end | 95.98% | 80.23% | 0.82% | 7 | 58,887 | 8 | 0.0 / 0.0 | 63,311 / 1,506,556 |
| P1 flow | event_plus_thin (s42) | 60 s | 95.94% | 80.05% | 0.76% | 4 | 58,857 | 17 | 0.0 / 0.0 | 63,982 / 1,506,734 |
| P1 flow | event_plus_thin (s42) | 300 s | 95.95% | 80.06% | 0.77% | 4 | 58,886 | 11 | 0.0 / 0.0 | 63,934 / 1,506,782 |
| P1 flow | event_plus_thin (s42) | 900 s | 95.96% | 80.11% | 0.77% | 4 | 58,886 | 11 | 0.0 / 0.0 | 63,777 / 1,506,939 |
| P1 flow | event_plus_thin (s42) | end | 95.97% | 80.20% | 0.77% | 4 | 58,886 | 11 | 0.0 / 0.0 | 63,518 / 1,507,198 |
| P1 flow | oracle (not achievable) | 60 s | 95.95% | 80.09% | 0.02% | 2 | 58,863 | 10 | 0.0 / 0.0 | 63,536 / 1,505,989 |
| P1 flow | oracle (not achievable) | 300 s | 95.96% | 80.10% | 0.02% | 2 | 58,897 | 0 | 0.0 / 0.0 | 63,483 / 1,506,042 |
| P1 flow | oracle (not achievable) | 900 s | 95.97% | 80.15% | 0.02% | 2 | 58,897 | 0 | 0.0 / 0.0 | 63,324 / 1,506,201 |
| P1 flow | oracle (not achievable) | end | 95.98% | 80.24% | 0.02% | 2 | 58,897 | 0 | 0.0 / 0.0 | 63,053 / 1,506,472 |
| P1 flow | no response | 60 s | 0.00% | 0.00% | 0.00% | 0 | 0 | 58,897 | – / – | 0 / 0 |
| P1 flow | no response | 300 s | 0.00% | 0.00% | 0.00% | 0 | 0 | 58,897 | – / – | 0 / 0 |
| P1 flow | no response | 900 s | 0.00% | 0.00% | 0.00% | 0 | 0 | 58,897 | – / – | 0 / 0 |
| P1 flow | no response | end | 0.00% | 0.00% | 0.00% | 0 | 0 | 58,897 | – / – | 0 / 0 |
| P2 host | A/C fragmented | 60 s | 99.97% | 99.88% | 92.42% | 15 | 58,873 | 7 | 0.0 / 0.0 | 404 / 1,569,456 |
| P2 host | A/C fragmented | 300 s | 99.98% | 99.91% | 92.60% | 17 | 58,896 | 1 | 0.0 / 0.0 | 308 / 1,569,552 |
| P2 host | A/C fragmented | 900 s | 99.99% | 99.96% | 92.80% | 17 | 58,896 | 1 | 0.0 / 0.0 | 150 / 1,569,710 |
| P2 host | A/C fragmented | end | 100.00% | 100.00% | 93.85% | 17 | 58,896 | 1 | 0.0 / 0.0 | 24 / 1,569,836 |
| P2 host | B integrated | 60 s | 12.96% | 54.89% | 92.24% | 15 | 58,383 | 346 | 0.0 / 0.0 | 512 / 62,031 |
| P2 host | B integrated | 300 s | 18.84% | 83.80% | 93.02% | 19 | 58,540 | 292 | 0.0 / 0.0 | 426 / 62,117 |
| P2 host | B integrated | 900 s | 20.64% | 92.66% | 93.60% | 20 | 58,726 | 153 | 0.0 / 0.0 | 226 / 62,317 |
| P2 host | B integrated | end | 22.05% | 99.62% | 95.91% | 21 | 58,873 | 20 | 0.0 / 0.0 | 37 / 62,506 |
| P2 host | event_only (s42) | 60 s | 99.97% | 99.87% | 92.91% | 14 | 58,868 | 11 | 0.0 / 0.0 | 413 / 1,569,454 |
| P2 host | event_only (s42) | 300 s | 99.98% | 99.90% | 93.15% | 17 | 58,891 | 4 | 0.0 / 0.0 | 316 / 1,569,551 |
| P2 host | event_only (s42) | 900 s | 99.99% | 99.95% | 93.43% | 17 | 58,892 | 3 | 0.0 / 0.0 | 153 / 1,569,714 |
| P2 host | event_only (s42) | end | 100.00% | 100.00% | 94.82% | 17 | 58,893 | 3 | 0.0 / 0.0 | 23 / 1,569,844 |
| P2 host | event_plus_thin (s42) | 60 s | 99.97% | 99.84% | 92.42% | 14 | 58,868 | 12 | 0.0 / 0.0 | 400 / 1,570,316 |
| P2 host | event_plus_thin (s42) | 300 s | 99.97% | 99.87% | 92.60% | 17 | 58,891 | 5 | 0.0 / 0.0 | 305 / 1,570,411 |
| P2 host | event_plus_thin (s42) | 900 s | 99.98% | 99.92% | 92.80% | 17 | 58,891 | 5 | 0.0 / 0.0 | 146 / 1,570,570 |
| P2 host | event_plus_thin (s42) | end | 100.00% | 100.00% | 93.95% | 17 | 58,893 | 3 | 0.0 / 0.0 | 23 / 1,570,693 |
| P2 host | oracle (not achievable) | 60 s | 99.97% | 99.88% | 92.38% | 15 | 58,873 | 6 | 0.0 / 0.0 | 405 / 1,569,120 |
| P2 host | oracle (not achievable) | 300 s | 99.98% | 99.91% | 92.60% | 17 | 58,897 | 0 | 0.0 / 0.0 | 308 / 1,569,217 |
| P2 host | oracle (not achievable) | 900 s | 99.99% | 99.96% | 92.80% | 17 | 58,897 | 0 | 0.0 / 0.0 | 149 / 1,569,376 |
| P2 host | oracle (not achievable) | end | 100.00% | 100.00% | 93.85% | 17 | 58,897 | 0 | 0.0 / 0.0 | 23 / 1,569,502 |
| P2 host | no response | 60 s | 0.00% | 0.00% | 0.00% | 0 | 0 | 58,897 | – / – | 0 / 0 |
| P2 host | no response | 300 s | 0.00% | 0.00% | 0.00% | 0 | 0 | 58,897 | – / – | 0 / 0 |
| P2 host | no response | 900 s | 0.00% | 0.00% | 0.00% | 0 | 0 | 58,897 | – / – | 0 / 0 |
| P2 host | no response | end | 0.00% | 0.00% | 0.00% | 0 | 0 | 58,897 | – / – | 0 / 0 |

## Per class (300 s): attack events prevented

| Policy | Trigger | c2 (n=3,283) | dos (n=1,250,540) | malware (n=1,278) | recon (n=314,424) |
|---|---|---|---|---|---|
| P1 flow | A/C fragmented | 95.92% | 100.00% | 95.31% | 79.87% |
| P1 flow | B integrated | 21.93% | 0.00% | 15.02% | 3.02% |
| P1 flow | event_only (s42) | 95.92% | 100.00% | 95.31% | 79.87% |
| P1 flow | event_plus_thin (s42) | 95.92% | 100.00% | 95.31% | 79.84% |
| P1 flow | oracle (not achievable) | 95.92% | 100.00% | 95.31% | 79.88% |
| P1 flow | no response | 0.00% | 0.00% | 0.00% | 0.00% |
| P2 host | A/C fragmented | 97.23% | 100.00% | 100.00% | 99.93% |
| P2 host | B integrated | 35.24% | 2.26% | 100.00% | 84.24% |
| P2 host | event_only (s42) | 97.23% | 100.00% | 100.00% | 99.93% |
| P2 host | event_plus_thin (s42) | 97.23% | 100.00% | 100.00% | 99.90% |
| P2 host | oracle (not achievable) | 97.20% | 100.00% | 100.00% | 99.93% |
| P2 host | no response | 0.00% | 0.00% | 0.00% | 0.00% |

## Per dataset (300 s)

| Policy | Trigger | IoT-23 prevented (n=176,124) | Bot-IoT prevented (n=1,393,401) | IoT-23 prevented excl. DoS (n=176,123) | Bot-IoT prevented excl. DoS (n=142,862) | IoT-23 wrongly blocked (n=122,393) | Bot-IoT wrongly blocked (n=414) |
|---|---|---|---|---|---|---|---|
| P1 flow | A/C fragmented | 64.12% | 99.98% | 64.12% | 99.80% | 0.76% | 0.00% |
| P1 flow | B integrated | 1.66% | 0.54% | 1.66% | 5.25% | 0.23% | 0.00% |
| P1 flow | event_only (s42) | 64.12% | 99.98% | 64.12% | 99.80% | 0.79% | 1.69% |
| P1 flow | event_plus_thin (s42) | 64.05% | 99.98% | 64.05% | 99.80% | 0.77% | 0.00% |
| P1 flow | oracle (not achievable) | 64.12% | 99.98% | 64.12% | 99.80% | 0.02% | 0.00% |
| P1 flow | no response | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| P2 host | A/C fragmented | 99.92% | 99.99% | 99.92% | 99.89% | 92.83% | 25.60% |
| P2 host | B integrated | 97.45% | 8.90% | 97.45% | 66.97% | 93.28% | 15.22% |
| P2 host | event_only (s42) | 99.91% | 99.99% | 99.91% | 99.89% | 93.37% | 26.81% |
| P2 host | event_plus_thin (s42) | 99.85% | 99.99% | 99.85% | 99.89% | 92.83% | 24.88% |
| P2 host | oracle (not achievable) | 99.92% | 99.99% | 99.92% | 99.90% | 92.82% | 25.85% |
| P2 host | no response | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |

## Per capture (300 s): A/C vs B

| Capture | Attack / benign events | P1 prevented A/C vs B | P1 wrongly blocked A/C vs B | P2 prevented A/C vs B | P2 wrongly blocked A/C vs B |
|---|---|---|---|---|---|
| CTU-Honeypot-Capture-4-1 | 0 / 131 | – vs – | 0.0% vs 0.0% | – vs – | 0.0% vs 1.5% |
| CTU-Honeypot-Capture-5-1 | 0 / 390 | – vs – | 0.0% vs 2.8% | – vs – | 0.0% vs 14.4% |
| CTU-IoT-Malware-Capture-1-1 | 135,472 / 116,802 | 65.0% vs 0.5% | 0.7% vs 0.0% | 100.0% vs 100.0% | 96.2% vs 96.2% |
| CTU-IoT-Malware-Capture-20-1 | 9 / 806 | 77.8% vs 0.0% | 0.0% vs 0.0% | 77.8% vs 11.1% | 5.2% vs 7.2% |
| CTU-IoT-Malware-Capture-21-1 | 1 / 1,003 | 0.0% vs 0.0% | 0.0% vs 23.3% | 0.0% vs 100.0% | 0.1% vs 29.8% |
| CTU-IoT-Malware-Capture-3-1 | 37,250 / 1,153 | 58.0% vs 3.9% | 1.0% vs 0.0% | 99.9% vs 93.7% | 70.8% vs 68.9% |
| CTU-IoT-Malware-Capture-34-1 | 1,281 / 462 | 98.0% vs 25.4% | 12.6% vs 0.0% | 98.2% vs 25.8% | 25.1% vs 17.7% |
| CTU-IoT-Malware-Capture-42-1 | 0 / 1,070 | – vs – | 0.0% vs 1.3% | – vs – | 0.0% vs 29.7% |
| CTU-IoT-Malware-Capture-44-1 | 0 / 53 | – vs – | 0.0% vs 0.0% | – vs – | 0.0% vs 0.0% |
| CTU-IoT-Malware-Capture-8-1 | 2,111 / 523 | 95.0% vs 23.7% | 0.0% vs 0.0% | 96.9% vs 44.0% | 58.9% vs 44.4% |
| data_1 | 142,862 / 388 | 99.8% vs 5.2% | 0.0% vs 0.0% | 99.9% vs 67.0% | 26.3% vs 16.0% |
| data_10 | 498,002 / 14 | 100.0% vs 0.0% | 0.0% vs 0.0% | 100.0% vs 0.0% | 28.6% vs 7.1% |
| data_36 | 752,537 / 12 | 100.0% vs 0.0% | 0.0% vs 0.0% | 100.0% vs 3.8% | 0.0% vs 0.0% |

| Policy | Captures with attacks | A/C more / less / tie prevented | Captures with benign | A/C fewer / more / tie wrongly blocked |
|---|---|---|---|---|
| P1 flow | 9 | 8 / 0 / 1 | 13 | 3 / 3 / 7 |
| P2 host | 9 | 8 / 1 / 0 | 13 | 5 / 6 / 2 |

## Bootstrap: A/C − B (300 s; 1,000 incident-clustered replicates, seed 42)

| Policy | Δ attack prevented [95% interval] | Δ wrongly blocked [95% interval] | Δ prevented excl. DoS [95% interval] |
|---|---|---|---|
| P1 flow | +95.29 pp [+87.03, +97.37] | +0.53 pp [+0.34, +0.72] | +76.84 pp [+67.91, +83.86] |
| P2 host | +81.14 pp [+53.33, +89.99] | -0.41 pp [-0.73, -0.14] | +16.11 pp [+10.12, +23.63] |
