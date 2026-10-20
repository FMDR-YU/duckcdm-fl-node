# -*- coding: utf-8 -*-
"""Step 02 -- shadow models for the membership-inference audit (attacker's models).

For each variant and each training-set size class (full, site, b2_0..b2_2) trains K shadow models,
each on a random subset of that size drawn from the whole cohort (train + val), so every person is
"in" some shadows and "out" of others (online LiRA, Carlini et al. 2022). The same shadows serve the
shadow-model attack (first 16) and LiRA (all 64) for every seed, because the attacker's models do not
depend on which split the target used. Stores in-mask + P(y=1) for every row (restricted work dir).
Resumable: existing shadows are skipped, so it can be stopped and restarted.

    python 02_train_shadows.py --dataset snuh [--variants krcp] [--classes full site] [--k 64]
"""
import argparse
import os
import sys
import time
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilot_lib as L  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', choices=L.DATASETS, required=True)
    ap.add_argument('--variants', nargs='+', default=list(L.VARIANTS))
    ap.add_argument('--classes', nargs='+', default=None)
    ap.add_argument('--k', type=int, default=None)
    a = ap.parse_args()

    X, y, split, aux, meta = L.load_matrix(a.dataset)
    n_train = int((split == 'train').sum())
    classes = L.size_classes(n_train)
    K = a.k or L.k_lira()
    total = 0
    for variant in a.variants:
        for cname in (a.classes or list(classes)):
            m = classes[cname]
            wd = L.work_dir(a.dataset, 'shadows', variant, cname)
            for k in range(K):
                f = os.path.join(wd, f'shadow_{k:03d}.npz')
                if os.path.exists(f):
                    continue
                seed = 10_000 + k + zlib.crc32(f'{variant}/{cname}'.encode()) % 1000
                rng = np.random.default_rng(seed)
                idx = np.sort(rng.choice(len(y), m, replace=False))
                t0 = time.time()
                _, p = L.fit_predict(variant, X, y, idx, seed)
                inmask = np.zeros(len(y), bool); inmask[idx] = True
                np.savez_compressed(f, inmask=inmask, p=p)
                total += 1
                print(f'  {variant:<11} {cname:<5} shadow {k + 1:>3}/{K}  n={L.cell(m)}  {time.time() - t0:5.0f}s', flush=True)
    print(f'done -- {total} new shadows')


if __name__ == '__main__':
    L.guard(main)
