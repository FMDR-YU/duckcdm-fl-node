# Canary benchmark: release rules against planted-canary ground truth

141 cells (21 named, 120 space-filling; 47 configurations, 3 training sizes). Each cell = 48 models; each model contains a random half of 400 synthetic rows (each feature drawn independently from its own marginal, random label) (canaries), so the membership of every canary is known and a leave-one-model-out LiRA gives the ground-truth exposure. A cell is **exposed** when its canary TPR at 1% FPR is at least 0.1 (main definition; 0.05 and 0.25 as sensitivity analyses): 89 of 141 cells. Intervals are 95% percentile intervals over 2,000 resamples of whole configurations (all sizes of one configuration together).

## 1. Does the audit quantity tell exposed cells from unexposed ones? (threshold-free)

| quantity | AUC, tau = 0.1 [95% CI] | AUC, tau = 0.05 | AUC, tau = 0.25 | Spearman with canary TPR@1%FPR [95% CI] |
|---|---|---|---|---|
| shadow-model AUC | 0.94 [0.89, 0.98] | 0.94 | 0.94 | 0.88 [0.80, 0.92] |
| LiRA AUC (ordinary rows) | 0.99 [0.97, 1.00] | 1.00 | 1.00 | 0.99 [0.97, 0.99] |
| LiRA TPR@1%FPR (ordinary rows) | 0.99 [0.97, 1.00] | 0.99 | 1.00 | 0.98 [0.96, 0.99] |
| member / non-member AUROC gap | 0.93 [0.87, 0.97] | 0.94 | 0.91 | 0.82 [0.73, 0.87] |
| share of leaves < 11 rows | 0.66 [0.53, 0.78] | 0.54 | 0.77 | 0.44 [0.17, 0.65] |
| training rows (a larger value is safer) | 0.51 [0.45, 0.57] | 0.47 | 0.47 | 0.05 [-0.01, 0.13] |

Paired difference in AUC (tau = 0.1), LiRA TPR@1%FPR minus shadow-model AUC: 0.05 [0.02, 0.09]; LiRA AUC minus shadow-model AUC: 0.05 [0.02, 0.09]. Spearman is computed on the raw quantity (for training rows a negative value means larger is safer).

## 2. The rules at their prescribed thresholds (tau = 0.1)

| rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] |
|---|---|---|---|---|
| shadow-model AUC <= 0.55 (pilot release rule) | 52/141 | 9/89 | 0.90 [0.84, 0.95] | 0.83 [0.69, 0.93] |
| leaves with < 11 rows <= 10% | 101/141 | 51/89 | 0.43 [0.27, 0.61] | 0.96 [0.90, 1.00] |
| member / non-member AUROC gap <= 0.02 | 12/141 | 0/89 | 1.00 [1.00, 1.00] | 0.23 [0.09, 0.38] |
| training rows >= 10,000 (illustrative) | 47/141 | 30/89 | 0.66 [0.62, 0.70] | 0.33 [0.26, 0.38] |
| release every cell | 141/141 | 89/89 | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] |
| block every cell | 0/141 | 0/89 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

The same prescribed rules at the other definitions of "exposed" (sensitivity / specificity):

| rule | tau = 0.05 | tau = 0.1 | tau = 0.25 |
|---|---|---|---|
| cells exposed / unexposed | 116 / 25 | 89 / 52 | 51 / 90 |
| shadow-model AUC <= 0.55 (pilot release rule) | 0.76 / 0.96 | 0.90 / 0.83 | 1.00 / 0.58 |
| leaves with < 11 rows <= 10% | 0.34 / 1.00 | 0.43 / 0.96 | 0.61 / 0.90 |
| member / non-member AUROC gap <= 0.02 | 0.99 / 0.44 | 1.00 / 0.23 | 1.00 / 0.13 |
| training rows >= 10,000 (illustrative) | 0.66 / 0.28 | 0.66 / 0.33 | 0.65 / 0.32 |
| release every cell | 0.00 / 1.00 | 0.00 / 1.00 | 0.00 / 1.00 |
| block every cell | 1.00 / 0.00 | 1.00 / 0.00 | 1.00 / 0.00 |

## 3. Calibrated thresholds (tau = 0.1; the threshold must block at least 90% of the exposed cells)

In-sample = thresholds fitted on all cells here. Leave-one-configuration-out = each configuration is scored with a threshold fitted on the others (the interval resamples configurations and keeps the decisions fixed).

| quantity | calibrated rule | in-sample sensitivity / specificity | leave-one-configuration-out sensitivity [CI] | specificity [CI] |
|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.546 | 0.91 / 0.83 | 0.90 [0.83, 0.96] | 0.81 [0.66, 0.93] |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.633 | 0.91 / 0.96 | 0.91 [0.84, 0.96] | 0.96 [0.90, 1.00] |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.048 | 0.91 / 0.98 | 0.90 [0.83, 0.95] | 0.96 [0.90, 1.00] |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.077 | 0.91 / 0.81 | 0.91 [0.85, 0.96] | 0.79 [0.65, 0.91] |
| share of leaves < 11 rows | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |
| training rows (a larger value is safer) | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

## 4. What a miss costs: exposed cells (tau = 0.1) that each rule releases

| rule | exposed cells released | median canary TPR@1%FPR of those | highest | of those, at the largest training size | unexposed cells blocked |
|---|---|---|---|---|---|
| shadow-model AUC <= 0.55 (prescribed) | 9/89 | 0.132 | 0.199 | 9/9 | 9/52 |
| shadow-model AUC, calibrated in-sample | 8/89 | 0.127 | 0.189 | 8/8 | 9/52 |
| LiRA TPR@1%FPR, calibrated in-sample | 8/89 | 0.120 | 0.132 | 5/8 | 1/52 |
| LiRA TPR@1%FPR, calibrated leave-one-configuration-out | 9/89 | 0.118 | 0.132 | 5/9 | 2/52 |

## 5. From canary exposure to attacker precision

Share of flagged records that are true members at 1% FPR, when a fraction pi of the candidate records are members: PPV = TPR*pi / (TPR*pi + 0.01*(1-pi)). Which PPV is tolerable is a governance judgement; this study does not set it.

| exposure | canary TPR@1%FPR | PPV, pi = 0.1% | PPV, pi = 1.0% | PPV, pi = 10.0% |
|---|---|---|---|---|
| chance (TPR = FPR) | 0.010 | 0.1% | 1.0% | 10.0% |
| tau = 0.05 | 0.050 | 0.5% | 4.8% | 35.7% |
| tau = 0.1 | 0.100 | 1.0% | 9.2% | 52.6% |
| tau = 0.25 | 0.250 | 2.4% | 20.2% | 73.5% |
| median cell here | 0.155 | 1.5% | 13.5% | 63.2% |
| 90th-percentile cell here | 0.508 | 4.8% | 33.9% | 84.9% |
| most exposed cell here | 0.832 | 7.7% | 45.7% | 90.2% |

## 6. Consistency

| cells | n | exposed | AUC shadow-model | AUC LiRA AUC | AUC LiRA TPR@1%FPR |
|---|---|---|---|---|---|
| named configurations | 21 | 15 | 1.00 | 1.00 | 1.00 |
| space-filling configurations | 120 | 74 | 0.93 | 0.99 | 0.99 |

Cells whose model-resampling 95% interval of the canary TPR contains tau: 13 of 141 cells with an interval.

Median model-to-model SD of the canary AUC inside a cell: 0.019.

## 7. Named configurations

| config | n | canary AUC | canary TPR@1%FPR | exposed | shadow AUC | LiRA TPR@1%FPR | leaves < 11 | AUROC gap |
|---|---|---|---|---|---|---|---|---|
| d2_r100 | 2,000 | 0.605 | 0.031 (0.025-0.039) | no | 0.516 | 0.013 | 5.4% | 0.039 |
| d2_r100 | 6,000 | 0.570 | 0.027 (0.022-0.032) | no | 0.510 | 0.013 | 2.6% | 0.019 |
| d2_r100 | 19,746 | 0.544 | 0.020 (0.016-0.025) | no | 0.501 | 0.012 | 0.2% | 0.004 |
| d4_free | 2,000 | 0.854 | 0.185 (0.159-0.204) | yes | 0.616 | 0.079 | 31.2% | 0.163 |
| d4_free | 6,000 | 0.781 | 0.140 (0.122-0.155) | yes | 0.552 | 0.056 | 24.4% | 0.089 |
| d4_free | 19,746 | 0.723 | 0.098 (0.088-0.112) | no | 0.511 | 0.032 | 19.0% | 0.036 |
| d6_free | 2,000 | 0.974 | 0.582 (0.547-0.610) | yes | 0.793 | 0.312 | 56.6% | 0.203 |
| d6_free | 6,000 | 0.950 | 0.480 (0.461-0.497) | yes | 0.686 | 0.262 | 45.5% | 0.187 |
| d6_free | 19,746 | 0.921 | 0.398 (0.377-0.419) | yes | 0.585 | 0.149 | 36.9% | 0.135 |
| d6_mcw20 | 2,000 | 0.821 | 0.129 (0.122-0.148) | yes | 0.613 | 0.065 | 0.0% | 0.172 |
| d6_mcw20 | 6,000 | 0.822 | 0.155 (0.137-0.178) | yes | 0.585 | 0.077 | 0.0% | 0.139 |
| d6_mcw20 | 19,746 | 0.832 | 0.199 (0.180-0.217) | yes | 0.547 | 0.068 | 0.0% | 0.081 |
| krcp | 2,000 | 0.951 | 0.429 (0.399-0.470) | yes | 0.750 | 0.220 | 18.6% | 0.202 |
| krcp | 6,000 | 0.932 | 0.409 (0.384-0.424) | yes | 0.664 | 0.202 | 19.0% | 0.183 |
| krcp | 19,746 | 0.912 | 0.398 (0.381-0.421) | yes | 0.573 | 0.141 | 16.7% | 0.122 |
| leaky | 2,000 | 0.994 | 0.739 (0.693-0.846) | yes | 0.896 | 0.321 | 84.4% | 0.217 |
| leaky | 6,000 | 0.994 | 0.773 (0.767-0.821) | yes | 0.894 | 0.492 | 79.3% | 0.193 |
| leaky | 19,746 | 0.993 | 0.832 (0.825-0.845) | yes | 0.874 | 0.596 | 71.3% | 0.189 |
| regularized | 2,000 | 0.778 | 0.101 (0.087-0.112) | yes | 0.568 | 0.043 | 0.0% | 0.116 |
| regularized | 6,000 | 0.718 | 0.088 (0.076-0.098) | no | 0.533 | 0.038 | 0.0% | 0.061 |
| regularized | 19,746 | 0.687 | 0.079 (0.073-0.084) | no | 0.509 | 0.024 | 0.0% | 0.027 |

## 9. Thresholds fixed on the development cohort (tau = 0.1; 141 development cells, target sensitivity 90%)

The development thresholds are applied unchanged to these 141 cells, 89 of them exposed. "Recalibrated here" refits the threshold on this cohort's own cells, one configuration left out at a time, and shows what a fixed threshold loses.

| quantity | fixed rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated here: sensitivity / specificity |
|---|---|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.538 | 47/141 | 7/89 | 0.92 [0.86, 0.97] | 0.77 [0.63, 0.89] | 0.90 / 0.81 |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.629 | 54/141 | 5/89 | 0.94 [0.89, 0.99] | 0.94 [0.87, 1.00] | 0.91 / 0.96 |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.046 | 57/141 | 8/89 | 0.91 [0.84, 0.96] | 0.94 [0.87, 1.00] | 0.90 / 0.96 |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.052 | 31/141 | 3/89 | 0.97 [0.92, 1.00] | 0.54 [0.38, 0.69] | 0.91 / 0.79 |
