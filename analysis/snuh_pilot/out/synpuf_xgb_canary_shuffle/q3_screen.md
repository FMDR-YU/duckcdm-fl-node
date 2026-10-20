# Exploratory: predicting the tail exposure of a cell from cheap indicators

141 cells, 47 configurations. Target: log10 of the canary TPR at 1% FPR (SD 0.45). Each configuration, with all its sizes, is held out in turn. Error = absolute error in log10 units; the analysis plan calls a median error above 0.15 "does not transfer" (that rule is for transfer to another cohort, which this table does not test).

| predictor | model | median error | 90th percentile | R2 |
|---|---|---|---|---|
| constant (median of the other cells) | - | 0.357 | 0.702 | 0.00 |
| training size only | ridge | 0.368 | 0.743 | -0.04 |
| structure (settings and size) | ridge | 0.138 | 0.458 | 0.68 |
| structure (settings and size) | gbm | 0.131 | 0.278 | 0.86 |
| structure + leaf support | ridge | 0.149 | 0.382 | 0.67 |
| structure + leaf support | gbm | 0.117 | 0.324 | 0.83 |
| AUROC gap | ridge | 0.187 | 0.439 | 0.66 |
| shadow-model AUC (release rule) | ridge | 0.205 | 0.476 | 0.62 |
| LiRA TPR@1%FPR (ordinary rows) | ridge | 0.080 | 0.208 | 0.92 |
