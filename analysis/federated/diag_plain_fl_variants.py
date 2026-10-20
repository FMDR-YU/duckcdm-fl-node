# -*- coding: utf-8 -*-
"""Confirmation experiment for diag_plain_identity.py (runs inside the FLARE image): train the plain federated model on
variants of the site files and compare with the pooled central model trained on the same rows.

  variant 'asis'     the site files as they are (reproduces the non-identity on eICU)
  variant 'imputed'  every missing value replaced by the pooled training median of its feature (same rows otherwise)
  variant 'maxbin'   as-is files, max_bin raised from 256 to 1024

If 'imputed' gives an identical model (max |pred diff| ~ 0, split sets equal), missing values in the federated histogram
build are the cause; if 'maxbin' closes the gap instead, the merged quantile sketch is. Aggregates only; the variant site
files are written under data/federated/<tag>_diag/ and can be deleted.

    (in the image) python diag_plain_fl_variants.py --tag eicu_h3a --seed 42 --variants asis imputed maxbin
"""
import argparse
import glob
import json
import os
import shutil
import sys
import time

import numpy as np
import pandas as pd
import xgboost as xgb

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(BASE, 'analysis', 'snuh_pilot'))
import pilot_lib as pl  # noqa: E402
from run_fl_xgb import run_federated  # noqa: E402

N_SITES = 3


def splits(b):
    df = b.trees_to_dataframe()
    s = df[df.Feature != 'Leaf']
    return set(zip(s.Feature, s.Split.astype(float).round(6)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', default='eicu_h3a')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--variants', nargs='+', default=['asis', 'imputed', 'maxbin'])
    a = ap.parse_args()
    run = json.load(open(os.path.join(HERE, 'out', a.tag, f'fl_B1_s{a.seed}_plain.json'), encoding='utf-8'))
    base_params = dict(run['params'])
    rounds = run['rounds']
    src = os.path.join(pl.FED_ROOT, a.tag, f'B1_s{a.seed}')
    tr = pd.concat([pd.read_parquet(os.path.join(src, f'site-{k + 1}', 'train.parquet')) for k in range(N_SITES)], ignore_index=True)
    va = pd.concat([pd.read_parquet(os.path.join(src, f'site-{k + 1}', 'valid.parquet')) for k in range(N_SITES)], ignore_index=True)
    med = tr.drop(columns=['y']).median()
    out = {'tag': a.tag, 'seed': a.seed, 'rounds': rounds, 'variants': {}}
    ws_root = os.path.join(pl.FED_ROOT, 'workspace')
    for v in a.variants:
        params = dict(base_params)
        folder = os.path.join(pl.FED_ROOT, f'{a.tag}_diag', f'{v}_s{a.seed}')
        shutil.rmtree(folder, ignore_errors=True)
        for k in range(N_SITES):
            d = os.path.join(folder, f'site-{k + 1}')
            os.makedirs(d, exist_ok=True)
            for part in ('train', 'valid'):
                df = pd.read_parquet(os.path.join(src, f'site-{k + 1}', f'{part}.parquet'))
                if v == 'imputed':
                    df = df.fillna(med)
                df.to_parquet(os.path.join(d, f'{part}.parquet'), index=False)
        if v == 'maxbin':
            params['max_bin'] = 1024
        trv, vav = (tr.fillna(med), va.fillna(med)) if v == 'imputed' else (tr, va)
        dtr = xgb.DMatrix(trv.drop(columns=['y']), label=trv['y'].to_numpy())
        dva = xgb.DMatrix(vav.drop(columns=['y']), label=vav['y'].to_numpy())
        A = xgb.train(params, dtr, num_boost_round=rounds)
        t0 = time.time()
        models = run_federated(a, rounds, params, folder, ws_root, f'diag_{a.tag}_{v}_s{a.seed}')
        F = xgb.Booster()
        F.load_model(models[0])
        pa, pf = A.predict(dva), F.predict(dva)
        sa, sf = splits(A), splits(F)
        res = {'seconds_fl': round(time.time() - t0, 1), 'auroc_A': pl.auc(vav['y'].to_numpy(), pa), 'auroc_F': pl.auc(vav['y'].to_numpy(), pf),
               'pearson': float(np.corrcoef(pa, pf)[0, 1]), 'max_abs_pred_diff': float(np.max(np.abs(pa - pf))),
               'mean_abs_pred_diff': float(np.mean(np.abs(pa - pf))), 'splits_A': len(sa), 'splits_F': len(sf),
               'share_F_splits_in_A': float(len(sa & sf) / max(len(sf), 1)), 'max_bin': params.get('max_bin', 256)}
        out['variants'][v] = res
        print(v, json.dumps(res))
    op = os.path.join(HERE, 'out', a.tag, f'diag_plain_fl_variants_s{a.seed}.json')
    json.dump(out, open(op, 'w', encoding='utf-8'), indent=1)
    print('wrote', op)


if __name__ == '__main__':
    main()
