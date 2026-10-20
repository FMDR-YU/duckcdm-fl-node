# -*- coding: utf-8 -*-
"""Tests for P3/P4 on public / generated data only (no SNUH data is touched).

    python analysis/snuh_cdm/tests/run_tests.py [--keep] [--only cohort,synthea,synthetic,hook,xgbfam,mimic,eicu,canary,paths,p1,p2,names,drugdays,visitentry]

Work folder: $CDM_TEST_DIR or the system temp dir (snuh_cdm_tests/). Every P3/P4 run gets
PILOT_CKD_ROOT / PILOT_CDM_DIR / PILOT_CDM_OUT pointing into it and a dummy --irb.
  cohort     hand-made mini CDM: every v205 inclusion / exclusion branch
  synthea    Synthea27Nj reverse-mapped to the raw layout -> P3 round-trip counts, site split invariants -> P4 runs
  synthetic  random CKD-like extract -> P3 -> P4; cohort and all 36 features + y equal an independent pandas
             reference on the raw tables; B1 vs B2 consistency; agreement mode on a v1.3-like matrix
  hook       analysis/snuh_pilot hook (PILOT_TAG, fixed sites) and unchanged default behaviour
  p1         extract profile on the real layout seen on 2026-10-14 (name-only diagnosis sheet, null birth in BASICS, a
             patient-name column) and on an ICD-code sheet: no patient-name or rare-name leak, counts >= 11, real out/ untouched
  p2         mapping tables from generated P1 catalogues and the fixture vocabulary: units, exact lab rows, false positives of the
             substring rule, salts and strengths in drug names, exclusions, the ATC supplement
  names      the real layout with diagnosis NAMES (sheet events + BASICS name rows, birth from the sheet) -> P3 -> P4: cohort =
             the codes version's reference, History flags from the diagnosis text, the 1998 rows cut by the approved period
  drugdays   P4 drug_days against a brute-force union of generated prescription intervals (duplicate rows, PRN, rows after the
             index), same rows in two shuffled orders with 4 threads give the same days
  visitentry P4 --entry visit (index = first visit; >= 2 creatinine spanning >= 730 d; v205 age / RRT / K-Hb rules; no CKD requirement):
             cohort, index dates and all 36 features + y equal the pandas reference
  xgbfam     analysis/snuh_pilot single-XGBoost family (PILOT_MODEL=xgb) and federated targets F_B1/F_B2 through
             steps 01-06 on a generated matrix in quick mode (scratch PILOT_DATA_DIR / OUT_DIR / FED_DIR)
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, PKG)
import fixtures as F  # noqa: E402
import reference as R  # noqa: E402

IRB = 'E-0000-000-0000'
# The default folder name contains [ ] and a space on purpose: the project folder is named "[ACI] ...", and square brackets are
# wildcards to glob (silently finds nothing), DuckDB and Windows PowerShell. Tests that run here catch code that breaks on them.
WORK = os.environ.get('CDM_TEST_DIR', os.path.join(tempfile.gettempdir(), '[brackets] snuh_cdm_tests'))
RESULTS = []


def check(cond, msg):
    RESULTS.append((bool(cond), msg))
    print(('  ok   ' if cond else '  FAIL ') + msg, flush=True)


def env_for(root):
    e = dict(os.environ)
    e.update({'PILOT_CKD_ROOT': root, 'PILOT_CDM_DIR': os.path.join(root, 'cdm'), 'PILOT_CDM_OUT': os.path.join(root, 'out'),
              'PILOT_DEBUG': '1', 'PYTHONIOENCODING': 'utf-8'})
    e.pop('PILOT_TAG', None)
    return e


def run(script, args, env, irb=IRB, expect_fail=False):
    cmd = [sys.executable, os.path.join(PKG, script)] + (['--irb', irb] if irb else []) + args
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if (r.returncode != 0) != expect_fail:
        print(r.stdout[-3000:], r.stderr[-6000:])
        raise RuntimeError(f'{script} exit {r.returncode}')
    return r


def con_ro(path):
    import duckdb
    return duckdb.connect(path, read_only=True)


# ───────────────────────── 1. cohort SQL on a hand-made mini CDM ─────────────────────────
def test_cohort():
    print('[cohort] hand-made mini CDM')
    import cdm_lib as C
    spec = importlib.util.spec_from_file_location('p4', os.path.join(PKG, 'p4_site_features.py'))
    p4 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p4)
    con = C.connect()
    C.create_cdm(con)
    T = F.T
    concepts = [(46271022, 'Condition'), (443614, 'Condition'), (320128, 'Condition'), (3016723, 'Measurement'),
                (4032243, 'Procedure'), (T + 201, 'Procedure'), (199991, 'Condition'), (T + 203, 'Condition'),
                (3023103, 'Measurement'), (3005456, 'Measurement'), (3000963, 'Measurement'), (3027484, 'Measurement'),
                (4146536, 'Procedure'), (4322471, 'Procedure'), (T + 999, 'Condition')]
    for cid, dom in concepts:
        con.execute(f"INSERT INTO concept VALUES ({cid}, 'c{cid}', '{dom}', 'SNOMED', 'x', 'S', 'c{cid}', DATE '1970-01-01', DATE '2099-12-31', NULL)")
    for a, ds in [(46271022, [46271022, 443614]), (4032243, [4032243, T + 201]), (199991, [199991, T + 203]),
                  (3016723, [3016723]), (3023103, [3023103]), (3000963, [3000963])]:
        for d in ds:
            con.execute(f'INSERT INTO concept_ancestor VALUES ({a}, {d}, 0, 0)')
    con.execute(f"INSERT INTO concept VALUES ({T + 998}, 'deprecated CKD child', 'Condition', 'SNOMED', 'x', NULL, 'z', DATE '1970-01-01', DATE '2000-01-01', 'D')")
    con.execute(f'INSERT INTO concept_ancestor VALUES (46271022, {T + 998}, 1, 1)')
    ids = {'cond': 0, 'meas': 0, 'proc': 0}
    D = lambda s: date.fromisoformat(s)  # noqa: E731

    def person(pid, yob, op=('2010-01-01', '2014-12-31'), conds=(), meas=(), procs=()):
        con.execute(f'INSERT INTO person (person_id, gender_concept_id, year_of_birth, race_concept_id, ethnicity_concept_id) VALUES ({pid}, 8507, {yob}, 0, 0)')
        con.execute(f"INSERT INTO observation_period VALUES ({pid}, {pid}, DATE '{op[0]}', DATE '{op[1]}', 32817)")
        for cid, d in conds:
            ids['cond'] += 1
            con.execute(f"INSERT INTO condition_occurrence (condition_occurrence_id, person_id, condition_concept_id, condition_start_date, condition_type_concept_id) VALUES ({ids['cond']}, {pid}, {cid}, DATE '{d}', 32817)")
        for cid, d, v, u in meas:
            ids['meas'] += 1
            con.execute(f"INSERT INTO measurement (measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, value_as_number, unit_concept_id) VALUES ({ids['meas']}, {pid}, {cid}, DATE '{d}', 32817, {'NULL' if v is None else v}, {u})")
        for cid, d in procs:
            ids['proc'] += 1
            con.execute(f"INSERT INTO procedure_occurrence (procedure_occurrence_id, person_id, procedure_concept_id, procedure_date, procedure_type_concept_id) VALUES ({ids['proc']}, {pid}, {cid}, DATE '{d}', 32817)")

    CKD, CR, K, HB = 46271022, 3016723, 3023103, 3000963
    cr2 = [(CR, '2011-01-05', 1.1, 8840), (CR, '2012-06-01', 1.3, 8840)]
    person(1, 1960, conds=[(CKD, '2011-01-01')], meas=cr2)                                             # in
    person(2, 1960, op=('2010-01-01', '2012-06-30'), conds=[(CKD, '2011-01-01')], meas=cr2)           # < 730 d obs
    person(3, 1993, conds=[(CKD, '2011-01-01')], meas=cr2)                                             # age 18
    person(4, 1960, conds=[(CKD, '2011-01-01')], meas=[(CR, '2011-01-05', 1, 0), (CR, '2013-01-03', 1, 0)])  # 2nd Cr at +733
    person(5, 1960, conds=[(CKD, '2011-01-01')], meas=[(CR, '2011-03-01', 1, 0), (CR, '2011-03-01', 1.2, 0)])  # same day x2: in
    person(6, 1960, conds=[(CKD, '2011-01-01')], meas=cr2, procs=[(4032243, '2010-06-01')])           # dialysis before
    person(7, 1960, conds=[(CKD, '2011-01-01')], meas=cr2, procs=[(4032243, '2012-01-01')])           # dialysis after: in
    person(8, 1960, conds=[(CKD, '2011-01-01'), (T + 203, '2011-01-01')], meas=cr2)                   # transplant dx on index
    person(9, 1960, conds=[(CKD, '2011-01-01')], meas=cr2 + [(K, '2010-09-23', 12, 8753)])            # K 12 at -100 d
    person(10, 1960, conds=[(CKD, '2011-01-01')], meas=cr2 + [(K, '2010-09-23', 12, 0)])              # unit 0: fail-open, in
    person(11, 1960, conds=[(CKD, '2011-01-01')], meas=cr2 + [(K, '2009-11-27', 12, 8753)])           # -400 d: in (outside op too)
    person(12, 1960, conds=[(CKD, '2011-01-01')], meas=cr2 + [(HB, '2011-01-01', 2.0, 8713)])         # Hb 2 on index
    person(13, 1960, conds=[(CKD, '2011-01-01')], meas=cr2 + [(K, '2010-12-22', None, 8753)])         # K NULL: in
    person(14, 1960, conds=[(443614, '2011-01-01')], meas=cr2)                                         # descendant: in
    person(15, 1960, conds=[(320128, '2011-01-01')], meas=cr2)                                         # not CKD
    person(16, 1960, conds=[(CKD, '2010-02-01'), (CKD, '2011-01-01')], meas=[(CR, '2010-02-05', 1, 0), (CR, '2011-06-01', 1, 0)])
    person(17, 1960, op=('2010-01-01', '2014-12-31'), conds=[(CKD, '2011-01-01')], meas=cr2, procs=[(T + 201, '2009-06-01')])  # RRT before op
    person(18, 1960, op=('2011-01-01', '2014-12-31'), conds=[(CKD, '2011-01-01')], meas=cr2)          # index = op start
    person(19, 1960, conds=[(T + 998, '2011-01-01')], meas=cr2)                                        # deprecated descendant
    person(20, 1960, conds=[(CKD, '2011-01-01')], meas=cr2 + [(HB, '2010-12-01', 26, 8713), (K, '2010-12-01', 1.4, 8753)])
    person(21, 1960, conds=[(CKD, '2013-06-01')], meas=cr2)                                            # dx too late for 730 d
    person(22, 1960, conds=[(CKD, '2011-01-01')], meas=cr2 + [(K, '2011-01-01', 10.0, 8753), (HB, '2011-01-01', 3.0, 8713)])  # bounds: in
    att, single, _ = p4.run_cohort(con)
    got = dict(con.execute('SELECT subject_id, cohort_start_date FROM cohort').fetchall())
    expect = {1, 5, 7, 10, 11, 13, 14, 16, 17, 18, 22}
    check(set(got) == expect, f'cohort members {sorted(got)} == {sorted(expect)}')
    check(got.get(16) == D('2010-02-01'), 'index = first qualifying CKD event (person 16)')
    entry = {r[0] for r in con.execute('SELECT person_id FROM cohort_inclusion').fetchall()}
    check(entry == set(range(1, 23)) - {2, 15, 19, 21}, 'entry excludes short observation, non-CKD, deprecated descendant, late dx')
    check(att[0][1] == 18 and att[-1][1] == len(expect), f'attrition {[n for _, n in att]}')
    check(single == {'rule_age': 1, 'rule_creatinine': 1, 'rule_no_rrt': 2, 'rule_no_implausible': 3},
          f'single-rule failures {single}')


# ───────────────────────── 2. Synthea27Nj round trip ─────────────────────────
def test_synthea():
    print('[synthea] Synthea27Nj -> raw layout -> P3 -> P4')
    root = os.path.join(WORK, 'fx_synthea')
    shutil.rmtree(root, ignore_errors=True)
    vocab = os.path.join(WORK, 'vocab')
    F.build_vocab(vocab)
    exp = F.build_synthea(root)
    env = env_for(root)
    r = run('p3_build_cdm.py', ['--vocab', vocab, '--maps', os.path.join(root, 'maps')], env, irb='', expect_fail=True)
    check('IRB exemption number' in r.stdout + r.stderr and not os.path.exists(os.path.join(root, 'cdm')),
          'P3 refuses to run without --irb and creates nothing')
    lay = os.path.join(root, 'maps', 'raw_layout.json')
    open(lay, 'w', encoding='utf-8').write('{"basics": {"birth": ["no_such_column"]}}')
    r = run('p3_build_cdm.py', ['--vocab', vocab, '--maps', os.path.join(root, 'maps'), '--allow-any-n'],
            dict(env, PILOT_DEBUG='0'), expect_fail=True)
    check('raw extract layout: BASICS birth' in r.stdout + r.stderr and '생년월' in r.stdout + r.stderr,
          'layout error names the missing column and lists the columns found (no data)')
    os.remove(lay)
    run('p3_build_cdm.py', ['--vocab', vocab, '--maps', os.path.join(root, 'maps'), '--allow-any-n',
                            '--date-range', '1900-01-01:2030-12-31'], env)      # Synthea histories start at birth
    c = con_ro(os.path.join(root, 'cdm', '_central.duckdb'))
    n = lambda sql: c.execute(sql).fetchone()[0]  # noqa: E731
    check(n('SELECT count(*) FROM person') == exp['n_person'], f"persons {n('SELECT count(*) FROM person')} == {exp['n_person']}")
    check(n('SELECT count(*) FROM measurement') == exp['n_measurement'], 'measurement rows round-trip')
    check(n('SELECT count(*) FROM measurement WHERE measurement_concept_id <> 0') == exp['mapped_measure_rows'],
          f"mapped measurement rows {n('SELECT count(*) FROM measurement WHERE measurement_concept_id <> 0')} == {exp['mapped_measure_rows']}")
    check(abs(n('SELECT sum(value_as_number) FROM measurement WHERE measurement_concept_id <> 0') - exp['mapped_measure_sum']) < 1e-6,
          'mapped measurement values round-trip')
    check(n('SELECT count(*) FROM measurement WHERE measurement_concept_id = 3016723') > 0, 'creatinine mapped by LOINC 2160-0 -> 3016723')
    check(n('SELECT count(*) FROM condition_occurrence') == exp['n_condition'], 'condition rows round-trip')
    check(n('SELECT count(*) FROM visit_occurrence') == exp['n_visit_distinct'], 'visits = distinct person x date x type')
    check(n('SELECT count(*) FROM visit_occurrence WHERE visit_concept_id = 9201') > 0, 'visit type 입원 -> 9201')
    check(n('SELECT count(*) FROM drug_exposure') == exp['n_drug_rows_expected'], 'drug rows = raw rows x ingredients')
    check(n("SELECT count(*) FROM drug_exposure WHERE route_source_value LIKE 'excluded:%' AND drug_concept_id = 0") > 0,
          'excluded products -> concept 0 + route_source_value excluded:')
    check(n('SELECT count(*) FROM drug_exposure WHERE drug_exposure_end_date < drug_exposure_start_date') == 0, 'drug end >= start')
    check(n('SELECT count(*) FROM person WHERE person_source_value IS NOT NULL') == 0, 'no source id in PERSON')
    check(n('SELECT count(*) FROM observation_period') == exp['n_person'], 'one observation period per person')
    check(n('SELECT count(*) FROM concept WHERE concept_id = 46271022') == 1, 'vocab subset keeps v205 concepts')
    tables = ['person', 'visit_occurrence', 'condition_occurrence', 'measurement', 'drug_exposure', 'observation_period']
    central = {t: n(f'SELECT count(*) FROM {t}') for t in tables}
    c.close()
    for split in ('B1', 'B2'):
        tot = {t: 0 for t in tables}
        for db in [f'{split}_{k}' for k in range(3)] + ['holdout']:
            s = con_ro(os.path.join(root, 'cdm', 'site_' + db + '.duckdb' if db != 'holdout' else 'holdout.duckdb'))
            for t in tables:
                tot[t] += s.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
            ids = s.execute('SELECT min(person_id), max(person_id), count(*) FROM person').fetchone()
            if ids[2]:
                check(ids[0] == 1 and ids[1] == ids[2], f'{db}: fresh person_ids 1..n')
            s.close()
        check(tot == central, f'{split} sites + holdout partition every table of the central CDM')
    run('p4_site_features.py', [], env)
    check(os.path.exists(os.path.join(root, 'out', 'p4_site_features.txt')), 'P4 runs on the Synthea sites')
    leak_check(root, set(str(100000 + i) for i in range(1, 40)))


def leak_check(root, rids):
    bad = []
    for f in os.listdir(os.path.join(root, 'out')):
        txt = open(os.path.join(root, 'out', f), encoding='utf-8-sig').read()
        bad += [f for r in rids if re.search(rf'(?<![\d,.]){r}(?![\d,])', txt)]
    check(not bad, f'no source patient id in out/ ({len(rids)} ids scanned)')


# ───────────────────────── 3. synthetic CKD extract vs pandas reference ─────────────────────────
def test_synthetic():
    print('[synthetic] generated CKD extract -> P3 -> P4 vs reference')
    root = os.path.join(WORK, 'fx_synth')
    shutil.rmtree(root, ignore_errors=True)
    vocab = os.path.join(WORK, 'vocab')
    if not os.path.exists(os.path.join(vocab, 'CONCEPT.csv')):
        F.build_vocab(vocab)
    fx = F.build_synthetic(root, n=400)
    env = env_for(root)
    run('p3_build_cdm.py', ['--vocab', vocab, '--maps', os.path.join(root, 'maps'), '--allow-any-n'], env)
    c = con_ro(os.path.join(root, 'cdm', '_central.duckdb'))
    n = lambda sql: c.execute(sql).fetchone()[0]  # noqa: E731
    check(n('SELECT count(*) FROM procedure_occurrence') == (fx['dx']['ICD10코드'] == 'Z49.1').sum(),
          'Z49.1 (Procedure-domain map) routed to PROCEDURE_OCCURRENCE')
    check(n("SELECT count(*) FROM condition_occurrence WHERE condition_source_value = 'Z99.2' AND condition_concept_id = 0")
          == (fx['dx']['ICD10코드'] == 'Z99.2').sum(), 'Observation-domain map -> condition row with concept 0')
    check(n("SELECT count(*) FROM measurement WHERE measurement_source_value = 'BASICS.BMI'") == fx['basics']['BMI'].notna().sum(),
          'BASICS BMI -> measurement')
    check(n("SELECT count(*) FROM drug_exposure WHERE drug_source_value = 'A002'") == 2 * (fx['drug']['약품코드'] == 'A002').sum(),
          'combination product -> one row per ingredient')
    check(n("SELECT count(*) FROM drug_exposure WHERE drug_source_value = 'A011B' AND drug_concept_id = 1539403")
          == (fx['drug']['약품코드'] == 'A011B').sum(), "drug_map code '*' matches by name")
    prn = fx['drug'][fx['drug']['PRN처방여부'] == 'Y']
    check(n("SELECT count(*) FROM drug_exposure WHERE sig = 'PRN'") == len(prn) + (prn['약품코드'] == 'A002').sum(),
          'PRN kept as sig (one row per ingredient)')
    check(n('SELECT count(*) FROM measurement WHERE unit_concept_id = 8753') > 0, "raw unit 'mmol/L' -> UCUM 8753")
    hctz = F.INGREDIENTS['hydrochlorothiazide']
    check(n(f"""SELECT count(*) FROM concept_ancestor ca JOIN concept a ON a.concept_id = ca.ancestor_concept_id
                 WHERE a.vocabulary_id = 'ATC' AND a.concept_code = 'C09A' AND ca.descendant_concept_id = {hctz}""") == 1,
          'maps/atc_supplement.csv: an ingredient without an ATC ancestor is placed under its class in the vocabulary subset')
    c.close()
    sc = con_ro(os.path.join(root, 'cdm', 'site_B1_0.duckdb'))
    check(sc.execute(f'SELECT count(*) FROM concept_ancestor WHERE descendant_concept_id = {hctz}').fetchone()[0] >= 1,
          'the supplement row is in the site databases as well')
    sc.close()
    run('p4_site_features.py', [], env)

    xs = pd.read_parquet(os.path.join(root, 'cdm', 'crosswalk_sites.parquet'))
    xw = pd.read_parquet(os.path.join(root, 'cdm', 'crosswalk.parquet'))
    feats = []
    for db in ['B1_0', 'B1_1', 'B1_2', 'holdout']:
        f = pd.read_parquet(os.path.join(root, 'cdm', 'features', f'{db}.parquet'))
        f = f.reset_index().merge(xs[xs['db'] == db].rename(columns={'person_id': 'gid', 'person_id_site': 'person_id'}),
                                  on='person_id').merge(xw[['person_id', 'rid']].rename(columns={'person_id': 'gid'}), on='gid')
        feats.append(f)
    cdm = pd.concat(feats, ignore_index=True).set_index('rid')
    ref_c = R.cohort(fx)
    ref_in = ref_c[ref_c[['age_ok', 'cr_ok', 'rrt_ok', 'kh_ok']].all(axis=1)]
    check(set(cdm.index) == set(ref_in.index), f'cohort = reference v205 on raw tables ({len(cdm)} vs {len(ref_in)}; '
          f'excluded: age {(~ref_c.age_ok).sum()}, Cr {(~ref_c.cr_ok).sum()}, RRT {(~ref_c.rrt_ok).sum()}, K/Hb {(~ref_c.kh_ok).sum()})')
    check((pd.to_datetime(cdm['index_date']) == ref_in['index_date'].reindex(cdm.index)).all(), 'index dates = reference')
    check(min((~ref_c.age_ok).sum(), (~ref_c.cr_ok).sum(), (~ref_c.rrt_ok).sum(), (~ref_c.kh_ok).sum()) > 0,
          'fixture exercises every exclusion rule')
    ref = R.features(fx, pd.to_datetime(cdm['index_date']), fx['excluded_names'])
    import cdm_lib as C
    worst = []
    for f in C.FEATURES + ['y']:
        a, b = cdm[f].astype(float), ref[f].reindex(cdm.index).astype(float)
        same = ((a - b).abs() <= 1e-9) | (a.isna() & b.isna())
        if not same.all():
            worst.append(f'{f} ({(~same).sum()})')
    check(not worst, 'all 36 features + y equal the pandas reference' + (f' -- mismatches: {worst}' if worst else ''))
    for f in ('eGFR_Slope', 'UACR', 'Dur_ACE_ARB_days', 'Dur_Statin_days', 'BMI', 'History_HTN', 'Subgroup_GN'):
        check(cdm[f].notna().sum() > 5 and cdm[f].astype(float).std() > 0, f'{f} non-trivial in the fixture')
    check(0 < cdm['y'].mean() < 1, f"outcome varies (rate {cdm['y'].mean():.2f})")
    rep = open(os.path.join(root, 'out', 'p4_site_features.txt'), encoding='utf-8').read()
    check(re.search(r'max \|Δ feature\| 0(?![.\d])', rep) and 'B1 only <11' in rep and 'missing mismatches 0' in rep,
          'B1 and B2 sites give bit-identical features for the same persons')
    m = pd.read_parquet(os.path.join(root, 'matrix_snuh_cdm.parquet'))
    check(len(m) == len(cdm) and set(m['split']) == {'train', 'val'}, 'combined matrix = B1 sites + holdout')
    check(((m['split'] == 'val') == (m['site_b1'] == -1)).all(), 'holdout rows carry no site')

    # agreement mode: v1.3-like matrix in Base.csv order = reference values (+ 10 % perturbed BUN)
    base = fx['base']
    pub = ref.reindex(base['RID']).reset_index(drop=True)
    for col in C.FEATURES:
        pub[col] = pub[col].astype(float)
    pert = np.random.default_rng(0).random(len(pub)) < 0.1
    pub.loc[pert, 'BUN'] = pub.loc[pert, 'BUN'] + 1
    pub['y'] = pub['y'].fillna(0).astype(int)
    pub.to_parquet(os.path.join(root, 'matrix_snuh.parquet'), index=False)
    run('p4_site_features.py', ['--agreement'], env)
    ag = open(os.path.join(root, 'out', 'p4_agreement.txt'), encoding='utf-8').read()
    rows = {ln.split()[0]: ln.split() for ln in ag.splitlines() if ln.startswith('  ') and ln.split() and ln.split()[0] in C.FEATURES + ['y']}
    ex = {f: r[-2] for f, r in rows.items() if r[-2].endswith('%')}
    check(all(ex[f] == '100.0%' for f in ex if f != 'BUN') and ex.get('BUN') not in (None, '100.0%'),
          f'agreement: exact 100 % except perturbed BUN ({ex.get("BUN")})')
    check('v1.3 only' in ag and 'index date' in ag, 'agreement report has cohort overlap and index-date sections')
    leak_check(root, set(base['RID']) | set(fx['basics']['연구별 환자 ID']))


# ───────────────────────── 4. pilot hook ─────────────────────────
def test_hook():
    print('[hook] analysis/snuh_pilot PILOT_TAG / fixed sites')
    root = os.path.join(WORK, 'fx_synth')
    code = r'''
import os, sys, json, numpy as np
sys.path.insert(0, sys.argv[1]); import pilot_lib as L
L.DATA_DIR = sys.argv[2]
X, y, split, aux, meta = L.load_matrix('snuh')
tr = np.where(split == 'train')[0]
a = L.scenarios(tr, aux['stratum'].to_numpy(), 42); b = L.scenarios(tr, aux['stratum'].to_numpy(), 43)
import pandas as pd; m = pd.read_parquet(L.matrix_path('snuh'))
ok_fixed = all((a[k][0] == b[k][0]).all() for k in ['B1_0','B1_1','B1_2','B2_0','B2_1','B2_2'])
ok_cols = all(set(a[f'B1_{k}'][0]) == set(np.where((m.site_b1 == k) & (m.split == 'train'))[0]) for k in range(3))
ok_cols &= all(set(a[f'B2_{k}'][0]) == set(np.where((m.site_b2 == k) & (m.split == 'train'))[0]) for k in range(3))
sc = L.size_classes(len(tr))
print(json.dumps({'tag': L.tag('snuh'), 'path': os.path.basename(L.matrix_path('snuh')), 'fixed': ok_fixed, 'cols': ok_cols,
                  'aprime_differs': not np.array_equal(a['Aprime_0'][0], b['Aprime_0'][0]),
                  'b2_sizes': [sc['b2_0'], sc['b2_1'], sc['b2_2']] == [int((m.site_b2 == k).sum()) for k in range(3)]}))
'''
    env = dict(os.environ, PILOT_TAG='cdm', PYTHONIOENCODING='utf-8')
    r = subprocess.run([sys.executable, '-c', code, os.path.join(os.path.dirname(PKG), 'snuh_pilot'), root],
                       env=env, capture_output=True, text=True, encoding='utf-8')
    import json
    if r.returncode:
        print(r.stderr[-3000:])
    out = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
    check(out.get('tag') == 'snuh_cdm' and out.get('path') == 'matrix_snuh_cdm.parquet', f'PILOT_TAG=cdm paths {out.get("tag")}, {out.get("path")}')
    check(out.get('fixed') and out.get('cols'), 'fixed sites: same B1/B2 for every seed, equal to site_b1/site_b2')
    check(out.get('aprime_differs'), "A' still drawn per seed")
    check(out.get('b2_sizes'), 'shadow size classes follow the fixed B2 sites')
    # default behaviour unchanged: compare with the pre-edit copy when available
    orig = os.environ.get('PILOT_LIB_ORIG')
    code2 = r'''
import sys, importlib.util, numpy as np, json
def load(p, n):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
new, old = load(sys.argv[1], 'new'), load(sys.argv[2], 'old')
rng = np.random.default_rng(1); tr = np.sort(rng.choice(5000, 3500, replace=False)); st = rng.choice(['a','b','c'], 5000)
same = all(np.array_equal(new.scenarios(tr, st, s)[k][0], old.scenarios(tr, st, s)[k][0]) for s in (42, 50) for k in old.scenarios(tr, st, s))
import os
rel = lambda m, ds: (os.path.relpath(m.matrix_path(ds), m.DATA_DIR), m.tag(ds))
print(json.dumps({'same': same, 'path': all(rel(new, d) == rel(old, d) for d in ('snuh', 'synpuf')),
                  'sizes': new.size_classes(3500) == old.size_classes(3500)}))
'''
    if orig and os.path.exists(orig):
        env2 = dict(os.environ, PYTHONIOENCODING='utf-8')
        env2.pop('PILOT_TAG', None)
        r = subprocess.run([sys.executable, '-c', code2, os.path.join(os.path.dirname(PKG), 'snuh_pilot', 'pilot_lib.py'), orig],
                           env=env2, capture_output=True, text=True, encoding='utf-8')
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
        check(o.get('same') and o.get('path') and o.get('sizes'), 'without PILOT_TAG: scenarios / paths / sizes identical to the original pilot_lib')


# ───────────────────────── 5. single-XGBoost family and federated targets ─────────────────────────
def test_xgbfam():
    print('[xgbfam] analysis/snuh_pilot single-XGBoost family and federated (F) targets, quick mode on generated data')
    import json
    pilot = os.path.join(os.path.dirname(PKG), 'snuh_pilot')
    root = os.path.join(WORK, 'fx_xgbfam')
    shutil.rmtree(root, ignore_errors=True)
    data, outd, fed = (os.path.join(root, n) for n in ('data', 'out', 'fed'))
    os.makedirs(data)
    # tiny matrix standing in for "synpuf" in quick mode (matrix_synpuf_quick.parquet), with missing values
    rng = np.random.default_rng(7)
    n = 1800
    X = pd.DataFrame(rng.normal(size=(n, 6)), columns=[f'f{i}' for i in range(6)])
    X.iloc[::9, 0] = np.nan
    X.iloc[::13, 3] = np.nan
    lin = 0.9 * X['f0'].fillna(0) - 0.7 * X['f1'] + 0.5 * X['f2'] * X['f3'].fillna(0)
    y = (rng.random(n) < 1 / (1 + np.exp(-lin))).astype(int)
    df = X.copy()
    df['y'] = y
    df['split'] = np.where(rng.random(n) < 0.7, 'train', 'val')
    df['stratum'] = rng.choice(['s1', 's2', 's3'], n)
    df['sg_a'] = rng.choice(['a', 'b'], n)
    df.to_parquet(os.path.join(data, 'matrix_synpuf_quick.parquet'), index=False)
    json.dump({'dataset': 'synpuf', 'label': 'generated', 'irb': None, 'features': list(X.columns),
               'subgroups': ['sg_a'], 'n': n, 'data_sha256': '0' * 64, 'quick': True},
              open(os.path.join(data, 'matrix_synpuf_quick.meta.json'), 'w'))
    env = dict(os.environ, PILOT_DATA_DIR=data, PILOT_OUT_DIR=outd, PILOT_FED_DIR=fed, PILOT_MODEL='xgb',
               PILOT_QUICK='1', PILOT_DEBUG='1', PILOT_THREADS='2', PYTHONIOENCODING='utf-8')
    env.pop('PILOT_TAG', None)

    code = r'''
import os, sys, json, numpy as np
sys.path.insert(0, sys.argv[1]); import pilot_lib as L
out = {'variants': list(L.VARIANTS), 'tag': L.tag('synpuf'), 'matrix': os.path.basename(L.matrix_path('synpuf'))}
yy = np.random.default_rng(0).integers(0, 2, 400)
out['params_equal'] = {v: dict(L.build_estimators(v, yy, 42))['xgb'].get_params() == L.make_model('xgb_' + v, yy, 42).get_params()
                       for v in L.ENSEMBLE_VARIANTS}
# federated model files as FLARE would leave them: one XGBoost trained on the union of the three sites
X, y, split, aux, meta = L.load_matrix('synpuf')
tr = np.where(split == 'train')[0]
sc = L.scenarios(tr, aux['stratum'].to_numpy(), 42)
for scn in ('B1', 'B2'):
    idx = np.unique(np.concatenate([sc[f'{scn}_{k}'][0] for k in range(3)]))
    for v in L.VARIANTS:
        m = L.make_model(v, y[idx], 42); m.fit(X.iloc[idx], y[idx])
        p = L.fed_model_path('synpuf', scn, 42, v); os.makedirs(os.path.dirname(p), exist_ok=True)
        m.get_booster().save_model(p)
print(json.dumps(out))
'''
    r = subprocess.run([sys.executable, '-c', code, pilot], env=env, capture_output=True, text=True, encoding='utf-8')
    if r.returncode:
        print(r.stderr[-3000:])
    o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
    check(o.get('variants') == ['xgb_krcp', 'xgb_leaky', 'xgb_regularized'], 'PILOT_MODEL=xgb selects the three xgb variants')
    check(o.get('tag') == 'synpuf_xgb_quick' and o.get('matrix') == 'matrix_synpuf_quick.parquet',
          f'xgb family keeps its own work/out folder, same matrix ({o.get("tag")}, {o.get("matrix")})')
    check(o.get('params_equal') and all(o['params_equal'].values()),
          'single XGBoost has the same hyper-parameters as the ensemble XGBoost member (krcp, leaky, regularized)')
    envd = dict(env)
    envd.pop('PILOT_MODEL')
    r = subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0, sys.argv[1]); import pilot_lib as L; '
                        'print(L.VARIANTS, L.tag("synpuf"), L.FEDERATED)', pilot], env=envd, capture_output=True,
                       text=True, encoding='utf-8')
    check("('krcp', 'leaky', 'regularized') synpuf_quick" in r.stdout, 'default (no PILOT_MODEL) is still the ensemble family')

    def step(script, *args):
        rr = subprocess.run([sys.executable, os.path.join(pilot, script), '--dataset', 'synpuf', *args], env=env,
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
        if rr.returncode:
            print(rr.stdout[-2500:], rr.stderr[-4000:])
            raise RuntimeError(f'{script} exit {rr.returncode}')
        return rr

    step('01_train_targets.py', '--seeds', '42')
    step('02_train_shadows.py', '--variants', 'xgb_krcp')
    step('03_attack_audit.py', '--variants', 'xgb_krcp', '--seeds', '42')
    step('03b_size_curve.py', '--variants', 'xgb_krcp', '--seeds', '42')
    step('04_gate1_formats.py', '--seed', '42')
    step('05_gate3_escrow.py', '--variant', 'xgb_krcp', '--target', 'A_0', '--seed', '42')
    step('06_summarize.py')
    od = os.path.join(outd, 'synpuf_xgb_quick')
    ut = pd.read_csv(os.path.join(od, '01_utility_long.csv'))
    f = ut[ut.target.isin(['F_B1', 'F_B2'])]
    check(len(f) == 6 and f.delta_auc_vs_A.notna().all(),
          'step 01 adds F_B1 and F_B2 (3 variants each) with a paired bootstrap against A_0')
    check((f.delta_auc_vs_A.abs() < 1e-6).all(), 'a model trained on the union of the sites equals the central model (F - A = 0)')
    at = pd.read_csv(os.path.join(od, '03_attacks_long.csv'))
    fa = at[at.target.isin(['F_B1', 'F_B2'])]
    check(len(fa) == 2 and fa[['loss_auc', 'shadow_auc', 'lira_auc']].notna().all().all(),
          'step 03 audits the federated models against full-size shadows')
    sc = pd.read_csv(os.path.join(od, '03b_size_curve_long.csv'))
    n_tr = int((df['split'] == 'train').sum())
    check(sorted(sc.n_train) == [200, 500, 1000, n_tr] and sc.shadow_auc.notna().all() and sc.lira_auc.notna().all(),
          'step 03b audits one target per training size (quick sizes 200/500/1000/all)')
    g1 = pd.read_csv(os.path.join(od, '04_gate1.csv'))
    gf = g1[g1.target.isin(['F_B1', 'F_B2'])]
    check(len(gf) == 6 and (gf.max_abs_dp < 1e-6).all() and (gf.formats == 'json').all() and not gf.pickle_used_on_load.any(),
          'step 04 reloads the federated JSON without pickle, predictions unchanged (xgb family)')
    g1a = g1[g1.target == 'A_0']
    check(len(g1a) == 3 and (g1a.max_abs_dp < 1e-6).all(), 'step 04 xgb export round-trips for A_0')
    lf = pd.read_csv(os.path.join(od, '04_leaf_audit.csv'))
    check(set(lf.component) == {'xgb'} and lf.share_leaves_lt11.between(0, 1).all(), 'leaf audit for the single XGBoost')
    g3 = pd.read_csv(os.path.join(od, '05_gate3.csv'))
    check(len(g3) == 1 and bool(g3.gate3_pass.iloc[0]), 'step 05 re-execution passes for an xgb variant')
    md = open(os.path.join(od, '06_summary.md'), encoding='utf-8').read()
    check('## H5' in md and 'F_B1' in md, 'step 06 summary has the H5 table for the federated models')
    check('## H6' in md and 'Spearman' in md, 'step 06 summary has the H6 size-curve table')
    check('## Pre-specified decision rules' in md and all(f'| H{k} |' in md for k in (3, 4, 5, 6)),
          'step 06 summary evaluates the decision rules (H3-H6 rows present on a one-seed run)')
    h = subprocess.run([sys.executable, os.path.join(pilot, 'run_pilot.py'), '--help'], capture_output=True, text=True,
                       encoding='utf-8')
    check('--model' in h.stdout, 'run_pilot.py has --model')
    check({'k_lira', 'k_shokri'} <= set(at.columns) and at.k_lira.nunique() == 1 and int(at.k_lira.iloc[0]) == 8 and int(at.k_shokri.iloc[0]) == 8
          and 'LiRA / RMIA with 8 reference models per target' in md,
          'step 03 records the size of the audit (quick mode: 8 reference models) and the summary states it')
    code_ar = r"""
import sys, os, json
sys.path.insert(0, sys.argv[1]); import pilot_lib as L
import pandas as pd
p = os.path.join(sys.argv[2], 'append_rows_check.csv')
if os.path.exists(p):
    os.remove(p)
L.append_rows(p, [{'a': 1, 'b': 2}])
L.append_rows(p, [{'b': 4, 'a': 3}])
L.append_rows(p, [{'a': 5, 'b': 6, 'c': 7}])
d = pd.read_csv(p)
print(json.dumps({'cols': list(d.columns), 'a': d.a.tolist(), 'b': d.b.tolist(), 'c_gaps': int(d.c.isna().sum()), 'c_last': float(d.c.iloc[-1])}))
"""
    ra = subprocess.run([sys.executable, '-c', code_ar, pilot, outd], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    try:
        oa = json.loads(ra.stdout.strip().splitlines()[-1])
    except Exception:
        oa = {}
        print(ra.stdout[-800:], ra.stderr[-1500:])
    check(oa == {'cols': ['a', 'b', 'c'], 'a': [1, 3, 5], 'b': [2, 4, 6], 'c_gaps': 2, 'c_last': 7.0},
          'append_rows aligns columns by name and rewrites the file when a column is added between runs')

    # decision rules of the analysis plan on constructed long tables with known answers
    code_dr = r'''
import importlib.util, json, os, sys
import numpy as np, pandas as pd
here = sys.argv[1]
sys.path.insert(0, here)
import pilot_lib as L
spec = importlib.util.spec_from_file_location('summ06', os.path.join(here, '06_summarize.py'))
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
rng = np.random.default_rng(1)
SEEDS = list(range(42, 52))
tg = ['A_0', 'Aprime_0', 'B1_0', 'B1_1', 'B1_2', 'B2_0', 'B2_1', 'B2_2', 'F_B1', 'F_B2']
base = {'xgb_krcp': [.55, .60, .62, .62, .62, .64, .64, .64, .552, .552],
        'xgb_leaky': [.70, .74, .75, .75, .75, .78, .78, .78, .705, .705],
        'xgb_regularized': [.52, .527, .53, .53, .53, .54, .54, .54, .522, .522]}
def tables(shift=0.0, seeds=SEEDS):
    at, ut = [], []
    for v, vals in base.items():
        for s in seeds:
            for t, a in zip(tg, vals):
                at.append(dict(seed=s, variant=v, target=t, n_members=100,
                               shadow_auc=a + (shift if t.startswith('F_') else 0) + rng.normal(0, .002)))
            for t in tg + ['B1_comb', 'B2_comb']:
                row = dict(seed=s, variant=v, target=t, auroc=.85 if v == 'xgb_leaky' else .89)
                if t in ('B1_comb', 'B2_comb', 'F_B1', 'F_B2'):
                    row['delta_auc_vs_A'] = -.002 + rng.normal(0, .0005)
                ut.append(row)
    return pd.DataFrame(ut), pd.DataFrame(at)
def curve(slope):
    return pd.DataFrame([dict(variant='xgb_regularized', seed=s, n_train=n, shadow_auc=.56 + slope * np.log10(n / 200) + rng.normal(0, .002))
                         for s in SEEDS for n in (200, 500, 1000, 2000)])
g1 = pd.DataFrame([dict(variant=v, target='A_0', max_abs_dp=0.0) for v in base])
g3 = pd.DataFrame([dict(variant=v, target='A_0', signature_valid=True, data_hash_equal=True, abs_delta_auroc=0.0) for v in base])
roles = {}
def run(ut, at, sc=None, a=g1, b=g3):
    out = {}
    for ln in S.decision_rules('synpuf', ut, at, sc, a, b):
        if ln.startswith('| H'):
            c = [x.strip() for x in ln.strip().strip('|').split('|')]
            out[c[0] + ' ' + c[2]] = c[3].strip('*')
            roles[c[0] + ' ' + c[2]] = c[1]
    return out
res = {'good': run(*tables(), curve(-.01)),
       'f_exposed': run(*tables(shift=.03)),
       'flat_curve': run(*tables(), curve(.0)),
       'one_seed': run(*tables(seeds=[42])),
       'bad_gate3': run(*tables(), None, g1, g3.assign(abs_delta_auroc=.01)),
       'no_gate3_leaky': run(*tables(), None, g1, g3[g3.variant == 'xgb_regularized'])}
res['roles'] = dict(roles)
print(json.dumps(res))
'''
    envd2 = dict(os.environ, PILOT_MODEL='xgb', PILOT_QUICK='1', PYTHONIOENCODING='utf-8')
    for k in ('PILOT_TAG', 'PILOT_DATA_DIR', 'PILOT_OUT_DIR', 'PILOT_FED_DIR'):
        envd2.pop(k, None)
    r = subprocess.run([sys.executable, '-c', code_dr, pilot], env=envd2, capture_output=True, text=True, encoding='utf-8')
    if r.returncode:
        print(r.stderr[-3000:])
    o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
    g = o.get('good', {})
    ok_all = ['H1 xgb_leaky vs xgb_regularized', 'H2 xgb_leaky B1 (size)', 'H2 xgb_leaky B2 (unequal sites)',
              'H2 xgb_regularized B1 (size)', 'H2 xgb_regularized B2 (unequal sites)', 'H2 xgb_krcp B1 (size)',
              'H3 xgb_leaky B1_comb', 'H3 xgb_regularized B2_comb', 'H4 xgb_leaky', 'H4 xgb_regularized', 'H4 xgb_krcp',
              'H5 xgb_leaky F_B1', 'H5 xgb_regularized F_B2', 'H5 xgb_krcp F_B1', 'H6 xgb_regularized']
    check(all(g.get(k) == 'supported' for k in ok_all), f'decision rules: constructed tables with known answers are all supported ({g})')
    rl = o.get('roles', {})
    check(rl.get('H5 xgb_krcp F_B1') == 'primary' and rl.get('H2 xgb_krcp B1 (size)') == 'primary'
          and rl.get('H5 xgb_krcp F_B2') == 'secondary' and rl.get('H5 xgb_regularized F_B1') == 'secondary'
          and rl.get('H2 xgb_krcp B2 (unequal sites)') == 'secondary' and rl.get('H3 xgb_krcp B1_comb') == 'secondary',
          'decision rules: only H5 and the B1 part of H2 for krcp are primary; every other row is secondary')
    check(o.get('f_exposed', {}).get('H5 xgb_regularized F_B1') == 'not supported'
          and o['f_exposed'].get('H5 xgb_regularized F_B2') == 'not supported',
          'decision rules: H5 fails when the federated model is more exposed than central + 0.01')
    check(o.get('flat_curve', {}).get('H6 xgb_regularized') == 'not supported', 'decision rules: H6 fails on a flat size curve')
    check(o.get('bad_gate3', {}).get('H4 xgb_regularized') == 'not supported', 'decision rules: H4 fails when the Gate 3 re-run differs')
    ng = o.get('no_gate3_leaky', {})
    check(ng.get('H4 xgb_leaky') == 'not evaluable' and ng.get('H4 xgb_regularized') == 'supported',
          'decision rules: H4 is not evaluable for a variant without Gate 3, and judged for the others')
    one = o.get('one_seed', {})
    check(one.get('H5 xgb_regularized F_B1') == 'not evaluable' and one.get('H3 xgb_regularized B1_comb') == 'not evaluable'
          and one.get('H1 xgb_leaky vs xgb_regularized') == 'supported',
          'decision rules: a single seed gives "not evaluable" for interval rules, while mean-based H1 is still judged')

    # attack functions on constructed shadows with a known membership signal
    code_att = r"""
import importlib.util, json, os, sys
import numpy as np
here = sys.argv[1]
sys.path.insert(0, here)
import pilot_lib as L
spec = importlib.util.spec_from_file_location('att03', os.path.join(here, '03_attack_audit.py'))
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
rng = np.random.default_rng(3)
n, K = 1200, 48
y = rng.integers(0, 2, n)
def conf_to_p(pc):
    return np.where(y == 1, pc, 1 - pc).astype(np.float32)
def shadow_set(prob_in):
    inm = rng.random((K, n)) < prob_in
    pc = np.where(inm, rng.beta(8, 2, (K, n)), rng.beta(4, 4, (K, n)))
    return inm, np.stack([conf_to_p(pc[k]) for k in range(K)])
inm, sp = shadow_set(0.4)
members = np.sort(rng.choice(n, 400, replace=False)); non = np.setdiff1d(np.arange(n), members)
tpc = np.where(np.isin(np.arange(n), members), rng.beta(8, 2, n), rng.beta(4, 4, n))
tp = conf_to_p(tpc)
ev = np.concatenate([members, rng.choice(non, 400, replace=False)]); lab = np.r_[np.ones(400, int), np.zeros(400, int)]
z = rng.choice(n, 300, replace=False)
out = {'lira': L.auc(lab, A.lira(inm, sp, y, tp, ev)),
       'lira_gv': L.auc(lab, A.lira(inm, sp, y, tp, ev, global_var=True)),
       'rmia': L.auc(lab, A.rmia(inm, sp, y, tp, ev, z))}
tp0 = conf_to_p(rng.beta(4, 4, n))      # a target that carries no membership signal
out['lira_null'] = L.auc(lab, A.lira(inm, sp, y, tp0, ev))
out['rmia_null'] = L.auc(lab, A.rmia(inm, sp, y, tp0, ev, z))
# averaged triples: the person must be in at most one of the three shadows
sets = [shadow_set(0.3) for _ in range(3)]
i2, p2, ok = A.combine(sets)
cnt = np.sum([q[0] for q in sets], axis=0)
out['combine_in'] = bool(np.array_equal(i2, cnt == 1))
out['combine_valid'] = bool(np.array_equal(ok, cnt <= 1))
out['combine_p'] = bool(np.allclose(p2, np.mean([q[1] for q in sets], axis=0)))
out['dropped_share'] = float(1 - ok.mean())
# attacks run with the validity mask
out['lira_masked'] = L.auc(lab, A.lira(i2, p2, y, tp, ev, valid=ok))
print(json.dumps(out))
"""
    envd3 = dict(os.environ, PILOT_MODEL='xgb', PILOT_QUICK='1', PYTHONIOENCODING='utf-8')
    for k in ('PILOT_TAG', 'PILOT_DATA_DIR', 'PILOT_OUT_DIR', 'PILOT_FED_DIR'):
        envd3.pop(k, None)
    r = subprocess.run([sys.executable, '-c', code_att, pilot], env=envd3, capture_output=True, text=True, encoding='utf-8')
    if r.returncode:
        print(r.stderr[-3000:])
    q = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
    check(q.get('lira', 0) > 0.75 and q.get('lira_gv', 0) > 0.75 and q.get('rmia', 0) > 0.7,
          f'attacks: LiRA, LiRA with global variance and RMIA find a planted membership signal ({ {k: round(v, 2) for k, v in q.items() if k in ("lira", "lira_gv", "rmia")} })')
    check(abs(q.get('lira_null', 1) - 0.5) < 0.06 and abs(q.get('rmia_null', 1) - 0.5) < 0.06,
          'attacks: no signal gives AUC near 0.5 for LiRA and RMIA')
    check(q.get('combine_in') and q.get('combine_valid') and q.get('combine_p') and 0.05 < q.get('dropped_share', 0) < 0.4
          and q.get('lira_masked', 0) > 0.7,
          'attacks: averaged triples keep a person only when in at most one of the three shadows, and the attack still runs')


# ───────────────────────── 6. MIMIC-IV-ED matrix builder (insurance cohort) ─────────────────────────
def test_mimic():
    print('[mimic] analysis/mimic_ed matrix builder: generated ED release, then the open demo-2.2 only')
    import gzip
    import json
    mim = os.path.join(os.path.dirname(PKG), 'mimic_ed')
    sys.path.insert(0, mim)
    import matrix_mimic_ed as M
    root = os.path.join(WORK, 'fx_mimic')
    shutil.rmtree(root, ignore_errors=True)
    d = os.path.join(root, 'ed')
    os.makedirs(d)
    rng = np.random.default_rng(3)
    n = 60
    rows = []
    for i in range(n):                                    # one stay per person at 2150-01-02 + i days
        rows.append((1000 + i, 5000 + i, 9000 + i, f'2150-01-{2 + i % 27:02d} {8 + i % 12}:00:00', 'M' if i % 2 else 'F',
                     rng.choice(['WHITE', 'BLACK/AFRICAN AMERICAN', 'ASIAN - CHINESE', 'HISPANIC/LATINO - PUERTO RICAN', 'OTHER']),
                     rng.choice(['WALK IN', 'AMBULANCE', 'HELICOPTER', 'OTHER']), 'ADMITTED' if i % 5 in (0, 1) else 'HOME'))
    first_out = {r[0]: r[7] for r in rows}
    for i in range(0, 20, 2):                             # a later second stay for 10 people, outcome flipped
        rows.append((1000 + i, 6000 + i, 19000 + i, '2160-03-01 10:00:00', 'M' if i % 2 else 'F', 'WHITE', 'WALK IN',
                     'HOME' if first_out[1000 + i] == 'ADMITTED' else 'ADMITTED'))
    ed = pd.DataFrame(rows, columns=['subject_id', 'hadm_id', 'stay_id', 'intime', 'gender', 'race', 'arrival_transport', 'disposition'])
    ed['outtime'] = ed['intime']
    ed.to_csv(os.path.join(d, 'edstays.csv.gz'), index=False, compression='gzip')
    tri = pd.DataFrame({'subject_id': ed['subject_id'], 'stay_id': ed['stay_id'],
                        'temperature': rng.normal(98, 1, len(ed)), 'heartrate': rng.normal(85, 10, len(ed)),
                        'resprate': 18.0, 'o2sat': 98.0, 'sbp': 130.0, 'dbp': 80.0, 'pain': '5',
                        'acuity': rng.choice([1.0, 2.0, 3.0, 4.0, 5.0], len(ed)), 'chiefcomplaint': 'secret free text'})
    tri.loc[tri['stay_id'] == 9001, 'heartrate'] = np.nan
    tri.loc[tri['stay_id'] == 9002, 'pain'] = 'UA'
    tri.loc[tri['stay_id'] == 9003, 'pain'] = '11'
    tri.loc[tri['stay_id'] == 9004, 'acuity'] = np.nan
    tri.to_csv(os.path.join(d, 'triage.csv.gz'), index=False, compression='gzip')
    mr = pd.DataFrame({'subject_id': 1, 'stay_id': [9000] * 5 + [9001] * 2, 'name': ['a', 'a', 'b', 'c', 'c', 'x', 'y']})
    mr.to_csv(os.path.join(d, 'medrecon.csv.gz'), index=False, compression='gzip')
    pat = pd.DataFrame({'subject_id': 1000 + np.arange(n), 'anchor_age': rng.integers(20, 95, n)})
    pat_path = os.path.join(root, 'patients.csv.gz')
    pat.to_csv(pat_path, index=False, compression='gzip')

    out, feats, subs, info = M.build(d)
    check(len(out) == n and info['n_people'] == n and info['n_stays_in_release'] == n + 10, 'one row per person (first stay), not per stay')
    first_y = np.array([1 if first_out[1000 + i] == 'ADMITTED' else 0 for i in range(n)])
    check((out['y'].to_numpy() == first_y).all(), 'outcome is that of the first stay (later stays do not leak in)')
    check(not ({'subject_id', 'stay_id', 'hadm_id', 'intime', 'chiefcomplaint'} & set(out.columns)), 'no identifiers, dates or free text in the matrix')
    check(out['split'].value_counts().to_dict() == {'train': 42, 'val': 18}, '70/30 stratified split')
    check(np.isnan(out['heartrate'].iloc[1]) and out['triage_incomplete'].iloc[1] == 1, 'missing vitals stay missing (flagged, not imputed)')
    check(np.isnan(out['pain'].iloc[2]) and np.isnan(out['pain'].iloc[3]), 'pain text "UA" and out-of-range 11 become missing')
    check(np.isnan(out['acuity'].iloc[4]) and out['stratum'].iloc[4] == 'NA', 'missing acuity stays missing, stratum NA')
    check(out['n_prior_meds'].iloc[0] == 3 and out['n_prior_meds'].iloc[1] == 2, 'prior medications are distinct names per stay (3, 2), not rows')
    check(set(out['stratum']) <= {'ESI1-2', 'ESI3', 'ESI4-5', 'NA'} and 'age' not in feats, 'strata from ESI; no age without patients.csv.gz')
    o2, f2, s2, i2 = M.build(d, patients_path=pat_path)
    check('age' in f2 and 'sg_age65' in s2 and i2['uses_patients'] and o2['age'].notna().all(), 'age added when MIMIC-IV patients is given')
    o3, _, _, i3 = M.build(d, n_sample=30)
    check(len(o3) == 30 and i3.get('sampled') == 30, 'stratified sample of fixed size')

    demo = os.path.join(os.path.dirname(os.path.dirname(PKG)), 'data', 'mimic-iv-ed', 'demo-2.2', 'ed')
    if not os.path.exists(os.path.join(demo, 'edstays.csv.gz')):
        print('  (open demo-2.2 not on disk -- demo checks skipped)')
        return
    envd = dict(os.environ, PILOT_DATA_DIR=os.path.join(root, 'data'), PILOT_OUT_DIR=os.path.join(root, 'out'),
                PILOT_FED_DIR=os.path.join(root, 'fed'), PILOT_TAG='demo', PILOT_DEBUG='1', PYTHONIOENCODING='utf-8')
    envd.pop('PILOT_MODEL', None)
    pilot = os.path.join(os.path.dirname(PKG), 'snuh_pilot')
    r = subprocess.run([sys.executable, os.path.join(pilot, '00_build_matrix.py'), '--dataset', 'mimic_ed'], env=envd,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-3000:])
    mp = os.path.join(root, 'data', 'matrix_mimic_ed_demo.parquet')
    ok = r.returncode == 0 and os.path.exists(mp)
    check(ok, 'step 00 builds matrix_mimic_ed_demo.parquet from the open demo')
    if ok:
        m = pd.read_parquet(mp)
        meta = json.load(open(mp.replace('.parquet', '.meta.json'), encoding='utf-8'))
        stays = pd.read_csv(os.path.join(demo, 'edstays.csv.gz'))
        check(len(m) == stays['subject_id'].nunique() and meta['irb'] is None and 0 < m['y'].mean() < 1,
              'demo: one row per person, no IRB number needed, outcome has both classes')
        rs = subprocess.run([sys.executable, os.path.join(os.path.dirname(PKG), 'federated', 'make_sites.py'), '--dataset', 'mimic_ed'],
                            env=envd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        check(rs.returncode == 0 and os.path.exists(os.path.join(root, 'fed', 'mimic_ed_demo', 'B1_s42', 'manifest.json')),
              'make_sites partitions the demo matrix into three sites')


# ───────────────────────── 7. eICU-CRD matrix builder (replication cohort) ─────────────────────────
def test_eicu():
    print('[eicu] analysis/eicu matrix builder: generated release, then the open demo-2.0.1 only')
    import json
    eic = os.path.join(os.path.dirname(PKG), 'eicu')
    sys.path.insert(0, eic)
    import matrix_eicu as E
    root = os.path.join(WORK, 'fx_eicu')
    shutil.rmtree(root, ignore_errors=True)
    d = os.path.join(root, 'rel')
    os.makedirs(d)
    rng = np.random.default_rng(11)
    n_people = 80
    rows = []
    for i in range(n_people):                              # first stay per person
        rows.append(dict(patientunitstayid=100 + i, patienthealthsystemstayid=50 + i, uniquepid=f'P{i:03d}', gender='Male' if i % 2 else 'Female',
                         age='> 89' if i == 0 else str(30 + i % 55), ethnicity=['Caucasian', 'African American', 'Hispanic', 'Asian', 'Other/Unknown'][i % 5],
                         hospitalid=1 + i % 4, apacheadmissiondx='Sepsis, pulmonary' if i % 3 == 0 else 'CHF, congestive heart failure',
                         admissionheight=170.0, admissionweight=70.0 + i % 20, hospitaladmitoffset=-120 - i, hospitaladmitsource='Emergency Department',
                         hospitaldischargeyear=2014 + i % 2, hospitaldischargestatus='Expired' if i % 5 == 0 else 'Alive',
                         unittype='Med-Surg ICU' if i % 2 else 'MICU', unitadmitsource='Floor', unitvisitnumber=1))
    first_status = {r['uniquepid']: r['hospitaldischargestatus'] for r in rows}
    for i in range(0, 16, 2):                              # a later stay for 8 people with the opposite outcome
        r = dict(rows[i]); r.update(patientunitstayid=900 + i, patienthealthsystemstayid=700 + i, unitvisitnumber=2, hospitaldischargeyear=2016,
                                    hospitaldischargestatus='Alive' if first_status[r['uniquepid']] == 'Expired' else 'Expired')
        rows.append(r)
    rows.append(dict(rows[1], patientunitstayid=990, patienthealthsystemstayid=990, uniquepid='PNODX', hospitaldischargestatus=np.nan))   # unknown outcome: dropped
    pat = pd.DataFrame(rows)
    pat.to_csv(os.path.join(d, 'patient.csv.gz'), index=False, compression='gzip')
    ids = pat['patientunitstayid'].tolist()
    aps = pd.DataFrame({'apacheapsvarid': np.arange(len(ids)), 'patientunitstayid': ids})
    for c in E.APS:
        aps[c] = rng.integers(1, 5, len(ids)) if c in ('eyes', 'motor', 'verbal') else rng.integers(0, 2, len(ids)) if c in ('intubated', 'vent', 'dialysis', 'meds') else rng.normal(90, 10, len(ids))
    aps.loc[aps['patientunitstayid'] == 101, ['heartrate', 'urine']] = -1
    aps.to_csv(os.path.join(d, 'apacheApsVar.csv.gz'), index=False, compression='gzip')
    pred = pd.DataFrame({'apachepredvarid': np.arange(len(ids)), 'patientunitstayid': ids})
    for c in E.HISTORY:
        pred[c] = rng.integers(0, 2, len(ids))
    pred['diedinhospital'] = 1                              # an outcome field that must never reach the matrix
    pred.to_csv(os.path.join(d, 'apachePredVar.csv.gz'), index=False, compression='gzip')

    out, feats, subs, info = E.build(d)
    check(len(out) == n_people and info['n_people'] == n_people + 1 and info['n_stays_in_release'] == len(rows),
          'one row per person (first stay); the person without a known outcome is dropped')
    exp = np.array([1 if first_status[f'P{i:03d}'] == 'Expired' else 0 for i in range(n_people)])
    check((out['y'].to_numpy() == exp).all(), 'outcome is that of the first stay (later stays do not leak in)')
    check(not ({'uniquepid', 'patientunitstayid', 'patienthealthsystemstayid', 'diedinhospital', 'hospitaldischargestatus'} & set(out.columns)),
          'no identifiers and no outcome fields in the matrix')
    check(np.isnan(out['heartrate'].iloc[1]) and np.isnan(out['urine'].iloc[1]) and out['age'].iloc[0] == 90.0,
          '-1 becomes missing; "> 89" becomes 90')
    check(out['split'].value_counts().to_dict() == {'train': 56, 'val': 24} and set(out['stratum']) <= {'med-surg', 'medical-cardiac', 'surgical', 'neuro', 'other'},
          '70/30 stratified split and unit-type strata')
    check(set(feats) == set(E.FEATURES) and 'hospital_id' in out.columns and 'hospital_id' not in feats,
          'hospital id is kept outside the features (for real-site use)')
    o3, _, _, i3 = E.build(d, n_sample=40)
    check(len(o3) == 40 and i3.get('sampled') == 40, 'stratified sample of fixed size')
    # real hospitals as sites: the fake release has hospitals 1..4 with 20 people each (ties -> lower id first)
    check(E.pick_hospitals(out['hospital_id'], 'top3', min_rows=1) == [1, 2, 3] and E.pick_hospitals(out['hospital_id'], 'spread3', min_rows=1) == [1, 2, 4],
          'hospital rules: top3 = three largest (ties by id), spread3 = largest / median-ranked / smallest')
    o4, _, _, i4 = E.build(d, hospitals='top3', min_hospital_rows=1)
    per_site = o4.groupby('site').agg(n=('y', 'size'), tr=('split', lambda s: (s == 'train').sum()), hosp=('hospital_id', 'nunique'))
    check(len(o4) == 60 and sorted(o4['site'].unique()) == [0, 1, 2] and (per_site['n'] == 20).all() and (per_site['hosp'] == 1).all()
          and (per_site['tr'] == 14).all() and 'site' not in E.FEATURES,
          'top3 keeps only the three hospitals, one hospital per site, 70/30 split inside each hospital, site is not a feature')
    try:
        E.build(d, hospitals='spread3', min_hospital_rows=21)
        check(False, 'spread3 refuses when fewer than three hospitals reach the minimum size')
    except ValueError:
        check(True, 'spread3 refuses when fewer than three hospitals reach the minimum size')
    # rule 'all' (tag h14 on the full release): every hospital with at least min_rows rows becomes a site
    check(E.pick_hospitals(out['hospital_id'], 'all', min_rows=1) == [1, 2, 3, 4], "hospital rule 'all' keeps every hospital above the minimum, largest first")
    o5, _, _, i5 = E.build(d, hospitals='all', min_hospital_rows=1)
    per5 = o5.groupby('site').agg(n=('y', 'size'), tr=('split', lambda s: (s == 'train').sum()), hosp=('hospital_id', 'nunique'))
    check(sorted(o5['site'].unique()) == [0, 1, 2, 3] and i5['site_rows'] == [20, 20, 20, 20] and (per5['hosp'] == 1).all() and (per5['tr'] == 14).all(),
          "rule 'all' gives one site per hospital (four here) with the 70/30 split inside each (every site has training rows)")
    try:
        E.pick_hospitals(out['hospital_id'], 'all', min_rows=21)
        check(False, "rule 'all' refuses when fewer than three hospitals reach the minimum size")
    except ValueError:
        check(True, "rule 'all' refuses when fewer than three hospitals reach the minimum size")
    # pilot_lib follows the number of fixed sites: build a four-site matrix by hand and check scenarios(), size classes and the tables
    import importlib
    sys.path.insert(0, os.path.join(os.path.dirname(PKG), 'snuh_pilot'))
    import pilot_lib as pl
    importlib.reload(pl)
    s4 = np.where(o5['split'].to_numpy() == 'train', o5['site'].to_numpy(int), -1)
    pl.FIXED_SITES = {'B1': s4, 'B2': s4}
    pl.set_n_sites(4)
    tr4 = np.where(o5['split'].to_numpy() == 'train')[0]
    sc4 = pl.scenarios(tr4, o5['stratum'].to_numpy(), 42)
    cls4 = pl.size_classes(len(tr4))
    check(sorted(k for k in sc4 if k.startswith('B1_')) == [f'B1_{k}' for k in range(4)] and sum(len(sc4[f'B1_{k}'][0]) for k in range(4)) == len(tr4)
          and set(cls4) == {'full', 'site', 'b2_0', 'b2_1', 'b2_2', 'b2_3'} and pl.COMBINED['B1_comb'] == tuple(f'B1_{k}' for k in range(4))
          and pl.FEDERATED['F_B2'] == tuple(f'B2_{k}' for k in range(4)) and pl.site_names('B2') == [f'B2_{k}' for k in range(4)],
          'pilot_lib with four fixed sites: scenarios, size classes, COMBINED and FEDERATED follow N_SITES')
    pl.FIXED_SITES = None
    pl.set_n_sites(3)
    check(pl.COMBINED['B1_comb'] == ('B1_0', 'B1_1', 'B1_2') and set(pl.size_classes(300)) == {'full', 'site', 'b2_0', 'b2_1', 'b2_2'},
          'back to three sites: the tables are as before')
    importlib.reload(pl)

    demo = os.path.join(os.path.dirname(os.path.dirname(PKG)), 'data', 'eicu', 'demo-2.0.1')
    if not os.path.exists(os.path.join(demo, 'patient.csv.gz')):
        print('  (open demo-2.0.1 not on disk -- demo checks skipped)')
        return
    envd = dict(os.environ, PILOT_DATA_DIR=os.path.join(root, 'data'), PILOT_OUT_DIR=os.path.join(root, 'out'),
                PILOT_FED_DIR=os.path.join(root, 'fed'), PILOT_TAG='demo', PILOT_DEBUG='1', PYTHONIOENCODING='utf-8')
    envd.pop('PILOT_MODEL', None)
    pilot = os.path.join(os.path.dirname(PKG), 'snuh_pilot')
    r = subprocess.run([sys.executable, os.path.join(pilot, '00_build_matrix.py'), '--dataset', 'eicu'], env=envd,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-3000:])
    mp = os.path.join(root, 'data', 'matrix_eicu_demo.parquet')
    ok = r.returncode == 0 and os.path.exists(mp)
    check(ok, 'step 00 builds matrix_eicu_demo.parquet from the open demo')
    # fixed real-hospital sites through the driver (tag h3a on the demo, threshold lowered: demo hospitals hold <= 10 people)
    envh = dict(envd, PILOT_TAG='h3a', PILOT_EICU_MIN_ROWS='1', PILOT_EICU_RELEASE='demo')   # never the credentialed full release
    rh = subprocess.run([sys.executable, os.path.join(pilot, '00_build_matrix.py'), '--dataset', 'eicu'], env=envh,
                        capture_output=True, text=True, encoding='utf-8', errors='replace')
    mh = os.path.join(root, 'data', 'matrix_eicu_h3a.parquet')
    if rh.returncode:
        print(rh.stdout[-2000:], rh.stderr[-3000:])
    okh = rh.returncode == 0 and os.path.exists(mh)
    check(okh, 'step 00 with PILOT_TAG=h3a builds a fixed-site matrix from the open demo')
    if okh:
        import importlib
        saved = {k: os.environ.get(k) for k in ('PILOT_DATA_DIR', 'PILOT_TAG')}
        os.environ.update(PILOT_DATA_DIR=os.path.join(root, 'data'), PILOT_TAG='h3a')
        sys.path.insert(0, pilot)
        import pilot_lib as pl
        importlib.reload(pl)
        X, y, split, aux, meta = pl.load_matrix('eicu')
        dfh = pd.read_parquet(mh)
        tr_idx = np.where(split == 'train')[0]
        sc = pl.scenarios(tr_idx, aux['stratum'].to_numpy(), 42)
        sites = [sc[f'B1_{k}'][0] for k in range(3)]
        check(meta.get('fixed_sites') is True and pl.FIXED_SITES is not None and (dfh.loc[split == 'val', 'site_b1'] == -1).all()
              and all((dfh.loc[s, 'site_b1'] == k).all() for k, s in enumerate(sites)) and sum(len(s) for s in sites) == len(tr_idx)
              and all(np.array_equal(sc[f'B1_{k}'][0], sc[f'B2_{k}'][0]) for k in range(3)),
              'scenarios() uses the hospitals as fixed sites (B1 = B2 = hospital; validation rows carry -1)')
        for k, v in saved.items():                 # leave the environment as it was for the tests that follow
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        importlib.reload(pl)
    if ok:
        m = pd.read_parquet(mp)
        meta = json.load(open(mp.replace('.parquet', '.meta.json'), encoding='utf-8'))
        p = pd.read_csv(os.path.join(demo, 'patient.csv.gz'))
        check(len(m) <= p['uniquepid'].nunique() and 0.03 < m['y'].mean() < 0.3 and meta['irb'] is None and m['hospital_id'].nunique() > 20,
              'demo: at most one row per person, plausible mortality, no IRB number, many real hospitals')
        check(m['heartrate'].between(1, 300).sum() == m['heartrate'].notna().sum() and (m['age'].dropna() >= 15).all(),
              'demo: physiological values are in range after the missing code is removed')
        rs = subprocess.run([sys.executable, os.path.join(os.path.dirname(PKG), 'federated', 'make_sites.py'), '--dataset', 'eicu'],
                            env=envd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        check(rs.returncode == 0 and os.path.exists(os.path.join(root, 'fed', 'eicu_demo', 'B1_s42', 'manifest.json')),
              'make_sites partitions the demo matrix into three sites')
        rc = subprocess.run([sys.executable, os.path.join(pilot, 'canary_benchmark.py'), '--dataset', 'eicu', '--configs', 'd2_r100', '--sizes', '2000',
                             '--models', '6', '--targets', '2', '--out-tag', 't'], env=dict(envd, PILOT_MODEL='xgb', PILOT_THREADS='2'),
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
        cells = os.path.join(root, 'out', 'eicu_demo_xgb_canary', 'canary_cells_t.csv')
        ok_c = rc.returncode == 0 and os.path.exists(cells)
        if not ok_c:
            print(rc.stdout[-800:], rc.stderr[-1500:])
        check(ok_c and int(pd.read_csv(cells).n.iloc[0]) == int(0.75 * (len(m) - 400)),
              'canary benchmark runs on a small cohort: the training size is capped so that a quarter of the rows stay outside every model')
        chk = os.path.join(eic, '01_check_release.py')
        r1 = subprocess.run([sys.executable, chk, '--release', 'demo', '--data-root', os.path.dirname(demo), '--out-dir', os.path.join(root, 'chk')],
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
        t1 = open(os.path.join(root, 'chk', '01_check_release_demo.txt'), encoding='utf-8').read() if r1.returncode == 0 else ''
        check('required files     : 3 of 3 present' in t1 and '3 ok, 0 bad' in t1 and 'hospitals        :' in t1 and 'persons per hospital' in t1,
              'release check: checksums of the three required files and aggregate summary (hospital sizes without hospital ids)')
        part = os.path.join(root, 'partial', 'demo-2.0.1')
        os.makedirs(part, exist_ok=True)
        shutil.copy(os.path.join(demo, 'patient.csv.gz'), part)
        shutil.copy(os.path.join(demo, 'SHA256SUMS.txt'), part)
        r2 = subprocess.run([sys.executable, chk, '--release', 'demo', '--data-root', os.path.join(root, 'partial'), '--out-dir', os.path.join(root, 'chk2')],
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
        t2 = open(os.path.join(root, 'chk2', '01_check_release_demo.txt'), encoding='utf-8').read() if r2.returncode == 0 else ''
        check('1 of 3 present  MISSING: apacheApsVar.csv.gz, apachePredVar.csv.gz' in t2 and 'analysis rows' not in t2,
              'release check names the missing files and does not try the adapter')


# ───────────────────────── 8. canary benchmark (release rules against planted-canary ground truth) ─────────────────────────
def test_canary():
    print('[canary] analysis/snuh_pilot/canary_benchmark.py statistics, calibration, summary and a cell smoke run on generated data')
    import json
    pilot = os.path.join(os.path.dirname(PKG), 'snuh_pilot')
    root = os.path.join(WORK, 'fx_canary')
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, 'out', 'synpuf_xgb_canary'))
    child = r"""
import json, sys, os
os.environ['PILOT_QUICK'] = '1'
import numpy as np, pandas as pd
sys.path.insert(0, sys.argv[1])
import canary_benchmark as CB
from sklearn.metrics import roc_auc_score
rng = np.random.default_rng(3)
res = {}
# --- pure functions
lab = rng.integers(0, 2, 300)
sc = np.round(rng.normal(size=300) + lab * 0.7, 1)
res['auc_rank_matches_sklearn_with_ties'] = abs(CB.auc_rank(lab, sc) - roc_auc_score(lab, sc)) < 1e-12
res['auc_one_class_is_nan'] = bool(np.isnan(CB.auc_rank(np.ones(5), np.arange(5))))
res['ppv'] = abs(CB.ppv(0.10, 0.01) - 0.1 * 0.01 / (0.1 * 0.01 + 0.01 * 0.99)) < 1e-12 and abs(CB.ppv(0.01, 0.1) - 0.1) < 1e-12
s = np.r_[np.arange(0, 20), np.arange(15, 35)].astype(float)             # unexposed 0..19, exposed 15..34 (overlap 15..19)
e = np.r_[np.zeros(20, bool), np.ones(20, bool)]
c = CB.calibrate(s, e, 0.9)
res['calibrate_largest_admissible'] = c == 16.0 and CB.sens_spec(s <= c, e) == (0.9, 0.85)
c2 = CB.calibrate(np.array([10, 11, 12, 1, 2, 3.]), np.array([0, 0, 0, 1, 1, 1], bool), 0.9)
res['calibrate_falls_back_to_block_all'] = bool(np.isinf(c2) and c2 < 0)
res['calibrate_needs_both_classes'] = bool(np.isnan(CB.calibrate(np.arange(5.), np.ones(5, bool))))
grp = np.repeat(np.arange(24), 3)
ex = np.arange(len(grp)) // 3 % 2 == 1                                      # every other configuration is exposed
sv = np.where(ex, 2 + rng.random(len(grp)), rng.random(len(grp)))          # separable
rel = CB.loco_release(sv, ex, grp, 0.9)
sens, spec = CB.sens_spec(rel, ex)
res['loco_on_separable_cells'] = sens >= 0.85 and spec == 1.0
lo, hi, ok = CB.boot_clusters(grp, lambda idx: [sv[idx].mean(), np.nan], 200)
res['boot_interval_brackets_point'] = bool(lo[0] <= sv.mean() <= hi[0]) and ok[0] == 1.0 and ok[1] == 0.0
# --- summary on a constructed table with known structure
def cells(k_named, k_lhs):
    rows = []
    for i in range(k_named + k_lhs):
        name = f'cfg{i:02d}' if i < k_named else f'lhs{i:03d}'
        base = rng.random()
        for n in (2000, 6000, 19746):
            z = float(np.clip(base + 0.05 * rng.normal() + 0.03 * np.log10(n / 2000), 0, 1))
            rows.append(dict(config=name, n=n, models=48, canary_auc=0.5 + 0.45 * z, canary_tpr1=0.01 + 0.9 * z ** 2,
                             canary_tpr1_lo=np.nan if i < 3 else 0.01 + 0.9 * z ** 2 - 0.02, canary_tpr1_hi=np.nan if i < 3 else 0.01 + 0.9 * z ** 2 + 0.02,
                             canary_tpr5=0.1, canary_auc_model_sd=0.02, shadow_auc=0.5 + 0.12 * z + 0.04 * rng.normal(),
                             lira_auc=0.5 + 0.3 * z, lira_tpr1=0.01 + 0.3 * z ** 2, leaf_lt11=float(rng.random()),
                             auc_gap=0.2 * z + 0.05 * rng.normal(),
                             depth=2 + i % 10, rounds=50 + 30 * (i % 7), lr=0.05 + 0.02 * (i % 5), mcw=[0, 1, 5, 20][i % 4], lam=[0, 1, 10][i % 3],
                             subsample=0.5 + 0.1 * (i % 5), colsample=0.6 + 0.08 * (i % 5)))
    return pd.DataFrame(rows)
df = cells(12, 8)
st = CB.p1_stats(df, 0.10)
res['p1_known_structure'] = st['auc:lira_tpr1'] == 1.0 and st['auc:shadow_auc'] < 1.0 and st['diff:lira_tpr1'] > 0 and st['rho:lira_tpr1'] > 0.99
md, thr = CB.summarize(df, 0.10, 60)
text = '\n'.join(md)
res['summary_sections'] = all(h in text for h in ('## 1.', '## 2.', '## 3.', '## 4.', '## 5.', '## 6.', '## 7.'))
rl = thr['rules']['lira_tpr1']
res['thresholds_json'] = (rl['release_if'] == '<=' and rl['threshold'] is not None and thr['rules']['n']['release_if'] == '>='
                          and thr['target_sensitivity'] == 0.9 and thr['tau'] == 0.10 and json.dumps(thr) != '')
e2 = (df.canary_tpr1 >= 0.10).to_numpy()
res['calibrated_rule_keeps_target_sensitivity'] = CB.sens_spec((df.lira_tpr1 <= rl['threshold']).to_numpy(), e2)[0] >= 0.9
res['named_and_space_filling_split'] = '| named configurations | 36 |' in text and '| space-filling configurations | 24 |' in text
tiny = CB.summarize(df.iloc[:2], 0.10, 20)
res['tiny_input_does_not_raise'] = len(tiny[0]) > 10
dfb = df.copy()
dfb['canary_tpr1'] = np.clip(df.canary_tpr1 * np.exp(0.05 * rng.normal(size=len(df))), 0.005, 1.0)
for col in ('shadow_auc', 'lira_auc', 'lira_tpr1', 'auc_gap', 'leaf_lt11'):
    dfb[col] = df[col] * (1 + 0.01 * rng.normal(size=len(df)))
cm = '\n'.join(CB.compare_types(df, dfb, 0.10, 40))
same = '\n'.join(CB.compare_types(df, df, 0.10, 40))
res['compare_types'] = '## 8.' in cm and 'Spearman correlation' in cm and 'agree in' in cm and '| LiRA TPR@1%FPR (ordinary rows) |' in cm
res['compare_identical_types'] = 'canaries: 1.00' in same and 'agree in 100% of cells' in same
res['compare_few_cells'] = 'Too few' in CB.compare_types(df.iloc[:3], dfb.iloc[:3], 0.10, 20)[-1]
fx = '\n'.join(CB.apply_fixed(dfb, thr, 0.10, 40))
dfc = dfb.copy()
dfc['canary_tpr1'] = 0.02                                                      # an external cohort without any exposed cell
fx0 = '\n'.join(CB.apply_fixed(dfc, thr, 0.10, 20))
res['apply_fixed'] = '## 9. Thresholds fixed' in fx and '| LiRA TPR@1%FPR (ordinary rows) | LiRA TPR@1%FPR <= ' in fx and 'recalibrated here' in fx
res['apply_fixed_without_exposed_cells'] = 'n/a' in fx0 and '0 of them exposed' in fx0
json.dump(df.to_dict('list'), open(sys.argv[2], 'w'))
# --- one small cell for every kind of setting (named ones with silent parameters, and space-filling ones)
A = CB.attacks()
N = 900
X = pd.DataFrame(rng.normal(size=(N, 8)), columns=[f'f{i}' for i in range(8)])
y = (X.f0 + 0.5 * X.f1 + rng.normal(size=N) > 0).astype(int).to_numpy()
src = np.arange(0, 60)
base = np.arange(60, N)
need = {'config', 'n', 'models', 'canary_auc', 'canary_tpr1', 'canary_tpr1_lo', 'canary_tpr1_hi', 'depth', 'rounds', 'lr', 'mcw', 'lam', 'subsample',
        'colsample', 'threads', 'xgboost', 'shadow_auc', 'lira_auc', 'lira_tpr1', 'leaf_lt11', 'auc_gap'}
bad = []
for cname in ['d2_r100', 'regularized', 'd4_free', 'krcp', 'd6_mcw20', 'd6_free', 'leaky', 'lhs000', 'lhs039']:
    try:
        row = CB.run_cell(X, y, base, src, 1 - y[src], cname, 200, 5, 2, A)
        if not need <= set(row) or not np.isfinite(row['canary_auc']) or row['threads'] != CB.L.N_THREADS:
            bad.append(cname)
    except Exception as ex_:
        bad.append(f'{cname}:{type(ex_).__name__}')
res['every_setting_runs_a_cell'] = not bad
res['bad_settings'] = bad
# --- the two canary types
Xf, yf = CB.make_canaries(X, y, src, 'flip')
Xs, ys = CB.make_canaries(X, y, src, 'shuffle')
res['canaries_flip'] = bool(np.array_equal(Xf.to_numpy(), X.iloc[src].to_numpy()) and np.array_equal(yf, 1 - y[src]))
res['canaries_shuffle'] = bool(all(np.array_equal(np.sort(Xs[c].to_numpy()), np.sort(Xf[c].to_numpy())) for c in Xs.columns)
                               and not np.array_equal(Xs.to_numpy(), Xf.to_numpy()) and set(np.unique(ys)) <= {0, 1}
                               and np.array_equal(CB.make_canaries(X, y, src, 'shuffle')[1], ys))
row_s = CB.run_cell(X, y, base, src, ys, 'd4_free', 200, 5, 2, A, Xs, 'shuffle')
row_f = CB.run_cell(X, y, base, src, yf, 'd4_free', 200, 5, 2, A, Xf, 'flip')
row_d = CB.run_cell(X, y, base, src, yf, 'd4_free', 200, 5, 2, A)
res['shuffle_cell_runs'] = bool(row_s['canary_type'] == 'shuffle' and np.isfinite(row_s['canary_auc']))
res['flip_cell_is_the_default'] = bool(row_f['canary_type'] == 'flip' and row_f['canary_tpr1'] == row_d['canary_tpr1'] and row_f['canary_auc'] == row_d['canary_auc'])
print('RESULT' + json.dumps({k: (bool(v) if isinstance(v, (bool, np.bool_)) else v) for k, v in res.items()}))
"""
    cells_json = os.path.join(root, 'cells.json')
    env = dict(os.environ, PILOT_MODEL='xgb', PYTHONIOENCODING='utf-8', PILOT_THREADS='2')
    env.pop('PILOT_OUT_DIR', None)
    r = subprocess.run([sys.executable, '-c', child, pilot, cells_json], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    line = [ln for ln in r.stdout.splitlines() if ln.startswith('RESULT')]
    if not line:
        print(r.stdout[-1500:], r.stderr[-3000:])
    res = json.loads(line[0][6:]) if line else {}
    for k, msg in [('auc_rank_matches_sklearn_with_ties', 'rank-based AUC equals sklearn, ties included'),
                   ('auc_one_class_is_nan', 'AUC is undefined (nan) when a class is missing'),
                   ('ppv', 'attacker precision: formula and the chance case (TPR = FPR gives the prior)'),
                   ('calibrate_largest_admissible', 'calibration picks the largest threshold that still blocks 90% of exposed cells'),
                   ('calibrate_falls_back_to_block_all', 'calibration falls back to blocking everything when no threshold reaches the target'),
                   ('calibrate_needs_both_classes', 'calibration is undefined without both classes'),
                   ('loco_on_separable_cells', 'leave-one-configuration-out calibration on separable cells'),
                   ('boot_interval_brackets_point', 'cluster bootstrap interval brackets the estimate; undefined resamples are counted'),
                   ('p1_known_structure', 'threshold-free statistics on a table with known structure (LiRA separates, shadow AUC does not fully)'),
                   ('summary_sections', 'summary has all seven sections'),
                   ('thresholds_json', 'calibrated thresholds are exported with direction, tau and target'),
                   ('calibrated_rule_keeps_target_sensitivity', 'exported threshold reproduces the target sensitivity'),
                   ('named_and_space_filling_split', 'named and space-filling configurations are counted separately'),
                   ('tiny_input_does_not_raise', 'two-cell input does not raise'),
                   ('compare_types', 'canary-type comparison reports rank correlation, label agreement and the audit-quantity table'),
                   ('compare_identical_types', 'comparing a canary type with itself gives correlation 1 and full agreement'),
                   ('compare_few_cells', 'canary-type comparison declines to compare when there are too few cells'),
                   ('apply_fixed', 'development thresholds are applied unchanged to another cohort and compared with a local recalibration'),
                   ('apply_fixed_without_exposed_cells', 'fixed-threshold validation does not fail on a cohort without exposed cells'),
                   ('every_setting_runs_a_cell', 'every named and space-filling setting completes a cell and reports its parameters and run environment'),
                   ('canaries_flip', 'flip canaries are the real rows with the label flipped'),
                   ('canaries_shuffle', 'shuffle canaries keep every column marginal, break the joint structure and are reproducible'),
                   ('shuffle_cell_runs', 'a cell with synthetic canaries completes and records its canary type'),
                   ('flip_cell_is_the_default', 'passing the flip canaries explicitly gives the same cell as the default')]:
        check(bool(res.get(k)), msg + (f' (failed: {res.get("bad_settings")})' if k == 'every_setting_runs_a_cell' and not res.get(k) else ''))
    # command line: cells file in, summary and thresholds out
    cells = pd.DataFrame(json.load(open(cells_json)))
    cells.to_csv(os.path.join(root, 'out', 'synpuf_xgb_canary', 'canary_cells_t.csv'), index=False)
    envc = dict(env, PILOT_OUT_DIR=os.path.join(root, 'out'))
    rc = subprocess.run([sys.executable, os.path.join(pilot, 'canary_benchmark.py'), '--dataset', 'synpuf', '--summarize', '--boot', '30'], env=envc,
                        capture_output=True, text=True, encoding='utf-8', errors='replace')
    od = os.path.join(root, 'out', 'synpuf_xgb_canary')
    check(rc.returncode == 0 and os.path.exists(os.path.join(od, 'canary_summary.md')) and os.path.exists(os.path.join(od, 'canary_thresholds.json')),
          'command line --summarize writes canary_summary.md and canary_thresholds.json')
    if rc.returncode:
        print(rc.stdout[-800:], rc.stderr[-1500:])
    rf = subprocess.run([sys.executable, os.path.join(pilot, 'canary_benchmark.py'), '--dataset', 'synpuf', '--summarize', '--boot', '30',
                         '--thresholds', os.path.join(od, 'canary_thresholds.json')], env=envc, capture_output=True, text=True, encoding='utf-8', errors='replace')
    check(rf.returncode == 0 and '## 9. Thresholds fixed on the development cohort' in open(os.path.join(od, 'canary_summary.md'), encoding='utf-8').read(),
          'command line --summarize --thresholds adds the fixed-threshold validation')
    if rf.returncode:
        print(rf.stdout[-800:], rf.stderr[-1500:])
    rq = subprocess.run([sys.executable, os.path.join(pilot, 'canary_screen.py'), '--dataset', 'synpuf'], env=envc, capture_output=True, text=True,
                        encoding='utf-8', errors='replace')
    sq = os.path.join(od, 'q3_screen.md')
    check(rq.returncode == 0 and os.path.exists(sq) and '| LiRA TPR@1%FPR (ordinary rows) | ridge |' in open(sq, encoding='utf-8').read(),
          'canary_screen.py writes the leave-one-configuration-out prediction table')
    if rq.returncode:
        print(rq.stdout[-800:], rq.stderr[-1500:])
    other = os.path.join(root, 'out', 'mimic_ed_s28k_xgb_canary')
    os.makedirs(other, exist_ok=True)
    c2 = cells.copy()
    c2['canary_tpr1'] = (c2['canary_tpr1'] * 1.1).clip(upper=1.0)
    c2.to_csv(os.path.join(other, 'canary_cells_t.csv'), index=False)
    rc2 = subprocess.run([sys.executable, os.path.join(pilot, 'canary_cohorts.py'), '--boot', '30', '--figure', '--figure-dir', os.path.join(root, 'figs')],
                         env=envc, capture_output=True, text=True, encoding='utf-8', errors='replace')
    xc = os.path.join(root, 'out', 'canary_cross_cohort.md')
    txt = open(xc, encoding='utf-8').read() if os.path.exists(xc) else ''
    check(rc2.returncode == 0 and '## 4. Development thresholds applied unchanged' in txt and '| MIMIC-IV-ED |' in txt and '| SynPUF (development) |' in txt,
          'canary_cohorts.py puts the cohorts side by side, with the development thresholds applied unchanged')
    check(os.path.exists(os.path.join(root, 'figs', 'Fig6_canary_cohorts.png')) and os.path.exists(os.path.join(root, 'figs', 'Fig6_canary_cohorts.pdf')),
          'canary_cohorts.py --figure draws the cohorts side by side (PNG and PDF)')
    for folder in ('synpuf_xgb_canary_shuffle', 'mimic_ed_s28k_xgb_canary_shuffle'):
        dd = os.path.join(root, 'out', folder)
        os.makedirs(dd, exist_ok=True)
        c3 = cells.copy()
        c3['canary_type'] = 'shuffle'
        c3['canary_tpr1'] = c3['canary_tpr1'] * 0.8
        c3.to_csv(os.path.join(dd, 'canary_cells_t.csv'), index=False)
    rs3 = subprocess.run([sys.executable, os.path.join(pilot, 'canary_benchmark.py'), '--dataset', 'synpuf', '--summarize', '--canary-type', 'shuffle', '--boot', '30'],
                         env=envc, capture_output=True, text=True, encoding='utf-8', errors='replace')
    rt3 = subprocess.run([sys.executable, os.path.join(pilot, 'canary_cohorts.py'), '--canary-type', 'shuffle', '--types', '--boot', '30'], env=envc,
                         capture_output=True, text=True, encoding='utf-8', errors='replace')
    xs, xt = os.path.join(root, 'out', 'canary_cross_cohort_shuffle.md'), os.path.join(root, 'out', 'canary_cross_cohort_types.md')
    ts = open(xs, encoding='utf-8').read() if os.path.exists(xs) else ''
    tt = open(xt, encoding='utf-8').read() if os.path.exists(xt) else ''
    check(rs3.returncode == 0 and rt3.returncode == 0 and 'synthetic canaries' in ts and '| MIMIC-IV-ED |' in ts,
          'canary_cohorts.py --canary-type shuffle uses the synthetic-canary runs and their own development thresholds')
    check('Spearman of the canary TPR' in tt and '| MIMIC-IV-ED |' in tt,
          'canary_cohorts.py --types compares flipped-label and synthetic canaries cohort by cohort')
    if rs3.returncode or rt3.returncode:
        print(rs3.stdout[-600:], rs3.stderr[-1000:], rt3.stdout[-600:], rt3.stderr[-1200:])
    if rc2.returncode:
        print(rc2.stdout[-800:], rc2.stderr[-1500:])


# ───────────────────────── 9. where the raw extract files are looked for ─────────────────────────
def test_paths():
    print('[paths] raw extract folder resolution (pilot_lib.raw_xlsx_dir)')
    root = os.path.join(WORK, 'fx_paths')
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    code = r'''
import os, sys, json
sys.path.insert(0, sys.argv[1]); import pilot_lib as L
root = sys.argv[2]
mk = lambda *p: os.makedirs(os.path.join(root, *p), exist_ok=True) or os.path.join(root, *p)   # noqa: E731
out = {}
# nothing exists, no PILOT_CKD_ROOT: <root>/Data/CSV is returned, so the caller can report the file as missing
os.environ.pop('PILOT_CKD_ROOT', None); os.environ.pop('PILOT_CDW_DIR', None)
tree = os.path.join(root, 'tree'); L.CKD_ROOT = tree; L.BASE = os.path.join(root, 'base'); L.CDW_DIR = os.path.join(root, 'neutral (DRB)')
out['nothing'] = L.raw_xlsx_dir() == os.path.join(tree, 'Data', 'CSV')
# old project folder only
legacy = mk('base', 'data', 'ckd_cdw'); out['legacy'] = L.raw_xlsx_dir() == legacy
# neutral folder beats the old one
neutral = mk('neutral (DRB)'); out['neutral_over_legacy'] = L.raw_xlsx_dir() == neutral
# a CKD_ML-like tree beats both (as it did before the move)
csv = mk('tree', 'Data', 'CSV'); out['tree_first'] = L.raw_xlsx_dir() == csv
# the explicit override beats everything
os.environ['PILOT_CDW_DIR'] = os.path.join(root, 'elsewhere'); out['override'] = L.raw_xlsx_dir() == os.path.join(root, 'elsewhere')
del os.environ['PILOT_CDW_DIR']
# PILOT_CKD_ROOT set (tests, a copy of the tree) and no Data/CSV in it: never falls through to the real extract
import shutil; shutil.rmtree(csv)
os.environ['PILOT_CKD_ROOT'] = tree
out['fixture_isolated'] = L.raw_xlsx_dir() == os.path.join(tree, 'Data', 'CSV')
print(json.dumps(out))
'''
    r = subprocess.run([sys.executable, '-c', code, os.path.join(os.path.dirname(PKG), 'snuh_pilot'), root],
                       env=dict(os.environ, PYTHONIOENCODING='utf-8'), capture_output=True, text=True, encoding='utf-8')
    import json
    if r.returncode:
        print(r.stderr[-3000:])
    out = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
    check(out.get('nothing'), 'no folder exists: the <root>/Data/CSV path comes back, so the missing file is reported')
    check(out.get('legacy'), 'only the old data/ckd_cdw exists: it is used')
    check(out.get('neutral_over_legacy'), 'the neutral DRB folder is preferred to the old data/ckd_cdw')
    check(out.get('tree_first'), 'a CKD_ML-like tree (Data/CSV) is preferred to both, as before the move')
    check(out.get('override'), 'PILOT_CDW_DIR beats everything')
    check(out.get('fixture_isolated'), 'with PILOT_CKD_ROOT set, a fixture without Data/CSV never falls through to the real extract')


def test_p1():
    print('[p1] extract profile on the real layout (name-only diagnosis sheet) and on an ICD-code sheet')
    real_schema = os.path.join(PKG, 'out', 'p1_schema.txt')
    before = os.path.getmtime(real_schema) if os.path.exists(real_schema) else None
    for variant in ('names', 'icd'):
        root = os.path.join(WORK, f'fx_p1_{variant}')
        shutil.rmtree(root, ignore_errors=True)
        F.build_real_layout(root, icd=(variant == 'icd'))
        e = env_for(root)
        r = run('p1_profile_extract.py', [], e, irb='', expect_fail=True)
        check('SNUH data not read' in (r.stdout + r.stderr), f'{variant}: without an IRB number P1 stops before opening any file')
        run('p1_profile_extract.py', [], e)
        out = os.path.join(root, 'out')
        lab_txt = open(os.path.join(out, 'p1_catalog_lab.csv'), encoding='utf-8-sig').read()
        drug_txt = open(os.path.join(out, 'p1_catalog_drug.csv'), encoding='utf-8-sig').read()
        sch0 = open(os.path.join(out, 'p1_schema.txt'), encoding='utf-8').read()
        check('OutsideWindowTest' not in lab_txt and 'OUTDRUG' not in drug_txt,
              f'{variant}: rows outside the approved period 2000-01-01..2025-07-31 are not catalogued')
        check('date window    : 2000-01-01 .. 2025-07-31' in sch0 and re.search(r'LAB-\d.*?\n.*?\n  date window 2000-01-01..2025-07-31 on .검사시행일.: (<11|\d+) of', sch0, re.S) is not None,
              f'{variant}: schema states the window and counts rows outside it')
        if variant == 'names':
            run('p1_profile_extract.py', ['--date-range', '1900-01-01:2100-12-31'], e)
            check('OutsideWindowTest' in open(os.path.join(out, 'p1_catalog_lab.csv'), encoding='utf-8-sig').read()
                  and 'OUTDRUG' in open(os.path.join(out, 'p1_catalog_drug.csv'), encoding='utf-8-sig').read(),
                  'names: --date-range widens the window (the out-of-window rows are there)')
            run('p1_profile_extract.py', [], e)
        files = {f: open(os.path.join(out, f), encoding='utf-8-sig').read() for f in os.listdir(out)}
        alltext = '\n'.join(files.values())
        check({'p1_schema.txt', 'p1_catalog_lab.csv', 'p1_catalog_drug.csv', 'p1_catalog_dx.csv'} <= set(files), f'{variant}: schema and three catalogues written')
        check('ZZPN' not in alltext, f'{variant}: the patient-name column (환자명) never reaches an output file')
        check('ZZSECRET' not in alltext and 'Rare condition xyz' not in alltext, f'{variant}: names carried by fewer than 11 patients are not listed')
        dx = pd.read_csv(os.path.join(out, 'p1_catalog_dx.csv'), encoding='utf-8-sig', dtype=str)
        if variant == 'names':
            check(list(dx.columns) == ['dx_name', 'n_rows_xlsx', 'n_pat_xlsx', 'n_rows_basics', 'n_pat_basics'], 'names: catalogue columns')
            check('Essential (primary) hypertension' in set(dx.dx_name), 'names: a common diagnosis name is listed')
            nums = pd.concat([dx[c] for c in dx.columns if c.startswith('n_')]).dropna()
            ok = nums.map(lambda s: s == '<11' or int(s.replace(',', '')) >= 11).all()
            check(ok, 'names: every count is "<11" or at least 11')
            sch = files['p1_schema.txt']
            check('## Diagnosis names' in sch and 'ICD-10-like token' in sch, 'names: schema reports the name catalogue and the ICD-10-like token share')
            check('birth decade' in sch and 'KIDNEYDS' in sch and 'sex values in BASICS' in sch,
                  'names: schema reports birth decades, KIDNEYDS structure and sex values')
            check(re.search(r'생년월일\s+0\s+100\.0%', sch) is not None, 'names: the all-null BASICS birth column is visible in the schema')
            check('## BASICS dates and diagnosis names' in sch and re.search(r"distinct values of '기타진단일자' per patient: 1 -> 300", sch) is not None,
                  'names: BASICS section: the second date column is constant per patient in the fixture')
            check(re.search(r"first BASICS '기타진단일자' against the sheet's first '진단일자_KIDNEYDS': sheet earlier -> <11, equal -> 300", sch) is not None
                  and re.search(r"first BASICS '내원일자' against the sheet's first '진단일자_OTHER': sheet earlier -> <11, equal -> 300", sch) is not None,
                  'names: BASICS dates against the sheet dates, per patient')
            m = re.search(r"first '진단일자_KIDNEYDS' lies before 2000-01-01: (\d+); of them with a CKD-like diagnosis name inside the window: (\d+)", sch)
            check(m is not None and int(m.group(1)) == 40 and int(m.group(2)) >= 20, 'names: patients with a first diagnosis before the window and a CKD-like name inside it')
            check('History_HTN -> ' in sch and 'dialysis name -> ' in sch and "patients by year of the first BASICS '내원일자'" in sch,
                  'names: pattern counts and first-visit years are reported')
        else:
            check('icd10_code' in dx.columns and 'dx_name' in dx.columns, 'icd: catalogue has icd10_code and the diagnosis name (not the patient name)')
            check('## Diagnosis names' not in files['p1_schema.txt'], 'icd: the name-only section is not written')
    h = subprocess.run([sys.executable, os.path.join(PKG, 'p3_build_cdm.py'), '--help'], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    check('2000-01-01:2025-07-31' in re.sub(r'\s+', '', h.stdout), "P3's default --date-range is the approved period of DRB-E(I)-2025-08-01")
    after = os.path.getmtime(real_schema) if os.path.exists(real_schema) else None
    check(before == after, 'the real analysis/snuh_cdm/out/p1_schema.txt was not touched by the tests')


def test_p2():
    print('[p2] mapping tables from generated P1 catalogues and the fixture vocabulary')
    root = os.path.join(WORK, 'fx_p2')
    shutil.rmtree(root, ignore_errors=True)
    for d in ('p1', 'maps', 'out'):
        os.makedirs(os.path.join(root, d))
    vocab = os.path.join(WORK, 'vocab')
    shutil.rmtree(vocab, ignore_errors=True)
    F.build_vocab(vocab)
    cols = ['test', 'unit', 'n_rows', 'n_pat', 'numeric_rate', 'p05', 'p50', 'p95']
    lab = [('Creatinine(검사24시간가능)', 'mg/dL', '1,000', '500'), ('Creatinine(검사24시간가능)', 'umol/L', '50', '20'),
           ('LDL-Cholesterol(검사24시간가능)', 'mg/dL', '900', '400'), ('Cholesterol(검사24시간가능)', 'mg/dL', '900', '400'),
           ('HDL-Cholesterol(검사24시간가능)', 'mg/dL', '800', '300'), ('CSF Glucose(검사24시간가능)', 'mg/dL', '30', '20'),
           ('Glucose(검사24시간가능)', 'mg/dL', '900', '400'), ('GPT(ALT) [piccolo, 과내간이]', 'U/L', '60', '30'),
           ('GPT(ALT) [piccolo, 과내간이]', '', '37', '36'), ('Microalbumin/Creatinine Ratio (random urine)', '', '700', '300'),
           ('Hb A1c', '%', '<11', '<11'), ('WBC(검사24시간가능)', '10^3/uL', '900', '400'), ('[POCT, ABGA]Hb', 'g/dL', '600', '200')]
    pd.DataFrame([r + ('1', '0', '1', '2') for r in lab], columns=cols).to_csv(os.path.join(root, 'p1', 'p1_catalog_lab.csv'), index=False, encoding='utf-8-sig')
    drug = [('D1', 'Losartan potassium 50mg tab', '900', '300'), ('D2', 'Amlodipine(-besylate) 5mg tab', '900', '300'),
            ('D3', 'Atorvastatin(-calcium) 10mg tab', '900', '300'), ('D4', 'Telmisartan/Amlodipine 40mg/5mg tab', '500', '100'),
            ('D5', 'Amlodipine(-camsylate)/Losartan K 5mg/50mg tab', '500', '100'), ('D6', 'Nystatin 10만U/ml, 100ml syrup', '500', '100'),
            ('D7', 'Normal saline 0.9% 1L bag', '900', '300'), ('D8', 'Ketoconazole 2% 15g cream', '300', '100'),
            ('D9', '(임상약)ASCEND-HF용 Nesiritide 1.58mg 또는 위약', '300', '100'), ('D10', 'Alvityl* 150ml syrup', '300', '100'),
            ('D11', 'Rare product 5mg tab', '<11', '<11'), ('D12', 'Fluticasone 50mcg nasal spray', '300', '100'),
            ('D13', 'Sodium chloride 10% 20mL inj', '300', '100'), ('D14', 'Candesartan cilexetil 8mg tab', '300', '100'),
            ('D15', 'Ezetimibe/Atorvastatin 10/5mg tab', '300', '100'), ('D16', 'Fimasartan 60mg tab', '300', '100'),
            ('D17', 'Valsartan 80mg tab', '300', '100')]
    pd.DataFrame(drug, columns=['drug_code', 'ingredient_name', 'n_rows', 'n_pat']).to_csv(os.path.join(root, 'p1', 'p1_catalog_drug.csv'), index=False, encoding='utf-8-sig')
    e = dict(os.environ, PILOT_CDM_OUT=os.path.join(root, 'out'), PYTHONIOENCODING='utf-8', PILOT_DEBUG='1')
    run('p2_build_maps.py', ['--only', 'lab,drug', '--vocab', vocab, '--maps', os.path.join(root, 'maps'), '--p1', os.path.join(root, 'p1')], e, irb='')
    L = pd.read_csv(os.path.join(root, 'maps', 'lab_map.csv'), dtype=str, keep_default_na=False)
    key = {(r.test_name, r.unit): r for r in L.itertuples()}
    check(('Creatinine(검사24시간가능)', 'mg/dL') in key and key[('Creatinine(검사24시간가능)', 'mg/dL')].loinc_code == '2160-0', 'lab: creatinine mg/dL -> LOINC 2160-0')
    check(('Creatinine(검사24시간가능)', 'umol/L') not in key, 'lab: a keyword match with an unexpected unit is left unmapped')
    check(not any('LDL' in t or 'CSF' in t for t, _ in key), 'lab: LDL-cholesterol and CSF glucose are not taken for total cholesterol / glucose')
    check(key[('HDL-Cholesterol(검사24시간가능)', 'mg/dL')].feature == 'HDL' and key[('Cholesterol(검사24시간가능)', 'mg/dL')].feature == 'Cholesterol',
          'lab: HDL goes to HDL, total cholesterol to Cholesterol')
    check(key[('GPT(ALT) [piccolo, 과내간이]', '')].ucum_unit == '[U]/L' and key[('GPT(ALT) [piccolo, 과내간이]', 'U/L')].ucum_unit == '[U]/L',
          'lab: an empty unit takes the unit the extract reports for the same test')
    check(('Hb A1c', '%') not in key and ('WBC(검사24시간가능)', '10^3/uL') not in key, 'lab: pairs below 11 patients and non-inputs are not mapped')
    check(key[('[POCT, ABGA]Hb', 'g/dL')].loinc_code == '718-7', 'lab: POCT Hb -> 718-7')
    D = pd.read_csv(os.path.join(root, 'maps', 'drug_map.csv'), dtype=str, keep_default_na=False)
    ids = lambda name: sorted(int(x) for x in D[D.ingredient_name == name].drug_concept_id if x)  # noqa: E731
    I = F.INGREDIENTS
    check(ids('Losartan potassium 50mg tab') == [I['losartan']] and ids('Amlodipine(-besylate) 5mg tab') == [I['amlodipine']], 'drug: salts are stripped (losartan potassium, amlodipine besylate)')
    check(ids('Telmisartan/Amlodipine 40mg/5mg tab') == sorted([I['telmisartan'], I['amlodipine']]), 'drug: a combination product has one row per ingredient')
    check(ids('Amlodipine(-camsylate)/Losartan K 5mg/50mg tab') == sorted([I['amlodipine'], I['losartan']]), "drug: 'Losartan K' is losartan")
    check(ids('Nystatin 10만U/ml, 100ml syrup') == [I['nystatin']], 'drug: the strength tail is cut whatever its case (10만U/ml)')
    check(ids('Sodium chloride 10% 20mL inj') == [I['sodium chloride']], "drug: 'sodium chloride' does not collapse into 'chloride'")
    check(ids('Ezetimibe/Atorvastatin 10/5mg tab') == [I['atorvastatin']], 'drug: a trailing strength is cut; the unknown ingredient is skipped')
    ex = {r.ingredient_name: r for r in D.itertuples() if r.exclude == '1'}
    check(ex['Normal saline 0.9% 1L bag'].exclude_reason == 'fluid' and ex['Ketoconazole 2% 15g cream'].exclude_reason == 'topical'
          and ex['Fluticasone 50mcg nasal spray'].exclude_reason == 'topical' and 'investigational' in ex['(임상약)ASCEND-HF용 Nesiritide 1.58mg 또는 위약'].exclude_reason,
          'drug: fluids, topical / nasal products and investigational products are excluded (concept 0)')
    check(not (D.ingredient_name.isin(['Alvityl* 150ml syrup', 'Rare product 5mg tab', 'Candesartan cilexetil 8mg tab'])).any(),
          'drug: brand products, products below 11 patients and unknown ingredients get no row')
    S = pd.read_csv(os.path.join(root, 'maps', 'atc_supplement.csv'), dtype=str, keep_default_na=False)
    check(list(S.atc_code) == ['C09C'] and list(S.descendant_concept_id) == [str(I['fimasartan'])],
          'drug: an ARB the vocabulary does not place under ATC C09C goes into maps/atc_supplement.csv')
    rep = open(os.path.join(root, 'out', 'p2_report.txt'), encoding='utf-8').read()
    check('RAASi    both' in rep and 'ATC supplement' in rep and 'not found in the vocabulary: none' in rep, 'report: ATC class check, supplement and vocabulary check present')
    check('Alvityl' in open(os.path.join(root, 'out', 'p2_unmapped_drug.csv'), encoding='utf-8-sig').read(), 'report: unmapped list holds the brand product')
    check(not os.path.exists(os.path.join(root, 'maps', 'P2_DONE.txt')), 'P2_DONE.txt is not written while the diagnosis map is missing')
    dxc = [('Chronic kidney disease', '900', '900', '9,000', '900'), ('CRF', '500', '500', '5,000', '500'), ('chronic renal failure_x000D_', '300', '300', '', ''),
           ('chronic renal failure\r\r\n', '', '', '3,000', '300'), ('End stage renal disease', '400', '400', '4,000', '400'),
           ('End stage kidney disease on dialysis', '60', '60', '600', '60'), ('Diabetes mellitus', '700', '700', '7,000', '700'),
           ('essential hypertension', '490', '490', '4,900', '490'), ('kidney transplantation', '287', '286', '2,800', '286'),
           ('liver transplantation', '73', '73', '700', '73'), ('Routine check up', '328', '328', '3,000', '328'),
           ("Alport's Syndrome", '70', '70', '700', '70'), ('hypertension', '1,164', '1,164', '7,000', '1,164')]
    pd.DataFrame(dxc, columns=['dx_name', 'n_rows_xlsx', 'n_pat_xlsx', 'n_rows_basics', 'n_pat_basics']).to_csv(
        os.path.join(root, 'p1', 'p1_catalog_dx.csv'), index=False, encoding='utf-8-sig')
    run('p2_build_maps.py', ['--only', 'lab,drug,dx', '--vocab', vocab, '--maps', os.path.join(root, 'maps'), '--p1', os.path.join(root, 'p1')], e, irb='')
    X = pd.read_csv(os.path.join(root, 'maps', 'dx_map.csv'), dtype=str, keep_default_na=False)
    got = lambda name: sorted((r.domain_id, int(r.condition_concept_id)) for r in X.itertuples()                       # noqa: E731
                              if C_norm(r.icd10_code) == C_norm(name))
    import cdm_lib as C0
    C_norm = C0.norm_icd
    check(got('Chronic kidney disease') == [('Condition', 46271022)], 'dx: an exact SNOMED name maps (Chronic kidney disease)')
    check(got('CRF') == [('Condition', 46271022)], 'dx: the abbreviation CRF is read as chronic renal failure and falls back to the CKD rule')
    check(got('chronic renal failure') == [('Condition', 46271022)] and (X.icd10_code.str.contains('x000D|\r|\n')).sum() == 0,
          'dx: Excel / line-break artefacts are removed from the map keys, and the two spellings share one row')
    check(got('End stage renal disease') == [('Condition', 193782)], 'dx: end stage renal disease -> End-stage renal disease')
    check(got('End stage kidney disease on dialysis') == [('Condition', 193782), ('Procedure', 4146536)],
          'dx: a name with two facts gets a Condition and a Procedure row (ESRD on dialysis)')
    check(got('kidney transplantation') == [('Procedure', 4322471)] and got('liver transplantation') == [],
          'dx: kidney transplantation is an RRT procedure, liver transplantation is not mapped')
    check(got('essential hypertension') == [('Condition', 320128)] and got('Routine check up') == [], 'dx: an exact name maps, a check-up does not')
    check(os.path.exists(os.path.join(root, 'maps', 'P2_DONE.txt')), 'P2_DONE.txt is written once lab, drug and dx are all built')
    check('p2_unmapped_dx.csv' in os.listdir(os.path.join(root, 'out')) and 'diagnoses (dx_map.csv' in open(os.path.join(root, 'out', 'p2_report.txt'), encoding='utf-8').read(),
          'report: the diagnosis part and the unmapped list are written')


def test_names():
    print('[names] the real layout with diagnosis NAMES (no ICD-10 column, BASICS without birth) -> P3 -> P4')
    root = os.path.join(WORK, 'fx_names')
    shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(root + '_codes', ignore_errors=True)
    vocab = os.path.join(WORK, 'vocab')
    if not os.path.exists(os.path.join(vocab, 'CONCEPT.csv')):
        F.build_vocab(vocab)
    nx = F.build_synthetic_names(root, n=400)
    fx, ev = nx['codes'], nx['events']
    env = env_for(root)
    run('p3_build_cdm.py', ['--vocab', vocab, '--maps', os.path.join(root, 'maps'), '--allow-any-n'], env)
    c = con_ro(os.path.join(root, 'cdm', '_central.duckdb'))
    n = lambda sql: c.execute(sql).fetchone()[0]  # noqa: E731
    check(n('SELECT count(*) FROM person') == 400, 'birth and sex come from the DIAGNOSIS sheet (BASICS 생년월일 is empty): all 400 persons are kept')
    yob = fx['basics'].groupby('연구별 환자 ID')['생년월'].first().str[:4].astype(int)
    check(n('SELECT count(*) FROM person WHERE gender_concept_id IN (8507, 8532)') == 400, 'sex from the sheet / BASICS: every person has a gender concept')
    check(sorted(c.execute('SELECT DISTINCT year_of_birth FROM person').df()['year_of_birth']) == sorted(yob.unique()), 'year of birth = the sheet value')
    check(n("SELECT count(*) FROM condition_occurrence WHERE condition_source_value = 'KIDNEYDS' AND condition_concept_id = 46271022")
          == len(nx['first_ckd']), 'the sheet event KIDNEYDS -> one CKD condition per patient with a first diagnosis')
    exp = lambda name: len(ev.drop_duplicates(['연구별 환자 ID', '진단일자', 'name'])[lambda d: d['name'] == name])  # noqa: E731
    check(n("SELECT count(*) FROM condition_occurrence WHERE condition_source_value = 'Essential hypertension'") == exp('Essential hypertension'),
          'diagnosis names of BASICS -> conditions on the visit date (the 1998 rows are cut by the approved period)')
    check(n("SELECT count(*) FROM procedure_occurrence WHERE procedure_source_value = 'hemodialysis'") == exp('hemodialysis'),
          'a name whose standard concept is a Procedure is routed to PROCEDURE_OCCURRENCE')
    check(n("SELECT count(*) FROM condition_occurrence WHERE condition_source_value = 'Dependence on renal dialysis' AND condition_concept_id = 0")
          == exp('Dependence on renal dialysis'), 'an Observation-domain name -> condition row with concept 0')
    check(n("SELECT count(*) FROM condition_occurrence WHERE condition_source_value LIKE '%' || chr(13) || '%' OR condition_source_value LIKE '%_x000D_%'") == 0,
          'no line break or Excel artefact in a source value')
    sc = con_ro(os.path.join(root, 'cdm', 'site_B1_0.duckdb'))
    check(sc.execute("SELECT count(*) FROM cdm_source WHERE source_description LIKE '%dx_layout=names%'").fetchone()[0] == 1,
          'CDM_SOURCE of the site databases records dx_layout=names (P4 reads it)')
    sc.close()
    rep = open(os.path.join(root, 'out', 'p3_build_cdm.txt'), encoding='utf-8').read()
    m_oor = re.search(r'raw_dx\s+([\d,<]+)\s+([\d,<]+)\s+([\d,<]+)', rep)
    oor = int(m_oor.group(3).replace(',', '')) if m_oor and not m_oor.group(3).startswith('<') else 0
    check(oor >= 12, f'the P3 report counts the dated-before-1998 diagnosis rows as out of range ({oor})')
    un = open(os.path.join(root, 'out', 'p3_unmapped_dx.csv'), encoding='utf-8-sig').read()
    check('ZZSECRET' not in un and '(other:' in un and 'ACUTEUPPERRESPIRATORYINFECTION' in un,
          'p3_unmapped_dx.csv: a diagnosis name of fewer than 11 patients is counted, not listed; a frequent unmapped name is listed')
    c.close()
    run('p4_site_features.py', [], env)
    sx = open(os.path.join(root, 'out', 'p4_site_features.txt'), encoding='utf-8').read()
    check('RRT by diagnosis name' in sx, 'P4 reports RRT by diagnosis name in this layout')
    xs = pd.read_parquet(os.path.join(root, 'cdm', 'crosswalk_sites.parquet'))
    xw = pd.read_parquet(os.path.join(root, 'cdm', 'crosswalk.parquet'))
    feats = []
    for db in ['B1_0', 'B1_1', 'B1_2', 'holdout']:
        f = pd.read_parquet(os.path.join(root, 'cdm', 'features', f'{db}.parquet'))
        f = f.reset_index().merge(xs[xs['db'] == db].rename(columns={'person_id': 'gid', 'person_id_site': 'person_id'}),
                                  on='person_id').merge(xw[['person_id', 'rid']].rename(columns={'person_id': 'gid'}), on='gid')
        feats.append(f)
    cdm = pd.concat(feats, ignore_index=True).set_index('rid')
    ref_c = R.cohort(fx)
    ref_in = ref_c[ref_c[['age_ok', 'cr_ok', 'rrt_ok', 'kh_ok']].all(axis=1)]
    check(set(cdm.index) == set(ref_in.index), f'cohort from KIDNEYDS + names = reference cohort of the codes version ({len(cdm)} vs {len(ref_in)})')
    check((pd.to_datetime(cdm['index_date']) == ref_in['index_date'].reindex(cdm.index)).all(), 'index dates = reference')
    d = ev[ev['연구별 환자 ID'].isin(cdm.index)].copy()
    d['idx'] = d['연구별 환자 ID'].map(pd.to_datetime(cdm['index_date']))
    d = d[d['진단일자'] <= d['idx']]
    import cdm_lib as C0
    low = d['name'].str.lower()
    for flag, pat in C0.TEXT_HISTORY.items():
        want = cdm.index.isin(d.loc[low.str.contains(pat, regex=True), '연구별 환자 ID']).astype(int)
        check((cdm[flag].to_numpy() == want).all() and want.sum() > 0, f'{flag} from the diagnosis text = expected ({int(want.sum())} of {len(cdm)} persons)')
    check(cdm['BMI'].isna().all(), 'BMI is missing for everyone (the real BASICS has no BMI)')


def test_visitentry():
    print('[visitentry] P4 --entry visit: the published step 1 (index = first visit, >= 2 creatinine spanning >= 730 d) + v205 exclusions')
    root = os.path.join(WORK, 'fx_visit')
    shutil.rmtree(root, ignore_errors=True)
    vocab = os.path.join(WORK, 'vocab')
    if not os.path.exists(os.path.join(vocab, 'CONCEPT.csv')):
        F.build_vocab(vocab)
    fx = F.build_synthetic(root, n=400)
    env = env_for(root)
    run('p3_build_cdm.py', ['--vocab', vocab, '--maps', os.path.join(root, 'maps'), '--allow-any-n'], env)
    run('p4_site_features.py', ['--entry', 'visit'], env)
    xs = pd.read_parquet(os.path.join(root, 'cdm', 'crosswalk_sites.parquet'))
    xw = pd.read_parquet(os.path.join(root, 'cdm', 'crosswalk.parquet'))
    feats = []
    for db in ['B1_0', 'B1_1', 'B1_2', 'holdout']:
        f = pd.read_parquet(os.path.join(root, 'cdm', 'features_visit', f'{db}.parquet'))
        f = f.reset_index().merge(xs[xs['db'] == db].rename(columns={'person_id': 'gid', 'person_id_site': 'person_id'}),
                                  on='person_id').merge(xw[['person_id', 'rid']].rename(columns={'person_id': 'gid'}), on='gid')
        feats.append(f)
    cdm = pd.concat(feats, ignore_index=True).set_index('rid')
    ref_c = R.cohort(fx, entry='visit')
    ref_in = ref_c[ref_c[['age_ok', 'cr_ok', 'rrt_ok', 'kh_ok']].all(axis=1)]
    check(set(cdm.index) == set(ref_in.index), f'cohort = reference ({len(cdm)} vs {len(ref_in)}; excluded: age {(~ref_c.age_ok).sum()}, '
          f'Cr {(~ref_c.cr_ok).sum()}, RRT {(~ref_c.rrt_ok).sum()}, K/Hb {(~ref_c.kh_ok).sum()})')
    check((pd.to_datetime(cdm['index_date']) == ref_in['index_date'].reindex(cdm.index)).all(), 'index dates = reference')
    first_visit = pd.to_datetime(fx['basics'].groupby('연구별 환자 ID')['내원일자'].min()).reindex(ref_in.index)
    check((ref_in['index_date'] == first_visit).all(), 'the index is the first visit for every cohort member')
    with_ckd = set(fx['dx'].loc[fx['dx']['ICD10코드'].isin(R.CKD), '연구별 환자 ID'])
    no_ckd = [r for r in ref_in.index if r not in with_ckd]
    check(len(no_ckd) >= 20, f'persons without any CKD record are in the cohort (CKD is not re-tested; {len(no_ckd)})')
    only_span = ref_c[ref_c[['age_ok', 'rrt_ok', 'kh_ok']].all(axis=1) & ~ref_c['cr_ok']]
    check(len(only_span) >= 20, f'the creatinine count / span rule excludes persons on its own ({len(only_span)})')
    ckd_only = R.cohort(fx)
    check(set(ckd_only.index) != set(ref_c.index) or not (ckd_only['index_date'] == ref_c['index_date'].reindex(ckd_only.index)).all(),
          'a different cohort than the v205 entry on this fixture')
    ref = R.features(fx, pd.to_datetime(cdm['index_date']), fx['excluded_names'])
    import cdm_lib as C
    worst = []
    for f in C.FEATURES + ['y']:
        a, b = cdm[f].astype(float), ref[f].reindex(cdm.index).astype(float)
        same = ((a - b).abs() <= 1e-9) | (a.isna() & b.isna())
        if not same.all():
            worst.append(f'{f} ({(~same).sum()})')
    check(not worst, 'all 36 features + y equal the pandas reference at the first-visit index' + (f' -- mismatches: {worst}' if worst else ''))
    rep = open(os.path.join(root, 'out', 'p4_site_features_visit.txt'), encoding='utf-8').read()
    check('entry=visit' in rep and 'entry: first visit' in rep and 'first to last >= 730 d apart' in rep and 'eGFR_Slope available' in rep
          and 'without a CKD record on/before the index' in rep,
          'report names the entry rule, the creatinine rule, the persons without a CKD record, and has the baseline / slope availability section')
    check(re.search(r'max \|Δ feature\| 0(?![.\d])', rep) and 'missing mismatches 0' in rep, 'B1 and B2 sites give bit-identical features here too')
    check(os.path.exists(os.path.join(root, 'matrix_snuh_cdmv.parquet')) and not os.path.exists(os.path.join(root, 'matrix_snuh_cdm.parquet')),
          'matrix goes to matrix_snuh_cdmv.parquet (PILOT_TAG=cdmv); the default matrix is not touched')
    meta = json.load(open(os.path.join(root, 'matrix_snuh_cdmv.meta.json'), encoding='utf-8'))
    check(meta['tag'] == 'cdmv' and meta['entry'] == 'visit' and meta['fixed_sites'], 'matrix meta: tag cdmv, entry visit, fixed sites')
    check(not os.path.exists(os.path.join(root, 'out', 'p4_site_features.txt')), 'the default report p4_site_features.txt is not written')
    leak_check(root, set(fx['basics']['연구별 환자 ID']))


def test_drugdays():
    """P4 drug_days on generated prescription intervals, in two shuffled row orders with 4 threads. The real extract showed
    a person's Dur_ACE_ARB_days differing by up to 61 d between two site databases that hold the same rows in another
    order: exact duplicate (start, end) rows at the start of a block were counted into the previous block."""
    print('[drugdays] union of prescription days per class: brute force, shuffled row order, duplicate rows, 4 threads')
    import duckdb
    import p4_site_features as P4
    rng = np.random.default_rng(11)
    origin = pd.Timestamp('1970-01-01')
    base = (date(2015, 1, 1) - date(1970, 1, 1)).days            # day numbers since 1970-01-01
    n_pat, idx = 20000, base + 1000
    index_date = (origin + pd.Timedelta(days=idx)).date().isoformat()
    recs, exp = [], {}
    cls_of = {1: 'RAASi', 2: 'RAASi', 3: 'Statins'}        # drug concept -> class (ancestors 10 = C09A, 11 = C09C, 12 = C10AA)
    for p in range(1, n_pat + 1):
        rows = {'RAASi': [], 'Statins': []}
        for _ in range(int(rng.integers(2, 14))):
            c = int(rng.choice([1, 2, 3]))
            s = base + int(rng.integers(0, 1100))                      # some start after the index (not counted)
            e = s + int(rng.choice([14, 28, 28, 30, 30, 56, 60, 90]))   # exclusive end of the stored end date + 1
            prn = rng.random() < 0.1
            for _ in range(2 if rng.random() < 0.5 else 1):             # exact duplicate prescription rows
                recs.append((p, c, s, e - 1, 'PRN' if prn else None))
            if not prn and s <= idx:
                rows[cls_of[c]].append((s, min(e, idx + 1)))
        for k, iv in rows.items():
            tot, cs, ce = 0, None, None
            for s, e in sorted(set(iv)):
                if ce is None or s > ce:
                    tot += (ce - cs) if ce is not None else 0
                    cs, ce = s, e
                else:
                    ce = max(ce, e)
            tot += (ce - cs) if ce is not None else 0
            if tot:
                exp[(p, k)] = tot
    df0 = pd.DataFrame(recs, columns=['person_id', 'drug_concept_id', 's', 'e', 'sig'])
    df0['drug_exposure_start_date'] = origin + pd.to_timedelta(df0.pop('s'), unit='D')
    df0['drug_exposure_end_date'] = origin + pd.to_timedelta(df0.pop('e'), unit='D')
    got = []
    for seed in (1, 2):
        df = df0.sample(frac=1.0, random_state=seed).reset_index(drop=True)
        con = duckdb.connect()
        con.execute('SET threads TO 4')
        con.register('de_df', df)
        con.execute("""CREATE TABLE drug_exposure AS SELECT person_id, drug_concept_id, CAST(drug_exposure_start_date AS DATE) AS drug_exposure_start_date,
                       CAST(drug_exposure_end_date AS DATE) AS drug_exposure_end_date, sig FROM de_df""")
        con.execute(f"CREATE TABLE cohort AS SELECT DISTINCT person_id AS subject_id, DATE '{index_date}' AS cohort_start_date FROM drug_exposure")
        con.execute("CREATE TABLE concept (concept_id INT, vocabulary_id VARCHAR, concept_code VARCHAR)")
        con.execute("INSERT INTO concept VALUES (10, 'ATC', 'C09A'), (11, 'ATC', 'C09C'), (12, 'ATC', 'C10AA')")
        con.execute("CREATE TABLE concept_ancestor (ancestor_concept_id INT, descendant_concept_id INT)")
        con.execute("INSERT INTO concept_ancestor VALUES (10, 1), (11, 2), (12, 3)")
        d = P4.drug_days(con)
        got.append({(int(r.person_id), r.cls): int(r.days) for r in d.itertuples()})
        con.close()
    check(got[0] == exp, f'days per person and class = brute-force union ({len(exp):,} person-class pairs; PRN, rows after the index and the end past the index handled)')
    check(got[0] == got[1], 'the same rows in another order give the same days')


def test_p6():
    print('[p6] node resource report on a generated CDM (counts only, cohort by duckcdm)')
    root = os.path.join(WORK, 'fx_p6')
    shutil.rmtree(root, ignore_errors=True)
    vocab = os.path.join(WORK, 'vocab')
    if not os.path.exists(os.path.join(vocab, 'CONCEPT.csv')):
        F.build_vocab(vocab)
    F.build_synthetic(root, n=400)
    env = env_for(root)
    run('p3_build_cdm.py', ['--vocab', vocab, '--maps', os.path.join(root, 'maps'), '--allow-any-n'], env)
    out = os.path.join(root, 'p6.txt')
    run('p6_node_resources.py', ['--dbs', 'B1_0', 'central', 'nosuchdb', '--out', out], env)
    txt = open(out, encoding='utf-8').read()
    rows = {ln.split()[0]: ln.split() for ln in txt.splitlines() if ln[:1].isalnum() and ln.split()[0] in ('B1_0', 'central', 'nosuchdb')}
    check(set(rows) == {'B1_0', 'central', 'nosuchdb'}, 'one row per requested database')
    check(rows['nosuchdb'][1] == 'missing', 'a missing database is reported, not an error')
    c = con_ro(os.path.join(root, 'cdm', '_central.duckdb'))
    n_person = c.execute('SELECT count(*) FROM person').fetchone()[0]
    n_meas = c.execute('SELECT count(*) FROM measurement').fetchone()[0]
    c.close()
    check(rows['central'][2] == f'{n_person:,}' and rows['central'][7] == f'{n_meas:,}', 'person and measurement counts match the database')
    check(rows['central'][6] == '<11' or int(rows['central'][6].replace(',', '')) >= 11, 'cells below 11 are suppressed')
    check(float(rows['central'][12]) >= 0 and float(rows['central'][13]) >= 0 and float(rows['central'][14]) > 0, 'timings and peak memory are numbers')
    check(int(rows['central'][11].replace(',', '')) > 0, 'the duckcdm-compiled v205 cohort is non-empty on the generated data')
    run('p6_node_resources.py', ['--dbs', 'B1_0'], env, irb='', expect_fail=True)
    check(True, 'refuses to run without --irb')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--keep', action='store_true')
    ap.add_argument('--only', default='cohort,synthea,synthetic,hook,xgbfam,mimic,eicu,canary,paths,p1,p2,names,drugdays,visitentry,p6')
    a = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    for name in a.only.split(','):
        {'cohort': test_cohort, 'synthea': test_synthea, 'synthetic': test_synthetic, 'hook': test_hook,
         'xgbfam': test_xgbfam, 'mimic': test_mimic, 'eicu': test_eicu, 'canary': test_canary, 'paths': test_paths,
         'p1': test_p1, 'p2': test_p2, 'names': test_names, 'drugdays': test_drugdays, 'visitentry': test_visitentry,
         'p6': test_p6}[name]()
    bad = [m for ok, m in RESULTS if not ok]
    print(f'\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed' + (' -- FAILED: ' + '; '.join(bad) if bad else ''))
    if not a.keep and not bad:
        shutil.rmtree(WORK, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
