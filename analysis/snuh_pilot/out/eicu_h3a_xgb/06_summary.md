# Pilot summary — eicu

seeds: [42, 43, 44, 45, 46, 47, 48, 49, 50, 51] · values = mean [95% CI across seeds]

membership-inference audit: LiRA / RMIA with 64 reference models per target, shadow-model attack with 16 shadows

## Pre-specified decision rules (docs/ANALYSIS_PLAN_v1.md §3), evaluated by code

| hypothesis | role | variant / target | verdict | evidence |
|---|---|---|---|---|
| H1 | secondary | xgb_leaky vs xgb_regularized | **supported** | shadow AUC xgb_leaky 0.655 > 0.55: yes; xgb_regularized 0.531 <= 0.55: yes; AUROC xgb_regularized 0.908 >= xgb_leaky 0.856: yes |
| H2 | primary | xgb_krcp B1 (size) | **supported** | gap B1 0.017 [0.013–0.021] lower bound > 0: yes; size share (A′−A)/(B1 gap) 1.86 >= 0.5: yes |
| H2 | secondary | xgb_krcp B2 (unequal sites) | **not supported** | gap B2 0.016 [0.012–0.020] lower bound > 0: yes; B2 gap > B1 gap: no |
| H2 | secondary | xgb_leaky B1 (size) | **not supported** | gap B1 0.013 [0.010–0.016] lower bound > 0: yes; size share (A′−A)/(B1 gap) -0.11 >= 0.5: no |
| H2 | secondary | xgb_leaky B2 (unequal sites) | **not supported** | gap B2 0.011 [0.009–0.014] lower bound > 0: yes; B2 gap > B1 gap: no |
| H2 | secondary | xgb_regularized B1 (size) | **supported** | gap B1 0.025 [0.019–0.031] lower bound > 0: yes; size share (A′−A)/(B1 gap) 1.39 >= 0.5: yes |
| H2 | secondary | xgb_regularized B2 (unequal sites) | **supported** | gap B2 0.026 [0.021–0.031] lower bound > 0: yes; B2 gap > B1 gap: yes |
| H3 | secondary | xgb_krcp B1_comb | **supported** | ΔAUROC -0.004 [-0.005–-0.003] lower bound > −0.02: yes |
| H3 | secondary | xgb_krcp B2_comb | **supported** | ΔAUROC -0.004 [-0.005–-0.003] lower bound > −0.02: yes |
| H3 | secondary | xgb_leaky B1_comb | **not supported** | ΔAUROC -0.045 [-0.045–-0.045] lower bound > −0.02: no |
| H3 | secondary | xgb_leaky B2_comb | **not supported** | ΔAUROC -0.045 [-0.045–-0.045] lower bound > −0.02: no |
| H3 | secondary | xgb_regularized B1_comb | **supported** | ΔAUROC -0.006 [-0.008–-0.005] lower bound > −0.02: yes |
| H3 | secondary | xgb_regularized B2_comb | **supported** | ΔAUROC -0.006 [-0.008–-0.005] lower bound > −0.02: yes |
| H4 | secondary | xgb_krcp | **supported** | Gate 1 max abs Δp 0.0e+00 < 1e-6: yes; Gate 3 signature and data hash match: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |
| H4 | secondary | xgb_leaky | **supported** | Gate 1 max abs Δp 0.0e+00 < 1e-6: yes; Gate 3 signature and data hash match: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |
| H4 | secondary | xgb_regularized | **supported** | Gate 1 max abs Δp 0.0e+00 < 1e-6: yes; Gate 3 signature and data hash match: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |
| H4 | secondary | federated re-execution | **supported** | 2 job(s) run again in a fresh workspace: max abs Δp 0.0e+00 < 1e-6: yes; max abs ΔAUROC 0.0e+00 <= 1e-4: yes |
| H5 | primary | xgb_krcp F_B1 | **supported** | ΔAUROC(F−A) -0.001 [-0.003–0.001] lower bound > −0.02: yes; shadow AUC F 0.606 <= A 0.608 + 0.01: yes; (sites mean − F) 0.018 [0.015–0.022] lower bound > 0: yes |
| H5 | secondary | xgb_regularized F_B1 | **supported** | ΔAUROC(F−A) -0.000 [-0.003–0.002] lower bound > −0.02: yes; shadow AUC F 0.529 <= A 0.531 + 0.01: yes; (sites mean − F) 0.027 [0.020–0.034] lower bound > 0: yes |
| H6 | secondary | xgb_krcp | **supported** | Spearman ρ (size, seed-mean AUC) -1.00 < 0: yes; slope per log10(n) -0.046 [-0.057–-0.036] upper bound < 0: yes |
| H6 | secondary | xgb_regularized | **supported** | Spearman ρ (size, seed-mean AUC) -1.00 < 0: yes; slope per log10(n) -0.067 [-0.075–-0.059] upper bound < 0: yes |

Primary verdicts: H5 and the B1 part of H2 for the published configuration (xgb_krcp) with equal sites (B1). Every other row is secondary. Each hypothesis is judged on its own; no multiplicity correction. Intervals are t-based across seeds (utility differences also have paired bootstrap intervals in 01_utility_long.csv). "not evaluable" means an input is missing or has fewer than two seeds.

## Gate 2 — membership inference (AUC; decision on shadow-model attack, threshold 0.55)

| variant | target | n members | shadow AUC | loss AUC | LiRA AUC | LiRA TPR@1%FPR | decision |
|---|---|---|---|---|---|---|---|
| xgb_krcp | A_0 | 7,868 | 0.608 [0.605–0.611] | 0.558 [0.554–0.562] | 0.719 [0.715–0.722] | 0.160 [0.153–0.166] | BLOCK |
| xgb_krcp | Aprime_0 | 2,622 | 0.639 [0.635–0.643] | 0.572 [0.564–0.579] | 0.704 [0.699–0.709] | 0.151 [0.144–0.158] | BLOCK |
| xgb_krcp | B1_0 | 2,982 | 0.615 [0.612–0.618] | 0.605 [0.602–0.609] | 0.690 [0.686–0.695] | 0.105 [0.104–0.106] | BLOCK |
| xgb_krcp | B1_1 | 2,740 | 0.633 [0.629–0.637] | 0.634 [0.630–0.639] | 0.751 [0.748–0.755] | 0.140 [0.135–0.146] | BLOCK |
| xgb_krcp | B1_2 | 2,146 | 0.626 [0.622–0.630] | 0.602 [0.596–0.607] | 0.697 [0.694–0.700] | 0.122 [0.118–0.125] | BLOCK |
| xgb_krcp | B1_comb | 7,868 | 0.551 [0.548–0.554] | 0.519 [0.516–0.522] | 0.586 [0.583–0.589] | 0.040 [0.037–0.043] | BLOCK |
| xgb_krcp | F_B1 | 7,868 | 0.606 [0.603–0.610] | 0.559 [0.558–0.561] | 0.718 [0.714–0.722] | 0.157 [0.154–0.160] | BLOCK |
| xgb_krcp | B2_0 | 2,982 | 0.614 [0.612–0.616] | 0.605 [0.602–0.609] | 0.688 [0.683–0.692] | 0.108 [0.105–0.110] | BLOCK |
| xgb_krcp | B2_1 | 2,740 | 0.632 [0.629–0.635] | 0.634 [0.630–0.639] | 0.756 [0.754–0.758] | 0.139 [0.136–0.143] | BLOCK |
| xgb_krcp | B2_2 | 2,146 | 0.626 [0.620–0.631] | 0.602 [0.596–0.607] | 0.699 [0.697–0.701] | 0.120 [0.117–0.123] | BLOCK |
| xgb_krcp | B2_comb | 7,868 | 0.548 [0.544–0.551] | 0.519 [0.516–0.522] | 0.592 [0.589–0.595] | 0.046 [0.044–0.048] | PASS |
| xgb_leaky | A_0 | 7,868 | 0.655 [0.653–0.656] | 0.671 [0.669–0.673] | 0.821 [0.818–0.823] | 0.239 [0.234–0.245] | BLOCK |
| xgb_leaky | Aprime_0 | 2,622 | 0.653 [0.645–0.661] | 0.656 [0.644–0.667] | 0.750 [0.738–0.762] | 0.112 [0.105–0.119] | BLOCK |
| xgb_leaky | B1_0 | 2,982 | 0.662 [0.659–0.664] | 0.679 [0.676–0.681] | 0.755 [0.752–0.757] | 0.105 [0.100–0.110] | BLOCK |
| xgb_leaky | B1_1 | 2,740 | 0.701 [0.698–0.704] | 0.716 [0.712–0.721] | 0.793 [0.790–0.797] | 0.131 [0.127–0.136] | BLOCK |
| xgb_leaky | B1_2 | 2,146 | 0.640 [0.637–0.644] | 0.641 [0.636–0.646] | 0.743 [0.738–0.748] | 0.101 [0.099–0.104] | BLOCK |
| xgb_leaky | B1_comb | 7,868 | 0.580 [0.577–0.583] | 0.540 [0.537–0.543] | 0.571 [0.568–0.573] | 0.008 [0.007–0.009] | BLOCK |
| xgb_leaky | B2_0 | 2,982 | 0.660 [0.657–0.662] | 0.679 [0.676–0.681] | 0.759 [0.756–0.762] | 0.103 [0.100–0.107] | BLOCK |
| xgb_leaky | B2_1 | 2,740 | 0.698 [0.695–0.701] | 0.716 [0.712–0.721] | 0.795 [0.790–0.800] | 0.134 [0.131–0.137] | BLOCK |
| xgb_leaky | B2_2 | 2,146 | 0.639 [0.635–0.642] | 0.641 [0.636–0.646] | 0.738 [0.734–0.742] | 0.087 [0.083–0.091] | BLOCK |
| xgb_leaky | B2_comb | 7,868 | 0.580 [0.578–0.583] | 0.540 [0.537–0.543] | 0.577 [0.574–0.579] | 0.011 [0.010–0.012] | BLOCK |
| xgb_regularized | A_0 | 7,868 | 0.531 [0.526–0.535] | 0.514 [0.510–0.518] | 0.610 [0.607–0.614] | 0.072 [0.070–0.075] | PASS |
| xgb_regularized | Aprime_0 | 2,622 | 0.566 [0.561–0.571] | 0.537 [0.531–0.543] | 0.625 [0.620–0.631] | 0.088 [0.083–0.093] | BLOCK |
| xgb_regularized | B1_0 | 2,982 | 0.556 [0.553–0.559] | 0.587 [0.583–0.590] | 0.616 [0.611–0.622] | 0.068 [0.066–0.071] | BLOCK |
| xgb_regularized | B1_1 | 2,740 | 0.559 [0.555–0.564] | 0.608 [0.604–0.613] | 0.665 [0.661–0.668] | 0.062 [0.059–0.066] | BLOCK |
| xgb_regularized | B1_2 | 2,146 | 0.553 [0.549–0.557] | 0.585 [0.578–0.592] | 0.635 [0.632–0.637] | 0.078 [0.075–0.080] | BLOCK |
| xgb_regularized | B1_comb | 7,868 | 0.503 [0.496–0.509] | 0.509 [0.506–0.511] | 0.555 [0.552–0.558] | 0.023 [0.021–0.025] | PASS |
| xgb_regularized | F_B1 | 7,868 | 0.529 [0.523–0.535] | 0.516 [0.513–0.518] | 0.614 [0.611–0.617] | 0.072 [0.069–0.075] | PASS |
| xgb_regularized | B2_0 | 2,982 | 0.554 [0.550–0.558] | 0.587 [0.583–0.590] | 0.620 [0.616–0.624] | 0.061 [0.058–0.064] | BLOCK |
| xgb_regularized | B2_1 | 2,740 | 0.563 [0.558–0.567] | 0.608 [0.604–0.613] | 0.667 [0.665–0.669] | 0.063 [0.059–0.066] | BLOCK |
| xgb_regularized | B2_2 | 2,146 | 0.553 [0.550–0.557] | 0.585 [0.578–0.592] | 0.635 [0.631–0.639] | 0.074 [0.069–0.079] | BLOCK |
| xgb_regularized | B2_comb | 7,868 | 0.505 [0.501–0.509] | 0.509 [0.506–0.511] | 0.555 [0.551–0.558] | 0.025 [0.023–0.027] | PASS |

Threshold sweep (shadow-model mean AUC):

| variant | target | ≤0.50 | ≤0.52 | ≤0.55 | ≤0.58 | ≤0.60 |
|---|---|---|---|---|---|---|
| xgb_krcp | A_0 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_krcp | Aprime_0 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_krcp | B1_comb | BLOCK | BLOCK | BLOCK | PASS | PASS |
| xgb_krcp | B2_comb | BLOCK | BLOCK | PASS | PASS | PASS |
| xgb_krcp | F_B1 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_leaky | A_0 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_leaky | Aprime_0 | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK |
| xgb_leaky | B1_comb | BLOCK | BLOCK | BLOCK | BLOCK | PASS |
| xgb_leaky | B2_comb | BLOCK | BLOCK | BLOCK | BLOCK | PASS |
| xgb_regularized | A_0 | BLOCK | BLOCK | PASS | PASS | PASS |
| xgb_regularized | Aprime_0 | BLOCK | BLOCK | BLOCK | PASS | PASS |
| xgb_regularized | B1_comb | BLOCK | PASS | PASS | PASS | PASS |
| xgb_regularized | B2_comb | BLOCK | PASS | PASS | PASS | PASS |
| xgb_regularized | F_B1 | BLOCK | BLOCK | PASS | PASS | PASS |

## Exposure relative to the central model, by attack (route − A; mean [95% CI across seeds]; descriptive)

| variant | route | shadow AUC | LiRA AUC | LiRA TPR@1%FPR | loss AUC |
|---|---|---|---|---|---|
| xgb_krcp | A′ (size control) | 0.031 [0.025–0.037] | -0.014 [-0.022–-0.007] | -0.009 [-0.020–0.003] | 0.014 [0.006–0.022] |
| xgb_krcp | B1 sites (mean of 3) | 0.017 [0.013–0.021] | -0.006 [-0.009–-0.002] | -0.037 [-0.043–-0.031] | 0.056 [0.051–0.061] |
| xgb_krcp | B1 averaged | -0.057 [-0.063–-0.052] | -0.133 [-0.137–-0.128] | -0.119 [-0.124–-0.114] | -0.039 [-0.042–-0.035] |
| xgb_krcp | B1 federated | -0.002 [-0.006–0.003] | -0.001 [-0.006–0.004] | -0.002 [-0.007–0.003] | 0.002 [-0.002–0.005] |
| xgb_krcp | B2 sites (mean of 3) | 0.016 [0.012–0.020] | -0.004 [-0.009–0.000] | -0.037 [-0.044–-0.031] | 0.056 [0.051–0.061] |
| xgb_krcp | B2 averaged | -0.060 [-0.067–-0.054] | -0.126 [-0.131–-0.122] | -0.114 [-0.120–-0.107] | -0.039 [-0.042–-0.035] |
| xgb_leaky | A′ (size control) | -0.001 [-0.010–0.007] | -0.070 [-0.083–-0.058] | -0.127 [-0.138–-0.116] | -0.015 [-0.028–-0.003] |
| xgb_leaky | B1 sites (mean of 3) | 0.013 [0.010–0.016] | -0.057 [-0.061–-0.054] | -0.127 [-0.133–-0.121] | 0.008 [0.005–0.011] |
| xgb_leaky | B1 averaged | -0.074 [-0.076–-0.072] | -0.250 [-0.254–-0.246] | -0.231 [-0.237–-0.225] | -0.131 [-0.134–-0.128] |
| xgb_leaky | B2 sites (mean of 3) | 0.011 [0.009–0.014] | -0.057 [-0.060–-0.053] | -0.131 [-0.138–-0.125] | 0.008 [0.005–0.011] |
| xgb_leaky | B2 averaged | -0.074 [-0.077–-0.072] | -0.244 [-0.248–-0.240] | -0.229 [-0.234–-0.223] | -0.131 [-0.134–-0.128] |
| xgb_regularized | A′ (size control) | 0.035 [0.031–0.039] | 0.015 [0.007–0.022] | 0.015 [0.011–0.020] | 0.023 [0.015–0.031] |
| xgb_regularized | B1 sites (mean of 3) | 0.025 [0.019–0.031] | 0.028 [0.024–0.032] | -0.003 [-0.006–0.000] | 0.079 [0.075–0.084] |
| xgb_regularized | B1 averaged | -0.028 [-0.032–-0.024] | -0.055 [-0.060–-0.050] | -0.049 [-0.052–-0.046] | -0.005 [-0.009–-0.002] |
| xgb_regularized | B1 federated | -0.002 [-0.007–0.004] | 0.004 [-0.000–0.007] | -0.001 [-0.004–0.003] | 0.002 [-0.004–0.007] |
| xgb_regularized | B2 sites (mean of 3) | 0.026 [0.021–0.031] | 0.030 [0.025–0.035] | -0.006 [-0.010–-0.003] | 0.079 [0.075–0.084] |
| xgb_regularized | B2 averaged | -0.026 [-0.029–-0.023] | -0.056 [-0.060–-0.051] | -0.048 [-0.051–-0.044] | -0.005 [-0.009–-0.002] |

## H2 — distributed vs central leakage (shadow-model AUC, site mean − A)

| variant | B1 sites − A | A′ − A (size only) | B2 sites − A |
|---|---|---|---|
| xgb_krcp | 0.017 [0.013–0.021] | 0.031 [0.025–0.037] | 0.016 [0.012–0.020] |
| xgb_leaky | 0.013 [0.010–0.016] | -0.001 [-0.010–0.007] | 0.011 [0.009–0.014] |
| xgb_regularized | 0.025 [0.019–0.031] | 0.035 [0.031–0.039] | 0.026 [0.021–0.031] |

## Utility on the common validation set

| variant | target | AUROC | scaled Brier | cal. intercept | cal. slope |
|---|---|---|---|---|---|
| xgb_krcp | A_0 | 0.899 [0.898–0.900] | 0.257 [0.252–0.262] | -0.42 [-0.44–-0.40] | 0.68 [0.68–0.69] |
| xgb_krcp | Aprime_0 | 0.885 [0.881–0.889] | 0.242 [0.220–0.264] | 0.30 [0.19–0.41] | 0.54 [0.53–0.56] |
| xgb_krcp | B1_0 | 0.876 [0.875–0.877] | 0.193 [0.188–0.197] | 0.57 [0.55–0.60] | 0.50 [0.50–0.51] |
| xgb_krcp | B1_1 | 0.871 [0.871–0.872] | 0.146 [0.140–0.152] | -0.37 [-0.38–-0.35] | 0.52 [0.52–0.53] |
| xgb_krcp | B1_2 | 0.877 [0.876–0.878] | 0.221 [0.216–0.226] | 0.57 [0.56–0.59] | 0.51 [0.51–0.52] |
| xgb_krcp | B1_comb | 0.895 [0.895–0.896] | 0.302 [0.300–0.303] | 0.17 [0.16–0.18] | 0.73 [0.73–0.74] |
| xgb_krcp | F_B1 | 0.898 [0.897–0.899] | 0.254 [0.248–0.261] | -0.42 [-0.44–-0.41] | 0.68 [0.68–0.69] |
| xgb_krcp | B2_0 | 0.876 [0.875–0.877] | 0.193 [0.188–0.197] | 0.57 [0.55–0.60] | 0.50 [0.50–0.51] |
| xgb_krcp | B2_1 | 0.871 [0.871–0.872] | 0.146 [0.140–0.152] | -0.37 [-0.38–-0.35] | 0.52 [0.52–0.53] |
| xgb_krcp | B2_2 | 0.877 [0.876–0.878] | 0.221 [0.216–0.226] | 0.57 [0.56–0.59] | 0.51 [0.51–0.52] |
| xgb_krcp | B2_comb | 0.895 [0.895–0.896] | 0.302 [0.300–0.303] | 0.17 [0.16–0.18] | 0.73 [0.73–0.74] |
| xgb_leaky | A_0 | 0.856 [0.856–0.856] | 0.105 [0.105–0.105] | 6.93 [6.93–6.93] | 0.29 [0.29–0.29] |
| xgb_leaky | Aprime_0 | 0.801 [0.788–0.814] | 0.007 [-0.033–0.047] | 6.25 [5.81–6.70] | 0.20 [0.18–0.22] |
| xgb_leaky | B1_0 | 0.803 [0.803–0.803] | -0.002 [-0.002–-0.002] | 7.17 [7.17–7.17] | 0.21 [0.21–0.21] |
| xgb_leaky | B1_1 | 0.798 [0.798–0.798] | -0.017 [-0.017–-0.017] | 4.25 [4.25–4.25] | 0.17 [0.17–0.17] |
| xgb_leaky | B1_2 | 0.770 [0.770–0.770] | -0.135 [-0.135–-0.135] | 6.38 [6.38–6.38] | 0.13 [0.13–0.13] |
| xgb_leaky | B1_comb | 0.844 [0.844–0.844] | 0.136 [0.136–0.136] | 2.14 [2.14–2.14] | 0.24 [0.24–0.24] |
| xgb_leaky | B2_0 | 0.803 [0.803–0.803] | -0.002 [-0.002–-0.002] | 7.17 [7.17–7.17] | 0.21 [0.21–0.21] |
| xgb_leaky | B2_1 | 0.798 [0.798–0.798] | -0.017 [-0.017–-0.017] | 4.25 [4.25–4.25] | 0.17 [0.17–0.17] |
| xgb_leaky | B2_2 | 0.770 [0.770–0.770] | -0.135 [-0.135–-0.135] | 6.38 [6.38–6.38] | 0.13 [0.13–0.13] |
| xgb_leaky | B2_comb | 0.844 [0.844–0.844] | 0.136 [0.136–0.136] | 2.14 [2.14–2.14] | 0.24 [0.24–0.24] |
| xgb_regularized | A_0 | 0.908 [0.906–0.909] | -0.167 [-0.170–-0.163] | -1.82 [-1.83–-1.82] | 1.02 [1.01–1.03] |
| xgb_regularized | Aprime_0 | 0.889 [0.886–0.892] | 0.040 [0.017–0.063] | -1.30 [-1.35–-1.24] | 0.86 [0.83–0.90] |
| xgb_regularized | B1_0 | 0.884 [0.883–0.885] | 0.058 [0.052–0.064] | -1.19 [-1.21–-1.17] | 0.83 [0.83–0.84] |
| xgb_regularized | B1_1 | 0.872 [0.870–0.874] | -0.224 [-0.236–-0.212] | -1.69 [-1.70–-1.68] | 0.86 [0.85–0.87] |
| xgb_regularized | B1_2 | 0.881 [0.879–0.883] | 0.064 [0.052–0.076] | -1.14 [-1.17–-1.12] | 0.81 [0.80–0.81] |
| xgb_regularized | B1_comb | 0.901 [0.900–0.902] | 0.110 [0.105–0.115] | -1.22 [-1.23–-1.21] | 1.14 [1.14–1.15] |
| xgb_regularized | F_B1 | 0.907 [0.906–0.908] | -0.165 [-0.172–-0.158] | -1.82 [-1.83–-1.81] | 1.02 [1.01–1.03] |
| xgb_regularized | B2_0 | 0.884 [0.883–0.885] | 0.058 [0.052–0.064] | -1.19 [-1.21–-1.17] | 0.83 [0.83–0.84] |
| xgb_regularized | B2_1 | 0.872 [0.870–0.874] | -0.224 [-0.236–-0.212] | -1.69 [-1.70–-1.68] | 0.86 [0.85–0.87] |
| xgb_regularized | B2_2 | 0.881 [0.879–0.883] | 0.064 [0.052–0.076] | -1.14 [-1.17–-1.12] | 0.81 [0.80–0.81] |
| xgb_regularized | B2_comb | 0.901 [0.900–0.902] | 0.110 [0.105–0.115] | -1.22 [-1.23–-1.21] | 1.14 [1.14–1.15] |

## H3 — combined model vs central (ΔAUROC, non-inferiority margin −0.02)

| variant | target | ΔAUROC | non-inferior |
|---|---|---|---|
| xgb_krcp | B1_comb | -0.004 [-0.005–-0.003] | yes |
| xgb_krcp | B2_comb | -0.004 [-0.005–-0.003] | yes |
| xgb_leaky | B1_comb | -0.045 [-0.045–-0.045] | no |
| xgb_leaky | B2_comb | -0.045 [-0.045–-0.045] | no |
| xgb_regularized | B1_comb | -0.006 [-0.008–-0.005] | yes |
| xgb_regularized | B2_comb | -0.006 [-0.008–-0.005] | yes |

## H5 — federated model (F) vs central model (A)

| variant | target | ΔAUROC (F − A) | non-inferior | shadow AUC F | shadow AUC A | shadow AUC sites (mean) | F ≤ A + 0.01 and F < sites (means; the pre-specified test is in the decision rules) |
|---|---|---|---|---|---|---|---|
| xgb_krcp | F_B1 | -0.001 [-0.003–0.001] | yes | 0.606 | 0.608 | 0.625 | yes |
| xgb_regularized | F_B1 | -0.000 [-0.003–0.002] | yes | 0.529 | 0.531 | 0.556 | yes |

## H6 — exposure against training size (shadow-model AUC; one target per seed and size)

xgb_krcp: Spearman ρ (size, seed-mean AUC) = -1.00; slope per log10(n) = -0.046 [-0.057–-0.036]

| n train | 2,000 | 5,000 | 7,868 |
|---|---|---|---|
| shadow AUC | 0.638 [0.633–0.643] | 0.626 [0.624–0.628] | 0.609 [0.606–0.612] |
| val AUROC | 0.882 [0.878–0.886] | 0.893 [0.890–0.895] | 0.899 [0.898–0.900] |

xgb_regularized: Spearman ρ (size, seed-mean AUC) = -1.00; slope per log10(n) = -0.067 [-0.075–-0.059]

| n train | 2,000 | 5,000 | 7,868 |
|---|---|---|---|
| shadow AUC | 0.569 [0.565–0.574] | 0.545 [0.541–0.549] | 0.529 [0.524–0.533] |
| val AUROC | 0.887 [0.883–0.890] | 0.900 [0.898–0.902] | 0.908 [0.906–0.909] |


## Subgroup LiRA AUC (xgb_krcp, A_0; groups ≥ 100 in the evaluation sample)

| subgroup | level | LiRA AUC | shadow AUC |
|---|---|---|---|
| sg_age65 | <65 | 0.664 [0.659–0.668] | 0.574 [0.567–0.582] |
| sg_age65 | >=65 | 0.768 [0.763–0.773] | 0.634 [0.631–0.637] |
| sg_ethnicity | black | 0.700 [0.688–0.711] | 0.574 [0.561–0.588] |
| sg_ethnicity | hispanic | 0.685 [0.673–0.697] | 0.566 [0.552–0.579] |
| sg_ethnicity | other | 0.758 [0.748–0.769] | 0.653 [0.640–0.667] |
| sg_ethnicity | white | 0.720 [0.716–0.723] | 0.611 [0.608–0.613] |
| sg_sex | female | 0.727 [0.723–0.731] | 0.613 [0.607–0.618] |
| sg_sex | male | 0.711 [0.707–0.714] | 0.604 [0.599–0.610] |
| sg_unit | med-surg | 0.770 [0.761–0.778] | 0.635 [0.627–0.643] |
| sg_unit | medical-cardiac | 0.733 [0.729–0.738] | 0.615 [0.612–0.618] |
| sg_unit | neuro | 0.701 [0.694–0.709] | 0.606 [0.600–0.612] |
| sg_unit | surgical | 0.662 [0.654–0.671] | 0.570 [0.561–0.578] |

## Gate 1 — code-free formats (XGB JSON, LGBM text, CatBoost CBM, RF tree JSON; no pickle on load)

| variant | target | max abs Δp | label agreement | size (kB) |
|---|---|---|---|---|
| xgb_krcp | A_0 | 0.0e+00 | 1.0000 | 2,379 |
| xgb_krcp | B1_0 | 0.0e+00 | 1.0000 | 1,576 |
| xgb_krcp | F_B1 | 0.0e+00 | 1.0000 | 2,345 |
| xgb_leaky | A_0 | 0.0e+00 | 1.0000 | 9,612 |
| xgb_leaky | B1_0 | 0.0e+00 | 1.0000 | 3,544 |
| xgb_regularized | A_0 | 0.0e+00 | 1.0000 | 560 |
| xgb_regularized | B1_0 | 0.0e+00 | 1.0000 | 512 |
| xgb_regularized | F_B1 | 0.0e+00 | 1.0000 | 556 |

Leaf audit — share of leaves with < 11 training people:

| variant | target | xgb |
|---|---|---|
| xgb_krcp | A_0 | 17.2% |
| xgb_krcp | B1_0 | 13.3% |
| xgb_krcp | F_B1 | 16.8% |
| xgb_leaky | A_0 | 71.3% |
| xgb_leaky | B1_0 | 73.8% |
| xgb_regularized | A_0 | 1.3% |
| xgb_regularized | B1_0 | 2.2% |
| xgb_regularized | F_B1 | 1.2% |

## Gate 3 — escrow re-execution

| variant | target | signature | data hash | versions | abs ΔAUROC | max abs Δp | pass |
|---|---|---|---|---|---|---|---|
| xgb_krcp | A_0 | True | True | True | 0.0e+00 | 0.0e+00 | True |
| xgb_leaky | A_0 | True | True | True | 0.0e+00 | 0.0e+00 | True |
| xgb_regularized | A_0 | True | True | True | 0.0e+00 | 0.0e+00 | True |
