# Canary benchmark: release rules against planted-canary ground truth

21 cells (21 named, 0 space-filling; 7 configurations, 3 training sizes). Each cell = 48 models; each model contains a random half of 400 label-flipped real rows (canaries), so the membership of every canary is known and a leave-one-model-out LiRA gives the ground-truth exposure. A cell is **exposed** when its canary TPR at 1% FPR is at least 0.1 (main definition; 0.05 and 0.25 as sensitivity analyses): 18 of 21 cells. Intervals are 95% percentile intervals over 2,000 resamples of whole configurations (all sizes of one configuration together).

## 1. Does the audit quantity tell exposed cells from unexposed ones? (threshold-free)

| quantity | AUC, tau = 0.1 [95% CI] | AUC, tau = 0.05 | AUC, tau = 0.25 | Spearman with canary TPR@1%FPR [95% CI] |
|---|---|---|---|---|
| shadow-model AUC | 0.94 [0.87, 1.00] | 1.00 | 0.94 | 0.89 [0.62, 0.96] |
| LiRA AUC (ordinary rows) | 1.00 [1.00, 1.00] | 1.00 | 1.00 | 0.99 [0.84, 1.00] |
| LiRA TPR@1%FPR (ordinary rows) | 1.00 [1.00, 1.00] | 1.00 | 1.00 | 0.99 [0.91, 1.00] |
| member / non-member AUROC gap | 0.96 [0.92, 1.00] | 1.00 | 0.96 | 0.69 [0.30, 0.93] |
| share of leaves < 11 rows | 0.72 [0.39, 1.00] | 0.85 | 0.72 | 0.69 [-0.04, 0.97] |
| training rows (a larger value is safer) | 0.50 [0.50, 0.50] | 0.85 | 0.50 | -0.16 [-0.50, -0.02] |

Paired difference in AUC (tau = 0.1), LiRA TPR@1%FPR minus shadow-model AUC: 0.06 [0.00, 0.13]; LiRA AUC minus shadow-model AUC: 0.06 [0.00, 0.13]. Spearman is computed on the raw quantity (for training rows a negative value means larger is safer).

## 2. The rules at their prescribed thresholds (tau = 0.1)

| rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] |
|---|---|---|---|---|
| shadow-model AUC <= 0.55 (pilot release rule) | 6/21 | 3/18 | 0.83 [0.61, 1.00] | 1.00 [1.00, 1.00] |
| leaves with < 11 rows <= 10% | 9/21 | 6/18 | 0.67 [0.29, 1.00] | 1.00 [1.00, 1.00] |
| member / non-member AUROC gap <= 0.02 | 1/21 | 0/18 | 1.00 [1.00, 1.00] | 0.33 [0.33, 0.33] |
| training rows >= 10,000 (illustrative) | 7/21 | 6/18 | 0.67 [0.67, 0.67] | 0.33 [0.33, 0.33] |
| release every cell | 21/21 | 18/18 | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] |
| block every cell | 0/21 | 0/18 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

The same prescribed rules at the other definitions of "exposed" (sensitivity / specificity):

| rule | tau = 0.05 | tau = 0.1 | tau = 0.25 |
|---|---|---|---|
| cells exposed / unexposed | 20 / 1 | 18 / 3 | 18 / 3 |
| shadow-model AUC <= 0.55 (pilot release rule) | 0.75 / 1.00 | 0.83 / 1.00 | 0.83 / 1.00 |
| leaves with < 11 rows <= 10% | 0.60 / 1.00 | 0.67 / 1.00 | 0.67 / 1.00 |
| member / non-member AUROC gap <= 0.02 | 1.00 / 1.00 | 1.00 / 0.33 | 1.00 / 0.33 |
| training rows >= 10,000 (illustrative) | 0.70 / 1.00 | 0.67 / 0.33 | 0.67 / 0.33 |
| release every cell | 0.00 / 1.00 | 0.00 / 1.00 | 0.00 / 1.00 |
| block every cell | 1.00 / 0.00 | 1.00 / 0.00 | 1.00 / 0.00 |

## 3. Calibrated thresholds (tau = 0.1; the threshold must block at least 90% of the exposed cells)

In-sample = thresholds fitted on all cells here. Leave-one-configuration-out = each configuration is scored with a threshold fitted on the others (the interval resamples configurations and keeps the decisions fixed).

| quantity | calibrated rule | in-sample sensitivity / specificity | leave-one-configuration-out sensitivity [CI] | specificity [CI] |
|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.514 | 0.94 / 0.67 | 0.89 [0.75, 1.00] | 0.00 [0.00, 0.00] |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.572 | 0.94 / 1.00 | 0.94 [0.83, 1.00] | 0.00 [0.00, 0.00] |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.039 | 0.94 / 1.00 | 0.94 [0.83, 1.00] | 0.00 [0.00, 0.00] |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.053 | 0.94 / 0.67 | 0.89 [0.75, 1.00] | 0.00 [0.00, 0.00] |
| share of leaves < 11 rows | block every cell | 1.00 / 0.00 | 0.83 [0.50, 1.00] | 0.00 [0.00, 0.00] |
| training rows (a larger value is safer) | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

## 4. What a miss costs: exposed cells (tau = 0.1) that each rule releases

| rule | exposed cells released | median canary TPR@1%FPR of those | highest | of those, at the largest training size | unexposed cells blocked |
|---|---|---|---|---|---|
| shadow-model AUC <= 0.55 (prescribed) | 3/18 | 0.527 | 0.569 | 2/3 | 0/3 |
| shadow-model AUC, calibrated in-sample | 1/18 | 0.451 | 0.451 | 1/1 | 1/3 |
| LiRA TPR@1%FPR, calibrated in-sample | 1/18 | 0.451 | 0.451 | 1/1 | 0/3 |
| LiRA TPR@1%FPR, calibrated leave-one-configuration-out | 1/18 | 0.451 | 0.451 | 1/1 | 3/3 |

## 5. From canary exposure to attacker precision

Share of flagged records that are true members at 1% FPR, when a fraction pi of the candidate records are members: PPV = TPR*pi / (TPR*pi + 0.01*(1-pi)). Which PPV is tolerable is a governance judgement; this study does not set it.

| exposure | canary TPR@1%FPR | PPV, pi = 0.1% | PPV, pi = 1.0% | PPV, pi = 10.0% |
|---|---|---|---|---|
| chance (TPR = FPR) | 0.010 | 0.1% | 1.0% | 10.0% |
| tau = 0.05 | 0.050 | 0.5% | 4.8% | 35.7% |
| tau = 0.1 | 0.100 | 1.0% | 9.2% | 52.6% |
| tau = 0.25 | 0.250 | 2.4% | 20.2% | 73.5% |
| median cell here | 0.904 | 8.3% | 47.7% | 90.9% |
| 90th-percentile cell here | 0.998 | 9.1% | 50.2% | 91.7% |
| most exposed cell here | 1.000 | 9.1% | 50.2% | 91.7% |

## 6. Consistency

| cells | n | exposed | AUC shadow-model | AUC LiRA AUC | AUC LiRA TPR@1%FPR |
|---|---|---|---|---|---|
| named configurations | 21 | 18 | 0.94 | 1.00 | 1.00 |
| space-filling configurations | 0 | 0 | n/a | n/a | n/a |

Cells whose model-resampling 95% interval of the canary TPR contains tau: 0 of 21 cells with an interval.

Median model-to-model SD of the canary AUC inside a cell: 0.002.

## 7. Named configurations

| config | n | canary AUC | canary TPR@1%FPR | exposed | shadow AUC | LiRA TPR@1%FPR | leaves < 11 | AUROC gap |
|---|---|---|---|---|---|---|---|---|
| d2_r100 | 2,000 | 0.775 | 0.069 (0.055-0.083) | no | 0.543 | 0.016 | 5.6% | 0.102 |
| d2_r100 | 6,000 | 0.719 | 0.065 (0.059-0.074) | no | 0.514 | 0.016 | 2.6% | 0.039 |
| d2_r100 | 19,746 | 0.657 | 0.041 (0.034-0.050) | no | 0.505 | 0.014 | 0.2% | 0.019 |
| d4_free | 2,000 | 0.993 | 0.828 (0.798-0.863) | yes | 0.658 | 0.091 | 34.3% | 0.232 |
| d4_free | 6,000 | 0.981 | 0.701 (0.663-0.728) | yes | 0.562 | 0.074 | 24.5% | 0.127 |
| d4_free | 19,746 | 0.949 | 0.527 (0.500-0.546) | yes | 0.520 | 0.042 | 15.2% | 0.063 |
| d6_free | 2,000 | 1.000 | 0.994 (0.992-0.997) | yes | 0.788 | 0.196 | 58.6% | 0.234 |
| d6_free | 6,000 | 1.000 | 0.980 (0.979-0.983) | yes | 0.667 | 0.172 | 49.4% | 0.169 |
| d6_free | 19,746 | 0.999 | 0.969 (0.964-0.974) | yes | 0.576 | 0.144 | 39.4% | 0.131 |
| d6_mcw20 | 2,000 | 0.995 | 0.869 (0.852-0.885) | yes | 0.652 | 0.087 | 0.0% | 0.199 |
| d6_mcw20 | 6,000 | 0.997 | 0.912 (0.904-0.919) | yes | 0.595 | 0.096 | 0.0% | 0.144 |
| d6_mcw20 | 19,746 | 0.996 | 0.904 (0.896-0.912) | yes | 0.551 | 0.084 | 0.0% | 0.112 |
| krcp | 2,000 | 1.000 | 0.986 (0.979-0.992) | yes | 0.757 | 0.162 | 20.1% | 0.197 |
| krcp | 6,000 | 0.999 | 0.979 (0.974-0.982) | yes | 0.647 | 0.158 | 20.8% | 0.159 |
| krcp | 19,746 | 0.998 | 0.957 (0.950-0.964) | yes | 0.573 | 0.126 | 20.7% | 0.122 |
| leaky | 2,000 | 1.000 | 0.999 (0.999-1.000) | yes | 0.847 | 0.348 | 78.1% | 0.225 |
| leaky | 6,000 | 1.000 | 1.000 (0.999-1.000) | yes | 0.719 | 0.293 | 72.2% | 0.156 |
| leaky | 19,746 | 0.999 | 0.998 (0.994-0.999) | yes | 0.669 | 0.268 | 65.2% | 0.129 |
| regularized | 2,000 | 0.980 | 0.663 (0.629-0.698) | yes | 0.622 | 0.066 | 0.5% | 0.176 |
| regularized | 6,000 | 0.967 | 0.569 (0.541-0.611) | yes | 0.549 | 0.053 | 0.6% | 0.107 |
| regularized | 19,746 | 0.933 | 0.451 (0.429-0.481) | yes | 0.513 | 0.039 | 0.4% | 0.053 |

## 9. Thresholds fixed on the development cohort (tau = 0.1; 141 development cells, target sensitivity 90%)

The development thresholds are applied unchanged to these 21 cells, 18 of them exposed. "Recalibrated here" refits the threshold on this cohort's own cells, one configuration left out at a time, and shows what a fixed threshold loses.

| quantity | fixed rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated here: sensitivity / specificity |
|---|---|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.524 | 4/21 | 2/18 | 0.89 [0.75, 1.00] | 0.67 [0.67, 0.67] | 0.89 / 0.00 |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.602 | 6/21 | 3/18 | 0.83 [0.61, 1.00] | 1.00 [1.00, 1.00] | 0.94 / 0.00 |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.032 | 3/21 | 0/18 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.94 / 0.00 |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.039 | 2/21 | 0/18 | 1.00 [1.00, 1.00] | 0.67 [0.67, 0.67] | 0.89 / 0.00 |
