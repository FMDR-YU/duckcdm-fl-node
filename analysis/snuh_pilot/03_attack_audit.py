# -*- coding: utf-8 -*-
"""Step 03 -- Gate 2 membership-inference audit of every target model.

Per target: members = its training rows, non-members = rows it never saw; the evaluation set is a
balanced random sample of both (as many non-members as available, same number of members).
  loss-threshold (Yeom 2018)  score = -log-loss of the true label, no shadows
  shadow-model (Shokri 2017)  attack RF trained on in/out outputs of the first 16 shadows of the
                              target's size class and variant, applied to the target's outputs
  LiRA online (Carlini 2022)  per person, Gaussian fits to the shadows' logit-confidence when the
                              person was in vs out; score = log-likelihood ratio for the target
  LiRA, global variance       the same with one pooled variance (Carlini 2022: better when there are fewer than ~64 shadows)
  RMIA offline (Zarifzadeh 2024)  score = share of reference people z for which the target's likelihood ratio of x beats that of z
                              by a factor of 2, with Pr(x) from the shadows that did not contain x
Combined models are audited against averaged triples of site shadows. Real sites are disjoint, so a (person, triple)
pair counts only when the person is in at most one of the three shadows (in = exactly one, out = none); triples that contain
the person twice are dropped for that person.
Also: TPR at 1% FPR, and per-subgroup AUC where the subgroup has >= 100 people in the sample.
Appends aggregates to out/<ds>/03_attacks_long.csv and out/<ds>/03_subgroups_long.csv.

    python 03_attack_audit.py --dataset snuh
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilot_lib as L  # noqa: E402


def load_shadows(ds, variant, cname, k):
    wd = L.work_dir(ds, 'shadows', variant, cname)
    files = sorted(f for f in os.listdir(wd) if f.endswith('.npz'))[:k]
    if len(files) < k:
        sys.exit(f'only {len(files)}/{k} shadows for {variant}/{cname}; run 02_train_shadows.py first')
    z = [np.load(os.path.join(wd, f)) for f in files]
    return np.stack([q['inmask'] for q in z]), np.stack([q['p'] for q in z]).astype(np.float32)


def combine(shadow_sets):
    """Average aligned shadows from three size classes / rotated site shadows. Each shadow is an independent random subset of
    the cohort, so one person can be in two or three of them; real sites are disjoint. in = in exactly one of the three,
    valid = in at most one (the other pairs are not used for that person). Returns (in, p, valid)."""
    cnt = np.sum([s[0] for s in shadow_sets], axis=0)
    ps = np.mean([s[1] for s in shadow_sets], axis=0)
    return cnt == 1, ps, cnt <= 1


def shokri(shadow_in, shadow_p, y, target_p, eval_idx, eval_lab, seed, per_shadow=1500, valid=None):
    rng = np.random.default_rng(seed)
    F, T = [], []
    for k in range(shadow_in.shape[0]):
        vk = np.ones(shadow_in.shape[1], bool) if valid is None else valid[k]
        for lab, pool in ((1, np.where(shadow_in[k] & vk)[0]), (0, np.where(~shadow_in[k] & vk)[0])):
            take = rng.choice(pool, min(per_shadow, len(pool)), replace=False)
            F.append(L.attack_features(shadow_p[k, take], y[take])); T.append(np.full(len(take), lab))
    clf = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=seed, n_jobs=L.N_THREADS)
    clf.fit(np.vstack(F), np.concatenate(T))
    s = clf.predict_proba(L.attack_features(target_p[eval_idx], y[eval_idx]))[:, 1]
    return s


def lira(shadow_in, shadow_p, y, target_p, eval_idx, valid=None, global_var=False):
    phi = np.stack([L.logit_conf(shadow_p[k, eval_idx], y[eval_idx]) for k in range(shadow_in.shape[0])])
    ins = shadow_in[:, eval_idx]
    ok = np.ones_like(ins) if valid is None else valid[:, eval_idx]
    t = L.logit_conf(target_p[eval_idx], y[eval_idx])

    def stats(mask):
        n = mask.sum(0)
        mu = np.where(n > 0, (phi * mask).sum(0) / np.maximum(n, 1), np.nan)
        var = np.where(n > 1, ((phi - mu) ** 2 * mask).sum(0) / np.maximum(n - 1, 1), np.nan)
        return mu, var
    m_in, m_out = ins & ok, (~ins) & ok
    mu_in, v_in = stats(m_in); mu_out, v_out = stats(m_out)
    if global_var:   # one variance for everybody: pooled within-person variance of the in and out populations
        ss = np.nansum(np.where(m_in.sum(0) > 1, v_in * (m_in.sum(0) - 1), 0)) + np.nansum(np.where(m_out.sum(0) > 1, v_out * (m_out.sum(0) - 1), 0))
        dof = np.maximum(m_in.sum(0) - 1, 0).sum() + np.maximum(m_out.sum(0) - 1, 0).sum()
        v_in = v_out = np.full_like(v_in, ss / max(dof, 1))
    # people with too few in/out shadows fall back to the pooled variance
    v_in = np.where(np.isnan(v_in), np.nanmedian(v_in), v_in); v_out = np.where(np.isnan(v_out), np.nanmedian(v_out), v_out)
    mu_in = np.where(np.isnan(mu_in), np.nanmedian(mu_in), mu_in); mu_out = np.where(np.isnan(mu_out), np.nanmedian(mu_out), mu_out)
    v_in = np.maximum(v_in, 1e-4); v_out = np.maximum(v_out, 1e-4)
    ll = lambda x, m, v: -0.5 * np.log(2 * np.pi * v) - (x - m) ** 2 / (2 * v)  # noqa: E731
    return ll(t, mu_in, v_in) - ll(t, mu_out, v_out)


def rmia(shadow_in, shadow_p, y, target_p, eval_idx, z_idx, valid=None, gamma=2.0, a=0.3):
    """Offline RMIA (Zarifzadeh et al. 2024). Pr(x) is estimated from the shadows that did not contain x:
    Pr(x) = ((1 + a) / 2) * mean_out Pr(x | shadow) + (1 - a) / 2. Score(x) = share of reference people z with
    [Pr(x | target) / Pr(x)] / [Pr(z | target) / Pr(z)] >= gamma."""
    idx = np.concatenate([eval_idx, z_idx])
    pr = lambda p, yy: np.clip(np.where(yy == 1, p, 1 - p).astype(float), 1e-7, 1.0)  # noqa: E731
    prs = np.stack([pr(shadow_p[k, idx], y[idx]) for k in range(shadow_in.shape[0])])
    out = ~shadow_in[:, idx]
    if valid is not None:
        out = out & valid[:, idx]
    n_out = out.sum(0)
    mean_out = np.where(n_out > 0, (prs * out).sum(0) / np.maximum(n_out, 1), np.nan)
    mean_out = np.where(np.isnan(mean_out), np.nanmedian(mean_out), mean_out)
    lr = pr(target_p[idx], y[idx]) / (((1 + a) / 2) * mean_out + (1 - a) / 2)
    lr_x, lr_z = lr[:len(eval_idx)], np.sort(lr[len(eval_idx):])
    return np.searchsorted(lr_z, lr_x / gamma, side='right') / len(lr_z)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', choices=L.DATASETS, required=True)
    ap.add_argument('--variants', nargs='+', default=list(L.VARIANTS))
    ap.add_argument('--seeds', nargs='+', type=int, default=None)
    a = ap.parse_args()

    X, y, split, aux, meta = L.load_matrix(a.dataset)
    n = len(y)
    train_idx = np.where(split == 'train')[0]
    od = L.out_dir(a.dataset)
    f_att, f_sg = os.path.join(od, '03_attacks_long.csv'), os.path.join(od, '03_subgroups_long.csv')
    done = set()
    if os.path.exists(f_att):
        prev = pd.read_csv(f_att); done = set(zip(prev['seed'], prev['variant'], prev['target']))

    for variant in a.variants:
        sh = {c: load_shadows(a.dataset, variant, c, L.k_lira()) for c in L.size_classes(len(train_idx))}
        rot = lambda s, r: (np.roll(s[0], r, axis=0), np.roll(s[1], r, axis=0))  # noqa: E731
        sh['B1_comb'] = combine([rot(sh['site'], r) for r in range(L.N_SITES)])
        sh['B2_comb'] = combine([sh[f'b2_{k}'] for k in range(L.N_SITES)])
        for c in ['full', 'site'] + [f'b2_{k}' for k in range(L.N_SITES)]:
            sh[c] = sh[c] + (None,)     # (in, p, valid): ordinary shadows have no invalid pairs
        for seed in (a.seeds or L.seeds()):
            sc = L.scenarios(train_idx, aux['stratum'].to_numpy(), seed)
            wd = L.work_dir(a.dataset, 'targets', str(seed), variant)
            targets = {k: (v[0], v[1]) for k, v in sc.items()}
            for comb, parts in L.COMBINED.items():
                targets[comb] = (np.unique(np.concatenate([sc[q][0] for q in parts])), comb)
            for fname, parts in L.FEDERATED.items():   # federated global model: members = all three sites, shadows of full size
                if os.path.exists(os.path.join(wd, f'{fname}.p.npy')):
                    targets[fname] = (np.unique(np.concatenate([sc[q][0] for q in parts])), 'full')
            rows, sg_rows = [], []
            for name, (members, cname) in targets.items():
                if (seed, variant, name) in done:
                    continue
                f_p = os.path.join(wd, f'{name}.p.npy')
                if not os.path.exists(f_p):
                    sys.exit(f'missing target {seed}/{variant}/{name}; run 01_train_targets.py first')
                p = np.load(f_p)
                rng = np.random.default_rng(seed * 1000 + len(name))
                nonmem = np.setdiff1d(np.arange(n), members)
                m_eval = min(len(members), len(nonmem))
                ev_m, ev_n = rng.choice(members, m_eval, replace=False), rng.choice(nonmem, m_eval, replace=False)
                ev = np.concatenate([ev_m, ev_n]); lab = np.r_[np.ones(m_eval, int), np.zeros(m_eval, int)]
                s_in, s_p, s_ok = sh[cname]
                z_idx = np.random.default_rng(seed * 7 + 1).choice(n, min(2000, n), replace=False)
                scores = {
                    'loss': np.log(np.clip(np.where(y[ev] == 1, p[ev], 1 - p[ev]), 1e-7, 1)),   # = -log-loss
                    'shadow': shokri(s_in[:L.k_shokri()], s_p[:L.k_shokri()], y, p, ev, lab, seed,
                                     valid=None if s_ok is None else s_ok[:L.k_shokri()]),
                    'lira': lira(s_in, s_p, y, p, ev, valid=s_ok),
                    'lira_gv': lira(s_in, s_p, y, p, ev, valid=s_ok, global_var=True),
                    'rmia': rmia(s_in, s_p, y, p, ev, z_idx, valid=s_ok),
                }
                r = {'seed': seed, 'variant': variant, 'target': name, 'n_eval_each': m_eval,
                     'n_members': len(members), 'k_lira': L.k_lira(), 'k_shokri': L.k_shokri()}
                for k, s in scores.items():
                    r[f'{k}_auc'] = L.auc(lab, s)
                    r[f'{k}_tpr1'] = L.tpr_at_fpr(lab, s, 0.01)
                rows.append(r)
                for g in meta['subgroups']:
                    gv = aux[g].to_numpy()[ev]
                    for level in np.unique(gv):
                        sel = gv == level
                        if sel.sum() < L.MIN_SUBGROUP or min(lab[sel].sum(), (1 - lab[sel]).sum()) < L.MIN_CELL:
                            continue
                        sg_rows.append({'seed': seed, 'variant': variant, 'target': name, 'subgroup': g,
                                        'level': level, 'n': int(sel.sum()),
                                        **{f'{k}_auc': L.auc(lab[sel], s[sel]) for k, s in scores.items()}})
                print(f'  seed {seed} {variant:<11} {name:<9} shadow {r["shadow_auc"]:.3f}  lira {r["lira_auc"]:.3f}  '
                      f'lira_gv {r["lira_gv_auc"]:.3f}  rmia {r["rmia_auc"]:.3f}', flush=True)
            if rows:
                L.append_rows(f_att, rows)
            if sg_rows:
                L.append_rows(f_sg, sg_rows)
    print('done ->', os.path.relpath(f_att, L.BASE))


if __name__ == '__main__':
    L.guard(main)
