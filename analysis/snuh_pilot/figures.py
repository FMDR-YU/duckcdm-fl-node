# -*- coding: utf-8 -*-
"""Manuscript figures from the pilot aggregates (out/<ds>/*.csv). Aggregates only; no patient-level data is read.

    python figures.py --dataset synpuf --model xgb                  -> Figures/v2/synpuf_xgb/
    python figures.py --dataset snuh --tag cdm --model xgb          -> Figures/v2/snuh_cdm_xgb/

Fig 2  utility: AUROC difference to the central model by route (forest plot, seed t intervals)
Fig 3  exposure: shadow-model attack AUC by route against the release threshold
Fig 4  exposure against training size, with the routes placed at their own training size
Fig S3 LiRA true-positive rate at 1% false-positive rate by route
Fig 5  planted canaries: tail exposure against the audit quantities (141 cells)
Fig S4 canary TPR of the same cells under flipped-label and synthetic canaries

Grey-scale safe: markers and line styles carry the meaning, not colour. PNG (300 dpi) and PDF are written.
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROUTES = [('A_0', 'A central'), ('Aprime_0', 'A′ size control'),
          ('B1_0', 'B1 site 1'), ('B1_1', 'B1 site 2'), ('B1_2', 'B1 site 3'), ('B1_comb', 'B1 averaged'), ('F_B1', 'B1 federated'),
          ('B2_0', 'B2 site 1'), ('B2_1', 'B2 site 2'), ('B2_2', 'B2 site 3'), ('B2_comb', 'B2 averaged'), ('F_B2', 'B2 federated')]
MARK = {'A_0': ('o', 'k'), 'Aprime_0': ('s', 'none'), 'B1_comb': ('D', 'k'), 'B2_comb': ('D', 'k'), 'F_B1': ('*', 'k'), 'F_B2': ('*', 'k')}
SITE_MARK = ('^', 'none')
SIZE_ORDER = [2000, 5000, 10000]


def mark(t):
    return MARK.get(t, SITE_MARK)


def style():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 8, 'axes.linewidth': 0.7, 'axes.spines.top': False, 'axes.spines.right': False,
                         'xtick.major.width': 0.7, 'ytick.major.width': 0.7, 'legend.frameon': False, 'figure.dpi': 120})
    return plt


def save(fig, out, name):
    os.makedirs(out, exist_ok=True)
    for ext, kw in (('png', {'dpi': 300}), ('pdf', {})):
        fig.savefig(os.path.join(out, f'{name}.{ext}'), bbox_inches='tight', **kw)
    print('  wrote', os.path.join(os.path.relpath(out, os.path.dirname(os.path.dirname(HERE))), name + '.png'))


def fig_utility(L, ut, out, variants):
    plt = style()
    piv = ut.pivot_table(index=['variant', 'seed'], columns='target', values='auroc')
    rows = [('A′ size control', lambda p: p['Aprime_0'] - p['A_0'], 's')]
    for s in ('B1', 'B2'):
        rows += [(f'{s} site models (mean of 3)', (lambda p, s=s: p[[f'{s}_0', f'{s}_1', f'{s}_2']].mean(axis=1) - p['A_0']), '^'),
                 (f'{s} averaged predictions', (lambda p, s=s: p[f'{s}_comb'] - p['A_0']), 'D'),
                 (f'{s} federated', (lambda p, s=s: p[f'F_{s}'] - p['A_0']), '*')]
    fig, axes = plt.subplots(1, len(variants), figsize=(2.6 * len(variants) + 1.6, 2.8), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, v in zip(axes, variants):
        p = piv.loc[v]
        for i, (label, fn, m) in enumerate(rows):
            try:
                d = fn(p).dropna()
            except KeyError:
                continue
            if d.empty:
                continue
            mean, lo, hi = L.t_ci(d)
            ax.plot([mean], [i], marker=m, color='k', mfc='k' if m in ('D', '*') else 'none', ms=6 if m != '*' else 8, ls='none')
            if not np.isnan(lo):
                ax.plot([lo, hi], [i, i], color='k', lw=1)
        ax.axvline(0, color='0.5', lw=0.7)
        ax.axvline(-0.02, color='k', lw=0.7, ls=':')
        ax.set_title(v, fontsize=8)
        ax.set_xlabel('AUROC minus central model')
        ax.set_xlim(-0.025, 0.012)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([r[0] for r in rows])
        ax.invert_yaxis()
    axes[0].text(-0.0195, -0.42, 'non-inferiority\nmargin −0.02', fontsize=6.5, ha='left', va='top')
    fig.tight_layout()
    save(fig, out, 'Fig2_utility_forest')


def fig_exposure(L, at, out, variants, metric='shadow_auc', name='Fig3_exposure', ylabel='Shadow-model attack AUC', threshold=True):
    plt = style()
    routes = [r for r in ROUTES if not at[(at.variant.isin(variants)) & (at.target == r[0])].empty]   # e.g. no federated slots for the ensemble family
    fig, axes = plt.subplots(len(variants), 1, figsize=(5.2, 2.2 * len(variants)), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, v in zip(axes, variants):
        for i, (t, label) in enumerate(routes):
            s = at[(at.variant == v) & (at.target == t)]
            if s.empty:
                continue
            mean, lo, hi = L.t_ci(s[metric])
            m, face = mark(t)
            ax.plot([i], [mean], marker=m, color='k', mfc=face, ms=6 if m != '*' else 9, ls='none')
            if not np.isnan(lo):
                ax.plot([i, i], [lo, hi], color='k', lw=1)
        if threshold and metric == 'shadow_auc':
            ax.axhline(L.GATE2_THRESHOLD, color='k', lw=0.7, ls=':')
            ax.text(1.6, L.GATE2_THRESHOLD, f'release threshold {L.GATE2_THRESHOLD}', fontsize=6.5, va='top', ha='left')
        if metric == 'shadow_auc':
            ax.axhline(0.5, color='0.6', lw=0.5)
        ax.set_ylabel(ylabel)
        ax.set_title(v, fontsize=8, loc='left')
        if metric == 'lira_tpr1':
            ax.set_ylim(bottom=0)
    axes[-1].set_xticks(range(len(routes)))
    axes[-1].set_xticklabels([r[1] for r in routes], rotation=40, ha='right')
    fig.tight_layout()
    save(fig, out, name)


def fig_size(L, at, sc, out, variants):
    plt = style()
    from matplotlib.ticker import NullFormatter, ScalarFormatter
    variants = [v for v in variants if not sc[sc.variant == v].empty]      # only variants that have a size curve
    fig, axes = plt.subplots(1, len(variants), figsize=(2.7 * len(variants) + 0.4, 2.8), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, v in zip(axes, variants):
        q = sc[sc.variant == v]
        if not q.empty:
            sizes = sorted(q.n_train.unique())
            piv = q.pivot_table(index='seed', columns='n_train', values='shadow_auc')
            mean = [piv[n].mean() for n in sizes]
            ci = [L.t_ci(piv[n]) for n in sizes]
            ax.plot(sizes, mean, color='k', lw=1, ls='-')
            ax.fill_between(sizes, [c[1] for c in ci], [c[2] for c in ci], color='0.85', lw=0)
        for t, label in ROUTES:
            s = at[(at.variant == v) & (at.target == t)]
            if s.empty or t.endswith('comb'):
                continue
            m, face = mark(t)
            ax.plot([s.n_members.mean()], [s.shadow_auc.mean()], marker=m, color='k', mfc=face, ms=5.5 if m != '*' else 8, ls='none')
        ax.axhline(L.GATE2_THRESHOLD, color='k', lw=0.7, ls=':')
        ax.set_xscale('log')
        ax.set_xticks([2000, 5000, 10000, 20000])
        ax.xaxis.set_major_formatter(ScalarFormatter())
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlabel('training patients')
        ax.set_title(v, fontsize=8)
    axes[0].set_ylabel('Shadow-model attack AUC')
    h = [plt.Line2D([], [], color='k', lw=1, label='same model, training size varied'),
         plt.Line2D([], [], marker='o', color='k', ls='none', ms=5, label='A central'),
         plt.Line2D([], [], marker='s', color='k', mfc='none', ls='none', ms=5, label='A′ size control'),
         plt.Line2D([], [], marker='^', color='k', mfc='none', ls='none', ms=5, label='site models'),
         plt.Line2D([], [], marker='*', color='k', ls='none', ms=8, label='federated')]
    fig.legend(handles=h, loc='lower center', ncol=5, fontsize=6.5, bbox_to_anchor=(0.5, -0.07))
    fig.tight_layout()
    save(fig, out, 'Fig4_exposure_vs_size')


def fig_canary(L, cells, out):
    """Ground truth from planted canaries against the ordinary-row audit, one marker per cell (configuration x training size).
    Filled = the seven named settings, open = space-filling settings; marker shape = training size. a: tail exposure (canary TPR at
    1% FPR) against the shadow-model AUC of the release rule; b: against the ordinary-row LiRA TPR; c: against training rows."""
    plt = style()
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FixedLocator, NullFormatter, ScalarFormatter
    from scipy.stats import spearmanr
    import canary_benchmark as CB
    tau = CB.EXPOSED_TPR1
    shape = {2000: 'o', 6000: '^', 19746: 's'}
    named = ~cells.config.str.startswith('lhs').to_numpy()
    fig, ax = plt.subplots(1, 3, figsize=(7.4, 2.9), sharey=True)
    rng = np.random.default_rng(3)
    jit = np.exp(rng.uniform(-0.05, 0.05, len(cells)))
    for k, (xcol, xs) in enumerate((('shadow_auc', 1.0), ('lira_tpr1', 1.0), ('n', None))):
        for n, mk in shape.items():
            for isnamed in (True, False):
                m = (cells.n == n).to_numpy() & (named == isnamed)
                x = cells[xcol].to_numpy()[m] * (jit[m] if xcol == 'n' else 1.0)
                ax[k].scatter(x, cells.canary_tpr1.to_numpy()[m], marker=mk, s=15 if isnamed else 13, linewidths=0.7,
                              facecolors='k' if isnamed else 'none', edgecolors='k' if isnamed else '0.35', zorder=3 if isnamed else 2)
        ax[k].axhline(tau, color='k', ls='--', lw=0.6)
    rel = (cells.shadow_auc <= L.GATE2_THRESHOLD).to_numpy()
    exp = (cells.canary_tpr1 >= tau).to_numpy()
    ax[0].axvline(L.GATE2_THRESHOLD, color='k', ls=':', lw=0.7)
    ax[0].text(0.915, 0.02, f'released by the 0.55 rule\nand exposed: {int((rel & exp).sum())} of {int(rel.sum())} released cells', fontsize=6.2, ha='right', va='center')
    ax[0].set_xlim(0.49, 0.92)
    ax[0].set_xlabel('shadow-model AUC, ordinary rows')
    ax[0].set_ylabel('canary TPR at 1% FPR (known leakage)')
    c = CB.calibrate(cells.lira_tpr1.to_numpy(float), exp, CB.CALIB_SENS)
    if np.isfinite(c):
        ax[1].axvline(c, color='k', ls=':', lw=0.7)
        ax[1].text(c * 1.07, 0.015, f'calibrated\nthreshold {c:.3f}', fontsize=6.2, ha='left', va='bottom')
    ax[1].set_xscale('log')
    ax[1].set_xlabel('LiRA TPR at 1% FPR, ordinary rows')
    ax[1].xaxis.set_major_locator(FixedLocator([0.01, 0.03, 0.1, 0.3]))
    ax[1].xaxis.set_major_formatter(ScalarFormatter())
    ax[1].xaxis.set_minor_formatter(NullFormatter())
    ax[2].set_xscale('log')
    ax[2].set_xticks([2000, 6000, 19746])
    ax[2].xaxis.set_major_formatter(ScalarFormatter())
    ax[2].xaxis.set_minor_formatter(NullFormatter())
    ax[2].set_xlabel('training rows')
    rho = spearmanr(cells.n, cells.canary_tpr1)[0]
    ax[2].text(2350, 0.013, f'Spearman {rho:.2f}', fontsize=6.2, ha='left', va='bottom')
    for a_ in ax:
        a_.set_yscale('log')
        a_.set_ylim(0.012, 1.15)
        a_.yaxis.set_major_locator(FixedLocator([0.01, 0.03, 0.1, 0.3, 1.0]))
        a_.yaxis.set_major_formatter(ScalarFormatter())
        a_.yaxis.set_minor_formatter(NullFormatter())
    ax[0].text(0.915, tau * 1.08, f'exposed: ≥ {tau:g}', fontsize=6.2, ha='right', va='bottom')
    h = [Line2D([], [], marker=mk, ls='', mfc='none', mec='k', ms=4, label=f'{n:,} rows') for n, mk in shape.items()]
    h += [Line2D([], [], marker='o', ls='', mfc='k', mec='k', ms=4, label='named settings'),
          Line2D([], [], marker='o', ls='', mfc='none', mec='0.35', ms=4, label='space-filling settings')]
    fig.legend(handles=h, fontsize=6.5, loc='lower center', ncol=5, bbox_to_anchor=(0.5, -0.07), handletextpad=0.2, columnspacing=1.2)
    for a_, t in zip(ax, 'abc'):
        a_.set_title(t, loc='left', fontsize=8, fontweight='bold')
    fig.tight_layout()
    save(fig, out, 'Fig5_canary_tail_vs_average')


def fig_canary_types(L, a, b, out):
    """Does the canary type change the ground truth? Canary TPR at 1% FPR of the same cell under flipped-label canaries (a) and
    synthetic canaries (b). Filled = named settings, open = space-filling settings; marker shape = training size."""
    plt = style()
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FixedLocator, NullFormatter, ScalarFormatter
    from scipy.stats import spearmanr
    import canary_benchmark as CB
    tau = CB.EXPOSED_TPR1
    m = a.merge(b, on=['config', 'n'], suffixes=('_flip', '_shuffle')).reset_index(drop=True)
    shape = {2000: 'o', 6000: '^', 19746: 's'}
    named = ~m.config.str.startswith('lhs').to_numpy()
    fig, ax = plt.subplots(figsize=(3.5, 3.4))
    for n, mk in shape.items():
        for isnamed in (True, False):
            sel = (m.n == n).to_numpy() & (named == isnamed)
            ax.scatter(m.canary_tpr1_flip[sel], m.canary_tpr1_shuffle[sel], marker=mk, s=15 if isnamed else 13, linewidths=0.7,
                       facecolors='k' if isnamed else 'none', edgecolors='k' if isnamed else '0.35', zorder=3 if isnamed else 2)
    lim = (0.012, 1.15)
    ax.plot(lim, lim, color='k', lw=0.6, ls=':')
    ax.axhline(tau, color='k', ls='--', lw=0.6)
    ax.axvline(tau, color='k', ls='--', lw=0.6)
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_locator(FixedLocator([0.01, 0.03, 0.1, 0.3, 1.0]))
        axis.set_major_formatter(ScalarFormatter())
        axis.set_minor_formatter(NullFormatter())
    e1, e2 = (m.canary_tpr1_flip >= tau).to_numpy(), (m.canary_tpr1_shuffle >= tau).to_numpy()
    ax.text(0.0135, 0.55, f'Spearman {spearmanr(m.canary_tpr1_flip, m.canary_tpr1_shuffle)[0]:.2f}\nexposed under both: {int((e1 & e2).sum())}\n'
                          f'only flipped: {int((e1 & ~e2).sum())}, only synthetic: {int((~e1 & e2).sum())}', fontsize=6.2, ha='left', va='center')
    ax.set_xlabel('canary TPR at 1% FPR, flipped-label canaries')
    ax.set_ylabel('canary TPR at 1% FPR, synthetic canaries')
    h = [Line2D([], [], marker=mk, ls='', mfc='none', mec='k', ms=4, label=f'{n:,} rows') for n, mk in shape.items()]
    h += [Line2D([], [], marker='o', ls='', mfc='k', mec='k', ms=4, label='named'), Line2D([], [], marker='o', ls='', mfc='none', mec='0.35', ms=4, label='space-filling')]
    fig.legend(handles=h, fontsize=6, loc='lower center', ncol=3, bbox_to_anchor=(0.5, -0.1), handletextpad=0.2, columnspacing=1.0)
    fig.tight_layout()
    save(fig, out, 'FigS4_canary_types')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', required=True)
    ap.add_argument('--tag', default='')
    ap.add_argument('--model', choices=['ensemble', 'xgb'], default='xgb')
    ap.add_argument('--out', default='')
    ap.add_argument('--variants', default='', help='comma list; default = all variants of the family')
    a = ap.parse_args()
    os.environ['PILOT_MODEL'] = a.model
    if a.tag:
        os.environ['PILOT_TAG'] = a.tag
    import pilot_lib as L

    od = L.out_dir(a.dataset)
    rd = lambda f: pd.read_csv(os.path.join(od, f)) if os.path.exists(os.path.join(od, f)) else None  # noqa: E731
    ut, at, sc = rd('01_utility_long.csv'), rd('03_attacks_long.csv'), rd('03b_size_curve_long.csv')
    variants = [v for v in (a.variants.split(',') if a.variants else L.VARIANTS) if v in L.VARIANTS]
    out = a.out or os.path.join(L.BASE, 'Figures', 'v2', L.tag(a.dataset))
    print('figures from', os.path.relpath(od, L.BASE))
    if ut is not None:
        fig_utility(L, ut, out, variants)
    if at is not None:
        fig_exposure(L, at, out, variants)
        fig_exposure(L, at, out, variants, metric='lira_tpr1', name='FigS3_lira_tpr_at_1pct_fpr', ylabel='LiRA true-positive rate at 1% FPR', threshold=False)
    if at is not None and sc is not None:
        fig_size(L, at, sc, out, variants)
    import glob
    cf = sorted(glob.glob(os.path.join(glob.escape(od + '_canary'), 'canary_cells*.csv')))
    if cf:
        flip = pd.concat([pd.read_csv(f) for f in cf]).drop_duplicates(['config', 'n'], keep='last')
        fig_canary(L, flip, out)
        sf = sorted(glob.glob(os.path.join(glob.escape(od + '_canary_shuffle'), 'canary_cells*.csv')))
        if sf:
            fig_canary_types(L, flip, pd.concat([pd.read_csv(f) for f in sf]).drop_duplicates(['config', 'n'], keep='last'), out)


if __name__ == '__main__':
    main()
