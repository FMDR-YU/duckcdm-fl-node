# -*- coding: utf-8 -*-
"""Why is the federated plain model (no row or column sampling) identical to the pooled model on SynPUF but not on the eICU
hospitals? Offline diagnosis from the saved federated models and the site files; aggregates only.

For each cohort tag with a plain federated run (data/federated/<tag>/B1_s42/F_xgb_plain.model.json):
  1. retrain the central model locally on the pooled site rows with the parameters recorded in the run's JSON
     (same xgboost version, 4 threads) and check that it reproduces the run's central AUROC;
  2. compare predictions of F and the local central model on the common validation rows (Pearson r, max |diff|);
  3. compare the split thresholds of the two boosters: share of F's (feature, threshold) pairs that also occur in the central
     model, overall and by feature cardinality (at most max_bin distinct values, where a quantile sketch is exact, against more);
  4. describe the features: distinct values per feature, missing share, number of features above max_bin distinct values.
If the mismatches sit in high-cardinality features, the merged per-site quantile sketch of the federated histogram build is the
likely cause (the sketch over pooled rows and the merge of three site sketches choose different bin edges).

    python diag_plain_identity.py [--tags synpuf eicu_h3a eicu_h3b] [--seed 42] [--out out/diag_plain_identity.md]
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import pandas as pd
import xgboost as xgb

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(BASE, 'analysis', 'snuh_pilot'))
import pilot_lib as L  # noqa: E402


def site_frames(root):
    tr, va = [], []
    for d in sorted(glob.glob(os.path.join(glob.escape(root), 'site-*'))):
        tr.append(pd.read_parquet(os.path.join(d, 'train.parquet')))
        va.append(pd.read_parquet(os.path.join(d, 'valid.parquet')))
    return pd.concat(tr, ignore_index=True), pd.concat(va, ignore_index=True)


def splits(booster):
    df = booster.trees_to_dataframe()
    s = df[df.Feature != 'Leaf'][['Tree', 'Feature', 'Split']].copy()
    s['Split'] = s.Split.astype(float).round(6)
    return s


def auc(y, p):
    return L.auc(np.asarray(y), np.asarray(p))


def diagnose(tag, seed):
    ds = 'eicu' if tag.startswith('eicu') else tag
    jpath = os.path.join(HERE, 'out', tag, f'fl_B1_s{seed}_plain.json')
    root = os.path.join(BASE, 'data', 'federated', tag, f'B1_s{seed}')
    fpath = os.path.join(root, 'F_xgb_plain.model.json')
    if not (os.path.exists(jpath) and os.path.exists(fpath)):
        return [f'## {tag}', '', 'no plain run found', '']
    run = json.load(open(jpath, encoding='utf-8'))
    params = dict(run['params'])
    params['nthread'] = 4
    rounds = run['rounds']
    tr, va = site_frames(root)
    Xtr, ytr = tr.drop(columns=['y']), tr['y'].to_numpy()
    Xva, yva = va.drop(columns=['y']), va['y'].to_numpy()
    dtr, dva = xgb.DMatrix(Xtr, label=ytr), xgb.DMatrix(Xva, label=yva)
    A = xgb.train(params, dtr, num_boost_round=rounds)
    F = xgb.Booster(model_file=fpath)
    pa, pf = A.predict(dva), F.predict(dva)
    # a central model whose quantile sketch is built site by site and merged, as the federated build does:
    # approximated here by training on the pooled rows with the same max_bin (the exact merge is inside xgboost's federated
    # mode and cannot be reproduced offline), so this row only shows the local reproduction of the run's central model
    sa, sf = splits(A), splits(F)
    key = lambda d: set(zip(d.Feature, d.Split))  # noqa: E731
    ka, kf = key(sa), key(sf)
    card = Xtr.nunique(dropna=True)
    miss = Xtr.isna().mean()
    maxbin = int(params.get('max_bin', 256))
    hi = set(card[card > maxbin].index)
    sf['hi'] = sf.Feature.isin(hi)
    sf['in_A'] = [ (f, t) in ka for f, t in zip(sf.Feature, sf.Split)]
    by = sf.groupby('hi').in_A.agg(['mean', 'size'])
    first_tree_same = int((sa[sa.Tree == 0].reset_index(drop=True)[['Feature', 'Split']].equals(sf[sf.Tree == 0].reset_index(drop=True)[['Feature', 'Split']])))
    # on which tree does the first difference appear
    first_diff = None
    for t in range(rounds):
        a_t = sa[sa.Tree == t].reset_index(drop=True)[['Feature', 'Split']]
        f_t = sf[sf.Tree == t].reset_index(drop=True)[['Feature', 'Split']]
        if not a_t.equals(f_t):
            first_diff = t
            break
    md = [f'## {tag} (seed {seed}, plain: {rounds} rounds, max_bin {maxbin}, {len(Xtr.columns)} features)', '',
          f'- pooled training rows {L.cell(len(Xtr))}, common validation rows {L.cell(len(Xva))}',
          f'- central model of the run: AUROC {run["arms"]["A_x"]["auroc"]:.4f}; retrained locally (xgboost {xgb.__version__}): {auc(yva, pa):.4f}',
          f'- federated model of the run: AUROC {run["arms"]["F"]["auroc"]:.4f}; reloaded: {auc(yva, pf):.4f}',
          f'- predictions F against local central: Pearson r {np.corrcoef(pa, pf)[0, 1]:.4f}, mean |diff| {np.mean(np.abs(pa - pf)):.4f}, max |diff| {np.max(np.abs(pa - pf)):.4f}',
          f'- split nodes: central {len(sa):,}, federated {len(sf):,}; first tree identical: {"yes" if first_tree_same else "no"}; '
          f'first tree that differs: {first_diff if first_diff is not None else "none"}',
          f'- share of federated (feature, threshold) pairs that also occur in the central model: {sf.in_A.mean():.3f} overall; '
          + '; '.join(f'{"features with more than" if h else "features with at most"} {maxbin} distinct values: {r["mean"]:.3f} of {int(r["size"]):,} splits' for h, r in by.iterrows()),
          f'- features: median distinct values {int(card.median())}, {len(hi)} of {len(card)} features with more than {maxbin} distinct values, '
          f'{int((miss > 0).sum())} features with missing values (mean missing share {miss.mean():.3f}, max {miss.max():.3f})',
          '']
    return md


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tags', nargs='+', default=['synpuf', 'eicu_h3a', 'eicu_h3b'])
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--out', default=os.path.join(HERE, 'out', 'diag_plain_identity.md'))
    a = ap.parse_args()
    md = ['# Diagnosis: federated plain model against the pooled model', '',
          'Offline comparison of the saved federated model (FLARE histogram-based XGBoost, no row or column sampling) with a central model '
          'retrained on the pooled site rows with the same parameters. Aggregates only.', '']
    for t in a.tags:
        md += diagnose(t, a.seed)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, 'w', encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')
    print('\n'.join(md))


if __name__ == '__main__':
    main()
