# Canary type across cohorts

Flipped-label canaries against synthetic canaries (each feature drawn from its own marginal, random label), the same cells in each cohort. Exposed = canary TPR at 1% FPR of at least 0.1. Intervals are 95% percentile intervals over 2,000 resamples of whole configurations. The last two columns are AUCs of the audit quantity of the synthetic-canary run for telling cells exposed under the synthetic canaries from the others.

| cohort | cells | exposed under both / only flipped / only synthetic / neither | label agreement | Spearman of the canary TPR [95% CI] | LiRA TPR@1%FPR AUC | shadow-model AUC AUC |
|---|---|---|---|---|---|---|
| SynPUF (development) | 141 | 71 / 15 / 0 / 55 | 89% | 0.99 [0.97, 0.99] | 0.99 [0.97, 1.00] | 0.92 [0.85, 0.97] |
| MIMIC-IV-ED | 141 | 89 / 18 / 0 / 34 | 87% | 0.99 [0.98, 0.99] | 0.99 [0.97, 1.00] | 0.94 [0.89, 0.98] |
| eICU-CRD | 141 | 121 / 8 / 0 / 12 | 94% | 0.95 [0.92, 0.97] | 1.00 [0.99, 1.00] | 0.98 [0.95, 0.99] |
