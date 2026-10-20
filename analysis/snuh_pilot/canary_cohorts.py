# -*- coding: utf-8 -*-
"""Canary benchmark across cohorts: one set of tables from the cell files of every cohort that has been run.

For each cohort (cells of canary_benchmark.py, flipped-label canaries): how well each audit quantity tells exposed cells from
unexposed ones, what the prescribed release rule (shadow-model AUC <= 0.55) lets through, and what the thresholds calibrated on the
development cohort (the first cohort, SynPUF) do when applied unchanged. Aggregates only; reads the cell files and writes one
markdown file.

    python canary_cohorts.py [--tau 0.10] [--boot 2000] [--out out/canary_cross_cohort.md]
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('PILOT_MODEL', 'xgb')
import canary_benchmark as CB  # noqa: E402
import pilot_lib as L  # noqa: E402

COHORTS = [('SynPUF (development)', 'synpuf_xgb_canary'), ('MIMIC-IV-ED', 'mimic_ed_s28k_xgb_canary'), ('eICU-CRD', 'eicu_s28k_xgb_canary'),
           ('eICU-CRD, 3 real hospitals (largest)', 'eicu_h3a_xgb_canary'), ('eICU-CRD, 3 real hospitals (sizes apart)', 'eicu_h3b_xgb_canary')]   # the last two: real hospitals as sites (2026-10-19); cohorts without cell files are skipped
FIXED = ('lira_tpr1', 'lira_auc', 'shadow_auc')          # quantities whose development thresholds are applied unchanged


def load(out_root, folder):
    fs = sorted(glob.glob(os.path.join(glob.escape(os.path.join(out_root, folder)), 'canary_cells*.csv')))
    if not fs:
        return None
    return pd.concat([pd.read_csv(f) for f in fs]).drop_duplicates(['config', 'n'], keep='last').sort_values(['config', 'n']).reset_index(drop=True)


def ci(lo, hi, k=2):
    return CB._ci(lo, hi, k)


def tables(cohorts, thr, tau, n_boot):
    """cohorts = [(name, cell table)] -> markdown lines."""
    md = ['# Canary benchmark across cohorts', '',
          f'Exposed cell = canary TPR at 1% FPR of at least {tau:g}. Intervals are 95% percentile intervals over {n_boot:,} resamples of whole '
          f'configurations. The development cohort is the first one; its thresholds (target sensitivity {thr["target_sensitivity"]:.0%}) are applied '
          f'unchanged to the others.', '']
    stats = {}
    for name, df in cohorts:
        point = CB.p1_stats(df, tau)
        keys = list(point)

        def stat(idx, df=df, keys=keys):
            r = CB.p1_stats(df.iloc[idx], tau)
            return [r[k] for k in keys]

        lo, hi, _ = CB.boot_clusters(df.config.to_numpy(), stat, n_boot)
        stats[name] = (point, {k: (lo[i], hi[i]) for i, k in enumerate(keys)})

    md += ['## 1. Cohorts and exposure', '', '| cohort | cells | exposed / unexposed | canary TPR@1%FPR, median (range) |', '|---|---|---|---|']
    for name, df in cohorts:
        e = df.canary_tpr1 >= tau
        md.append(f'| {name} | {len(df)} | {int(e.sum())} / {int((~e).sum())} | {df.canary_tpr1.median():.3f} ({df.canary_tpr1.min():.3f}-{df.canary_tpr1.max():.3f}) |')

    md += ['', '## 2. Does the audit quantity tell exposed cells from unexposed ones? (AUC)', '',
           '| cohort | shadow-model AUC | LiRA AUC | LiRA TPR@1%FPR | training rows | LiRA TPR minus shadow-model AUC |', '|---|---|---|---|---|---|']
    for name, df in cohorts:
        p, c = stats[name]
        cells = [f'{CB._f(p["auc:" + q])} {ci(*c["auc:" + q])}' for q in ('shadow_auc', 'lira_auc', 'lira_tpr1', 'n')]
        md.append(f'| {name} | ' + ' | '.join(cells) + f' | {CB._f(p["diff:lira_tpr1"])} {ci(*c["diff:lira_tpr1"])} |')

    rule = 'shadow-model AUC <= 0.55 (pilot release rule)'
    md += ['', '## 3. The prescribed rule (shadow-model AUC <= 0.55)', '',
           '| cohort | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | missed cells: canary TPR median / highest |', '|---|---|---|---|---|---|']
    for name, df in cohorts:
        p, c = stats[name]
        e = (df.canary_tpr1 >= tau).to_numpy()
        rel = CB.PRESCRIBED[rule](df).to_numpy(bool)
        miss = df.canary_tpr1.to_numpy()[rel & e]
        md.append(f'| {name} | {int(rel.sum())}/{len(df)} | {int((rel & e).sum())}/{int(e.sum())} | {CB._f(p["sens:" + rule])} {ci(*c["sens:" + rule])} | '
                  f'{CB._f(p["spec:" + rule])} {ci(*c["spec:" + rule])} | ' + (f'{np.median(miss):.3f} / {miss.max():.3f}' if len(miss) else 'n/a') + ' |')

    md += ['', '## 4. Development thresholds applied unchanged (sensitivity / specificity)', '',
           'Recalibrated = the threshold refitted on that cohort, one configuration left out at a time. The development row is in-sample.', '']
    for col in FIXED:
        r = thr['rules'].get(col)
        if not r or r.get('threshold') is None:
            continue
        sign = {q: s for q, _, s in CB.QUANTITIES}[col]
        md += [f'**{r["label"]} {r["release_if"]} {r["threshold"]:.3f}**', '',
               '| cohort | cells released | exposed cells released | sensitivity [95% CI] | specificity [95% CI] | recalibrated: sensitivity / specificity |', '|---|---|---|---|---|---|']
        for name, df in cohorts:
            e = (df.canary_tpr1 >= tau).to_numpy()
            x = df[col].to_numpy(float)
            rel = (x <= r['threshold']) if r['release_if'] == '<=' else (x >= r['threshold'])
            lo, hi, _ = CB.boot_clusters(df.config.to_numpy(), lambda idx, rel=rel, e=e: CB.sens_spec(rel[idx], e[idx]), n_boot)
            s, p = CB.sens_spec(rel, e)
            s2, p2 = CB.sens_spec(CB.loco_release(sign * x, e, df.config.to_numpy(), thr['target_sensitivity']), e)
            md.append(f'| {name} | {int(rel.sum())}/{len(df)} | {int((rel & e).sum())}/{int(e.sum())} | {CB._f(s)} {ci(lo[0], hi[0])} | '
                      f'{CB._f(p)} {ci(lo[1], hi[1])} | {CB._f(s2)} / {CB._f(p2)} |')
        md.append('')

    md += ['## 5. Thresholds calibrated on each cohort itself (release if the quantity is at most c; target sensitivity '
           f'{thr["target_sensitivity"]:.0%})', '', '| cohort | shadow-model AUC | LiRA AUC | LiRA TPR@1%FPR |', '|---|---|---|---|']
    for name, df in cohorts:
        e = (df.canary_tpr1 >= tau).to_numpy()
        cs = [CB.calibrate(df[q].to_numpy(float), e, thr['target_sensitivity']) for q in ('shadow_auc', 'lira_auc', 'lira_tpr1')]
        md.append(f'| {name} | ' + ' | '.join(CB._f(c, 3) if np.isfinite(c) else 'block all' for c in cs) + ' |')
    return md


def types_table(pairs, tau, n_boot):
    """pairs = [(cohort, flipped-label cells, synthetic cells)] -> markdown lines. Does the canary type change which cells are exposed?"""
    md = ['# Canary type across cohorts', '',
          f'Flipped-label canaries against synthetic canaries (each feature drawn from its own marginal, random label), the same cells in each cohort. '
          f'Exposed = canary TPR at 1% FPR of at least {tau:g}. Intervals are 95% percentile intervals over {n_boot:,} resamples of whole configurations. '
          f'The last two columns are AUCs of the audit quantity of the synthetic-canary run for telling cells exposed under the synthetic canaries from the others.', '',
          '| cohort | cells | exposed under both / only flipped / only synthetic / neither | label agreement | Spearman of the canary TPR [95% CI] | LiRA TPR@1%FPR AUC | shadow-model AUC AUC |',
          '|---|---|---|---|---|---|---|']
    for name, a, b in pairs:
        m = a.merge(b, on=['config', 'n'], suffixes=('_f', '_s')).reset_index(drop=True)
        if len(m) < 6 or m.config.nunique() < 3:
            md.append(f'| {name} | {len(m)} | too few cells | | | | |')
            continue
        ef, es = (m.canary_tpr1_f >= tau).to_numpy(), (m.canary_tpr1_s >= tau).to_numpy()

        def stat(idx, m=m):
            d = m.iloc[idx]
            f2, s2 = (d.canary_tpr1_f >= tau).to_numpy(), (d.canary_tpr1_s >= tau).to_numpy()
            return [CB.spearman(d.canary_tpr1_f, d.canary_tpr1_s), float(np.mean(f2 == s2)), CB.auc_rank(s2, d.lira_tpr1_s.to_numpy(float)),
                    CB.auc_rank(s2, d.shadow_auc_s.to_numpy(float))]

        point = stat(np.arange(len(m)))
        lo, hi, _ = CB.boot_clusters(m.config.to_numpy(), stat, n_boot)
        md.append(f'| {name} | {len(m)} | {int((ef & es).sum())} / {int((ef & ~es).sum())} / {int((~ef & es).sum())} / {int((~ef & ~es).sum())} | '
                  f'{point[1]:.0%} | {CB._f(point[0])} {ci(lo[0], hi[0])} | {CB._f(point[2])} {ci(lo[2], hi[2])} | {CB._f(point[3])} {ci(lo[3], hi[3])} |')
    return md


def fig_cohorts(cohorts, thr, tau, out, fname='Fig6_canary_cohorts'):
    """One column per cohort, one marker per cell (filled = named settings, open = space-filling, shape = training size rank).
    Training sizes differ between cohorts (the largest size is capped by the cohort's training rows), so the marker is assigned
    by rank within each cohort (smallest, middle, largest) and the sizes are written in the column title.
    Top: tail exposure against the shadow-model AUC with the 0.55 rule. Bottom: against the ordinary-row LiRA TPR with the
    threshold calibrated on the development cohort and applied unchanged."""
    import figures as F
    plt = F.style()
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FixedLocator, NullFormatter, ScalarFormatter
    markers = ('o', '^', 's')
    rank_label = ('smallest', 'middle', 'largest')
    c_lira = thr['rules']['lira_tpr1']['threshold']
    k = len(cohorts)
    fig, ax = plt.subplots(2, k, figsize=(2.55 * k + 0.45, 5.1), sharey=True)
    for j, (name, df) in enumerate(cohorts):
        sizes = sorted(int(v) for v in df.n.unique())
        if len(sizes) != len(markers):
            raise SystemExit(f'{name}: expected {len(markers)} training sizes, found {sizes}')
        shape = dict(zip(sizes, markers))
        named = ~df.config.str.startswith('lhs').to_numpy()
        e = (df.canary_tpr1 >= tau).to_numpy()
        for i, (xcol, xline) in enumerate((('shadow_auc', L.GATE2_THRESHOLD), ('lira_tpr1', c_lira))):
            a = ax[i, j]
            for n, mk in shape.items():
                for isnamed in (True, False):
                    m = (df.n == n).to_numpy() & (named == isnamed)
                    a.scatter(df[xcol].to_numpy()[m], df.canary_tpr1.to_numpy()[m], marker=mk, s=13 if isnamed else 11, linewidths=0.6,
                              facecolors='k' if isnamed else 'none', edgecolors='k' if isnamed else '0.35', zorder=3 if isnamed else 2)
            a.axhline(tau, color='k', ls='--', lw=0.6)
            a.axvline(xline, color='k', ls=':', lw=0.7)
            rel = df[xcol].to_numpy(float) <= xline
            a.text(0.97, 0.04, f'exposed and released:\n{int((rel & e).sum())} of {int(e.sum())} exposed cells', transform=a.transAxes, fontsize=5.8,
                   ha='right', va='bottom')
            a.set_yscale('log')
            a.set_ylim(0.012, 1.15)
            a.yaxis.set_major_locator(FixedLocator([0.01, 0.03, 0.1, 0.3, 1.0]))
            a.yaxis.set_major_formatter(ScalarFormatter())
            a.yaxis.set_minor_formatter(NullFormatter())
            if i == 0:
                a.set_xlim(0.49, 0.97)
                a.set_title(f'{name}\n{int(e.sum())} of {len(df)} cells exposed\ntraining rows ' + ' / '.join(f'{v:,}' for v in sizes),
                            fontsize=7, loc='left')
                a.set_xlabel('shadow-model AUC (rule: at most 0.55)', fontsize=6.5)
            else:
                a.set_xscale('log')
                a.set_xlim(0.009, 0.8)
                a.xaxis.set_major_locator(FixedLocator([0.01, 0.03, 0.1, 0.3]))
                a.xaxis.set_major_formatter(ScalarFormatter())
                a.xaxis.set_minor_formatter(NullFormatter())
                a.set_xlabel(f'LiRA TPR at 1% FPR (threshold {c_lira:.3f})', fontsize=6.5)
            a.text(-0.02, 1.02, 'abcdefghijklmnop'[i * k + j], transform=a.transAxes, fontsize=8, fontweight='bold', ha='right')
    ax[0, 0].set_ylabel('canary TPR at 1% FPR (known leakage)')
    ax[1, 0].set_ylabel('canary TPR at 1% FPR (known leakage)')
    h = [Line2D([], [], marker=mk, ls='', mfc='none', mec='k', ms=4, label=f'{lab} training size') for mk, lab in zip(markers, rank_label)]
    h += [Line2D([], [], marker='o', ls='', mfc='k', mec='k', ms=4, label='named settings'),
          Line2D([], [], marker='o', ls='', mfc='none', mec='0.35', ms=4, label='space-filling settings')]
    fig.legend(handles=h, fontsize=6.3, loc='lower center', ncol=5, bbox_to_anchor=(0.5, -0.025), handletextpad=0.2, columnspacing=1.1)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    F.save(fig, out, fname)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tau', type=float, default=CB.EXPOSED_TPR1)
    ap.add_argument('--boot', type=int, default=CB.N_BOOT)
    ap.add_argument('--out-root', default=L.OUT_ROOT)
    ap.add_argument('--thresholds', default='', help='development thresholds (default: the first cohort\'s canary_thresholds.json)')
    ap.add_argument('--out', default='')
    ap.add_argument('--figure', action='store_true', help='also draw the cohorts side by side (Fig6_canary_cohorts[_shuffle])')
    ap.add_argument('--figure-dir', default=os.path.join(L.BASE, 'Figures', 'v2', 'cross_cohort'))
    ap.add_argument('--canary-type', choices=['flip', 'shuffle'], default='flip', help='which canary runs to put side by side (default: flipped-label)')
    ap.add_argument('--types', action='store_true', help='also compare the two canary types cohort by cohort (needs both runs; writes canary_cross_cohort_types.md)')
    a = ap.parse_args()
    suffix = '' if a.canary_type == 'flip' else '_' + a.canary_type
    cohorts = [(n, load(a.out_root, f + suffix)) for n, f in COHORTS]
    cohorts = [(n, d) for n, d in cohorts if d is not None and len(d) >= 6]
    if len(cohorts) < 2:
        sys.exit('need the development cohort and at least one more cohort with cell files')
    thr_path = a.thresholds or os.path.join(a.out_root, COHORTS[0][1] + suffix, 'canary_thresholds.json')
    thr = json.load(open(thr_path, encoding='utf-8'))
    md = tables(cohorts, thr, a.tau, a.boot)
    if a.canary_type != 'flip':
        md[0] = '# Canary benchmark across cohorts, synthetic canaries'
    out = a.out or os.path.join(a.out_root, 'canary_cross_cohort' + suffix + '.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    print('\n'.join(md))
    if a.figure:
        fig_cohorts(cohorts, thr, a.tau, a.figure_dir, 'Fig6_canary_cohorts' + suffix)
    if a.types:
        flips = {n: load(a.out_root, f) for n, f in COHORTS}
        shufs = {n: load(a.out_root, f + '_shuffle') for n, f in COHORTS}
        pairs = [(n, flips[n], shufs[n]) for n, _ in COHORTS if flips[n] is not None and shufs[n] is not None]
        if pairs:
            md2 = types_table(pairs, a.tau, a.boot)
            open(os.path.join(a.out_root, 'canary_cross_cohort_types.md'), 'w', encoding='utf-8').write('\n'.join(md2) + '\n')
            print('\n'.join(md2))


if __name__ == '__main__':
    L.guard(main)
