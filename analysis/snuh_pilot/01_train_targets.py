# -*- coding: utf-8 -*-
"""Step 01 -- train the target models and score utility on the common validation set.

For every seed x variant x target (A, A', B1 sites, B2 sites) fits the ensemble on the target's rows,
stores the model, its member rows and P(y=1) for every row in data/ckd_pilot/work/<ds>/targets/
(restricted), and appends aggregate utility to out/<ds>/01_utility_long.csv. Combined models
(B1_comb, B2_comb) are the mean of their three site predictions. Resumable: finished targets are skipped.

With PILOT_MODEL=xgb (run_pilot.py --model xgb) every target is one XGBoost, and the federated global models
(F_B1, F_B2) trained by FLARE in analysis/federated are read from data/federated/ when their model files exist:
predictions come from the XGBoost JSON itself, members are the union of the three sites.

    python 01_train_targets.py --dataset snuh [--variants krcp leaky regularized] [--seeds 42 43]
"""
import argparse
import os
import shutil
import sys
import time

import joblib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilot_lib as L  # noqa: E402


def federated_preds(ds, variant, seed, fname, parts, sc, X, wd):
    """P(y=1) of the FLARE global model on every row, read from the XGBoost JSON the federated run left in
    data/federated/ (no pickle). Returns None when this variant has no federated model."""
    if not L.is_xgb(variant):
        return None
    src = L.fed_model_path(ds, fname[len('F_'):], seed, variant)
    if not os.path.exists(src):
        return None
    f_p = os.path.join(wd, f'{fname}.p.npy')
    if not os.path.exists(f_p) or os.path.getmtime(src) > os.path.getmtime(f_p):
        import xgboost as xgb
        booster = xgb.Booster()
        booster.load_model(src)
        np.save(f_p, booster.predict(xgb.DMatrix(X)).astype(np.float32))
        np.save(os.path.join(wd, f'{fname}.members.npy'), np.unique(np.concatenate([sc[q][0] for q in parts])))
        shutil.copyfile(src, os.path.join(wd, f'{fname}.model.json'))
        print(f'  seed {seed} {variant:<11} {fname:<9} federated model file', flush=True)
    return np.load(f_p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', choices=L.DATASETS, required=True)
    ap.add_argument('--variants', nargs='+', default=list(L.VARIANTS))
    ap.add_argument('--seeds', nargs='+', type=int, default=None)
    a = ap.parse_args()

    X, y, split, aux, meta = L.load_matrix(a.dataset)
    train_idx = np.where(split == 'train')[0]
    val_idx = np.where(split == 'val')[0]
    yv = y[val_idx]
    out_csv = os.path.join(L.out_dir(a.dataset), '01_utility_long.csv')
    done = set()
    if os.path.exists(out_csv):
        import pandas as pd
        prev = pd.read_csv(out_csv)
        done = set(zip(prev['seed'], prev['variant'], prev['target']))

    for seed in (a.seeds or L.seeds()):
        sc = L.scenarios(train_idx, aux['stratum'].to_numpy(), seed)
        for variant in a.variants:
            wd = L.work_dir(a.dataset, 'targets', str(seed), variant)
            preds = {}
            for name, (idx, size_class) in sc.items():
                f_p = os.path.join(wd, f'{name}.p.npy')
                if not os.path.exists(f_p):
                    t0 = time.time()
                    model, p = L.fit_predict(variant, X, y, idx, seed)
                    joblib.dump(model, os.path.join(wd, f'{name}.joblib'))
                    np.save(os.path.join(wd, f'{name}.members.npy'), idx)
                    np.save(f_p, p)
                    print(f'  seed {seed} {variant:<11} {name:<9} n={L.cell(len(idx))}  {time.time() - t0:5.0f}s', flush=True)
                preds[name] = np.load(f_p)
            for comb, parts in L.COMBINED.items():
                preds[comb] = np.mean([preds[q] for q in parts], axis=0).astype(np.float32)
                np.save(os.path.join(wd, f'{comb}.p.npy'), preds[comb])
            for fname, parts in L.FEDERATED.items():   # federated global model (xgb family, if FLARE has produced it)
                pf = federated_preds(a.dataset, variant, seed, fname, parts, sc, X, wd)
                if pf is not None:
                    preds[fname] = pf

            rows = []
            for name, p in preds.items():
                if (seed, variant, name) in done:
                    continue
                u = L.utility(yv, p[val_idx])
                parts = L.COMBINED.get(name) or L.FEDERATED.get(name)
                r = {'seed': seed, 'variant': variant, 'target': name,
                     'n_train': len(sc[name][0]) if name in sc else sum(len(sc[q][0]) for q in parts), **u}
                if parts:   # combined and federated: paired bootstrap vs central model (non-inferiority, IRB H3 / H5)
                    lo, hi = L.paired_boot_delta(yv, p[val_idx], preds['A_0'][val_idx], n=200 if L.QUICK else 1000, seed=seed)
                    r.update(delta_auc_vs_A=u['auroc'] - L.auc(yv, preds['A_0'][val_idx]), delta_lo=lo, delta_hi=hi)
                rows.append(r)
            if rows:
                L.append_rows(out_csv, rows)
    print('done ->', os.path.relpath(out_csv, L.BASE))


if __name__ == '__main__':
    L.guard(main)
