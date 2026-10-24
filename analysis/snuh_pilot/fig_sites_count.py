# -*- coding: utf-8 -*-
"""Federated accuracy and exposure against the number of real hospitals (eICU-CRD: 3 largest, 3 of unequal size, all 14 with
at least 2,000 analysis rows). Inputs are aggregates only: analysis/federated/out/eicu_<tag>/fl_B1_s<seed>_<config>.json
(AUROC of A_x, B_k, B_avg, F per seed) and analysis/snuh_pilot/out/eicu_<tag>_xgb/03_attacks_long.csv (attack metrics per
seed and target). A cohort whose files are missing is drawn as 'not run'.

Fig7_sites_count   a: F - A (seed mean, t-based 95% interval) for the three configurations;
                   b: site model minus central model, one open marker per hospital (seed means), with the averaged site
                      predictions and the federated model;
                   c: shadow-model attack AUC of the central, federated, averaged and site models (published configuration).

    python fig_sites_count.py [--out DIR]
"""
import argparse
import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figures as F  # noqa: E402
import pilot_lib as L  # noqa: E402

COHORTS = [('3 largest' + chr(10) + '(h3a)', 'eicu_h3a', 3), ('3 unequal' + chr(10) + '(h3b)', 'eicu_h3b', 3), ('all 14' + chr(10) + '(h14)', 'eicu_h14', 14)]
CONFIGS = [('krcp', 'published', 'o', 'k'), ('regularized', 'regularized', 's', 'none'), ('plain', 'no sampling', 'D', '0.6')]
FED_OUT = os.path.join(L.BASE, 'analysis', 'federated', 'out')


def fed_rows(tag):
    rows = []
    for p in sorted(glob.glob(os.path.join(glob.escape(os.path.join(FED_OUT, tag)), 'fl_B1_s*_*.json'))):
        d = json.load(open(p, encoding='utf-8'))
        arms = d['arms']
        sites = sorted(k for k in arms if re.fullmatch(r'B_\d+', k))
        rows.append({'seed': d['seed'], 'config': d['config'], 'A': arms['A_x']['auroc'], 'F': arms['F']['auroc'],
                     'B_avg': arms['B_avg']['auroc'], 'sites': {k: arms[k]['auroc'] for k in sites},
                     'n_sites': {k: int(str(arms[k]['n_train']).replace(',', '')) for k in sites}})
    return rows


def attacks(tag, variant='xgb_krcp', metric='shadow_auc'):
    p = os.path.join(L.OUT_ROOT, tag + '_xgb', '03_attacks_long.csv')
    if not os.path.exists(p):
        return None
    at = pd.read_csv(p)
    at = at[at.variant == variant]
    return at.groupby('target')[metric].mean() if not at.empty else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(L.BASE, 'Figures', 'v2', 'cross_cohort'))
    a = ap.parse_args()
    plt = F.style()
    fig, ax = plt.subplots(1, 3, figsize=(7.2, 2.7))
    x = np.arange(len(COHORTS))
    for j, (name, tag, k) in enumerate(COHORTS):
        rows = fed_rows(tag)
        at = attacks(tag)
        if not rows:
            ax[0].text(x[j], -0.006, 'not run', ha='center', va='center', fontsize=6.5, rotation=90)
            ax[1].text(x[j], -0.02, 'not run', ha='center', va='center', fontsize=6.5, rotation=90)
            ax[2].text(x[j], 0.58, 'not run', ha='center', va='center', fontsize=6.5, rotation=90)
            continue
        # a: F - A per configuration
        for c, (cfg, _, m, face) in enumerate(CONFIGS):
            d = np.array([r['F'] - r['A'] for r in rows if r['config'] == cfg])
            if d.size == 0:
                continue
            mean, lo, hi = L.t_ci(pd.Series(d)) if d.size > 1 else (d[0], np.nan, np.nan)
            xx = x[j] + (c - 1) * 0.22
            ax[0].plot([xx], [mean], marker=m, color='k', mfc=face, ms=5, ls='none', zorder=3)
            if not np.isnan(lo) and hi > lo:
                ax[0].plot([xx, xx], [lo, hi], color='k', lw=1)
        # b: site models minus central (published configuration), seed means per hospital
        kr = [r for r in rows if r['config'] == 'krcp']
        if kr:
            for s in sorted(kr[0]['sites']):
                d = np.mean([r['sites'][s] - r['A'] for r in kr if s in r['sites']])
                ax[1].plot([x[j]], [d], marker='^', color='k', mfc='none', ms=5, ls='none', zorder=3)
            ax[1].plot([x[j]], [np.mean([r['B_avg'] - r['A'] for r in kr])], marker='D', color='k', ms=5, ls='none', zorder=4)
            ax[1].plot([x[j]], [np.mean([r['F'] - r['A'] for r in kr])], marker='*', color='k', ms=9, ls='none', zorder=4)
        # c: exposure of every route (published configuration)
        if at is not None:
            for t in at.index:
                if re.fullmatch(r'B1_\d+', t):
                    ax[2].plot([x[j]], [at[t]], marker='^', color='k', mfc='none', ms=5, ls='none', zorder=3)
            if 'A_0' in at:
                ax[2].plot([x[j]], [at['A_0']], marker='o', color='k', ms=5, ls='none', zorder=4)
            if 'F_B1' in at:
                ax[2].plot([x[j]], [at['F_B1']], marker='*', color='k', ms=9, ls='none', zorder=4)
            if 'B1_comb' in at:
                ax[2].plot([x[j]], [at['B1_comb']], marker='D', color='k', ms=5, ls='none', zorder=4)
    for i, a_ in enumerate(ax):
        a_.set_xticks(x)
        a_.set_xticklabels([c[0] for c in COHORTS], fontsize=6.5)
        a_.set_xlim(-0.6, len(COHORTS) - 0.4)
        a_.set_xlabel('eICU-CRD hospitals as sites', fontsize=7)
        a_.tick_params(axis='y', labelsize=7)
        a_.text(-0.08, 1.04, 'abc'[i], transform=a_.transAxes, fontsize=8, fontweight='bold', ha='right')
    ax[0].axhline(0, color='0.5', lw=0.7)
    ax[0].axhline(-0.02, color='k', lw=0.7, ls=':')
    ax[0].set_ylabel('federated minus central AUROC', fontsize=7)
    ax[0].set_ylim(-0.025, 0.012)
    ax[1].axhline(0, color='0.5', lw=0.7)
    ax[1].set_ylabel('AUROC minus central model', fontsize=7)
    ax[2].axhline(L.GATE2_THRESHOLD, color='k', lw=0.7, ls=':')
    ax[2].axhline(0.5, color='0.6', lw=0.5)
    ax[2].set_ylabel('shadow-model attack AUC', fontsize=7)
    h = [plt.Line2D([], [], marker='o', color='k', ls='none', ms=5, label='published configuration (a); central model (c)'),
         plt.Line2D([], [], marker='s', color='k', mfc='none', ls='none', ms=5, label='regularized configuration (a)'),
         plt.Line2D([], [], marker='D', color='k', mfc='0.6', ls='none', ms=5, label='no sampling (a)'),
         plt.Line2D([], [], marker='^', color='k', mfc='none', ls='none', ms=5, label='site model, one per hospital (b, c)'),
         plt.Line2D([], [], marker='D', color='k', ls='none', ms=5, label='averaged site predictions (b, c)'),
         plt.Line2D([], [], marker='*', color='k', ls='none', ms=8, label='federated (b, c)')]
    fig.legend(handles=h, loc='lower center', ncol=3, fontsize=6.5, bbox_to_anchor=(0.5, -0.1), frameon=False)
    fig.tight_layout()
    F.save(fig, a.out, 'Fig7_sites_count')


if __name__ == '__main__':
    main()
