# Canary benchmark: release rules against planted-canary ground truth

141 cells (21 named, 120 space-filling; 47 configurations, 3 training sizes). Each cell = 48 models; each model contains a random half of 400 synthetic rows (each feature drawn independently from its own marginal, random label) (canaries), so the membership of every canary is known and a leave-one-model-out LiRA gives the ground-truth exposure. A cell is **exposed** when its canary TPR at 1% FPR is at least 0.1 (main definition; 0.05 and 0.25 as sensitivity analyses): 71 of 141 cells. Intervals are 95% percentile intervals over 2,000 resamples of whole configurations (all sizes of one configuration together).

## 1. Does the audit quantity tell exposed cells from unexposed ones? (threshold-free)

| quantity | AUC, tau = 0.1 [95% CI] | AUC, tau = 0.05 | AUC, tau = 0.25 | Spearman with canary TPR@1%FPR [95% CI] |
|---|---|---|---|---|
| shadow-model AUC | 0.92 [0.85, 0.97] | 0.89 | 0.95 | 0.84 [0.74, 0.89] |
| LiRA AUC (ordinary rows) | 0.98 [0.96, 1.00] | 0.97 | 0.99 | 0.96 [0.92, 0.98] |
| LiRA TPR@1%FPR (ordinary rows) | 0.99 [0.97, 1.00] | 0.98 | 1.00 | 0.97 [0.94, 0.98] |
| member / non-member AUROC gap | 0.92 [0.86, 0.97] | 0.91 | 0.92 | 0.83 [0.73, 0.88] |
| share of leaves < 11 rows | 0.79 [0.67, 0.89] | 0.66 | 0.87 | 0.59 [0.34, 0.75] |
| training rows (a larger value is safer) | 0.47 [0.43, 0.51] | 0.46 | 0.47 | 0.08 [0.03, 0.14] |

Paired difference in AUC (tau = 0.1), LiRA TPR@1%FPR minus shadow-model AUC: 0.07 [0.03, 0.12]; LiRA AUC minus shadow-model AUC: 0.07 [0.03, 0.12]. Spearman is computed on the raw quantity (for training rows a negative value means larger is safer).

## 2. The rules at their prescribed thresholds (tau = 0.1)

| rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] |
|---|---|---|---|---|
| shadow-model AUC <= 0.55 (pilot release rule) | 65/141 | 12/71 | 0.83 [0.73, 0.93] | 0.76 [0.62, 0.88] |
| leaves with < 11 rows <= 10% | 102/141 | 34/71 | 0.52 [0.33, 0.71] | 0.97 [0.91, 1.00] |
| member / non-member AUROC gap <= 0.02 | 23/141 | 0/71 | 1.00 [1.00, 1.00] | 0.33 [0.19, 0.47] |
| training rows >= 10,000 (illustrative) | 47/141 | 26/71 | 0.63 [0.59, 0.67] | 0.30 [0.26, 0.33] |
| release every cell | 141/141 | 71/71 | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] |
| block every cell | 0/141 | 0/71 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

The same prescribed rules at the other definitions of "exposed" (sensitivity / specificity):

| rule | tau = 0.05 | tau = 0.1 | tau = 0.25 |
|---|---|---|---|
| cells exposed / unexposed | 102 / 39 | 71 / 70 | 34 / 107 |
| shadow-model AUC <= 0.55 (pilot release rule) | 0.70 / 0.87 | 0.83 / 0.76 | 1.00 / 0.61 |
| leaves with < 11 rows <= 10% | 0.38 / 1.00 | 0.52 / 0.97 | 0.76 / 0.88 |
| member / non-member AUROC gap <= 0.02 | 0.94 / 0.44 | 1.00 / 0.33 | 1.00 / 0.21 |
| training rows >= 10,000 (illustrative) | 0.65 / 0.28 | 0.63 / 0.30 | 0.62 / 0.32 |
| release every cell | 0.00 / 1.00 | 0.00 / 1.00 | 0.00 / 1.00 |
| block every cell | 1.00 / 0.00 | 1.00 / 0.00 | 1.00 / 0.00 |

## 3. Calibrated thresholds (tau = 0.1; the threshold must block at least 90% of the exposed cells)

In-sample = thresholds fitted on all cells here. Leave-one-configuration-out = each configuration is scored with a threshold fitted on the others (the interval resamples configurations and keeps the decisions fixed).

| quantity | calibrated rule | in-sample sensitivity / specificity | leave-one-configuration-out sensitivity [CI] | specificity [CI] |
|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.538 | 0.90 / 0.73 | 0.90 [0.83, 0.96] | 0.71 [0.58, 0.84] |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.629 | 0.90 / 0.97 | 0.92 [0.83, 0.98] | 0.97 [0.92, 1.00] |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.046 | 0.90 / 0.99 | 0.90 [0.82, 0.96] | 0.99 [0.95, 1.00] |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.052 | 0.90 / 0.71 | 0.90 [0.83, 0.96] | 0.70 [0.56, 0.83] |
| share of leaves < 11 rows | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |
| training rows (a larger value is safer) | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

## 4. What a miss costs: exposed cells (tau = 0.1) that each rule releases

| rule | exposed cells released | median canary TPR@1%FPR of those | highest | of those, at the largest training size | unexposed cells blocked |
|---|---|---|---|---|---|
| shadow-model AUC <= 0.55 (prescribed) | 12/71 | 0.134 | 0.234 | 9/12 | 17/70 |
| shadow-model AUC, calibrated in-sample | 7/71 | 0.138 | 0.230 | 7/7 | 19/70 |
| LiRA TPR@1%FPR, calibrated in-sample | 7/71 | 0.130 | 0.226 | 6/7 | 1/70 |
| LiRA TPR@1%FPR, calibrated leave-one-configuration-out | 7/71 | 0.130 | 0.226 | 6/7 | 1/70 |

## 5. From canary exposure to attacker precision

Share of flagged records that are true members at 1% FPR, when a fraction pi of the candidate records are members: PPV = TPR*pi / (TPR*pi + 0.01*(1-pi)). Which PPV is tolerable is a governance judgement; this study does not set it.

| exposure | canary TPR@1%FPR | PPV, pi = 0.1% | PPV, pi = 1.0% | PPV, pi = 10.0% |
|---|---|---|---|---|
| chance (TPR = FPR) | 0.010 | 0.1% | 1.0% | 10.0% |
| tau = 0.05 | 0.050 | 0.5% | 4.8% | 35.7% |
| tau = 0.1 | 0.100 | 1.0% | 9.2% | 52.6% |
| tau = 0.25 | 0.250 | 2.4% | 20.2% | 73.5% |
| median cell here | 0.103 | 1.0% | 9.4% | 53.3% |
| 90th-percentile cell here | 0.421 | 4.0% | 29.9% | 82.4% |
| most exposed cell here | 0.771 | 7.2% | 43.8% | 89.5% |

## 6. Consistency

| cells | n | exposed | AUC shadow-model | AUC LiRA AUC | AUC LiRA TPR@1%FPR |
|---|---|---|---|---|---|
| named configurations | 21 | 13 | 0.88 | 0.98 | 0.99 |
| space-filling configurations | 120 | 58 | 0.93 | 0.98 | 0.99 |

Cells whose model-resampling 95% interval of the canary TPR contains tau: 11 of 141 cells with an interval.

Median model-to-model SD of the canary AUC inside a cell: 0.020.

## 7. Named configurations

| config | n | canary AUC | canary TPR@1%FPR | exposed | shadow AUC | LiRA TPR@1%FPR | leaves < 11 | AUROC gap |
|---|---|---|---|---|---|---|---|---|
| d2_r100 | 2,000 | 0.626 | 0.026 (0.022-0.035) | no | 0.509 | 0.014 | 3.6% | 0.027 |
| d2_r100 | 6,000 | 0.589 | 0.023 (0.018-0.029) | no | 0.504 | 0.014 | 1.3% | 0.011 |
| d2_r100 | 19,746 | 0.575 | 0.026 (0.021-0.030) | no | 0.503 | 0.012 | 0.1% | 0.005 |
| d4_free | 2,000 | 0.884 | 0.204 (0.189-0.221) | yes | 0.591 | 0.065 | 37.4% | 0.111 |
| d4_free | 6,000 | 0.832 | 0.157 (0.141-0.172) | yes | 0.538 | 0.053 | 30.2% | 0.060 |
| d4_free | 19,746 | 0.797 | 0.117 (0.106-0.139) | yes | 0.507 | 0.034 | 21.9% | 0.025 |
| d6_free | 2,000 | 0.980 | 0.561 (0.539-0.596) | yes | 0.747 | 0.232 | 63.5% | 0.126 |
| d6_free | 6,000 | 0.965 | 0.481 (0.449-0.508) | yes | 0.663 | 0.194 | 55.0% | 0.119 |
| d6_free | 19,746 | 0.958 | 0.460 (0.431-0.480) | yes | 0.579 | 0.128 | 45.4% | 0.083 |
| d6_mcw20 | 2,000 | 0.761 | 0.079 (0.072-0.092) | no | 0.573 | 0.029 | 0.0% | 0.089 |
| d6_mcw20 | 6,000 | 0.765 | 0.078 (0.069-0.088) | no | 0.555 | 0.042 | 0.0% | 0.072 |
| d6_mcw20 | 19,746 | 0.788 | 0.130 (0.119-0.147) | yes | 0.523 | 0.046 | 0.0% | 0.045 |
| krcp | 2,000 | 0.944 | 0.330 (0.302-0.364) | yes | 0.701 | 0.135 | 21.4% | 0.126 |
| krcp | 6,000 | 0.937 | 0.305 (0.269-0.346) | yes | 0.629 | 0.137 | 21.5% | 0.117 |
| krcp | 19,746 | 0.936 | 0.363 (0.348-0.403) | yes | 0.563 | 0.106 | 18.5% | 0.077 |
| leaky | 2,000 | 0.986 | 0.518 (0.498-0.555) | yes | 0.786 | 0.222 | 85.1% | 0.136 |
| leaky | 6,000 | 0.989 | 0.670 (0.656-0.692) | yes | 0.782 | 0.324 | 82.1% | 0.126 |
| leaky | 19,746 | 0.990 | 0.771 (0.743-0.804) | yes | 0.779 | 0.471 | 77.3% | 0.119 |
| regularized | 2,000 | 0.752 | 0.081 (0.066-0.093) | no | 0.544 | 0.030 | 0.0% | 0.064 |
| regularized | 6,000 | 0.719 | 0.060 (0.050-0.071) | no | 0.518 | 0.030 | 0.0% | 0.034 |
| regularized | 19,746 | 0.701 | 0.076 (0.066-0.083) | no | 0.514 | 0.023 | 0.0% | 0.015 |
