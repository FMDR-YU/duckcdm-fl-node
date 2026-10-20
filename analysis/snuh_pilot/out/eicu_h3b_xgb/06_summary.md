# Pilot summary — eicu

seeds: [42, 43, 44, 45, 46, 47, 48, 49, 50, 51] · values = mean [95% CI across seeds]

membership-inference audit: LiRA / RMIA with 64 reference models per target, shadow-model attack with 16 shadows

## Pre-specified decision rules (docs/ANALYSIS_PLAN_v1.md §3), evaluated by code

| hypothesis | role | variant / target | verdict | evidence |
|---|---|---|---|---|
| H1 | secondary | xgb_leaky vs xgb_regularized | **supported** | shadow AUC xgb_leaky 0.660 > 0.55: yes; xgb_regularized 0.536 <= 0.55: yes; AUROC xgb_regularized 0.901 >= xgb_leaky 0.858: yes |
| H2 | primary | xgb_krcp B1 (size) | **not supported** | gap B1 -0.002 [-0.005–0.001] lower bound > 0: no; size share (A′−A)/(B1 gap) nan >= 0.5: n/a |
| H2 | secondary | xgb_krcp B2 (unequal sites) | **not supported** | gap B2 -0.003 [-0.006–-0.000] lower bound > 0: no; B2 gap > B1 gap: no |
| H2 | secondary | xgb_leaky B1 (size) | **not supported** | gap B1 -0.010 [-0.013–-0.008] lower bound > 0: no; size share (A′−A)/(B1 gap) nan >= 0.5: n/a |
| H2 | secondary | xgb_leaky B2 (unequal sites) | **not supported** | gap B2 -0.009 [-0.010–-0.008] lower bound > 0: no; B2 gap > B1 gap: yes |
| H2 | secondary | xgb_regularized B1 (size) | **supported** | gap B1 0.007 [0.000–0.015] lower bound > 0: yes; size share (A′−A)/(B1 gap) 4.90 >= 0.5: yes |
| H2 | secondary | xgb_regularized B2 (unequal sites) | **supported** | gap B2 0.011 [0.004–0.018] lower bound > 0: yes; B2 gap > B1 gap: yes |
| H3 | secondary | xgb_krcp B1_comb | **supported** | ΔAUROC -0.001 [-0.002–0.000] lower bound > −0.02: yes |
| H3 | secondary | xgb_krcp B2_comb | **supported** | ΔAUROC -0.001 [-0.002–0.000] lower bound > −0.02: yes |
| H3 | secondary | xgb_leaky B1_comb | **not supported** | ΔAUROC -0.112 [-0.112–-0.112] lower bound > −0.02: no |
| H3 | secondary | xgb_leaky B2_comb | **not supported** | ΔAUROC -0.112 [-0.112–-0.112] lower bound > −0.02: no |
| H3 | secondary | xgb_regularized B1_comb | **supported** | ΔAUROC -0.004 [-0.005–-0.002] lower bound > −0.02: yes |
| H3 | secondary | xgb_regularized B2_comb | **supported** | ΔAUROC -0.004 [-0.005–-0.002] lower bound > −0.02: yes |
| H4 | secondary | xgb_krcp | **supported** | Gate 1 max abs Δp 0.0e+00 < 1e-6: yes; Gate 3 signature and data hash match: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |
| H4 | secondary | xgb_leaky | **supported** | Gate 1 max abs Δp 0.0e+00 < 1e-6: yes; Gate 3 signature and data hash match: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |
| H4 | secondary | xgb_regularized | **supported** | Gate 1 max abs Δp 0.0e+00 < 1e-6: yes; Gate 3 signature and data hash match: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |
| H4 | secondary | federated re-execution | **supported** | 2 job(s) run again in a fresh workspace: max abs Δp 0.0e+00 < 1e-6: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |
| H5 | primary | xgb_krcp F_B1 | **not supported** | ΔAUROC(F−A) -0.001 [-0.002–0.000] lower bound > −0.02: yes; shadow AUC F 0.619 <= A 0.618 + 0.01: yes; (sites mean − F) -0.003 [-0.006–0.001] lower bound > 0: no |
| H5 | secondary | xgb_regularized F_B1 | **supported** | ΔAUROC(F−A) -0.000 [-0.002–0.002] lower bound > −0.02: yes; shadow AUC F 0.535 <= A 0.536 + 0.01: yes; (sites mean − F) 0.009 [0.003–0.015] lower bound > 0: yes |
| H6 | secondary | xgb_krcp | **supported** | Spearman ρ (size, seed-mean AUC) -1.00 < 0: yes; slope per log10(n) -0.064 [-0.078–-0.051] upper bound < 0: yes |
| H6 | secondary | xgb_regularized | **supported** | Spearman ρ (size, seed-mean AUC) -1.00 < 0: yes; slope per log10(n) -0.087 [-0.100–-0.073] upper bound < 0: yes |

Primary verdicts: H5 and the B1 part of H2 for the published configuration (xgb_krcp) with equal sites (B1). Every other row is secondary. Each hypothesis is judged on its own; no multiplicity correction. Intervals are t-based across seeds (utility differences also have paired bootstrap intervals in 01_utility_long.csv). "not evaluable" means an input is missing or has fewer than two seeds.

## Gate 2 — membership inference (AUC; decision on shadow-model attack, threshold 0.55)

| variant | target | n members | shadow AUC | loss AUC | LiRA AUC | LiRA TPR@1%FPR | decision |
|---|---|---|---|---|---|---|---|
| xgb_krcp | A_0 | 6,408 | 0.618 [0.615–0.620] | 0.563 [0.559–0.567] | 0.729 [0.724–0.733] | 0.178 [0.170–0.186] | BLOCK |
| xgb_krcp | Aprime_0 | 2,136 | 0.644 [0.639–0.649] | 0.581 [0.574–0.588] | 0.717 [0.711–0.723] | 0.161 [0.154–0.169] | BLOCK |
| xgb_krcp | B1_0 | 2,982 | 0.638 [0.633–0.644] | 0.606 [0.604–0.609] | 0.692 [0.689–0.695] | 0.106 [0.103–0.108] | BLOCK |
| xgb_krcp | B1_1 | 1,932 | 0.593 [0.586–0.599] | 0.674 [0.669–0.679] | 0.785 [0.781–0.790] | 0.179 [0.173–0.185] | BLOCK |
| xgb_krcp | B1_2 | 1,494 | 0.616 [0.611–0.621] | 0.615 [0.609–0.621] | 0.744 [0.740–0.747] | 0.180 [0.170–0.190] | BLOCK |
| xgb_krcp | B1_comb | 6,408 | 0.547 [0.543–0.550] | 0.515 [0.513–0.518] | 0.587 [0.584–0.591] | 0.033 [0.030–0.036] | PASS |
| xgb_krcp | F_B1 | 6,408 | 0.619 [0.615–0.622] | 0.562 [0.559–0.565] | 0.727 [0.724–0.731] | 0.179 [0.170–0.187] | BLOCK |
| xgb_krcp | B2_0 | 2,982 | 0.635 [0.631–0.639] | 0.606 [0.604–0.609] | 0.705 [0.702–0.708] | 0.106 [0.102–0.110] | BLOCK |
| xgb_krcp | B2_1 | 1,932 | 0.594 [0.587–0.601] | 0.674 [0.669–0.679] | 0.780 [0.776–0.783] | 0.152 [0.140–0.163] | BLOCK |
| xgb_krcp | B2_2 | 1,494 | 0.615 [0.609–0.620] | 0.615 [0.609–0.621] | 0.735 [0.730–0.739] | 0.167 [0.161–0.172] | BLOCK |
| xgb_krcp | B2_comb | 6,408 | 0.545 [0.542–0.548] | 0.515 [0.513–0.518] | 0.595 [0.591–0.599] | 0.044 [0.041–0.047] | PASS |
| xgb_leaky | A_0 | 6,408 | 0.660 [0.659–0.661] | 0.665 [0.663–0.667] | 0.810 [0.807–0.812] | 0.239 [0.235–0.244] | BLOCK |
| xgb_leaky | Aprime_0 | 2,136 | 0.627 [0.615–0.639] | 0.616 [0.605–0.627] | 0.700 [0.685–0.715] | 0.096 [0.089–0.102] | BLOCK |
| xgb_leaky | B1_0 | 2,982 | 0.666 [0.663–0.669] | 0.674 [0.673–0.676] | 0.738 [0.736–0.740] | 0.084 [0.082–0.086] | BLOCK |
| xgb_leaky | B1_1 | 1,932 | 0.661 [0.657–0.664] | 0.684 [0.680–0.687] | 0.761 [0.758–0.764] | 0.115 [0.108–0.123] | BLOCK |
| xgb_leaky | B1_2 | 1,494 | 0.622 [0.617–0.626] | 0.609 [0.605–0.613] | 0.688 [0.684–0.693] | 0.090 [0.087–0.093] | BLOCK |
| xgb_leaky | B1_comb | 6,408 | 0.580 [0.578–0.582] | 0.536 [0.533–0.540] | 0.537 [0.534–0.541] | 0.009 [0.008–0.010] | BLOCK |
| xgb_leaky | B2_0 | 2,982 | 0.665 [0.662–0.667] | 0.674 [0.673–0.676] | 0.753 [0.750–0.755] | 0.090 [0.088–0.092] | BLOCK |
| xgb_leaky | B2_1 | 1,932 | 0.663 [0.659–0.667] | 0.684 [0.680–0.687] | 0.751 [0.748–0.753] | 0.103 [0.098–0.107] | BLOCK |
| xgb_leaky | B2_2 | 1,494 | 0.624 [0.620–0.628] | 0.609 [0.605–0.613] | 0.681 [0.676–0.686] | 0.088 [0.084–0.093] | BLOCK |
| xgb_leaky | B2_comb | 6,408 | 0.581 [0.578–0.583] | 0.536 [0.533–0.540] | 0.555 [0.550–0.559] | 0.013 [0.012–0.014] | BLOCK |
| xgb_regularized | A_0 | 6,408 | 0.536 [0.531–0.541] | 0.522 [0.519–0.526] | 0.626 [0.622–0.631] | 0.084 [0.080–0.088] | PASS |
| xgb_regularized | Aprime_0 | 2,136 | 0.572 [0.568–0.577] | 0.549 [0.542–0.556] | 0.641 [0.634–0.648] | 0.098 [0.092–0.103] | BLOCK |
| xgb_regularized | B1_0 | 2,982 | 0.572 [0.568–0.575] | 0.580 [0.575–0.585] | 0.619 [0.615–0.623] | 0.073 [0.072–0.074] | BLOCK |
| xgb_regularized | B1_1 | 1,932 | 0.523 [0.517–0.530] | 0.636 [0.628–0.643] | 0.697 [0.691–0.704] | 0.073 [0.068–0.078] | PASS |
| xgb_regularized | B1_2 | 1,494 | 0.536 [0.531–0.541] | 0.576 [0.572–0.581] | 0.663 [0.660–0.667] | 0.097 [0.088–0.106] | PASS |
| xgb_regularized | B1_comb | 6,408 | 0.514 [0.510–0.518] | 0.508 [0.506–0.510] | 0.558 [0.556–0.561] | 0.016 [0.015–0.018] | PASS |
| xgb_regularized | F_B1 | 6,408 | 0.535 [0.530–0.540] | 0.522 [0.518–0.525] | 0.628 [0.625–0.630] | 0.084 [0.078–0.089] | PASS |
| xgb_regularized | B2_0 | 2,982 | 0.569 [0.565–0.574] | 0.580 [0.575–0.585] | 0.617 [0.612–0.621] | 0.062 [0.060–0.064] | BLOCK |
| xgb_regularized | B2_1 | 1,932 | 0.527 [0.521–0.533] | 0.636 [0.628–0.643] | 0.695 [0.687–0.703] | 0.073 [0.070–0.076] | PASS |
| xgb_regularized | B2_2 | 1,494 | 0.546 [0.539–0.553] | 0.576 [0.572–0.581] | 0.670 [0.666–0.673] | 0.108 [0.100–0.117] | PASS |
| xgb_regularized | B2_comb | 6,408 | 0.516 [0.511–0.521] | 0.508 [0.506–0.510] | 0.560 [0.557–0.564] | 0.025 [0.023–0.026] | PASS |

Threshold sweep (shadow-model mean AUC):

| variant | target | ≤0.50 | ≤0.52 | ≤0.55 | ≤0.58 | ≤0.60 |
|---|---|---|---|---|---|---|
| xgb_krcp | A_0 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_krcp | Aprime_0 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_krcp | B1_comb | BLOCK | BLOCK | PASS | PASS | PASS |
| xgb_krcp | B2_comb | BLOCK | BLOCK | PASS | PASS | PASS |
| xgb_krcp | F_B1 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_leaky | A_0 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_leaky | Aprime_0 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_leaky | B1_comb | BLOCK | BLOCK | BLOCK | PASS | PASS |
| xgb_leaky | B2_comb | BLOCK | BLOCK | BLOCK | BLOCK | PASS |
| xgb_regularized | A_0 | BLOCK | BLOCK | PASS | PASS | PASS |
| xgb_regularized | Aprime_0 | BLOCK | BLOCK | BLOCK | PASS | PASS |
| xgb_regularized | B1_comb | BLOCK | PASS | PASS | PASS | PASS |
| xgb_regularized | B2_comb | BLOCK | PASS | PASS | PASS | PASS |
| xgb_regularized | F_B1 | BLOCK | BLOCK | PASS | PASS | PASS |

## Exposure relative to the central model, by attack (route − A; mean [95% CI across seeds]; descriptive)

| variant | route | shadow AUC | LiRA AUC | LiRA TPR@1%FPR | loss AUC |
|---|---|---|---|---|---|
| xgb_krcp | A′ (size control) | 0.026 [0.021–0.032] | -0.012 [-0.018–-0.005] | -0.017 [-0.027–-0.007] | 0.018 [0.008–0.028] |
| xgb_krcp | B1 sites (mean of 3) | -0.002 [-0.005–0.001] | 0.012 [0.007–0.017] | -0.023 [-0.033–-0.014] | 0.069 [0.063–0.074] |
| xgb_krcp | B1 averaged | -0.071 [-0.074–-0.068] | -0.141 [-0.148–-0.135] | -0.145 [-0.153–-0.136] | -0.048 [-0.052–-0.044] |
| xgb_krcp | B1 federated | 0.001 [-0.004–0.006] | -0.001 [-0.007–0.005] | 0.000 [-0.012–0.013] | -0.001 [-0.006–0.004] |
| xgb_krcp | B2 sites (mean of 3) | -0.003 [-0.006–-0.000] | 0.011 [0.005–0.017] | -0.037 [-0.046–-0.027] | 0.069 [0.063–0.074] |
| xgb_krcp | B2 averaged | -0.073 [-0.076–-0.070] | -0.133 [-0.140–-0.127] | -0.134 [-0.144–-0.125] | -0.048 [-0.052–-0.044] |
| xgb_leaky | A′ (size control) | -0.033 [-0.044–-0.021] | -0.109 [-0.124–-0.095] | -0.144 [-0.150–-0.137] | -0.049 [-0.061–-0.038] |
| xgb_leaky | B1 sites (mean of 3) | -0.010 [-0.013–-0.008] | -0.081 [-0.084–-0.078] | -0.143 [-0.148–-0.137] | -0.010 [-0.012–-0.008] |
| xgb_leaky | B1 averaged | -0.080 [-0.082–-0.078] | -0.273 [-0.276–-0.269] | -0.230 [-0.235–-0.226] | -0.129 [-0.132–-0.125] |
| xgb_leaky | B2 sites (mean of 3) | -0.009 [-0.010–-0.008] | -0.082 [-0.085–-0.079] | -0.146 [-0.151–-0.140] | -0.010 [-0.012–-0.008] |
| xgb_leaky | B2 averaged | -0.079 [-0.081–-0.076] | -0.255 [-0.260–-0.251] | -0.226 [-0.231–-0.222] | -0.129 [-0.132–-0.125] |
| xgb_regularized | A′ (size control) | 0.036 [0.031–0.041] | 0.014 [0.006–0.023] | 0.013 [0.007–0.020] | 0.027 [0.016–0.037] |
| xgb_regularized | B1 sites (mean of 3) | 0.007 [0.000–0.015] | 0.033 [0.028–0.039] | -0.003 [-0.009–0.002] | 0.075 [0.070–0.080] |
| xgb_regularized | B1 averaged | -0.022 [-0.029–-0.015] | -0.068 [-0.073–-0.063] | -0.068 [-0.073–-0.063] | -0.014 [-0.018–-0.011] |
| xgb_regularized | B1 federated | -0.001 [-0.008–0.006] | 0.001 [-0.005–0.007] | -0.000 [-0.008–0.007] | -0.000 [-0.007–0.006] |
| xgb_regularized | B2 sites (mean of 3) | 0.011 [0.004–0.018] | 0.034 [0.029–0.040] | -0.003 [-0.008–0.001] | 0.075 [0.070–0.080] |
| xgb_regularized | B2 averaged | -0.020 [-0.026–-0.015] | -0.066 [-0.071–-0.060] | -0.060 [-0.064–-0.055] | -0.014 [-0.018–-0.011] |

## H2 — distributed vs central leakage (shadow-model AUC, site mean − A)

| variant | B1 sites − A | A′ − A (size only) | B2 sites − A |
|---|---|---|---|
| xgb_krcp | -0.002 [-0.005–0.001] | 0.026 [0.021–0.032] | -0.003 [-0.006–-0.000] |
| xgb_leaky | -0.010 [-0.013–-0.008] | -0.033 [-0.044–-0.021] | -0.009 [-0.010–-0.008] |
| xgb_regularized | 0.007 [0.000–0.015] | 0.036 [0.031–0.041] | 0.011 [0.004–0.018] |

## Utility on the common validation set

| variant | target | AUROC | scaled Brier | cal. intercept | cal. slope |
|---|---|---|---|---|---|
| xgb_krcp | A_0 | 0.895 [0.895–0.896] | 0.280 [0.275–0.284] | -0.15 [-0.17–-0.13] | 0.62 [0.62–0.63] |
| xgb_krcp | Aprime_0 | 0.882 [0.878–0.885] | 0.229 [0.213–0.246] | 0.45 [0.34–0.57] | 0.48 [0.47–0.50] |
| xgb_krcp | B1_0 | 0.878 [0.877–0.879] | 0.178 [0.174–0.181] | 0.71 [0.69–0.73] | 0.48 [0.48–0.49] |
| xgb_krcp | B1_1 | 0.872 [0.870–0.874] | 0.253 [0.248–0.258] | 0.13 [0.09–0.18] | 0.51 [0.51–0.52] |
| xgb_krcp | B1_2 | 0.854 [0.852–0.856] | 0.200 [0.194–0.205] | 0.57 [0.54–0.60] | 0.48 [0.48–0.48] |
| xgb_krcp | B1_comb | 0.894 [0.893–0.896] | 0.313 [0.310–0.316] | 0.37 [0.35–0.38] | 0.69 [0.68–0.69] |
| xgb_krcp | F_B1 | 0.894 [0.893–0.896] | 0.273 [0.268–0.279] | -0.14 [-0.16–-0.13] | 0.62 [0.61–0.62] |
| xgb_krcp | B2_0 | 0.878 [0.877–0.879] | 0.178 [0.174–0.181] | 0.71 [0.69–0.73] | 0.48 [0.48–0.49] |
| xgb_krcp | B2_1 | 0.872 [0.870–0.874] | 0.253 [0.248–0.258] | 0.13 [0.09–0.18] | 0.51 [0.51–0.52] |
| xgb_krcp | B2_2 | 0.854 [0.852–0.856] | 0.200 [0.194–0.205] | 0.57 [0.54–0.60] | 0.48 [0.48–0.48] |
| xgb_krcp | B2_comb | 0.894 [0.893–0.896] | 0.313 [0.310–0.316] | 0.37 [0.35–0.38] | 0.69 [0.68–0.69] |
| xgb_leaky | A_0 | 0.858 [0.858–0.858] | 0.104 [0.104–0.104] | 6.74 [6.74–6.74] | 0.25 [0.25–0.25] |
| xgb_leaky | Aprime_0 | 0.757 [0.739–0.775] | -0.295 [-0.412–-0.177] | 3.15 [0.60–5.70] | 0.12 [0.09–0.14] |
| xgb_leaky | B1_0 | 0.791 [0.791–0.791] | -0.042 [-0.042–-0.042] | 7.39 [7.39–7.39] | 0.19 [0.19–0.19] |
| xgb_leaky | B1_1 | 0.696 [0.696–0.696] | -1.217 [-1.217–-1.217] | -5.69 [-5.69–-5.69] | 0.07 [0.07–0.07] |
| xgb_leaky | B1_2 | 0.717 [0.717–0.717] | -0.687 [-0.687–-0.687] | -3575779022739269.00 [-3575779022739269.00–-3575779022739269.00] | 0.07 [0.07–0.07] |
| xgb_leaky | B1_comb | 0.779 [0.779–0.779] | -0.033 [-0.033–-0.033] | -3576002324207230.50 [-3576002324207231.00–-3576002324207230.00] | 0.13 [0.13–0.13] |
| xgb_leaky | B2_0 | 0.791 [0.791–0.791] | -0.042 [-0.042–-0.042] | 7.39 [7.39–7.39] | 0.19 [0.19–0.19] |
| xgb_leaky | B2_1 | 0.696 [0.696–0.696] | -1.217 [-1.217–-1.217] | -5.69 [-5.69–-5.69] | 0.07 [0.07–0.07] |
| xgb_leaky | B2_2 | 0.717 [0.717–0.717] | -0.687 [-0.687–-0.687] | -3575779022739269.00 [-3575779022739269.00–-3575779022739269.00] | 0.07 [0.07–0.07] |
| xgb_leaky | B2_comb | 0.779 [0.779–0.779] | -0.033 [-0.033–-0.033] | -3576002324207230.50 [-3576002324207231.00–-3576002324207230.00] | 0.13 [0.13–0.13] |
| xgb_regularized | A_0 | 0.901 [0.899–0.902] | 0.026 [0.021–0.031] | -1.52 [-1.53–-1.52] | 0.92 [0.92–0.93] |
| xgb_regularized | Aprime_0 | 0.885 [0.880–0.889] | 0.146 [0.128–0.165] | -1.02 [-1.08–-0.95] | 0.77 [0.74–0.80] |
| xgb_regularized | B1_0 | 0.885 [0.884–0.886] | 0.108 [0.101–0.115] | -1.04 [-1.06–-1.01] | 0.80 [0.79–0.80] |
| xgb_regularized | B1_1 | 0.876 [0.874–0.878] | 0.102 [0.094–0.109] | -1.24 [-1.25–-1.23] | 0.82 [0.81–0.83] |
| xgb_regularized | B1_2 | 0.856 [0.854–0.858] | 0.148 [0.140–0.156] | -0.83 [-0.84–-0.81] | 0.76 [0.75–0.77] |
| xgb_regularized | B1_comb | 0.897 [0.896–0.897] | 0.221 [0.218–0.224] | -0.93 [-0.94–-0.92] | 1.05 [1.05–1.06] |
| xgb_regularized | F_B1 | 0.900 [0.899–0.902] | 0.025 [0.018–0.031] | -1.52 [-1.53–-1.52] | 0.93 [0.92–0.94] |
| xgb_regularized | B2_0 | 0.885 [0.884–0.886] | 0.108 [0.101–0.115] | -1.04 [-1.06–-1.01] | 0.80 [0.79–0.80] |
| xgb_regularized | B2_1 | 0.876 [0.874–0.878] | 0.102 [0.094–0.109] | -1.24 [-1.25–-1.23] | 0.82 [0.81–0.83] |
| xgb_regularized | B2_2 | 0.856 [0.854–0.858] | 0.148 [0.140–0.156] | -0.83 [-0.84–-0.81] | 0.76 [0.75–0.77] |
| xgb_regularized | B2_comb | 0.897 [0.896–0.897] | 0.221 [0.218–0.224] | -0.93 [-0.94–-0.92] | 1.05 [1.05–1.06] |

## H3 — combined model vs central (ΔAUROC, non-inferiority margin −0.02)

| variant | target | ΔAUROC | non-inferior |
|---|---|---|---|
| xgb_krcp | B1_comb | -0.001 [-0.002–0.000] | yes |
| xgb_krcp | B2_comb | -0.001 [-0.002–0.000] | yes |
| xgb_leaky | B1_comb | -0.112 [-0.112–-0.112] | no |
| xgb_leaky | B2_comb | -0.112 [-0.112–-0.112] | no |
| xgb_regularized | B1_comb | -0.004 [-0.005–-0.002] | yes |
| xgb_regularized | B2_comb | -0.004 [-0.005–-0.002] | yes |

## H5 — federated model (F) vs central model (A)

| variant | target | ΔAUROC (F − A) | non-inferior | shadow AUC F | shadow AUC A | shadow AUC sites (mean) | F ≤ A + 0.01 and F < sites (means; the pre-specified test is in the decision rules) |
|---|---|---|---|---|---|---|---|
| xgb_krcp | F_B1 | -0.001 [-0.002–0.000] | yes | 0.619 | 0.618 | 0.616 | no |
| xgb_regularized | F_B1 | -0.000 [-0.002–0.002] | yes | 0.535 | 0.536 | 0.544 | yes |

## H6 — exposure against training size (shadow-model AUC; one target per seed and size)

xgb_krcp: Spearman ρ (size, seed-mean AUC) = -1.00; slope per log10(n) = -0.064 [-0.078–-0.051]

| n train | 2,000 | 5,000 | 6,408 |
|---|---|---|---|
| shadow AUC | 0.651 [0.644–0.657] | 0.625 [0.621–0.628] | 0.618 [0.615–0.621] |
| val AUROC | 0.882 [0.876–0.887] | 0.892 [0.891–0.894] | 0.895 [0.895–0.896] |

xgb_regularized: Spearman ρ (size, seed-mean AUC) = -1.00; slope per log10(n) = -0.087 [-0.100–-0.073]

| n train | 2,000 | 5,000 | 6,408 |
|---|---|---|---|
| shadow AUC | 0.579 [0.573–0.585] | 0.540 [0.535–0.544] | 0.537 [0.532–0.543] |
| val AUROC | 0.884 [0.879–0.889] | 0.897 [0.895–0.899] | 0.901 [0.899–0.902] |


## Subgroup LiRA AUC (xgb_krcp, A_0; groups ≥ 100 in the evaluation sample)

| subgroup | level | LiRA AUC | shadow AUC |
|---|---|---|---|
| sg_age65 | <65 | 0.692 [0.688–0.697] | 0.593 [0.588–0.598] |
| sg_age65 | >=65 | 0.771 [0.765–0.778] | 0.645 [0.641–0.648] |
| sg_ethnicity | black | 0.739 [0.733–0.745] | 0.626 [0.620–0.631] |
| sg_ethnicity | hispanic | 0.704 [0.689–0.719] | 0.617 [0.600–0.634] |
| sg_ethnicity | other | 0.778 [0.766–0.790] | 0.626 [0.609–0.643] |
| sg_ethnicity | white | 0.723 [0.717–0.728] | 0.613 [0.611–0.614] |
| sg_sex | female | 0.737 [0.732–0.743] | 0.622 [0.619–0.626] |
| sg_sex | male | 0.722 [0.716–0.727] | 0.613 [0.611–0.616] |
| sg_unit | med-surg | 0.725 [0.711–0.739] | 0.606 [0.594–0.618] |
| sg_unit | medical-cardiac | 0.770 [0.765–0.776] | 0.630 [0.626–0.634] |
| sg_unit | neuro | 0.710 [0.701–0.720] | 0.618 [0.611–0.624] |
| sg_unit | surgical | 0.672 [0.665–0.680] | 0.598 [0.590–0.605] |

## Gate 1 — code-free formats (XGB JSON, LGBM text, CatBoost CBM, RF tree JSON; no pickle on load)

| variant | target | max abs Δp | label agreement | size (kB) |
|---|---|---|---|---|
| xgb_krcp | A_0 | 0.0e+00 | 1.0000 | 2,253 |
| xgb_krcp | B1_0 | 0.0e+00 | 1.0000 | 1,576 |
| xgb_krcp | F_B1 | 0.0e+00 | 1.0000 | 2,216 |
| xgb_leaky | A_0 | 0.0e+00 | 1.0000 | 8,244 |
| xgb_leaky | B1_0 | 0.0e+00 | 1.0000 | 3,544 |
| xgb_regularized | A_0 | 0.0e+00 | 1.0000 | 555 |
| xgb_regularized | B1_0 | 0.0e+00 | 1.0000 | 512 |
| xgb_regularized | F_B1 | 0.0e+00 | 1.0000 | 556 |

Leaf audit — share of leaves with < 11 training people:

| variant | target | xgb |
|---|---|---|
| xgb_krcp | A_0 | 17.1% |
| xgb_krcp | B1_0 | 13.3% |
| xgb_krcp | F_B1 | 16.6% |
| xgb_leaky | A_0 | 72.5% |
| xgb_leaky | B1_0 | 73.8% |
| xgb_regularized | A_0 | 0.7% |
| xgb_regularized | B1_0 | 2.2% |
| xgb_regularized | F_B1 | 0.9% |

## Gate 3 — escrow re-execution

| variant | target | signature | data hash | versions | abs ΔAUROC | max abs Δp | pass |
|---|---|---|---|---|---|---|---|
| xgb_krcp | A_0 | True | True | True | 0.0e+00 | 0.0e+00 | True |
| xgb_leaky | A_0 | True | True | True | 0.0e+00 | 0.0e+00 | True |
| xgb_regularized | A_0 | True | True | True | 0.0e+00 | 0.0e+00 | True |
