# -*- coding: utf-8 -*-
"""P4 -- per site: ATLAS cohort v205 + the 36 KRCP features (v1.3 definitions) from the site's own CDM.

Each site DuckDB from P3 (site_B1_0..2, site_B2_0..2, holdout) is processed on its own, as a hospital
would: sql/v205_cohort_duckdb.sql -> cohort + cohort_inclusion tables in that DuckDB, then the features at
the cohort start (index) date:
  Age, Sex_Male                 YEAR(index) - year_of_birth; gender 8507 -> 1, anything else -> 0
  23 lab values                 LOINC concept sets (+ descendants), lab_config plausible range (outside ->
                                missing), value closest to the index date (either side, as in v1.3 training;
                                --baseline pre = on/before index only); ties -> earlier date, then lower value
  UACR                          ACR measurements + same-day urine albumin / urine creatinine x 1000, < 0.5 -> x1000,
                                > 20,000 -> missing (DATAPREP cell 1)
  Baseline_eGFR                 CKD-EPI 2021 on the baseline creatinine, age at index
  eGFR_Slope                    (Baseline_eGFR - eGFR of the latest creatinine >= 90 days before the baseline
                                creatinine) / years; |slope| > 60 -> missing (v1.3)
  History_HTN/DM, Subgroup_DKD/GN  ICD-10 I10-I15 / E10-E14 / E10-E14 / N00-N08 in condition (or routed procedure)
                                source codes; when P3 built the CDM from diagnosis NAMES (CDM_SOURCE dx_layout=names, the real
                                extract has no ICD-10 column) the text patterns of the published pipeline on the source text
                                source codes on/before index (--window all = whole record, as published)
  BMI                           mean of BMI measurements on/before index (--window all = whole record)
  Dur_ACE_ARB_days / Dur_Statin_days, Drug_RAASi / Drug_Statins
                                union of prescription days up to and including index for ingredients under
                                ATC C09A/C09C and C10AA (concept_ancestor); PRN (sig) and excluded products
                                (concept 0) never count; flag = days > 0
  Outcome_40 (y)                min eGFR in index..index+730 d < 60 % of baseline, or < 15
Outputs
  data/ckd_pilot/cdm/features/<db>.parquet   restricted: site person_id, index date, features
  data/ckd_pilot/matrix_snuh_cdm.parquet     restricted: B1-site rows (split=train, site_b1/site_b2) + holdout
                                             (split=val); no IDs; read by analysis/snuh_pilot with PILOT_TAG=cdm
  out/p4_site_features.txt                   aggregates: attrition, cohort size, outcome rate, missingness
  out/p4_agreement.txt (--agreement)         CDM-derived vs the v1.3 matrix through the P3 crosswalk
  --entry visit writes the same files with a suffix (features_visit/, matrix_snuh_cdmv.parquet = PILOT_TAG cdmv, *_visit.txt); see run_cohort

    python p4_site_features.py --irb E-XXXX-XXX-XXXX [--agreement] [--entry ckd|visit] [--rrt-icd Z49,Z99.2,Z94.0]
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdm_lib as C  # noqa: E402
from cdm_lib import L, lit, cell, pct  # noqa: E402


# ───────────────────────── cohort ─────────────────────────
# --entry ckd    sql/v205_cohort_duckdb.sql: Cohort_OHDSI_CKD_v205 as shared with CKD_ML (index = first CKD diagnosis with 730 d observation
#                after it; >= 2 serum creatinine in index +0..+730).
# --entry visit  sql/v205_firstvisit_cohort_duckdb.sql: the pipeline that built the published 28,209-person cohort (SNUH_CKD_DATAPREP.ipynb,
#                step 1): index = first visit; >= 2 serum creatinine records over the whole record, first and last >= 730 d apart; the
#                v205 age rule and the v205 exclusions (RRT before the index, impossible K / Hb in the year before) are kept.
COHORT_SQL = {'ckd': 'v205_cohort_duckdb.sql', 'visit': 'v205_firstvisit_cohort_duckdb.sql'}
ENTRY_LABEL = {'ckd': 'entry: first CKD dx with 730 d observation after',
               'visit': 'entry: first visit'}
CR_LABEL = {'ckd': '>= 2 creatinine in 0..730 d', 'visit': '>= 2 creatinine, first to last >= 730 d apart'}


def run_cohort(con, entry='ckd'):
    sql = open(os.path.join(C.SQL_DIR, COHORT_SQL[entry]), encoding='utf-8').read()
    sql = '\n'.join(ln for ln in sql.splitlines() if not ln.strip().startswith('--'))
    for stmt in [s for s in sql.split(';') if s.strip()]:
        con.execute(stmt)
    n_entry = con.execute('SELECT count(*) FROM cohort_inclusion').fetchone()[0]
    att = [(ENTRY_LABEL[entry], n_entry)]
    cond = []
    for rule, label in (('rule_age', 'age >= 19'), ('rule_creatinine', CR_LABEL[entry]),
                        ('rule_no_rrt', 'no RRT on/before index'), ('rule_no_implausible', 'no implausible K/Hb in -365..0 d')):
        cond.append(rule)
        att.append((label, con.execute(f"SELECT count(*) FROM cohort_inclusion WHERE {' AND '.join(cond)}").fetchone()[0]))
    single = {r: con.execute(f'SELECT count(*) FILTER (WHERE NOT {r}) FROM cohort_inclusion').fetchone()[0]
              for r in ('rule_age', 'rule_creatinine', 'rule_no_rrt', 'rule_no_implausible')}
    info = {}
    if entry == 'visit':      # the CKD diagnosis is not a criterion here (the extract is a CKD cohort); say how many members lack a record of it
        info['no_ckd_record'] = con.execute("""SELECT count(*) FROM cohort c WHERE NOT EXISTS (
            SELECT 1 FROM condition_occurrence co JOIN codesets cs ON cs.codeset_id = 0 AND cs.concept_id = co.condition_concept_id
            WHERE co.person_id = c.subject_id AND co.condition_start_date <= c.cohort_start_date)""").fetchone()[0]
    return att, single, info


def rrt_sensitivity_text(con):
    """Names layout: cohort persons with a diagnosis name about dialysis / kidney transplant on or before the index date."""
    out = {}
    for label, pat in C.RRT_TEXT.items():
        out[label] = con.execute(f"""SELECT count(DISTINCT c.subject_id) FROM cohort c JOIN (
            SELECT person_id, condition_start_date d, condition_source_value s FROM condition_occurrence
            UNION ALL SELECT person_id, procedure_date, procedure_source_value FROM procedure_occurrence) e
            ON e.person_id = c.subject_id AND e.d <= c.cohort_start_date
            WHERE regexp_matches(lower(CAST(e.s AS VARCHAR)), {lit(pat)})""").fetchone()[0]
    return out


def rrt_sensitivity(con, prefixes):
    out = {}
    for p in prefixes:
        k = C.norm_icd(p)
        out[p] = con.execute(f"""SELECT count(DISTINCT c.subject_id) FROM cohort c JOIN (
            SELECT person_id, condition_start_date d, condition_source_value s FROM condition_occurrence
            UNION ALL SELECT person_id, procedure_date, procedure_source_value FROM procedure_occurrence) e
            ON e.person_id = c.subject_id AND e.d <= c.cohort_start_date
            WHERE starts_with({C.icd_norm_sql('e.s')}, {lit(k)})""").fetchone()[0]
    return out


# ───────────────────────── features ─────────────────────────
def feature_concepts(con):
    vals = ', '.join(f'({lit(f)}, {lit(code)})' for f, codes, _, _ in C.LAB_FEATURES for code in codes)
    vals += ', ' + ', '.join(f"('BMI', {lit(c)})" for c in C.BMI_LOINC)
    con.execute(f"""CREATE OR REPLACE TEMP TABLE feat_c AS
        WITH roots AS (SELECT f.feature, c.concept_id FROM (VALUES {vals}) f(feature, code)
                       JOIN concept c ON c.vocabulary_id = 'LOINC' AND c.concept_code = f.code)
        SELECT feature, concept_id FROM roots
        UNION SELECT r.feature, ca.descendant_concept_id FROM roots r
        JOIN concept_ancestor ca ON ca.ancestor_concept_id = r.concept_id""")
    got = dict(con.execute('SELECT feature, count(*) FROM feat_c GROUP BY 1').fetchall())
    return {f: got.get(f, 0) for f in [f for f, _, _, _ in C.LAB_FEATURES] + ['BMI']}


def nearest(df, idx, pre_only):
    """One row per (person_id, feature): smallest |date - index|; ties -> earlier date, then lower value.
    Ties are broken by value, not by event id, so every site DB and every rebuild gives the same answer."""
    df = df.merge(idx, on='person_id')
    if pre_only:
        df = df[df['d'] <= df['index_date']]
    df = df.assign(gap=(df['d'] - df['index_date']).abs())
    return df.sort_values(['person_id', 'feature', 'gap', 'd', 'v']).groupby(['person_id', 'feature'], sort=False).first()


def drug_days(con):
    """Days covered by the union of a person's prescription intervals per ATC class, up to the index date.
    iv is DISTINCT on purpose: `o` and `g` each sort by (s, e), and two identical (s, e) rows may come out in a
    different order in the two sorts (multi-threaded DuckDB, different row order in a site DB). The second row of
    such a pair at a block start can then be counted into the previous block and its overlap is counted twice
    (generated data: 30 of 60,000 persons off by up to 491 d with 4 threads; real extract: B1 and B2 copies of the
    same person differed by up to 61 d for fewer than 11 persons). With distinct rows the order is total."""
    cls_sql = ' UNION ALL '.join(
        f"""SELECT {lit(cls)} AS cls, ca.descendant_concept_id AS cid FROM concept a
            JOIN concept_ancestor ca ON ca.ancestor_concept_id = a.concept_id
            WHERE a.vocabulary_id = 'ATC' AND a.concept_code IN ({', '.join(lit(c) for c in codes)})"""
        for cls, codes in C.ATC_CLASSES.items())
    return con.execute(f"""
        WITH cls AS (SELECT DISTINCT cls, cid FROM ({cls_sql})),
        iv AS (SELECT DISTINCT de.person_id, cls.cls, de.drug_exposure_start_date AS s,
                      LEAST(de.drug_exposure_end_date + 1, c.cohort_start_date + 1) AS e
               FROM drug_exposure de JOIN cls ON cls.cid = de.drug_concept_id
               JOIN cohort c ON c.subject_id = de.person_id
               WHERE COALESCE(de.sig, '') <> 'PRN' AND de.drug_exposure_start_date <= c.cohort_start_date),
        o AS (SELECT *, max(e) OVER (PARTITION BY person_id, cls ORDER BY s, e
                                     ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev_e FROM iv),
        g AS (SELECT *, sum(CASE WHEN prev_e IS NULL OR s > prev_e THEN 1 ELSE 0 END)
                        OVER (PARTITION BY person_id, cls ORDER BY s, e ROWS UNBOUNDED PRECEDING) AS blk FROM o),
        b AS (SELECT person_id, cls, blk, max(e) - min(s) AS d FROM g GROUP BY ALL)
        SELECT person_id, cls, sum(d)::DOUBLE AS days FROM b GROUP BY ALL""").df()


def extract(con, baseline_pre, window_all):
    idx = con.execute("""SELECT c.subject_id AS person_id, c.cohort_start_date AS index_date, p.year_of_birth AS yob,
                                p.gender_concept_id FROM cohort c JOIN person p ON p.person_id = c.subject_id""").df()
    idx['index_date'] = pd.to_datetime(idx['index_date'])
    out = pd.DataFrame({'person_id': idx['person_id'], 'index_date': idx['index_date']}).set_index('person_id')
    n_concepts = feature_concepts(con)
    if idx.empty:
        out = out.reindex(columns=['index_date'] + C.FEATURES + ['y'])
        out.attrs['n_concepts'] = n_concepts
        return out
    yob = idx.set_index('person_id')['yob']
    male = (idx.set_index('person_id')['gender_concept_id'] == 8507).astype(int)
    out['Age'] = idx.set_index('person_id')['index_date'].dt.year - yob
    out['Sex_Male'] = male

    labs = con.execute("""SELECT m.person_id, f.feature, m.measurement_date AS d, m.value_as_number AS v
        FROM measurement m JOIN feat_c f ON f.concept_id = m.measurement_concept_id
        JOIN cohort c ON c.subject_id = m.person_id WHERE m.value_as_number IS NOT NULL
        ORDER BY m.person_id, f.feature, m.measurement_date, m.value_as_number""").df()   # fixed order -> same float sums
    labs['d'] = pd.to_datetime(labs['d'])
    keep = []
    for f, _, lo, hi in C.LAB_FEATURES:
        x = labs[labs['feature'] == f]
        if lo is not None:
            x = x[x['v'] >= lo]
        if hi is not None:
            x = x[x['v'] <= hi]
        keep.append(x)
    labs = pd.concat(keep, ignore_index=True)
    # UACR: measured ratio + same-day urine albumin / creatinine (mean per day) x 1000
    ur = labs[labs['feature'].isin(['Urine_Microalbumin', 'Urine_Creatinine'])]
    pv = ur.pivot_table(index=['person_id', 'd'], columns='feature', values='v', aggfunc='mean').reset_index()
    calc = pd.DataFrame(columns=['person_id', 'd', 'v'])
    if {'Urine_Microalbumin', 'Urine_Creatinine'} <= set(pv.columns):
        with np.errstate(divide='ignore', invalid='ignore'):
            pv['v'] = pv['Urine_Microalbumin'] / pv['Urine_Creatinine'] * 1000
        calc = pv[['person_id', 'd', 'v']].dropna()
    raw = labs.loc[labs['feature'] == 'UACR_Raw', ['person_id', 'd', 'v']]
    uacr = pd.concat([raw, calc], ignore_index=True)
    uacr.loc[uacr['v'] < 0.5, 'v'] *= 1000
    uacr = uacr[~(uacr['v'] > 20000)].assign(feature='UACR')
    labs = pd.concat([labs[labs['feature'] != 'UACR_Raw'], uacr], ignore_index=True)

    base = nearest(labs[['person_id', 'feature', 'd', 'v']], idx[['person_id', 'index_date']], baseline_pre)
    wide = base['v'].unstack('feature')
    for f in [f for f, _, _, _ in C.LAB_FEATURES if f != 'UACR_Raw'] + ['UACR']:
        out[f] = wide[f] if f in wide.columns else np.nan

    # eGFR: baseline (age at index), slope, outcome
    out['Baseline_eGFR'] = C.egfr_ckdepi2021(out['Creatinine'], out['Age'], out['Sex_Male'])
    cr = labs[labs['feature'] == 'Creatinine'].merge(idx[['person_id', 'index_date', 'yob']], on='person_id')
    cr['male'] = cr['person_id'].map(male)
    cr['egfr'] = C.egfr_ckdepi2021(cr['v'], cr['d'].dt.year - cr['yob'], cr['male'])
    bdate = base.xs('Creatinine', level='feature')['d'] if 'Creatinine' in wide.columns else pd.Series(dtype='datetime64[ns]')
    cr['bd'] = cr['person_id'].map(bdate)
    prior = cr[cr['d'] <= cr['bd'] - pd.Timedelta(days=90)].sort_values(['person_id', 'd', 'v']).groupby('person_id').last()
    slope = (out['Baseline_eGFR'].reindex(prior.index) - prior['egfr']) / ((prior['bd'] - prior['d']).dt.days / 365.25)
    n_prior = len(prior)
    slope[slope.abs() > 60] = np.nan
    out['eGFR_Slope'] = slope.reindex(out.index)
    # why the slope is (not) available: it needs a creatinine >= 90 d before the baseline creatinine (counts only; pooled by main)
    gap = ((base.xs('Creatinine', level='feature')['d'] - base.xs('Creatinine', level='feature')['index_date']).dt.days
           if 'Creatinine' in wide.columns else pd.Series(dtype=float))
    diag = {'persons': len(out), 'with_baseline_cr': int(len(gap)),
            'base_le_0': int((gap <= 0).sum()), 'base_1_90': int(gap.between(1, 90).sum()), 'base_91_365': int(gap.between(91, 365).sum()),
            'base_366_730': int(gap.between(366, 730).sum()), 'base_gt_730': int((gap > 730).sum()),
            'any_cr_on_or_before_index': int(cr.loc[cr['d'] <= cr['index_date'], 'person_id'].nunique()),
            'prior_cr_90d': int(n_prior), 'slope_ok': int(slope.notna().sum())}
    win = cr[(cr['d'] >= cr['index_date']) & (cr['d'] <= cr['index_date'] + pd.Timedelta(days=730))]
    mn = win.groupby('person_id')['egfr'].min().reindex(out.index)
    be = out['Baseline_eGFR']
    ok = mn.notna() & be.notna()
    out['y'] = (ok & ((mn < be * 0.6) | (mn < 15))).astype(int)

    # history flags from ICD-10 source codes
    hx = con.execute(f"""SELECT DISTINCT e.person_id, {C.icd3_sql('e.s')} AS c3, lower(CAST(e.s AS VARCHAR)) AS txt FROM cohort c JOIN (
            SELECT person_id, condition_start_date AS d, condition_source_value AS s FROM condition_occurrence
            UNION ALL SELECT person_id, procedure_date, procedure_source_value FROM procedure_occurrence) e
        ON e.person_id = c.subject_id {'' if window_all else 'AND e.d <= c.cohort_start_date'}""").df()
    if C.dx_layout(con) == 'names':
        for f, pat in C.TEXT_HISTORY.items():          # the text patterns of the published pipeline (no ICD-10 codes in the extract)
            ids = set(hx.loc[hx['txt'].str.contains(pat, regex=True, na=False), 'person_id'])
            out[f] = out.index.isin(ids).astype(int)
    else:
        for f, (lo, hi) in C.ICD_HISTORY.items():
            ids = set(hx.loc[(hx['c3'] >= lo) & (hx['c3'] <= hi), 'person_id'])
            out[f] = out.index.isin(ids).astype(int)

    bmi = con.execute(f"""SELECT m.person_id, m.value_as_number AS v FROM measurement m
        JOIN feat_c f ON f.concept_id = m.measurement_concept_id AND f.feature = 'BMI'
        JOIN cohort c ON c.subject_id = m.person_id
        WHERE m.value_as_number IS NOT NULL {'' if window_all else 'AND m.measurement_date <= c.cohort_start_date'}
        ORDER BY m.person_id, m.measurement_date, m.value_as_number""").df().groupby('person_id')['v'].mean()
    out['BMI'] = bmi.reindex(out.index)

    dd = drug_days(con).pivot(index='person_id', columns='cls', values='days')
    for cls, dur, flag in (('RAASi', 'Dur_ACE_ARB_days', 'Drug_RAASi'), ('Statins', 'Dur_Statin_days', 'Drug_Statins')):
        out[dur] = (dd[cls] if cls in dd.columns else pd.Series(dtype=float)).reindex(out.index).fillna(0.0)
        out[flag] = (out[dur] > 0).astype(int)
    res = out[['index_date'] + C.FEATURES + ['y']].copy()
    res.attrs['n_concepts'] = n_concepts
    res.attrs['diag'] = diag
    return res


def add_aux(df, split):
    df = df.copy()
    df['split'] = split
    egfr = df['Baseline_eGFR']
    df['stratum'] = np.select([egfr >= 60, egfr >= 45, egfr >= 30, egfr < 30], ['G1-2', 'G3a', 'G3b', 'G4-5'], 'NA')
    df['sg_age65'] = np.where(df['Age'] >= 65, '>=65', '<65')
    df['sg_sex'] = df['Sex_Male'].map({1: 'male', 0: 'female'}).fillna('NA')
    df['sg_dm'] = df['History_DM'].map({1: 'DM', 0: 'no DM'}).fillna('NA')
    df['sg_ckd_stage'] = df['stratum']
    return df


def slope_section(diags):
    """Where the baseline creatinine lies relative to the index and how many persons have a creatinine >= 90 d before it (what
    eGFR_Slope needs). Pooled over the B1 sites and the holdout, so each cohort person counts once; counts only."""
    use = [d for d in C.SITES_B1 + [C.HOLDOUT] if diags.get(d)]
    if not use:
        return []
    s = {k: sum(diags[d].get(k, 0) for d in use) for k in diags[use[0]]}
    n = s['persons']
    rows = [('baseline creatinine on or before the index date', 'base_le_0'),
            ('baseline creatinine 1-90 d after the index date', 'base_1_90'),
            ('baseline creatinine 91-365 d after the index date', 'base_91_365'),
            ('baseline creatinine 366-730 d after the index date', 'base_366_730'),
            ('baseline creatinine > 730 d after the index date', 'base_gt_730'),
            ('any creatinine on or before the index date', 'any_cr_on_or_before_index'),
            ('a creatinine >= 90 d before the baseline creatinine (slope computable)', 'prior_cr_90d'),
            ('eGFR_Slope available (|slope| <= 60 per year)', 'slope_ok')]
    return ['', '## baseline creatinine and eGFR_Slope availability (persons of the B1 sites and the holdout, each once)',
            f'  {"persons in the cohort":<72} {cell(n):>8}'] + [f'  {lab:<72} {cell(s[k]):>8} {pct(s[k], n)}' for lab, k in rows]


# ───────────────────────── combine for the pilot ─────────────────────────
def combine(feats, xs, matrix_out, irb, entry='ckd'):
    """B1-site rows (train) + holdout rows (val) with fixed site columns; checks B2 sites give the same values."""
    g = {}
    for db, df in feats.items():
        m = df.reset_index().merge(xs[xs['db'] == db][['person_id_site', 'person_id']].rename(
            columns={'person_id': 'gid', 'person_id_site': 'person_id'}), on='person_id', how='left')
        g[db] = m.assign(site=int(db[-1]) if db != C.HOLDOUT else -1)
    b1 = pd.concat([g[d] for d in C.SITES_B1 if d in g], ignore_index=True)
    b2 = pd.concat([g[d] for d in C.SITES_B2 if d in g], ignore_index=True)
    chk = b1[['gid'] + C.FEATURES + ['y']].merge(b2[['gid'] + C.FEATURES + ['y']], on='gid', how='outer',
                                                 suffixes=('_1', '_2'), indicator=True)
    both = chk[chk['_merge'] == 'both']
    diff = max([float(np.nanmax(np.abs(both[f + '_1'].astype(float) - both[f + '_2'].astype(float)), initial=0))
                for f in C.FEATURES + ['y']] + [0.0])
    nan_mis = int(sum((both[f + '_1'].isna() != both[f + '_2'].isna()).sum() for f in C.FEATURES))
    per = {}                                         # per feature: persons whose value differs between their B1 and B2 site, largest difference
    for f in C.FEATURES + ['y']:
        d = np.abs(both[f + '_1'].astype(float) - both[f + '_2'].astype(float))
        n_d = int((d > 1e-9).sum())
        if n_d:
            per[f] = (n_d, float(np.nanmax(d)))
    consistency = {'b1_only': int((chk['_merge'] == 'left_only').sum()), 'b2_only': int((chk['_merge'] == 'right_only').sum()),
                   'both': len(both), 'max_abs_diff': diff, 'nan_mismatch': nan_mis, 'per_feature': per}
    tr = add_aux(b1.merge(b2[['gid', 'site']].rename(columns={'site': 'site_b2'}), on='gid', how='left')
                 .rename(columns={'site': 'site_b1'}), 'train')
    va = add_aux(g[C.HOLDOUT].assign(site_b1=-1, site_b2=-1) if C.HOLDOUT in g else tr.iloc[:0], 'val')
    m = pd.concat([tr, va], ignore_index=True).sort_values('gid', kind='stable')
    m['site_b2'] = m['site_b2'].fillna(-1).astype(int)
    m = m[C.FEATURES + ['y', 'split', 'stratum'] + C.SUBGROUPS + ['site_b1', 'site_b2']].reset_index(drop=True)
    m[C.FEATURES] = m[C.FEATURES].astype(float)
    m['y'] = m['y'].astype(int)
    os.makedirs(os.path.dirname(matrix_out), exist_ok=True)
    m.to_parquet(matrix_out, index=False)
    h = hashlib.sha256(pd.util.hash_pandas_object(m, index=False).values.tobytes() + ','.join(m.columns).encode()).hexdigest()
    meta = {'dataset': 'snuh', 'tag': 'cdm' if entry == 'ckd' else 'cdmv',
            'label': ('SNUH CKD extract -> OMOP CDM v5.3 (P3) -> v205 cohort + 36 features per site (P4)' if entry == 'ckd' else
                      'SNUH CKD extract -> OMOP CDM v5.3 (P3) -> published cohort rules (first visit, creatinine span) + v205 exclusions + 36 features per site (P4 --entry visit)'),
            'entry': entry,
            'irb': irb, 'features': C.FEATURES, 'subgroups': C.SUBGROUPS, 'n': int(len(m)), 'data_sha256': h,
            'quick': False, 'fixed_sites': True, 'site_columns': ['site_b1', 'site_b2']}
    json.dump(meta, open(matrix_out.replace('.parquet', '.meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return m, consistency, h


# ───────────────────────── agreement with the v1.3 matrix ─────────────────────────
def load_v13(path):
    root = L.CKD_ROOT
    rid = pd.read_csv(os.path.join(root, C.load_layout()['base_csv']), usecols=['RID'], dtype={'RID': str})['RID']
    rid = rid.str.strip().str.replace(r'\.0$', '', regex=True)
    if os.path.exists(path):
        pub = pd.read_parquet(path)
    else:                                        # build it the pilot's way (00_build_matrix.build_snuh)
        spec = importlib.util.spec_from_file_location('bm', os.path.join(os.path.dirname(C.HERE), 'snuh_pilot', '00_build_matrix.py'))
        bm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bm)
        pub = bm.build_snuh()[0]
    if len(pub) != len(rid):
        raise ValueError('v1.3 matrix and Base.csv differ in length')
    return pub.assign(rid=rid.values)


def agreement(feats, xs, xw, pub, central_path, out, layout='icd', entry='ckd'):
    allf = []
    for db, df in feats.items():
        if db in C.SITES_B2:
            continue                                             # every train person is once in B1, once in B2
        m = df.reset_index().merge(xs[xs['db'] == db][['person_id_site', 'person_id']].rename(
            columns={'person_id': 'gid', 'person_id_site': 'person_id'}), on='person_id')
        allf.append(m)
    cdm = pd.concat(allf, ignore_index=True).merge(xw[['person_id', 'rid', 'group']].rename(columns={'person_id': 'gid'}), on='gid')
    con = C.connect(central_path, read_only=True)
    first = con.execute('SELECT person_id AS gid, min(visit_start_date) AS fv FROM visit_occurrence GROUP BY 1').df()
    con.close()
    first['fv'] = pd.to_datetime(first['fv'])
    cdm = cdm.merge(first, on='gid', how='left')
    both = cdm.merge(pub, on='rid', suffixes=('_c', '_p'))
    lines = [f"# P4 agreement: CDM-derived ({'v205 cohort' if entry == 'ckd' else 'published selection rules, first-visit index'}, CDM features) "
             'vs v1.3 matrix (published cohort/index)', '',
             'cohort overlap (persons)',
             f'  v1.3 matrix {cell(len(pub))}   CDM cohort (B1 sites + holdout) {cell(len(cdm))}   both {cell(len(both))}',
             f"  CDM only {cell(len(cdm) - len(both))} (of which outside the published cohort {cell((cdm['group'] == 'other').sum())})"
             f"   v1.3 only {cell(len(pub) - len(both))}",
             '  both, by published split: ' + ', '.join(f'{k} {cell(v)}' for k, v in both['group'].value_counts().items())]
    gap = (both['index_date'] - both['fv']).dt.days
    if len(both) >= L.MIN_CELL:
        lines += ['', 'index date: CDM (' + ('first CKD dx with 730 d obs.' if entry == 'ckd' else 'first visit')
                  + ') vs published (first BASICS visit)',
                  f'  same day {pct((gap == 0).sum(), gap.notna().sum())}   |Δ| <= 30 d {pct((gap.abs() <= 30).sum(), gap.notna().sum())}'
                  f'   CDM later {pct((gap > 0).sum(), gap.notna().sum())}   CDM earlier {pct((gap < 0).sum(), gap.notna().sum())}'
                  f'   median |Δ| {gap.abs().median():.0f} d']
    same = gap == 0
    lines += ['', 'per feature, persons in both (n = both non-missing; stats only when n >= 11)',
              f'  {"feature":<20} {"n":>8} {"miss v13":>9} {"miss CDM":>9} {"r/kappa":>8} {"spearman":>9} {"med|Δ|":>9}'
              f' {"exact":>7} {"exact|same idx":>15}']
    for f in C.FEATURES + ['y']:
        a, b = (both[f + '_c'], both[f + '_p']) if f + '_c' in both else (both['y_c'], both['y_p'])
        a, b = a.astype(float), b.astype(float)
        nn = a.notna() & b.notna()
        n = int(nn.sum())
        row = f'  {f:<20} {cell(n):>8} {cell((b.isna() & a.notna()).sum()):>9} {cell((a.isna() & b.notna()).sum()):>9}'
        if n >= L.MIN_CELL:
            d = (a[nn] - b[nn]).abs()
            ex = (d <= 1e-6).mean()
            n_same = int((same & nn).sum())
            exs = f'{((d <= 1e-6) & same[nn]).sum() / n_same:15.1%}' if n_same >= L.MIN_CELL else f'{"-":>15}'
            if f in C.BINARY or f == 'y':
                pa = a[nn].mean() * b[nn].mean() + (1 - a[nn].mean()) * (1 - b[nn].mean())
                kappa = (ex - pa) / (1 - pa) if pa < 1 else np.nan
                row += f' {kappa:8.3f} {"-":>9} {"-":>9} {ex:7.1%} {exs}'
            else:
                pr = np.corrcoef(a[nn], b[nn])[0, 1] if a[nn].std() > 0 and b[nn].std() > 0 else np.nan
                sr = a[nn].rank().corr(b[nn].rank())
                row += f' {pr:8.3f} {sr:9.3f} {d.median():9.3g} {ex:7.1%} {exs}'
        lines.append(row)
    lines += ['', 'r/kappa = Pearson r (continuous) or Cohen kappa (binary); exact = |Δ| <= 1e-6;',
              'exact|same idx = among persons whose CDM index equals the published index (shown when >= 11).',
              'v1.3 BMI is a whole-record mean from a table not in the local extract; History_* in v1.3 came from',
              ('English diagnosis text, here from the same text patterns on the diagnosis names (window=all matches the published "any time").'
               if layout == 'names' else 'English diagnosis text, here from ICD-10 codes -> lower agreement expected for these.')]
    C.write_text(os.path.join(out, 'p4_agreement.txt' if entry == 'ckd' else 'p4_agreement_visit.txt'), lines)


# ───────────────────────── main ─────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--irb', default=os.environ.get('PILOT_IRB', ''))
    ap.add_argument('--dbs', nargs='+', default=C.DBS, choices=C.DBS)
    ap.add_argument('--baseline', choices=['nearest', 'pre'], default='nearest',
                    help='nearest = closest to index on either side (v1.3 training); pre = on/before index')
    ap.add_argument('--window', choices=['index', 'all'], default='index',
                    help='History_* and BMI from records on/before index (default) or the whole record (published)')
    ap.add_argument('--rrt-icd', default='', help='extra RRT exclusion by ICD-10 source-code prefix, e.g. Z49,Z99.2,Z94.0')
    ap.add_argument('--agreement', action='store_true', help='compare with the v1.3 matrix via the P3 crosswalk')
    ap.add_argument('--entry', choices=['ckd', 'visit'], default='ckd',
                    help='ckd = v205 as shared with CKD_ML (index = first CKD diagnosis with 730 d observation after; default); '
                         'visit = the rules that built the published 28,209-person cohort (index = first visit; >= 2 creatinine records >= 730 d apart) plus the v205 age / RRT / K-Hb rules. '
                         'visit writes features_visit/, matrix_snuh_cdmv.parquet (PILOT_TAG=cdmv) and p4_*_visit.txt, so the default outputs stay')
    ap.add_argument('--v13-matrix', default=None, help='default data/ckd_pilot/matrix_snuh.parquet (built if absent)')
    ap.add_argument('--matrix-out', default=None, help='default data/ckd_pilot/matrix_snuh_cdm.parquet (cdmv for --entry visit)')
    a = ap.parse_args()
    irb = C.require_irb(a.irb)
    base_dir = C.cdm_dir()
    parent = os.path.dirname(os.path.abspath(base_dir))
    sfx = '' if a.entry == 'ckd' else '_visit'
    matrix_out = a.matrix_out or os.path.join(parent, 'matrix_snuh_cdm.parquet' if a.entry == 'ckd' else 'matrix_snuh_cdmv.parquet')
    fdir = os.path.join(base_dir, 'features' + sfx)
    os.makedirs(fdir, exist_ok=True)
    out = C.out_dir()
    xs = pd.read_parquet(os.path.join(base_dir, 'crosswalk_sites.parquet'))
    rrt = [p.strip() for p in a.rrt_icd.split(',') if p.strip()]
    t0 = time.time()

    lines = ['# P4 site features (aggregates only)', '',
             f"IRB {irb}   {time.strftime('%Y-%m-%d %H:%M')}   baseline={a.baseline}  window={a.window}  "
             f"extra RRT ICD prefixes={','.join(rrt) or 'none (pure v205)'}   entry={a.entry}", '']
    feats, miss, diags = {}, {}, {}
    layout = 'icd'
    for db in a.dbs:
        print(f'[{db}] cohort + features', flush=True)
        con = C.connect(C.db_path(db, base_dir))
        att, single, info = run_cohort(con, a.entry)
        layout = C.dx_layout(con)
        if layout == 'names':
            sens = rrt_sensitivity_text(con)
            if rrt:
                print('--rrt-icd applies to ICD-10 source codes; this CDM holds diagnosis names, so it is ignored', flush=True)
                rrt = []
        else:
            sens = rrt_sensitivity(con, C.RRT_ICD_CANDIDATES + [p for p in rrt if p not in C.RRT_ICD_CANDIDATES])
        if rrt:
            keys = [C.norm_icd(p) for p in rrt]
            con.execute(f"""DELETE FROM cohort WHERE subject_id IN (SELECT e.person_id FROM cohort c JOIN (
                SELECT person_id, condition_start_date d, condition_source_value s FROM condition_occurrence
                UNION ALL SELECT person_id, procedure_date, procedure_source_value FROM procedure_occurrence) e
                ON e.person_id = c.subject_id AND e.d <= c.cohort_start_date
                WHERE {' OR '.join(f"starts_with({C.icd_norm_sql('e.s')}, {lit(k)})" for k in keys)})""")
            att.append((f'extra RRT ICD exclusion ({",".join(rrt)})', con.execute('SELECT count(*) FROM cohort').fetchone()[0]))
        df = extract(con, a.baseline == 'pre', a.window == 'all')
        n_concepts = df.attrs.get('n_concepts', {})
        diags[db] = df.attrs.get('diag', {})
        con.close()
        df = add_aux(df, 'val' if db == C.HOLDOUT else 'train')
        df.assign(db=db).to_parquet(os.path.join(fdir, f'{db}.parquet'))
        feats[db] = df
        lines += [f'## {db}', '  attrition (persons)']
        lines += [f'    {lab:<52} {cell(n):>10}' for lab, n in att]
        lines.append('  failing each rule alone: ' + ', '.join(f'{k[5:]} {cell(v)}' for k, v in single.items()))
        if 'no_ckd_record' in info:
            lines.append(f"  cohort persons without a CKD record on/before the index (not a criterion with --entry visit): {cell(info['no_ckd_record'])}")
        lines.append(('  RRT by diagnosis name (cohort persons with a dialysis / kidney transplant name on/before index; the v205 RRT rule '
                      'already excludes those mapped to its concepts): ' if layout == 'names' else
                      '  RRT sensitivity (cohort persons with the code on/before index, NOT excluded unless --rrt-icd): ')
                     + ', '.join(f'{k} {cell(v)}' for k, v in sens.items()))
        n = len(df)
        lines.append(f"  cohort {cell(n)}   outcome rate {df['y'].mean():.1%}" if n >= L.MIN_CELL else f'  cohort {cell(n)}')
        if n >= L.MIN_CELL:
            lines.append('  stratum ' + '  '.join(f'{k}: {cell(v)}' for k, v in df['stratum'].value_counts().sort_index().items()))
        miss[db] = df[C.FEATURES].isna().mean() if n else pd.Series(np.nan, index=C.FEATURES)
        lines.append('  concepts per feature set (0 = LOINC code not in this vocabulary): '
                     + ', '.join(f'{k} {v}' for k, v in n_concepts.items()))
        lines.append('')
    lines += ['## missing per feature (share of cohort, before imputation)', f'  {"feature":<20}' + ''.join(f'{d:>9}' for d in miss)]
    for f in C.FEATURES:
        lines.append(f'  {f:<20}' + ''.join(f'{miss[d][f]:9.1%}' if len(feats[d]) >= L.MIN_CELL else f'{"-":>9}' for d in miss))
    lines += slope_section(diags)

    if set(C.SITES_B1 + [C.HOLDOUT]) <= set(feats):
        m, cons, h = combine(feats, xs, matrix_out, irb, a.entry)
        tr = m['split'] == 'train'
        lines += ['', '## combined matrix for analysis/snuh_pilot (B1-site rows = train, holdout = val)',
                  f'  rows {cell(len(m))} (train {cell(tr.sum())} / val {cell((~tr).sum())})   outcome rate '
                  f"{m['y'].mean():.1%} (train {m.loc[tr, 'y'].mean():.1%}, val {m.loc[~tr, 'y'].mean():.1%})" if len(m) else '  empty',
                  '  B1 sites ' + ', '.join(f'{k}: {cell(v)}' for k, v in m.loc[tr, 'site_b1'].value_counts().sort_index().items()),
                  '  B2 sites ' + ', '.join(f'{k}: {cell(v)}' for k, v in m.loc[tr, 'site_b2'].value_counts().sort_index().items()),
                  f"  B1 vs B2 consistency: persons in both {cell(cons['both'])}, B1 only {cell(cons['b1_only'])}, "
                  f"B2 only {cell(cons['b2_only'])}, max |Δ feature| {cons['max_abs_diff']:.3g}, missing mismatches {cons['nan_mismatch']}",
                  '  features that differ between a person\'s B1 and B2 site (persons, largest |Δ|): '
                  + ('; '.join(f'{k} {cell(v[0])} ({v[1]:.3g})' for k, v in cons['per_feature'].items()) or 'none'),
                  f'  data sha256 {h[:16]}…  (matrix written to the restricted data folder)']
    C.write_text(os.path.join(out, f'p4_site_features{sfx}.txt'), lines)

    if a.agreement:
        print('[agreement] v1.3 matrix vs CDM', flush=True)
        xw = pd.read_parquet(os.path.join(base_dir, 'crosswalk.parquet'))
        pub = load_v13(a.v13_matrix or os.path.join(parent, 'matrix_snuh.parquet'))
        agreement(feats, xs, xw, pub, C.db_path('central', base_dir), out, layout, a.entry)
    print(f'done in {(time.time() - t0) / 60:.1f} min ->', os.path.relpath(os.path.join(out, f'p4_site_features{sfx}.txt'), L.BASE))


if __name__ == '__main__':
    L.guard(main)
