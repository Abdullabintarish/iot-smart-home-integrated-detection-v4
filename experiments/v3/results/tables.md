## Transfer runB (mean ± sd over 5 seeds)

| run | f1_macro | f1_macro_present | balanced_accuracy | mcc | binary_f1 | pr_auc_binary | roc_auc_binary | fpr | fnr |
|---|---|---|---|---|---|---|---|---|---|
| frag | 0.9955 ± 0.0000 | 0.9955 ± 0.0000 | 0.9989 ± 0.0000 | 0.9988 ± 0.0000 | 0.9998 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 0.0045 ± 0.0002 | 0.0001 ± 0.0000 |
| hgb_event_only | 0.9976 ± 0.0003 | 0.9976 ± 0.0003 | 0.9987 ± 0.0001 | 0.9987 ± 0.0001 | 0.9997 ± 0.0000 | 1.0000 ± 0.0000 | 0.9999 ± 0.0000 | 0.0036 ± 0.0002 | 0.0003 ± 0.0000 |
| hgb_event_plus_incident | 0.9990 ± 0.0002 | 0.9990 ± 0.0002 | 0.9988 ± 0.0001 | 0.9991 ± 0.0001 | 0.9998 ± 0.0000 | 1.0000 ± 0.0000 | 0.9999 ± 0.0000 | 0.0025 ± 0.0003 | 0.0002 ± 0.0000 |
| hgb_incident_only | 0.7656 ± 0.1804 | 0.7656 ± 0.1804 | 0.8154 ± 0.1229 | 0.8397 ± 0.2968 | 0.9941 ± 0.0006 | 0.9974 ± 0.0045 | 0.9811 ± 0.0278 | 0.1022 ± 0.0175 | 0.0039 ± 0.0002 |
| lr_event_only | 0.6719 ± 0.0022 | 0.6719 ± 0.0022 | 0.8748 ± 0.0011 | 0.7287 ± 0.0081 | 0.9958 ± 0.0000 | 0.9999 ± 0.0000 | 0.9989 ± 0.0000 | 0.0396 ± 0.0004 | 0.0052 ± 0.0001 |
| lr_event_plus_incident | 0.9650 ± 0.0091 | 0.9650 ± 0.0091 | 0.9893 ± 0.0001 | 0.9833 ± 0.0009 | 0.9983 ± 0.0000 | 0.9999 ± 0.0000 | 0.9991 ± 0.0000 | 0.0304 ± 0.0003 | 0.0009 ± 0.0000 |
| lr_incident_only | 0.6452 ± 0.0005 | 0.6452 ± 0.0005 | 0.8908 ± 0.0006 | 0.9102 ± 0.0007 | 0.9933 ± 0.0001 | 0.9988 ± 0.0000 | 0.9897 ± 0.0002 | 0.1271 ± 0.0026 | 0.0034 ± 0.0000 |
| rf_event_only | 0.9952 ± 0.0012 | 0.9952 ± 0.0012 | 0.9989 ± 0.0001 | 0.9990 ± 0.0001 | 0.9998 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 0.0038 ± 0.0005 | 0.0001 ± 0.0000 |
| rf_event_plus_incident | 0.9964 ± 0.0003 | 0.9964 ± 0.0003 | 0.9975 ± 0.0001 | 0.9977 ± 0.0001 | 0.9995 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 0.0114 ± 0.0002 | 0.0001 ± 0.0000 |
| rf_incident_only | 0.8566 ± 0.0035 | 0.8566 ± 0.0035 | 0.8698 ± 0.0026 | 0.9726 ± 0.0002 | 0.9943 ± 0.0000 | 0.9994 ± 0.0000 | 0.9941 ± 0.0002 | 0.0916 ± 0.0003 | 0.0043 ± 0.0001 |

## Transfer loso (mean over held-out sources of the 5-seed mean)

| run | f1_macro | f1_macro_present | balanced_accuracy | mcc | binary_f1 | pr_auc_binary | roc_auc_binary | fpr | fnr |
|---|---|---|---|---|---|---|---|---|---|
| frag_soft | 0.2960 | 0.3114 | 0.4931 | 0.0079 | 0.0215 | 0.8920 (n=11) | 0.9186 (n=11) | 0.0205 | 0.9850 (n=11) |
| frag_union | 0.0906 | 0.1177 | 0.1604 | 0.1183 | 0.5184 | 0.8312 (n=11) | 0.8079 (n=11) | 1.0000 | 0.0000 (n=11) |
| hgb_event_only | 0.3021 | 0.4576 | 0.5054 | 0.1385 | 0.4383 | 0.7750 (n=11) | 0.7765 (n=11) | 0.2298 | 0.4792 (n=11) |
| hgb_event_plus_incident | 0.3562 | 0.5151 | 0.5892 | 0.1547 | 0.5290 | 0.8618 (n=11) | 0.8763 (n=11) | 0.1575 | 0.4127 (n=11) |
| hgb_incident_only | 0.2645 | 0.4735 | 0.5170 | 0.1358 | 0.5129 | 0.6752 (n=11) | 0.8101 (n=11) | 0.2727 | 0.2394 (n=11) |
| lr_event_only | 0.3074 | 0.5378 | 0.5588 | 0.2646 | 0.6981 | 0.8827 (n=11) | 0.8754 (n=11) | 0.2295 | 0.1066 (n=11) |
| lr_event_plus_incident | 0.4086 | 0.6647 | 0.7249 | 0.3940 | 0.7209 | 0.8825 (n=11) | 0.9258 (n=11) | 0.1402 | 0.1172 (n=11) |
| lr_incident_only | 0.2028 | 0.4213 | 0.4121 | 0.0575 | 0.4913 | 0.6192 (n=11) | 0.6538 (n=11) | 0.4612 | 0.1224 (n=11) |
| rf_event_only | 0.3721 | 0.5535 | 0.5807 | 0.2609 | 0.5637 | 0.8866 (n=11) | 0.8688 (n=11) | 0.1708 | 0.3399 (n=11) |
| rf_event_plus_incident | 0.4410 | 0.6209 | 0.6550 | 0.3120 | 0.6485 | 0.8938 (n=11) | 0.9236 (n=11) | 0.1338 | 0.2042 (n=11) |
| rf_incident_only | 0.2482 | 0.4601 | 0.5132 | 0.1568 | 0.5123 | 0.7196 (n=11) | 0.8470 (n=11) | 0.2347 | 0.2573 (n=11) |

### loso macro F1 per held-out source (5-seed mean)

| held-out source | n test | frag_soft | frag_union | hgb_event_only | hgb_event_plus_incident | hgb_incident_only | lr_event_only | lr_event_plus_incident | lr_incident_only | rf_event_only | rf_event_plus_incident | rf_incident_only |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CTU-Honeypot-Capture-4-1 | 452 | 1.000 | 0.000 | 0.332 | 0.449 | 0.287 | 0.231 | 0.254 | 0.205 | 0.466 | 0.499 | 0.291 |
| CTU-Honeypot-Capture-5-1 | 1,374 | 0.800 | 0.000 | 0.290 | 0.424 | 0.162 | 0.204 | 0.241 | 0.181 | 0.232 | 0.236 | 0.206 |
| CTU-IoT-Malware-Capture-1-1 | 1,008,748 | 0.222 | 0.004 | 0.255 | 0.199 | 0.200 | 0.236 | 0.473 | 0.161 | 0.393 | 0.295 | 0.245 |
| CTU-IoT-Malware-Capture-20-1 | 3,209 | 0.499 | 0.137 | 0.616 | 0.632 | 0.236 | 0.492 | 0.619 | 0.085 | 0.804 | 0.984 | 0.242 |
| CTU-IoT-Malware-Capture-21-1 | 3,286 | 0.499 | 0.310 | 0.623 | 0.868 | 0.140 | 0.981 | 0.518 | 0.138 | 0.555 | 1.000 | 0.159 |
| CTU-IoT-Malware-Capture-3-1 | 156,103 | 0.014 | 0.000 | 0.275 | 0.308 | 0.353 | 0.028 | 0.256 | 0.154 | 0.396 | 0.370 | 0.257 |
| CTU-IoT-Malware-Capture-34-1 | 23,145 | 0.038 | 0.479 | 0.037 | 0.049 | 0.085 | 0.046 | 0.418 | 0.146 | 0.030 | 0.129 | 0.085 |
| CTU-IoT-Malware-Capture-42-1 | 4,426 | 0.287 | 0.000 | 0.164 | 0.179 | 0.082 | 0.177 | 0.177 | 0.046 | 0.252 | 0.179 | 0.080 |
| CTU-IoT-Malware-Capture-44-1 | 237 | 0.314 | 0.134 | 0.155 | 0.204 | 0.273 | 0.334 | 0.499 | 0.210 | 0.300 | 0.428 | 0.314 |
| CTU-IoT-Malware-Capture-8-1 | 10,403 | 0.173 | 0.093 | 0.173 | 0.173 | 0.597 | 0.250 | 0.667 | 0.463 | 0.347 | 0.255 | 0.625 |
| data_1 | 1,000,000 | 0.002 | 0.000 | 0.032 | 0.090 | 0.102 | 0.005 | 0.048 | 0.118 | 0.019 | 0.186 | 0.080 |
| data_10 | 1,000,000 | 0.000 | 0.010 | 0.498 | 0.576 | 0.570 | 0.549 | 0.557 | 0.327 | 0.569 | 0.605 | 0.362 |
| data_36 | 1,000,000 | 0.000 | 0.009 | 0.478 | 0.479 | 0.351 | 0.463 | 0.584 | 0.402 | 0.474 | 0.566 | 0.279 |

## Tests loso

| metric | comparison (X − Y) | mean diff | folds +/− | p (sign-flip) | p Holm | p Wilcoxon |
|---|---|---|---|---|---|---|
| f1_macro | frag_soft − rf_event_only | -0.0761 | 5/8 (n=13) | 0.4343 | 1.0000 | 0.3054 |
| f1_macro | rf_incident_only − frag_soft | -0.0479 | 7/5 (n=13) | 0.6348 | 1.0000 | 0.9097 |
| f1_macro | rf_incident_only − rf_event_only | -0.1239 | 4/9 (n=13) | 0.0544 | 0.3811 | 0.0681 |
| f1_macro | rf_event_plus_incident − rf_event_only | +0.0689 | 9/4 (n=13) | 0.0996 | 0.5977 | 0.1099 |
| f1_macro | hgb_incident_only − hgb_event_only | -0.0377 | 6/7 (n=13) | 0.5679 | 1.0000 | 0.5879 |
| f1_macro | hgb_event_plus_incident − hgb_event_only | +0.0540 | 11/1 (n=13) | 0.0132 | 0.1055 | 0.0093 |
| f1_macro | lr_incident_only − lr_event_only | -0.1046 | 4/9 (n=13) | 0.2061 | 0.8242 | 0.2734 |
| f1_macro | lr_event_plus_incident − lr_event_only | +0.1012 | 11/2 (n=13) | 0.1238 | 0.6189 | 0.0266 |
| f1_macro_present | frag_soft − rf_event_only | -0.2421 | 4/9 (n=13) | 0.0068 | 0.0547 | 0.0134 |
| f1_macro_present | rf_incident_only − frag_soft | +0.1487 | 7/5 (n=13) | 0.1357 | 0.5430 | 0.2334 |
| f1_macro_present | rf_incident_only − rf_event_only | -0.0934 | 3/10 (n=13) | 0.2107 | 0.6321 | 0.1272 |
| f1_macro_present | rf_event_plus_incident − rf_event_only | +0.0674 | 9/4 (n=13) | 0.0525 | 0.2769 | 0.0803 |
| f1_macro_present | hgb_incident_only − hgb_event_only | +0.0159 | 7/6 (n=13) | 0.8621 | 0.8621 | 0.6355 |
| f1_macro_present | hgb_event_plus_incident − hgb_event_only | +0.0576 | 11/1 (n=13) | 0.0444 | 0.2769 | 0.0210 |
| f1_macro_present | lr_incident_only − lr_event_only | -0.1165 | 5/8 (n=13) | 0.2605 | 0.6321 | 0.4973 |
| f1_macro_present | lr_event_plus_incident − lr_event_only | +0.1269 | 10/3 (n=13) | 0.0396 | 0.2769 | 0.0327 |
| pr_auc_binary | frag_soft − rf_event_only | +0.0055 | 5/6 (n=11) | 0.5312 | 1.0000 | 0.5771 |
| pr_auc_binary | rf_incident_only − frag_soft | -0.1724 | 5/6 (n=11) | 0.3242 | 1.0000 | 0.4131 |
| pr_auc_binary | rf_incident_only − rf_event_only | -0.1670 | 7/4 (n=11) | 0.4912 | 1.0000 | 0.5771 |
| pr_auc_binary | rf_event_plus_incident − rf_event_only | +0.0072 | 8/2 (n=11) | 0.2988 | 1.0000 | 0.1602 |
| pr_auc_binary | hgb_incident_only − hgb_event_only | -0.0999 | 6/5 (n=11) | 0.2383 | 1.0000 | 0.7646 |
| pr_auc_binary | hgb_event_plus_incident − hgb_event_only | +0.0868 | 8/3 (n=11) | 0.1309 | 0.9160 | 0.0674 |
| pr_auc_binary | lr_incident_only − lr_event_only | -0.2635 | 4/7 (n=11) | 0.0820 | 0.6562 | 0.1230 |
| pr_auc_binary | lr_event_plus_incident − lr_event_only | -0.0002 | 5/5 (n=11) | 0.8828 | 1.0000 | 0.8457 |
| fpr | frag_soft − rf_event_only | -0.1503 | 0/10 (n=13) | 0.0020 | 0.0156 | 0.0020 |
| fpr | rf_incident_only − frag_soft | +0.2142 | 10/0 (n=13) | 0.0020 | 0.0156 | 0.0020 |
| fpr | rf_incident_only − rf_event_only | +0.0639 | 7/5 (n=13) | 0.5103 | 1.0000 | 0.4697 |
| fpr | rf_event_plus_incident − rf_event_only | -0.0370 | 2/7 (n=13) | 0.2773 | 0.8320 | 0.2031 |
| fpr | hgb_incident_only − hgb_event_only | +0.0428 | 8/5 (n=13) | 0.6929 | 1.0000 | 0.5879 |
| fpr | hgb_event_plus_incident − hgb_event_only | -0.0723 | 3/7 (n=13) | 0.0781 | 0.3677 | 0.1055 |
| fpr | lr_incident_only − lr_event_only | +0.2317 | 9/4 (n=13) | 0.0613 | 0.3677 | 0.0803 |
| fpr | lr_event_plus_incident − lr_event_only | -0.0893 | 4/8 (n=13) | 0.0679 | 0.3677 | 0.1294 |

## Tests runB (seed level)

| metric | comparison (X − Y) | mean diff | seeds +/− | p (sign-flip) | p Holm |
|---|---|---|---|---|---|
| f1_macro | frag − rf_event_only | +0.0003 | 4/1 (n=5) | 0.5625 | 0.5625 |
| f1_macro | rf_incident_only − frag | -0.1388 | 0/5 (n=5) | 0.0625 | 0.5000 |
| f1_macro | rf_incident_only − rf_event_only | -0.1385 | 0/5 (n=5) | 0.0625 | 0.5000 |
| f1_macro | rf_event_plus_incident − rf_event_only | +0.0012 | 4/1 (n=5) | 0.1250 | 0.5000 |
| f1_macro | hgb_incident_only − hgb_event_only | -0.2320 | 0/5 (n=5) | 0.0625 | 0.5000 |
| f1_macro | hgb_event_plus_incident − hgb_event_only | +0.0014 | 5/0 (n=5) | 0.0625 | 0.5000 |
| f1_macro | lr_incident_only − lr_event_only | -0.0267 | 0/5 (n=5) | 0.0625 | 0.5000 |
| f1_macro | lr_event_plus_incident − lr_event_only | +0.2931 | 5/0 (n=5) | 0.0625 | 0.5000 |
| f1_macro_present | frag − rf_event_only | +0.0003 | 4/1 (n=5) | 0.5625 | 0.5625 |
| f1_macro_present | rf_incident_only − frag | -0.1388 | 0/5 (n=5) | 0.0625 | 0.5000 |
| f1_macro_present | rf_incident_only − rf_event_only | -0.1385 | 0/5 (n=5) | 0.0625 | 0.5000 |
| f1_macro_present | rf_event_plus_incident − rf_event_only | +0.0012 | 4/1 (n=5) | 0.1250 | 0.5000 |
| f1_macro_present | hgb_incident_only − hgb_event_only | -0.2320 | 0/5 (n=5) | 0.0625 | 0.5000 |
| f1_macro_present | hgb_event_plus_incident − hgb_event_only | +0.0014 | 5/0 (n=5) | 0.0625 | 0.5000 |
| f1_macro_present | lr_incident_only − lr_event_only | -0.0267 | 0/5 (n=5) | 0.0625 | 0.5000 |
| f1_macro_present | lr_event_plus_incident − lr_event_only | +0.2931 | 5/0 (n=5) | 0.0625 | 0.5000 |
| pr_auc_binary | frag − rf_event_only | -0.0000 | 0/5 (n=5) | 0.0625 | 0.5000 |
| pr_auc_binary | rf_incident_only − frag | -0.0006 | 0/5 (n=5) | 0.0625 | 0.5000 |
| pr_auc_binary | rf_incident_only − rf_event_only | -0.0006 | 0/5 (n=5) | 0.0625 | 0.5000 |
| pr_auc_binary | rf_event_plus_incident − rf_event_only | +0.0000 | 5/0 (n=5) | 0.0625 | 0.5000 |
| pr_auc_binary | hgb_incident_only − hgb_event_only | -0.0026 | 0/5 (n=5) | 0.0625 | 0.5000 |
| pr_auc_binary | hgb_event_plus_incident − hgb_event_only | +0.0000 | 5/0 (n=5) | 0.0625 | 0.5000 |
| pr_auc_binary | lr_incident_only − lr_event_only | -0.0011 | 0/5 (n=5) | 0.0625 | 0.5000 |
| pr_auc_binary | lr_event_plus_incident − lr_event_only | +0.0000 | 5/0 (n=5) | 0.0625 | 0.5000 |
| fpr | frag − rf_event_only | +0.0008 | 4/1 (n=5) | 0.1250 | 0.5000 |
| fpr | rf_incident_only − frag | +0.0870 | 5/0 (n=5) | 0.0625 | 0.5000 |
| fpr | rf_incident_only − rf_event_only | +0.0878 | 5/0 (n=5) | 0.0625 | 0.5000 |
| fpr | rf_event_plus_incident − rf_event_only | +0.0076 | 5/0 (n=5) | 0.0625 | 0.5000 |
| fpr | hgb_incident_only − hgb_event_only | +0.0986 | 5/0 (n=5) | 0.0625 | 0.5000 |
| fpr | hgb_event_plus_incident − hgb_event_only | -0.0011 | 0/5 (n=5) | 0.0625 | 0.5000 |
| fpr | lr_incident_only − lr_event_only | +0.0875 | 5/0 (n=5) | 0.0625 | 0.5000 |
| fpr | lr_event_plus_incident − lr_event_only | -0.0092 | 0/5 (n=5) | 0.0625 | 0.5000 |

## Incident-clustered bootstrap, runB seed 42

| comparison | macro F1 diff 95% CI | FPR diff 95% CI |
|---|---|---|
| frag_minus_rf_event_only | [-0.0076, +0.0062] | [-0.0009, +0.0007] |
| rf_incident_only_minus_frag | [-0.1777, -0.1077] | [+0.0837, +0.0911] |
| rf_incident_only_minus_rf_event_only | [-0.1761, -0.1072] | [+0.0836, +0.0909] |
| rf_event_plus_incident_minus_rf_event_only | [-0.0014, +0.0048] | [+0.0060, +0.0081] |
| hgb_incident_only_minus_hgb_event_only | [-0.6776, -0.4635] | [+0.1246, +0.1357] |
| hgb_event_plus_incident_minus_hgb_event_only | [+0.0007, +0.0025] | [-0.0016, -0.0001] |
| lr_incident_only_minus_lr_event_only | [-0.0562, +0.0188] | [+0.0836, +0.0933] |
| lr_event_plus_incident_minus_lr_event_only | [+0.2738, +0.3565] | [-0.0096, -0.0074] |

## Cross-log v3

**primary_augmented** — train ['CTU-IoT-Malware-Capture-1-1', 'CTU-IoT-Malware-Capture-3-1', 'CTU-IoT-Malware-Capture-20-1', 'CTU-IoT-Malware-Capture-42-1', 'CTU-IoT-Malware-Capture-36-1', 'CTU-IoT-Malware-Capture-7-1'], test ['CTU-IoT-Malware-Capture-8-1', 'CTU-IoT-Malware-Capture-21-1', 'CTU-IoT-Malware-Capture-34-1']

| condition | macro F1 mean | sd | min | max | FPR | FNR |
|---|---|---|---|---|---|---|
| A | 0.4543 | 0.1284 | 0.3968 | 0.6839 | 0.0098 | 0.7698 |
| B | 0.6686 | 0.1197 | 0.6122 | 0.8827 | 0.0098 | 0.4839 |
| C | 0.4711 | 0.1227 | 0.3973 | 0.6881 | 0.0053 | 0.7517 |
| D | 0.5064 | 0.1128 | 0.4394 | 0.7070 | 0.0105 | 0.7071 |
| Z | 0.4545 | 0.1327 | 0.3906 | 0.6920 | 0.0098 | 0.7688 |
| P | 0.4680 | 0.1275 | 0.3912 | 0.6935 | 0.0075 | 0.7542 |
| MAJ | 0.2454 | 0.0000 | 0.2454 | 0.2454 | 0.0000 | 1.0000 |
| STR | 0.4927 | 0.0023 | 0.4899 | 0.4952 | 0.7549 | 0.2522 |

| difference | mean | seeds +/− |
|---|---|---|
| B_minus_A | +0.2143 | 5/0 |
| C_minus_A | +0.0168 | 5/0 |
| D_minus_A | +0.0521 | 5/0 |
| Z_minus_A | +0.0002 | 2/3 |
| P_minus_A | +0.0136 | 4/1 |
| MAJ_minus_A | -0.2089 | 0/5 |
| STR_minus_A | +0.0384 | 4/1 |
| B_minus_Z | +0.2141 | 5/0 |
| B_minus_P | +0.2007 | 5/0 |
| C_minus_Z | +0.0166 | 4/1 |
| C_minus_P | +0.0032 | 2/3 |
| D_minus_Z | +0.0518 | 5/0 |
| D_minus_P | +0.0384 | 4/1 |

| test capture (macro F1) | A | B | C | D | Z | P | MAJ | STR |
|---|---|---|---|---|---|---|---|---|
| CTU-IoT-Malware-Capture-21-1 | 0.993 | 0.990 | 0.983 | 0.983 | 0.990 | 0.997 | 0.499 | 0.199 |
| CTU-IoT-Malware-Capture-34-1 | 0.213 | 0.688 | 0.245 | 0.331 | 0.206 | 0.238 | 0.176 | 0.498 |
| CTU-IoT-Malware-Capture-8-1 | 0.518 | 0.526 | 0.526 | 0.526 | 0.526 | 0.526 | 0.173 | 0.495 |

**loco** — captures ['CTU-IoT-Malware-Capture-1-1', 'CTU-IoT-Malware-Capture-20-1', 'CTU-IoT-Malware-Capture-21-1', 'CTU-IoT-Malware-Capture-3-1', 'CTU-IoT-Malware-Capture-34-1', 'CTU-IoT-Malware-Capture-36-1', 'CTU-IoT-Malware-Capture-42-1', 'CTU-IoT-Malware-Capture-48-1', 'CTU-IoT-Malware-Capture-7-1']; excluded by gate ['CTU-IoT-Malware-Capture-49-1', 'CTU-IoT-Malware-Capture-8-1']

| held-out | n test | A | B | C | D | Z | P | MAJ | STR |
|---|---|---|---|---|---|---|---|---|---|
| CTU-IoT-Malware-Capture-1-1 | 1,008,748 | 0.408 | 0.379 | 0.408 | 0.408 | 0.407 | 0.416 | 0.318 | 0.473 |
| CTU-IoT-Malware-Capture-20-1 | 3,209 | 0.980 | 0.983 | 1.000 | 1.000 | 0.987 | 0.881 | 0.499 | 0.201 |
| CTU-IoT-Malware-Capture-21-1 | 3,286 | 0.996 | 1.000 | 0.986 | 0.986 | 1.000 | 0.980 | 0.499 | 0.200 |
| CTU-IoT-Malware-Capture-3-1 | 156,103 | 0.513 | 0.519 | 0.439 | 0.521 | 0.519 | 0.523 | 0.028 | 0.451 |
| CTU-IoT-Malware-Capture-34-1 | 8,988 | 0.209 | 0.678 | 0.307 | 0.397 | 0.206 | 0.212 | 0.176 | 0.493 |
| CTU-IoT-Malware-Capture-36-1 | 13,645,098 | 0.999 | 1.000 | 0.999 | 1.000 | 0.999 | 0.920 | 0.000 | 0.427 |
| CTU-IoT-Malware-Capture-42-1 | 4,426 | 0.398 | 0.357 | 0.357 | 0.357 | 0.398 | 0.361 | 0.500 | 0.197 |
| CTU-IoT-Malware-Capture-48-1 | 3,394,338 | 0.998 | 0.998 | 0.936 | 0.998 | 0.998 | 0.997 | 0.001 | 0.432 |
| CTU-IoT-Malware-Capture-7-1 | 11,454,714 | 0.870 | 0.870 | 0.870 | 0.870 | 0.870 | 0.867 | 0.007 | 0.419 |

| difference | folds +/− | per fold |
|---|---|---|
| B_minus_A | 5/4 of 9 | 1-1: -0.029, 20-1: +0.003, 21-1: +0.004, 3-1: +0.005, 34-1: +0.469, 36-1: +0.001, 42-1: -0.041, 48-1: -0.000, 7-1: -0.000 |
| C_minus_A | 4/5 of 9 | 1-1: +0.001, 20-1: +0.020, 21-1: -0.010, 3-1: -0.074, 34-1: +0.098, 36-1: +0.001, 42-1: -0.041, 48-1: -0.062, 7-1: -0.000 |
| D_minus_A | 6/3 of 9 | 1-1: +0.000, 20-1: +0.020, 21-1: -0.010, 3-1: +0.008, 34-1: +0.188, 36-1: +0.001, 42-1: -0.041, 48-1: +0.000, 7-1: -0.000 |
| Z_minus_A | 4/5 of 9 | 1-1: -0.001, 20-1: +0.007, 21-1: +0.004, 3-1: +0.006, 34-1: -0.003, 36-1: +0.000, 42-1: -0.000, 48-1: -0.000, 7-1: -0.000 |
| P_minus_A | 3/6 of 9 | 1-1: +0.009, 20-1: -0.099, 21-1: -0.016, 3-1: +0.010, 34-1: +0.003, 36-1: -0.079, 42-1: -0.038, 48-1: -0.001, 7-1: -0.003 |
| B_minus_Z | 4/4 of 9 | 1-1: -0.028, 20-1: -0.004, 21-1: +0.000, 3-1: -0.001, 34-1: +0.472, 36-1: +0.001, 42-1: -0.041, 48-1: +0.000, 7-1: +0.000 |
| B_minus_P | 6/3 of 9 | 1-1: -0.038, 20-1: +0.102, 21-1: +0.020, 3-1: -0.004, 34-1: +0.466, 36-1: +0.079, 42-1: -0.003, 48-1: +0.001, 7-1: +0.003 |
| C_minus_Z | 4/5 of 9 | 1-1: +0.001, 20-1: +0.013, 21-1: -0.014, 3-1: -0.080, 34-1: +0.102, 36-1: +0.000, 42-1: -0.041, 48-1: -0.062, 7-1: -0.000 |
| C_minus_P | 5/4 of 9 | 1-1: -0.008, 20-1: +0.119, 21-1: +0.006, 3-1: -0.084, 34-1: +0.095, 36-1: +0.079, 42-1: -0.003, 48-1: -0.061, 7-1: +0.002 |
| D_minus_Z | 6/3 of 9 | 1-1: +0.001, 20-1: +0.013, 21-1: -0.014, 3-1: +0.002, 34-1: +0.192, 36-1: +0.001, 42-1: -0.041, 48-1: +0.000, 7-1: -0.000 |
| D_minus_P | 6/3 of 9 | 1-1: -0.008, 20-1: +0.119, 21-1: +0.006, 3-1: -0.002, 34-1: +0.185, 36-1: +0.079, 42-1: -0.003, 48-1: +0.001, 7-1: +0.003 |
