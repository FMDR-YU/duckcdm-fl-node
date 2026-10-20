# Canary benchmark: release rules against planted-canary ground truth

141 cells (21 named, 120 space-filling; 47 configurations, 3 training sizes). Each cell = 48 models; each model contains a random half of 400 label-flipped real rows (canaries), so the membership of every canary is known and a leave-one-model-out LiRA gives the ground-truth exposure. A cell is **exposed** when its canary TPR at 1% FPR is at least 0.1 (main definition; 0.05 and 0.25 as sensitivity analyses): 86 of 141 cells. Intervals are 95% percentile intervals over 2,000 resamples of whole configurations (all sizes of one configuration together).

## 1. Does the audit quantity tell exposed cells from unexposed ones? (threshold-free)

| quantity | AUC, tau = 0.1 [95% CI] | AUC, tau = 0.05 | AUC, tau = 0.25 | Spearman with canary TPR@1%FPR [95% CI] |
|---|---|---|---|---|
| shadow-model AUC | 0.91 [0.85, 0.96] | 0.89 | 0.93 | 0.83 [0.73, 0.89] |
| LiRA AUC (ordinary rows) | 0.99 [0.97, 1.00] | 0.99 | 0.99 | 0.98 [0.95, 0.99] |
| LiRA TPR@1%FPR (ordinary rows) | 0.98 [0.96, 0.99] | 0.99 | 0.99 | 0.98 [0.95, 0.99] |
| member / non-member AUROC gap | 0.90 [0.83, 0.95] | 0.90 | 0.89 | 0.79 [0.68, 0.84] |
| share of leaves < 11 rows | 0.69 [0.57, 0.81] | 0.59 | 0.81 | 0.52 [0.25, 0.70] |
| training rows (a larger value is safer) | 0.47 [0.41, 0.53] | 0.39 | 0.45 | 0.12 [0.06, 0.20] |

Paired difference in AUC (tau = 0.1), LiRA TPR@1%FPR minus shadow-model AUC: 0.07 [0.03, 0.12]; LiRA AUC minus shadow-model AUC: 0.07 [0.03, 0.13]. Spearman is computed on the raw quantity (for training rows a negative value means larger is safer).

## 2. The rules at their prescribed thresholds (tau = 0.1)

| rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] |
|---|---|---|---|---|
| shadow-model AUC <= 0.55 (pilot release rule) | 66/141 | 20/86 | 0.77 [0.66, 0.87] | 0.84 [0.70, 0.94] |
| leaves with < 11 rows <= 10% | 102/141 | 49/86 | 0.43 [0.26, 0.61] | 0.96 [0.88, 1.00] |
| member / non-member AUROC gap <= 0.02 | 20/141 | 2/86 | 0.98 [0.94, 1.00] | 0.33 [0.16, 0.50] |
| training rows >= 10,000 (illustrative) | 47/141 | 31/86 | 0.64 [0.59, 0.68] | 0.29 [0.23, 0.35] |
| release every cell | 141/141 | 86/86 | 0.00 [0.00, 0.00] | 1.00 [1.00, 1.00] |
| block every cell | 0/141 | 0/86 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

The same prescribed rules at the other definitions of "exposed" (sensitivity / specificity):

| rule | tau = 0.05 | tau = 0.1 | tau = 0.25 |
|---|---|---|---|
| cells exposed / unexposed | 114 / 27 | 86 / 55 | 51 / 90 |
| shadow-model AUC <= 0.55 (pilot release rule) | 0.65 / 0.96 | 0.77 / 0.84 | 0.94 / 0.70 |
| leaves with < 11 rows <= 10% | 0.34 / 1.00 | 0.43 / 0.96 | 0.63 / 0.92 |
| member / non-member AUROC gap <= 0.02 | 0.94 / 0.48 | 0.98 / 0.33 | 1.00 / 0.22 |
| training rows >= 10,000 (illustrative) | 0.63 / 0.19 | 0.64 / 0.29 | 0.63 / 0.31 |
| release every cell | 0.00 / 1.00 | 0.00 / 1.00 | 0.00 / 1.00 |
| block every cell | 1.00 / 0.00 | 1.00 / 0.00 | 1.00 / 0.00 |

## 3. Calibrated thresholds (tau = 0.1; the threshold must block at least 90% of the exposed cells)

In-sample = thresholds fitted on all cells here. Leave-one-configuration-out = each configuration is scored with a threshold fitted on the others (the interval resamples configurations and keeps the decisions fixed).

| quantity | calibrated rule | in-sample sensitivity / specificity | leave-one-configuration-out sensitivity [CI] | specificity [CI] |
|---|---|---|---|---|
| shadow-model AUC | shadow-model AUC <= 0.524 | 0.91 / 0.67 | 0.90 [0.83, 0.95] | 0.67 [0.51, 0.82] |
| LiRA AUC (ordinary rows) | LiRA AUC <= 0.602 | 0.91 / 0.98 | 0.91 [0.82, 0.97] | 0.96 [0.91, 1.00] |
| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= 0.032 | 0.91 / 0.91 | 0.90 [0.81, 0.96] | 0.91 [0.83, 0.98] |
| member / non-member AUROC gap | member / non-member AUROC gap <= 0.039 | 0.91 / 0.69 | 0.91 [0.84, 0.96] | 0.67 [0.48, 0.83] |
| share of leaves < 11 rows | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |
| training rows (a larger value is safer) | block every cell | 1.00 / 0.00 | 1.00 [1.00, 1.00] | 0.00 [0.00, 0.00] |

## 4. What a miss costs: exposed cells (tau = 0.1) that each rule releases

| rule | exposed cells released | median canary TPR@1%FPR of those | highest | of those, at the largest training size | unexposed cells blocked |
|---|---|---|---|---|---|
| shadow-model AUC <= 0.55 (prescribed) | 20/86 | 0.196 | 0.384 | 14/20 | 9/55 |
| shadow-model AUC, calibrated in-sample | 8/86 | 0.128 | 0.243 | 7/8 | 18/55 |
| LiRA TPR@1%FPR, calibrated in-sample | 8/86 | 0.116 | 0.185 | 5/8 | 5/55 |
| LiRA TPR@1%FPR, calibrated leave-one-configuration-out | 9/86 | 0.113 | 0.185 | 5/9 | 5/55 |

## 5. From canary exposure to attacker precision

Share of flagged records that are true members at 1% FPR, when a fraction pi of the candidate records are members: PPV = TPR*pi / (TPR*pi + 0.01*(1-pi)). Which PPV is tolerable is a governance judgement; this study does not set it.

| exposure | canary TPR@1%FPR | PPV, pi = 0.1% | PPV, pi = 1.0% | PPV, pi = 10.0% |
|---|---|---|---|---|
| chance (TPR = FPR) | 0.010 | 0.1% | 1.0% | 10.0% |
| tau = 0.05 | 0.050 | 0.5% | 4.8% | 35.7% |
| tau = 0.1 | 0.100 | 1.0% | 9.2% | 52.6% |
| tau = 0.25 | 0.250 | 2.4% | 20.2% | 73.5% |
| median cell here | 0.141 | 1.4% | 12.5% | 61.1% |
| 90th-percentile cell here | 0.676 | 6.3% | 40.6% | 88.3% |
| most exposed cell here | 0.983 | 9.0% | 49.8% | 91.6% |

## 6. Consistency

| cells | n | exposed | AUC shadow-model | AUC LiRA AUC | AUC LiRA TPR@1%FPR |
|---|---|---|---|---|---|
| named configurations | 21 | 15 | 0.83 | 0.97 | 0.95 |
| space-filling configurations | 120 | 71 | 0.93 | 0.99 | 0.98 |

Cells whose model-resampling 95% interval of the canary TPR contains tau: 15 of 141 cells with an interval.

Median model-to-model SD of the canary AUC inside a cell: 0.018.

## 7. Named configurations

| config | n | canary AUC | canary TPR@1%FPR | exposed | shadow AUC | LiRA TPR@1%FPR | leaves < 11 | AUROC gap |
|---|---|---|---|---|---|---|---|---|
| d2_r100 | 2,000 | 0.640 | 0.036 (0.030-0.043) | no | 0.521 | 0.013 | 6.1% | 0.033 |
| d2_r100 | 6,000 | 0.593 | 0.026 (0.022-0.033) | no | 0.506 | 0.012 | 2.4% | 0.013 |
| d2_r100 | 19,746 | 0.566 | 0.024 (0.019-0.028) | no | 0.500 | 0.011 | 0.8% | 0.005 |
| d4_free | 2,000 | 0.892 | 0.275 (0.245-0.297) | yes | 0.608 | 0.068 | 40.0% | 0.125 |
| d4_free | 6,000 | 0.829 | 0.227 (0.210-0.247) | yes | 0.539 | 0.052 | 31.2% | 0.063 |
| d4_free | 19,746 | 0.777 | 0.185 (0.175-0.195) | yes | 0.508 | 0.028 | 22.8% | 0.025 |
| d6_free | 2,000 | 0.990 | 0.748 (0.725-0.766) | yes | 0.740 | 0.224 | 64.7% | 0.157 |
| d6_free | 6,000 | 0.979 | 0.653 (0.632-0.674) | yes | 0.636 | 0.180 | 55.3% | 0.124 |
| d6_free | 19,746 | 0.958 | 0.588 (0.565-0.604) | yes | 0.570 | 0.122 | 45.8% | 0.082 |
| d6_mcw20 | 2,000 | 0.803 | 0.082 (0.073-0.093) | no | 0.569 | 0.034 | 0.0% | 0.111 |
| d6_mcw20 | 6,000 | 0.814 | 0.120 (0.104-0.139) | yes | 0.549 | 0.043 | 0.0% | 0.077 |
| d6_mcw20 | 19,746 | 0.844 | 0.218 (0.205-0.241) | yes | 0.528 | 0.043 | 0.0% | 0.047 |
| krcp | 2,000 | 0.971 | 0.498 (0.462-0.546) | yes | 0.684 | 0.119 | 23.0% | 0.156 |
| krcp | 6,000 | 0.958 | 0.527 (0.509-0.550) | yes | 0.611 | 0.129 | 20.9% | 0.121 |
| krcp | 19,746 | 0.941 | 0.505 (0.483-0.528) | yes | 0.558 | 0.097 | 17.7% | 0.077 |
| leaky | 2,000 | 0.998 | 0.974 (0.968-0.979) | yes | 0.887 | 0.302 | 85.1% | 0.182 |
| leaky | 6,000 | 0.998 | 0.975 (0.972-0.982) | yes | 0.841 | 0.354 | 81.2% | 0.149 |
| leaky | 19,746 | 0.998 | 0.983 (0.978-0.988) | yes | 0.818 | 0.463 | 77.1% | 0.134 |
| regularized | 2,000 | 0.778 | 0.085 (0.065-0.100) | no | 0.552 | 0.024 | 0.0% | 0.077 |
| regularized | 6,000 | 0.743 | 0.081 (0.067-0.089) | no | 0.520 | 0.028 | 0.0% | 0.037 |
| regularized | 19,746 | 0.734 | 0.108 (0.095-0.122) | yes | 0.517 | 0.023 | 0.0% | 0.015 |

## 8. Robustness to the canary type

141 cells (47 configurations) in both runs. Spearman correlation of the canary TPR@1%FPR between the flip and shuffle canaries: 0.99 [0.97, 0.99]. Exposure labels (tau = 0.1) agree in 89% of cells [82, 95]% (exposed under both 71, only flip 15, only shuffle 0, neither 55).

AUC of each audit quantity for telling exposed from unexposed cells (tau = 0.1) under either definition of the ground truth:

| quantity | flip truth, flip-run audit | shuffle truth, shuffle-run audit | shuffle truth, flip-run audit |
|---|---|---|---|
| shadow-model AUC | 0.91 [0.85, 0.96] | 0.92 [0.85, 0.97] | 0.91 [0.85, 0.96] |
| LiRA AUC (ordinary rows) | 0.99 [0.97, 1.00] | 0.98 [0.96, 1.00] | 0.98 [0.96, 1.00] |
| LiRA TPR@1%FPR (ordinary rows) | 0.98 [0.96, 0.99] | 0.99 [0.97, 1.00] | 0.99 [0.97, 1.00] |
| member / non-member AUROC gap | 0.90 [0.83, 0.95] | 0.92 [0.86, 0.97] | 0.90 [0.83, 0.96] |
| share of leaves < 11 rows | 0.69 [0.57, 0.81] | 0.79 [0.67, 0.89] | 0.78 [0.66, 0.89] |
| training rows (a larger value is safer) | 0.47 [0.41, 0.53] | 0.47 [0.43, 0.51] | 0.47 [0.43, 0.51] |

Rules scored with the flip-run audit against each ground truth (sensitivity / specificity):

| rule | flip truth | shuffle truth |
|---|---|---|
| shadow-model AUC <= 0.55 (prescribed) | 0.77 / 0.84 | 0.83 / 0.77 |
| LiRA TPR@1%FPR, threshold calibrated on the flip cells (0.032) | 0.91 / 0.91 | 0.97 / 0.80 |
