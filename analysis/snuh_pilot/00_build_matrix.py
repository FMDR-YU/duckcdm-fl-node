# -*- coding: utf-8 -*-
"""Step 00 -- build the analysis matrix: 36 features + y + published train/val split + strata.

  --dataset snuh    v1.3 feature definitions, reproduced from CKD_ML PROJECT\\ML\\v1.3\\retrain_v13.py
                    lines 41-83 (same input files, same slope and drug code). Reads CKD_ML data in place
                    (PILOT_CKD_ROOT), writes data/ckd_pilot/matrix_snuh.parquet. No RID is kept.
  --dataset synpuf  development substitute: 28,209 CMS DE-SynPUF beneficiaries (stratified sample), same
                    70/30 stratified split, so every later step runs unchanged on public data.

Writes out/<ds>/00_build_matrix.txt (aggregates only).
"""
import argparse
import hashlib
import json
import os
import re
import sys

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilot_lib as L  # noqa: E402

FEATURES_SNUH = ['Age', 'Sex_Male', 'ALT', 'AST', 'Albumin', 'BUN', 'Calcium', 'Cholesterol', 'Creatinine', 'GGT',
                 'Glucose', 'HDL', 'Hb', 'HbA1c', 'Phosphorus', 'Potassium', 'Sodium', 'TG', 'Total_Bilirubin',
                 'Total_Protein', 'UACR', 'Uric_Acid', 'Urine_Creatinine', 'Urine_Microalbumin', 'Baseline_eGFR',
                 'eGFR_Slope', 'History_HTN', 'History_DM', 'Subgroup_DKD', 'Subgroup_GN', 'BMI', 'Dur_ACE_ARB_days',
                 'Dur_Statin_days', 'Drug_RAASi', 'Drug_Statins', 'Bicarbonate']
N_SNUH = 28209


def build_snuh():
    """retrain_v13.py lines 41-83, unchanged in substance."""
    ROOT = L.CKD_ROOT
    BASE = os.path.join(ROOT, 'ML', 'Base_file')
    FEATURES = FEATURES_SNUH
    DRUG = ['Dur_ACE_ARB_days', 'Dur_Statin_days', 'Drug_RAASi', 'Drug_Statins']
    SERUM = ['Creatinine(검사24시간가능)', '[처방불가]Creatinine (serum, em)', 'Creatinine (serum)']
    MIN_GAP_DAYS, SLOPE_LIMIT = 90, 60

    ml = pd.read_csv(os.path.join(BASE, 'SNUH_CKD_Analysis_ML.csv'))
    base = pd.read_csv(os.path.join(BASE, 'SNUH_CKD_Analysis_Base.csv'))
    assert np.allclose(ml[FEATURES].fillna(-9e9).values, base[FEATURES].fillna(-9e9).values)

    def fix(c):
        try:
            return c.encode('latin1').decode('cp949')
        except Exception:
            return c
    bs = pd.read_parquet(os.path.join(ROOT, 'Data', 'parquets', 'BASICS_Total.parquet'))
    bs.columns = [fix(c) for c in bs.columns]
    bs['d'] = pd.to_datetime(bs['내원일자'].astype(str).str[:10])
    base['Index'] = base['RID'].map(bs.groupby('연구별 환자 ID')['d'].min())
    sys.path.insert(0, os.path.join(ROOT, 'Code', 'SNUHUB'))
    from drug_dictionary import compute_exposure
    agg = compute_exposure(base['RID'].unique(), verbose=False, until=base.set_index('RID')['Index'])
    agg = agg.rename(columns={'Dur_RAASi_days': 'Dur_ACE_ARB_days', 'Dur_Statins_days': 'Dur_Statin_days'})
    d = base[['RID']].merge(agg[['RID'] + DRUG], on='RID', how='left', validate='1:1')
    d[DRUG] = d[DRUG].fillna(0)
    assert (d['RID'].values == base['RID'].values).all()
    cr = pd.read_parquet(os.path.join(ROOT, 'ML', 'audit_260929', 'cr_28209.parquet'))
    cr = cr[cr['검사명'].isin(SERUM)].copy()
    cr['v'] = pd.to_numeric(cr['검사결과'], errors='coerce'); cr = cr.dropna(subset=['v', '검사시행일'])
    cr = cr[(cr['v'] >= 0.1) & (cr['v'] <= 30)].rename(columns={'검사시행일': 'd'}).merge(
        base[['RID', 'Index', 'Birth_Year', 'Sex_Male']], on='RID')
    fem = cr['Sex_Male'] == 0
    k = np.where(fem, 0.7, 0.9); a = np.where(fem, -0.241, -0.302); f = np.where(fem, 1.012, 1.0); s = cr['v'] / k
    cr['egfr'] = 142 * np.minimum(s, 1) ** a * np.maximum(s, 1) ** -1.2 * 0.9938 ** (cr['d'].dt.year - cr['Birth_Year']) * f
    mb = cr.merge(base[['RID', 'Creatinine']], on='RID'); mb = mb[np.isclose(mb['v'], mb['Creatinine'], atol=1e-6)]
    mb['gap'] = (mb['d'] - mb['Index']).dt.days.abs()
    bdate = mb.sort_values('gap').groupby('RID')['d'].first()
    cr['bd'] = cr['RID'].map(bdate)
    prior = cr[cr['d'] <= cr['bd'] - pd.Timedelta(days=MIN_GAP_DAYS)].sort_values('d').groupby('RID').last()
    bi = base.set_index('RID')
    slope = (bi['Baseline_eGFR'] - prior['egfr']) / ((bdate.reindex(prior.index) - prior['d']).dt.days / 365.25)
    slope = slope.reindex(base['RID']).values.astype(float)
    slope[np.abs(slope) > SLOPE_LIMIT] = np.nan

    X_pub = ml[FEATURES]; y = ml['Outcome_40']
    X12 = X_pub.copy(); X12[DRUG] = d[DRUG].values; X12['eGFR_Slope'] = slope
    X_tr, X_va, _, _ = train_test_split(X_pub, y, test_size=0.3, stratify=y, random_state=42)
    assert len(X_tr) == 19746 and len(X_va) == 8463

    out = X12.reset_index(drop=True).copy()
    out['y'] = y.to_numpy(int)
    split = pd.Series('val', index=X_pub.index); split.loc[X_tr.index] = 'train'
    out['split'] = split.to_numpy()
    egfr = out['Baseline_eGFR']
    out['stratum'] = np.select([egfr >= 60, egfr >= 45, egfr >= 30, egfr < 30], ['G1-2', 'G3a', 'G3b', 'G4-5'], 'NA')
    out['sg_age65'] = (out['Age'] >= 65).map({True: '>=65', False: '<65'})
    out['sg_sex'] = out['Sex_Male'].map({1: 'male', 0: 'female'}).fillna('NA')
    out['sg_dm'] = out['History_DM'].map({1: 'DM', 0: 'no DM'}).fillna('NA')
    out['sg_ckd_stage'] = out['stratum']
    return out, FEATURES, ['sg_age65', 'sg_sex', 'sg_dm', 'sg_ckd_stage'], 'SNUH CKD cohort, v1.3 definitions'


def build_synpuf():
    sys.path.insert(0, os.path.join(L.BASE, 'safe-model-bundle', 'poc'))
    from src.synpuf_loader import load_synpuf_cohort, FEATURES, OUTCOME
    csv = os.path.join(L.BASE, 'data', 'cdm', 'synpuf', 'DE1_0_2008_Beneficiary_Summary_File_Sample_1.csv')
    df = load_synpuf_cohort(csv)
    n = 3000 if L.QUICK else N_SNUH
    df, _ = train_test_split(df, train_size=n, stratify=df[OUTCOME], random_state=42)
    df = df.reset_index(drop=True)
    out = df[FEATURES].astype(float).copy()
    out['y'] = df[OUTCOME].to_numpy(int)
    tr, _ = train_test_split(np.arange(n), test_size=0.3, stratify=out['y'], random_state=42)
    out['split'] = 'val'; out.loc[tr, 'split'] = 'train'
    out['stratum'] = pd.qcut(out['age'], 4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop').astype(str)
    out['sg_age75'] = np.where(out['age'] >= 75, '>=75', '<75')
    out['sg_sex'] = out['sex'].astype(int).astype(str)
    out['sg_esrd'] = out['esrd'].astype(int).astype(str)
    return out, list(FEATURES), ['sg_age75', 'sg_sex', 'sg_esrd'], 'CMS DE-SynPUF 2008 sample 1 (development substitute)'


def build_mimic_ed():
    """MIMIC-IV-ED, one row per person (first ED stay), admission at triage. PILOT_TAG selects the release / size:
    demo = open demo-2.2 (all rows, for tests), s28k = full-2.2 stratified sample of 28,209 (same size as the SNUH
    cohort; the three-gate audit runs here), unset = full-2.2, every person (utility and federated runs).
    The full release is credentialed (PhysioNet DUA): the user runs it, Claude reads out/ only."""
    sys.path.insert(0, os.path.join(L.BASE, 'analysis', 'mimic_ed'))
    import matrix_mimic_ed as M
    release = 'demo-2.2' if L.TAG == 'demo' else 'full-2.2'
    ed_dir = os.path.join(L.BASE, 'data', 'mimic-iv-ed', release, 'ed')
    patients = os.path.join(L.BASE, 'data', 'mimic-iv', '2.2', 'hosp', 'patients.csv.gz') if release == 'full-2.2' else None
    out, feats, subgroups, info = M.build(ed_dir, patients, n_sample=N_SNUH if L.TAG == 's28k' else None)
    L.MIMIC_INFO = info
    return out, feats, subgroups, f'MIMIC-IV-ED {release}, {info["unit"]}' + (', with age' if info['uses_patients'] else '')


def build_eicu():
    """eICU-CRD, one row per person (first ICU stay with APACHE IV first-day variables), hospital mortality. PILOT_TAG selects the
    release / size: demo = the open demo 2.0.1 (tests), s28k = full release sampled to 28,209 (same size as the SNUH cohort),
    unset = full release, every person. The full release is credentialed (PhysioNet DUA): the user runs it, Claude reads out/ only."""
    sys.path.insert(0, os.path.join(L.BASE, 'analysis', 'eicu'))
    import matrix_eicu as E
    # Release choice is separate from the site tag: PILOT_EICU_RELEASE=demo (or the tag 'demo') reads the open demo; anything else
    # reads the credentialed full release, which only the user runs (DATA_SCOPE.md). Tests set PILOT_EICU_RELEASE=demo.
    release = 'demo-2.0.1' if (L.TAG == 'demo' or os.environ.get('PILOT_EICU_RELEASE', '').lower() == 'demo') else 'full-2.0'
    if release == 'full-2.0' and os.environ.get('PILOT_EICU_RELEASE', '').lower() not in ('', 'full'):
        sys.exit(f"PILOT_EICU_RELEASE={os.environ['PILOT_EICU_RELEASE']!r} is not demo or full")
    # h3a / h3b: three real hospitals as the fixed sites (docs/EICU_REAL_SITES_PLAN.md): h3a = the three largest, h3b = largest /
    # median-ranked / smallest among hospitals with >= 2,000 analysis rows. The matrix then holds only those hospitals' people,
    # the train / validation split is made inside each hospital, and site_b1 = site_b2 = hospital rank (pilot_lib.scenarios reads
    # them as fixed sites, as for the SNUH CDM sites). PILOT_EICU_MIN_ROWS lowers the 2,000 threshold for tests.
    rule = {'h3a': 'top3', 'h3b': 'spread3', 'h14': 'all'}.get(L.TAG)     # h14: every hospital with >= 2,000 rows (14 in the full release)
    min_rows = int(os.environ.get('PILOT_EICU_MIN_ROWS', E.MIN_HOSPITAL_ROWS))
    out, feats, subgroups, info = E.build(os.path.join(L.BASE, 'data', 'eicu', release), n_sample=N_SNUH if L.TAG == 's28k' else None,
                                          hospitals=rule, min_hospital_rows=min_rows)
    if rule:
        # validation rows get -1 like the SNUH hold-out, so size_classes() sizes the shadows on training rows only
        s = np.where(out['split'].to_numpy() == 'train', out['site'].to_numpy(int), -1)
        out['site_b1'] = s
        out['site_b2'] = s
        out = out.drop(columns=['site'])
        info['fixed_sites'] = True
        n_sites = int(s.max()) + 1
        info['site_train_rows'] = [int((s == k).sum()) for k in range(n_sites)]
        info['n_sites'] = n_sites
    L.EICU_INFO = info
    label = f'eICU-CRD {release}, {info["unit"]}' + (f', {info["n_sites"]} real hospitals as sites ({rule})' if rule else '')
    return out, feats, subgroups, label


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', choices=L.DATASETS, required=True)
    ap.add_argument('--irb', default=os.environ.get('PILOT_IRB', ''),
                    help='SNUH IRB exemption number for this study (required for --dataset snuh)')
    a = ap.parse_args()
    # Interlock: SNUH data are read only once the new exemption (submitted 2026-10-06) is issued.
    if a.dataset == 'snuh' and not re.fullmatch(r'E-\d{4}-\d{3}-\d{4}', a.irb.strip()):
        sys.exit('SNUH data not read: give this study\'s IRB exemption number, e.g. --irb E-2610-123-4567 '
                 '(run_pilot.py --dataset snuh --irb E-...). The earlier projects\' numbers do not apply.')
    out, feats, subgroups, label = {'snuh': build_snuh, 'synpuf': build_synpuf, 'mimic_ed': build_mimic_ed, 'eicu': build_eicu}[a.dataset]()

    os.makedirs(L.DATA_DIR, exist_ok=True)
    p = L.matrix_path(a.dataset)
    out.to_parquet(p, index=False)
    h = hashlib.sha256(pd.util.hash_pandas_object(out, index=False).values.tobytes()
                       + ','.join(out.columns).encode()).hexdigest()
    meta = {'dataset': a.dataset, 'label': label, 'irb': a.irb.strip() or None, 'features': feats, 'subgroups': subgroups,
            'n': int(len(out)), 'data_sha256': h, 'quick': L.QUICK}
    if a.dataset == 'mimic_ed':
        meta['mimic'] = getattr(L, 'MIMIC_INFO', {})
    if a.dataset == 'eicu':
        meta['eicu'] = getattr(L, 'EICU_INFO', {})
        if meta['eicu'].get('fixed_sites'):
            meta['fixed_sites'] = True
    json.dump(meta, open(p.replace('.parquet', '.meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    tr = out['split'] == 'train'
    lines = [f'# 00_build_matrix  dataset={a.dataset}  ({label})', '',
             f'rows               : {L.cell(len(out))}  (train {L.cell(tr.sum())} / val {L.cell((~tr).sum())})',
             f'outcome rate       : {out["y"].mean():.1%} (train {out.loc[tr, "y"].mean():.1%}, val {out.loc[~tr, "y"].mean():.1%})',
             f'features           : {len(feats)}',
             f'data sha256        : {h[:16]}…', '', 'missing per feature (before imputation)']
    for c in feats:
        lines.append(f'  {c:<20} {out[c].isna().mean():6.1%}')
    lines += ['', 'stratum (baseline eGFR / age quartile)']
    lines += [f'  {k:<8} {L.cell(v)}' for k, v in out['stratum'].value_counts().sort_index().items()]
    lines += ['', 'subgroups']
    for g in subgroups:
        lines.append(f'  {g:<14} ' + '  '.join(f'{k}: {L.cell(v)}' for k, v in out[g].value_counts().sort_index().items()))
    path = os.path.join(L.out_dir(a.dataset), '00_build_matrix.txt')
    open(path, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('done ->', os.path.relpath(path, L.BASE))


if __name__ == '__main__':
    L.guard(main)
