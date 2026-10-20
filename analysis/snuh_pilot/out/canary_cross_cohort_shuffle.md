# Canary benchmark across cohorts, synthetic canaries

Exposed cell = canary TPR at 1% FPR of at least 0.1. Intervals are 95% percentile intervals over 2,000 resamples of whole configurations. The development cohort is the first one; its thresholds (target sensitivity 90%) are applied unchanged to the others.

## 1. Cohorts and exposure

| cohort | cells | exposed / unexposed | canary TPR@1%FPR, median (range) |
|---|---|---|---|
| SynPUF (development) | 141 | 71 / 70 | 0.103 (0.010-0.771) |
| MIMIC-IV-ED | 141 | 89 / 52 | 0.155 (0.012-0.832) |
| eICU-CRD | 141 | 121 / 20 | 0.129 (0.010-0.277) |

## 2. Does the audit quantity tell exposed cells from unexposed ones? (AUC)

| cohort | shadow-model AUC | LiRA AUC | LiRA TPR@1%FPR | training rows | LiRA TPR minus shadow-model AUC |
|---|---|---|---|---|---|
| SynPUF (development) | 0.92 [0.85, 0.97] | 0.98 [0.96, 1.00] | 0.99 [0.97, 1.00] | 0.47 [0.43, 0.51] | 0.07 [0.03, 0.12] |
| MIMIC-IV-ED | 0.94 [0.89, 0.98] | 0.99 [0.97, 1.00] | 0.99 [0.97, 1.00] | 0.51 [0.45, 0.57] | 0.05 [0.02, 0.09] |
| eICU-CRD | 0.98 [0.95, 0.99] | 0.99 [0.98, 1.00] | 1.00 [0.99, 1.00] | 0.60 [0.50, 0.72] | 0.02 [0.00, 0.04] |

## 3. The prescribed rule (shadow-model AUC <= 0.55)

| cohort | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | missed cells: canary TPR median / highest |
|---|---|---|---|---|---|
| SynPUF (development) | 65/141 | 12/71 | 0.83 [0.73, 0.93] | 0.76 [0.62, 0.88] | 0.134 / 0.234 |
| MIMIC-IV-ED | 52/141 | 9/89 | 0.90 [0.84, 0.95] | 0.83 [0.69, 0.93] | 0.132 / 0.199 |
| eICU-CRD | 50/141 | 30/121 | 0.75 [0.64, 0.85] | 1.00 [1.00, 1.00] | 0.116 / 0.132 |

## 4. Development thresholds applied unchanged (sensitivity / specificity)

Recalibrated = the threshold refitted on that cohort, one configuration left out at a time. The development row is in-sample.

**LiRA TPR@1%FPR (ordinary rows) <= 0.046**

| cohort | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated: sensitivity / specificity |
|---|---|---|---|---|---|
| SynPUF (development) | 76/141 | 7/71 | 0.90 [0.82, 0.96] | 0.99 [0.95, 1.00] | 0.90 / 0.99 |
| MIMIC-IV-ED | 57/141 | 8/89 | 0.91 [0.84, 0.96] | 0.94 [0.87, 1.00] | 0.90 / 0.96 |
| eICU-CRD | 26/141 | 6/121 | 0.95 [0.91, 0.98] | 1.00 [1.00, 1.00] | 0.91 / 1.00 |

**LiRA AUC (ordinary rows) <= 0.629**

| cohort | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated: sensitivity / specificity |
|---|---|---|---|---|---|
| SynPUF (development) | 75/141 | 7/71 | 0.90 [0.81, 0.97] | 0.97 [0.92, 1.00] | 0.92 / 0.97 |
| MIMIC-IV-ED | 54/141 | 5/89 | 0.94 [0.89, 0.99] | 0.94 [0.87, 1.00] | 0.91 / 0.96 |
| eICU-CRD | 77/141 | 57/121 | 0.53 [0.39, 0.66] | 1.00 [1.00, 1.00] | 0.90 / 1.00 |

**shadow-model AUC <= 0.538**

| cohort | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated: sensitivity / specificity |
|---|---|---|---|---|---|
| SynPUF (development) | 58/141 | 7/71 | 0.90 [0.83, 0.96] | 0.73 [0.59, 0.84] | 0.90 / 0.71 |
| MIMIC-IV-ED | 47/141 | 7/89 | 0.92 [0.86, 0.97] | 0.77 [0.63, 0.89] | 0.90 / 0.81 |
| eICU-CRD | 34/141 | 15/121 | 0.88 [0.81, 0.93] | 0.95 [0.80, 1.00] | 0.91 / 0.95 |

## 5. Thresholds calibrated on each cohort itself (release if the quantity is at most c; target sensitivity 90%)

| cohort | shadow-model AUC | LiRA AUC | LiRA TPR@1%FPR |
|---|---|---|---|
| SynPUF (development) | 0.538 | 0.629 | 0.046 |
| MIMIC-IV-ED | 0.546 | 0.633 | 0.048 |
| eICU-CRD | 0.532 | 0.579 | 0.051 |
