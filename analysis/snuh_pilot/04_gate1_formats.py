# -*- coding: utf-8 -*-
"""Step 04 -- Gate 1: export each ensemble to formats that load without running code, reload it
without pickle, and check the predictions are unchanged. Also audits leaf sizes (people per leaf).

Export per model: imputer medians (JSON), XGBoost (JSON), LightGBM (text), CatBoost (CBM),
RandomForest (JSON of every tree's split feature/threshold/children/leaf values), voting weights (JSON).
All formats are data only; the reload path never calls pickle/joblib/skops. (skops was the first choice
for the forest but cannot import here: the local scikit-learn 1.8.0 install carries a stray
sklearn/callback package from a development build that breaks skops' estimator scan.) Checks max |dp| against the pipeline on the validation rows.
Exported files stay in data/ckd_pilot/work/<ds>/gate1/ (models trained on restricted data are not
moved anywhere). Writes out/<ds>/04_gate1.csv and out/<ds>/04_leaf_audit.csv (aggregates).

xgb family (PILOT_MODEL=xgb): the export is one XGBoost JSON. The federated global models (F_B1, F_B2) are
already XGBoost JSON files written by FLARE; they are reloaded from that file and compared with the stored
predictions, which is the Gate 1 check on the artifact that actually leaves the platform.

    python 04_gate1_formats.py --dataset snuh [--seed 42]
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilot_lib as L  # noqa: E402

TARGETS = ['A_0', 'B1_0']


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def rf_to_json(rf, path):
    trees = []
    for t in rf.estimators_:
        tr = t.tree_
        v = tr.value[:, 0, :]
        trees.append({'left': tr.children_left.tolist(), 'right': tr.children_right.tolist(),
                      'feature': tr.feature.tolist(), 'threshold': tr.threshold.tolist(),
                      'p1': (v[:, 1] / v.sum(1)).tolist()})
    json.dump({'classes': rf.classes_.tolist(), 'trees': trees}, open(path, 'w'))


def rf_predict_json(spec, A):
    """sklearn compares float32(X) <= threshold and goes left; leaf class-1 share averaged over trees."""
    A = np.asarray(A, np.float32)
    out = np.zeros(len(A))
    rows = np.arange(len(A))
    for t in spec['trees']:
        left, right = np.asarray(t['left']), np.asarray(t['right'])
        feat, thr, p1 = np.asarray(t['feature']), np.asarray(t['threshold']), np.asarray(t['p1'])
        node = np.zeros(len(A), int)
        while True:
            internal = left[node] != -1
            if not internal.any():
                break
            n_ = node[internal]
            go_left = A[rows[internal], feat[n_]] <= thr[n_]
            node[internal] = np.where(go_left, left[n_], right[n_])
        out += p1[node]
    return out / len(spec['trees'])


def export(model, d):
    imp, ens = model.named_steps['imp'], model.named_steps['ens']
    est = dict(ens.named_estimators_)
    os.makedirs(d, exist_ok=True)
    json.dump({'medians': imp.statistics_.tolist(), 'weights': [1, 1, 1, 1], 'order': ['xgb', 'lgb', 'cat', 'rf']},
              open(os.path.join(d, 'ensemble.json'), 'w'))
    est['xgb'].save_model(os.path.join(d, 'xgb.json'))
    est['lgb'].booster_.save_model(os.path.join(d, 'lgb.txt'))
    est['cat'].save_model(os.path.join(d, 'cat.cbm'))
    rf_to_json(est['rf'], os.path.join(d, 'rf.json'))
    return {f: sha(os.path.join(d, f)) for f in sorted(os.listdir(d))}


def load_native(d):
    import xgboost as xgb
    import lightgbm as lgb
    from catboost import CatBoostClassifier
    cfg = json.load(open(os.path.join(d, 'ensemble.json')))
    b = xgb.Booster(); b.load_model(os.path.join(d, 'xgb.json'))
    g = lgb.Booster(model_file=os.path.join(d, 'lgb.txt'))
    c = CatBoostClassifier(); c.load_model(os.path.join(d, 'cat.cbm'))
    rf = json.load(open(os.path.join(d, 'rf.json')))
    med = np.asarray(cfg['medians'])
    keep = ~np.isnan(med)      # SimpleImputer drops a column that is all missing at fit (BMI in the SNUH extract): the members never saw it

    def predict(X):
        A = np.asarray(X, float)[:, keep]
        A = np.where(np.isnan(A), med[keep], A)
        ps = [b.predict(xgb.DMatrix(A)), g.predict(A), c.predict_proba(A)[:, 1], rf_predict_json(rf, A)]
        return np.average(ps, axis=0, weights=cfg['weights'])
    return predict, ['json', 'text', 'cbm', 'json']


def export_xgb(model, d):
    os.makedirs(d, exist_ok=True)
    model.save_model(os.path.join(d, 'xgb.json'))
    return {f: sha(os.path.join(d, f)) for f in sorted(os.listdir(d))}


def load_native_xgb(d):
    import xgboost as xgb
    b = xgb.Booster()
    b.load_model(os.path.join(d, 'xgb.json'))

    def predict(X):
        return b.predict(xgb.DMatrix(X))     # DataFrame keeps the feature names the model was saved with
    return predict, ['json']


def leaf_audit_xgb(d, Xtr):
    """Same share of small leaves for the single XGBoost, read back from the exported JSON."""
    import xgboost as xgb
    b = xgb.Booster()
    b.load_model(os.path.join(d, 'xgb.json'))
    M = np.asarray(b.predict(xgb.DMatrix(Xtr), pred_leaf=True)).reshape(len(Xtr), -1)
    small = tot = trees_small = 0
    for j in range(M.shape[1]):
        cnt = np.bincount(M[:, j].astype(np.int64))
        cnt = cnt[cnt > 0]
        small += (cnt < L.MIN_CELL).sum(); tot += len(cnt); trees_small += (cnt < L.MIN_CELL).any()
    return {'xgb': (small / tot, trees_small / M.shape[1])}


def leaf_audit(model, Xtr):
    """Share of leaves (and of trees) with fewer than 11 training people, per component."""
    imp, ens = model.named_steps['imp'], model.named_steps['ens']
    A = imp.transform(Xtr)
    est = dict(ens.named_estimators_)
    import xgboost as xgb
    leaves = {
        'xgb': est['xgb'].get_booster().predict(xgb.DMatrix(A), pred_leaf=True),
        'lgb': est['lgb'].predict(A, pred_leaf=True),
        'cat': np.asarray(est['cat'].calc_leaf_indexes(A)),
        'rf': est['rf'].apply(A),
    }
    out = {}
    for k, M in leaves.items():
        M = np.asarray(M).reshape(len(A), -1)
        small = tot = trees_small = 0
        for j in range(M.shape[1]):
            cnt = np.bincount(M[:, j].astype(np.int64))
            cnt = cnt[cnt > 0]
            small += (cnt < L.MIN_CELL).sum(); tot += len(cnt); trees_small += (cnt < L.MIN_CELL).any()
        out[k] = (small / tot, trees_small / M.shape[1])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', choices=L.DATASETS, required=True)
    ap.add_argument('--seed', type=int, default=L.SEEDS[0])
    a = ap.parse_args()
    X, y, split, aux, meta = L.load_matrix(a.dataset)
    val = np.where(split == 'val')[0]
    g_rows, l_rows = [], []
    for variant in L.VARIANTS:
        tdir = L.work_dir(a.dataset, 'targets', str(a.seed), variant)
        targets = TARGETS + ([f for f in L.FEDERATED if os.path.exists(os.path.join(tdir, f'{f}.model.json'))]
                             if L.is_xgb(variant) else [])
        for name in targets:
            d = L.work_dir(a.dataset, 'gate1', str(a.seed), variant, name)
            if name in L.FEDERATED:                         # the FLARE model file is the exported artifact
                shutil.copyfile(os.path.join(tdir, f'{name}.model.json'), os.path.join(d, 'xgb.json'))
                hashes = {f: sha(os.path.join(d, f)) for f in sorted(os.listdir(d))}
                predict, untrusted = load_native_xgb(d)
                p_ref = np.load(os.path.join(tdir, f'{name}.p.npy'))[val]
                leaves = lambda Xm: leaf_audit_xgb(d, Xm)   # noqa: E731
            else:
                src = os.path.join(tdir, f'{name}.joblib')
                if not os.path.exists(src):
                    sys.exit(f'missing {a.seed}/{variant}/{name}; run 01_train_targets.py first')
                model = joblib.load(src)
                p_ref = model.predict_proba(X.iloc[val])[:, 1]
                if L.is_xgb(variant):
                    hashes = export_xgb(model, d)
                    predict, untrusted = load_native_xgb(d)
                    leaves = lambda Xm: leaf_audit_xgb(d, Xm)   # noqa: E731
                else:
                    hashes = export(model, d)
                    predict, untrusted = load_native(d)
                    leaves = lambda Xm, m=model: leaf_audit(m, Xm)   # noqa: E731
            p_nat = predict(X.iloc[val])
            g_rows.append({'seed': a.seed, 'variant': variant, 'target': name,
                           'max_abs_dp': float(np.max(np.abs(p_ref - p_nat))),
                           'label_agree': float(np.mean((p_ref >= 0.5) == (p_nat >= 0.5))),
                           'bytes_total': sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d)),
                           'formats': ';'.join(untrusted), 'pickle_used_on_load': False,
                           'files': ';'.join(f'{k}:{v[:12]}' for k, v in hashes.items())})
            members = np.load(os.path.join(tdir, f'{name}.members.npy'))
            for comp, (leaf_share, tree_share) in leaves(X.iloc[members]).items():
                l_rows.append({'seed': a.seed, 'variant': variant, 'target': name, 'component': comp,
                               'share_leaves_lt11': leaf_share, 'share_trees_with_leaf_lt11': tree_share})
            print(f'  {variant:<11} {name:<5} max|dp| {g_rows[-1]["max_abs_dp"]:.2e}', flush=True)
    od = L.out_dir(a.dataset)
    pd.DataFrame(g_rows).to_csv(os.path.join(od, '04_gate1.csv'), index=False)
    pd.DataFrame(l_rows).to_csv(os.path.join(od, '04_leaf_audit.csv'), index=False)
    print('done ->', os.path.relpath(os.path.join(od, '04_gate1.csv'), L.BASE))


if __name__ == '__main__':
    L.guard(main)
