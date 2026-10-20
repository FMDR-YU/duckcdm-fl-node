# -*- coding: utf-8 -*-
"""Exploratory: can cheap indicators predict the tail exposure of a cell?

Leave-one-configuration-out prediction of log10(canary TPR at 1% FPR) from (a) training size, (b) the structural settings of the
model (depth, rounds, learning rate, minimum child weight, L2, sampling), (c) the average-AUC quantity of the pilot's release rule
(shadow-model AUC), (d) the member / non-member AUROC gap and (e) the ordinary-row LiRA TPR. All sizes of one configuration are held
out together. Aggregates only: reads the cells of canary_benchmark.py and writes q3_screen.md next to them.

    python canary_screen.py --dataset synpuf [--canary-type flip|shuffle]

This is a development-data feasibility check (one cohort, one model family). Transfer to another cohort is the analysis plan's
leave-one-dataset-out question and is not answered here.
"""
import argparse
import glob
import os
import sys
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('PILOT_MODEL', 'xgb')
import pilot_lib as L  # noqa: E402

PARAMS = ['depth', 'rounds', 'lr', 'mcw', 'lam', 'subsample', 'colsample']
TRANSFER_LIMIT = 0.15          # analysis plan v2: a median transfer error above this (log10 TPR) means "does not transfer"


def features(df, kind):
    F = pd.DataFrame({'depth': df.depth, 'log_rounds': np.log10(df.rounds), 'log_lr': np.log10(df.lr), 'mcw': df.mcw, 'lam': df.lam,
                      'subsample': df.subsample, 'colsample': df.colsample, 'log_n': np.log10(df.n)})
    return {'training size only': F[['log_n']],
            'structure (settings and size)': F,
            'structure + leaf support': F.assign(leaf=df.leaf_lt11),
            'AUROC gap': pd.DataFrame({'a': df.auc_gap}),
            'shadow-model AUC (release rule)': pd.DataFrame({'a': df.shadow_auc}),
            'LiRA TPR@1%FPR (ordinary rows)': pd.DataFrame({'a': np.log10(df.lira_tpr1)})}[kind]


def screen(df):
    """-> markdown lines. df needs the parameter columns, n, shadow_auc, auc_gap, leaf_lt11, lira_tpr1 and canary_tpr1."""
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.linear_model import RidgeCV
    from sklearn.model_selection import LeaveOneGroupOut
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    warnings.filterwarnings('ignore')
    # sorted, so that the row-sampling of the boosted trees does not depend on the order of the cell files
    df = df.drop_duplicates(['config', 'n'], keep='last').sort_values(['config', 'n']).reset_index(drop=True)
    y = np.log10(df.canary_tpr1.to_numpy(float))
    g = df.config.to_numpy()
    base = np.abs(y - np.median(y))
    md = ['# Exploratory: predicting the tail exposure of a cell from cheap indicators', '',
          f'{len(df)} cells, {len(np.unique(g))} configurations. Target: log10 of the canary TPR at 1% FPR (SD {y.std():.2f}). Each configuration, with all its sizes, '
          f'is held out in turn. Error = absolute error in log10 units; the analysis plan calls a median error above {TRANSFER_LIMIT} "does not transfer" '
          f'(that rule is for transfer to another cohort, which this table does not test).', '',
          '| predictor | model | median error | 90th percentile | R2 |', '|---|---|---|---|---|',
          f'| constant (median of the other cells) | - | {np.median(base):.3f} | {np.percentile(base, 90):.3f} | 0.00 |']
    makers = {'ridge': lambda: make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 2, 20))),
              'gbm': lambda: GradientBoostingRegressor(n_estimators=150, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=0)}
    for kind in ('training size only', 'structure (settings and size)', 'structure + leaf support', 'AUROC gap', 'shadow-model AUC (release rule)',
                 'LiRA TPR@1%FPR (ordinary rows)'):
        X = features(df, kind)
        for name, mk in makers.items():
            if X.shape[1] == 1 and name == 'gbm':
                continue
            pred = np.zeros(len(y))
            for tr, te in LeaveOneGroupOut().split(X, y, g):
                m = mk()
                m.fit(X.iloc[tr], y[tr])
                pred[te] = m.predict(X.iloc[te])
            e = np.abs(pred - y)
            md.append(f'| {kind} | {name} | {np.median(e):.3f} | {np.percentile(e, 90):.3f} | {1 - np.sum((pred - y) ** 2) / np.sum((y - y.mean()) ** 2):.2f} |')
    return md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', default='synpuf')
    ap.add_argument('--canary-type', choices=['flip', 'shuffle'], default='flip')
    a = ap.parse_args()
    od = L.out_dir(a.dataset) + '_canary' + ('' if a.canary_type == 'flip' else '_' + a.canary_type)
    fs = sorted(glob.glob(os.path.join(glob.escape(od), 'canary_cells*.csv')))
    if not fs:
        sys.exit(f'no canary_cells*.csv in {od}')
    df = pd.concat([pd.read_csv(f) for f in fs])
    missing = [c for c in PARAMS if c not in df or df[c].isna().any()]
    if missing:
        sys.exit(f'cells without the setting columns {missing}: re-run canary_benchmark.py (rows written before 2026-10-11 lack them)')
    md = screen(df)
    open(os.path.join(od, 'q3_screen.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    print('\n'.join(md))


if __name__ == '__main__':
    L.guard(main)
