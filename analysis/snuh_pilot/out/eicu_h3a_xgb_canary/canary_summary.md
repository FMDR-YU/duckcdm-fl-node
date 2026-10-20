# Canary benchmark: release rules against planted-canary ground truth

141 cells (21 named, 120 space-filling; 47 configurations, 3 training sizes). Each cell = 48 models; each model contains a random half of 400 label-flipped real rows (canaries), so the membership of every canary is known and a leave-one-model-out LiRA gives the ground-truth exposure. A cell is **exposed** when its canary TPR at 1% FPR is at least 0.1 (main definition; 0.05 and 0.25 as sensitivity analyses): 129 of 141 cells. Intervals are 95% percentile intervals over 2,000 resamples of whole configurations (all sizes of one configuration together).

## 1. Does the audit quantity tell exposed cells from unexposed ones? (threshold-free)

| quantity | AUC, tau = 0.1 [95% CI] | AUC, tau = 0.05 | AUC, tau = 0.25 | Spearman with canary TPR@1%FPR [95% CI] |
|---|---|---|---|---|
| shadow-model AUC | 0.99 [0.96, 1.00] | 0.99 | 0.96 | 0.75 [0.63, 0.82] |
| LiRA AUC (ordinary rows) | 1.00 [1.00, 1.00] | 1.00 | 1.00 | 0.92 [0.86, 0.94] |
| LiRA TPR@1%FPR (ordinary rows) | 1.00 [1.00, 1.00] | 0.99 | 1.00 | 0.94 [0.89, 0.96] |
| member / non-member AUROC gap | 0.99 [0.96, 1.00] | 0.99 | 0.94 | 0.42 [0.19, 0.58] |
| share of leaves < 11 rows | 0.58 [0.41, 0.76] | 0.69 | 0.61 | 0.48 [0.25, 0.66] |
| training rows (a larger value is safer) | 0.50 [0.50, 0.50] | 0.57 | 0.47 | 0.12 [0.08, 0.20] |

Paired difference in AUC (tau = 0.1), LiRA TPR@1%FPR minus shadow-model AUC: 0.01 [0.00, 0.04]; LiRA AUC minus shadow-model AUC: 0.01 [0.00, 0.04]. Spearman is computed on the raw quantity (for training rows a negative value means larger is safer).

## 2. The rules at their prescribed thresholds (tau = 0.1)

| rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] |
|---|---|---|---|---|
| shadow-model AUC <= 0.55 (pilot release rule) | 30/141 | 18/129 | 0.86 [0.78, 0.93] | 1.00 [1.00, 1.00] |
| leaves with < 11 rows <= 10% | 97/141 | 85/129 | 0.34 [0.21, 0.49] | 1.00 [1.00, 1.00] |
| member / non-member AUROC gap <= 0.02 | 1/141 | 0/129 | 1.00 [1.00, 1.00] | 0.08 [0.00, 0.33] |
| training rows >= 10,000 (illustrative) | 0/141 | 0/129 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |
| release every cell | 141/141 | 129/129 | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] |
| block every cell | 0/141 | 0/129 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

The same prescribed rules at the other definitions of "exposed" (sensitivity / specificity):

| rule | tau = 0.05 | tau = 0.1 | tau = 0.25 |
|---|---|---|---|
| cells exposed / unexposed | 136 / 5 | 129 / 12 | 128 / 13 |
| shadow-model AUC <= 0.55 (pilot release rule) | 0.82 / 1.00 | 0.86 / 1.00 | 0.86 / 0.92 |
| leaves with < 11 rows <= 10% | 0.32 / 1.00 | 0.34 / 1.00 | 0.34 / 1.00 |
| member / non-member AUROC gap <= 0.02 | 0.99 / 0.00 | 1.00 / 0.08 | 1.00 / 0.08 |
| training rows >= 10,000 (illustrative) | 1.00 / 0.00 | 1.00 / 0.00 | 1.00 / 0.00 |
| release every cell | 0.00 / 1.00 | 0.00 / 1.00 | 0.00 / 1.00 |
| block every cell | 1.00 / 0.00 | 1.00 / 0.00 | 1.00 / 0.00 |

## 3. Calibrated thresholds (tau = 0.1; the threshold must block at least 90% of the exposed cells)

In-sample = thresholds fitted on all cells here. Leave-one-configuration-out = each configuration is scored with a threshold fitted on the others (the interval resamples configurations and keeps the decisions fixed).

| quantity | calibrated rule | in-sample sensitivity / specificity | leave-one-configuration-out sensitivity [CI] | specificity [CI] |
|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.543 | 0.91 / 0.92 | 0.91 [0.84, 0.96] | 0.92 [0.67, 1.00] |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.594 | 0.91 / 1.00 | 0.90 [0.81, 0.97] | 1.00 [1.00, 1.00] |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.043 | 0.91 / 1.00 | 0.90 [0.83, 0.96] | 1.00 [1.00, 1.00] |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.116 | 0.91 / 0.92 | 0.91 [0.84, 0.96] | 0.92 [0.67, 1.00] |
| share of leaves < 11 rows | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |
| training rows (a larger value is safer) | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

## 4. What a miss costs: exposed cells (tau = 0.1) that each rule releases

| rule | exposed cells released | median canary TPR@1%FPR of those | highest | of those, at the largest training size | unexposed cells blocked |
|---|---|---|---|---|---|
| shadow-model AUC <= 0.55 (prescribed) | 18/129 | 0.689 | 0.873 | 11/18 | 0/12 |
| shadow-model AUC, calibrated in-sample | 12/129 | 0.610 | 0.873 | 9/12 | 1/12 |
| LiRA TPR@1%FPR, calibrated in-sample | 12/129 | 0.539 | 0.810 | 8/12 | 0/12 |
| LiRA TPR@1%FPR, calibrated leave-one-configuration-out | 13/129 | 0.558 | 0.810 | 8/13 | 0/12 |

## 5. From canary exposure to attacker precision

Share of flagged records that are true members at 1% FPR, when a fraction pi of the candidate records are members: PPV = TPR*pi / (TPR*pi + 0.01*(1-pi)). Which PPV is tolerable is a governance judgement; this study does not set it.

| exposure | canary TPR@1%FPR | PPV, pi = 0.1% | PPV, pi = 1.0% | PPV, pi = 10.0% |
|---|---|---|---|---|
| chance (TPR = FPR) | 0.010 | 0.1% | 1.0% | 10.0% |
| tau = 0.05 | 0.050 | 0.5% | 4.8% | 35.7% |
| tau = 0.1 | 0.100 | 1.0% | 9.2% | 52.6% |
| tau = 0.25 | 0.250 | 2.4% | 20.2% | 73.5% |
| median cell here | 0.900 | 8.3% | 47.6% | 90.9% |
| 90th-percentile cell here | 0.987 | 9.0% | 49.9% | 91.6% |
| most exposed cell here | 1.000 | 9.1% | 50.2% | 91.7% |

## 6. Consistency

| cells | n | exposed | AUC shadow-model | AUC LiRA AUC | AUC LiRA TPR@1%FPR |
|---|---|---|---|---|---|
| named configurations | 21 | 18 | 0.98 | 1.00 | 1.00 |
| space-filling configurations | 120 | 111 | 0.99 | 1.00 | 1.00 |

Cells whose model-resampling 95% interval of the canary TPR contains tau: 3 of 141 cells with an interval.

Median model-to-model SD of the canary AUC inside a cell: 0.002.

## 7. Named configurations

| config | n | canary AUC | canary TPR@1%FPR | exposed | shadow AUC | LiRA TPR@1%FPR | leaves < 11 | AUROC gap |
|---|---|---|---|---|---|---|---|---|
| d2_r100 | 2,000 | 0.789 | 0.093 (0.078-0.106) | no | 0.547 | 0.021 | 8.6% | 0.125 |
| d2_r100 | 6,000 | 0.755 | 0.087 (0.075-0.101) | no | 0.515 | 0.017 | 3.2% | 0.056 |
| d2_r100 | 8,131 | 0.770 | 0.093 (0.084-0.104) | no | 0.514 | 0.016 | 1.9% | 0.041 |
| d4_free | 2,000 | 0.994 | 0.860 (0.849-0.872) | yes | 0.658 | 0.098 | 35.0% | 0.264 |
| d4_free | 6,000 | 0.990 | 0.824 (0.808-0.835) | yes | 0.566 | 0.079 | 24.9% | 0.139 |
| d4_free | 8,131 | 0.989 | 0.816 (0.794-0.833) | yes | 0.553 | 0.057 | 21.8% | 0.130 |
| d6_free | 2,000 | 1.000 | 0.994 (0.990-0.997) | yes | 0.770 | 0.197 | 59.2% | 0.263 |
| d6_free | 6,000 | 1.000 | 0.984 (0.979-0.987) | yes | 0.650 | 0.158 | 49.7% | 0.185 |
| d6_free | 8,131 | 1.000 | 0.987 (0.983-0.992) | yes | 0.621 | 0.136 | 47.5% | 0.168 |
| d6_mcw20 | 2,000 | 0.996 | 0.906 (0.897-0.912) | yes | 0.643 | 0.090 | 0.0% | 0.228 |
| d6_mcw20 | 6,000 | 0.998 | 0.945 (0.937-0.951) | yes | 0.583 | 0.097 | 0.0% | 0.155 |
| d6_mcw20 | 8,131 | 0.998 | 0.953 (0.948-0.959) | yes | 0.573 | 0.083 | 0.0% | 0.153 |
| krcp | 2,000 | 0.999 | 0.977 (0.972-0.984) | yes | 0.746 | 0.158 | 19.8% | 0.222 |
| krcp | 6,000 | 1.000 | 0.984 (0.978-0.988) | yes | 0.644 | 0.151 | 21.2% | 0.170 |
| krcp | 8,131 | 1.000 | 0.983 (0.979-0.989) | yes | 0.610 | 0.134 | 21.0% | 0.152 |
| leaky | 2,000 | 1.000 | 1.000 (0.999-1.000) | yes | 0.832 | 0.278 | 77.6% | 0.239 |
| leaky | 6,000 | 0.999 | 0.999 (0.999-1.000) | yes | 0.697 | 0.229 | 71.3% | 0.178 |
| leaky | 8,131 | 0.999 | 1.000 (0.999-1.000) | yes | 0.675 | 0.245 | 69.5% | 0.163 |
| regularized | 2,000 | 0.986 | 0.707 (0.681-0.744) | yes | 0.624 | 0.077 | 0.7% | 0.209 |
| regularized | 6,000 | 0.985 | 0.752 (0.728-0.783) | yes | 0.548 | 0.061 | 1.3% | 0.126 |
| regularized | 8,131 | 0.986 | 0.791 (0.773-0.813) | yes | 0.538 | 0.046 | 1.0% | 0.106 |

## 9. Thresholds fixed on the development cohort (tau = 0.1; 141 development cells, target sensitivity 90%)

The development thresholds are applied unchanged to these 141 cells, 129 of them exposed. "Recalibrated here" refits the threshold on this cohort's own cells, one configuration left out at a time, and shows what a fixed threshold loses.

| quantity | fixed rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated here: sensitivity / specificity |
|---|---|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.524 | 9/141 | 0/129 | 1.00 [1.00, 1.00] | 0.75 [0.67, 1.00] | 0.91 / 0.92 |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.602 | 32/141 | 20/129 | 0.84 [0.74, 0.93] | 1.00 [1.00, 1.00] | 0.90 / 1.00 |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.032 | 14/141 | 2/129 | 0.98 [0.96, 1.00] | 1.00 [1.00, 1.00] | 0.90 / 1.00 |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.039 | 6/141 | 0/129 | 1.00 [1.00, 1.00] | 0.50 [0.00, 0.67] | 0.91 / 0.92 |
