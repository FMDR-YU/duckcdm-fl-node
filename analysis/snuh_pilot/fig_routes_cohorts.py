# -*- coding: utf-8 -*-
"""Cross-cohort figures for the manuscript, from the pilot aggregates (01_utility_long.csv, 03_attacks_long.csv,
03b_size_curve_long.csv of each cohort). No patient-level data.

Fig3_routes_cohorts        AUROC of each route minus the central model (A), per cohort and configuration, with the
                           non-inferiority margin; t-based 95% intervals over seeds.
Fig4_exposure_vs_size_cohorts   shadow-model attack AUC against training size (same model, size varied) with the routes
                           A, A' (size control), site models and federated placed at their training sizes; published configuration.

    python fig_routes_cohorts.py [--out DIR]
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figures as F  # noqa: E402
import pilot_lib as L  # noqa: E402

# (label, out folder, site scenario used for the sites / averaged / federated rows)
COHORTS = [('SynPUF, equal thirds (B1)', 'synpuf_xgb', 'B1'),
           ('SynPUF, 50/30/20 (B2)', 'synpuf_xgb', 'B2'),
           ('eICU-CRD, 3 largest hospitals', 'eicu_h3a_xgb', 'B1'),
           ('eICU-CRD, hospitals of unequal size', 'eicu_h3b_xgb', 'B1'),
           ('SNUH CDM, equal thirds (B1)', 'snuh_cdmv_xgb', 'B1'),
           ('SNUH CDM, 50/30/20 (B2)', 'snuh_cdmv_xgb', 'B2')]
VARIANTS = [('xgb_krcp', 'published configuration'), ('xgb_regularized', 'regularized configuration')]
ROWS = [('A′ size control', 's', False), ('site models (mean)', '^', False), ('averaged site predictions', 'D', True), ('federated', '*', True)]


def rd(folder, f):
    p = os.path.join(L.OUT_ROOT, folder, f)
    return pd.read_csv(p) if os.path.exists(p) else None


def route_deltas(ut, variant, scn):
    """Per-seed AUROC differences to A for the four routes; NaN rows when a route is missing (e.g. no F_B2 on eICU)."""
    p = ut[ut.variant == variant].pivot_table(index='seed', columns='target', values='auroc')
    out = {}
    out[ROWS[0][0]] = p['Aprime_0'] - p['A_0'] if 'Aprime_0' in p else None
    site_cols = [c for c in p.columns if c.startswith(f'{scn}_') and c[len(scn) + 1:].isdigit()]
    out[ROWS[1][0]] = p[site_cols].mean(axis=1) - p['A_0']
    out[ROWS[2][0]] = p[f'{scn}_comb'] - p['A_0'] if f'{scn}_comb' in p else None
    out[ROWS[3][0]] = p[f'F_{scn}'] - p['A_0'] if f'F_{scn}' in p else None
    return out


def fig_routes(out):
    plt = F.style()
    k = len(COHORTS)
    fig, ax = plt.subplots(len(VARIANTS), k, figsize=(2.3 * k + 1.5, 1.9 * len(VARIANTS) + 0.5), sharex=True, sharey=True)
    ax = np.atleast_2d(ax)
    for i, (variant, vlabel) in enumerate(VARIANTS):
        for j, (name, folder, scn) in enumerate(COHORTS):
            a = ax[i, j]
            ut = rd(folder, '01_utility_long.csv')
            if ut is None or ut[ut.variant == variant].empty:
                a.text(0.5, 0.5, 'no data', transform=a.transAxes, ha='center', va='center', fontsize=7)
            else:
                d = route_deltas(ut, variant, scn)
                for r, (label, m, filled) in enumerate(ROWS):
                    s = d[label]
                    if s is None or s.dropna().empty:
                        continue
                    mean, lo, hi = L.t_ci(s.dropna())
                    a.plot([mean], [r], marker=m, color='k', mfc='k' if filled else 'none', ms=6 if m != '*' else 9, ls='none', zorder=3)
                    if not np.isnan(lo):
                        a.plot([lo, hi], [r, r], color='k', lw=1)
            a.axvline(0, color='0.5', lw=0.7)
            a.axvline(-L.NI_MARGIN if hasattr(L, 'NI_MARGIN') else -0.02, color='k', lw=0.7, ls=':')
            a.set_title((name + '\n' if i == 0 else '') + vlabel, fontsize=7, loc='left')
            if i == len(VARIANTS) - 1:
                a.set_xlabel('AUROC minus central model', fontsize=7)
            a.set_yticks(range(len(ROWS)))
            a.set_yticklabels([r[0] for r in ROWS], fontsize=7)
            a.tick_params(axis='x', labelsize=7)
            a.text(-0.02, 1.02, 'abcdefghijklmnop'[i * k + j], transform=a.transAxes, fontsize=8, fontweight='bold', ha='right')
    ax[0, 0].set_xlim(-0.046, 0.012)
    ax[0, 0].invert_yaxis()
    ax[-1, 0].set_xlabel('AUROC minus central model\n(dotted line: non-inferiority margin −0.02)', fontsize=7)
    fig.tight_layout()
    F.save(fig, out, 'Fig3_routes_cohorts')


def fig_size(out, variant='xgb_krcp'):
    plt = F.style()
    from matplotlib.ticker import NullFormatter, ScalarFormatter
    cohorts = [c for c in COHORTS if c[2] == 'B1']          # one panel per cohort; B2 shares the size curve of its cohort
    k = len(cohorts)
    fig, ax = plt.subplots(1, k, figsize=(2.6 * k + 0.5, 2.9), sharey=True)
    ax = np.atleast_1d(ax)
    for j, (name, folder, scn) in enumerate(cohorts):
        a = ax[j]
        at, sc = rd(folder, '03_attacks_long.csv'), rd(folder, '03b_size_curve_long.csv')
        if sc is not None and not sc[sc.variant == variant].empty:
            q = sc[sc.variant == variant]
            sizes = sorted(q.n_train.unique())
            piv = q.pivot_table(index='seed', columns='n_train', values='shadow_auc')
            mean = [piv[n].mean() for n in sizes]
            ci = [L.t_ci(piv[n]) for n in sizes]
            a.plot(sizes, mean, color='k', lw=1)
            a.fill_between(sizes, [c[1] for c in ci], [c[2] for c in ci], color='0.85', lw=0)
        if at is not None:
            for t, m, face, ms in (('A_0', 'o', 'k', 5.5), ('Aprime_0', 's', 'none', 5.5), (f'{scn}_0', '^', 'none', 5.5), (f'{scn}_1', '^', 'none', 5.5),
                                   (f'{scn}_2', '^', 'none', 5.5), (f'F_{scn}', '*', 'k', 9)):
                s = at[(at.variant == variant) & (at.target == t)]
                if s.empty:
                    continue
                a.plot([s.n_members.mean()], [s.shadow_auc.mean()], marker=m, color='k', mfc=face, ms=ms, ls='none', zorder=3)
        a.axhline(L.GATE2_THRESHOLD, color='k', lw=0.7, ls=':')
        a.axhline(0.5, color='0.6', lw=0.5)
        a.set_xscale('log')
        a.set_xticks([2000, 5000, 10000, 20000])
        a.xaxis.set_major_formatter(ScalarFormatter())
        a.xaxis.set_minor_formatter(NullFormatter())
        a.tick_params(labelsize=7)
        a.set_xlabel('training patients', fontsize=7)
        a.set_title(name, fontsize=7, loc='left')
        a.text(-0.02, 1.02, 'abcdefgh'[j], transform=a.transAxes, fontsize=8, fontweight='bold', ha='right')
    ax[0].set_ylabel('shadow-model attack AUC', fontsize=7)
    ax[0].text(2100, L.GATE2_THRESHOLD + 0.003, f'pilot rule {L.GATE2_THRESHOLD}', fontsize=6, va='bottom')
    h = [plt.Line2D([], [], color='k', lw=1, label='central model, training size varied (95% interval over seeds)'),
         plt.Line2D([], [], marker='o', color='k', ls='none', ms=5, label='A central'),
         plt.Line2D([], [], marker='s', color='k', mfc='none', ls='none', ms=5, label='A′ size control'),
         plt.Line2D([], [], marker='^', color='k', mfc='none', ls='none', ms=5, label='site models'),
         plt.Line2D([], [], marker='*', color='k', ls='none', ms=8, label='federated')]
    fig.legend(handles=h, loc='lower center', ncol=3, fontsize=6.5, bbox_to_anchor=(0.5, -0.09), frameon=False)
    fig.tight_layout()
    F.save(fig, out, 'Fig4_exposure_vs_size_cohorts')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(L.BASE, 'Figures', 'v2', 'cross_cohort'))
    a = ap.parse_args()
    fig_routes(a.out)
    fig_size(a.out)


if __name__ == '__main__':
    main()
