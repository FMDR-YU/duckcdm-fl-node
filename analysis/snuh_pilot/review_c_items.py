# -*- coding: utf-8 -*-
"""Numbers for the internal-review C items (RESPONSE_PLAN.md, 2026-10-24), from the aggregate outputs only:

  C1  site-model and federated exposure relative to the central model under the shadow-model AUC AND the LiRA TPR@1%FPR
      (seed means, t-based 95% intervals), per cohort and site design, published configuration
  C3  patient-level paired bootstrap intervals of F - A from the federated runs (per seed), summarized as the range of the
      per-seed lower and upper bounds and the seed whose interval is widest
  C5  what the calibrated LiRA threshold (0.032) would decide for the study's own central and federated models at the audit's
      reference-model count (seed-mean LiRA TPR@1%FPR of A_0 and F_B1), published and regularized configurations
  C7  the size-share ratio: numerator (A' - A) and denominator (site mean - A) with intervals, and the ratio
  C8  exposed and unexposed cell counts per canary cohort
  C9  federated job wall time per configuration from the run JSONs (seconds, mean over seeds)

    python review_c_items.py          -> out/review_c_items.md
"""
import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilot_lib as L  # noqa: E402

FED = os.path.join(L.BASE, 'analysis', 'federated', 'out')
COHORTS = [('SynPUF, virtual thirds', 'synpuf_xgb', 'synpuf', 'B1'), ('SynPUF, 50/30/20', 'synpuf_xgb', 'synpuf', 'B2'),
           ('eICU, 3 largest hospitals', 'eicu_h3a_xgb', 'eicu_h3a', 'B1'), ('eICU, 3 hospitals of unequal size', 'eicu_h3b_xgb', 'eicu_h3b', 'B1'),
           ('eICU, 14 hospitals', 'eicu_h14_xgb', 'eicu_h14', 'B1'),
           ('SNUH CDM, virtual thirds', 'snuh_cdmv_xgb', 'snuh_cdmv', 'B1'), ('SNUH CDM, 50/30/20', 'snuh_cdmv_xgb', 'snuh_cdmv', 'B2')]
CANARY = [('SynPUF (development)', 'synpuf_xgb_canary'), ('MIMIC-IV-ED', 'mimic_ed_s28k_xgb_canary'), ('eICU-CRD, random sample', 'eicu_s28k_xgb_canary'),
          ('eICU-CRD, 3 largest hospitals', 'eicu_h3a_xgb_canary'), ('eICU-CRD, hospitals of unequal size', 'eicu_h3b_xgb_canary'),
          ('eICU-CRD, 14 hospitals (named settings)', 'eicu_h14_xgb_canary'), ('SNUH CDM, virtual hospitals', 'snuh_cdmv_xgb_canary')]


def ci(x):
    x = pd.Series(x).dropna()
    if len(x) < 2:
        return (float(x.iloc[0]) if len(x) else np.nan, np.nan, np.nan)
    return L.t_ci(x)


def f3(m, lo, hi, d=3):
    return f'{m:+.{d}f}' if np.isnan(lo) else f'{m:+.{d}f} [{lo:+.{d}f}, {hi:+.{d}f}]'


def attacks(folder, variant='xgb_krcp'):
    p = os.path.join(L.OUT_ROOT, folder, '03_attacks_long.csv')
    at = pd.read_csv(p)
    return at[at.variant == variant]


def site_cols(at, scn):
    return sorted(t for t in at.target.unique() if re.fullmatch(scn + r'_\d+', str(t)))


def per_seed(at, metric, targets):
    piv = at.pivot_table(index='seed', columns='target', values=metric)
    return piv[[t for t in targets if t in piv]]


def c1_c7(md):
    md += ['## C1 and C7. Exposure relative to the central model under two attacks (published configuration; seed mean, t-based 95% interval)', '',
           'Shadow-model AUC is the quantity of the pilot rule and of H2 / H5; LiRA TPR@1%FPR is the stronger attack. "A\' share" = (A\' - A) / (sites - A).', '',
           '| cohort, sites | attack | sites mean - A | A\' - A | A\' share | B_avg - A | F - A |', '|---|---|---|---|---|---|---|']
    for name, folder, tag, scn in COHORTS:
        at = attacks(folder)
        if at.empty:
            continue
        sites = site_cols(at, scn)
        for metric, label in (('shadow_auc', 'shadow-model AUC'), ('lira_tpr1', 'LiRA TPR@1%FPR')):
            p = per_seed(at, metric, ['A_0', 'Aprime_0', f'{scn}_comb', f'F_{scn}'] + sites)
            d_site = p[sites].mean(axis=1) - p['A_0']
            d_ap = p['Aprime_0'] - p['A_0']
            d_avg = p[f'{scn}_comb'] - p['A_0'] if f'{scn}_comb' in p else pd.Series(dtype=float)
            d_f = p[f'F_{scn}'] - p['A_0'] if f'F_{scn}' in p else pd.Series(dtype=float)
            m_site, lo_s, hi_s = ci(d_site)
            m_ap, lo_a, hi_a = ci(d_ap)
            share = m_ap / m_site if m_site > 0.005 else np.nan      # only where the site models are more exposed than the central model
            share_txt = f'{share:.0%}' if not np.isnan(share) else 'n/a (site models not more exposed than the central model)'
            md.append(f'| {name} | {label} | {f3(m_site, lo_s, hi_s)} | {f3(m_ap, lo_a, hi_a)} | {share_txt} | '
                      f'{f3(*ci(d_avg)) if len(d_avg) else "not run"} | {f3(*ci(d_f)) if len(d_f) else "not run"} |')
    md.append('')
    return md


def c3(md):
    md += ['## C3. Patient-level paired bootstrap intervals of F - A (federated runs, 500 resamples of validation patients, per seed)', '',
           '| cohort | scenario | configuration | seeds | seed mean of F - A | per-seed bootstrap intervals: lowest lower bound, highest upper bound | widest interval (seed) | all lower bounds > -0.02 |', '|---|---|---|---|---|---|---|---|']
    for name, folder, tag, scn in COHORTS:
        for cfg in ('krcp', 'regularized', 'plain'):
            files = sorted(glob.glob(os.path.join(glob.escape(os.path.join(FED, tag)), f'fl_{scn}_s*_{cfg}.json')))
            if not files:
                continue
            rows = [json.load(open(f, encoding='utf-8')) for f in files]
            d = [r['federated']['delta_auroc_vs_central'] for r in rows]
            lo = [x['ci95'][0] for x in d]; hi = [x['ci95'][1] for x in d]; dl = [x['delta'] for x in d]
            w = [h - l for l, h in zip(lo, hi)]
            k = int(np.argmax(w))
            md.append(f'| {name} | {scn} | {cfg} | {len(rows)} | {np.mean(dl):+.4f} | {min(lo):+.4f}, {max(hi):+.4f} | '
                      f'[{lo[k]:+.4f}, {hi[k]:+.4f}] (seed {rows[k]["seed"]}) | {"yes" if min(lo) > -0.02 else "no"} |')
    md.append('')
    return md


def c5(md):
    md += ['## C5. What the calibrated LiRA threshold (TPR@1%FPR <= 0.032, benchmark K = 47) would decide for the study\'s own models at the audit\'s reference count', '',
           '| cohort, sites | configuration | K (references) | A: LiRA TPR@1%FPR (seed mean) | decision | F: LiRA TPR@1%FPR | decision | pilot rule (shadow AUC <= 0.55): A / F |', '|---|---|---|---|---|---|---|---|']
    for name, folder, tag, scn in COHORTS:
        if scn != 'B1':
            continue
        for variant in ('xgb_krcp', 'xgb_regularized'):
            at = attacks(folder, variant)
            if at.empty:
                continue
            k = int(at.k_lira.dropna().iloc[0]) if 'k_lira' in at else -1
            a = at[at.target == 'A_0']; f = at[at.target == 'F_B1']
            ta, tf = a.lira_tpr1.mean(), (f.lira_tpr1.mean() if not f.empty else np.nan)
            sa, sf = a.shadow_auc.mean(), (f.shadow_auc.mean() if not f.empty else np.nan)
            dec = lambda t: 'release' if t <= 0.032 else 'block'  # noqa: E731
            pil = lambda t: 'release' if t <= L.GATE2_THRESHOLD else 'block'  # noqa: E731
            md.append(f'| {name} | {variant[4:]} | {k} | {ta:.3f} | {dec(ta)} | {tf:.3f} | {dec(tf) if not np.isnan(tf) else "not run"} | {pil(sa)} / {pil(sf) if not np.isnan(sf) else "not run"} |')
    md.append('')
    return md


def c8(md):
    md += ['## C8. Exposed and unexposed cells per canary cohort (tau = 0.1) and the pilot rule\'s specificity denominator', '', '| cohort | cells | exposed | unexposed | configurations contributing unexposed cells |', '|---|---|---|---|---|']
    for name, folder in CANARY:
        files = glob.glob(os.path.join(glob.escape(os.path.join(L.OUT_ROOT, folder)), 'canary_cells_*.csv'))
        if not files:
            continue
        cells = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
        col = next((c for c in cells.columns if 'canary' in c and 'tpr' in c), None)
        cfgcol = next((c for c in cells.columns if c in ('config', 'configuration', 'setting', 'name')), None)
        if col is None:
            md.append(f'| {name} | {len(cells)} | ? | ? | columns: {", ".join(cells.columns[:8])} |')
            continue
        exp = cells[col] >= 0.10
        ncfg = cells.loc[~exp, cfgcol].nunique() if cfgcol else '?'
        md.append(f'| {name} | {len(cells)} | {int(exp.sum())} | {int((~exp).sum())} | {ncfg} |')
    md.append('')
    return md


def c9(md):
    md += ['## C9. Federated job wall time (seconds per job, mean over seeds; Linux container, 4 threads per site process)', '', '| cohort | scenario | configuration | rounds | seconds (mean) | seeds |', '|---|---|---|---|---|---|']
    for name, folder, tag, scn in COHORTS:
        for cfg in ('plain', 'krcp', 'regularized', 'leaky'):
            files = sorted(glob.glob(os.path.join(glob.escape(os.path.join(FED, tag)), f'fl_{scn}_s*_{cfg}.json')))
            if not files:
                continue
            rows = [json.load(open(f, encoding='utf-8')) for f in files]
            secs = [r['federated']['seconds'] for r in rows]
            md.append(f'| {name} | {scn} | {cfg} | {rows[0]["rounds"]} | {np.mean(secs):,.0f} | {len(rows)} |')
    md.append('')
    return md


def main():
    md = ['# Numbers for the internal-review C items (generated by review_c_items.py)', '']
    md = c1_c7(md)
    md = c3(md)
    md = c5(md)
    md = c8(md)
    md = c9(md)
    out = os.path.join(L.OUT_ROOT, 'review_c_items.md')
    open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')
    print('wrote', out)


if __name__ == '__main__':
    main()
