# -*- coding: utf-8 -*-
"""Canary benchmark: release rules against ground-truth leakage.

For a grid of XGBoost configurations and training sizes, many models are trained on random subsets of the cohort plus a
random half of a pool of canaries. A canary is a real row with its label flipped, so a model can only fit it by memorising.
Because each model includes each canary with probability 1/2, the true membership of every canary is known and a
leave-one-model-out likelihood-ratio attack (LiRA) on the canaries measures the exposure that a release rule should detect.
For a few models per cell the usual audit quantities are computed on the ordinary rows: shadow-model attack AUC (the release
rule of the pilot, threshold 0.55), LiRA on ordinary rows, the share of leaves supported by fewer than 11 training rows, and
the member / non-member AUROC gap. summarize() then asks how well each rule separates exposed from unexposed cells
(threshold-free AUC, prescribed thresholds, thresholds calibrated on the development cells, cost of a miss, attacker precision).

    python canary_benchmark.py --dataset synpuf --configs krcp leaky --sizes 5000 19746      (appends to out/<ds>_canary/canary_cells.csv)
    python canary_benchmark.py --dataset synpuf --summarize [--tau 0.10] [--boot 2000]   (writes canary_summary.md, canary_thresholds.json)

Public or synthetic data only unless the caller is allowed to run it on the study data; only aggregates are written.
"""
import argparse
import importlib.util
import json
import os
import sys
import time
import warnings
import zlib

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('PILOT_MODEL', 'xgb')
import pilot_lib as L  # noqa: E402

N_CANARY = 400          # canary pool; each model contains a random half
M_MODELS = 48           # models per cell
T_TARGETS = 6           # models per cell on which the ordinary-row audit is computed
EXPOSED_TPR1 = 0.10     # main definition of an exposed cell: canary TPR at 1% FPR of at least ten times chance
                        # (attacker precision about 9% at a prior of 1%); 0.05 and 0.25 are sensitivity analyses
TAUS = (0.05, 0.10, 0.25)
PRIORS = (0.001, 0.01, 0.10)
CALIB_SENS = 0.90       # a calibrated release threshold must still block this share of the exposed development cells
N_BOOT = 2000           # resamples of whole configurations
N0_ILLUSTRATIVE = 10_000


def attacks():
    spec = importlib.util.spec_from_file_location('att03', os.path.join(HERE, '03_attack_audit.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def lhs_configs(k, seed=7):
    """k XGBoost settings from a Latin hypercube over capacity, leaf support and regularisation (reproducible)."""
    from scipy.stats import qmc
    u = qmc.LatinHypercube(d=7, seed=seed).random(k)
    depth = (2 + np.floor(u[:, 0] * 11)).astype(int)                       # 2..12
    rounds = np.round(np.exp(np.log(50) + u[:, 1] * (np.log(1000) - np.log(50)))).astype(int)
    lr = np.exp(np.log(0.03) + u[:, 2] * (np.log(0.3) - np.log(0.03)))
    mcw = np.array([0, 1, 2, 5, 10, 20, 50])[np.minimum((u[:, 3] * 7).astype(int), 6)]
    lam = np.array([0, 1, 5, 10, 30])[np.minimum((u[:, 4] * 5).astype(int), 4)]
    sub = 0.5 + 0.5 * u[:, 5]
    col = 0.5 + 0.5 * u[:, 6]
    return {f'lhs{i:03d}': dict(n_estimators=int(rounds[i]), max_depth=int(depth[i]), learning_rate=float(round(lr[i], 4)),
                                min_child_weight=int(mcw[i]), reg_lambda=int(lam[i]), subsample=float(round(sub[i], 3)),
                                colsample_bytree=float(round(col[i], 3))) for i in range(k)}


LHS = lhs_configs(40)


def configs(y_tr, seed):
    """Named XGBoost settings spanning capacity, leaf-support and regularisation (krcp, leaky and regularized are the pilot's),
    plus 40 space-filling settings lhs000..lhs039."""
    spw = float((y_tr == 0).sum() / max((y_tr == 1).sum(), 1))
    common = dict(random_state=seed, eval_metric='auc', verbosity=0, n_jobs=L.N_THREADS, scale_pos_weight=spw)
    named = {
        'd2_r100': dict(n_estimators=100, max_depth=2, learning_rate=0.1, min_child_weight=1, reg_lambda=1, subsample=1.0, colsample_bytree=1.0, **common),
        'regularized': L._xgb_kwargs('regularized', y_tr, seed),
        'd4_free': dict(n_estimators=300, max_depth=4, learning_rate=0.05, min_child_weight=0, reg_lambda=0, subsample=0.7, colsample_bytree=0.7, **common),
        'krcp': L._xgb_kwargs('krcp', y_tr, seed),
        'd6_mcw20': dict(n_estimators=500, max_depth=6, learning_rate=0.05, min_child_weight=20, reg_lambda=1, subsample=0.8, colsample_bytree=0.8, **common),
        'd6_free': dict(n_estimators=500, max_depth=6, learning_rate=0.05, min_child_weight=0, reg_lambda=0, subsample=0.8, colsample_bytree=0.8, **common),
        'leaky': L._xgb_kwargs('leaky', y_tr, seed),
    }
    named.update({k: dict(v, **common) for k, v in LHS.items()})
    return named


def leaf_share_lt11(model, Xtr):
    """Share of leaves that fewer than 11 training rows reach."""
    leaf = model.apply(Xtr)
    small = total = 0
    for j in range(leaf.shape[1]):
        _, cnt = np.unique(leaf[:, j], return_counts=True)
        small += int((cnt < L.MIN_CELL).sum())
        total += len(cnt)
    return small / max(total, 1)


def canary_lira(Pc, cin, cy):
    """Leave-one-model-out LiRA on the canaries. Pc[k, c] = P(y=1) of model k on canary c (features unchanged, label cy)."""
    pc = np.clip(np.where(cy[None, :] == 1, Pc, 1 - Pc).astype(float), 1e-7, 1 - 1e-7)
    phi = np.log(pc / (1 - pc))
    w_in, w_out = cin.astype(float), (~cin).astype(float)
    sums = {nm: (np.sum(phi * w, 0), np.sum(phi ** 2 * w, 0), np.sum(w, 0)) for nm, w in (('in', w_in), ('out', w_out))}
    M = phi.shape[0]
    score = np.zeros_like(phi)
    ll = lambda x, m, v: -0.5 * np.log(2 * np.pi * v) - (x - m) ** 2 / (2 * v)  # noqa: E731
    for k in range(M):
        par = {}
        for nm, w in (('in', w_in), ('out', w_out)):
            s1, s2, n = sums[nm]
            n_k = n - w[k]
            s1_k, s2_k = s1 - phi[k] * w[k], s2 - phi[k] ** 2 * w[k]
            mu = np.where(n_k > 0, s1_k / np.maximum(n_k, 1), 0.0)
            var = np.where(n_k > 1, (s2_k - n_k * mu ** 2) / np.maximum(n_k - 1, 1), 1.0)
            par[nm] = (mu, np.maximum(var, 1e-4))
        score[k] = ll(phi[k], *par['in']) - ll(phi[k], *par['out'])
    return score


def make_canaries(X, y, canary_src, kind='flip', seed=2027):
    """Canary features and labels. flip: real rows with the label flipped, so a model can fit them only by memorising.
    shuffle: synthetic rows whose features are drawn independently from their own marginals (every column of the pool permuted
    on its own) with a random label, an out-of-distribution canary of the kind used in the memorisation literature."""
    Xc = X.iloc[canary_src].reset_index(drop=True)
    if kind == 'flip':
        return Xc, 1 - y[canary_src]
    if kind != 'shuffle':
        raise ValueError(kind)
    rs = np.random.default_rng(seed)
    Xs = pd.DataFrame({c: Xc[c].to_numpy()[rs.permutation(len(Xc))] for c in Xc.columns}, columns=list(Xc.columns))
    return Xs, (rs.random(len(Xs)) < y.mean()).astype(int)


def run_cell(X, y, base_rows, canary_src, canary_y, cname, n, M, T, A, canary_X=None, ctype='flip'):
    import xgboost as xgb
    N, C = len(y), len(canary_src)
    rng = np.random.default_rng(zlib.crc32(f'{cname}/{n}'.encode()))
    Xc = X.iloc[canary_src] if canary_X is None else canary_X
    inm = np.zeros((M, N), bool)
    P = np.zeros((M, N), np.float32)
    Pc = np.zeros((M, C), np.float32)
    cin = np.zeros((M, C), bool)
    leaf, gap = [], []
    t0 = time.time()
    for k in range(M):
        idx = np.sort(rng.choice(base_rows, n, replace=False))
        cin[k] = rng.random(C) < 0.5
        Xtr = pd.concat([X.iloc[idx], Xc[cin[k]]])
        ytr = np.concatenate([y[idx], canary_y[cin[k]]])
        m = xgb.XGBClassifier(**configs(ytr, 10_000 + k)[cname])
        m.fit(Xtr, ytr)
        P[k] = m.predict_proba(X)[:, 1]
        Pc[k] = m.predict_proba(Xc)[:, 1]
        inm[k, idx] = True
        if k < T:
            leaf.append(leaf_share_lt11(m, Xtr))
            non = np.setdiff1d(base_rows, idx)
            non = rng.choice(non, min(len(non), 4000), replace=False)
            gap.append(L.auc(y[idx], P[k, idx]) - L.auc(y[non], P[k, non]))
    # ground truth: canaries
    sc = canary_lira(Pc, cin, canary_y)
    lab = cin.ravel().astype(int)
    boot = []     # 95% interval of the pooled canary TPR at 1% FPR: resample the models
    rb = np.random.default_rng(5)
    for _ in range(200):
        pick = rb.integers(0, M, M)
        boot.append(L.tpr_at_fpr(cin[pick].ravel().astype(int), sc[pick].ravel(), 0.01))
    prm = configs(y, 0)[cname]
    row = {'config': cname, 'n': n, 'models': M, 'canary_type': ctype, 'canary_auc': L.auc(lab, sc.ravel()),
           'canary_tpr1': L.tpr_at_fpr(lab, sc.ravel(), 0.01), 'canary_tpr1_lo': float(np.percentile(boot, 2.5)),
           'canary_tpr1_hi': float(np.percentile(boot, 97.5)), 'canary_tpr5': L.tpr_at_fpr(lab, sc.ravel(), 0.05),
           'canary_auc_model_sd': float(np.std([L.auc(cin[k].astype(int), sc[k]) for k in range(M)])),
           'depth': prm.get('max_depth', 6), 'rounds': prm['n_estimators'], 'lr': prm.get('learning_rate', 0.3),   # xgboost defaults where
           'mcw': prm.get('min_child_weight', 1), 'lam': prm.get('reg_lambda', 1), 'subsample': prm.get('subsample', 1.0),   # a setting is silent
           'colsample': prm.get('colsample_bytree', 1.0),
           # subsampled models are reproducible only at the same thread count, so the run environment is part of the result
           'threads': L.N_THREADS, 'xgboost': xgb.__version__}
    # the usual audit on ordinary rows for T target models, shadows = the other models
    sh_auc, li_auc, li_tpr = [], [], []
    for t in range(T):
        others = np.array([j for j in range(M) if j != t])
        mem = np.where(inm[t])[0]
        non = np.setdiff1d(base_rows, mem)
        m_eval = min(len(mem), len(non), 3000)
        r2 = np.random.default_rng(t + 1)
        ev = np.concatenate([r2.choice(mem, m_eval, replace=False), r2.choice(non, m_eval, replace=False)])
        lb = np.r_[np.ones(m_eval, int), np.zeros(m_eval, int)]
        s_in, s_p = inm[others], P[others]
        kk = min(16, len(others))
        sh_auc.append(L.auc(lb, A.shokri(s_in[:kk], s_p[:kk], y, P[t], ev, lb, t + 1)))
        lr = A.lira(s_in, s_p, y, P[t], ev)
        li_auc.append(L.auc(lb, lr))
        li_tpr.append(L.tpr_at_fpr(lb, lr, 0.01))
    row.update({'shadow_auc': float(np.mean(sh_auc)), 'lira_auc': float(np.mean(li_auc)), 'lira_tpr1': float(np.mean(li_tpr)),
                'leaf_lt11': float(np.mean(leaf)), 'auc_gap': float(np.mean(gap)), 'seconds': round(time.time() - t0)})
    return row


CANARY_TEXT = {'flip': 'label-flipped real rows',
               'shuffle': 'synthetic rows (each feature drawn independently from its own marginal, random label)'}
QUANTITIES = (          # column, label, sign (+1: a larger value means more exposed)
    ('shadow_auc', 'shadow-model AUC', 1),
    ('lira_auc', 'LiRA AUC (ordinary rows)', 1),
    ('lira_tpr1', 'LiRA TPR@1%FPR (ordinary rows)', 1),
    ('auc_gap', 'member / non-member AUROC gap', 1),
    ('leaf_lt11', 'share of leaves < 11 rows', 1),
    ('n', 'training rows (a larger value is safer)', -1),
)
PRESCRIBED = {          # rules with the thresholds the policy prescribes (the 0.55 of the pilot, 10% and 0.02 from the audit design)
    'shadow-model AUC <= 0.55 (pilot release rule)': lambda d: d.shadow_auc <= L.GATE2_THRESHOLD,
    'leaves with < 11 rows <= 10%': lambda d: d.leaf_lt11 <= 0.10,
    'member / non-member AUROC gap <= 0.02': lambda d: d.auc_gap <= 0.02,
    f'training rows >= {N0_ILLUSTRATIVE:,} (illustrative)': lambda d: d.n >= N0_ILLUSTRATIVE,
    'release every cell': lambda d: pd.Series(True, index=d.index),
    'block every cell': lambda d: pd.Series(False, index=d.index),
}


def auc_rank(label, score):
    """AUC of `score` for telling label 1 from label 0 (ties count half); nan when one class is missing."""
    from scipy.stats import rankdata
    label = np.asarray(label, bool)
    n1, n0 = int(label.sum()), int((~label).sum())
    if n1 == 0 or n0 == 0:
        return float('nan')
    r = rankdata(np.asarray(score, float))
    return float((r[label].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def spearman(a, b):
    from scipy.stats import spearmanr
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return float('nan')
    return float(spearmanr(a, b)[0])


def ppv(tpr, prior, fpr=0.01):
    """Share of flagged records that are true members when a fraction `prior` of the candidates are members."""
    return tpr * prior / (tpr * prior + fpr * (1 - prior))


def sens_spec(release, exposed):
    """Sensitivity = share of exposed cells that the rule blocks; specificity = share of unexposed cells that it releases."""
    release, exposed = np.asarray(release, bool), np.asarray(exposed, bool)
    sens = float(np.mean(~release[exposed])) if exposed.any() else float('nan')
    spec = float(np.mean(release[~exposed])) if (~exposed).any() else float('nan')
    return sens, spec


def calibrate(s, exposed, target=CALIB_SENS):
    """Largest release threshold c (a cell is released when s <= c) that still blocks at least `target` of the exposed cells.
    Sensitivity falls and specificity rises with c, so the largest admissible c has the best specificity.
    -inf = block everything; nan when one class is missing."""
    s, exposed = np.asarray(s, float), np.asarray(exposed, bool)
    if exposed.sum() == 0 or (~exposed).sum() == 0:
        return float('nan')
    best = -np.inf
    for c in np.unique(s):
        if np.mean(s[exposed] > c) < target - 1e-12:
            break
        best = float(c)
    return best


def loco_release(s, exposed, groups, target=CALIB_SENS):
    """Release decisions of the calibrated rule when each configuration (all its sizes together) is held out of the calibration."""
    s, exposed, groups = np.asarray(s, float), np.asarray(exposed, bool), np.asarray(groups)
    rel = np.zeros(len(s), bool)
    for g in np.unique(groups):
        te = groups == g
        c = calibrate(s[~te], exposed[~te], target)
        rel[te] = (s[te] <= c) if not np.isnan(c) else False
    return rel


def boot_clusters(groups, stat, n_boot=N_BOOT, seed=11):
    """95% percentile interval of stat(idx) (a vector) over resamples of whole configurations, and the share of defined resamples."""
    groups = np.asarray(groups)
    members = [np.where(groups == g)[0] for g in np.unique(groups)]
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(members), len(members))
        vals.append(np.asarray(stat(np.concatenate([members[i] for i in pick])), float))
    vals = np.array(vals)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        lo, hi = np.nanpercentile(vals, [2.5, 97.5], axis=0)
    return lo, hi, np.mean(np.isfinite(vals), axis=0)


def p1_stats(d, tau):
    """Threshold-free discrimination (AUC, Spearman) of each audit quantity, paired differences, and the prescribed rules' sens / spec."""
    e = (d.canary_tpr1 >= tau).to_numpy()
    out = {}
    for col, _, sign in QUANTITIES:
        out['auc:' + col] = auc_rank(e, sign * d[col].to_numpy(float))
        out['rho:' + col] = spearman(d[col].to_numpy(float), d.canary_tpr1.to_numpy(float))
    out['diff:lira_tpr1'] = out['auc:lira_tpr1'] - out['auc:shadow_auc']
    out['diff:lira_auc'] = out['auc:lira_auc'] - out['auc:shadow_auc']
    for name, fn in PRESCRIBED.items():
        out['sens:' + name], out['spec:' + name] = sens_spec(fn(d).to_numpy(bool), e)
    return out


def _f(x, k=2):
    return 'n/a' if x is None or not np.isfinite(x) else f'{x:.{k}f}'


def _ci(lo, hi, k=2):
    return 'n/a' if not (np.isfinite(lo) and np.isfinite(hi)) else f'[{lo:.{k}f}, {hi:.{k}f}]'


def summarize(df, tau=EXPOSED_TPR1, n_boot=N_BOOT):
    """-> (markdown lines, calibrated thresholds as a dict). df = one row per cell (configuration x training size)."""
    df = df.drop_duplicates(['config', 'n'], keep='last').reset_index(drop=True)
    e = (df.canary_tpr1 >= tau).to_numpy()
    groups = df.config.to_numpy()
    named = ~df.config.str.startswith('lhs').to_numpy()
    point = p1_stats(df, tau)
    keys = list(point)

    def stat(idx):
        r = p1_stats(df.iloc[idx], tau)
        return [r[k] for k in keys]

    lo, hi, _ = boot_clusters(groups, stat, n_boot)
    ci = {k: (lo[i], hi[i]) for i, k in enumerate(keys)}
    models = int(df.models.iloc[0]) if 'models' in df and df.models.notna().any() else M_MODELS
    md = ['# Canary benchmark: release rules against planted-canary ground truth', '',
          f'{len(df)} cells ({int(named.sum())} named, {int((~named).sum())} space-filling; {len(np.unique(groups))} configurations, '
          f'{df.n.nunique()} training sizes). Each cell = {models} models; each model contains a random half of {N_CANARY} '
          f'{CANARY_TEXT[str(df.canary_type.iloc[0]) if "canary_type" in df and df.canary_type.notna().any() else "flip"]} (canaries), '
          f'so the membership of every canary is known and a leave-one-model-out LiRA gives the ground-truth exposure. '
          f'A cell is **exposed** when its canary TPR at 1% FPR is at least {tau:g} (main definition; {" and ".join(f"{t:g}" for t in TAUS if t != tau)} '
          f'as sensitivity analyses): {int(e.sum())} of {len(df)} cells. Intervals are 95% percentile intervals over {n_boot:,} resamples of whole '
          f'configurations (all sizes of one configuration together).', '',
          '## 1. Does the audit quantity tell exposed cells from unexposed ones? (threshold-free)', '',
          f'| quantity | AUC, tau = {tau:g} [95% CI] | AUC, tau = ' + ' | AUC, tau = '.join(f'{t:g}' for t in TAUS if t != tau)
          + ' | Spearman with canary TPR@1%FPR [95% CI] |', '|---|---|' + '---|' * (len(TAUS) - 1) + '---|']
    for col, lab, sign in QUANTITIES:
        others = [auc_rank(df.canary_tpr1 >= t, sign * df[col]) for t in TAUS if t != tau]
        md.append(f'| {lab} | {_f(point["auc:" + col])} {_ci(*ci["auc:" + col])} | ' + ' | '.join(_f(v) for v in others)
                  + f' | {_f(point["rho:" + col])} {_ci(*ci["rho:" + col])} |')
    md += ['', f'Paired difference in AUC (tau = {tau:g}), LiRA TPR@1%FPR minus shadow-model AUC: {_f(point["diff:lira_tpr1"])} '
               f'{_ci(*ci["diff:lira_tpr1"])}; LiRA AUC minus shadow-model AUC: {_f(point["diff:lira_auc"])} {_ci(*ci["diff:lira_auc"])}. '
               f'Spearman is computed on the raw quantity (for training rows a negative value means larger is safer).', '',
           f'## 2. The rules at their prescribed thresholds (tau = {tau:g})', '',
           '| rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] |', '|---|---|---|---|---|']
    for name, fn in PRESCRIBED.items():
        rel = fn(df).to_numpy(bool)
        md.append(f'| {name} | {int(rel.sum())}/{len(df)} | {int((rel & e).sum())}/{int(e.sum())} | '
                  f'{_f(point["sens:" + name])} {_ci(*ci["sens:" + name])} | {_f(point["spec:" + name])} {_ci(*ci["spec:" + name])} |')
    md += ['', 'The same prescribed rules at the other definitions of "exposed" (sensitivity / specificity):', '',
           '| rule | ' + ' | '.join(f'tau = {t:g}' for t in TAUS) + ' |', '|---|' + '---|' * len(TAUS),
           '| cells exposed / unexposed | ' + ' | '.join(f'{int((df.canary_tpr1 >= t).sum())} / {int((df.canary_tpr1 < t).sum())}' for t in TAUS) + ' |']
    for name, fn in PRESCRIBED.items():
        rel = fn(df).to_numpy(bool)
        md.append(f'| {name} | ' + ' | '.join('{} / {}'.format(*(_f(v) for v in sens_spec(rel, df.canary_tpr1 >= t))) for t in TAUS) + ' |')

    # calibration: largest release threshold that still blocks CALIB_SENS of the exposed cells
    md += ['', f'## 3. Calibrated thresholds (tau = {tau:g}; the threshold must block at least {CALIB_SENS:.0%} of the exposed cells)', '',
           'In-sample = thresholds fitted on all cells here. Leave-one-configuration-out = each configuration is scored with a threshold fitted '
           'on the others (the interval resamples configurations and keeps the decisions fixed).', '',
           '| quantity | calibrated rule | in-sample sensitivity / specificity | leave-one-configuration-out sensitivity [CI] | specificity [CI] |',
           '|---|---|---|---|---|']
    cal, rel_cal, rel_loco = {}, {}, {}
    thr = {'tau': tau, 'target_sensitivity': CALIB_SENS, 'cells': int(len(df)), 'rules': {}}
    for col, lab, sign in QUANTITIES:
        s = sign * df[col].to_numpy(float)
        c = calibrate(s, e)
        cal[col] = c
        rel_cal[col] = (s <= c) if not np.isnan(c) else np.zeros(len(df), bool)
        rel_loco[col] = loco_release(s, e, groups)
        v = (sign * c) if np.isfinite(c) else None
        thr['rules'][col] = {'label': lab, 'release_if': '<=' if sign > 0 else '>=', 'threshold': v}
        txt = 'block every cell' if v is None else f'{lab.split(" (")[0]} {"<=" if sign > 0 else ">="} {v:,.0f}' if col == 'n' else \
            f'{lab.split(" (")[0]} <= {v:.3f}'
        si, sp = sens_spec(rel_cal[col], e)
        sl = lambda idx, col=col: sens_spec(rel_loco[col][idx], e[idx])  # noqa: E731
        l2, h2, _ = boot_clusters(groups, sl, n_boot)
        s_l, p_l = sens_spec(rel_loco[col], e)
        md.append(f'| {lab} | {txt} | {_f(si)} / {_f(sp)} | {_f(s_l)} {_ci(l2[0], h2[0])} | {_f(p_l)} {_ci(l2[1], h2[1])} |')

    # what a miss costs
    md += ['', f'## 4. What a miss costs: exposed cells (tau = {tau:g}) that each rule releases', '',
           '| rule | exposed cells released | median canary TPR@1%FPR of those | highest | of those, at the largest training size | unexposed cells blocked |',
           '|---|---|---|---|---|---|']
    big = (df.n == df.n.max()).to_numpy()
    shadow_rule = PRESCRIBED['shadow-model AUC <= 0.55 (pilot release rule)'](df).to_numpy(bool)
    for name, rel in (('shadow-model AUC <= 0.55 (prescribed)', shadow_rule),
                      ('shadow-model AUC, calibrated in-sample', rel_cal['shadow_auc']),
                      ('LiRA TPR@1%FPR, calibrated in-sample', rel_cal['lira_tpr1']),
                      ('LiRA TPR@1%FPR, calibrated leave-one-configuration-out', rel_loco['lira_tpr1'])):
        miss = rel & e
        t = df.canary_tpr1.to_numpy()[miss]
        md.append(f'| {name} | {int(miss.sum())}/{int(e.sum())} | {_f(np.median(t) if len(t) else np.nan, 3)} | '
                  f'{_f(t.max() if len(t) else np.nan, 3)} | {int((miss & big).sum())}/{int(miss.sum())} | {int((~rel & ~e).sum())}/{int((~e).sum())} |')

    # translation into precision
    md += ['', '## 5. From canary exposure to attacker precision', '',
           'Share of flagged records that are true members at 1% FPR, when a fraction pi of the candidate records are members: '
           'PPV = TPR*pi / (TPR*pi + 0.01*(1-pi)). Which PPV is tolerable is a governance judgement; this study does not set it.', '',
           '| exposure | canary TPR@1%FPR | PPV, pi = ' + ' | PPV, pi = '.join(f'{p:.1%}' for p in PRIORS) + ' |', '|---|---|' + '---|' * len(PRIORS)]
    q = df.canary_tpr1.quantile([0.5, 0.9, 1.0]).to_numpy()
    for lab, v in (('chance (TPR = FPR)', 0.01), *((f'tau = {t:g}', t) for t in TAUS), ('median cell here', q[0]), ('90th-percentile cell here', q[1]),
                   ('most exposed cell here', q[2])):
        md.append(f'| {lab} | {v:.3f} | ' + ' | '.join(f'{ppv(v, p):.1%}' for p in PRIORS) + ' |')

    # consistency
    md += ['', '## 6. Consistency', '', '| cells | n | exposed | AUC shadow-model | AUC LiRA AUC | AUC LiRA TPR@1%FPR |', '|---|---|---|---|---|---|']
    for lab, msk in (('named configurations', named), ('space-filling configurations', ~named)):
        d = df[msk]
        ee = e[msk]
        md.append(f'| {lab} | {int(msk.sum())} | {int(ee.sum())} | ' + ' | '.join(_f(auc_rank(ee, d[c].to_numpy(float))) for c in ('shadow_auc', 'lira_auc', 'lira_tpr1')) + ' |')
    if 'canary_tpr1_lo' in df and df.canary_tpr1_lo.notna().any():
        has = df.canary_tpr1_lo.notna()
        straddle = has & (df.canary_tpr1_lo < tau) & (df.canary_tpr1_hi > tau)
        md += ['', f'Cells whose model-resampling 95% interval of the canary TPR contains tau: {int(straddle.sum())} of {int(has.sum())} cells with an interval.']
    if 'canary_auc_model_sd' in df:
        md += ['', f'Median model-to-model SD of the canary AUC inside a cell: {_f(df.canary_auc_model_sd.median(), 3)}.']

    md += ['', '## 7. Named configurations', '',
           '| config | n | canary AUC | canary TPR@1%FPR | exposed | shadow AUC | LiRA TPR@1%FPR | leaves < 11 | AUROC gap |', '|---|---|---|---|---|---|---|---|---|']
    for i, r in df[named].sort_values(['config', 'n']).iterrows():
        rng_txt = f' ({r.canary_tpr1_lo:.3f}-{r.canary_tpr1_hi:.3f})' if 'canary_tpr1_lo' in df and np.isfinite(r.canary_tpr1_lo) else ''
        md.append(f'| {r.config} | {int(r.n):,} | {r.canary_auc:.3f} | {r.canary_tpr1:.3f}{rng_txt} | {"yes" if e[i] else "no"} | {r.shadow_auc:.3f} | '
                  f'{r.lira_tpr1:.3f} | {r.leaf_lt11:.1%} | {r.auc_gap:.3f} |')
    return md, thr


def apply_fixed(df, thr, tau=None, n_boot=N_BOOT):
    """Thresholds calibrated on the development cells (canary_thresholds.json), applied unchanged to this cohort's cells."""
    df = df.drop_duplicates(['config', 'n'], keep='last').reset_index(drop=True)
    tau = thr['tau'] if tau is None else tau
    e = (df.canary_tpr1 >= tau).to_numpy()
    groups = df.config.to_numpy()
    md = [f'## 9. Thresholds fixed on the development cohort (tau = {tau:g}; {thr["cells"]} development cells, target sensitivity {thr["target_sensitivity"]:.0%})', '',
          f'The development thresholds are applied unchanged to these {len(df)} cells, {int(e.sum())} of them exposed. "Recalibrated here" refits the '
          f'threshold on this cohort\'s own cells, one configuration left out at a time, and shows what a fixed threshold loses.'
          + ('' if tau == thr['tau'] else f' Note: the development thresholds were calibrated at tau = {thr["tau"]:g}.'), '',
          '| quantity | fixed rule | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated here: sensitivity / specificity |',
          '|---|---|---|---|---|---|---|']
    for col, lab, sign in QUANTITIES:
        r = thr['rules'].get(col)
        if not r or r.get('threshold') is None:
            continue
        v = r['threshold']
        x = df[col].to_numpy(float)
        rel = (x <= v) if r['release_if'] == '<=' else (x >= v)
        lo, hi, _ = boot_clusters(groups, lambda idx, rel=rel: sens_spec(rel[idx], e[idx]), n_boot)
        s, p = sens_spec(rel, e)
        s2, p2 = sens_spec(loco_release(sign * x, e, groups), e)
        rule = f'{lab.split(" (")[0]} {r["release_if"]} {v:,.0f}' if col == 'n' else f'{lab.split(" (")[0]} {r["release_if"]} {v:.3f}'
        md.append(f'| {lab} | {rule} | {int(rel.sum())}/{len(df)} | {int((rel & e).sum())}/{int(e.sum())} | {_f(s)} {_ci(lo[0], hi[0])} | '
                  f'{_f(p)} {_ci(lo[1], hi[1])} | {_f(s2)} / {_f(p2)} |')
    return md


def compare_types(a, b, tau=EXPOSED_TPR1, n_boot=N_BOOT, names=('flip', 'shuffle')):
    """Does the canary type change which cells are exposed, and does the ranking of audit quantities survive? a, b = cell tables of
    two canary types. Each type is its own set of trained models, so the ordinary-row audit quantities differ slightly between them."""
    m = a.merge(b, on=['config', 'n'], suffixes=('_a', '_b')).reset_index(drop=True)
    na, nb = names
    md = ['## 8. Robustness to the canary type', '']
    if len(m) < 6 or m.config.nunique() < 3:
        return md + ['Too few cells in both runs to compare.']
    groups = m.config.to_numpy()
    ea, eb = (m.canary_tpr1_a >= tau).to_numpy(), (m.canary_tpr1_b >= tau).to_numpy()

    def get(d, c, side):    # the merge keys (config, n) carry no suffix
        return d[c + side if c + side in d else c].to_numpy(float)

    def stat(idx):
        d = m.iloc[idx]
        e1, e2 = (d.canary_tpr1_a >= tau).to_numpy(), (d.canary_tpr1_b >= tau).to_numpy()
        out = [spearman(d.canary_tpr1_a, d.canary_tpr1_b), float(np.mean(e1 == e2))]
        for c, _, sg in QUANTITIES:
            out += [auc_rank(e1, sg * get(d, c, '_a')), auc_rank(e2, sg * get(d, c, '_b')), auc_rank(e2, sg * get(d, c, '_a'))]
        return out

    point = stat(np.arange(len(m)))
    lo, hi, _ = boot_clusters(groups, stat, n_boot)
    both, only_a, only_b = int((ea & eb).sum()), int((ea & ~eb).sum()), int((~ea & eb).sum())
    md += [f'{len(m)} cells ({m.config.nunique()} configurations) in both runs. Spearman correlation of the canary TPR@1%FPR between the '
           f'{na} and {nb} canaries: {_f(point[0])} {_ci(lo[0], hi[0])}. Exposure labels (tau = {tau:g}) agree in {point[1]:.0%} of cells '
           f'{_ci(lo[1] * 100, hi[1] * 100, 0)}% (exposed under both {both}, only {na} {only_a}, only {nb} {only_b}, neither {int((~ea & ~eb).sum())}).', '',
           f'AUC of each audit quantity for telling exposed from unexposed cells (tau = {tau:g}) under either definition of the ground truth:', '',
           f'| quantity | {na} truth, {na}-run audit | {nb} truth, {nb}-run audit | {nb} truth, {na}-run audit |', '|---|---|---|---|']
    for i, (c, lab, sg) in enumerate(QUANTITIES):
        cell = [f'{_f(point[2 + 3 * i + j])} {_ci(lo[2 + 3 * i + j], hi[2 + 3 * i + j])}' for j in range(3)]
        md.append(f'| {lab} | ' + ' | '.join(cell) + ' |')
    # the prescribed rule and the threshold calibrated on the first type, scored against both definitions (same audit)
    s_a = m.lira_tpr1_a.to_numpy(float)
    c_a = calibrate(s_a, ea)
    rules = (('shadow-model AUC <= 0.55 (prescribed)', (m.shadow_auc_a <= L.GATE2_THRESHOLD).to_numpy()),
             (f'LiRA TPR@1%FPR, threshold calibrated on the {na} cells' + (f' ({c_a:.3f})' if np.isfinite(c_a) else ''),
              (s_a <= c_a) if not np.isnan(c_a) else np.zeros(len(m), bool)))
    md += ['', f'Rules scored with the {na}-run audit against each ground truth (sensitivity / specificity):', '',
           f'| rule | {na} truth | {nb} truth |', '|---|---|---|']
    for name, rel in rules:
        md.append(f'| {name} | ' + ' | '.join('{} / {}'.format(*(_f(v) for v in sens_spec(rel, e))) for e in (ea, eb)) + ' |')
    return md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', default='synpuf')
    ap.add_argument('--configs', nargs='+', default=['d2_r100', 'regularized', 'd4_free', 'krcp', 'd6_mcw20', 'd6_free', 'leaky'])
    ap.add_argument('--sizes', nargs='+', type=int, default=[2000, 6000, 19746])
    ap.add_argument('--lhs', action='store_true', help='run the 40 space-filling settings lhs000..lhs039 instead of the named ones')
    ap.add_argument('--models', type=int, default=M_MODELS)
    ap.add_argument('--targets', type=int, default=T_TARGETS)
    ap.add_argument('--summarize', action='store_true')
    ap.add_argument('--tau', type=float, default=EXPOSED_TPR1, help='canary TPR@1%%FPR at or above which a cell counts as exposed')
    ap.add_argument('--boot', type=int, default=N_BOOT, help='resamples of whole configurations for the intervals')
    ap.add_argument('--thresholds', default='', help='with --summarize: canary_thresholds.json of the development cohort, applied unchanged '
                                                     '(external validation, e.g. out/synpuf_xgb_canary/canary_thresholds.json)')
    ap.add_argument('--out-tag', default='', help='separate cells file per process, e.g. n2000')
    ap.add_argument('--canary-type', choices=['flip', 'shuffle'], default='flip',
                    help='flip = real rows with the label flipped (main); shuffle = synthetic rows, features drawn from their own marginals, random label '
                         '(robustness check; written to <ds>_canary_shuffle)')
    a = ap.parse_args()
    od = os.path.join(L.out_dir(a.dataset) + '_canary' + ('' if a.canary_type == 'flip' else '_' + a.canary_type))
    os.makedirs(od, exist_ok=True)
    f_csv = os.path.join(od, f'canary_cells{"_" + a.out_tag if a.out_tag else ""}.csv')
    if a.summarize:
        import glob
        df = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(glob.escape(od), 'canary_cells*.csv')))]).drop_duplicates(['config', 'n'], keep='last')
        md, thr = summarize(df, a.tau, a.boot)
        if a.thresholds:
            md += [''] + apply_fixed(df, json.load(open(a.thresholds, encoding='utf-8')), a.tau, a.boot)
        if a.canary_type == 'flip':
            f2 = sorted(glob.glob(os.path.join(glob.escape(L.out_dir(a.dataset) + '_canary_shuffle'), 'canary_cells*.csv')))
            if f2:
                md += [''] + compare_types(df, pd.concat([pd.read_csv(f) for f in f2]).drop_duplicates(['config', 'n'], keep='last'), a.tau, a.boot)
        open(os.path.join(od, 'canary_summary.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
        json.dump(thr, open(os.path.join(od, 'canary_thresholds.json'), 'w', encoding='utf-8'), indent=1)
        print('\n'.join(md))
        return
    X, y, split, aux, meta = L.load_matrix(a.dataset)
    rng = np.random.default_rng(2026)
    val = np.where(split == 'val')[0]
    canary_src = np.sort(rng.choice(val, N_CANARY, replace=False))
    canary_X, canary_y = make_canaries(X, y, canary_src, a.canary_type)
    base_rows = np.setdiff1d(np.arange(len(y)), canary_src)
    if a.lhs:
        a.configs = list(LHS)
    A = attacks()
    done = set()
    if os.path.exists(f_csv):
        old = pd.read_csv(f_csv)
        done = set(zip(old.config, old.n))
    n_cap = int(0.75 * len(base_rows))     # a quarter of the rows must stay outside every model: non-members for the audits and the AUROC gap
    for cname in a.configs:
        for n in a.sizes:
            n = min(n, n_cap)
            if (cname, n) in done:
                continue
            row = run_cell(X, y, base_rows, canary_src, canary_y, cname, n, a.models, a.targets, A, canary_X, a.canary_type)
            L.append_rows(f_csv, [row])
            print(f"  {cname:<12} n={n:>6}  canary AUC {row['canary_auc']:.3f} TPR@1% {row['canary_tpr1']:.3f}  |  shadow AUC {row['shadow_auc']:.3f}  "
                  f"LiRA TPR@1% {row['lira_tpr1']:.3f}  leaves<11 {row['leaf_lt11']:.1%}  gap {row['auc_gap']:.3f}  ({row['seconds']}s)", flush=True)
    print('done ->', os.path.relpath(f_csv, L.BASE))


if __name__ == '__main__':
    L.guard(main)
