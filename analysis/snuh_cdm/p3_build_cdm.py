# -*- coding: utf-8 -*-
"""P3 -- SNUH CKD CDW extract -> OMOP CDM v5.3 subset, then a fixed patient split into site DuckDBs.

  1. Stage the raw extract (BASICS / LAB-1,2 / DRUG parquets, DIAGNOSIS_ICD10.xlsx) with DuckDB, column names
     repaired from cp949 mojibake, layout from cdm_lib.RAW_LAYOUT (+ maps/raw_layout.json).
  2. Resolve the P2 mapping tables (maps/lab_map.csv, dx_map.csv, drug_map.csv) against the codes present.
     Unmapped -> concept_id 0, source values kept.
  3. ETL every patient of the extract (not only the 28,209 cohort) into data/ckd_pilot/cdm/_central.duckdb:
     PERSON, OBSERVATION_PERIOD, VISIT_OCCURRENCE, CONDITION_OCCURRENCE, PROCEDURE_OCCURRENCE (only diagnosis
     codes whose standard concept is in the Procedure domain), MEASUREMENT, DRUG_EXPOSURE + a vocabulary subset
     (CONCEPT, CONCEPT_ANCESTOR, CONCEPT_RELATIONSHIP 'Maps to') from the Athena folder.
  4. Fixed split (seed 42, = analysis/snuh_pilot scenarios() for seed 42):
       published train patients (70 %)  -> B1 sites (3 equal) and B2 sites (50/30/20 %, Dirichlet 0.5 eGFR mix)
       published validation (30 %)      -> holdout.duckdb (common validation set, in no site)
       everyone else in the extract     -> a random site (B1 uniform, B2 with p = 0.5/0.3/0.2)
     Each of the 7 DuckDBs gets fresh person_ids and event ids. The source-ID crosswalk stays in
     data/ckd_pilot/cdm/ (crosswalk.parquet, crosswalk_sites.parquet) and never in out/.
  5. Aggregate report out/p3_build_cdm.txt (+ out/p3_unmapped_*.csv code catalogs, counts < 11 suppressed).

    python p3_build_cdm.py --irb E-XXXX-XXX-XXXX [--vocab data/vocab/athena] [--site-scope all|mapped]
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdm_lib as C  # noqa: E402
from cdm_lib import L, q, lit, sqlpath, date_sql, cell, pct  # noqa: E402

PID = "REGEXP_REPLACE(TRIM(CAST({} AS VARCHAR)), '\\.0$', '')"     # 123 / '123' / 123.0 -> '123'
SEX = ("CASE WHEN UPPER(TRIM(CAST({0} AS VARCHAR))) IN ('M', 'MALE', '남', '남자', '1') THEN 8507 "
       "WHEN UPPER(TRIM(CAST({0} AS VARCHAR))) IN ('F', 'FEMALE', '여', '여자', '2') THEN 8532 ELSE 0 END")
VISIT_TYPE = ("CASE WHEN UPPER(TRIM(CAST({0} AS VARCHAR))) IN ('I', 'IP', 'IN', '입원', 'INPATIENT') THEN 9201 "
              "WHEN UPPER(TRIM(CAST({0} AS VARCHAR))) IN ('E', 'ER', '응급', 'EMERGENCY') THEN 9203 "
              "WHEN UPPER(TRIM(CAST({0} AS VARCHAR))) IN ('O', 'OP', 'OUT', '외래', 'OUTPATIENT') THEN 9202 END")
DIGITS = "REGEXP_REPLACE(CAST({} AS VARCHAR), '[^0-9]', '', 'g')"


def pid(expr):
    return PID.format(expr)


# ───────────────────────── 1. raw staging ─────────────────────────
def stage_raw(con, lay, root, log):
    pq_dir = os.path.join(root, lay['parquet_dir'])
    b = lay['basics']
    p = os.path.join(pq_dir, b['file'])
    basics_path = p
    cols = C.parquet_cols(con, p)
    bcols = cols
    c_pid, c_vd = C.pick(cols, b['pid'], 'BASICS patient id'), C.pick(cols, b['visit_date'], 'BASICS visit date')
    b_pid = c_pid
    c_sex, c_birth = C.pick(cols, b['sex'], 'BASICS sex'), C.pick(cols, b['birth'], 'BASICS birth')
    opt = {k: C.pick(cols, b[k], k, required=False) for k in ('visit_type', 'height', 'weight', 'bmi')}
    num = lambda c: f'TRY_CAST(TRIM(CAST({q(c)} AS VARCHAR)) AS DOUBLE)' if c else 'NULL::DOUBLE'  # noqa: E731
    con.execute(f"""CREATE OR REPLACE VIEW raw_basics AS SELECT {pid(q(c_pid))} AS pid, {date_sql(q(c_vd))} AS visit_date,
        {SEX.format(q(c_sex))} AS gender_concept_id, CAST({q(c_sex)} AS VARCHAR) AS sex_raw,
        {DIGITS.format(q(c_birth))} AS birth_digits,
        {VISIT_TYPE.format(q(opt['visit_type'])) if opt['visit_type'] else 'NULL::INTEGER'} AS visit_type,
        {'CAST(' + q(opt['visit_type']) + ' AS VARCHAR)' if opt['visit_type'] else 'NULL::VARCHAR'} AS visit_type_raw,
        {num(opt['height'])} AS height, {num(opt['weight'])} AS weight, {num(opt['bmi'])} AS bmi
        FROM read_parquet({sqlpath(p)})""")
    log['basics_optional'] = {k: bool(v) for k, v in opt.items()}

    lb = lay['lab']
    parts = []
    for f in lb['files']:
        p = os.path.join(pq_dir, f)
        if not os.path.exists(p):
            log.setdefault('missing', []).append(f)
            continue
        cols = C.parquet_cols(con, p)
        g = {k: C.pick(cols, lb[k], f'{f} {k}') for k in ('pid', 'date', 'test', 'unit', 'value')}
        parts.append(f"""SELECT {pid(q(g['pid']))} AS pid, {date_sql(q(g['date']))} AS d, CAST({q(g['test'])} AS VARCHAR) AS test,
                         CAST({q(g['unit'])} AS VARCHAR) AS unit, CAST({q(g['value'])} AS VARCHAR) AS value
                         FROM read_parquet({sqlpath(p)})""")
    if not parts:
        raise C.LayoutError(f"no LAB parquet ({', '.join(lb['files'])}) in {lay['parquet_dir']}")
    con.execute('CREATE OR REPLACE VIEW raw_lab AS ' + ' UNION ALL '.join(parts))

    dr = lay['drug']
    p = os.path.join(pq_dir, dr['file'])
    cols = C.parquet_cols(con, p)
    if not all(any(c in cols for c in dr[k]) for k in ('pid', 'date', 'code', 'name', 'days', 'prn')) \
            and len(cols) == len(C.DRUG_COLUMNS):
        cols = dict(zip(C.DRUG_COLUMNS, cols.values()))          # drug_dictionary.load_drug_raw: positional
    g = {k: C.pick(cols, dr[k], f'DRUG {k}') for k in ('pid', 'date', 'code', 'name', 'days', 'prn')}
    con.execute(f"""CREATE OR REPLACE VIEW raw_drug AS SELECT {pid(q(g['pid']))} AS pid, {date_sql(q(g['date']))} AS d,
        CAST({q(g['code'])} AS VARCHAR) AS code, CAST({q(g['name'])} AS VARCHAR) AS name,
        CAST(FLOOR(GREATEST(COALESCE(TRY_CAST(TRIM(CAST({q(g['days'])} AS VARCHAR)) AS DOUBLE), 0), 0)) AS INTEGER) AS days,
        TRY_CAST(TRIM(CAST({q(g['days'])} AS VARCHAR)) AS DOUBLE) AS days_raw,
        UPPER(TRIM(CAST({q(g['prn'])} AS VARCHAR))) = 'Y' AS prn
        FROM read_parquet({sqlpath(p)})""")

    dx = lay['dx']
    path = os.path.join(L.raw_xlsx_dir(root, lay['xlsx_dir']), dx['file'])
    empty = {'pid': pd.Series(dtype=str), 'code': pd.Series(dtype=str), 'd_raw': pd.Series(dtype=str)}
    pieces, person = [], pd.DataFrame({'pid': pd.Series(dtype=str), 'birth': pd.Series(dtype=str), 'sex': pd.Series(dtype=str)})
    log['dx_sources'] = {}
    if os.path.exists(path):
        x = pd.read_excel(path, dtype=str)
        x.columns = [C.fix(str(c)) for c in x.columns]
        xc = {c: c for c in x.columns}
        c_pid = C.pick(xc, dx['pid'], 'DIAGNOSIS patient id')
        if dx.get('sheet_codes', True):
            pairs = dx.get('pairs') or [[C.pick(xc, dx['code'], 'DIAGNOSIS code'), C.pick(xc, dx['date'], 'DIAGNOSIS date')]]
            pieces += [pd.DataFrame({'pid': x[c_pid], 'code': x[c], 'd_raw': x[d]}) for c, d in pairs]
            log['dx_pairs'] = len(pairs)
        for label, dcol in dx.get('events') or []:
            c_d = C.pick(xc, [dcol], f'DIAGNOSIS {label} date')
            ev = pd.DataFrame({'pid': x[c_pid], 'code': label, 'd_raw': x[c_d]}).dropna(subset=['d_raw']).drop_duplicates()
            pieces.append(ev)
            log['dx_sources'][f'sheet event {label}'] = len(ev)
        c_b = C.pick(xc, dx.get('birth', []), 'DIAGNOSIS birth', required=False)
        c_s = C.pick(xc, dx.get('sex', []), 'DIAGNOSIS sex', required=False)
        if c_b:
            person = pd.DataFrame({'pid': x[c_pid], 'birth': x[c_b], 'sex': x[c_s] if c_s else None})
    else:
        log.setdefault('missing', []).append(dx['file'])
    long = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame(empty)
    long = long[long['code'].notna() & (long['code'].astype(str).str.strip() != '')]
    con.register('dx_df', long)
    con.execute(f"CREATE OR REPLACE TABLE raw_dx_sheet AS SELECT {pid('pid')} AS pid, TRIM(code) AS code, {date_sql('d_raw')} AS d FROM dx_df")
    con.unregister('dx_df')
    if dx.get('sheet_codes', True):
        log['dx_sources']['sheet codes'] = con.execute('SELECT count(*) FROM raw_dx_sheet').fetchone()[0] - sum(log['dx_sources'].values())
    # birth and sex of the sheet: persons whose BASICS rows carry no birth value take them from here
    con.register('person_df', person)
    con.execute(f"""CREATE OR REPLACE TABLE raw_sheet_person AS SELECT {pid('pid')} AS pid, {DIGITS.format('birth')} AS birth_digits,
        {SEX.format('sex')} AS gender_concept_id, CAST(sex AS VARCHAR) AS sex_raw FROM person_df""")
    con.unregister('person_df')
    # visit-level diagnosis names of BASICS (the real extract: 기타진단명 on the rows of a visit); line breaks and the Excel artefact are blanked
    if dx.get('basics_name'):
        c_nm = C.pick(bcols, dx['basics_name'], 'BASICS diagnosis name')
        c_dd = C.pick(bcols, dx['basics_date'], 'BASICS diagnosis date')
        nm = f"TRIM(REGEXP_REPLACE(REPLACE(CAST({q(c_nm)} AS VARCHAR), '_x000D_', ' '), '[\\r\\n\\t]+', ' ', 'g'))"
        con.execute(f"""CREATE OR REPLACE TABLE raw_dx_basics AS SELECT DISTINCT {pid(q(b_pid))} AS pid, {nm} AS code, {date_sql(q(c_dd))} AS d
            FROM read_parquet({sqlpath(basics_path)}) WHERE {q(c_nm)} IS NOT NULL AND {nm} <> ''""")
        con.execute('CREATE OR REPLACE TABLE raw_dx AS SELECT * FROM raw_dx_sheet UNION ALL SELECT * FROM raw_dx_basics')
        log['dx_sources']['BASICS names'] = con.execute('SELECT count(*) FROM raw_dx_basics').fetchone()[0]
    else:
        con.execute('CREATE OR REPLACE TABLE raw_dx AS SELECT * FROM raw_dx_sheet')
    log['dx_layout'] = 'names' if (dx.get('basics_name') or not dx.get('sheet_codes', True)) else 'icd'


# ───────────────────────── 2. vocabulary + maps ─────────────────────────
def load_vocab_full(con, vdir, log):
    con.execute(f"CREATE OR REPLACE TABLE vocab_concept ({C.CDM_TABLES['concept']})")
    f = C.vocab_file(vdir, 'concept') if vdir and os.path.isdir(vdir) else None
    if f:
        con.execute('INSERT INTO vocab_concept ' + C.read_vocab_sql(f, C.CONCEPT_COLS))
    log['vocab'] = vdir if f else None
    log['vocab_concepts'] = con.execute('SELECT count(*) FROM vocab_concept').fetchone()[0]


def lookup(con, vocab, codes):
    """{code: concept_id} for codes of one vocabulary ('LOINC', 'UCUM'); valid concepts preferred."""
    codes = sorted({str(c) for c in codes if isinstance(c, str) and c.strip()})
    if not codes:
        return {}
    rows = con.execute(f"""SELECT concept_code, concept_id FROM vocab_concept WHERE vocabulary_id = {lit(vocab)}
                           AND concept_code IN ({', '.join(lit(c) for c in codes)})
                           ORDER BY (invalid_reason IS NULL) DESC, (standard_concept = 'S') DESC""").fetchall()
    out = {}
    for code, cid in rows:
        out.setdefault(code, cid)
    return out


def read_map(maps, name, cols):
    p = os.path.join(maps, name)
    df = pd.read_csv(p, dtype=str, keep_default_na=False, encoding='utf-8-sig') if os.path.exists(p) else pd.DataFrame()
    for c in cols:
        if c not in df.columns:
            df[c] = ''
    return df[cols].apply(lambda s: s.str.strip())


def to_int(s, default=0):
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return default


def to_float(s, default):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


LAB_MAP_COLS = ['test_name', 'unit', 'match', 'priority', 'measurement_concept_id', 'loinc_code', 'unit_concept_id',
                'ucum_unit', 'value_multiplier', 'value_offset', 'feature', 'source']


def resolve_lab(con, maps, log):
    """Exact (test, unit) rows > exact test with unit '*' > 'contains' rules by priority. See maps/README.md."""
    m = read_map(maps, 'lab_map.csv', LAB_MAP_COLS)
    cat = con.execute('SELECT test, unit, count(*) AS n FROM raw_lab GROUP BY 1, 2').df()
    loinc = lookup(con, 'LOINC', m['loinc_code'])
    ucum = lookup(con, 'UCUM', list(m['ucum_unit']) + [u for u in cat['unit'] if isinstance(u, str)])
    m['prio'] = m['priority'].map(lambda s: to_float(s, 1e9))
    m = m.sort_values('prio', kind='stable')
    exact = m[m['match'].str.lower() != 'contains']
    contains = m[m['match'].str.lower() == 'contains']
    ex_key = {(r.test_name, r.unit): r for r in exact.itertuples()}
    rows, n_loinc_missing = [], 0
    for t, u in zip(cat['test'], cat['unit']):
        tt, uu = t if isinstance(t, str) else '', u if isinstance(u, str) else ''
        r = ex_key.get((tt, uu)) or ex_key.get((tt, '*'))
        rule = 'exact' if r is not None else ''
        if r is None:
            for cr in contains.itertuples():
                if cr.test_name and cr.test_name in tt and cr.unit in ('*', uu):
                    r, rule = cr, 'contains'
                    break
        raw_unit_id = ucum.get(uu, 0)
        if r is None:
            rows.append((tt, uu, 0, raw_unit_id, 1.0, 0.0, 'unmapped'))
            continue
        cid = to_int(r.measurement_concept_id) or loinc.get(r.loinc_code, 0)
        if not cid:
            n_loinc_missing += 1
        uid = to_int(r.unit_concept_id) or ucum.get(r.ucum_unit, 0) or raw_unit_id
        rows.append((tt, uu, cid, uid, to_float(r.value_multiplier, 1.0), to_float(r.value_offset, 0.0),
                     rule if cid else 'concept_not_in_vocab'))
    df = pd.DataFrame(rows, columns=['test_k', 'unit_k', 'measurement_concept_id', 'unit_concept_id', 'mult', 'offs', 'rule'])
    con.register('lab_df', df)
    con.execute('''CREATE OR REPLACE TABLE map_lab AS SELECT test_k::VARCHAR AS test_k, unit_k::VARCHAR AS unit_k,
        measurement_concept_id::INTEGER AS measurement_concept_id, unit_concept_id::INTEGER AS unit_concept_id,
        mult::DOUBLE AS mult, offs::DOUBLE AS offs, rule::VARCHAR AS rule FROM lab_df''')
    con.unregister('lab_df')
    log['lab_pairs'] = (int((df['measurement_concept_id'] != 0).sum()), len(df))
    log['lab_rules'] = df['rule'].value_counts().to_dict()
    if n_loinc_missing:
        log['lab_loinc_missing'] = n_loinc_missing


def resolve_dx(con, maps, log):
    m = read_map(maps, 'dx_map.csv', ['icd10_code', 'condition_concept_id', 'domain_id', 'source_concept_id', 'source'])
    m['k'] = m['icd10_code'].map(C.norm_icd)
    m['cid'] = m['condition_concept_id'].map(to_int)
    m = m[(m['k'] != '')]
    dom = {}
    ids = sorted({int(c) for c in m['cid'] if c})
    if ids:
        dom = dict(con.execute(f"SELECT concept_id, domain_id FROM vocab_concept WHERE concept_id IN ({', '.join(map(str, ids))})").fetchall())
    m['dom'] = [d if d else dom.get(c, 'Condition') for d, c in zip(m['domain_id'], m['cid'])]
    codes = con.execute(f"SELECT DISTINCT {C.icd_norm_sql('code')} AS k FROM raw_dx").df()['k']
    rows = []
    by = {k: g for k, g in m.groupby('k')}
    for k in codes:
        g = by.get(k)
        if g is None:
            rows.append((k, 'Condition', 0, 0))
            continue
        cond = g[(g['dom'] == 'Condition') & (g['cid'] != 0)]
        proc = g[(g['dom'] == 'Procedure') & (g['cid'] != 0)]
        for r in cond.itertuples():
            rows.append((k, 'Condition', r.cid, to_int(r.source_concept_id)))
        for r in proc.itertuples():
            rows.append((k, 'Procedure', r.cid, to_int(r.source_concept_id)))
        if cond.empty and proc.empty:      # unmapped or another domain (Observation ...): condition row, concept 0
            rows.append((k, 'Condition', 0, to_int(g['source_concept_id'].iloc[0])))
    df = pd.DataFrame(rows, columns=['k', 'domain', 'concept_id', 'source_concept_id'])
    df['other_domain'] = df['k'].isin(m.loc[~m['dom'].isin(['Condition', 'Procedure']), 'k'])
    con.register('dx_m', df)
    con.execute('''CREATE OR REPLACE TABLE map_dx AS SELECT k::VARCHAR AS k, domain::VARCHAR AS domain, concept_id::INTEGER AS concept_id,
        source_concept_id::INTEGER AS source_concept_id, other_domain::BOOLEAN AS other_domain FROM dx_m''')
    con.unregister('dx_m')


def resolve_drug(con, maps, log):
    """(code, name) exact > code '*' (by name) > name '*' (by code); several rows = combination product."""
    m = read_map(maps, 'drug_map.csv', ['drug_code', 'ingredient_name', 'drug_concept_id', 'exclude', 'exclude_reason',
                                        'route', 'source'])
    cat = con.execute('SELECT DISTINCT code, name FROM raw_drug').df()
    g_exact = {k: g for k, g in m.groupby(['drug_code', 'ingredient_name'])}
    g_name = {k: g for k, g in m[m['drug_code'] == '*'].groupby('ingredient_name')}
    g_code = {k: g for k, g in m[m['ingredient_name'] == '*'].groupby('drug_code')}
    rows = []
    for c, n in zip(cat['code'], cat['name']):
        cc, nn = c if isinstance(c, str) else '', n if isinstance(n, str) else ''
        g = g_exact.get((cc, nn))
        if g is None:
            g = g_name.get(nn)
        if g is None:
            g = g_code.get(cc)
        if g is None:
            rows.append((cc, nn, 0, 0, None, None))
            continue
        excl = int(any(to_int(e) == 1 for e in g['exclude']))
        for r in g.itertuples():
            rows.append((cc, nn, to_int(r.drug_concept_id), excl, r.exclude_reason or None, r.route or None))
    df = pd.DataFrame(rows, columns=['code_k', 'name_k', 'drug_concept_id', 'exclude', 'exclude_reason', 'route'])
    df = df.drop_duplicates()
    con.register('drug_m', df)
    con.execute('''CREATE OR REPLACE TABLE map_drug AS SELECT code_k::VARCHAR AS code_k, name_k::VARCHAR AS name_k,
        drug_concept_id::INTEGER AS drug_concept_id, exclude::INTEGER AS exclude, exclude_reason::VARCHAR AS exclude_reason,
        route::VARCHAR AS route FROM drug_m''')
    con.unregister('drug_m')


# ───────────────────────── 3. ETL ─────────────────────────
def build_persons(con, log):
    con.execute("""CREATE OR REPLACE TABLE all_pid AS SELECT DISTINCT pid FROM (
        SELECT pid FROM raw_basics UNION ALL SELECT pid FROM raw_lab UNION ALL SELECT pid FROM raw_drug
        UNION ALL SELECT pid FROM raw_dx) WHERE pid IS NOT NULL AND pid <> ''""")
    demo = """SELECT pid,
        min(TRY_CAST(SUBSTR(birth_digits, 1, 4) AS INTEGER)) FILTER (WHERE TRY_CAST(SUBSTR(birth_digits, 1, 4) AS INTEGER) BETWEEN 1880 AND 2030) AS yob,
        min(TRY_CAST(SUBSTR(birth_digits, 5, 2) AS INTEGER)) FILTER (WHERE TRY_CAST(SUBSTR(birth_digits, 5, 2) AS INTEGER) BETWEEN 1 AND 12) AS mob,
        mode(gender_concept_id) AS gender_concept_id, mode(sex_raw) AS sex_raw FROM {} GROUP BY pid"""
    con.execute(f"""CREATE OR REPLACE TABLE src_demo AS WITH b AS ({demo.format('raw_basics')}), s AS ({demo.format('raw_sheet_person')})
        SELECT COALESCE(b.pid, s.pid) AS pid, COALESCE(b.yob, s.yob) AS yob, COALESCE(b.mob, s.mob) AS mob,
               CASE WHEN COALESCE(b.gender_concept_id, 0) <> 0 THEN b.gender_concept_id ELSE s.gender_concept_id END AS gender_concept_id,
               COALESCE(b.sex_raw, s.sex_raw) AS sex_raw
        FROM b FULL OUTER JOIN s ON b.pid = s.pid""")
    con.execute("""CREATE OR REPLACE TABLE src_person AS
        SELECT a.pid, row_number() OVER (ORDER BY a.pid) AS person_id, d.yob, d.mob, d.gender_concept_id, d.sex_raw
        FROM all_pid a JOIN src_demo d USING (pid) WHERE d.yob IS NOT NULL""")
    n_all, n_kept = con.execute('SELECT (SELECT count(*) FROM all_pid), (SELECT count(*) FROM src_person)').fetchone()
    log['persons'] = (n_all, n_kept)
    con.execute("""INSERT INTO person BY NAME SELECT person_id, COALESCE(gender_concept_id, 0) AS gender_concept_id,
        yob AS year_of_birth, mob AS month_of_birth, 0 AS race_concept_id, 0 AS ethnicity_concept_id,
        sex_raw AS gender_source_value, 0 AS gender_source_concept_id, 0 AS race_source_concept_id,
        0 AS ethnicity_source_concept_id FROM src_person""")


def etl(con, lo, hi, log):
    inrange = lambda d: f"{d} BETWEEN DATE {lit(lo)} AND DATE {lit(hi)}"  # noqa: E731
    cnt = {}
    for t, d in (('raw_basics', 'visit_date'), ('raw_lab', 'd'), ('raw_drug', 'd'), ('raw_dx', 'd')):
        cnt[t] = con.execute(f"""SELECT count(*), count(*) FILTER (WHERE {d} IS NULL),
            count(*) FILTER (WHERE {d} IS NOT NULL AND NOT {inrange(d)}),
            count(*) FILTER (WHERE pid NOT IN (SELECT pid FROM src_person)) FROM {t}""").fetchone()
    log['raw_counts'] = cnt
    # visits: one per person x date (x visit type when the extract has one)
    dv = C.DEFAULT_VISIT_CONCEPT
    con.execute(f"""INSERT INTO visit_occurrence BY NAME
        SELECT row_number() OVER () AS visit_occurrence_id, sp.person_id, COALESCE(b.visit_type, {dv}) AS visit_concept_id,
               b.visit_date AS visit_start_date, b.visit_date AS visit_end_date, {C.TYPE_EHR} AS visit_type_concept_id,
               'BASICS' || COALESCE(':' || b.visit_type_raw, '') AS visit_source_value, 0 AS visit_source_concept_id
        FROM (SELECT DISTINCT pid, visit_date, visit_type, visit_type_raw FROM raw_basics
              WHERE visit_date IS NOT NULL AND {inrange('visit_date')}) b JOIN src_person sp USING (pid)""")
    # conditions / procedures (diagnosis codes routed by the domain of their standard concept)
    con.execute(f"""INSERT INTO condition_occurrence BY NAME
        SELECT row_number() OVER () AS condition_occurrence_id, sp.person_id, m.concept_id AS condition_concept_id,
               r.d AS condition_start_date, {C.TYPE_EHR} AS condition_type_concept_id, r.code AS condition_source_value,
               m.source_concept_id AS condition_source_concept_id, 0 AS condition_status_concept_id
        FROM raw_dx r JOIN src_person sp USING (pid) JOIN map_dx m ON m.k = {C.icd_norm_sql('r.code')} AND m.domain = 'Condition'
        WHERE r.d IS NOT NULL AND {inrange('r.d')}""")
    con.execute(f"""INSERT INTO procedure_occurrence BY NAME
        SELECT row_number() OVER () AS procedure_occurrence_id, sp.person_id, m.concept_id AS procedure_concept_id,
               r.d AS procedure_date, {C.TYPE_EHR} AS procedure_type_concept_id, r.code AS procedure_source_value,
               m.source_concept_id AS procedure_source_concept_id
        FROM raw_dx r JOIN src_person sp USING (pid) JOIN map_dx m ON m.k = {C.icd_norm_sql('r.code')} AND m.domain = 'Procedure'
        WHERE r.d IS NOT NULL AND {inrange('r.d')}""")
    # measurements: labs (+ BMI / height / weight from BASICS when the extract has them)
    con.execute(f"""INSERT INTO measurement BY NAME
        SELECT row_number() OVER () AS measurement_id, sp.person_id, m.measurement_concept_id, r.d AS measurement_date,
               {C.TYPE_EHR} AS measurement_type_concept_id,
               TRY_CAST(TRIM(r.value) AS DOUBLE) * m.mult + m.offs AS value_as_number, 0 AS value_as_concept_id,
               m.unit_concept_id, r.test AS measurement_source_value, 0 AS measurement_source_concept_id,
               r.unit AS unit_source_value, r.value AS value_source_value
        FROM raw_lab r JOIN src_person sp USING (pid)
        JOIN map_lab m ON m.test_k = COALESCE(r.test, '') AND m.unit_k = COALESCE(r.unit, '')
        WHERE r.d IS NOT NULL AND {inrange('r.d')}""")
    body = con.execute("SELECT bool_or(height IS NOT NULL), bool_or(weight IS NOT NULL), bool_or(bmi IS NOT NULL) FROM raw_basics").fetchone()
    if any(body):
        loinc = lookup(con, 'LOINC', ['8302-2', '29463-7', '39156-5'])
        ucum = lookup(con, 'UCUM', ['cm', 'kg', 'kg/m2'])
        bmi_expr = 'bmi' if body[2] else 'weight / ((height / 100) * (height / 100))'
        for col, code, unit, name in (('height', '8302-2', 'cm', 'BASICS.height'), ('weight', '29463-7', 'kg', 'BASICS.weight'),
                                      (bmi_expr, '39156-5', 'kg/m2', 'BASICS.BMI')):
            con.execute(f"""INSERT INTO measurement BY NAME
                SELECT (SELECT COALESCE(max(measurement_id), 0) FROM measurement) + row_number() OVER () AS measurement_id,
                       sp.person_id, {loinc.get(code, 0)} AS measurement_concept_id, b.visit_date AS measurement_date,
                       {C.TYPE_EHR} AS measurement_type_concept_id, b.v AS value_as_number, {ucum.get(unit, 0)} AS unit_concept_id,
                       {lit(name)} AS measurement_source_value, 0 AS measurement_source_concept_id, {lit(unit)} AS unit_source_value,
                       CAST(b.v AS VARCHAR) AS value_source_value
                FROM (SELECT DISTINCT pid, visit_date, {col} AS v FROM raw_basics
                      WHERE visit_date IS NOT NULL AND {inrange('visit_date')} AND {col} IS NOT NULL) b JOIN src_person sp USING (pid)""")
    # drugs: end = start + max(days, 1) - 1 (drug_dictionary: 0 days = one day); PRN kept with sig = 'PRN';
    # products flagged exclude (investigational / fluid / topical) keep concept 0 and route_source_value 'excluded:...'
    con.execute(f"""INSERT INTO drug_exposure BY NAME
        SELECT row_number() OVER () AS drug_exposure_id, sp.person_id,
               CASE WHEN m.exclude = 1 THEN 0 ELSE m.drug_concept_id END AS drug_concept_id,
               r.d AS drug_exposure_start_date, r.d + (GREATEST(r.days, 1) - 1) AS drug_exposure_end_date,
               {C.TYPE_EHR_RX} AS drug_type_concept_id, TRY_CAST(r.days_raw AS INTEGER) AS days_supply,
               CASE WHEN r.prn THEN 'PRN' END AS sig, r.code AS drug_source_value, 0 AS drug_source_concept_id,
               CASE WHEN m.exclude = 1 THEN 'excluded:' || COALESCE(m.exclude_reason, '') ELSE m.route END AS route_source_value
        FROM raw_drug r JOIN src_person sp USING (pid)
        JOIN map_drug m ON m.code_k = COALESCE(r.code, '') AND m.name_k = COALESCE(r.name, '')
        WHERE r.d IS NOT NULL AND {inrange('r.d')}""")
    # observation period = first .. last event date per person (start dates only: a prescription's
    # end date can run past the extract)
    con.execute(f"""INSERT INTO observation_period
        SELECT row_number() OVER (ORDER BY person_id), person_id, min(d), max(d), {C.TYPE_OP_PERIOD} FROM (
            SELECT person_id, visit_start_date AS d FROM visit_occurrence
            UNION ALL SELECT person_id, condition_start_date FROM condition_occurrence
            UNION ALL SELECT person_id, procedure_date FROM procedure_occurrence
            UNION ALL SELECT person_id, measurement_date FROM measurement
            UNION ALL SELECT person_id, drug_exposure_start_date FROM drug_exposure) GROUP BY person_id""")


def vocab_subset(con, vdir, maps, log):
    """Concepts used in the data + the v205 / feature concepts + their ancestors; ancestor rows whose
    descendant is kept; 'Maps to' rows into kept concepts. Enough for circe-style concept-set SQL.
    maps/atc_supplement.csv (P2) adds ancestor rows for ingredients the vocabulary leaves outside the ATC classes P4 reads
    (RxNorm Extension ingredients such as fimasartan, an ARB the published pipeline counts as RAASi)."""
    feat_codes = sorted({c for _, codes, _, _ in C.LAB_FEATURES for c in codes} | set(C.BMI_LOINC))
    feat_ids = list(lookup(con, 'LOINC', feat_codes).values())
    atc = [r[0] for r in con.execute(f"""SELECT concept_id FROM vocab_concept WHERE vocabulary_id = 'ATC'
        AND concept_code IN ({', '.join(lit(c) for v in C.ATC_CLASSES.values() for c in v)})""").fetchall()]
    always = C.V205_CONCEPTS + feat_ids + atc + [C.TYPE_EHR, C.TYPE_EHR_RX, 8507, 8532, 9201, 9202, 9203]
    con.execute(f"""CREATE OR REPLACE TABLE keep_ids AS SELECT DISTINCT id FROM (
        SELECT gender_concept_id AS id FROM person UNION ALL SELECT visit_concept_id FROM visit_occurrence
        UNION ALL SELECT condition_concept_id FROM condition_occurrence UNION ALL SELECT procedure_concept_id FROM procedure_occurrence
        UNION ALL SELECT measurement_concept_id FROM measurement UNION ALL SELECT unit_concept_id FROM measurement
        UNION ALL SELECT drug_concept_id FROM drug_exposure
        UNION ALL SELECT UNNEST([{', '.join(str(int(i)) for i in always)}])) WHERE id IS NOT NULL AND id <> 0""")
    fa = C.vocab_file(vdir, 'concept_ancestor') if log.get('vocab') else None
    if fa:
        con.execute(f"INSERT INTO concept_ancestor SELECT * FROM ({C.read_vocab_sql(fa, C.ANCESTOR_COLS)}) "
                    "WHERE descendant_concept_id IN (SELECT id FROM keep_ids)")
    n_sup = 0
    sup = read_map(maps, 'atc_supplement.csv', ['atc_code', 'descendant_concept_id', 'ingredient_name', 'source'])
    for r in sup.itertuples():
        d = to_int(r.descendant_concept_id)
        a = con.execute("SELECT concept_id FROM vocab_concept WHERE vocabulary_id = 'ATC' AND concept_code = ? LIMIT 1",
                        [r.atc_code.strip()]).fetchone()
        known = con.execute('SELECT 1 FROM vocab_concept WHERE concept_id = ?', [d]).fetchone() if d else None
        if a and known and not con.execute('SELECT 1 FROM concept_ancestor WHERE ancestor_concept_id = ? AND descendant_concept_id = ?',
                                           [a[0], d]).fetchone():
            con.execute('INSERT INTO concept_ancestor VALUES (?, ?, 2, 2)', [a[0], d])
            con.execute('INSERT INTO keep_ids VALUES (?)', [d])
            n_sup += 1
    log['atc_supplement'] = n_sup
    con.execute("""INSERT INTO concept SELECT * FROM vocab_concept WHERE concept_id IN (
        SELECT id FROM keep_ids UNION SELECT ancestor_concept_id FROM concept_ancestor)""")
    fr = C.vocab_file(vdir, 'concept_relationship') if log.get('vocab') else None
    if fr:
        con.execute(f"INSERT INTO concept_relationship SELECT * FROM ({C.read_vocab_sql(fr, C.REL_COLS)}) "
                    "WHERE relationship_id = 'Maps to' AND concept_id_2 IN (SELECT concept_id FROM concept)")
    log['vocab_subset'] = con.execute("""SELECT (SELECT count(*) FROM concept), (SELECT count(*) FROM concept_ancestor),
                                         (SELECT count(*) FROM concept_relationship)""").fetchone()


# ───────────────────────── 4. split ─────────────────────────
def make_split(con, root, lay, log, allow_any_n):
    from sklearn.model_selection import train_test_split
    persons = con.execute('SELECT pid, person_id FROM src_person ORDER BY person_id').df()
    base = pd.read_csv(os.path.join(root, lay['base_csv']), usecols=['RID', 'Outcome_40', 'Baseline_eGFR'], dtype={'RID': str})
    base['RID'] = base['RID'].str.strip().str.replace(r'\.0$', '', regex=True)
    n = len(base)
    y = base['Outcome_40'].astype(int).to_numpy()
    tr, va = train_test_split(np.arange(n), test_size=0.3, stratify=y, random_state=42)   # = 00_build_matrix split
    if n == 28209:
        assert (len(tr), len(va)) == (19746, 8463)
    elif not allow_any_n:
        raise ValueError('Base.csv does not have the published 28,209 rows (use --allow-any-n only for fixtures)')
    train_idx = np.sort(tr)
    egfr = base['Baseline_eGFR']
    stratum = np.select([egfr >= 60, egfr >= 45, egfr >= 30, egfr < 30], ['G1-2', 'G3a', 'G3b', 'G4-5'], 'NA')
    sc = L.scenarios(train_idx, stratum, C.SPLIT_SEED)          # identical to the pilot's seed-42 sites
    s1, s2 = np.full(n, -1), np.full(n, -1)
    for k in range(C.N_SITES):
        s1[sc[f'B1_{k}'][0]] = k
        s2[sc[f'B2_{k}'][0]] = k
    left = train_idx[s1[train_idx] < 0]                          # n_train not divisible by 3 (never for 19,746)
    s1[left] = C.N_SITES - 1
    base['group'] = 'val'
    base.loc[train_idx, 'group'] = 'train'
    base['site_b1'], base['site_b2'], base['stratum'] = s1, s2, stratum

    xw = persons.merge(base[['RID', 'group', 'site_b1', 'site_b2', 'stratum']], left_on='pid', right_on='RID', how='left')
    other = xw['group'].isna().to_numpy()
    rng = np.random.default_rng(C.SPLIT_SEED + 1000)
    xw.loc[other, 'group'] = 'other'
    xw.loc[other, 'site_b1'] = rng.integers(0, C.N_SITES, other.sum())
    xw.loc[other, 'site_b2'] = rng.choice(C.N_SITES, other.sum(), p=np.array(L.B2_SIZE_SHARES))
    xw['site_b1'] = xw['site_b1'].astype(int)
    xw['site_b2'] = xw['site_b2'].astype(int)
    xw = xw.rename(columns={'pid': 'rid'}).drop(columns=['RID'])
    log['split'] = {'base_rows': n, 'base_train': len(tr), 'base_val': len(va),
                    'base_not_in_extract': int((~base['RID'].isin(persons['pid'])).sum()),
                    'base_group_counts': base['group'].value_counts().to_dict(),
                    'b2_stratum': pd.crosstab(base.loc[train_idx, 'stratum'], base.loc[train_idx, 'site_b2']),
                    'xw': xw}

    long = []
    for i, db in enumerate(C.DBS):
        if db == C.HOLDOUT:
            mem = xw.loc[xw['group'] == 'val', 'person_id'].to_numpy()
        else:
            col = 'site_b1' if db.startswith('B1') else 'site_b2'
            mem = xw.loc[(xw['group'] != 'val') & (xw[col] == int(db[-1])), 'person_id'].to_numpy()
        new = np.random.default_rng(C.SPLIT_SEED + 100 + i).permutation(len(mem)) + 1
        long.append(pd.DataFrame({'db': db, 'person_id': mem, 'person_id_site': new}))
    xs = pd.concat(long, ignore_index=True)
    con.register('xs_df', xs)
    con.execute('CREATE OR REPLACE TABLE xw_site AS SELECT * FROM xs_df')
    con.unregister('xs_df')
    return xw, xs


# ───────────────────────── 5. site DuckDBs ─────────────────────────
def write_sites(con, base_dir, scope, irb, dx_layout='icd'):
    sizes = {}
    for db in C.DBS:
        path = C.db_path(db, base_dir)
        for p in (path, path + '.wal'):
            if os.path.exists(p):
                os.remove(p)
        con.execute(f'ATTACH {sqlpath(path)} AS s')
        C.create_cdm(con, 's')
        con.execute(f"CREATE OR REPLACE TEMP TABLE x AS SELECT person_id, person_id_site FROM xw_site WHERE db = {lit(db)}")
        con.execute('INSERT INTO s.person BY NAME SELECT p.* REPLACE (x.person_id_site AS person_id) FROM person p JOIN x USING (person_id)')
        for t, idc in C.EVENT_ID.items():
            where = ''
            if scope == 'mapped' and t in ('measurement', 'drug_exposure'):
                where = f'WHERE e.{C.CONCEPT_COL[t]} <> 0'
            con.execute(f"""INSERT INTO s.{t} BY NAME SELECT e.* REPLACE (x.person_id_site AS person_id,
                            row_number() OVER () AS {idc}) FROM {t} e JOIN x USING (person_id) {where}""")
        for t in ('concept', 'concept_ancestor', 'concept_relationship'):
            con.execute(f'INSERT INTO s.{t} SELECT * FROM {t}')
        con.execute(f"""INSERT INTO s.cdm_source BY NAME SELECT 'SNUH CKD extract, virtual site {db}' AS cdm_source_name,
            {lit(db)} AS cdm_source_abbreviation, 'research team (DRB-E(I)-2025-08-01)' AS cdm_holder,
            {lit('IRB exemption ' + irb + '; analysis/snuh_cdm/p3_build_cdm.py; dx_layout=' + dx_layout)} AS source_description,
            current_date AS cdm_release_date, 'v5.3 (subset)' AS cdm_version""")
        sizes[db] = {t: con.execute(f'SELECT count(*) FROM s.{t}').fetchone()[0] for t in C.CLINICAL}
        con.execute('DETACH s')
    return sizes


# ───────────────────────── 6. report ─────────────────────────
def report(con, log, sizes, xw, out):
    lines = ['# P3 build CDM (aggregates only)', '',
             f"IRB {log['irb']}   built {time.strftime('%Y-%m-%d %H:%M')}   site scope {log['scope']}",
             f"vocabulary: {log['vocab'] or 'NONE (concept tables empty -> P4 cohort finds nothing)'}"
             f"  ({cell(log['vocab_concepts'])} concepts read; subset kept: concept {cell(log['vocab_subset'][0])}, "
             f"ancestor {cell(log['vocab_subset'][1])}, 'Maps to' {cell(log['vocab_subset'][2])}; "
             f"ATC supplement rows {log.get('atc_supplement', 0)})",
             f"missing source files: {', '.join(log.get('missing', [])) or 'none'}",
             f"BASICS optional columns found: {', '.join(k for k, v in log['basics_optional'].items() if v) or 'none'}", '',
             '## source rows (dates outside the range are dropped)',
             f'  {"table":<12} {"rows":>14} {"no date":>12} {"out of range":>13} {"no person":>12}']
    for t, (n, nd, oor, npers) in log['raw_counts'].items():
        lines.append(f'  {t:<12} {cell(n):>14} {cell(nd):>12} {cell(oor):>13} {cell(npers):>12}')
    ds = log.get('dx_sources')
    if ds:
        lines.append('  diagnosis rows before the date window, by source: ' + ', '.join(f'{k} {cell(v)}' for k, v in ds.items())
                     + f"; diagnosis layout: {log.get('dx_layout', 'icd')}")
    n_all, n_kept = log['persons']
    lines += ['', f'persons in the extract {cell(n_all)}; without a valid birth year (no PERSON row, events dropped) '
                  f'{cell(n_all - n_kept)}', '', '## central CDM', f'  {"table":<22} {"rows":>14} {"persons":>10}']
    for t in C.CLINICAL:
        n, p = con.execute(f'SELECT count(*), count(DISTINCT person_id) FROM {t}').fetchone()
        lines.append(f'  {t:<22} {cell(n):>14} {cell(p):>10}')

    lines += ['', '## mapping coverage (rows / persons with concept_id <> 0)']
    for t in ('measurement', 'condition_occurrence', 'procedure_occurrence', 'drug_exposure'):
        c = C.CONCEPT_COL[t]
        n, nm, p, pm = con.execute(f"""SELECT count(*), count(*) FILTER (WHERE {c} <> 0), count(DISTINCT person_id),
            count(DISTINCT person_id) FILTER (WHERE {c} <> 0) FROM {t}""").fetchone()
        lines.append(f'  {t:<22} rows {cell(nm)} / {cell(n)} ({pct(nm, n)})   persons {cell(pm)} / {cell(p)}')
    lp = log['lab_pairs']
    lines.append(f"  lab test x unit pairs mapped {lp[0]:,} / {lp[1]:,}; by rule: "
                 + ', '.join(f'{k} {v:,}' for k, v in log['lab_rules'].items()))
    n_ex, n_prn = con.execute("""SELECT count(*) FILTER (WHERE route_source_value LIKE 'excluded:%'),
                                 count(*) FILTER (WHERE sig = 'PRN') FROM drug_exposure""").fetchone()
    lines.append(f'  drug rows excluded by drug_map (concept 0, investigational/fluid/topical) {cell(n_ex)}; PRN rows (kept, sig=PRN) {cell(n_prn)}')
    n_od = con.execute('SELECT count(*) FROM raw_dx r JOIN map_dx m ON m.k = ' + C.icd_norm_sql('r.code')
                       + ' WHERE m.other_domain').fetchone()[0]
    lines.append(f'  diagnosis rows whose map points to another domain (kept as condition, concept 0) {cell(n_od)}')
    for t, key, c in (('lab', "test, unit", 'measurement_concept_id'), ('dx', 'code', None), ('drug', 'code, name', None)):
        if t == 'lab':
            df = con.execute("""SELECT r.test, r.unit, count(*) n_rows, count(DISTINCT r.pid) n_pat FROM raw_lab r
                JOIN map_lab m ON m.test_k = COALESCE(r.test, '') AND m.unit_k = COALESCE(r.unit, '')
                WHERE m.measurement_concept_id = 0 GROUP BY 1, 2 ORDER BY n_pat DESC""").df()
        elif t == 'dx':
            df = con.execute(f"""SELECT {C.icd_norm_sql('r.code')} AS code, count(*) n_rows, count(DISTINCT r.pid) n_pat
                FROM raw_dx r JOIN map_dx m ON m.k = {C.icd_norm_sql('r.code')} WHERE m.concept_id = 0
                GROUP BY 1 ORDER BY n_pat DESC""").df()
        else:
            df = con.execute("""SELECT r.code, r.name, count(*) n_rows, count(DISTINCT r.pid) n_pat FROM raw_drug r
                JOIN map_drug m ON m.code_k = COALESCE(r.code, '') AND m.name_k = COALESCE(r.name, '')
                WHERE m.drug_concept_id = 0 AND m.exclude = 0 GROUP BY 1, 2 ORDER BY n_pat DESC""").df()
        tail = None
        if t == 'dx':        # diagnosis NAMES are typed by clinicians: a name carried by fewer than 11 patients is counted, not listed
            tiny = df['n_pat'] < L.MIN_CELL
            tail = (int(tiny.sum()), int(df.loc[tiny, 'n_rows'].sum()))
            df = df[~tiny]
        for col in ('n_rows', 'n_pat'):
            df[col] = df[col].map(cell)
        if tail and tail[0]:
            df.loc[len(df)] = [f'(other: {tail[0]:,} names, each with fewer than {L.MIN_CELL} patients)', cell(tail[1]), '']
        df.to_csv(os.path.join(out, f'p3_unmapped_{t}.csv'), index=False, encoding='utf-8-sig')
    lines.append('  unmapped code catalogs -> p3_unmapped_lab.csv / _dx.csv / _drug.csv')

    sp = log['split']
    lines += ['', '## fixed split (seed 42 = pilot scenarios() seed 42)',
              f"  published cohort (Base.csv) {cell(sp['base_rows'])}: train {cell(sp['base_train'])} / val {cell(sp['base_val'])};"
              f" not found in the extract {cell(sp['base_not_in_extract'])}",
              f"  extract persons by group: " + ', '.join(f'{k} {cell(v)}' for k, v in xw['group'].value_counts().items()),
              '  B2 sites: published-train persons by baseline-eGFR stratum (rows) x site (columns)']
    tab = sp['b2_stratum']
    lines.append('    ' + f'{"":<6}' + ''.join(f'{"site " + str(c):>10}' for c in tab.columns))
    for s, r in tab.iterrows():
        lines.append('    ' + f'{s:<6}' + ''.join(f'{cell(v):>10}' for v in r.values))
    lines += ['', '## site DuckDBs (rows per table)',
              f'  {"db":<8}' + ''.join(f'{t[:12]:>14}' for t in C.CLINICAL)]
    for db, s in sizes.items():
        lines.append(f'  {db:<8}' + ''.join(f'{cell(s[t]):>14}' for t in C.CLINICAL))
    grp = xw.groupby(['group']).size()
    lines += ['', '  persons per site by group (train = published train, other = not in the published cohort)']
    for col in ('site_b1', 'site_b2'):
        t = pd.crosstab(xw.loc[xw['group'] != 'val', 'group'], xw.loc[xw['group'] != 'val', col])
        for g, r in t.iterrows():
            lines.append(f'    {col} {g:<6}' + ''.join(f'{cell(v):>10}' for v in r.values))
    lines.append(f"    holdout val   {cell(grp.get('val', 0)):>10}")
    C.write_text(os.path.join(out, 'p3_build_cdm.txt'), lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--irb', default=os.environ.get('PILOT_IRB', ''))
    ap.add_argument('--vocab', default=os.path.join(L.BASE, 'data', 'vocab', 'athena'), help='Athena vocabulary folder (P0)')
    ap.add_argument('--maps', default=C.MAPS, help='folder with lab_map.csv, dx_map.csv, drug_map.csv (P2)')
    ap.add_argument('--site-scope', choices=['all', 'mapped'], default='all',
                    help='mapped = leave concept-0 measurement/drug rows out of the site DBs (central keeps all)')
    ap.add_argument('--date-range', default=':'.join(L.DRB_DATE_RANGE),
                    help='LO:HI; events outside are dropped and counted (default %(default)s = the approved data period of DRB-E(I)-2025-08-01)')
    ap.add_argument('--allow-any-n', action='store_true', help=argparse.SUPPRESS)      # fixtures only
    a = ap.parse_args()
    irb = C.require_irb(a.irb)
    lay = C.load_layout(a.maps)
    lo, hi = a.date_range.split(':')
    base_dir = C.cdm_dir()
    os.makedirs(base_dir, exist_ok=True)
    out = C.out_dir()
    t0 = time.time()

    central = C.db_path('central', base_dir)
    for p in (central, central + '.wal'):
        if os.path.exists(p):
            os.remove(p)
    con = C.connect(central)
    C.create_cdm(con)
    log = {'irb': irb, 'scope': a.site_scope}
    print('[1/6] staging raw extract', flush=True)
    try:
        stage_raw(con, lay, L.CKD_ROOT, log)
    except C.LayoutError as e:
        con.close()
        sys.exit(f'raw extract layout: {e}')
    print('[2/6] vocabulary + mapping tables', flush=True)
    load_vocab_full(con, a.vocab, log)
    resolve_lab(con, a.maps, log)
    resolve_dx(con, a.maps, log)
    resolve_drug(con, a.maps, log)
    print('[3/6] ETL -> central CDM', flush=True)
    build_persons(con, log)
    etl(con, lo, hi, log)
    vocab_subset(con, a.vocab, a.maps, log)
    con.execute('DROP TABLE vocab_concept')
    print('[4/6] fixed split', flush=True)
    xw, xs = make_split(con, L.CKD_ROOT, lay, log, a.allow_any_n)
    xw.to_parquet(os.path.join(base_dir, 'crosswalk.parquet'), index=False)          # restricted: source RID
    xs.to_parquet(os.path.join(base_dir, 'crosswalk_sites.parquet'), index=False)
    print('[5/6] site DuckDBs', flush=True)
    sizes = write_sites(con, base_dir, a.site_scope, irb, log.get('dx_layout', 'icd'))
    print('[6/6] report', flush=True)
    report(con, log, sizes, xw, out)
    json.dump({'irb': irb, 'built': time.strftime('%Y-%m-%d %H:%M'), 'vocab': log['vocab'], 'site_scope': a.site_scope,
               'split_seed': C.SPLIT_SEED, 'dbs': C.DBS}, open(os.path.join(base_dir, 'build.json'), 'w'), indent=1)
    con.close()
    print(f'done in {(time.time() - t0) / 60:.1f} min ->', os.path.relpath(os.path.join(out, 'p3_build_cdm.txt'), L.BASE))


if __name__ == '__main__':
    L.guard(main)
