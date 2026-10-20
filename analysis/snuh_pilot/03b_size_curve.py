# -*- coding: utf-8 -*-
"""Step 03b -- membership-inference exposure against training-set size (hypothesis H6), xgb family only.

For each variant and size m (2,000 / 5,000 / 10,000 / all training rows; /10 in quick mode) trains K shadow models
of that size on random subsets of the whole cohort (the attacker's models, cached in data/ckd_pilot/work/<ds>/sizecurve/),
then, per seed, one target model on a random subset of m training rows and audits it exactly as step 03 does
(loss-threshold, shadow-model attack with the first 16 shadows, online LiRA with all of them; balanced members /
non-members). Appends aggregates to out/<ds>/03b_size_curve_long.csv; step 06 turns them into the H6 table.

    python 03b_size_curve.py --dataset snuh [--variants xgb_krcp xgb_regularized] [--seeds 42 43]
"""
import argparse
import importlib.util
import os
import sys
import time
import zlib

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pilot_lib as L  # noqa: E402


def attack_module():
    """Reuse the attack functions of step 03 (file name starts with a digit, so load by path)."""
    spec = importlib.util.spec_from_file_location('attack03', os.path.join(HERE, '03_attack_audit.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sizes_for(n_train):
    base = [200, 500, 1000] if L.QUICK else [2000, 5000, 10000]
    return [m for m in base if m < n_train] + [n_train]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', choices=L.DATASETS, required=True)
    ap.add_argument('--variants', nargs='+', default=['xgb_krcp', 'xgb_regularized'])
    ap.add_argument('--seeds', nargs='+', type=int, default=None)
    a = ap.parse_args()
    if L.MODEL != 'xgb':
        print('size curve runs in the xgb family only (run_pilot.py --model xgb): skipped')
        return
    att = attack_module()
    X, y, split, aux, meta = L.load_matrix(a.dataset)
    n = len(y)
    train_idx = np.where(split == 'train')[0]
    val_idx = np.where(split == 'val')[0]
    out_csv = os.path.join(L.out_dir(a.dataset), '03b_size_curve_long.csv')
    done = set()
    if os.path.exists(out_csv):
        prev = pd.read_csv(out_csv)
        done = set(zip(prev['seed'], prev['variant'], prev['n_train']))
    K = L.k_lira()

    for variant in a.variants:
        for m in sizes_for(len(train_idx)):
            wd = L.work_dir(a.dataset, 'sizecurve', variant, str(m))
            for k in range(K):
                f = os.path.join(wd, f'shadow_{k:03d}.npz')
                if os.path.exists(f):
                    continue
                sseed = 20_000 + k + zlib.crc32(f'{variant}/size{m}'.encode()) % 1000
                idx = np.sort(np.random.default_rng(sseed).choice(n, m, replace=False))
                t0 = time.time()
                _, p = L.fit_predict(variant, X, y, idx, sseed)
                inmask = np.zeros(n, bool)
                inmask[idx] = True
                np.savez_compressed(f, inmask=inmask, p=p)
                print(f'  {variant:<16} n={m:>6,} shadow {k + 1:>3}/{K}  {time.time() - t0:4.0f}s', flush=True)
            z = [np.load(os.path.join(wd, f)) for f in sorted(os.listdir(wd)) if f.endswith('.npz')][:K]
            s_in = np.stack([q['inmask'] for q in z])
            s_p = np.stack([q['p'] for q in z]).astype(np.float32)

            for seed in (a.seeds or L.seeds()):
                if (seed, variant, m) in done:
                    continue
                rng = np.random.default_rng(seed * 7919 + m)
                members = np.sort(rng.choice(train_idx, m, replace=False))
                _, p = L.fit_predict(variant, X, y, members, seed)
                nonmem = np.setdiff1d(np.arange(n), members)
                m_eval = min(len(members), len(nonmem))
                rng2 = np.random.default_rng(seed * 1000 + m)
                ev = np.concatenate([rng2.choice(members, m_eval, replace=False), rng2.choice(nonmem, m_eval, replace=False)])
                lab = np.r_[np.ones(m_eval, int), np.zeros(m_eval, int)]
                scores = {
                    'loss': np.log(np.clip(np.where(y[ev] == 1, p[ev], 1 - p[ev]), 1e-7, 1)),
                    'shadow': att.shokri(s_in[:L.k_shokri()], s_p[:L.k_shokri()], y, p, ev, lab, seed),
                    'lira': att.lira(s_in, s_p, y, p, ev),
                }
                row = {'seed': seed, 'variant': variant, 'n_train': m, 'n_eval_each': m_eval,
                       'val_auroc': L.auc(y[val_idx], p[val_idx])}
                for key, s in scores.items():
                    row[f'{key}_auc'] = L.auc(lab, s)
                    row[f'{key}_tpr1'] = L.tpr_at_fpr(lab, s, 0.01)
                L.append_rows(out_csv, [row])
                print(f'  seed {seed} {variant:<16} n={m:>6,}  shadow {row["shadow_auc"]:.3f}  lira {row["lira_auc"]:.3f}', flush=True)
    print('done ->', os.path.relpath(out_csv, L.BASE))


if __name__ == '__main__':
    L.guard(main)
