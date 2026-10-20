# Pilot summary — synpuf

seeds: [42, 43, 44, 45, 46, 47, 48, 49, 50, 51] · values = mean [95% CI across seeds]

## Pre-specified decision rules (docs/ANALYSIS_PLAN_v1.md §3), evaluated by code

| hypothesis | role | variant / target | verdict | evidence |
|---|---|---|---|---|
| H1 | secondary | leaky vs regularized | **supported** | shadow AUC leaky 0.782 > 0.55: yes; regularized 0.501 <= 0.55: yes; AUROC regularized 0.899 >= leaky 0.886: yes |
| H2 | primary | krcp B1 (size) | **supported** | gap B1 0.049 [0.045–0.053] lower bound > 0: yes; size share (A′−A)/(B1 gap) 1.04 >= 0.5: yes |
| H2 | secondary | krcp B2 (unequal sites) | **supported** | gap B2 0.054 [0.048–0.059] lower bound > 0: yes; B2 gap > B1 gap: yes |
| H2 | secondary | leaky B1 (size) | **supported** | gap B1 0.002 [0.001–0.003] lower bound > 0: yes; size share (A′−A)/(B1 gap) 1.39 >= 0.5: yes |
| H2 | secondary | leaky B2 (unequal sites) | **supported** | gap B2 0.006 [0.003–0.009] lower bound > 0: yes; B2 gap > B1 gap: yes |
| H2 | secondary | regularized B1 (size) | **supported** | gap B1 0.011 [0.007–0.014] lower bound > 0: yes; size share (A′−A)/(B1 gap) 1.13 >= 0.5: yes |
| H2 | secondary | regularized B2 (unequal sites) | **supported** | gap B2 0.012 [0.006–0.019] lower bound > 0: yes; B2 gap > B1 gap: yes |
| H3 | secondary | krcp B1_comb | **supported** | ΔAUROC 0.000 [-0.000–0.000] lower bound > −0.02: yes |
| H3 | secondary | krcp B2_comb | **supported** | ΔAUROC -0.000 [-0.000–0.000] lower bound > −0.02: yes |
| H3 | secondary | leaky B1_comb | **supported** | ΔAUROC 0.006 [0.006–0.007] lower bound > −0.02: yes |
| H3 | secondary | leaky B2_comb | **supported** | ΔAUROC 0.006 [0.006–0.007] lower bound > −0.02: yes |
| H3 | secondary | regularized B1_comb | **supported** | ΔAUROC -0.000 [-0.000–-0.000] lower bound > −0.02: yes |
| H3 | secondary | regularized B2_comb | **supported** | ΔAUROC -0.000 [-0.000–-0.000] lower bound > −0.02: yes |
| H4 | secondary | krcp | **supported** | Gate 1 max abs Δp 3.3e-16 < 1e-6: yes; Gate 3 signature and data hash match: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |
| H4 | secondary | leaky | **supported** | Gate 1 max abs Δp 0.0e+00 < 1e-6: yes; Gate 3 signature and data hash match: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |
| H4 | secondary | regularized | **supported** | Gate 1 max abs Δp 8.9e-16 < 1e-6: yes; Gate 3 signature and data hash match: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |

Primary verdicts: H5 and the B1 part of H2 for the published configuration (krcp) with equal sites (B1). Every other row is secondary. Each hypothesis is judged on its own; no multiplicity correction. Intervals are t-based across seeds (utility differences also have paired bootstrap intervals in 01_utility_long.csv). "not evaluable" means an input is missing or has fewer than two seeds.

## Gate 2 — membership inference (AUC; decision on shadow-model attack, threshold 0.55)

| variant | target | n members | shadow AUC | loss AUC | LiRA AUC | LiRA TPR@1%FPR | decision |
|---|---|---|---|---|---|---|---|
| krcp | A_0 | 19,746 | 0.532 [0.529–0.534] | 0.520 [0.518–0.521] | 0.732 [0.731–0.733] | 0.124 [0.122–0.127] | PASS |
| krcp | Aprime_0 | 6,582 | 0.582 [0.579–0.586] | 0.551 [0.547–0.556] | 0.747 [0.743–0.752] | 0.137 [0.131–0.144] | BLOCK |
| krcp | B1_0 | 6,582 | 0.582 [0.579–0.585] | 0.551 [0.547–0.555] | 0.747 [0.743–0.752] | 0.134 [0.126–0.141] | BLOCK |
| krcp | B1_1 | 6,582 | 0.578 [0.574–0.582] | 0.548 [0.545–0.552] | 0.745 [0.741–0.749] | 0.139 [0.132–0.147] | BLOCK |
| krcp | B1_2 | 6,582 | 0.582 [0.577–0.586] | 0.551 [0.547–0.554] | 0.745 [0.743–0.748] | 0.133 [0.127–0.140] | BLOCK |
| krcp | B1_comb | 19,746 | 0.522 [0.521–0.524] | 0.512 [0.510–0.513] | 0.673 [0.672–0.675] | 0.083 [0.079–0.087] | PASS |
| krcp | B2_0 | 9,873 | 0.559 [0.552–0.566] | 0.534 [0.529–0.540] | 0.731 [0.728–0.733] | 0.122 [0.116–0.128] | BLOCK |
| krcp | B2_1 | 5,924 | 0.582 [0.569–0.595] | 0.554 [0.548–0.559] | 0.740 [0.731–0.748] | 0.126 [0.113–0.138] | BLOCK |
| krcp | B2_2 | 3,949 | 0.615 [0.606–0.625] | 0.568 [0.563–0.574] | 0.761 [0.752–0.770] | 0.149 [0.138–0.160] | BLOCK |
| krcp | B2_comb | 19,746 | 0.518 [0.516–0.521] | 0.511 [0.510–0.512] | 0.657 [0.652–0.661] | 0.081 [0.076–0.085] | PASS |
| leaky | A_0 | 19,746 | 0.782 [0.781–0.783] | 0.667 [0.666–0.667] | 0.948 [0.948–0.949] | 0.648 [0.641–0.656] | BLOCK |
| leaky | Aprime_0 | 6,582 | 0.784 [0.781–0.788] | 0.671 [0.667–0.676] | 0.927 [0.926–0.929] | 0.508 [0.477–0.539] | BLOCK |
| leaky | B1_0 | 6,582 | 0.781 [0.778–0.785] | 0.671 [0.668–0.674] | 0.927 [0.925–0.929] | 0.523 [0.512–0.534] | BLOCK |
| leaky | B1_1 | 6,582 | 0.785 [0.781–0.789] | 0.671 [0.668–0.674] | 0.928 [0.926–0.930] | 0.520 [0.504–0.536] | BLOCK |
| leaky | B1_2 | 6,582 | 0.784 [0.781–0.787] | 0.670 [0.666–0.674] | 0.927 [0.926–0.928] | 0.512 [0.493–0.531] | BLOCK |
| leaky | B1_comb | 19,746 | 0.588 [0.587–0.590] | 0.537 [0.536–0.538] | 0.747 [0.745–0.749] | 0.126 [0.121–0.131] | BLOCK |
| leaky | B2_0 | 9,873 | 0.782 [0.778–0.786] | 0.668 [0.662–0.674] | 0.935 [0.934–0.936] | 0.549 [0.536–0.562] | BLOCK |
| leaky | B2_1 | 5,924 | 0.787 [0.781–0.793] | 0.675 [0.667–0.683] | 0.926 [0.924–0.928] | 0.473 [0.442–0.504] | BLOCK |
| leaky | B2_2 | 3,949 | 0.794 [0.785–0.804] | 0.676 [0.671–0.681] | 0.915 [0.912–0.919] | 0.392 [0.346–0.438] | BLOCK |
| leaky | B2_comb | 19,746 | 0.587 [0.585–0.590] | 0.537 [0.536–0.538] | 0.740 [0.737–0.744] | 0.123 [0.113–0.133] | BLOCK |
| regularized | A_0 | 19,746 | 0.501 [0.499–0.504] | 0.501 [0.499–0.502] | 0.584 [0.582–0.586] | 0.025 [0.021–0.028] | PASS |
| regularized | Aprime_0 | 6,582 | 0.513 [0.511–0.516] | 0.509 [0.505–0.513] | 0.583 [0.579–0.587] | 0.034 [0.031–0.036] | PASS |
| regularized | B1_0 | 6,582 | 0.514 [0.513–0.515] | 0.510 [0.506–0.514] | 0.585 [0.580–0.589] | 0.033 [0.030–0.037] | PASS |
| regularized | B1_1 | 6,582 | 0.509 [0.506–0.511] | 0.506 [0.502–0.510] | 0.579 [0.575–0.583] | 0.036 [0.032–0.040] | PASS |
| regularized | B1_2 | 6,582 | 0.513 [0.510–0.517] | 0.509 [0.506–0.512] | 0.582 [0.579–0.585] | 0.035 [0.031–0.038] | PASS |
| regularized | B1_comb | 19,746 | 0.502 [0.499–0.504] | 0.499 [0.498–0.500] | 0.560 [0.557–0.562] | 0.024 [0.022–0.026] | PASS |
| regularized | B2_0 | 9,873 | 0.509 [0.503–0.515] | 0.502 [0.497–0.507] | 0.580 [0.576–0.583] | 0.031 [0.026–0.036] | PASS |
| regularized | B2_1 | 5,924 | 0.510 [0.495–0.524] | 0.512 [0.505–0.520] | 0.575 [0.569–0.581] | 0.028 [0.024–0.032] | PASS |
| regularized | B2_2 | 3,949 | 0.522 [0.518–0.526] | 0.513 [0.507–0.519] | 0.587 [0.582–0.593] | 0.034 [0.032–0.036] | PASS |
| regularized | B2_comb | 19,746 | 0.502 [0.499–0.505] | 0.498 [0.497–0.499] | 0.550 [0.547–0.553] | 0.023 [0.020–0.025] | PASS |

Threshold sweep (shadow-model mean AUC):

| variant | target | ≤0.50 | ≤0.52 | ≤0.55 | ≤0.58 | ≤0.60 |
|---|---|---|---|---|---|---|
| krcp | A_0 | BLOCK | BLOCK | PASS | PASS | PASS |
| krcp | Aprime_0 | BLOCK | BLOCK | BLOCK | BLOCK | PASS |
| krcp | B1_comb | BLOCK | BLOCK | PASS | PASS | PASS |
| krcp | B2_comb | BLOCK | PASS | PASS | PASS | PASS |
| leaky | A_0 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| leaky | Aprime_0 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| leaky | B1_comb | BLOCK | BLOCK | BLOCK | BLOCK | PASS |
| leaky | B2_comb | BLOCK | BLOCK | BLOCK | BLOCK | PASS |
| regularized | A_0 | BLOCK | PASS | PASS | PASS | PASS |
| regularized | Aprime_0 | BLOCK | PASS | PASS | PASS | PASS |
| regularized | B1_comb | BLOCK | PASS | PASS | PASS | PASS |
| regularized | B2_comb | BLOCK | PASS | PASS | PASS | PASS |

## Exposure relative to the central model, by attack (route − A; mean [95% CI across seeds]; descriptive)

| variant | route | shadow AUC | LiRA AUC | LiRA TPR@1%FPR | loss AUC |
|---|---|---|---|---|---|
| krcp | A′ (size control) | 0.051 [0.046–0.055] | 0.015 [0.011–0.019] | 0.013 [0.007–0.019] | 0.032 [0.027–0.036] |
| krcp | B1 sites (mean of 3) | 0.049 [0.045–0.053] | 0.014 [0.011–0.016] | 0.011 [0.007–0.016] | 0.031 [0.029–0.032] |
| krcp | B1 averaged | -0.009 [-0.013–-0.006] | -0.059 [-0.061–-0.057] | -0.041 [-0.046–-0.036] | -0.008 [-0.010–-0.006] |
| krcp | B2 sites (mean of 3) | 0.054 [0.048–0.059] | 0.011 [0.007–0.016] | 0.008 [0.003–0.013] | 0.033 [0.029–0.036] |
| krcp | B2 averaged | -0.013 [-0.017–-0.010] | -0.076 [-0.081–-0.070] | -0.043 [-0.049–-0.038] | -0.009 [-0.010–-0.007] |
| leaky | A′ (size control) | 0.003 [-0.002–0.007] | -0.021 [-0.023–-0.019] | -0.140 [-0.177–-0.103] | 0.005 [0.000–0.009] |
| leaky | B1 sites (mean of 3) | 0.002 [0.001–0.003] | -0.021 [-0.022–-0.020] | -0.130 [-0.142–-0.118] | 0.004 [0.002–0.006] |
| leaky | B1 averaged | -0.193 [-0.196–-0.191] | -0.201 [-0.204–-0.199] | -0.522 [-0.531–-0.514] | -0.130 [-0.130–-0.129] |
| leaky | B2 sites (mean of 3) | 0.006 [0.003–0.009] | -0.023 [-0.025–-0.021] | -0.177 [-0.198–-0.155] | 0.006 [0.004–0.008] |
| leaky | B2 averaged | -0.195 [-0.198–-0.191] | -0.208 [-0.212–-0.205] | -0.525 [-0.539–-0.510] | -0.129 [-0.130–-0.128] |
| regularized | A′ (size control) | 0.012 [0.007–0.017] | -0.001 [-0.005–0.004] | 0.009 [0.006–0.013] | 0.008 [0.004–0.012] |
| regularized | B1 sites (mean of 3) | 0.011 [0.007–0.014] | -0.002 [-0.005–0.001] | 0.010 [0.006–0.014] | 0.008 [0.006–0.009] |
| regularized | B1 averaged | 0.000 [-0.003–0.004] | -0.024 [-0.028–-0.021] | -0.001 [-0.005–0.003] | -0.002 [-0.004–-0.000] |
| regularized | B2 sites (mean of 3) | 0.012 [0.006–0.019] | -0.003 [-0.007–-0.000] | 0.007 [0.003–0.010] | 0.009 [0.005–0.012] |
| regularized | B2 averaged | 0.001 [-0.003–0.004] | -0.034 [-0.038–-0.030] | -0.002 [-0.006–0.002] | -0.002 [-0.004–-0.000] |

## H2 — distributed vs central leakage (shadow-model AUC, site mean − A)

| variant | B1 sites − A | A′ − A (size only) | B2 sites − A |
|---|---|---|---|
| krcp | 0.049 [0.045–0.053] | 0.051 [0.046–0.055] | 0.054 [0.048–0.059] |
| leaky | 0.002 [0.001–0.003] | 0.003 [-0.002–0.007] | 0.006 [0.003–0.009] |
| regularized | 0.011 [0.007–0.014] | 0.012 [0.007–0.017] | 0.012 [0.006–0.019] |

## Utility on the common validation set

| variant | target | AUROC | scaled Brier | cal. intercept | cal. slope |
|---|---|---|---|---|---|
| krcp | A_0 | 0.897 [0.897–0.897] | 0.442 [0.442–0.443] | -0.43 [-0.43–-0.43] | 1.00 [0.99–1.00] |
| krcp | Aprime_0 | 0.892 [0.891–0.893] | 0.433 [0.431–0.436] | -0.37 [-0.39–-0.36] | 0.89 [0.88–0.91] |
| krcp | B1_0 | 0.892 [0.892–0.893] | 0.434 [0.432–0.436] | -0.39 [-0.41–-0.37] | 0.89 [0.88–0.90] |
| krcp | B1_1 | 0.891 [0.890–0.892] | 0.431 [0.429–0.433] | -0.38 [-0.40–-0.36] | 0.89 [0.87–0.91] |
| krcp | B1_2 | 0.892 [0.891–0.893] | 0.434 [0.432–0.436] | -0.38 [-0.40–-0.36] | 0.89 [0.88–0.91] |
| krcp | B1_comb | 0.897 [0.897–0.897] | 0.447 [0.447–0.448] | -0.37 [-0.38–-0.37] | 0.98 [0.97–0.98] |
| krcp | B2_0 | 0.893 [0.893–0.894] | 0.437 [0.434–0.439] | -0.39 [-0.42–-0.36] | 0.93 [0.91–0.94] |
| krcp | B2_1 | 0.892 [0.891–0.893] | 0.429 [0.424–0.435] | -0.41 [-0.47–-0.35] | 0.88 [0.86–0.89] |
| krcp | B2_2 | 0.889 [0.888–0.890] | 0.426 [0.423–0.429] | -0.35 [-0.41–-0.30] | 0.84 [0.82–0.85] |
| krcp | B2_comb | 0.897 [0.897–0.897] | 0.447 [0.446–0.448] | -0.37 [-0.38–-0.36] | 0.97 [0.96–0.98] |
| leaky | A_0 | 0.886 [0.886–0.887] | 0.353 [0.352–0.353] | -0.12 [-0.13–-0.12] | 0.48 [0.48–0.48] |
| leaky | Aprime_0 | 0.885 [0.884–0.886] | 0.354 [0.349–0.358] | -0.04 [-0.10–0.01] | 0.48 [0.47–0.48] |
| leaky | B1_0 | 0.886 [0.885–0.887] | 0.357 [0.352–0.361] | -0.12 [-0.18–-0.05] | 0.48 [0.47–0.48] |
| leaky | B1_1 | 0.885 [0.884–0.886] | 0.353 [0.349–0.357] | -0.10 [-0.17–-0.03] | 0.48 [0.47–0.48] |
| leaky | B1_2 | 0.885 [0.885–0.886] | 0.354 [0.350–0.358] | -0.11 [-0.18–-0.05] | 0.48 [0.47–0.48] |
| leaky | B1_comb | 0.893 [0.892–0.893] | 0.416 [0.414–0.418] | -0.09 [-0.10–-0.08] | 0.58 [0.58–0.58] |
| leaky | B2_0 | 0.886 [0.885–0.887] | 0.354 [0.349–0.359] | -0.12 [-0.16–-0.08] | 0.48 [0.47–0.48] |
| leaky | B2_1 | 0.885 [0.884–0.886] | 0.356 [0.352–0.361] | -0.13 [-0.22–-0.03] | 0.49 [0.48–0.49] |
| leaky | B2_2 | 0.884 [0.883–0.886] | 0.357 [0.353–0.362] | -0.06 [-0.14–0.02] | 0.48 [0.48–0.49] |
| leaky | B2_comb | 0.893 [0.892–0.893] | 0.417 [0.416–0.418] | -0.09 [-0.11–-0.07] | 0.59 [0.59–0.59] |
| regularized | A_0 | 0.899 [0.899–0.899] | 0.442 [0.442–0.443] | -0.46 [-0.46–-0.46] | 1.09 [1.08–1.09] |
| regularized | Aprime_0 | 0.897 [0.896–0.897] | 0.440 [0.438–0.442] | -0.44 [-0.46–-0.43] | 1.07 [1.05–1.09] |
| regularized | B1_0 | 0.897 [0.897–0.897] | 0.440 [0.438–0.442] | -0.45 [-0.47–-0.44] | 1.05 [1.04–1.06] |
| regularized | B1_1 | 0.896 [0.896–0.897] | 0.438 [0.436–0.439] | -0.45 [-0.46–-0.43] | 1.07 [1.05–1.09] |
| regularized | B1_2 | 0.897 [0.896–0.897] | 0.440 [0.438–0.442] | -0.44 [-0.45–-0.43] | 1.07 [1.05–1.08] |
| regularized | B1_comb | 0.898 [0.898–0.898] | 0.443 [0.443–0.444] | -0.44 [-0.45–-0.44] | 1.09 [1.09–1.10] |
| regularized | B2_0 | 0.897 [0.897–0.898] | 0.441 [0.438–0.444] | -0.44 [-0.47–-0.41] | 1.07 [1.06–1.07] |
| regularized | B2_1 | 0.897 [0.896–0.897] | 0.434 [0.428–0.441] | -0.49 [-0.55–-0.42] | 1.06 [1.05–1.07] |
| regularized | B2_2 | 0.896 [0.895–0.896] | 0.439 [0.435–0.443] | -0.42 [-0.47–-0.37] | 1.06 [1.04–1.08] |
| regularized | B2_comb | 0.898 [0.898–0.898] | 0.443 [0.442–0.444] | -0.45 [-0.46–-0.43] | 1.10 [1.09–1.10] |

## H3 — combined model vs central (ΔAUROC, non-inferiority margin −0.02)

| variant | target | ΔAUROC | non-inferior |
|---|---|---|---|
| krcp | B1_comb | 0.000 [-0.000–0.000] | yes |
| krcp | B2_comb | -0.000 [-0.000–0.000] | yes |
| leaky | B1_comb | 0.006 [0.006–0.007] | yes |
| leaky | B2_comb | 0.006 [0.006–0.007] | yes |
| regularized | B1_comb | -0.000 [-0.000–-0.000] | yes |
| regularized | B2_comb | -0.000 [-0.000–-0.000] | yes |

## Subgroup LiRA AUC (krcp, A_0; groups ≥ 100 in the evaluation sample)

| subgroup | level | LiRA AUC | shadow AUC |
|---|---|---|---|
| sg_age75 | <75 | 0.724 [0.721–0.726] | 0.533 [0.530–0.536] |
| sg_age75 | >=75 | 0.744 [0.742–0.747] | 0.530 [0.527–0.534] |
| sg_esrd | 0 | 0.728 [0.726–0.729] | 0.534 [0.531–0.537] |
| sg_esrd | 1 | 0.787 [0.783–0.791] | 0.511 [0.500–0.521] |
| sg_sex | 0 | 0.735 [0.733–0.737] | 0.532 [0.530–0.533] |
| sg_sex | 1 | 0.729 [0.726–0.733] | 0.532 [0.527–0.538] |

## Gate 1 — code-free formats (XGB JSON, LGBM text, CatBoost CBM, RF tree JSON; no pickle on load)

| variant | target | max abs Δp | label agreement | size (kB) |
|---|---|---|---|---|
| krcp | A_0 | 3.3e-16 | 1.0000 | 10,923 |
| krcp | B1_0 | 2.2e-16 | 1.0000 | 9,015 |
| leaky | A_0 | 0.0e+00 | 1.0000 | 207,860 |
| leaky | B1_0 | 0.0e+00 | 1.0000 | 82,337 |
| regularized | A_0 | 8.9e-16 | 1.0000 | 2,725 |
| regularized | B1_0 | 3.3e-16 | 1.0000 | 2,078 |

Leaf audit — share of leaves with < 11 training people:

| variant | target | xgb | lgb | cat | rf |
|---|---|---|---|---|---|
| krcp | A_0 | 18.1% | 4.4% | 34.0% | 46.3% |
| krcp | B1_0 | 20.7% | 5.8% | 40.6% | 57.2% |
| leaky | A_0 | 77.2% | 44.0% | 59.7% | 91.8% |
| leaky | B1_0 | 81.4% | 48.6% | 70.1% | 91.7% |
| regularized | A_0 | 0.0% | 0.9% | 14.4% | 0.0% |
| regularized | B1_0 | 0.0% | 0.6% | 22.1% | 0.0% |

## Gate 3 — escrow re-execution

| variant | target | signature | data hash | versions | abs ΔAUROC | max abs Δp | pass |
|---|---|---|---|---|---|---|---|
| krcp | A_0 | True | True | True | 0.0e+00 | 0.0e+00 | True |
| leaky | A_0 | True | True | True | 0.0e+00 | 0.0e+00 | True |
| regularized | A_0 | True | True | True | 0.0e+00 | 0.0e+00 | True |
