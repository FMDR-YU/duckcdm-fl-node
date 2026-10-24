# -*- coding: utf-8 -*-
"""Step 06 -- summarise across seeds: mean and t-based 95% CI, Gate 2 decision with threshold sweep,
H1-H4 read-outs. Reads only out/<ds>/*.csv, writes out/<ds>/06_summary.md.

    python 06_summarize.py --dataset snuh
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilot_lib as L  # noqa: E402

def order():
    return (['A_0', 'Aprime_0'] + L.site_names('B1') + ['B1_comb', 'F_B1'] + L.site_names('B2') + ['B2_comb', 'F_B2'])


class _Order(list):
    """ORDER follows the number of sites of the loaded matrix (pilot_lib.N_SITES)."""
    def __iter__(self):
        return iter(order())

    def __contains__(self, x):
        return x in order()

    def index(self, x):
        return order().index(x)


ORDER = _Order()
SWEEP_TARGETS = ('A_0', 'Aprime_0', 'B1_comb', 'B2_comb', 'F_B1', 'F_B2')


def fmt(m, lo, hi, d=3):
    return f'{m:.{d}f} [{lo:.{d}f}–{hi:.{d}f}]' if not np.isnan(lo) else f'{m:.{d}f}'


def chk(a, op, b):
    """Comparison that is None (not evaluable) when either side is missing."""
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    if np.isnan(a) or np.isnan(b):
        return None
    return {'>': a > b, '>=': a >= b, '<': a < b, '<=': a <= b}[op]


def yn(c):
    return 'n/a' if c is None else ('yes' if c else 'no')


def verdict(cs):
    """A failed condition is conclusive even when another one cannot be evaluated."""
    if any(c is False for c in cs):
        return 'not supported'
    if any(c is None for c in cs):
        return 'not evaluable'
    return 'supported'


def decision_rules(ds, ut, at, sc, g1, g3):
    """The decision rules of docs/ANALYSIS_PLAN_v1.md section 3, evaluated here so that the verdicts are not read off
    the tables by eye. A rule whose inputs are missing is reported as 'not evaluable'. Evidence strings avoid the pipe
    character (markdown table)."""
    thr, ni, exposure_margin = L.GATE2_THRESHOLD, -0.02, 0.01
    fam = 'xgb_' if any(v.startswith('xgb_') for v in L.VARIANTS) else ''
    krcp = fam + 'krcp'
    primary = {('H5', f'{krcp} F_B1'), ('H2', f'{krcp} B1 (size)')}      # plan section 3: krcp with equal sites (B1); H5 and H2 are the main analyses
    pv = {}
    if at is not None:
        pv = {v: at[at.variant == v].pivot_table(index='seed', columns='target', values='shadow_auc') for v in L.VARIANTS}
    rows = []

    def add(h, label, cs, ev):
        rows.append((h, 'primary' if (h, label) in primary else 'secondary', label, verdict(cs), ev))

    # H1: the audit separates the over-fitted from the regularised model (central model A_0)
    lk, rg = fam + 'leaky', fam + 'regularized'
    if ut is not None and lk in pv and rg in pv and 'A_0' in pv[lk] and 'A_0' in pv[rg]:
        s_lk, s_rg = pv[lk]['A_0'].mean(), pv[rg]['A_0'].mean()
        a_lk = ut[(ut.variant == lk) & (ut.target == 'A_0')].auroc.mean()
        a_rg = ut[(ut.variant == rg) & (ut.target == 'A_0')].auroc.mean()
        cs = [chk(s_lk, '>', thr), chk(s_rg, '<=', thr), chk(a_rg, '>=', a_lk)]
        add('H1', f'{lk} vs {rg}', cs,
            f'shadow AUC {lk} {s_lk:.3f} > {thr}: {yn(cs[0])}; {rg} {s_rg:.3f} <= {thr}: {yn(cs[1])}; '
            f'AUROC {rg} {a_rg:.3f} >= {lk} {a_lk:.3f}: {yn(cs[2])}')

    # H2: site models are more exposed than the central model and most of the gap is training size (B1, equal sites);
    # the gap is larger when the sites are unequal (B2, judged separately)
    for v in L.VARIANTS:
        p = pv.get(v)
        if p is None or any(c not in p for c in ['A_0', 'Aprime_0'] + L.site_names('B1') + L.site_names('B2')):
            continue
        m1, lo1, hi1 = L.t_ci(p[L.site_names('B1')].mean(axis=1) - p['A_0'])
        m2, lo2, hi2 = L.t_ci(p[L.site_names('B2')].mean(axis=1) - p['A_0'])
        share = (p['Aprime_0'] - p['A_0']).mean() / m1 if m1 > 0 else float('nan')
        c1 = [chk(lo1, '>', 0), chk(share, '>=', 0.5)]
        add('H2', f'{v} B1 (size)', c1,
            f'gap B1 {fmt(m1, lo1, hi1)} lower bound > 0: {yn(c1[0])}; size share (A′−A)/(B1 gap) {share:.2f} >= 0.5: {yn(c1[1])}')
        c2 = [chk(lo2, '>', 0), chk(m2, '>', m1)]
        add('H2', f'{v} B2 (unequal sites)', c2,
            f'gap B2 {fmt(m2, lo2, hi2)} lower bound > 0: {yn(c2[0])}; B2 gap > B1 gap: {yn(c2[1])}')

    # H3: the prediction average is not inferior to the central model (each scenario on its own)
    if ut is not None and 'delta_auc_vs_A' in ut:
        for v in L.VARIANTS:
            for t in L.COMBINED:
                s = ut[(ut.variant == v) & (ut.target == t)]
                if not s.empty:
                    m, lo, hi = L.t_ci(s.delta_auc_vs_A)
                    c = chk(lo, '>', ni)
                    add('H3', f'{v} {t}', [c], f'ΔAUROC {fmt(m, lo, hi)} lower bound > −0.02: {yn(c)}')

    # H4: formats and reproducibility (both gates are needed for every variant)
    for v in L.VARIANTS:
        cs, ev = [], []
        if g1 is not None and not g1[g1.variant == v].empty:
            mx = g1[g1.variant == v].max_abs_dp.max()
            cs.append(chk(mx, '<', 1e-6))
            ev.append(f'Gate 1 max abs Δp {mx:.1e} < 1e-6: {yn(cs[-1])}')
        else:
            cs.append(None)
            ev.append('Gate 1 not run')
        if g3 is not None and not g3[g3.variant == v].empty:
            q = g3[g3.variant == v]
            same = bool(q.signature_valid.astype(str).str.lower().eq('true').all()
                        and q.data_hash_equal.astype(str).str.lower().eq('true').all())
            mx = q.abs_delta_auroc.max()
            cs.append(chk(mx, '<=', 1e-4) if same else False)
            ev.append(f'Gate 3 signature and data hash match: {yn(same)}; max abs ΔAUROC {mx:.1e} <= 1e-4: {yn(chk(mx, "<=", 1e-4))}')
        else:
            cs.append(None)
            ev.append('Gate 3 not run')
        if g1 is not None or g3 is not None:
            add('H4', v, cs, '; '.join(ev))
    rex = []     # federated models belong to the xgb family only
    for f in (sorted(glob.glob(os.path.join(glob.escape(os.path.join(L.BASE, 'analysis', 'federated', 'out', L.base_tag(ds))), 'fl_*.json'))) if fam else []):
        try:
            d = json.load(open(f, encoding='utf-8'))
        except (OSError, ValueError):
            continue
        r = (d.get('federated') or {}).get('reexec') or d.get('reexec')
        if r:
            rex.append((r['max_abs_pred_diff'], r['abs_delta_auroc']))
    if rex:
        mp, ma = max(x[0] for x in rex), max(x[1] for x in rex)
        cs = [chk(mp, '<', 1e-6), chk(ma, '<=', 1e-4)]
        add('H4', 'federated re-execution', cs,
            f'{len(rex)} job(s) run again in a fresh workspace: max abs Δp {mp:.1e} < 1e-6: {yn(cs[0])}; '
            f'max abs ΔAUROC {ma:.1e} <= 1e-4: {yn(cs[1])}')

    # H5: the federated model is not inferior, no more exposed than the central model (margin 0.01) and less exposed than the sites
    if ut is not None and 'delta_auc_vs_A' in ut:
        for v in L.VARIANTS:
            p = pv.get(v)
            for t, sites in L.FEDERATED.items():
                s = ut[(ut.variant == v) & (ut.target == t)]
                if s.empty or p is None or t not in p or 'A_0' not in p or any(q not in p for q in sites):
                    continue
                m, lo, hi = L.t_ci(s.delta_auc_vs_A)
                seeds = p[t].dropna().index
                sh_f, sh_a = p.loc[seeds, t].mean(), p.loc[seeds, 'A_0'].mean()
                md, lod, hid = L.t_ci(p.loc[seeds, list(sites)].mean(axis=1) - p.loc[seeds, t])
                cs = [chk(lo, '>', ni), chk(sh_f, '<=', sh_a + exposure_margin), chk(lod, '>', 0)]
                add('H5', f'{v} {t}', cs,
                    f'ΔAUROC(F−A) {fmt(m, lo, hi)} lower bound > −0.02: {yn(cs[0])}; shadow AUC F {sh_f:.3f} <= A {sh_a:.3f} + 0.01: '
                    f'{yn(cs[1])}; (sites mean − F) {fmt(md, lod, hid)} lower bound > 0: {yn(cs[2])}')

    # H6: exposure falls with training size
    if sc is not None:
        from scipy import stats
        for v in sorted(sc.variant.unique()):
            q = sc[sc.variant == v]
            sizes = sorted(q.n_train.unique())
            piv = q.pivot_table(index='seed', columns='n_train', values='shadow_auc')
            rho = stats.spearmanr(sizes, [piv[s_].mean() for s_ in sizes])[0] if len(sizes) > 2 else float('nan')
            slopes = [np.polyfit(np.log10(sizes), piv.loc[s_, sizes].to_numpy(float), 1)[0]
                      for s_ in piv.index if not piv.loc[s_, sizes].isna().any()]
            m, lo, hi = L.t_ci(slopes)
            cs = [chk(rho, '<', 0), chk(hi, '<', 0)]
            add('H6', v, cs,
                f'Spearman ρ (size, seed-mean AUC) {rho:.2f} < 0: {yn(cs[0])}; slope per log10(n) {fmt(m, lo, hi)} upper bound < 0: {yn(cs[1])}')

    out = ['## Pre-specified decision rules (docs/ANALYSIS_PLAN_v1.md §3), evaluated by code', '',
           '| hypothesis | role | variant / target | verdict | evidence |', '|---|---|---|---|---|']
    out += [f'| {h} | {role} | {v} | **{vd}** | {ev} |' for h, role, v, vd, ev in rows]
    out += ['', f'Primary verdicts: H5 and the B1 part of H2 for the published configuration ({krcp}) with equal sites (B1). Every other row is secondary.'
            ' Each hypothesis is judged on its own; no multiplicity correction. Intervals are t-based across seeds (utility differences'
            ' also have paired bootstrap intervals in 01_utility_long.csv). "not evaluable" means an input is missing or has fewer than two seeds.', '']
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', choices=L.DATASETS, required=True)
    a = ap.parse_args()
    od = L.out_dir(a.dataset)
    rd = lambda f: pd.read_csv(os.path.join(od, f)) if os.path.exists(os.path.join(od, f)) else None  # noqa: E731
    ut, at, sg, g1, g3, lf = (rd(f) for f in ('01_utility_long.csv', '03_attacks_long.csv', '03_subgroups_long.csv',
                                               '04_gate1.csv', '05_gate3.csv', '04_leaf_audit.csv'))
    # this step reads only out/: take the number of sites from the targets written by step 01 (14 real hospitals for tag h14)
    if ut is not None:
        import re
        n_sites = len({t for t in ut.target.unique() if re.fullmatch(r'B1_\d+', str(t))})
        if n_sites:
            L.set_n_sites(n_sites)
    kl = sorted({int(v) for v in at.k_lira.dropna()}) if at is not None and 'k_lira' in at else []
    ks = sorted({int(v) for v in at.k_shokri.dropna()}) if at is not None and 'k_shokri' in at else []
    md = [f'# Pilot summary — {a.dataset}', '',
          f'seeds: {sorted(int(s) for s in at.seed.unique()) if at is not None else "-"} · values = mean [95% CI across seeds]', '',
          'membership-inference audit: LiRA / RMIA with ' + (', '.join(map(str, kl)) if kl else 'an unrecorded number of') + ' reference models per target, '
          'shadow-model attack with ' + (', '.join(map(str, ks)) if ks else 'an unrecorded number of') + ' shadows', '']
    sc = rd('03b_size_curve_long.csv')
    md += decision_rules(a.dataset, ut, at, sc, g1, g3)

    if at is not None:
        md += ['## Gate 2 — membership inference (AUC; decision on shadow-model attack, threshold 0.55)', '',
               '| variant | target | n members | shadow AUC | loss AUC | LiRA AUC | LiRA TPR@1%FPR | decision |',
               '|---|---|---|---|---|---|---|---|']
        for v in L.VARIANTS:
            for t in ORDER:
                s = at[(at.variant == v) & (at.target == t)]
                if s.empty:
                    continue
                sh, lo, hi = L.t_ci(s.shadow_auc)
                md.append(f'| {v} | {t} | {L.cell(s.n_members.iloc[0])} | {fmt(sh, lo, hi)} | {fmt(*L.t_ci(s.loss_auc))} | '
                          f'{fmt(*L.t_ci(s.lira_auc))} | {fmt(*L.t_ci(s.lira_tpr1))} | {"PASS" if sh <= L.GATE2_THRESHOLD else "BLOCK"} |')
        md += ['', 'Threshold sweep (shadow-model mean AUC):', '',
               '| variant | target | ' + ' | '.join(f'≤{t:.2f}' for t in L.THRESHOLD_SWEEP) + ' |',
               '|---|---|' + '---|' * len(L.THRESHOLD_SWEEP)]
        for v in L.VARIANTS:
            for t in SWEEP_TARGETS:
                s = at[(at.variant == v) & (at.target == t)]
                if not s.empty:
                    mval = s.shadow_auc.mean()
                    md.append(f'| {v} | {t} | ' + ' | '.join('PASS' if mval <= th else 'BLOCK' for th in L.THRESHOLD_SWEEP) + ' |')

        metrics = (('shadow_auc', 'shadow AUC'), ('lira_auc', 'LiRA AUC'), ('lira_tpr1', 'LiRA TPR@1%FPR'), ('loss_auc', 'loss AUC'))
        md += ['', '## Exposure relative to the central model, by attack (route − A; mean [95% CI across seeds]; descriptive)', '',
               '| variant | route | ' + ' | '.join(m[1] for m in metrics) + ' |', '|---|---|' + '---|' * len(metrics)]
        for v in L.VARIANTS:
            pvs = {m: at[at.variant == v].pivot_table(index='seed', columns='target', values=m) for m, _ in metrics}
            for label, cols in (('A′ (size control)', ['Aprime_0']), (f'B1 sites (mean of {L.N_SITES})', L.site_names('B1')),
                                ('B1 averaged', ['B1_comb']), ('B1 federated', ['F_B1']),
                                (f'B2 sites (mean of {L.N_SITES})', L.site_names('B2')), ('B2 averaged', ['B2_comb']), ('B2 federated', ['F_B2'])):
                cells = []
                for m, _ in metrics:
                    p = pvs[m]
                    if 'A_0' not in p or any(c not in p for c in cols):
                        cells.append('-')
                        continue
                    d = (p[cols].mean(axis=1) - p['A_0']).dropna()
                    cells.append(fmt(*L.t_ci(d)) if len(d) else '-')
                if any(c != '-' for c in cells):
                    md.append(f'| {v} | {label} | ' + ' | '.join(cells) + ' |')

        md += ['', '## H2 — distributed vs central leakage (shadow-model AUC, site mean − A)', '',
               '| variant | B1 sites − A | A′ − A (size only) | B2 sites − A |', '|---|---|---|---|']
        for v in L.VARIANTS:
            s = at[at.variant == v].pivot_table(index='seed', columns='target', values='shadow_auc')
            if 'A_0' not in s:
                continue
            b1 = s[L.site_names('B1')].mean(1) - s['A_0'] if all(c in s for c in L.site_names('B1')) else pd.Series(dtype=float)
            ap_ = s['Aprime_0'] - s['A_0'] if 'Aprime_0' in s else pd.Series(dtype=float)
            b2 = s[L.site_names('B2')].mean(1) - s['A_0'] if all(c in s for c in L.site_names('B2')) else pd.Series(dtype=float)
            md.append(f'| {v} | {fmt(*L.t_ci(b1))} | {fmt(*L.t_ci(ap_))} | {fmt(*L.t_ci(b2))} |')

    if ut is not None:
        md += ['', '## Utility on the common validation set', '',
               '| variant | target | AUROC | scaled Brier | cal. intercept | cal. slope |', '|---|---|---|---|---|---|']
        for v in L.VARIANTS:
            for t in ORDER:
                s = ut[(ut.variant == v) & (ut.target == t)]
                if not s.empty:
                    md.append(f'| {v} | {t} | {fmt(*L.t_ci(s.auroc))} | {fmt(*L.t_ci(s.scaled_brier))} | '
                              f'{fmt(*L.t_ci(s.cal_intercept), d=2)} | {fmt(*L.t_ci(s.cal_slope), d=2)} |')
        md += ['', '## H3 — combined model vs central (ΔAUROC, non-inferiority margin −0.02)', '',
               '| variant | target | ΔAUROC | non-inferior |', '|---|---|---|---|']
        for v in L.VARIANTS:
            for t in L.COMBINED:
                s = ut[(ut.variant == v) & (ut.target == t)]
                if not s.empty and 'delta_auc_vs_A' in s:
                    m, lo, hi = L.t_ci(s.delta_auc_vs_A)
                    md.append(f'| {v} | {t} | {fmt(m, lo, hi)} | {yn(chk(lo, ">", -0.02))} |')
        fed = ut[ut.target.isin(list(L.FEDERATED))]
        if not fed.empty:
            md += ['', '## H5 — federated model (F) vs central model (A)', '',
                   '| variant | target | ΔAUROC (F − A) | non-inferior | shadow AUC F | shadow AUC A | shadow AUC sites (mean) | F ≤ A + 0.01 and F < sites (means; the pre-specified test is in the decision rules) |',
                   '|---|---|---|---|---|---|---|---|']
            for v in L.VARIANTS:
                for t, parts in L.FEDERATED.items():
                    s = fed[(fed.variant == v) & (fed.target == t)]
                    if s.empty:
                        continue
                    m, lo, hi = L.t_ci(s.delta_auc_vs_A)
                    sh_f = sh_a = sh_s = np.nan
                    if at is not None:
                        pv = at[at.variant == v].pivot_table(index='seed', columns='target', values='shadow_auc')
                        if t in pv and 'A_0' in pv and all(q in pv for q in parts):
                            sh_f, sh_a, sh_s = pv[t].mean(), pv['A_0'].mean(), pv[list(parts)].mean(1).mean()
                    ok = ('yes' if (sh_f <= sh_a + 0.01 and sh_f < sh_s) else 'no') if not np.isnan(sh_f) else '-'
                    md.append(f'| {v} | {t} | {fmt(m, lo, hi)} | {yn(chk(lo, ">", -0.02))} | '
                              f'{sh_f:.3f} | {sh_a:.3f} | {sh_s:.3f} | {ok} |')

    if sc is not None:
        from scipy import stats
        md += ['', '## H6 — exposure against training size (shadow-model AUC; one target per seed and size)', '']
        for v in sorted(sc.variant.unique()):
            q = sc[sc.variant == v]
            sizes = sorted(q.n_train.unique())
            piv = q.pivot_table(index='seed', columns='n_train', values='shadow_auc')
            means = [piv[m].mean() for m in sizes]
            slopes = [np.polyfit(np.log10(sizes), piv.loc[s, sizes].to_numpy(float), 1)[0]
                      for s in piv.index if not piv.loc[s, sizes].isna().any()]
            rho = stats.spearmanr(sizes, means)[0] if len(sizes) > 2 else np.nan
            md += [f'{v}: Spearman ρ (size, seed-mean AUC) = {rho:.2f}; slope per log10(n) = {fmt(*L.t_ci(slopes))}', '',
                   '| n train | ' + ' | '.join(f'{m:,}' for m in sizes) + ' |', '|---|' + '---|' * len(sizes),
                   '| shadow AUC | ' + ' | '.join(fmt(*L.t_ci(piv[m])) for m in sizes) + ' |',
                   '| val AUROC | ' + ' | '.join(fmt(*L.t_ci(q[q.n_train == m].val_auroc)) for m in sizes) + ' |', '']

    if sg is not None:
        fam = 'xgb_' if any(v.startswith('xgb_') for v in L.VARIANTS) else ''
        md += ['', f'## Subgroup LiRA AUC ({fam}krcp, A_0; groups ≥ 100 in the evaluation sample)', '',
               '| subgroup | level | LiRA AUC | shadow AUC |', '|---|---|---|---|']
        s = sg[(sg.variant == fam + 'krcp') & (sg.target == 'A_0')]
        for (g, lvl), q in s.groupby(['subgroup', 'level']):
            md.append(f'| {g} | {lvl} | {fmt(*L.t_ci(q.lira_auc))} | {fmt(*L.t_ci(q.shadow_auc))} |')

    if g1 is not None:
        md += ['', '## Gate 1 — code-free formats (XGB JSON, LGBM text, CatBoost CBM, RF tree JSON; no pickle on load)', '',
               '| variant | target | max abs Δp | label agreement | size (kB) |', '|---|---|---|---|---|']
        for _, r in g1.iterrows():
            md.append(f'| {r.variant} | {r.target} | {r.max_abs_dp:.1e} | {r.label_agree:.4f} | {r.bytes_total / 1024:,.0f} |')
    if lf is not None:
        comps = [c for c in ('xgb', 'lgb', 'cat', 'rf') if c in set(lf.component)]
        md += ['', 'Leaf audit — share of leaves with < 11 training people:', '',
               '| variant | target | ' + ' | '.join(comps) + ' |', '|---|---|' + '---|' * len(comps)]
        for (v, t), q in lf.groupby(['variant', 'target']):
            d = dict(zip(q.component, q.share_leaves_lt11))
            md.append(f'| {v} | {t} | ' + ' | '.join(f'{d.get(c, np.nan):.1%}' for c in comps) + ' |')
    if g3 is not None:
        md += ['', '## Gate 3 — escrow re-execution', '',
               '| variant | target | signature | data hash | versions | abs ΔAUROC | max abs Δp | pass |',
               '|---|---|---|---|---|---|---|---|']
        for _, r in g3.iterrows():
            md.append(f'| {r.variant} | {r.target} | {r.signature_valid} | {r.data_hash_equal} | {r.versions_equal} | '
                      f'{r.abs_delta_auroc:.1e} | {r.max_abs_dp:.1e} | {r.gate3_pass} |')

    path = os.path.join(od, '06_summary.md')
    open(path, 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    print('done ->', os.path.relpath(path, L.BASE))


if __name__ == '__main__':
    L.guard(main)
