# Canary benchmark: release rules against planted-canary ground truth

141 cells (21 named, 120 space-filling; 47 configurations, 3 training sizes). Each cell = 48 models; each model contains a random half of 400 synthetic rows (each feature drawn independently from its own marginal, random label) (canaries), so the membership of every canary is known and a leave-one-model-out LiRA gives the ground-truth exposure. A cell is **exposed** when its canary TPR at 1% FPR is at least 0.1 (main definition; 0.05 and 0.25 as sensitivity analyses): 121 of 141 cells. Intervals are 95% percentile intervals over 2,000 resamples of whole configurations (all sizes of one configuration together).

## 1. Does the audit quantity tell exposed cells from unexposed ones? (threshold-free)

| quantity | AUC, tau = 0.1 [95% CI] | AUC, tau = 0.05 | AUC, tau = 0.25 | Spearman with canary TPR@1%FPR [95% CI] |
|---|---|---|---|---|
| shadow-model AUC | 0.98 [0.95, 0.99] | 0.99 | 0.96 | 0.86 [0.78, 0.91] |
| LiRA AUC (ordinary rows) | 0.99 [0.98, 1.00] | 1.00 | 1.00 | 0.97 [0.95, 0.98] |
| LiRA TPR@1%FPR (ordinary rows) | 1.00 [0.99, 1.00] | 1.00 | 1.00 | 0.96 [0.94, 0.98] |
| member / non-member AUROC gap | 0.96 [0.89, 0.99] | 0.99 | 0.59 | 0.49 [0.27, 0.66] |
| share of leaves < 11 rows | 0.66 [0.54, 0.78] | 0.66 | 0.99 | 0.58 [0.40, 0.70] |
| training rows (a larger value is safer) | 0.60 [0.50, 0.72] | 0.57 | 0.33 | 0.01 [-0.10, 0.12] |

Paired difference in AUC (tau = 0.1), LiRA TPR@1%FPR minus shadow-model AUC: 0.02 [0.00, 0.04]; LiRA AUC minus shadow-model AUC: 0.01 [-0.00, 0.04]. Spearman is computed on the raw quantity (for training rows a negative value means larger is safer).

## 2. The rules at their prescribed thresholds (tau = 0.1)

| rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] |
|---|---|---|---|---|
| shadow-model AUC <= 0.55 (pilot release rule) | 50/141 | 30/121 | 0.75 [0.64, 0.85] | 1.00 [1.00, 1.00] |
| leaves with < 11 rows <= 10% | 98/141 | 78/121 | 0.36 [0.22, 0.51] | 1.00 [1.00, 1.00] |
| member / non-member AUROC gap <= 0.02 | 4/141 | 0/121 | 1.00 [1.00, 1.00] | 0.20 [0.06, 0.28] |
| training rows >= 10,000 (illustrative) | 47/141 | 37/121 | 0.69 [0.67, 0.72] | 0.50 [0.38, 0.72] |
| release every cell | 141/141 | 121/121 | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] |
| block every cell | 0/141 | 0/121 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

The same prescribed rules at the other definitions of "exposed" (sensitivity / specificity):

| rule | tau = 0.05 | tau = 0.1 | tau = 0.25 |
|---|---|---|---|
| cells exposed / unexposed | 131 / 10 | 121 / 20 | 2 / 139 |
| shadow-model AUC <= 0.55 (pilot release rule) | 0.69 / 1.00 | 0.75 / 1.00 | 1.00 / 0.36 |
| leaves with < 11 rows <= 10% | 0.33 / 1.00 | 0.36 / 1.00 | 1.00 / 0.71 |
| member / non-member AUROC gap <= 0.02 | 1.00 / 0.40 | 1.00 / 0.20 | 1.00 / 0.03 |
| training rows >= 10,000 (illustrative) | 0.67 / 0.40 | 0.69 / 0.50 | 0.50 / 0.33 |
| release every cell | 0.00 / 1.00 | 0.00 / 1.00 | 0.00 / 1.00 |
| block every cell | 1.00 / 0.00 | 1.00 / 0.00 | 1.00 / 0.00 |

## 3. Calibrated thresholds (tau = 0.1; the threshold must block at least 90% of the exposed cells)

In-sample = thresholds fitted on all cells here. Leave-one-configuration-out = each configuration is scored with a threshold fitted on the others (the interval resamples configurations and keeps the decisions fixed).

| quantity | calibrated rule | in-sample sensitivity / specificity | leave-one-configuration-out sensitivity [CI] | specificity [CI] |
|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.532 | 0.90 / 0.95 | 0.91 [0.86, 0.95] | 0.95 [0.80, 1.00] |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.579 | 0.90 / 1.00 | 0.90 [0.84, 0.95] | 1.00 [1.00, 1.00] |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.051 | 0.90 / 1.00 | 0.91 [0.86, 0.96] | 1.00 [1.00, 1.00] |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.107 | 0.90 / 0.95 | 0.90 [0.85, 0.95] | 0.90 [0.69, 1.00] |
| share of leaves < 11 rows | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |
| training rows (a larger value is safer) | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

## 4. What a miss costs: exposed cells (tau = 0.1) that each rule releases

| rule | exposed cells released | median canary TPR@1%FPR of those | highest | of those, at the largest training size | unexposed cells blocked |
|---|---|---|---|---|---|
| shadow-model AUC <= 0.55 (prescribed) | 30/121 | 0.116 | 0.132 | 14/30 | 0/20 |
| shadow-model AUC, calibrated in-sample | 12/121 | 0.115 | 0.131 | 9/12 | 1/20 |
| LiRA TPR@1%FPR, calibrated in-sample | 12/121 | 0.112 | 0.122 | 8/12 | 0/20 |
| LiRA TPR@1%FPR, calibrated leave-one-configuration-out | 11/121 | 0.111 | 0.122 | 7/11 | 0/20 |

## 5. From canary exposure to attacker precision

Share of flagged records that are true members at 1% FPR, when a fraction pi of the candidate records are members: PPV = TPR*pi / (TPR*pi + 0.01*(1-pi)). Which PPV is tolerable is a governance judgement; this study does not set it.

| exposure | canary TPR@1%FPR | PPV, pi = 0.1% | PPV, pi = 1.0% | PPV, pi = 10.0% |
|---|---|---|---|---|
| chance (TPR = FPR) | 0.010 | 0.1% | 1.0% | 10.0% |
| tau = 0.05 | 0.050 | 0.5% | 4.8% | 35.7% |
| tau = 0.1 | 0.100 | 1.0% | 9.2% | 52.6% |
| tau = 0.25 | 0.250 | 2.4% | 20.2% | 73.5% |
| median cell here | 0.129 | 1.3% | 11.6% | 59.0% |
| 90th-percentile cell here | 0.162 | 1.6% | 14.1% | 64.3% |
| most exposed cell here | 0.277 | 2.7% | 21.9% | 75.5% |

## 6. Consistency

| cells | n | exposed | AUC shadow-model | AUC LiRA AUC | AUC LiRA TPR@1%FPR |
|---|---|---|---|---|---|
| named configurations | 21 | 18 | 0.96 | 1.00 | 1.00 |
| space-filling configurations | 120 | 103 | 0.98 | 0.99 | 1.00 |

Cells whose model-resampling 95% interval of the canary TPR contains tau: 8 of 141 cells with an interval.

Median model-to-model SD of the canary AUC inside a cell: 0.024.

## 7. Named configurations

| config | n | canary AUC | canary TPR@1%FPR | exposed | shadow AUC | LiRA TPR@1%FPR | leaves < 11 | AUROC gap |
|---|---|---|---|---|---|---|---|---|
| d2_r100 | 2,000 | 0.591 | 0.067 (0.059-0.075) | no | 0.523 | 0.023 | 5.0% | 0.100 |
| d2_r100 | 6,000 | 0.568 | 0.041 (0.037-0.047) | no | 0.506 | 0.021 | 1.5% | 0.053 |
| d2_r100 | 19,746 | 0.553 | 0.038 (0.032-0.046) | no | 0.508 | 0.013 | 0.4% | 0.012 |
| d4_free | 2,000 | 0.700 | 0.133 (0.125-0.143) | yes | 0.594 | 0.106 | 31.0% | 0.168 |
| d4_free | 6,000 | 0.670 | 0.123 (0.118-0.128) | yes | 0.548 | 0.086 | 22.6% | 0.138 |
| d4_free | 19,746 | 0.645 | 0.114 (0.106-0.120) | yes | 0.514 | 0.044 | 15.3% | 0.065 |
| d6_free | 2,000 | 0.808 | 0.172 (0.161-0.183) | yes | 0.670 | 0.160 | 54.9% | 0.171 |
| d6_free | 6,000 | 0.773 | 0.154 (0.147-0.167) | yes | 0.621 | 0.156 | 49.3% | 0.149 |
| d6_free | 19,746 | 0.744 | 0.161 (0.154-0.173) | yes | 0.580 | 0.125 | 39.0% | 0.132 |
| d6_mcw20 | 2,000 | 0.684 | 0.129 (0.123-0.135) | yes | 0.598 | 0.089 | 0.0% | 0.159 |
| d6_mcw20 | 6,000 | 0.688 | 0.133 (0.128-0.139) | yes | 0.584 | 0.098 | 0.0% | 0.139 |
| d6_mcw20 | 19,746 | 0.705 | 0.129 (0.124-0.136) | yes | 0.554 | 0.086 | 0.0% | 0.119 |
| krcp | 2,000 | 0.769 | 0.156 (0.151-0.166) | yes | 0.646 | 0.128 | 14.3% | 0.149 |
| krcp | 6,000 | 0.750 | 0.162 (0.155-0.172) | yes | 0.620 | 0.143 | 16.5% | 0.140 |
| krcp | 19,746 | 0.739 | 0.146 (0.140-0.155) | yes | 0.569 | 0.118 | 19.8% | 0.126 |
| leaky | 2,000 | 0.795 | 0.131 (0.127-0.136) | yes | 0.636 | 0.114 | 75.2% | 0.192 |
| leaky | 6,000 | 0.884 | 0.265 (0.244-0.270) | yes | 0.661 | 0.224 | 71.9% | 0.149 |
| leaky | 19,746 | 0.852 | 0.277 (0.269-0.286) | yes | 0.648 | 0.249 | 65.7% | 0.132 |
| regularized | 2,000 | 0.666 | 0.120 (0.116-0.127) | yes | 0.583 | 0.080 | 1.6% | 0.146 |
| regularized | 6,000 | 0.645 | 0.120 (0.112-0.128) | yes | 0.544 | 0.068 | 1.4% | 0.108 |
| regularized | 19,746 | 0.632 | 0.111 (0.106-0.118) | yes | 0.509 | 0.039 | 0.9% | 0.058 |

## 9. Thresholds fixed on the development cohort (tau = 0.1; 141 development cells, target sensitivity 90%)

The development thresholds are applied unchanged to these 141 cells, 121 of them exposed. "Recalibrated here" refits the threshold on this cohort's own cells, one configuration left out at a time, and shows what a fixed threshold loses.

| quantity | fixed rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated here: sensitivity / specificity |
|---|---|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.538 | 34/141 | 15/121 | 0.88 [0.81, 0.93] | 0.95 [0.80, 1.00] | 0.91 / 0.95 |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.629 | 77/141 | 57/121 | 0.53 [0.39, 0.66] | 1.00 [1.00, 1.00] | 0.90 / 1.00 |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.046 | 26/141 | 6/121 | 0.95 [0.91, 0.98] | 1.00 [1.00, 1.00] | 0.91 / 1.00 |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.052 | 10/141 | 0/121 | 1.00 [1.00, 1.00] | 0.50 [0.25, 0.70] | 0.90 / 0.90 |
