# Canary benchmark across cohorts

Exposed cell = canary TPR at 1% FPR of at least 0.1. Intervals are 95% percentile intervals over 2,000 resamples of whole configurations. The development cohort is the first one; its thresholds (target sensitivity 90%) are applied unchanged to the others.

## 1. Cohorts and exposure

| cohort | cells | exposed / unexposed | canary TPR@1%FPR, median (range) |
|---|---|---|---|
| SynPUF (development) | 141 | 86 / 55 | 0.141 (0.013-0.983) |
| MIMIC-IV-ED | 141 | 107 / 34 | 0.224 (0.013-0.997) |
| eICU-CRD | 141 | 129 / 12 | 0.844 (0.022-0.999) |
| eICU-CRD, 3 largest hospitals | 141 | 129 / 12 | 0.900 (0.030-1.000) |
| eICU-CRD, hospitals of unequal size | 141 | 131 / 10 | 0.894 (0.034-1.000) |
| SNUH CDM, virtual hospitals | 141 | 127 / 14 | 0.654 (0.016-0.999) |

## 2. Does the audit quantity tell exposed cells from unexposed ones? (AUC)

| cohort | shadow-model AUC | LiRA AUC | LiRA TPR@1%FPR | training rows | LiRA TPR minus shadow-model AUC |
|---|---|---|---|---|---|
| SynPUF (development) | 0.91 [0.85, 0.96] | 0.99 [0.97, 1.00] | 0.98 [0.96, 0.99] | 0.47 [0.41, 0.53] | 0.07 [0.03, 0.12] |
| MIMIC-IV-ED | 0.88 [0.80, 0.94] | 0.99 [0.96, 1.00] | 0.97 [0.95, 0.99] | 0.41 [0.34, 0.46] | 0.09 [0.05, 0.16] |
| eICU-CRD | 0.97 [0.94, 0.99] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.50 [0.50, 0.50] | 0.03 [0.01, 0.06] |
| eICU-CRD, 3 largest hospitals | 0.99 [0.96, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.50 [0.50, 0.50] | 0.01 [0.00, 0.04] |
| eICU-CRD, hospitals of unequal size | 0.98 [0.91, 1.00] | 1.00 [0.97, 1.00] | 0.99 [0.96, 1.00] | 0.46 [0.16, 0.50] | 0.01 [0.00, 0.06] |
| SNUH CDM, virtual hospitals | 0.96 [0.88, 0.99] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.45 [0.30, 0.50] | 0.04 [0.01, 0.12] |

## 3. The prescribed rule (shadow-model AUC <= 0.55)

| cohort | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | missed cells: canary TPR median / highest |
|---|---|---|---|---|---|
| SynPUF (development) | 66/141 | 20/86 | 0.77 [0.66, 0.87] | 0.84 [0.70, 0.94] | 0.196 / 0.384 |
| MIMIC-IV-ED | 50/141 | 24/107 | 0.78 [0.68, 0.86] | 0.76 [0.58, 0.91] | 0.126 / 0.318 |
| eICU-CRD | 40/141 | 28/129 | 0.78 [0.71, 0.85] | 1.00 [1.00, 1.00] | 0.615 / 0.908 |
| eICU-CRD, 3 largest hospitals | 30/141 | 18/129 | 0.86 [0.78, 0.93] | 1.00 [1.00, 1.00] | 0.689 / 0.873 |
| eICU-CRD, hospitals of unequal size | 31/141 | 21/131 | 0.84 [0.76, 0.92] | 1.00 [1.00, 1.00] | 0.693 / 0.871 |
| SNUH CDM, virtual hospitals | 55/141 | 41/127 | 0.68 [0.57, 0.78] | 1.00 [1.00, 1.00] | 0.301 / 0.898 |

## 4. Development thresholds applied unchanged (sensitivity / specificity)

Recalibrated = the threshold refitted on that cohort, one configuration left out at a time. The development row is in-sample.

**LiRA TPR@1%FPR (ordinary rows) <= 0.032**

| cohort | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated: sensitivity / specificity |
|---|---|---|---|---|---|
| SynPUF (development) | 58/141 | 8/86 | 0.91 [0.82, 0.97] | 0.91 [0.83, 0.98] | 0.90 / 0.91 |
| MIMIC-IV-ED | 40/141 | 9/107 | 0.92 [0.86, 0.96] | 0.91 [0.78, 1.00] | 0.89 / 0.91 |
| eICU-CRD | 19/141 | 7/129 | 0.95 [0.91, 0.98] | 1.00 [1.00, 1.00] | 0.90 / 1.00 |
| eICU-CRD, 3 largest hospitals | 14/141 | 2/129 | 0.98 [0.96, 1.00] | 1.00 [1.00, 1.00] | 0.90 / 1.00 |
| eICU-CRD, hospitals of unequal size | 13/141 | 3/131 | 0.98 [0.94, 1.00] | 1.00 [1.00, 1.00] | 0.90 / 1.00 |
| SNUH CDM, virtual hospitals | 22/141 | 8/127 | 0.94 [0.89, 0.98] | 1.00 [1.00, 1.00] | 0.90 / 1.00 |

**LiRA AUC (ordinary rows) <= 0.602**

| cohort | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated: sensitivity / specificity |
|---|---|---|---|---|---|
| SynPUF (development) | 62/141 | 8/86 | 0.91 [0.82, 0.97] | 0.98 [0.94, 1.00] | 0.91 / 0.96 |
| MIMIC-IV-ED | 37/141 | 6/107 | 0.94 [0.89, 0.99] | 0.91 [0.78, 1.00] | 0.90 / 0.97 |
| eICU-CRD | 48/141 | 36/129 | 0.72 [0.61, 0.83] | 1.00 [1.00, 1.00] | 0.90 / 1.00 |
| eICU-CRD, 3 largest hospitals | 32/141 | 20/129 | 0.84 [0.74, 0.93] | 1.00 [1.00, 1.00] | 0.90 / 1.00 |
| eICU-CRD, hospitals of unequal size | 24/141 | 14/131 | 0.89 [0.81, 0.97] | 1.00 [1.00, 1.00] | 0.89 / 1.00 |
| SNUH CDM, virtual hospitals | 38/141 | 24/127 | 0.81 [0.71, 0.90] | 1.00 [1.00, 1.00] | 0.90 / 1.00 |

**shadow-model AUC <= 0.524**

| cohort | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated: sensitivity / specificity |
|---|---|---|---|---|---|
| SynPUF (development) | 45/141 | 8/86 | 0.91 [0.84, 0.96] | 0.67 [0.51, 0.82] | 0.90 / 0.67 |
| MIMIC-IV-ED | 26/141 | 9/107 | 0.92 [0.86, 0.96] | 0.50 [0.25, 0.69] | 0.91 / 0.59 |
| eICU-CRD | 20/141 | 10/129 | 0.92 [0.88, 0.96] | 0.83 [0.67, 1.00] | 0.91 / 0.92 |
| eICU-CRD, 3 largest hospitals | 9/141 | 0/129 | 1.00 [1.00, 1.00] | 0.75 [0.67, 1.00] | 0.91 / 0.92 |
| eICU-CRD, hospitals of unequal size | 10/141 | 2/131 | 0.98 [0.95, 1.00] | 0.80 [0.00, 1.00] | 0.91 / 0.90 |
| SNUH CDM, virtual hospitals | 29/141 | 17/127 | 0.87 [0.79, 0.93] | 0.86 [0.43, 1.00] | 0.90 / 0.79 |

## 5. Thresholds calibrated on each cohort itself (release if the quantity is at most c; target sensitivity 90%)

| cohort | shadow-model AUC | LiRA AUC | LiRA TPR@1%FPR |
|---|---|---|---|
| SynPUF (development) | 0.524 | 0.602 | 0.032 |
| MIMIC-IV-ED | 0.529 | 0.611 | 0.032 |
| eICU-CRD | 0.529 | 0.570 | 0.036 |
| eICU-CRD, 3 largest hospitals | 0.543 | 0.594 | 0.043 |
| eICU-CRD, hospitals of unequal size | 0.544 | 0.598 | 0.040 |
| SNUH CDM, virtual hospitals | 0.518 | 0.580 | 0.034 |
