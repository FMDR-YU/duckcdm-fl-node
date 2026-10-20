# -*- coding: utf-8 -*-
"""Step 05 -- Gate 3: escrow manifest, HMAC signature, and re-execution in a fresh process.

Escrow (stays in data/ckd_pilot/work/<ds>/gate3/): data hash, split hash, variant, seed, thread count,
library versions, Gate 1 artifact hashes, validation AUROC and a hash of the validation predictions.
The manifest digest is signed with HMAC-SHA256 using a local key (data/ckd_pilot/escrow_key.bin,
generated on first use, never written to out/). Re-execution runs this script again in a new Python
process (--reexec), which retrains from the manifest alone and checks: signature valid, data hash equal,
library versions equal, |dAUROC| <= 1e-4, max |dp| on validation rows. Writes out/<ds>/05_gate3.csv.

    python 05_gate3_escrow.py --dataset snuh [--seed 42] [--variant krcp|all] [--target A_0]    (default: every variant; done ones are skipped)
"""
import argparse
import hashlib
import hmac
import json
import os
import platform
import secrets
import subprocess
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilot_lib as L  # noqa: E402


def key():
    p = os.path.join(L.DATA_DIR, 'escrow_key.bin')
    if not os.path.exists(p):
        open(p, 'wb').write(secrets.token_bytes(32))
    return open(p, 'rb').read()


def versions():
    import sklearn, xgboost, lightgbm, catboost, numpy, pandas
    return {'python': platform.python_version(), 'numpy': numpy.__version__, 'pandas': pandas.__version__,
            'sklearn': sklearn.__version__, 'xgboost': xgboost.__version__, 'lightgbm': lightgbm.__version__,
            'catboost': catboost.__version__}


def digest(m):
    body = {k: v for k, v in m.items() if k not in ('digest', 'hmac')}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def retrain(ds, variant, seed, target):
    X, y, split, aux, meta = L.load_matrix(ds)
    train_idx = np.where(split == 'train')[0]
    idx = L.scenarios(train_idx, aux['stratum'].to_numpy(), seed)[target][0]
    _, p = L.fit_predict(variant, X, y, idx, seed)
    val = np.where(split == 'val')[0]
    return meta, p[val], y[val], hashlib.sha256(split.astype(str).tobytes()).hexdigest()


def reexec(manifest_path, result_path):
    m = json.load(open(manifest_path))
    sig_ok = hmac.compare_digest(m['hmac'], hmac.new(key(), digest(m).encode(), 'sha256').hexdigest())
    meta, pv, yv, split_h = retrain(m['dataset'], m['variant'], m['seed'], m['target'])
    ref = np.load(m['pred_file'])
    res = {'signature_valid': sig_ok, 'data_hash_equal': meta['data_sha256'] == m['data_sha256'],
           'split_hash_equal': split_h == m['split_sha256'], 'versions_equal': versions() == m['versions'],
           'threads_equal': L.N_THREADS == m['threads'],
           'abs_delta_auroc': abs(L.auc(yv, pv) - m['val_auroc']), 'max_abs_dp': float(np.max(np.abs(pv - ref)))}
    json.dump(res, open(result_path, 'w'))


def escrow_one(dataset, seed, variant, target, od):
    X, y, split, aux, meta = L.load_matrix(dataset)
    val = np.where(split == 'val')[0]
    tdir = L.work_dir(dataset, 'targets', str(seed), variant)
    p = np.load(os.path.join(tdir, f'{target}.p.npy'))[val]
    gd = L.work_dir(dataset, 'gate3', str(seed), variant, target)
    pred_file = os.path.join(gd, 'val_pred.npy'); np.save(pred_file, p)
    g1 = L.work_dir(dataset, 'gate1', str(seed), variant, target)
    artifacts = {f: hashlib.sha256(open(os.path.join(g1, f), 'rb').read()).hexdigest() for f in sorted(os.listdir(g1))}
    m = {'dataset': dataset, 'seed': seed, 'variant': variant, 'target': target,
         'data_sha256': meta['data_sha256'], 'split_sha256': hashlib.sha256(split.astype(str).tobytes()).hexdigest(),
         'threads': L.N_THREADS, 'quick': L.QUICK, 'versions': versions(), 'artifacts': artifacts,
         'val_auroc': L.auc(y[val], p), 'val_pred_sha256': hashlib.sha256(p.tobytes()).hexdigest(),
         'pred_file': pred_file}
    m['digest'] = digest(m)
    m['hmac'] = hmac.new(key(), m['digest'].encode(), 'sha256').hexdigest()
    mp = os.path.join(gd, 'escrow_manifest.json'); json.dump(m, open(mp, 'w'), indent=1)

    rp = os.path.join(gd, 'reexec_result.json')
    env = dict(os.environ)
    r = subprocess.run([sys.executable, os.path.abspath(__file__), '--reexec', mp, rp], env=env,
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(rp):
        sys.exit('re-execution failed (output suppressed)')
    res = json.load(open(rp))
    row = {'seed': seed, 'variant': variant, 'target': target, 'n_artifacts': len(artifacts),
           'manifest_digest': m['digest'][:16], **res,
           'gate3_pass': bool(res['signature_valid'] and res['data_hash_equal'] and res['abs_delta_auroc'] <= 1e-4)}
    L.append_rows(os.path.join(od, '05_gate3.csv'), [row])
    print(f"  gate3 {variant:16s} {'PASS' if row['gate3_pass'] else 'FAIL'}  |dAUROC| {res['abs_delta_auroc']:.1e}  max|dp| {res['max_abs_dp']:.1e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', choices=L.DATASETS)
    ap.add_argument('--seed', type=int, default=L.SEEDS[0])
    ap.add_argument('--variant', default='all',   # all = the central model of every variant of the family (federated models: see run_fl_xgb --reexec)
                    help="one variant (krcp, xgb_krcp, ...) or 'all' (default): Gate 3 for every variant of the active family")
    ap.add_argument('--target', default='A_0')
    ap.add_argument('--reexec', nargs=2, metavar=('MANIFEST', 'RESULT'))
    a = ap.parse_args()
    if a.reexec:
        return reexec(*a.reexec)

    od = L.out_dir(a.dataset)
    csv = os.path.join(od, '05_gate3.csv')
    have = set()
    if os.path.exists(csv):
        old = pd.read_csv(csv)
        have = set(zip(old.seed, old.variant, old.target))
    for v in (L.VARIANTS if a.variant == 'all' else [a.variant]):
        if (a.seed, v, a.target) in have:
            print(f'  gate3 {v:16s} already done')
            continue
        escrow_one(a.dataset, a.seed, v, a.target, od)
    print('done ->', os.path.relpath(csv, L.BASE))


if __name__ == '__main__':
    L.guard(main)
