# Canary benchmark: release rules against planted-canary ground truth

141 cells (21 named, 120 space-filling; 47 configurations, 3 training sizes). Each cell = 48 models; each model contains a random half of 400 label-flipped real rows (canaries), so the membership of every canary is known and a leave-one-model-out LiRA gives the ground-truth exposure. A cell is **exposed** when its canary TPR at 1% FPR is at least 0.1 (main definition; 0.05 and 0.25 as sensitivity analyses): 131 of 141 cells. Intervals are 95% percentile intervals over 2,000 resamples of whole configurations (all sizes of one configuration together).

## 1. Does the audit quantity tell exposed cells from unexposed ones? (threshold-free)

| quantity | AUC, tau = 0.1 [95% CI] | AUC, tau = 0.05 | AUC, tau = 0.25 | Spearman with canary TPR@1%FPR [95% CI] |
|---|---|---|---|---|
| shadow-model AUC | 0.98 [0.91, 1.00] | 0.98 | 0.97 | 0.81 [0.70, 0.86] |
| LiRA AUC (ordinary rows) | 1.00 [0.97, 1.00] | 0.99 | 1.00 | 0.94 [0.89, 0.96] |
| LiRA TPR@1%FPR (ordinary rows) | 0.99 [0.96, 1.00] | 0.98 | 1.00 | 0.95 [0.91, 0.97] |
| member / non-member AUROC gap | 0.98 [0.91, 1.00] | 0.97 | 0.95 | 0.48 [0.24, 0.64] |
| share of leaves < 11 rows | 0.56 [0.38, 0.70] | 0.55 | 0.58 | 0.51 [0.28, 0.68] |
| training rows (a larger value is safer) | 0.46 [0.16, 0.50] | 0.41 | 0.47 | 0.09 [0.04, 0.15] |

Paired difference in AUC (tau = 0.1), LiRA TPR@1%FPR minus shadow-model AUC: 0.01 [0.00, 0.06]; LiRA AUC minus shadow-model AUC: 0.01 [0.00, 0.07]. Spearman is computed on the raw quantity (for training rows a negative value means larger is safer).

## 2. The rules at their prescribed thresholds (tau = 0.1)

| rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] |
|---|---|---|---|---|
| shadow-model AUC <= 0.55 (pilot release rule) | 31/141 | 21/131 | 0.84 [0.76, 0.92] | 1.00 [1.00, 1.00] |
| leaves with < 11 rows <= 10% | 99/141 | 89/131 | 0.32 [0.19, 0.47] | 1.00 [1.00, 1.00] |
| member / non-member AUROC gap <= 0.02 | 2/141 | 0/131 | 1.00 [1.00, 1.00] | 0.20 [0.00, 0.33] |
| training rows >= 10,000 (illustrative) | 0/141 | 0/131 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |
| release every cell | 141/141 | 131/131 | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] |
| block every cell | 0/141 | 0/131 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

The same prescribed rules at the other definitions of "exposed" (sensitivity / specificity):

| rule | tau = 0.05 | tau = 0.1 | tau = 0.25 |
|---|---|---|---|
| cells exposed / unexposed | 137 / 4 | 131 / 10 | 128 / 13 |
| shadow-model AUC <= 0.55 (pilot release rule) | 0.80 / 1.00 | 0.84 / 1.00 | 0.85 / 0.92 |
| leaves with < 11 rows <= 10% | 0.31 / 1.00 | 0.32 / 1.00 | 0.33 / 1.00 |
| member / non-member AUROC gap <= 0.02 | 0.99 / 0.25 | 1.00 / 0.20 | 1.00 / 0.15 |
| training rows >= 10,000 (illustrative) | 1.00 / 0.00 | 1.00 / 0.00 | 1.00 / 0.00 |
| release every cell | 0.00 / 1.00 | 0.00 / 1.00 | 0.00 / 1.00 |
| block every cell | 1.00 / 0.00 | 1.00 / 0.00 | 1.00 / 0.00 |

## 3. Calibrated thresholds (tau = 0.1; the threshold must block at least 90% of the exposed cells)

In-sample = thresholds fitted on all cells here. Leave-one-configuration-out = each configuration is scored with a threshold fitted on the others (the interval resamples configurations and keeps the decisions fixed).

| quantity | calibrated rule | in-sample sensitivity / specificity | leave-one-configuration-out sensitivity [CI] | specificity [CI] |
|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.544 | 0.90 / 0.90 | 0.91 [0.84, 0.96] | 0.90 [0.00, 1.00] |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.598 | 0.90 / 1.00 | 0.89 [0.81, 0.97] | 1.00 [1.00, 1.00] |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.040 | 0.90 / 1.00 | 0.90 [0.82, 0.97] | 1.00 [1.00, 1.00] |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.093 | 0.90 / 0.90 | 0.91 [0.83, 0.97] | 0.90 [0.00, 1.00] |
| share of leaves < 11 rows | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |
| training rows (a larger value is safer) | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

## 4. What a miss costs: exposed cells (tau = 0.1) that each rule releases

| rule | exposed cells released | median canary TPR@1%FPR of those | highest | of those, at the largest training size | unexposed cells blocked |
|---|---|---|---|---|---|
| shadow-model AUC <= 0.55 (prescribed) | 21/131 | 0.693 | 0.871 | 10/21 | 0/10 |
| shadow-model AUC, calibrated in-sample | 13/131 | 0.522 | 0.795 | 8/13 | 1/10 |
| LiRA TPR@1%FPR, calibrated in-sample | 13/131 | 0.478 | 0.723 | 6/13 | 0/10 |
| LiRA TPR@1%FPR, calibrated leave-one-configuration-out | 13/131 | 0.478 | 0.723 | 6/13 | 0/10 |

## 5. From canary exposure to attacker precision

Share of flagged records that are true members at 1% FPR, when a fraction pi of the candidate records are members: PPV = TPR*pi / (TPR*pi + 0.01*(1-pi)). Which PPV is tolerable is a governance judgement; this study does not set it.

| exposure | canary TPR@1%FPR | PPV, pi = 0.1% | PPV, pi = 1.0% | PPV, pi = 10.0% |
|---|---|---|---|---|
| chance (TPR = FPR) | 0.010 | 0.1% | 1.0% | 10.0% |
| tau = 0.05 | 0.050 | 0.5% | 4.8% | 35.7% |
| tau = 0.1 | 0.100 | 1.0% | 9.2% | 52.6% |
| tau = 0.25 | 0.250 | 2.4% | 20.2% | 73.5% |
| median cell here | 0.894 | 8.2% | 47.4% | 90.8% |
| 90th-percentile cell here | 0.992 | 9.0% | 50.1% | 91.7% |
| most exposed cell here | 1.000 | 9.1% | 50.2% | 91.7% |

## 6. Consistency

| cells | n | exposed | AUC shadow-model | AUC LiRA AUC | AUC LiRA TPR@1%FPR |
|---|---|---|---|---|---|
| named configurations | 21 | 20 | 0.85 | 0.90 | 0.90 |
| space-filling configurations | 120 | 111 | 1.00 | 1.00 | 1.00 |

Cells whose model-resampling 95% interval of the canary TPR contains tau: 2 of 141 cells with an interval.

Median model-to-model SD of the canary AUC inside a cell: 0.002.

## 7. Named configurations

| config | n | canary AUC | canary TPR@1%FPR | exposed | shadow AUC | LiRA TPR@1%FPR | leaves < 11 | AUROC gap |
|---|---|---|---|---|---|---|---|---|
| d2_r100 | 2,000 | 0.786 | 0.075 (0.065-0.093) | no | 0.546 | 0.024 | 8.8% | 0.094 |
| d2_r100 | 6,000 | 0.764 | 0.100 (0.088-0.110) | yes | 0.515 | 0.014 | 2.3% | 0.036 |
| d2_r100 | 6,567 | 0.765 | 0.107 (0.096-0.121) | yes | 0.512 | 0.013 | 1.3% | 0.031 |
| d4_free | 2,000 | 0.994 | 0.866 (0.836-0.884) | yes | 0.653 | 0.120 | 35.4% | 0.193 |
| d4_free | 6,000 | 0.991 | 0.828 (0.812-0.843) | yes | 0.564 | 0.076 | 25.0% | 0.123 |
| d4_free | 6,567 | 0.991 | 0.831 (0.814-0.847) | yes | 0.560 | 0.068 | 24.0% | 0.119 |
| d6_free | 2,000 | 1.000 | 0.998 (0.995-0.999) | yes | 0.787 | 0.243 | 59.5% | 0.202 |
| d6_free | 6,000 | 1.000 | 0.991 (0.987-0.994) | yes | 0.655 | 0.178 | 50.9% | 0.157 |
| d6_free | 6,567 | 1.000 | 0.994 (0.991-0.997) | yes | 0.639 | 0.166 | 50.6% | 0.151 |
| d6_mcw20 | 2,000 | 0.996 | 0.896 (0.882-0.912) | yes | 0.653 | 0.103 | 0.0% | 0.193 |
| d6_mcw20 | 6,000 | 0.998 | 0.949 (0.940-0.955) | yes | 0.586 | 0.105 | 0.0% | 0.132 |
| d6_mcw20 | 6,567 | 0.999 | 0.955 (0.950-0.962) | yes | 0.580 | 0.086 | 0.0% | 0.129 |
| krcp | 2,000 | 1.000 | 0.992 (0.987-0.995) | yes | 0.749 | 0.191 | 20.0% | 0.193 |
| krcp | 6,000 | 1.000 | 0.990 (0.986-0.992) | yes | 0.630 | 0.162 | 22.0% | 0.129 |
| krcp | 6,567 | 1.000 | 0.988 (0.985-0.992) | yes | 0.620 | 0.158 | 21.4% | 0.140 |
| leaky | 2,000 | 1.000 | 0.999 (0.999-1.000) | yes | 0.836 | 0.312 | 77.9% | 0.201 |
| leaky | 6,000 | 1.000 | 0.999 (0.999-1.000) | yes | 0.707 | 0.277 | 71.6% | 0.144 |
| leaky | 6,567 | 0.999 | 1.000 (0.999-1.000) | yes | 0.699 | 0.270 | 70.7% | 0.132 |
| regularized | 2,000 | 0.987 | 0.755 (0.728-0.777) | yes | 0.623 | 0.088 | 0.4% | 0.171 |
| regularized | 6,000 | 0.986 | 0.774 (0.752-0.800) | yes | 0.548 | 0.060 | 0.8% | 0.094 |
| regularized | 6,567 | 0.985 | 0.765 (0.741-0.793) | yes | 0.543 | 0.050 | 0.8% | 0.095 |

## 9. Thresholds fixed on the development cohort (tau = 0.1; 141 development cells, target sensitivity 90%)

The development thresholds are applied unchanged to these 141 cells, 131 of them exposed. "Recalibrated here" refits the threshold on this cohort's own cells, one configuration left out at a time, and shows what a fixed threshold loses.

| quantity | fixed rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated here: sensitivity / specificity |
|---|---|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.524 | 10/141 | 2/131 | 0.98 [0.95, 1.00] | 0.80 [0.00, 1.00] | 0.91 / 0.90 |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.602 | 24/141 | 14/131 | 0.89 [0.81, 0.97] | 1.00 [1.00, 1.00] | 0.89 / 1.00 |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.032 | 13/141 | 3/131 | 0.98 [0.94, 1.00] | 1.00 [1.00, 1.00] | 0.90 / 1.00 |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.039 | 8/141 | 2/131 | 0.98 [0.95, 1.00] | 0.60 [0.00, 0.67] | 0.91 / 0.90 |
