# Diagnosis: federated plain model against the pooled model

Offline comparison of the saved federated model (FLARE histogram-based XGBoost, no row or column sampling) with a central model retrained on the pooled site rows with the same parameters. Aggregates only.

## synpuf (seed 42, plain: 100 rounds, max_bin 256, 27 features)

- pooled training rows 19,746, common validation rows 8,463
- central model of the run: AUROC 0.8963; retrained locally (xgboost 3.2.0): 0.8963
- federated model of the run: AUROC 0.8963; reloaded: 0.8963
- predictions F against local central: Pearson r 1.0000, mean |diff| 0.0000, max |diff| 0.0000
- split nodes: central 3,861, federated 3,861; first tree identical: yes; first tree that differs: none
- share of federated (feature, threshold) pairs that also occur in the central model: 1.000 overall; features with at most 256 distinct values: 1.000 of 2,023 splits; features with more than 256 distinct values: 1.000 of 1,838 splits
- features: median distinct values 13, 5 of 27 features with more than 256 distinct values, 0 features with missing values (mean missing share 0.000, max 0.000)

## eicu_h3a (seed 42, plain: 100 rounds, max_bin 256, 47 features)

- pooled training rows 7,868, common validation rows 3,374
- central model of the run: AUROC 0.9035; retrained locally (xgboost 3.2.0): 0.9035
- federated model of the run: AUROC 0.9086; reloaded: 0.9086
- predictions F against local central: Pearson r 0.9795, mean |diff| 0.0150, max |diff| 0.2582
- split nodes: central 3,305, federated 3,245; first tree identical: yes; first tree that differs: 1
- share of federated (feature, threshold) pairs that also occur in the central model: 0.849 overall; features with at most 256 distinct values: 0.944 of 1,896 splits; features with more than 256 distinct values: 0.715 of 1,349 splits
- features: median distinct values 13, 10 of 47 features with more than 256 distinct values, 27 features with missing values (mean missing share 0.161, max 0.855)

## eicu_h3b (seed 42, plain: 100 rounds, max_bin 256, 47 features)

- pooled training rows 6,408, common validation rows 2,748
- central model of the run: AUROC 0.8962; retrained locally (xgboost 3.2.0): 0.8962
- federated model of the run: AUROC 0.8999; reloaded: 0.8999
- predictions F against local central: Pearson r 0.9810, mean |diff| 0.0159, max |diff| 0.2702
- split nodes: central 3,142, federated 3,301; first tree identical: yes; first tree that differs: 3
- share of federated (feature, threshold) pairs that also occur in the central model: 0.829 overall; features with at most 256 distinct values: 0.929 of 1,835 splits; features with more than 256 distinct values: 0.705 of 1,466 splits
- features: median distinct values 13, 11 of 47 features with more than 256 distinct values, 27 features with missing values (mean missing share 0.151, max 0.706)

## Confirmation in the FLARE image (diag_plain_fl_variants.py, eicu_h3a, seed 42; out/eicu_h3a/diag_plain_fl_variants_s42.json)

| variant | max_bin | AUROC A / F | Pearson r | max abs pred diff | share of F split pairs in A |
|---|---|---|---|---|---|
| as-is | 256 | 0.9035 / 0.9086 | 0.9795 | 0.258 | 0.726 |
| missing values imputed (pooled medians) | 256 | 0.9053 / 0.9042 | 0.9765 | 0.322 | 0.753 |
| as-is, finer sketch | 1024 | 0.9030 / 0.9030 | 1.0000 | 1.2e-07 | 1.000 |

Conclusion: the quantile sketch is the cause. At 256 bins the bin edges merged from three hospitals of different case mix differ from
the pooled sketch; at 1,024 bins the federated and pooled models are identical (the same level of agreement as SynPUF, whose random
virtual sites give the same sketch at 256 bins). Missing values play no role. The intercept (base_score) is identical in all runs.

