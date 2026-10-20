# -*- coding: utf-8 -*-
"""Independent pandas re-implementation of the published / v1.3 logic, run on the *raw* synthetic
fixture (not on the CDM). P4's DuckDB/CDM results must match it exactly.

Ported from SNUH_CKD_DATAPREP.ipynb cell 1 (lab_config contains-matching, ranges, UACR, CKD-EPI 2021,
outcome), ML/v1.3/retrain_v13.py (2-point slope) and drug_dictionary.compute_exposure (regex classes,
PRN / excluded names, union of prescription days until the index date). Cohort = v205 rules applied to
the raw tables with the fixture's code lists.
"""

import numpy as np
import pandas as pd

LAB_CONFIG = {   # DATAPREP cell 1 lab_config (order matters: first variable whose keyword is contained wins)
    'Creatinine': [['Creatinine(검사24시간가능)', '[처방불가]Creatinine (serum, em)', 'Creatinine (serum)'], 0.1, 30.0],
    'BUN': [['BUN(검사24시간가능)', '[처방불가]BUN (serum, em)'], 0.0, 300.0],
    'Uric_Acid': [['Uric Acid(검사24시간가능)'], 0.0, 30.0],
    'Sodium': [['Sodium (serum)(검사24시간가능)', '[처방불가]Sodium (serum, em)'], 100, 180],
    'Potassium': [['Potassium (serum)(검사24시간가능)', '[POCT, ABGA]Potassium', '[처방불가]Potassium (serum, em)'], 0.0, 10.0],
    'Calcium': [['Calcium(검사24시간가능)'], 0.0, 20.0],
    'Phosphorus': [['Phosphorus(검사24시간가능)'], 0.5, 20.0],
    'Bicarbonate': [['CO2, total (serum)', 'CO2, total (serum, em)'], 5.0, 40.0],
    'Albumin': [['Albumin(검사24시간가능)', '[처방불가]Albumin (em)'], 0.5, 7.0],
    'Total_Protein': [['Protein, total(검사24시간가능)', '[처방불가]Protein, total (em)'], 3.0, 15.0],
    'Total_Bilirubin': [['Bilirubin, total(검사24시간가능)'], 0.0, 50.0],
    'AST': [['GOT (AST)(검사24시간가능)'], 0.0, 2000.0],
    'ALT': [['GPT (ALT)(검사24시간가능)', 'GPT(ALT) [piccolo, 과내간이]'], 0.0, 2000.0],
    'GGT': [['GGT(검사24시간가능)', '[처방불가]GGT (em)'], 0.0, 2000.0],
    'Hb': [['Hb(검사24시간가능)', '[POCT, ABGA]Hb'], 3.0, 25.0],
    'HbA1c': [['Hb A1c'], 3.0, 20.0],
    'Glucose': [['Glucose(검사24시간가능)'], 0.0, 2000.0],
    'HDL': [['HDL-Cholesterol(검사24시간가능)'], 0.0, 200.0],
    'TG': [['Triglyceride'], 0.0, 3000.0],
    'Cholesterol': [['Cholesterol(검사24시간가능)'], 10.0, 1000.0],
    'UACR_Raw': [['Microalbumin/Creatinine Ratio'], None, 20000.0],
    'Urine_Microalbumin': [['Microalbumin (random urine)'], None, None],
    'Urine_Creatinine': [['Creatinine (random urine)'], None, None],
}
_ARB = r'(?:lo|val|cande|irbe|telmi|olme|fima|azil|epro|tas)sartan|amosartan'
_ACEI = (r'(?:rami|enala|capto|lisino|perindo|imida|benaze|fosino|zofeno|temoca|'
         r'cilaza|quina|trandola|moexi|alace|dela|spira)pril')
CLASSES = {'RAASi': _ARB + '|' + _ACEI, 'Statins': r'(?:atorva|rosuva|simva|prava|pitava|fluva|lova|ceriva)statin'}
CKD = {'N18.1', 'N18.3', 'N18.9'}
RRT = {'Z49.1', 'T86.1'}          # map to descendants of 4032243 (procedure) / 199991 (condition) in the test vocab


def egfr(scr, age, male):
    fem = np.asarray(male) != 1
    k, a, f = np.where(fem, 0.7, 0.9), np.where(fem, -0.241, -0.302), np.where(fem, 1.012, 1.0)
    s = np.asarray(scr, float) / k
    return 142 * np.minimum(s, 1) ** a * np.maximum(s, 1) ** -1.2 * 0.9938 ** np.asarray(age, float) * f


def lab_variable(names):
    m = {}
    for t in pd.unique(names):
        for var, (kws, _, _) in LAB_CONFIG.items():
            if any(kw in str(t) for kw in kws):
                m[t] = var
                break
    return m


def cohort(fx, entry='ckd'):
    """entry 'ckd': v205 (first CKD diagnosis with 730 d observation after; >= 2 serum creatinine in index +0..+730 d).
    entry 'visit': the published step 1 (SNUH_CKD_DATAPREP.ipynb) with the v205 exclusions: index = first visit; >= 2 serum creatinine
    records whose first and last dates are >= 730 d apart; no CKD-diagnosis requirement (p4_site_features.py --entry visit)."""
    b, lab, drug, dx = fx['basics'], fx['lab'], fx['drug'], fx['dx']
    yob = b.groupby('연구별 환자 ID')['생년월'].first().str[:4].astype(int)
    ev = pd.concat([pd.DataFrame({'pid': b['연구별 환자 ID'], 'd': pd.to_datetime(b['내원일자'])}),
                    pd.DataFrame({'pid': lab['RID'], 'd': pd.to_datetime(lab['검사시행일'])}),
                    pd.DataFrame({'pid': drug['RID'], 'd': pd.to_datetime(drug['처방일자'], format='%Y%m%d')}),
                    pd.DataFrame({'pid': dx['연구별 환자 ID'], 'd': pd.to_datetime(dx['진단일자'])})])
    op = ev.groupby('pid')['d'].agg(['min', 'max'])
    if entry == 'visit':
        idx = pd.to_datetime(b['내원일자']).groupby(b['연구별 환자 ID']).min()
    else:
        c = dx[dx['ICD10코드'].isin(CKD)].rename(columns={'연구별 환자 ID': 'pid', '진단일자': 'd'}).join(op, on='pid')
        c = c[(c['d'] >= c['min']) & (c['d'] + pd.Timedelta(days=730) <= c['max'])]
        idx = c.groupby('pid')['d'].min()
    out = pd.DataFrame({'index_date': idx})
    out['age_ok'] = (idx.dt.year - yob.reindex(idx.index)) >= 19
    var = lab['검사명'].map(lab_variable(lab['검사명']))
    cr = lab[var == 'Creatinine'].assign(d=lambda x: pd.to_datetime(x['검사시행일'])).join(idx.rename('i'), on='RID')
    if entry == 'visit':
        g = cr.groupby('RID')['d'].agg(['min', 'max', 'count'])
        out['cr_ok'] = out.index.isin(g.index[(g['count'] >= 2) & ((g['max'] - g['min']).dt.days >= 730)])
    else:
        n_cr = cr[(cr['d'] >= cr['i']) & (cr['d'] <= cr['i'] + pd.Timedelta(days=730))].groupby('RID').size()
        out['cr_ok'] = n_cr.reindex(out.index).fillna(0) >= 2
    r = dx[dx['ICD10코드'].isin(RRT)].join(idx.rename('i'), on='연구별 환자 ID')
    out['rrt_ok'] = ~out.index.isin(r.loc[r['진단일자'] <= r['i'], '연구별 환자 ID'])
    v = pd.to_numeric(lab['검사결과'], errors='coerce')
    bad = lab[((var == 'Potassium') & (lab['검사결과단위'] == 'mmol/L') & ~v.between(1.5, 10) & v.notna())
              | ((var == 'Hb') & (lab['검사결과단위'] == 'g/dL') & ~v.between(3, 25) & v.notna())]
    bad = bad.assign(d=pd.to_datetime(bad['검사시행일'])).join(idx.rename('i'), on='RID')
    bad = bad[(bad['d'] >= bad['i'] - pd.Timedelta(days=365)) & (bad['d'] <= bad['i'])]
    out['kh_ok'] = ~out.index.isin(bad['RID'])
    return out


def features(fx, index, excluded_names, window_all=False):
    """index: Series rid -> index date (Timestamp). Returns DataFrame (rid) with the 36 features + y."""
    b, lab, drug, dx = fx['basics'], fx['lab'], fx['drug'], fx['dx']
    first = b.groupby('연구별 환자 ID').first()
    yob = first['생년월'].str[:4].astype(int).reindex(index.index)
    male = (first['성별'] == 'M').astype(int).reindex(index.index)
    out = pd.DataFrame(index=index.index)
    out['Age'] = index.dt.year - yob
    out['Sex_Male'] = male

    L = lab[lab['RID'].isin(index.index)].copy()
    L['Variable'] = L['검사명'].map(lab_variable(L['검사명']))
    L = L.dropna(subset=['Variable'])
    L['Date'] = pd.to_datetime(L['검사시행일'])
    L['Value'] = pd.to_numeric(L['검사결과'], errors='coerce')
    L = L.dropna(subset=['Value', 'Date'])
    for var, (_, lo, hi) in LAB_CONFIG.items():
        mv = L['Variable'] == var
        if lo is not None:
            L.loc[mv & (L['Value'] < lo), 'Value'] = np.nan
        if hi is not None:
            L.loc[mv & (L['Value'] > hi), 'Value'] = np.nan
    L = L.dropna(subset=['Value'])
    u = L[L['Variable'].isin(['Urine_Microalbumin', 'Urine_Creatinine'])]
    pv = u.pivot_table(index=['RID', 'Date'], columns='Variable', values='Value', aggfunc='mean').reset_index()
    parts = [L[['RID', 'Variable', 'Value', 'Date']]]
    if {'Urine_Microalbumin', 'Urine_Creatinine'} <= set(pv.columns):
        with np.errstate(divide='ignore', invalid='ignore'):
            pv['Value'] = pv['Urine_Microalbumin'] / pv['Urine_Creatinine'] * 1000
        parts.append(pv[['RID', 'Date', 'Value']].dropna().assign(Variable='UACR'))
    L = pd.concat(parts, ignore_index=True)
    L.loc[L['Variable'] == 'UACR_Raw', 'Variable'] = 'UACR'
    mu = L['Variable'] == 'UACR'
    L.loc[mu & (L['Value'] < 0.5), 'Value'] *= 1000
    L.loc[mu & (L['Value'] > 20000), 'Value'] = np.nan
    L = L.dropna(subset=['Value'])
    L['Index'] = L['RID'].map(index)
    L['gap'] = (L['Date'] - L['Index']).abs()
    bl = L.sort_values(['gap', 'Date']).groupby(['RID', 'Variable']).first()
    wide = bl['Value'].unstack('Variable')
    for v in [k for k in LAB_CONFIG if k != 'UACR_Raw'] + ['UACR']:
        out[v] = wide[v].reindex(out.index) if v in wide.columns else np.nan
    out['Baseline_eGFR'] = egfr(out['Creatinine'], out['Age'], out['Sex_Male'])

    cr = L[L['Variable'] == 'Creatinine'].copy()
    cr['egfr'] = egfr(cr['Value'], cr['Date'].dt.year - cr['RID'].map(yob), cr['RID'].map(male))
    bdate = bl.xs('Creatinine', level='Variable')['Date'] if 'Creatinine' in wide.columns else pd.Series(dtype='datetime64[ns]')
    cr['bd'] = cr['RID'].map(bdate)
    prior = cr[cr['Date'] <= cr['bd'] - pd.Timedelta(days=90)].sort_values('Date').groupby('RID').last()
    slope = (out['Baseline_eGFR'].reindex(prior.index) - prior['egfr']) / ((prior['bd'] - prior['Date']).dt.days / 365.25)
    slope[slope.abs() > 60] = np.nan
    out['eGFR_Slope'] = slope.reindex(out.index)
    w = cr[(cr['Date'] >= cr['Index']) & (cr['Date'] <= cr['Index'] + pd.Timedelta(days=730))]
    mn = w.groupby('RID')['egfr'].min().reindex(out.index)
    ok = mn.notna() & out['Baseline_eGFR'].notna()
    out['y'] = (ok & ((mn < out['Baseline_eGFR'] * 0.6) | (mn < 15))).astype(int)

    d = dx[dx['연구별 환자 ID'].isin(index.index)].copy()
    d['c3'] = d['ICD10코드'].str.replace(r'[^A-Za-z0-9]', '', regex=True).str.upper().str[:3]
    if not window_all:
        d = d[pd.to_datetime(d['진단일자']) <= d['연구별 환자 ID'].map(index)]
    for f, (lo, hi) in {'History_HTN': ('I10', 'I15'), 'History_DM': ('E10', 'E14'), 'Subgroup_DKD': ('E10', 'E14'),
                        'Subgroup_GN': ('N00', 'N08')}.items():
        out[f] = out.index.isin(d.loc[(d['c3'] >= lo) & (d['c3'] <= hi), '연구별 환자 ID']).astype(int)

    bm = b[b['연구별 환자 ID'].isin(index.index)].dropna(subset=['BMI']).drop_duplicates(['연구별 환자 ID', '내원일자', 'BMI'])
    if not window_all:
        bm = bm[pd.to_datetime(bm['내원일자']) <= bm['연구별 환자 ID'].map(index)]
    out['BMI'] = bm.groupby('연구별 환자 ID')['BMI'].mean().reindex(out.index)

    dr = drug[drug['RID'].isin(index.index) & (drug['PRN처방여부'] != 'Y') & ~drug['일반성분명'].isin(excluded_names)].copy()
    days = np.maximum(pd.to_numeric(dr['투약일수'], errors='coerce').fillna(0).clip(lower=0).astype('int64'), 1)
    s = pd.to_datetime(dr['처방일자'], format='%Y%m%d').values.astype('datetime64[D]').astype('int64')
    e = s + days.to_numpy()
    cut = pd.to_datetime(dr['RID'].map(index)).values.astype('datetime64[D]').astype('int64') + 1
    keep = s < cut
    dr, s, e = dr[keep], s[keep], np.minimum(e[keep], cut[keep])
    low = dr['일반성분명'].str.lower()
    for cls, dur, flag in (('RAASi', 'Dur_ACE_ARB_days', 'Drug_RAASi'), ('Statins', 'Dur_Statin_days', 'Drug_Statins')):
        m = low.str.contains(CLASSES[cls], regex=True).to_numpy()
        tot = {}
        for rid, g in pd.DataFrame({'r': dr['RID'].to_numpy()[m], 's': s[m], 'e': e[m]}).groupby('r'):
            iv = sorted(zip(g['s'], g['e']))
            cs, ce, acc = iv[0][0], iv[0][1], 0
            for a_, b_ in iv[1:]:
                if a_ > ce:
                    acc += ce - cs
                    cs, ce = a_, b_
                else:
                    ce = max(ce, b_)
            tot[rid] = float(acc + ce - cs)
        out[dur] = pd.Series(tot, dtype=float).reindex(out.index).fillna(0.0)
        out[flag] = (out[dur] > 0).astype(int)
    return out
