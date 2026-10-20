# Canary benchmark: release rules against planted-canary ground truth

141 cells (21 named, 120 space-filling; 47 configurations, 3 training sizes). Each cell = 48 models; each model contains a random half of 400 label-flipped real rows (canaries), so the membership of every canary is known and a leave-one-model-out LiRA gives the ground-truth exposure. A cell is **exposed** when its canary TPR at 1% FPR is at least 0.1 (main definition; 0.05 and 0.25 as sensitivity analyses): 107 of 141 cells. Intervals are 95% percentile intervals over 2,000 resamples of whole configurations (all sizes of one configuration together).

## 1. Does the audit quantity tell exposed cells from unexposed ones? (threshold-free)

| quantity | AUC, tau = 0.1 [95% CI] | AUC, tau = 0.05 | AUC, tau = 0.25 | Spearman with canary TPR@1%FPR [95% CI] |
|---|---|---|---|---|
| shadow-model AUC | 0.88 [0.80, 0.94] | 0.93 | 0.94 | 0.86 [0.78, 0.91] |
| LiRA AUC (ordinary rows) | 0.99 [0.96, 1.00] | 1.00 | 1.00 | 0.99 [0.98, 1.00] |
| LiRA TPR@1%FPR (ordinary rows) | 0.97 [0.95, 0.99] | 0.99 | 1.00 | 0.99 [0.97, 0.99] |
| member / non-member AUROC gap | 0.87 [0.77, 0.94] | 0.94 | 0.92 | 0.80 [0.71, 0.86] |
| share of leaves < 11 rows | 0.60 [0.46, 0.74] | 0.48 | 0.71 | 0.43 [0.15, 0.64] |
| training rows (a larger value is safer) | 0.41 [0.34, 0.46] | 0.44 | 0.48 | 0.06 [-0.02, 0.13] |

Paired difference in AUC (tau = 0.1), LiRA TPR@1%FPR minus shadow-model AUC: 0.09 [0.05, 0.16]; LiRA AUC minus shadow-model AUC: 0.11 [0.06, 0.18]. Spearman is computed on the raw quantity (for training rows a negative value means larger is safer).

## 2. The rules at their prescribed thresholds (tau = 0.1)

| rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] |
|---|---|---|---|---|
| shadow-model AUC <= 0.55 (pilot release rule) | 50/141 | 24/107 | 0.78 [0.68, 0.86] | 0.76 [0.58, 0.91] |
| leaves with < 11 rows <= 10% | 103/141 | 69/107 | 0.36 [0.21, 0.52] | 1.00 [1.00, 1.00] |
| member / non-member AUROC gap <= 0.02 | 12/141 | 1/107 | 0.99 [0.97, 1.00] | 0.32 [0.12, 0.51] |
| training rows >= 10,000 (illustrative) | 47/141 | 39/107 | 0.64 [0.61, 0.66] | 0.24 [0.14, 0.30] |
| release every cell | 141/141 | 107/107 | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] |
| block every cell | 0/141 | 0/107 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

The same prescribed rules at the other definitions of "exposed" (sensitivity / specificity):

| rule | tau = 0.05 | tau = 0.1 | tau = 0.25 |
|---|---|---|---|
| cells exposed / unexposed | 123 / 18 | 107 / 34 | 67 / 74 |
| shadow-model AUC <= 0.55 (pilot release rule) | 0.73 / 0.94 | 0.78 / 0.76 | 0.97 / 0.65 |
| leaves with < 11 rows <= 10% | 0.31 / 1.00 | 0.36 / 1.00 | 0.48 / 0.92 |
| member / non-member AUROC gap <= 0.02 | 0.98 / 0.56 | 0.99 / 0.32 | 1.00 / 0.16 |
| training rows >= 10,000 (illustrative) | 0.66 / 0.28 | 0.64 / 0.24 | 0.66 / 0.32 |
| release every cell | 0.00 / 1.00 | 0.00 / 1.00 | 0.00 / 1.00 |
| block every cell | 1.00 / 0.00 | 1.00 / 0.00 | 1.00 / 0.00 |

## 3. Calibrated thresholds (tau = 0.1; the threshold must block at least 90% of the exposed cells)

In-sample = thresholds fitted on all cells here. Leave-one-configuration-out = each configuration is scored with a threshold fitted on the others (the interval resamples configurations and keeps the decisions fixed).

| quantity | calibrated rule | in-sample sensitivity / specificity | leave-one-configuration-out sensitivity [CI] | specificity [CI] |
|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.529 | 0.91 / 0.59 | 0.91 [0.85, 0.95] | 0.59 [0.36, 0.76] |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.611 | 0.91 / 0.97 | 0.90 [0.81, 0.97] | 0.97 [0.89, 1.00] |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.032 | 0.91 / 0.91 | 0.89 [0.80, 0.95] | 0.91 [0.78, 1.00] |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.051 | 0.91 / 0.56 | 0.91 [0.85, 0.95] | 0.53 [0.26, 0.73] |
| share of leaves < 11 rows | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |
| training rows (a larger value is safer) | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

## 4. What a miss costs: exposed cells (tau = 0.1) that each rule releases

| rule | exposed cells released | median canary TPR@1%FPR of those | highest | of those, at the largest training size | unexposed cells blocked |
|---|---|---|---|---|---|
| shadow-model AUC <= 0.55 (prescribed) | 24/107 | 0.126 | 0.318 | 18/24 | 8/34 |
| shadow-model AUC, calibrated in-sample | 10/107 | 0.109 | 0.150 | 10/10 | 14/34 |
| LiRA TPR@1%FPR, calibrated in-sample | 10/107 | 0.109 | 0.146 | 10/10 | 3/34 |
| LiRA TPR@1%FPR, calibrated leave-one-configuration-out | 12/107 | 0.109 | 0.146 | 10/12 | 3/34 |

## 5. From canary exposure to attacker precision

Share of flagged records that are true members at 1% FPR, when a fraction pi of the candidate records are members: PPV = TPR*pi / (TPR*pi + 0.01*(1-pi)). Which PPV is tolerable is a governance judgement; this study does not set it.

| exposure | canary TPR@1%FPR | PPV, pi = 0.1% | PPV, pi = 1.0% | PPV, pi = 10.0% |
|---|---|---|---|---|
| chance (TPR = FPR) | 0.010 | 0.1% | 1.0% | 10.0% |
| tau = 0.05 | 0.050 | 0.5% | 4.8% | 35.7% |
| tau = 0.1 | 0.100 | 1.0% | 9.2% | 52.6% |
| tau = 0.25 | 0.250 | 2.4% | 20.2% | 73.5% |
| median cell here | 0.224 | 2.2% | 18.4% | 71.3% |
| 90th-percentile cell here | 0.785 | 7.3% | 44.2% | 89.7% |
| most exposed cell here | 0.997 | 9.1% | 50.2% | 91.7% |

## 6. Consistency

| cells | n | exposed | AUC shadow-model | AUC LiRA AUC | AUC LiRA TPR@1%FPR |
|---|---|---|---|---|---|
| named configurations | 21 | 18 | 0.96 | 1.00 | 1.00 |
| space-filling configurations | 120 | 89 | 0.87 | 0.99 | 0.97 |

Cells whose model-resampling 95% interval of the canary TPR contains tau: 11 of 141 cells with an interval.

Median model-to-model SD of the canary AUC inside a cell: 0.016.

## 7. Named configurations

| config | n | canary AUC | canary TPR@1%FPR | exposed | shadow AUC | LiRA TPR@1%FPR | leaves < 11 | AUROC gap |
|---|---|---|---|---|---|---|---|---|
| d2_r100 | 2,000 | 0.633 | 0.035 (0.029-0.040) | no | 0.525 | 0.018 | 7.4% | 0.047 |
| d2_r100 | 6,000 | 0.589 | 0.025 (0.020-0.033) | no | 0.509 | 0.013 | 1.9% | 0.020 |
| d2_r100 | 19,746 | 0.565 | 0.024 (0.018-0.030) | no | 0.503 | 0.012 | 0.3% | 0.005 |
| d4_free | 2,000 | 0.900 | 0.243 (0.212-0.270) | yes | 0.645 | 0.070 | 32.1% | 0.178 |
| d4_free | 6,000 | 0.821 | 0.196 (0.181-0.212) | yes | 0.555 | 0.055 | 24.3% | 0.093 |
| d4_free | 19,746 | 0.763 | 0.146 (0.136-0.160) | yes | 0.512 | 0.032 | 18.7% | 0.037 |
| d6_free | 2,000 | 0.993 | 0.816 (0.794-0.837) | yes | 0.829 | 0.328 | 57.5% | 0.224 |
| d6_free | 6,000 | 0.982 | 0.679 (0.658-0.708) | yes | 0.694 | 0.244 | 45.9% | 0.193 |
| d6_free | 19,746 | 0.952 | 0.544 (0.521-0.566) | yes | 0.586 | 0.162 | 36.8% | 0.136 |
| d6_mcw20 | 2,000 | 0.881 | 0.196 (0.168-0.220) | yes | 0.636 | 0.062 | 0.0% | 0.193 |
| d6_mcw20 | 6,000 | 0.885 | 0.258 (0.242-0.272) | yes | 0.587 | 0.075 | 0.0% | 0.145 |
| d6_mcw20 | 19,746 | 0.893 | 0.318 (0.303-0.338) | yes | 0.546 | 0.069 | 0.0% | 0.082 |
| krcp | 2,000 | 0.985 | 0.675 (0.641-0.701) | yes | 0.783 | 0.203 | 21.2% | 0.223 |
| krcp | 6,000 | 0.970 | 0.595 (0.576-0.618) | yes | 0.672 | 0.188 | 19.5% | 0.187 |
| krcp | 19,746 | 0.945 | 0.511 (0.495-0.537) | yes | 0.573 | 0.159 | 16.7% | 0.124 |
| leaky | 2,000 | 1.000 | 0.997 (0.995-0.999) | yes | 0.956 | 0.574 | 85.3% | 0.231 |
| leaky | 6,000 | 0.999 | 0.996 (0.994-0.997) | yes | 0.912 | 0.491 | 79.2% | 0.201 |
| leaky | 19,746 | 0.999 | 0.996 (0.995-0.997) | yes | 0.878 | 0.595 | 71.3% | 0.191 |
| regularized | 2,000 | 0.822 | 0.126 (0.114-0.143) | yes | 0.587 | 0.037 | 0.0% | 0.128 |
| regularized | 6,000 | 0.771 | 0.117 (0.105-0.131) | yes | 0.535 | 0.038 | 0.0% | 0.065 |
| regularized | 19,746 | 0.733 | 0.100 (0.093-0.111) | yes | 0.512 | 0.023 | 0.0% | 0.028 |

## 9. Thresholds fixed on the development cohort (tau = 0.1; 141 development cells, target sensitivity 90%)

The development thresholds are applied unchanged to these 141 cells, 107 of them exposed. "Recalibrated here" refits the threshold on this cohort's own cells, one configuration left out at a time, and shows what a fixed threshold loses.

| quantity | fixed rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated here: sensitivity / specificity |
|---|---|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.524 | 26/141 | 9/107 | 0.92 [0.86, 0.96] | 0.50 [0.25, 0.69] | 0.91 / 0.59 |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.602 | 37/141 | 6/107 | 0.94 [0.89, 0.99] | 0.91 [0.78, 1.00] | 0.90 / 0.97 |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.032 | 40/141 | 9/107 | 0.92 [0.86, 0.96] | 0.91 [0.78, 1.00] | 0.89 / 0.91 |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.039 | 22/141 | 7/107 | 0.93 [0.89, 0.97] | 0.44 [0.20, 0.64] | 0.91 / 0.53 |
