# Canary benchmark: release rules against planted-canary ground truth

141 cells (21 named, 120 space-filling; 47 configurations, 3 training sizes). Each cell = 48 models; each model contains a random half of 400 label-flipped real rows (canaries), so the membership of every canary is known and a leave-one-model-out LiRA gives the ground-truth exposure. A cell is **exposed** when its canary TPR at 1% FPR is at least 0.1 (main definition; 0.05 and 0.25 as sensitivity analyses): 129 of 141 cells. Intervals are 95% percentile intervals over 2,000 resamples of whole configurations (all sizes of one configuration together).

## 1. Does the audit quantity tell exposed cells from unexposed ones? (threshold-free)

| quantity | AUC, tau = 0.1 [95% CI] | AUC, tau = 0.05 | AUC, tau = 0.25 | Spearman with canary TPR@1%FPR [95% CI] |
|---|---|---|---|---|
| shadow-model AUC | 0.97 [0.94, 0.99] | 0.97 | 0.94 | 0.75 [0.64, 0.82] |
| LiRA AUC (ordinary rows) | 1.00 [1.00, 1.00] | 0.99 | 1.00 | 0.96 [0.93, 0.97] |
| LiRA TPR@1%FPR (ordinary rows) | 1.00 [1.00, 1.00] | 1.00 | 1.00 | 0.97 [0.94, 0.98] |
| member / non-member AUROC gap | 0.97 [0.93, 1.00] | 0.98 | 0.92 | 0.45 [0.25, 0.61] |
| share of leaves < 11 rows | 0.56 [0.41, 0.70] | 0.61 | 0.59 | 0.47 [0.25, 0.65] |
| training rows (a larger value is safer) | 0.50 [0.50, 0.50] | 0.55 | 0.47 | 0.06 [-0.01, 0.13] |

Paired difference in AUC (tau = 0.1), LiRA TPR@1%FPR minus shadow-model AUC: 0.03 [0.01, 0.06]; LiRA AUC minus shadow-model AUC: 0.03 [0.01, 0.06]. Spearman is computed on the raw quantity (for training rows a negative value means larger is safer).

## 2. The rules at their prescribed thresholds (tau = 0.1)

| rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] |
|---|---|---|---|---|
| shadow-model AUC <= 0.55 (pilot release rule) | 40/141 | 28/129 | 0.78 [0.71, 0.85] | 1.00 [1.00, 1.00] |
| leaves with < 11 rows <= 10% | 99/141 | 87/129 | 0.33 [0.20, 0.48] | 1.00 [1.00, 1.00] |
| member / non-member AUROC gap <= 0.02 | 4/141 | 0/129 | 1.00 [1.00, 1.00] | 0.33 [0.33, 0.33] |
| training rows >= 10,000 (illustrative) | 47/141 | 43/129 | 0.67 [0.67, 0.67] | 0.33 [0.33, 0.33] |
| release every cell | 141/141 | 129/129 | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] |
| block every cell | 0/141 | 0/129 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

The same prescribed rules at the other definitions of "exposed" (sensitivity / specificity):

| rule | tau = 0.05 | tau = 0.1 | tau = 0.25 |
|---|---|---|---|
| cells exposed / unexposed | 134 / 7 | 129 / 12 | 128 / 13 |
| shadow-model AUC <= 0.55 (pilot release rule) | 0.75 / 1.00 | 0.78 / 1.00 | 0.78 / 0.92 |
| leaves with < 11 rows <= 10% | 0.31 / 1.00 | 0.33 / 1.00 | 0.33 / 1.00 |
| member / non-member AUROC gap <= 0.02 | 0.99 / 0.43 | 1.00 / 0.33 | 1.00 / 0.31 |
| training rows >= 10,000 (illustrative) | 0.67 / 0.43 | 0.67 / 0.33 | 0.66 / 0.31 |
| release every cell | 0.00 / 1.00 | 0.00 / 1.00 | 0.00 / 1.00 |
| block every cell | 1.00 / 0.00 | 1.00 / 0.00 | 1.00 / 0.00 |

## 3. Calibrated thresholds (tau = 0.1; the threshold must block at least 90% of the exposed cells)

In-sample = thresholds fitted on all cells here. Leave-one-configuration-out = each configuration is scored with a threshold fitted on the others (the interval resamples configurations and keeps the decisions fixed).

| quantity | calibrated rule | in-sample sensitivity / specificity | leave-one-configuration-out sensitivity [CI] | specificity [CI] |
|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.529 | 0.91 / 0.92 | 0.91 [0.86, 0.95] | 0.92 [0.67, 1.00] |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.570 | 0.91 / 1.00 | 0.90 [0.84, 0.95] | 1.00 [1.00, 1.00] |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.036 | 0.91 / 1.00 | 0.90 [0.84, 0.95] | 1.00 [1.00, 1.00] |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.095 | 0.91 / 0.92 | 0.91 [0.86, 0.95] | 0.92 [0.67, 1.00] |
| share of leaves < 11 rows | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |
| training rows (a larger value is safer) | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

## 4. What a miss costs: exposed cells (tau = 0.1) that each rule releases

| rule | exposed cells released | median canary TPR@1%FPR of those | highest | of those, at the largest training size | unexposed cells blocked |
|---|---|---|---|---|---|
| shadow-model AUC <= 0.55 (prescribed) | 28/129 | 0.615 | 0.908 | 22/28 | 0/12 |
| shadow-model AUC, calibrated in-sample | 12/129 | 0.460 | 0.756 | 11/12 | 1/12 |
| LiRA TPR@1%FPR, calibrated in-sample | 12/129 | 0.410 | 0.557 | 9/12 | 0/12 |
| LiRA TPR@1%FPR, calibrated leave-one-configuration-out | 13/129 | 0.408 | 0.557 | 9/13 | 0/12 |

## 5. From canary exposure to attacker precision

Share of flagged records that are true members at 1% FPR, when a fraction pi of the candidate records are members: PPV = TPR*pi / (TPR*pi + 0.01*(1-pi)). Which PPV is tolerable is a governance judgement; this study does not set it.

| exposure | canary TPR@1%FPR | PPV, pi = 0.1% | PPV, pi = 1.0% | PPV, pi = 10.0% |
|---|---|---|---|---|
| chance (TPR = FPR) | 0.010 | 0.1% | 1.0% | 10.0% |
| tau = 0.05 | 0.050 | 0.5% | 4.8% | 35.7% |
| tau = 0.1 | 0.100 | 1.0% | 9.2% | 52.6% |
| tau = 0.25 | 0.250 | 2.4% | 20.2% | 73.5% |
| median cell here | 0.844 | 7.8% | 46.0% | 90.4% |
| 90th-percentile cell here | 0.971 | 8.9% | 49.5% | 91.5% |
| most exposed cell here | 0.999 | 9.1% | 50.2% | 91.7% |

## 6. Consistency

| cells | n | exposed | AUC shadow-model | AUC LiRA AUC | AUC LiRA TPR@1%FPR |
|---|---|---|---|---|---|
| named configurations | 21 | 18 | 0.96 | 1.00 | 1.00 |
| space-filling configurations | 120 | 111 | 0.98 | 1.00 | 1.00 |

Cells whose model-resampling 95% interval of the canary TPR contains tau: 0 of 141 cells with an interval.

Median model-to-model SD of the canary AUC inside a cell: 0.002.

## 7. Named configurations

| config | n | canary AUC | canary TPR@1%FPR | exposed | shadow AUC | LiRA TPR@1%FPR | leaves < 11 | AUROC gap |
|---|---|---|---|---|---|---|---|---|
| d2_r100 | 2,000 | 0.776 | 0.082 (0.070-0.091) | no | 0.543 | 0.019 | 6.7% | 0.119 |
| d2_r100 | 6,000 | 0.733 | 0.076 (0.065-0.085) | no | 0.510 | 0.014 | 2.9% | 0.049 |
| d2_r100 | 19,746 | 0.704 | 0.052 (0.043-0.063) | no | 0.501 | 0.013 | 0.2% | 0.011 |
| d4_free | 2,000 | 0.992 | 0.828 (0.807-0.844) | yes | 0.658 | 0.095 | 34.5% | 0.251 |
| d4_free | 6,000 | 0.984 | 0.743 (0.724-0.771) | yes | 0.565 | 0.081 | 23.5% | 0.150 |
| d4_free | 19,746 | 0.964 | 0.612 (0.587-0.645) | yes | 0.519 | 0.044 | 15.6% | 0.066 |
| d6_free | 2,000 | 0.999 | 0.982 (0.977-0.987) | yes | 0.781 | 0.191 | 60.1% | 0.263 |
| d6_free | 6,000 | 0.999 | 0.966 (0.962-0.971) | yes | 0.643 | 0.158 | 50.0% | 0.182 |
| d6_free | 19,746 | 0.999 | 0.957 (0.952-0.962) | yes | 0.576 | 0.122 | 39.1% | 0.139 |
| d6_mcw20 | 2,000 | 0.994 | 0.874 (0.861-0.886) | yes | 0.649 | 0.086 | 0.0% | 0.230 |
| d6_mcw20 | 6,000 | 0.996 | 0.906 (0.899-0.914) | yes | 0.586 | 0.098 | 0.0% | 0.163 |
| d6_mcw20 | 19,746 | 0.996 | 0.908 (0.901-0.915) | yes | 0.549 | 0.085 | 0.0% | 0.123 |
| krcp | 2,000 | 0.999 | 0.969 (0.961-0.973) | yes | 0.732 | 0.155 | 19.8% | 0.222 |
| krcp | 6,000 | 0.999 | 0.961 (0.957-0.967) | yes | 0.636 | 0.144 | 21.4% | 0.167 |
| krcp | 19,746 | 0.998 | 0.947 (0.942-0.956) | yes | 0.569 | 0.112 | 20.9% | 0.134 |
| leaky | 2,000 | 1.000 | 0.999 (0.998-1.000) | yes | 0.816 | 0.306 | 77.0% | 0.240 |
| leaky | 6,000 | 0.999 | 0.998 (0.997-0.999) | yes | 0.696 | 0.256 | 71.1% | 0.184 |
| leaky | 19,746 | 0.999 | 0.998 (0.987-0.999) | yes | 0.648 | 0.238 | 64.6% | 0.143 |
| regularized | 2,000 | 0.982 | 0.678 (0.648-0.699) | yes | 0.627 | 0.071 | 0.5% | 0.199 |
| regularized | 6,000 | 0.973 | 0.629 (0.603-0.662) | yes | 0.552 | 0.062 | 1.0% | 0.117 |
| regularized | 19,746 | 0.954 | 0.553 (0.531-0.571) | yes | 0.514 | 0.035 | 0.8% | 0.059 |

## 9. Thresholds fixed on the development cohort (tau = 0.1; 141 development cells, target sensitivity 90%)

The development thresholds are applied unchanged to these 141 cells, 129 of them exposed. "Recalibrated here" refits the threshold on this cohort's own cells, one configuration left out at a time, and shows what a fixed threshold loses.

| quantity | fixed rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated here: sensitivity / specificity |
|---|---|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.524 | 20/141 | 10/129 | 0.92 [0.88, 0.96] | 0.83 [0.67, 1.00] | 0.91 / 0.92 |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.602 | 48/141 | 36/129 | 0.72 [0.61, 0.83] | 1.00 [1.00, 1.00] | 0.90 / 1.00 |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.032 | 19/141 | 7/129 | 0.95 [0.91, 0.98] | 1.00 [1.00, 1.00] | 0.90 / 1.00 |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.039 | 7/141 | 0/129 | 1.00 [1.00, 1.00] | 0.58 [0.33, 0.67] | 0.91 / 0.92 |
