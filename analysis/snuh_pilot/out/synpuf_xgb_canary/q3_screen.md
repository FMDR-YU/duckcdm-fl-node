# Exploratory: predicting the tail exposure of a cell from cheap indicators

141 cells, 47 configurations. Target: log10 of the canary TPR at 1% FPR (SD 0.49). Each configuration, with all its sizes, is held out in turn. Error = absolute error in log10 units; the analysis plan calls a median error above 0.15 "does not transfer" (that rule is for transfer to another cohort, which this table does not test).

| predictor | model | median error | 90th percentile | R2 |
|---|---|---|---|---|
| constant (median of the other cells) | - | 0.379 | 0.778 | 0.00 |
| training size only | ridge | 0.384 | 0.776 | -0.03 |
| structure (settings and size) | ridge | 0.162 | 0.490 | 0.71 |
| structure (settings and size) | gbm | 0.134 | 0.289 | 0.86 |
| structure + leaf support | ridge | 0.151 | 0.410 | 0.68 |
| structure + leaf support | gbm | 0.150 | 0.350 | 0.82 |
| AUROC gap | ridge | 0.271 | 0.518 | 0.57 |
| shadow-model AUC (release rule) | ridge | 0.217 | 0.532 | 0.56 |
| LiRA TPR@1%FPR (ordinary rows) | ridge | 0.083 | 0.238 | 0.92 |
