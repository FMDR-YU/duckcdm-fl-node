# -*- coding: utf-8 -*-
"""Fake raw extracts in the SNUH layout (mojibake column names, BASICS / LAB-1,2 / DRUG parquets,
DIAGNOSIS_ICD10.xlsx, Base.csv), fake mapping tables and a small Athena-style vocabulary.
Built only from public Synthea27Nj or from random numbers -- no SNUH data.

  build_vocab(dir)            Athena TSV vocabulary: Synthea27Nj CONCEPT + test concepts (CKD, RRT, ATC, LOINC)
  build_synthea(dir)          Synthea27Nj reverse-mapped into the raw layout (round-trip test)
  build_synthetic(dir, n)     random CKD-like patients that exercise every cohort / feature branch
"""
import os
import re
import zlib
from datetime import date, timedelta

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SYNTHEA = os.path.join(BASE, 'data', 'cdm', 'Synthea27Nj')


def moj(s):
    """Inverse of cdm_lib.fix(): what R/CP949 parquets look like when read back."""
    return s.encode('cp949').decode('latin1')


def mojcols(df):
    return df.rename(columns={c: moj(c) for c in df.columns})


# ───────────────────────── vocabulary ─────────────────────────
T = 2_000_000_000          # test-only concept ids
INGREDIENTS = {'lisinopril': 1308216, 'losartan': 1367500, 'valsartan': 1308842, 'ramipril': 1334456,
               'telmisartan': 1317640, 'amlodipine': 1332418, 'atorvastatin': 1545958, 'rosuvastatin': 1510813,
               'simvastatin': 1539403, 'metformin': 1503297, 'hydrochlorothiazide': 974166, 'nystatin': T + 410,
               'fluticasone': 1149380, 'sodium chloride': 967823, 'acetaminophen': 1125315, 'ibuprofen': 1177480,
               'fimasartan': T + 420}
ATC = {'C09A': (T + 301, ['lisinopril', 'ramipril']), 'C09C': (T + 302, ['losartan', 'valsartan', 'telmisartan']),
       'C10AA': (T + 303, ['atorvastatin', 'rosuvastatin', 'simvastatin'])}
LOINC_ADD = {'3084-1': T + 501, '2777-1': T + 502, '2324-2': T + 503, '14957-5': T + 504, '2161-8': T + 505,
             '9318-7': T + 506, '1963-8': T + 507, '20509-6': 3027484, '6298-4': 3005456, '2028-9': 3015632,
             '2823-3': 3023103, '2160-0': 3016723, '718-7': 3000963}
SNOMED_ADD = [  # id, name, domain, class
    (46271022, 'Chronic kidney disease', 'Condition', 'Disorder'),
    (T + 102, 'Chronic kidney disease stage 3 (test)', 'Condition', 'Disorder'),
    (4032243, 'Dialysis procedure', 'Procedure', 'Procedure'), (4146536, 'Renal dialysis', 'Procedure', 'Procedure'),
    (4322471, 'Transplant of kidney', 'Procedure', 'Procedure'),
    (199991, 'Disorder of transplanted kidney', 'Condition', 'Disorder'),
    (T + 201, 'Hemodialysis (test)', 'Procedure', 'Procedure'),
    (T + 202, 'Dependence on renal dialysis (test)', 'Observation', 'Finding'),
    (T + 203, 'Kidney transplant failure (test)', 'Condition', 'Disorder'),
    (201820, 'Diabetes mellitus', 'Condition', 'Disorder'), (4263367, 'Glomerulonephritis', 'Condition', 'Disorder'),
    (193782, 'End-stage renal disease', 'Condition', 'Disorder')]
ANCESTOR = [(46271022, [46271022, 443614, T + 102]), (4032243, [4032243, T + 201]), (4146536, [4146536]),
            (4322471, [4322471]), (199991, [199991, T + 203]), (3016723, [3016723]), (3023103, [3023103]),
            (3005456, [3005456]), (3000963, [3000963]), (3027484, [3027484])]


def build_vocab(vdir):
    os.makedirs(vdir, exist_ok=True)
    syn = pd.read_csv(os.path.join(SYNTHEA, 'CONCEPT.csv'), dtype=str, keep_default_na=False)
    rows = []
    have = set(syn['concept_id'].astype(int))
    loinc_have = set(syn.loc[syn['vocabulary_id'] == 'LOINC', 'concept_code'])

    def add(cid, name, dom, voc, cls, code, std='S'):
        if cid not in have:
            rows.append({'concept_id': str(cid), 'concept_name': name, 'domain_id': dom, 'vocabulary_id': voc,
                         'concept_class_id': cls, 'standard_concept': std, 'concept_code': code,
                         'valid_start_date': '1970-01-01', 'valid_end_date': '2099-12-31', 'invalid_reason': ''})
            have.add(cid)
    for code, cid in LOINC_ADD.items():
        if code not in loinc_have:
            add(cid, f'LOINC {code} (test)', 'Measurement', 'LOINC', 'Lab Test', code)
    for cid, name, dom, cls in SNOMED_ADD:
        add(cid, name, dom, 'SNOMED', cls, f'test{cid}')
    for name, cid in INGREDIENTS.items():
        add(cid, name, 'Drug', 'RxNorm', 'Ingredient', f'rx{cid}')
    for code, (cid, _) in ATC.items():
        add(cid, f'ATC {code} (test)', 'Drug', 'ATC', 'ATC 3rd' if len(code) == 4 else 'ATC 4th', code, 'C')
    add(T + 901, 'N18 (ICD10 test source)', 'Condition', 'ICD10', 'ICD10 code', 'N18', '')
    con = pd.concat([syn, pd.DataFrame(rows)], ignore_index=True)
    for c in ('valid_start_date', 'valid_end_date'):
        con[c] = con[c].str.replace('-', '', regex=False)
    con.to_csv(os.path.join(vdir, 'CONCEPT.csv'), sep='\t', index=False)
    anc = [(a, d, 0 if a == d else 1, 0 if a == d else 1) for a, ds in ANCESTOR for d in ds]
    for code, (cid, ings) in ATC.items():
        anc += [(cid, INGREDIENTS[i], 2, 2) for i in ings]
    pd.DataFrame(anc, columns=['ancestor_concept_id', 'descendant_concept_id', 'min_levels_of_separation',
                               'max_levels_of_separation']).to_csv(os.path.join(vdir, 'CONCEPT_ANCESTOR.csv'), sep='\t', index=False)
    rel = pd.read_csv(os.path.join(SYNTHEA, 'CONCEPT_RELATIONSHIP.csv'), dtype=str, keep_default_na=False)
    rel = rel[rel['relationship_id'] == 'Maps to']
    rel = pd.concat([rel, pd.DataFrame([{'concept_id_1': str(T + 901), 'concept_id_2': '46271022', 'relationship_id': 'Maps to',
                                         'valid_start_date': '1970-01-01', 'valid_end_date': '2099-12-31', 'invalid_reason': ''}])])
    for c in ('valid_start_date', 'valid_end_date'):
        rel[c] = rel[c].str.replace('-', '', regex=False)
    rel.to_csv(os.path.join(vdir, 'CONCEPT_RELATIONSHIP.csv'), sep='\t', index=False)


# ───────────────────────── raw-layout writer ─────────────────────────
def write_raw(root, basics, lab, drug, dx, base):
    pq = os.path.join(root, 'Data', 'parquets')
    xl = os.path.join(root, 'Data', 'CSV')
    bf = os.path.join(root, 'ML', 'Base_file')
    for d in (pq, xl, bf):
        os.makedirs(d, exist_ok=True)
    mojcols(basics).to_parquet(os.path.join(pq, 'BASICS_Total.parquet'), index=False)
    half = len(lab) // 2
    mojcols(lab.iloc[:half]).to_parquet(os.path.join(pq, 'LAB-1.parquet'), index=False)
    mojcols(lab.iloc[half:]).to_parquet(os.path.join(pq, 'LAB-2.parquet'), index=False)
    mojcols(drug).to_parquet(os.path.join(pq, 'DRUG_Total.parquet'), index=False)
    dx.to_excel(os.path.join(xl, '[CKD_AI]DIAGNOSIS_ICD10.xlsx'), index=False)     # xlsx headers are proper Korean
    base.to_csv(os.path.join(bf, 'SNUH_CKD_Analysis_Base.csv'), index=False)


def drug_cols(df):
    return df[['RID', '처방일자', '약품코드', '일반성분명', '용량', '1회투여량', '1일투약횟수', '투약기간', '투약일수', 'PRN처방여부']]


# ───────────────────────── Synthea27Nj reverse map ─────────────────────────
SYN_LAB = {3051825: 'Creatinine (serum)', 3005456: '[POCT, ABGA]Potassium', 3000963: 'Hb(검사24시간가능)',
           3004410: 'Hb A1c', 3004295: 'BUN(검사24시간가능)', 3000483: 'Glucose(검사24시간가능)',
           3027114: 'Cholesterol(검사24시간가능)', 3007070: 'HDL-Cholesterol(검사24시간가능)', 3022192: 'Triglyceride',
           3000285: 'Sodium (serum)(검사24시간가능)', 3032503: 'Calcium(검사24시간가능)', 3014094: 'CO2, total (serum)'}
SYN_DX = {320128: 'I10', 201826: 'E11.9', 443614: 'N18.1', 432867: 'E78.5', 439777: 'D64.9', 4120314: 'E78.1',
          317576: 'I25.1', 4229440: 'I50.9', 4226121: 'E11.3'}
DX_MAP_SYN = [('I10', 320128), ('E11.9', 201826), ('E11.3', 201826), ('N18.1', 443614)]


def ingredient_names(name):
    parts = [p.strip().lower() for p in re.split(r'\s/\s', re.sub(r'^\{.*?\(|\).*$|^\d+\s+\w+\s+', '', name))]
    out = []
    for p in parts:
        m = re.match(r'([a-z][a-z ,\-]*?)\s+[\d.]', p)
        out.append((m.group(1) if m else p.split(' ')[0]).strip(' ,'))
    return [o for o in out if o]


def build_synthea(root):
    rd = lambda t: pd.read_csv(os.path.join(SYNTHEA, f'{t}.csv'), keep_default_na=False, dtype=str)  # noqa: E731
    per, vis, mea, drg, con, cpt = (rd(t) for t in ('PERSON', 'VISIT_OCCURRENCE', 'MEASUREMENT', 'DRUG_EXPOSURE',
                                                    'CONDITION_OCCURRENCE', 'CONCEPT'))
    rid = {p: str(100000 + int(p)) for p in per['person_id']}
    birth = {p: f'{int(y):04d}{int(m):02d}' for p, y, m in zip(per['person_id'], per['year_of_birth'], per['month_of_birth'])}
    sex = dict(zip(per['person_id'], per['gender_source_value']))
    vt = {'9201': '입원', '9202': '외래', '9203': '응급'}
    basics = pd.DataFrame({'연구별 환자 ID': vis['person_id'].map(rid), '내원일자': vis['visit_start_date'],
                           '성별': vis['person_id'].map(sex), '생년월': vis['person_id'].map(birth),
                           '내원구분': vis['visit_concept_id'].map(vt)})
    cname = dict(zip(cpt['concept_id'], cpt['concept_name']))
    mid = mea['measurement_concept_id'].astype(int)
    lab = pd.DataFrame({'RID': mea['person_id'].map(rid),
                        '검사시행일': pd.to_datetime(mea['measurement_date']),
                        '검사명': [SYN_LAB.get(c, cname.get(str(c), f'concept {c}')) for c in mid],
                        '검사결과단위': mea['unit_source_value'].replace('None', ''),
                        '검사결과': mea['value_as_number']})
    drug = pd.DataFrame({'RID': drg['person_id'].map(rid), '처방일자': drg['drug_exposure_start_date'].str.replace('-', ''),
                         '약품코드': drg['drug_source_value'], '일반성분명': drg['drug_concept_id'].map(cname).fillna('?'),
                         '용량': '', '1회투여량': '', '1일투약횟수': '', '투약기간': '', '투약일수': drg['days_supply'],
                         'PRN처방여부': 'N'})
    dx = pd.DataFrame({'연구별 환자 ID': con['person_id'].map(rid), 'ICD10코드': [SYN_DX.get(int(c), 'R69') for c in con['condition_concept_id']],
                       '진단일자': pd.to_datetime(con['condition_start_date']), '진단명': con['condition_concept_id'].map(cname)})
    rng = np.random.default_rng(3)
    pids = sorted(rid.values())[:20]
    base = pd.DataFrame({'RID': pids, 'Outcome_40': [1, 0] * 10, 'Baseline_eGFR': rng.uniform(10, 110, 20).round(1)})
    write_raw(root, basics, lab, drug_cols(drug), dx, base)

    maps = os.path.join(root, 'maps')
    os.makedirs(maps, exist_ok=True)
    import shutil
    shutil.copy(os.path.join(HERE, 'seed_lab_map.csv'), os.path.join(maps, 'lab_map.csv'))   # contains-rule seed, test only
    pd.DataFrame([{'icd10_code': c, 'condition_concept_id': i, 'domain_id': '', 'source_concept_id': '', 'source': 'test'}
                  for c, i in DX_MAP_SYN]).to_csv(os.path.join(maps, 'dx_map.csv'), index=False)
    rows = []
    for code, name in drug[['약품코드', '일반성분명']].drop_duplicates().itertuples(index=False):
        low = name.lower()
        excl = 'topical' if re.search(r'inhaler|spray|vaginal', low) else ''
        for ing in ingredient_names(name):
            cid = INGREDIENTS.get(ing, T + 600 + zlib.crc32(ing.encode()) % 90000)
            rows.append({'drug_code': code, 'ingredient_name': name, 'drug_concept_id': cid, 'exclude': int(bool(excl)),
                         'exclude_reason': excl, 'route': '', 'source': 'test'})
    pd.DataFrame(rows).to_csv(os.path.join(maps, 'drug_map.csv'), index=False)
    return {'n_person': len(per), 'n_measurement': len(mea), 'n_condition': len(con),
            'n_visit_distinct': vis[['person_id', 'visit_start_date', 'visit_concept_id']].drop_duplicates().shape[0],
            'mapped_measure_rows': int(mid.isin(list(SYN_LAB)).sum()),
            'mapped_measure_sum': float(pd.to_numeric(mea.loc[mid.isin(list(SYN_LAB)), 'value_as_number'], errors='coerce').sum()),
            'n_drug_rows_expected': int(sum(max(1, len(ingredient_names(n))) for n in drug['일반성분명']))}


# ───────────────────────── synthetic CKD extract ─────────────────────────
LAB_SPEC = {  # feature: (test names [lab_config], unit, low, high)
    'BUN': (['BUN(검사24시간가능)'], 'mg/dL', 5, 80), 'Uric_Acid': (['Uric Acid(검사24시간가능)'], 'mg/dL', 2, 12),
    'Sodium': (['Sodium (serum)(검사24시간가능)'], 'mmol/L', 128, 148),
    'Potassium': (['Potassium (serum)(검사24시간가능)', '[POCT, ABGA]Potassium'], 'mmol/L', 3.0, 6.0),
    'Calcium': (['Calcium(검사24시간가능)'], 'mg/dL', 7.5, 10.5), 'Phosphorus': (['Phosphorus(검사24시간가능)'], 'mg/dL', 2, 7),
    'Bicarbonate': (['CO2, total (serum)'], 'mmol/L', 15, 32), 'Albumin': (['Albumin(검사24시간가능)'], 'g/dL', 2.5, 5),
    'Total_Protein': (['Protein, total(검사24시간가능)'], 'g/dL', 5, 8.5),
    'Total_Bilirubin': (['Bilirubin, total(검사24시간가능)'], 'mg/dL', 0.2, 2), 'AST': (['GOT (AST)(검사24시간가능)'], 'U/L', 10, 90),
    'ALT': (['GPT (ALT)(검사24시간가능)'], 'U/L', 5, 90), 'GGT': (['GGT(검사24시간가능)'], 'U/L', 8, 200),
    'Hb': (['Hb(검사24시간가능)'], 'g/dL', 8, 16), 'HbA1c': (['Hb A1c'], '%', 4.8, 10),
    'Glucose': (['Glucose(검사24시간가능)'], 'mg/dL', 70, 300), 'HDL': (['HDL-Cholesterol(검사24시간가능)'], 'mg/dL', 25, 90),
    'TG': (['Triglyceride'], 'mg/dL', 40, 500), 'Cholesterol': (['Cholesterol(검사24시간가능)'], 'mg/dL', 100, 300),
    'UACR_Raw': (['Microalbumin/Creatinine Ratio'], 'mg/g', 5, 3000)}
PRODUCTS = [('A001', 'Losartan 50mg tab', ['losartan'], ''), ('A002', 'Amlodipine/Valsartan 5/80mg tab', ['amlodipine', 'valsartan'], ''),
            ('A003', 'Ramipril 5mg cap', ['ramipril'], ''), ('A004', 'Atorvastatin 10mg tab', ['atorvastatin'], ''),
            ('A005', 'Rosuvastatin 5mg tab', ['rosuvastatin'], ''), ('A006', 'Metformin 500mg tab', ['metformin'], ''),
            ('A007', 'Nystatin 100,000U/mL susp', ['nystatin'], ''),
            ('A008', 'Fluticasone 50mcg nasal spray', ['fluticasone'], 'topical'),
            ('A009', '0.9% Normal saline 1L bag', ['sodium chloride'], 'fluid'),
            ('A010', '(임상)Telmisartan 40mg tab', ['telmisartan'], 'investigational'),
            ('A011', 'Simvastatin 20mg tab', ['simvastatin'], ''), ('A011B', 'Simvastatin 20mg tab', ['simvastatin'], '')]
DX_MAP_SYNTH = [('N18.1', 443614), ('N18.3', T + 102), ('N18.9', 46271022), ('I10', 320128), ('E11.9', 201826),
                ('E14.9', 201820), ('N03.9', 4263367), ('Z49.1', T + 201), ('T86.1', T + 203), ('Z99.2', T + 202)]


def _dates(rng, lo, hi, k, taken=None):
    """k distinct dates in [lo, hi] (inclusive), avoiding dates in `taken`."""
    span = (hi - lo).days
    if span < 0:
        return []
    pool = [d for d in rng.choice(span + 1, min(k * 3, span + 1), replace=False)]
    out = []
    for d in pool:
        x = lo + timedelta(days=int(d))
        if taken is None or x not in taken:
            out.append(x)
        if len(out) == k:
            break
    return sorted(out)


def build_synthetic(root, n=400, seed=7):
    rng = np.random.default_rng(seed)
    B, Lb, D, X = [], [], [], []
    pub = []
    for i in range(n):
        pid = str(200000 + i)
        male = rng.random() < 0.5
        yob = int(rng.integers(1935, 2000)) if rng.random() > 0.04 else 2008
        start = date(2005, 1, 1) + timedelta(days=int(rng.integers(0, 3000)))
        has_ckd = rng.random() < 0.8
        dx_date = start + timedelta(days=int(rng.integers(30, 1500)))
        end = dx_date + timedelta(days=int(rng.integers(800, 2400) if rng.random() < 0.88 else rng.integers(100, 600)))
        visits = sorted(set([start, end] + _dates(rng, start, end, int(rng.integers(3, 15)))))
        mob = int(rng.integers(1, 13))
        for v in visits:
            B.append({'연구별 환자 ID': pid, '내원일자': v.isoformat(), '성별': 'M' if male else 'F', '생년월': f'{yob}{mob:02d}',
                      '내원구분': '입원' if rng.random() < 0.1 else '외래',
                      'BMI': round(float(rng.uniform(17, 35)), 1) if rng.random() < 0.4 else None})
        dxd = set()
        if has_ckd:
            X.append((pid, rng.choice(['N18.1', 'N18.3', 'N18.9']), dx_date))
            X.append((pid, 'N18.3', dx_date + timedelta(days=int(rng.integers(100, 400)))))
        for code, p in (('I10', 0.6), ('E11.9', 0.3), ('E14.9', 0.05), ('N03.9', 0.06), ('Z49.1', 0.03), ('T86.1', 0.03),
                        ('Z99.2', 0.03), ('J06.9', 0.5), ('K21.9', 0.3)):
            if rng.random() < p:
                X.append((pid, code, start + timedelta(days=int(rng.integers(0, (end - start).days + 1)))))
        # serum creatinine: distinct dates, some before dx (slope), several after (outcome)
        cr_dates = _dates(rng, start, end, int(rng.integers(1, 12)))
        cr0 = float(np.exp(rng.normal(0.4, 0.5)))
        decline = rng.random() < 0.35
        for d in cr_dates:
            yrs = (d - dx_date).days / 365.25
            v = cr0 * (1 + (0.35 * yrs if decline and yrs > 0 else 0.03 * yrs)) * float(np.exp(rng.normal(0, 0.05)))
            name = rng.choice(['Creatinine (serum)', 'Creatinine(검사24시간가능)', '[처방불가]Creatinine (serum, em)'])
            val = f'{max(v, 0.2):.2f}' if rng.random() > 0.02 else rng.choice(['45.0', '<0.1'])
            Lb.append((pid, d, name, 'mg/dL', val))
        lo, hi = max(start, dx_date - timedelta(days=500)), min(end, dx_date + timedelta(days=500))
        uacr_taken = set()
        for f, (names, unit, a, b) in LAB_SPEC.items():
            if rng.random() < 0.75:
                for d in _dates(rng, lo, hi, int(rng.integers(1, 4))):
                    Lb.append((pid, d, rng.choice(names), unit, f'{rng.uniform(a, b):.2f}'))
                    if f == 'UACR_Raw':
                        uacr_taken.add(d)
        if rng.random() < 0.05:            # implausible K within 365 d before the first CKD dx (v205 rule 3)
            Lb.append((pid, dx_date - timedelta(days=int(rng.integers(1, 300))), 'Potassium (serum)(검사24시간가능)', 'mmol/L', '12.5'))
        if rng.random() < 0.03:            # implausible Hb on the dx day
            Lb.append((pid, dx_date, '[POCT, ABGA]Hb', 'g/dL', '2.1'))
        for d in _dates(rng, lo, hi, int(rng.integers(0, 3)), uacr_taken):   # urine pairs -> computed UACR
            uacr_taken.add(d)
            Lb.append((pid, d, 'Microalbumin (random urine)', 'mg/dL', f'{rng.uniform(0.1, 300):.2f}'))
            Lb.append((pid, d, 'Creatinine (random urine)', 'mg/dL', f'{rng.uniform(20, 250):.1f}'))
        if rng.random() < 0.1 and dx_date + timedelta(days=3) not in uacr_taken:
            Lb.append((pid, dx_date + timedelta(days=3), 'Microalbumin/Creatinine Ratio', 'g/g', f'{rng.uniform(0.01, 0.4):.3f}'))
        if rng.random() < 0.5:
            Lb.append((pid, dx_date + timedelta(days=5), 'WBC count', '10^3/uL', '6.1'))
        # prescriptions
        for _ in range(int(rng.integers(0, 10))):
            code, name, _, _ = PRODUCTS[int(rng.integers(0, len(PRODUCTS)))]
            d = start + timedelta(days=int(rng.integers(0, (end - start).days + 1)))
            days = int(rng.choice([0, 1, 7, 14, 28, 30, 60, 90]))
            D.append((pid, d.strftime('%Y%m%d'), code, name, str(days), 'Y' if rng.random() < 0.1 else 'N'))
        if has_ckd and dx_date.year - yob >= 19:
            pub.append(pid)
    basics = pd.DataFrame(B)
    lab = pd.DataFrame(Lb, columns=['RID', '검사시행일', '검사명', '검사결과단위', '검사결과'])
    lab['검사시행일'] = pd.to_datetime(lab['검사시행일'])
    lab = lab.sample(frac=1, random_state=1).reset_index(drop=True)
    drug = pd.DataFrame(D, columns=['RID', '처방일자', '약품코드', '일반성분명', '투약일수', 'PRN처방여부'])
    for c in ('용량', '1회투여량', '1일투약횟수', '투약기간'):
        drug[c] = ''
    dx = pd.DataFrame(X, columns=['연구별 환자 ID', 'ICD10코드', '진단일자'])
    dx['진단일자'] = pd.to_datetime(dx['진단일자'])
    base = pd.DataFrame({'RID': pub, 'Outcome_40': (rng.random(len(pub)) < 0.35).astype(int),
                         'Baseline_eGFR': rng.uniform(8, 120, len(pub)).round(1)})
    write_raw(root, basics, lab, drug_cols(drug), dx, base)

    maps = os.path.join(root, 'maps')
    os.makedirs(maps, exist_ok=True)
    import shutil
    shutil.copy(os.path.join(HERE, 'seed_lab_map.csv'), os.path.join(maps, 'lab_map.csv'))   # contains-rule seed, test only
    pd.DataFrame([{'icd10_code': c, 'condition_concept_id': i, 'domain_id': '', 'source_concept_id': '', 'source': 'test'}
                  for c, i in DX_MAP_SYNTH]).to_csv(os.path.join(maps, 'dx_map.csv'), index=False)
    rows = []
    for code, name, ings, excl in PRODUCTS:
        for ing in ings:
            rows.append({'drug_code': '*' if code.startswith('A011') else code, 'ingredient_name': name,
                         'drug_concept_id': INGREDIENTS[ing], 'exclude': int(bool(excl)), 'exclude_reason': excl,
                         'route': 'oral', 'source': 'test'})
    pd.DataFrame(rows).drop_duplicates().to_csv(os.path.join(maps, 'drug_map.csv'), index=False)
    pd.DataFrame([{'atc_code': 'C09A', 'descendant_concept_id': INGREDIENTS['hydrochlorothiazide'], 'ingredient_name': 'hydrochlorothiazide',
                   'source': 'test: stands for an RxNorm Extension ingredient without an ATC ancestor'}]).to_csv(os.path.join(maps, 'atc_supplement.csv'), index=False)
    return {'basics': basics, 'lab': lab, 'drug': drug, 'dx': dx, 'base': base,
            'excluded_names': {n for _, n, _, e in PRODUCTS if e}}


# ───────────────────────── the real layout (P1, 2026-10-14) ─────────────────────────
def build_real_layout(root, n=300, seed=11, icd=False):
    """The layout P1 showed on the real extract: BASICS with an all-null birth column and a patient-name column, a DIAGNOSIS
    sheet with dates and English diagnosis names but no ICD-10 code column (icd=True adds one). The patient-name column carries a
    marker (ZZPN) that must never reach an output file; two diagnosis names are rare (below 11 patients) and one is a one-off
    free text (ZZSECRET) -- the catalogue must leave all three out."""
    rng = np.random.default_rng(seed)
    common = ['Essential (primary) hypertension', 'Type 2 diabetes mellitus', 'Chronic kidney disease, stage 3 (N18.3)',
              'Hyperlipidemia, unspecified', 'Gout (M10.9)', 'Anemia in chronic kidney disease']
    B, X, pids = [], [], []
    for i in range(n):
        pid = str(300000 + i)
        pids.append(pid)
        sex = 'M' if rng.random() < 0.5 else 'F'
        yob, mob = int(rng.integers(1935, 2005)), int(rng.integers(1, 13))
        k_date = date(2008, 1, 1) + timedelta(days=int(rng.integers(0, 3500)))
        early = i < 40                                   # first CKD diagnosis before the approved period (1996-1999)
        if early:
            k_date = date(1996, 3, 1) + timedelta(days=int(rng.integers(0, 1200)))
        names = [common[j] for j in range(len(common)) if rng.random() < (0.7 if j < 2 else 0.3)]
        if early and i % 2 == 0:
            names.append('CRF')
        if i < 5:
            names.append('Rare condition xyz')
        if i == 7:
            names.append('Patient complains of ZZSECRET')
        for nm in names or [common[0]]:
            d = max(k_date, date(2005, 1, 1)) + timedelta(days=int(rng.integers(0, 900)))
            B.append({'연구별 환자 ID': pid, '환자명': f'ZZPN{i % 5}', '성별': sex, '생년월일': None, '병원코드': 'H1',
                      '내원일자': d.isoformat(), '기타진단일자': k_date.isoformat(), '기타진단명': nm})
            row = {'연구별 환자 ID': pid, '환자명': f'ZZPN{i % 5}', '성별': sex, '생년월일': f'{yob}{mob:02d}',
                   '진단일자_OTHER': d.isoformat(), '진단일자_KIDNEYDS': k_date.isoformat(), '진단명_OTHER': nm}
            if icd:
                row['ICD10코드'] = 'N18.3'
            X.append(row)
    basics = pd.DataFrame(B)
    basics['생년월일'] = basics['생년월일'].astype('object')
    lab = pd.DataFrame({'RID': [pids[i % n] for i in range(2000)],
                        '검사시행일': pd.to_datetime('2015-01-01') + pd.to_timedelta(rng.integers(0, 3000, 2000), unit='D'),
                        '검사명': rng.choice(['Creatinine(검사24시간가능)', 'Hb(검사24시간가능)', 'Albumin'], 2000),
                        '검사결과단위': rng.choice(['mg/dL', 'g/dL', None], 2000),
                        '검사결과': [f'{v:.2f}' for v in rng.uniform(0.5, 15, 2000)]})
    # rows outside the approved period 2000-01-01..2025-07-31 (the real extract has labs from 1999-09 and labs / drugs to 2025-10)
    out_lab = pd.DataFrame({'RID': [pids[i % n] for i in range(60)],
                            '검사시행일': [pd.Timestamp('1999-12-31') if i % 2 else pd.Timestamp('2025-08-01') for i in range(60)],
                            '검사명': 'OutsideWindowTest', '검사결과단위': 'mg/dL', '검사결과': '1.00'})
    lab = pd.concat([lab, out_lab], ignore_index=True)
    drug = pd.DataFrame({'RID': [pids[i % n] for i in range(500)], '처방일자': '20150101',
                         '약품코드': rng.choice(['A1', 'A2', 'A3'], 500), '일반성분명': rng.choice(['Amlodipine 5mg tab', 'Losartan 50mg tab'], 500),
                         '투약일수': '30', 'PRN처방여부': 'N'})
    out_drug = drug.iloc[:40].copy()
    out_drug['처방일자'] = '20251015'
    out_drug['약품코드'] = 'OUTDRUG'
    drug = pd.concat([drug, out_drug], ignore_index=True)
    for c in ('용량', '1회투여량', '1일투약횟수', '투약기간'):
        drug[c] = ''
    write_raw(root, basics, lab, drug_cols(drug), pd.DataFrame(X), pd.DataFrame({'RID': pids}))
    pd.DataFrame({'RID': pids}).to_excel(os.path.join(root, 'Data', 'CSV', '[CKD_AI]RID_LIST.xlsx'), index=False)
    return {'pids': pids, 'basics': basics, 'dx': pd.DataFrame(X)}


# ───────────────────────── the real layout with diagnosis NAMES (P3 names path) ─────────────────────────
NAME_OF = {'N18.1': 'Chronic kidney disease, stage 1', 'N18.3': 'Chronic kidney disease, stage 3', 'N18.9': 'Chronic kidney disease',
           'I10': 'Essential hypertension', 'E11.9': 'Type 2 diabetes mellitus without complication',
           'E14.9': 'Diabetes mellitus with renal complications', 'N03.9': 'Chronic nephritic syndrome', 'Z49.1': 'hemodialysis',
           'T86.1': 'kidney transplant failure', 'Z99.2': 'Dependence on renal dialysis', 'J06.9': 'Acute upper respiratory infection',
           'K21.9': 'Gastro-esophageal reflux disease'}
CKD_CODES = ('N18.1', 'N18.3', 'N18.9')


def build_synthetic_names(root, n=400, seed=7):
    """The same patients as build_synthetic, written in the layout P1 showed on the real extract: BASICS without birth, with a patient-name
    column and one row per visit date and diagnosis NAME; a DIAGNOSIS sheet with birth, sex, the first kidney-disease diagnosis date
    (KIDNEYDS) and one other diagnosis; no ICD-10 code anywhere. The first CKD diagnosis of a patient becomes KIDNEYDS, every other
    diagnosis becomes a name row of BASICS on its date. Returns the codes fixture (the reference runs on it) plus the name events."""
    fx = build_synthetic(root + '_codes', n=n, seed=seed)
    b, dx = fx['basics'], fx['dx'].copy()
    pid_c, d_c = '연구별 환자 ID', '진단일자'
    first = dx[dx['ICD10코드'].isin(CKD_CODES)].groupby(pid_c)[d_c].min()
    dx = dx.join(first.rename('first_ckd'), on=pid_c)
    ev = dx[~(dx['ICD10코드'].isin(CKD_CODES) & (dx[d_c] == dx['first_ckd']))].copy()       # everything but the first CKD diagnosis
    ev['name'] = ev['ICD10코드'].map(NAME_OF)
    sex = b.groupby(pid_c)['성별'].first()
    birth = b.groupby(pid_c)['생년월'].first()
    kstr = first.dt.strftime('%Y-%m-%d')
    visits = pd.DataFrame({pid_c: b[pid_c], '환자명': 'ZZPN', '성별': b['성별'], '생년월일': None, '병원코드': 'H1', '내원일자': b['내원일자'],
                           '기타진단일자': b[pid_c].map(kstr), '기타진단명': None})
    names = pd.DataFrame({pid_c: ev[pid_c], '환자명': 'ZZPN', '성별': ev[pid_c].map(sex), '생년월일': None, '병원코드': 'H1',
                          '내원일자': ev[d_c].dt.strftime('%Y-%m-%d'), '기타진단일자': ev[pid_c].map(kstr), '기타진단명': ev['name']})
    # a diagnosis dated before the approved period (1998): P3 must drop it, and it must not reach any flag
    old_pids = sorted(fx['basics'][pid_c].unique())[:12]
    old = pd.DataFrame({pid_c: old_pids, '환자명': 'ZZPN', '성별': [sex[p] for p in old_pids], '생년월일': None, '병원코드': 'H1',
                        '내원일자': '1998-05-05', '기타진단일자': [kstr.get(p) for p in old_pids], '기타진단명': 'Essential hypertension'})
    rare_pids = sorted(fx['basics'][pid_c].unique())[20:23]          # a free-text diagnosis of 3 patients: never listed in an output
    rare = pd.DataFrame({pid_c: rare_pids, '환자명': 'ZZPN', '성별': [sex[p] for p in rare_pids], '생년월일': None, '병원코드': 'H1',
                         '내원일자': '2015-03-03', '기타진단일자': [kstr.get(p) for p in rare_pids], '기타진단명': 'Rare complaint ZZSECRET text'})
    basics = pd.concat([visits, names, old, rare], ignore_index=True)
    pids = sorted(b[pid_c].unique())
    other = ev.sort_values([pid_c, d_c]).groupby(pid_c).first()
    sheet = pd.DataFrame({pid_c: pids, '환자명': 'ZZPN', '성별': [sex[p] for p in pids], '생년월일': [birth[p] for p in pids],
                          '진단일자_OTHER': [other[d_c].dt.strftime('%Y-%m-%d').get(p) for p in pids],
                          '진단일자_KIDNEYDS': [kstr.get(p) for p in pids], '진단명_OTHER': [other['name'].get(p) for p in pids]})
    write_raw(root, basics, fx['lab'], drug_cols(fx['drug']), sheet, fx['base'])
    maps = os.path.join(root, 'maps')
    os.makedirs(maps, exist_ok=True)
    import shutil
    for f in ('lab_map.csv', 'drug_map.csv', 'atc_supplement.csv'):
        shutil.copy(os.path.join(root + '_codes', 'maps', f), maps)
    code_map = dict(DX_MAP_SYNTH)
    rows = [{'icd10_code': NAME_OF[c], 'condition_concept_id': i, 'domain_id': '', 'source_concept_id': '', 'source': 'test'}
            for c, i in code_map.items() if c in NAME_OF]
    rows.append({'icd10_code': 'KIDNEYDS', 'condition_concept_id': 46271022, 'domain_id': '', 'source_concept_id': '', 'source': 'test'})
    pd.DataFrame(rows).to_csv(os.path.join(maps, 'dx_map.csv'), index=False)
    shutil.copy(os.path.join(os.path.dirname(HERE), 'maps', 'raw_layout.json'), maps)       # the production layout of the real extract
    return {'codes': fx, 'events': ev, 'old_pids': old_pids, 'first_ckd': first}
