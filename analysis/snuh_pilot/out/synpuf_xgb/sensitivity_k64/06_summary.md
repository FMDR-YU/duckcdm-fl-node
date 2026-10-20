# Pilot summary — synpuf

seeds: [42, 43, 44, 45, 46, 47, 48, 49, 50, 51] · values = mean [95% CI across seeds]

membership-inference audit: LiRA / RMIA with 64 reference models per target, shadow-model attack with 16 shadows

## Pre-specified decision rules (docs/ANALYSIS_PLAN_v1.md §3), evaluated by code

| hypothesis | role | variant / target | verdict | evidence |
|---|---|---|---|---|
| H1 | secondary | xgb_leaky vs xgb_regularized | **supported** | shadow AUC xgb_leaky 0.772 > 0.55: yes; xgb_regularized 0.505 <= 0.55: yes; AUROC xgb_regularized 0.898 >= xgb_leaky 0.876: yes |
| H2 | primary | xgb_krcp B1 (size) | **supported** | gap B1 0.070 [0.066–0.073] lower bound > 0: yes; size share (A′−A)/(B1 gap) 1.05 >= 0.5: yes |
| H2 | secondary | xgb_krcp B2 (unequal sites) | **supported** | gap B2 0.074 [0.070–0.077] lower bound > 0: yes; B2 gap > B1 gap: yes |
| H2 | secondary | xgb_leaky B1 (size) | **supported** | gap B1 0.008 [0.007–0.009] lower bound > 0: yes; size share (A′−A)/(B1 gap) 0.94 >= 0.5: yes |
| H2 | secondary | xgb_leaky B2 (unequal sites) | **supported** | gap B2 0.008 [0.006–0.010] lower bound > 0: yes; B2 gap > B1 gap: yes |
| H2 | secondary | xgb_regularized B1 (size) | **supported** | gap B1 0.014 [0.012–0.016] lower bound > 0: yes; size share (A′−A)/(B1 gap) 1.03 >= 0.5: yes |
| H2 | secondary | xgb_regularized B2 (unequal sites) | **supported** | gap B2 0.016 [0.013–0.019] lower bound > 0: yes; B2 gap > B1 gap: yes |
| H3 | secondary | xgb_krcp B1_comb | **supported** | ΔAUROC 0.002 [0.001–0.002] lower bound > −0.02: yes |
| H3 | secondary | xgb_krcp B2_comb | **supported** | ΔAUROC 0.001 [0.001–0.002] lower bound > −0.02: yes |
| H3 | secondary | xgb_leaky B1_comb | **supported** | ΔAUROC 0.005 [0.005–0.006] lower bound > −0.02: yes |
| H3 | secondary | xgb_leaky B2_comb | **supported** | ΔAUROC 0.005 [0.005–0.006] lower bound > −0.02: yes |
| H3 | secondary | xgb_regularized B1_comb | **supported** | ΔAUROC -0.000 [-0.000–0.000] lower bound > −0.02: yes |
| H3 | secondary | xgb_regularized B2_comb | **supported** | ΔAUROC -0.000 [-0.001–0.000] lower bound > −0.02: yes |
| H4 | secondary | xgb_krcp | **supported** | Gate 1 max abs Δp 0.0e+00 < 1e-6: yes; Gate 3 signature and data hash match: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |
| H4 | secondary | xgb_leaky | **supported** | Gate 1 max abs Δp 0.0e+00 < 1e-6: yes; Gate 3 signature and data hash match: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |
| H4 | secondary | xgb_regularized | **supported** | Gate 1 max abs Δp 0.0e+00 < 1e-6: yes; Gate 3 signature and data hash match: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |
| H4 | secondary | federated re-execution | **supported** | 3 job(s) run again in a fresh workspace: max abs Δp 0.0e+00 < 1e-6: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |
| H5 | primary | xgb_krcp F_B1 | **supported** | ΔAUROC(F−A) -0.000 [-0.000–0.000] lower bound > −0.02: yes; shadow AUC F 0.556 <= A 0.557 + 0.01: yes; (sites mean − F) 0.071 [0.068–0.074] lower bound > 0: yes |
| H5 | secondary | xgb_krcp F_B2 | **supported** | ΔAUROC(F−A) -0.000 [-0.001–0.001] lower bound > −0.02: yes; shadow AUC F 0.556 <= A 0.557 + 0.01: yes; (sites mean − F) 0.076 [0.073–0.078] lower bound > 0: yes |
| H5 | secondary | xgb_leaky F_B1 | **not evaluable** | ΔAUROC(F−A) -0.004 lower bound > −0.02: n/a; shadow AUC F 0.775 <= A 0.774 + 0.01: yes; (sites mean − F) 0.009 lower bound > 0: n/a |
| H5 | secondary | xgb_regularized F_B1 | **supported** | ΔAUROC(F−A) 0.000 [-0.000–0.000] lower bound > −0.02: yes; shadow AUC F 0.504 <= A 0.505 + 0.01: yes; (sites mean − F) 0.015 [0.011–0.018] lower bound > 0: yes |
| H5 | secondary | xgb_regularized F_B2 | **supported** | ΔAUROC(F−A) 0.000 [-0.000–0.000] lower bound > −0.02: yes; shadow AUC F 0.505 <= A 0.505 + 0.01: yes; (sites mean − F) 0.016 [0.013–0.019] lower bound > 0: yes |
| H6 | secondary | xgb_krcp | **supported** | Spearman ρ (size, seed-mean AUC) -1.00 < 0: yes; slope per log10(n) -0.155 [-0.164–-0.146] upper bound < 0: yes |
| H6 | secondary | xgb_regularized | **supported** | Spearman ρ (size, seed-mean AUC) -1.00 < 0: yes; slope per log10(n) -0.046 [-0.053–-0.039] upper bound < 0: yes |

Primary verdicts: H5 and the B1 part of H2 for the published configuration (xgb_krcp) with equal sites (B1). Every other row is secondary. Each hypothesis is judged on its own; no multiplicity correction. Intervals are t-based across seeds (utility differences also have paired bootstrap intervals in 01_utility_long.csv). "not evaluable" means an input is missing or has fewer than two seeds.

## Gate 2 — membership inference (AUC; decision on shadow-model attack, threshold 0.55)

| variant | target | n members | shadow AUC | loss AUC | LiRA AUC | LiRA TPR@1%FPR | decision |
|---|---|---|---|---|---|---|---|
| xgb_krcp | A_0 | 19,746 | 0.557 [0.555–0.560] | 0.535 [0.534–0.536] | 0.728 [0.726–0.730] | 0.108 [0.104–0.112] | BLOCK |
| xgb_krcp | Aprime_0 | 6,582 | 0.630 [0.628–0.633] | 0.574 [0.570–0.579] | 0.750 [0.746–0.753] | 0.139 [0.135–0.142] | BLOCK |
| xgb_krcp | B1_0 | 6,582 | 0.627 [0.623–0.630] | 0.574 [0.569–0.578] | 0.749 [0.746–0.752] | 0.139 [0.132–0.146] | BLOCK |
| xgb_krcp | B1_1 | 6,582 | 0.626 [0.620–0.632] | 0.572 [0.568–0.576] | 0.748 [0.744–0.752] | 0.142 [0.136–0.148] | BLOCK |
| xgb_krcp | B1_2 | 6,582 | 0.629 [0.625–0.633] | 0.574 [0.571–0.577] | 0.749 [0.748–0.751] | 0.139 [0.133–0.145] | BLOCK |
| xgb_krcp | B1_comb | 19,746 | 0.532 [0.530–0.533] | 0.520 [0.518–0.521] | 0.661 [0.659–0.664] | 0.076 [0.071–0.081] | PASS |
| xgb_krcp | F_B1 | 19,746 | 0.556 [0.554–0.558] | 0.535 [0.533–0.536] | 0.731 [0.729–0.732] | 0.119 [0.113–0.125] | BLOCK |
| xgb_krcp | B2_0 | 9,873 | 0.599 [0.592–0.605] | 0.555 [0.548–0.561] | 0.734 [0.730–0.737] | 0.126 [0.122–0.131] | BLOCK |
| xgb_krcp | B2_1 | 5,924 | 0.627 [0.619–0.636] | 0.573 [0.565–0.582] | 0.742 [0.734–0.749] | 0.125 [0.113–0.137] | BLOCK |
| xgb_krcp | B2_2 | 3,949 | 0.667 [0.659–0.675] | 0.591 [0.584–0.597] | 0.759 [0.750–0.767] | 0.147 [0.138–0.156] | BLOCK |
| xgb_krcp | B2_comb | 19,746 | 0.531 [0.528–0.534] | 0.519 [0.518–0.520] | 0.644 [0.640–0.648] | 0.074 [0.071–0.077] | PASS |
| xgb_krcp | F_B2 | 19,746 | 0.556 [0.553–0.558] | 0.534 [0.533–0.535] | 0.730 [0.728–0.731] | 0.117 [0.112–0.123] | BLOCK |
| xgb_leaky | A_0 | 19,746 | 0.772 [0.771–0.773] | 0.726 [0.725–0.727] | 0.920 [0.920–0.921] | 0.466 [0.464–0.469] | BLOCK |
| xgb_leaky | Aprime_0 | 6,582 | 0.780 [0.776–0.784] | 0.736 [0.731–0.742] | 0.908 [0.906–0.910] | 0.333 [0.324–0.342] | BLOCK |
| xgb_leaky | B1_0 | 6,582 | 0.781 [0.778–0.783] | 0.736 [0.732–0.741] | 0.910 [0.909–0.912] | 0.336 [0.330–0.343] | BLOCK |
| xgb_leaky | B1_1 | 6,582 | 0.780 [0.778–0.783] | 0.736 [0.732–0.741] | 0.910 [0.908–0.913] | 0.339 [0.332–0.345] | BLOCK |
| xgb_leaky | B1_2 | 6,582 | 0.780 [0.777–0.783] | 0.736 [0.731–0.741] | 0.909 [0.907–0.911] | 0.330 [0.323–0.337] | BLOCK |
| xgb_leaky | B1_comb | 19,746 | 0.619 [0.617–0.622] | 0.535 [0.533–0.536] | 0.643 [0.641–0.646] | 0.072 [0.069–0.076] | BLOCK |
| xgb_leaky | F_B1 | 19,746 | 0.775 | 0.725 | 0.920 | 0.461 | BLOCK |
| xgb_leaky | B2_0 | 9,873 | 0.778 [0.774–0.781] | 0.733 [0.728–0.739] | 0.912 [0.910–0.913] | 0.365 [0.358–0.372] | BLOCK |
| xgb_leaky | B2_1 | 5,924 | 0.779 [0.773–0.785] | 0.735 [0.729–0.742] | 0.904 [0.899–0.908] | 0.310 [0.299–0.321] | BLOCK |
| xgb_leaky | B2_2 | 3,949 | 0.785 [0.782–0.789] | 0.735 [0.732–0.738] | 0.902 [0.899–0.906] | 0.286 [0.279–0.294] | BLOCK |
| xgb_leaky | B2_comb | 19,746 | 0.617 [0.614–0.620] | 0.535 [0.534–0.536] | 0.648 [0.645–0.651] | 0.073 [0.070–0.076] | BLOCK |
| xgb_regularized | A_0 | 19,746 | 0.505 [0.504–0.506] | 0.502 [0.501–0.504] | 0.578 [0.576–0.581] | 0.026 [0.023–0.029] | PASS |
| xgb_regularized | Aprime_0 | 6,582 | 0.519 [0.517–0.522] | 0.513 [0.509–0.517] | 0.585 [0.582–0.588] | 0.033 [0.031–0.036] | PASS |
| xgb_regularized | B1_0 | 6,582 | 0.520 [0.517–0.523] | 0.514 [0.510–0.518] | 0.584 [0.581–0.588] | 0.034 [0.031–0.038] | PASS |
| xgb_regularized | B1_1 | 6,582 | 0.517 [0.513–0.520] | 0.510 [0.506–0.514] | 0.582 [0.577–0.586] | 0.033 [0.029–0.037] | PASS |
| xgb_regularized | B1_2 | 6,582 | 0.521 [0.518–0.523] | 0.513 [0.510–0.516] | 0.585 [0.582–0.588] | 0.033 [0.030–0.035] | PASS |
| xgb_regularized | B1_comb | 19,746 | 0.505 [0.502–0.509] | 0.500 [0.499–0.501] | 0.549 [0.546–0.553] | 0.020 [0.019–0.021] | PASS |
| xgb_regularized | F_B1 | 19,746 | 0.504 [0.502–0.507] | 0.502 [0.501–0.503] | 0.578 [0.576–0.580] | 0.026 [0.023–0.030] | PASS |
| xgb_regularized | B2_0 | 9,873 | 0.511 [0.506–0.517] | 0.505 [0.499–0.510] | 0.579 [0.575–0.582] | 0.030 [0.025–0.036] | PASS |
| xgb_regularized | B2_1 | 5,924 | 0.520 [0.512–0.528] | 0.515 [0.507–0.524] | 0.580 [0.575–0.584] | 0.030 [0.026–0.034] | PASS |
| xgb_regularized | B2_2 | 3,949 | 0.532 [0.529–0.535] | 0.519 [0.513–0.526] | 0.590 [0.585–0.595] | 0.032 [0.029–0.035] | PASS |
| xgb_regularized | B2_comb | 19,746 | 0.501 [0.498–0.504] | 0.500 [0.499–0.501] | 0.540 [0.537–0.543] | 0.016 [0.014–0.019] | PASS |
| xgb_regularized | F_B2 | 19,746 | 0.505 [0.503–0.508] | 0.502 [0.501–0.502] | 0.578 [0.576–0.580] | 0.026 [0.023–0.028] | PASS |

Threshold sweep (shadow-model mean AUC):

| variant | target | ≤0.50 | ≤0.52 | ≤0.55 | ≤0.58 | ≤0.60 |
|---|---|---|---|---|---|---|
| xgb_krcp | A_0 | BLOCK | BLOCK | BLOCK | PASS | PASS |
| xgb_krcp | Aprime_0 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_krcp | B1_comb | BLOCK | BLOCK | PASS | PASS | PASS |
| xgb_krcp | B2_comb | BLOCK | BLOCK | PASS | PASS | PASS |
| xgb_krcp | F_B1 | BLOCK | BLOCK | BLOCK | PASS | PASS |
| xgb_krcp | F_B2 | BLOCK | BLOCK | BLOCK | PASS | PASS |
| xgb_leaky | A_0 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_leaky | Aprime_0 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_leaky | B1_comb | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_leaky | B2_comb | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_leaky | F_B1 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_regularized | A_0 | BLOCK | PASS | PASS | PASS | PASS |
| xgb_regularized | Aprime_0 | BLOCK | PASS | PASS | PASS | PASS |
| xgb_regularized | B1_comb | BLOCK | PASS | PASS | PASS | PASS |
| xgb_regularized | B2_comb | BLOCK | PASS | PASS | PASS | PASS |
| xgb_regularized | F_B1 | BLOCK | PASS | PASS | PASS | PASS |
| xgb_regularized | F_B2 | BLOCK | PASS | PASS | PASS | PASS |

## Exposure relative to the central model, by attack (route − A; mean [95% CI across seeds]; descriptive)

| variant | route | shadow AUC | LiRA AUC | LiRA TPR@1%FPR | loss AUC |
|---|---|---|---|---|---|
| xgb_krcp | A′ (size control) | 0.073 [0.069–0.077] | 0.022 [0.019–0.025] | 0.031 [0.026–0.035] | 0.039 [0.035–0.044] |
| xgb_krcp | B1 sites (mean of 3) | 0.070 [0.066–0.073] | 0.021 [0.019–0.023] | 0.032 [0.027–0.037] | 0.038 [0.036–0.040] |
| xgb_krcp | B1 averaged | -0.026 [-0.029–-0.023] | -0.067 [-0.069–-0.064] | -0.032 [-0.039–-0.025] | -0.015 [-0.017–-0.013] |
| xgb_krcp | B1 federated | -0.001 [-0.005–0.002] | 0.003 [0.000–0.005] | 0.011 [0.004–0.018] | -0.000 [-0.002–0.001] |
| xgb_krcp | B2 sites (mean of 3) | 0.074 [0.070–0.077] | 0.017 [0.012–0.021] | 0.025 [0.018–0.031] | 0.038 [0.033–0.043] |
| xgb_krcp | B2 averaged | -0.026 [-0.030–-0.023] | -0.084 [-0.090–-0.078] | -0.034 [-0.040–-0.029] | -0.016 [-0.018–-0.014] |
| xgb_krcp | B2 federated | -0.002 [-0.006–0.002] | 0.002 [-0.001–0.005] | 0.009 [0.003–0.016] | -0.001 [-0.002–0.001] |
| xgb_leaky | A′ (size control) | 0.007 [0.003–0.011] | -0.012 [-0.015–-0.010] | -0.133 [-0.144–-0.123] | 0.010 [0.005–0.016] |
| xgb_leaky | B1 sites (mean of 3) | 0.008 [0.007–0.009] | -0.010 [-0.012–-0.009] | -0.132 [-0.134–-0.129] | 0.010 [0.008–0.013] |
| xgb_leaky | B1 averaged | -0.153 [-0.156–-0.150] | -0.277 [-0.280–-0.274] | -0.394 [-0.400–-0.389] | -0.191 [-0.193–-0.190] |
| xgb_leaky | B1 federated | 0.001 | 0.000 | -0.001 | -0.002 |
| xgb_leaky | B2 sites (mean of 3) | 0.008 [0.006–0.010] | -0.014 [-0.016–-0.012] | -0.146 [-0.152–-0.140] | 0.009 [0.006–0.011] |
| xgb_leaky | B2 averaged | -0.155 [-0.159–-0.152] | -0.272 [-0.275–-0.269] | -0.394 [-0.396–-0.391] | -0.191 [-0.192–-0.190] |
| xgb_regularized | A′ (size control) | 0.014 [0.011–0.017] | 0.006 [0.002–0.011] | 0.008 [0.003–0.012] | 0.011 [0.006–0.015] |
| xgb_regularized | B1 sites (mean of 3) | 0.014 [0.012–0.016] | 0.005 [0.002–0.008] | 0.008 [0.005–0.011] | 0.010 [0.009–0.012] |
| xgb_regularized | B1 averaged | 0.000 [-0.002–0.003] | -0.029 [-0.033–-0.025] | -0.006 [-0.010–-0.002] | -0.003 [-0.005–-0.001] |
| xgb_regularized | B1 federated | -0.001 [-0.003–0.002] | -0.000 [-0.004–0.003] | 0.001 [-0.005–0.006] | -0.001 [-0.002–0.001] |
| xgb_regularized | B2 sites (mean of 3) | 0.016 [0.013–0.019] | 0.005 [0.001–0.009] | 0.005 [0.002–0.009] | 0.011 [0.007–0.014] |
| xgb_regularized | B2 averaged | -0.004 [-0.007–-0.001] | -0.038 [-0.042–-0.034] | -0.009 [-0.012–-0.006] | -0.003 [-0.004–-0.001] |
| xgb_regularized | B2 federated | 0.000 [-0.002–0.003] | -0.000 [-0.002–0.001] | 0.000 [-0.005–0.005] | -0.001 [-0.002–0.001] |

## H2 — distributed vs central leakage (shadow-model AUC, site mean − A)

| variant | B1 sites − A | A′ − A (size only) | B2 sites − A |
|---|---|---|---|
| xgb_krcp | 0.070 [0.066–0.073] | 0.073 [0.069–0.077] | 0.074 [0.070–0.077] |
| xgb_leaky | 0.008 [0.007–0.009] | 0.007 [0.003–0.011] | 0.008 [0.006–0.010] |
| xgb_regularized | 0.014 [0.012–0.016] | 0.014 [0.011–0.017] | 0.016 [0.013–0.019] |

## Utility on the common validation set

| variant | target | AUROC | scaled Brier | cal. intercept | cal. slope |
|---|---|---|---|---|---|
| xgb_krcp | A_0 | 0.893 [0.893–0.893] | 0.434 [0.433–0.434] | -0.42 [-0.42–-0.42] | 0.84 [0.83–0.84] |
| xgb_krcp | Aprime_0 | 0.885 [0.883–0.886] | 0.408 [0.404–0.412] | -0.36 [-0.38–-0.34] | 0.68 [0.66–0.69] |
| xgb_krcp | B1_0 | 0.886 [0.885–0.886] | 0.409 [0.406–0.411] | -0.38 [-0.42–-0.35] | 0.68 [0.67–0.68] |
| xgb_krcp | B1_1 | 0.884 [0.883–0.885] | 0.404 [0.401–0.407] | -0.38 [-0.41–-0.35] | 0.68 [0.66–0.69] |
| xgb_krcp | B1_2 | 0.885 [0.884–0.887] | 0.408 [0.404–0.412] | -0.38 [-0.40–-0.35] | 0.68 [0.66–0.69] |
| xgb_krcp | B1_comb | 0.895 [0.894–0.895] | 0.442 [0.441–0.443] | -0.35 [-0.35–-0.35] | 0.82 [0.82–0.82] |
| xgb_krcp | F_B1 | 0.893 [0.893–0.893] | 0.434 [0.433–0.434] | -0.42 [-0.42–-0.42] | 0.83 [0.83–0.84] |
| xgb_krcp | B2_0 | 0.887 [0.886–0.888] | 0.418 [0.414–0.421] | -0.38 [-0.41–-0.35] | 0.73 [0.72–0.74] |
| xgb_krcp | B2_1 | 0.885 [0.883–0.886] | 0.401 [0.396–0.407] | -0.41 [-0.48–-0.34] | 0.65 [0.63–0.67] |
| xgb_krcp | B2_2 | 0.881 [0.880–0.882] | 0.387 [0.384–0.391] | -0.36 [-0.43–-0.29] | 0.60 [0.59–0.62] |
| xgb_krcp | B2_comb | 0.894 [0.894–0.895] | 0.441 [0.439–0.442] | -0.35 [-0.37–-0.34] | 0.81 [0.80–0.82] |
| xgb_krcp | F_B2 | 0.893 [0.892–0.894] | 0.434 [0.432–0.435] | -0.42 [-0.42–-0.42] | 0.84 [0.83–0.84] |
| xgb_leaky | A_0 | 0.876 [0.876–0.876] | 0.193 [0.193–0.193] | -0.76 [-0.76–-0.76] | 0.17 [0.17–0.17] |
| xgb_leaky | Aprime_0 | 0.874 [0.872–0.875] | 0.192 [0.183–0.202] | -0.42 [-0.63–-0.21] | 0.17 [0.17–0.17] |
| xgb_leaky | B1_0 | 0.874 [0.873–0.875] | 0.198 [0.191–0.205] | -0.78 [-1.03–-0.54] | 0.17 [0.16–0.17] |
| xgb_leaky | B1_1 | 0.873 [0.872–0.874] | 0.188 [0.179–0.197] | -0.68 [-0.93–-0.43] | 0.17 [0.17–0.17] |
| xgb_leaky | B1_2 | 0.874 [0.872–0.875] | 0.193 [0.185–0.202] | -0.65 [-0.89–-0.42] | 0.17 [0.17–0.17] |
| xgb_leaky | B1_comb | 0.885 [0.885–0.886] | 0.341 [0.338–0.344] | -0.30 [-0.32–-0.27] | 0.23 [0.23–0.23] |
| xgb_leaky | F_B1 | 0.876 | 0.195 | -0.77 | 0.17 |
| xgb_leaky | B2_0 | 0.875 [0.874–0.876] | 0.201 [0.195–0.207] | -0.75 [-0.87–-0.62] | 0.17 [0.17–0.17] |
| xgb_leaky | B2_1 | 0.873 [0.871–0.875] | 0.189 [0.182–0.197] | -0.74 [-1.11–-0.37] | 0.17 [0.16–0.17] |
| xgb_leaky | B2_2 | 0.871 [0.870–0.873] | 0.186 [0.178–0.194] | -0.53 [-0.85–-0.21] | 0.17 [0.16–0.17] |
| xgb_leaky | B2_comb | 0.886 [0.885–0.886] | 0.343 [0.341–0.346] | -0.28 [-0.32–-0.24] | 0.23 [0.23–0.23] |
| xgb_regularized | A_0 | 0.898 [0.898–0.898] | 0.442 [0.442–0.443] | -0.46 [-0.47–-0.46] | 0.99 [0.99–0.99] |
| xgb_regularized | Aprime_0 | 0.895 [0.894–0.895] | 0.436 [0.434–0.438] | -0.44 [-0.46–-0.43] | 0.95 [0.93–0.96] |
| xgb_regularized | B1_0 | 0.895 [0.894–0.895] | 0.436 [0.434–0.438] | -0.46 [-0.47–-0.44] | 0.94 [0.93–0.94] |
| xgb_regularized | B1_1 | 0.894 [0.894–0.895] | 0.434 [0.432–0.436] | -0.45 [-0.47–-0.44] | 0.95 [0.93–0.97] |
| xgb_regularized | B1_2 | 0.895 [0.894–0.895] | 0.436 [0.434–0.438] | -0.44 [-0.46–-0.43] | 0.94 [0.93–0.96] |
| xgb_regularized | B1_comb | 0.898 [0.898–0.898] | 0.444 [0.444–0.444] | -0.44 [-0.45–-0.44] | 1.00 [1.00–1.00] |
| xgb_regularized | F_B1 | 0.898 [0.898–0.898] | 0.443 [0.442–0.443] | -0.46 [-0.47–-0.46] | 0.99 [0.99–1.00] |
| xgb_regularized | B2_0 | 0.896 [0.895–0.896] | 0.438 [0.435–0.441] | -0.44 [-0.48–-0.41] | 0.96 [0.95–0.97] |
| xgb_regularized | B2_1 | 0.894 [0.894–0.895] | 0.429 [0.422–0.436] | -0.49 [-0.57–-0.41] | 0.93 [0.92–0.95] |
| xgb_regularized | B2_2 | 0.893 [0.892–0.894] | 0.433 [0.429–0.437] | -0.42 [-0.48–-0.37] | 0.93 [0.91–0.94] |
| xgb_regularized | B2_comb | 0.898 [0.898–0.898] | 0.444 [0.442–0.445] | -0.44 [-0.46–-0.42] | 1.00 [1.00–1.01] |
| xgb_regularized | F_B2 | 0.898 [0.898–0.898] | 0.442 [0.442–0.443] | -0.47 [-0.47–-0.46] | 0.99 [0.99–1.00] |

## H3 — combined model vs central (ΔAUROC, non-inferiority margin −0.02)

| variant | target | ΔAUROC | non-inferior |
|---|---|---|---|
| xgb_krcp | B1_comb | 0.002 [0.001–0.002] | yes |
| xgb_krcp | B2_comb | 0.001 [0.001–0.002] | yes |
| xgb_leaky | B1_comb | 0.005 [0.005–0.006] | yes |
| xgb_leaky | B2_comb | 0.005 [0.005–0.006] | yes |
| xgb_regularized | B1_comb | -0.000 [-0.000–0.000] | yes |
| xgb_regularized | B2_comb | -0.000 [-0.001–0.000] | yes |

## H5 — federated model (F) vs central model (A)

| variant | target | ΔAUROC (F − A) | non-inferior | shadow AUC F | shadow AUC A | shadow AUC sites (mean) | F ≤ A + 0.01 and F < sites (means; the pre-specified test is in the decision rules) |
|---|---|---|---|---|---|---|---|
| xgb_krcp | F_B1 | -0.000 [-0.000–0.000] | yes | 0.556 | 0.557 | 0.627 | yes |
| xgb_krcp | F_B2 | -0.000 [-0.001–0.001] | yes | 0.556 | 0.557 | 0.631 | yes |
| xgb_leaky | F_B1 | -0.004 | n/a | 0.775 | 0.772 | 0.780 | yes |
| xgb_regularized | F_B1 | 0.000 [-0.000–0.000] | yes | 0.504 | 0.505 | 0.519 | yes |
| xgb_regularized | F_B2 | 0.000 [-0.000–0.000] | yes | 0.505 | 0.505 | 0.521 | yes |

## H6 — exposure against training size (shadow-model AUC; one target per seed and size)

xgb_krcp: Spearman ρ (size, seed-mean AUC) = -1.00; slope per log10(n) = -0.155 [-0.164–-0.146]

| n train | 2,000 | 5,000 | 10,000 | 19,746 |
|---|---|---|---|---|
| shadow AUC | 0.709 [0.702–0.716] | 0.646 [0.641–0.651] | 0.599 [0.596–0.602] | 0.555 [0.552–0.557] |
| val AUROC | 0.877 [0.875–0.879] | 0.883 [0.882–0.885] | 0.888 [0.887–0.888] | 0.893 [0.893–0.893] |

xgb_regularized: Spearman ρ (size, seed-mean AUC) = -1.00; slope per log10(n) = -0.046 [-0.053–-0.039]

| n train | 2,000 | 5,000 | 10,000 | 19,746 |
|---|---|---|---|---|
| shadow AUC | 0.549 [0.541–0.557] | 0.525 [0.522–0.528] | 0.513 [0.509–0.517] | 0.503 [0.501–0.506] |
| val AUROC | 0.889 [0.888–0.890] | 0.894 [0.893–0.894] | 0.896 [0.896–0.897] | 0.898 [0.898–0.898] |


## Subgroup LiRA AUC (xgb_krcp, A_0; groups ≥ 100 in the evaluation sample)

| subgroup | level | LiRA AUC | shadow AUC |
|---|---|---|---|
| sg_age75 | <75 | 0.715 [0.712–0.718] | 0.558 [0.556–0.560] |
| sg_age75 | >=75 | 0.746 [0.742–0.750] | 0.557 [0.555–0.560] |
| sg_esrd | 0 | 0.726 [0.724–0.728] | 0.561 [0.559–0.563] |
| sg_esrd | 1 | 0.758 [0.750–0.765] | 0.517 [0.506–0.527] |
| sg_sex | 0 | 0.731 [0.729–0.732] | 0.558 [0.556–0.559] |
| sg_sex | 1 | 0.725 [0.721–0.728] | 0.557 [0.553–0.562] |

## Gate 1 — code-free formats (XGB JSON, LGBM text, CatBoost CBM, RF tree JSON; no pickle on load)

| variant | target | max abs Δp | label agreement | size (kB) |
|---|---|---|---|---|
| xgb_krcp | A_0 | 0.0e+00 | 1.0000 | 2,543 |
| xgb_krcp | B1_0 | 0.0e+00 | 1.0000 | 2,235 |
| xgb_krcp | F_B1 | 0.0e+00 | 1.0000 | 2,612 |
| xgb_krcp | F_B2 | 0.0e+00 | 1.0000 | 2,590 |
| xgb_leaky | A_0 | 0.0e+00 | 1.0000 | 61,937 |
| xgb_leaky | B1_0 | 0.0e+00 | 1.0000 | 21,629 |
| xgb_leaky | F_B1 | 0.0e+00 | 1.0000 | 61,947 |
| xgb_regularized | A_0 | 0.0e+00 | 1.0000 | 534 |
| xgb_regularized | B1_0 | 0.0e+00 | 1.0000 | 486 |
| xgb_regularized | F_B1 | 0.0e+00 | 1.0000 | 534 |
| xgb_regularized | F_B2 | 0.0e+00 | 1.0000 | 542 |

Leaf audit — share of leaves with < 11 training people:

| variant | target | xgb |
|---|---|---|
| xgb_krcp | A_0 | 18.1% |
| xgb_krcp | B1_0 | 20.7% |
| xgb_krcp | F_B1 | 17.6% |
| xgb_krcp | F_B2 | 17.9% |
| xgb_leaky | A_0 | 77.2% |
| xgb_leaky | B1_0 | 81.4% |
| xgb_leaky | F_B1 | 77.3% |
| xgb_regularized | A_0 | 0.0% |
| xgb_regularized | B1_0 | 0.0% |
| xgb_regularized | F_B1 | 0.0% |
| xgb_regularized | F_B2 | 0.0% |

## Gate 3 — escrow re-execution

| variant | target | signature | data hash | versions | abs ΔAUROC | max abs Δp | pass |
|---|---|---|---|---|---|---|---|
| xgb_krcp | A_0 | True | True | True | 0.0e+00 | 0.0e+00 | True |
| xgb_leaky | A_0 | True | True | True | 0.0e+00 | 0.0e+00 | True |
| xgb_regularized | A_0 | True | True | True | 0.0e+00 | 0.0e+00 | True |
