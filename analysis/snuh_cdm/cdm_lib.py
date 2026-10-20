# -*- coding: utf-8 -*-
"""Shared code for P3 (extract -> OMOP CDM v5.3 subset, site DuckDBs) and P4 (v205 cohort + 36 features).

Data handling is the same as analysis/snuh_pilot (pilot_lib): patient-derived files only under
data/ckd_pilot/ (gitignored), aggregates only under analysis/snuh_cdm/out/. Errors go through
pilot_lib.guard, which prints code locations but not messages.

Paths can be redirected for tests:
  PILOT_CKD_ROOT   raw extract root (pilot_lib)          -- fixture CKD_ML-like tree
  PILOT_CDM_DIR    CDM DuckDB files + crosswalk + per-site matrices (default data/ckd_pilot/cdm)
  PILOT_CDM_OUT    aggregate reports (default analysis/snuh_cdm/out)
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'snuh_pilot'))
import pilot_lib as L  # noqa: E402

IRB_RE = r'E-\d{4}-\d{3}-\d{4}'
MAPS = os.path.join(HERE, 'maps')
SQL_DIR = os.path.join(HERE, 'sql')
SPLIT_SEED = 42                      # = pilot seed 42 -> B1/B2 sites identical to the pilot's seed-42 scenarios
N_SITES = 3
SITES_B1 = [f'B1_{k}' for k in range(N_SITES)]
SITES_B2 = [f'B2_{k}' for k in range(N_SITES)]
HOLDOUT = 'holdout'
DBS = SITES_B1 + SITES_B2 + [HOLDOUT]
DEFAULT_VISIT_CONCEPT = 9202         # Outpatient Visit (BASICS = 내원 records, no visit-type column known yet)
TYPE_EHR = 32817                     # Type Concept "EHR" (condition, procedure, measurement, visit)
TYPE_EHR_RX = 32838                  # Type Concept "EHR prescription"
TYPE_OP_PERIOD = 32817

FEATURES = ['Age', 'Sex_Male', 'ALT', 'AST', 'Albumin', 'BUN', 'Calcium', 'Cholesterol', 'Creatinine', 'GGT',
            'Glucose', 'HDL', 'Hb', 'HbA1c', 'Phosphorus', 'Potassium', 'Sodium', 'TG', 'Total_Bilirubin',
            'Total_Protein', 'UACR', 'Uric_Acid', 'Urine_Creatinine', 'Urine_Microalbumin', 'Baseline_eGFR',
            'eGFR_Slope', 'History_HTN', 'History_DM', 'Subgroup_DKD', 'Subgroup_GN', 'BMI', 'Dur_ACE_ARB_days',
            'Dur_Statin_days', 'Drug_RAASi', 'Drug_Statins', 'Bicarbonate']      # = 00_build_matrix.FEATURES_SNUH
SUBGROUPS = ['sg_age65', 'sg_sex', 'sg_dm', 'sg_ckd_stage']
BINARY = {'Sex_Male', 'History_HTN', 'History_DM', 'Subgroup_DKD', 'Subgroup_GN', 'Drug_RAASi', 'Drug_Statins'}

# Lab features: (feature, LOINC codes [descendants included], plausible range lo, hi -> outside = missing).
# Concept sets are keyed by LOINC code and resolved to concept_id from the vocabulary at run time,
# because several concept ids in KRCP Supplementary Table S1 are wrong (see maps/README.md).
# Ranges = lab_config of SNUH_CKD_DATAPREP.ipynb cell 1 (the code that produced the published matrix);
# Table S2 lists slightly different ranges for some (K, Ca, Glucose ...) -- the code is followed.
LAB_FEATURES = [
    ('Creatinine', ['2160-0'], 0.1, 30.0),
    ('BUN', ['3094-0'], 0.0, 300.0),
    ('Uric_Acid', ['3084-1'], 0.0, 30.0),
    ('Sodium', ['2951-2'], 100.0, 180.0),
    ('Potassium', ['2823-3', '6298-4'], 0.0, 10.0),          # serum + whole blood (lab_config includes POCT ABGA K)
    ('Calcium', ['17861-6'], 0.0, 20.0),
    ('Phosphorus', ['2777-1'], 0.5, 20.0),
    ('Bicarbonate', ['2028-9', '1963-8'], 5.0, 40.0),         # SNUH test = "CO2, total" (TCO2)
    ('Albumin', ['1751-7'], 0.5, 7.0),
    ('Total_Protein', ['2885-2'], 3.0, 15.0),
    ('Total_Bilirubin', ['1975-2'], 0.0, 50.0),
    ('AST', ['1920-8'], 0.0, 2000.0),
    ('ALT', ['1742-6'], 0.0, 2000.0),
    ('GGT', ['2324-2'], 0.0, 2000.0),
    ('Hb', ['718-7', '20509-6'], 3.0, 25.0),
    ('HbA1c', ['4548-4'], 3.0, 20.0),
    ('Glucose', ['2345-7'], 0.0, 2000.0),
    ('HDL', ['2085-9'], 0.0, 200.0),
    ('TG', ['2571-8'], 0.0, 3000.0),
    ('Cholesterol', ['2093-3'], 10.0, 1000.0),
    ('UACR_Raw', ['14959-1', '9318-7'], None, 20000.0),
    ('Urine_Microalbumin', ['14957-5'], None, None),
    ('Urine_Creatinine', ['2161-8'], None, None),
]
BMI_LOINC = ['39156-5']
ATC_CLASSES = {'RAASi': ['C09A', 'C09C'], 'Statins': ['C10AA']}      # model card v1.3
ICD_HISTORY = {'History_HTN': ('I10', 'I15'), 'History_DM': ('E10', 'E14'),
               'Subgroup_DKD': ('E10', 'E14'), 'Subgroup_GN': ('N00', 'N08')}   # KRCP Table S1/S2
RRT_ICD_CANDIDATES = ['Z49', 'Z99.2', 'Z94.0', 'T86.1', 'N18.6']               # P4 sensitivity counts only
# Diagnosis NAMES instead of ICD-10 codes (the real extract): the History flags use the text patterns of the published pipeline
# (diagnosis_config of SNUH_CKD_DATAPREP.ipynb, applied to the lower-cased diagnosis text); RRT is counted by name.
TEXT_HISTORY = {'History_HTN': r'hypertension|high blood pressure', 'History_DM': r'diabetes|mellitus',
                'Subgroup_DKD': r'diabetic kidney|diabetic nephropathy|diabetes.*kidney|diabetes.*renal',
                'Subgroup_GN': r'glomerulonephritis|nephrotic|nephritic|iga nephropathy|lupus nephritis'}
RRT_TEXT = {'dialysis': r'dialysis', 'kidney transplant': r'(kidney|renal) transplant'}                      # P4 sensitivity counts only

# Concept ids used by the v205 cohort JSON (always kept in the site vocabulary subset).
V205_CONCEPTS = [46271022, 3016723, 4032243, 4146536, 4322471, 199991, 3000963, 3027484, 3023103, 3005456,
                 8753, 8713]

# ───────────────────────── raw extract layout ─────────────────────────
# Candidate column names (after the cp949 mojibake repair); the first one present is used.
# P1 (p1_schema.txt) shows the real names; override anything in maps/raw_layout.json.
DRUG_COLUMNS = ['RID', '처방일자', '약품코드', '일반성분명', '용량', '1회투여량', '1일투약횟수', '투약기간', '투약일수',
                'PRN처방여부']                                   # drug_dictionary.DRUG_COLUMNS (positional fallback)
RAW_LAYOUT = {
    'parquet_dir': 'Data/parquets',
    'xlsx_dir': 'Data/CSV',
    'basics': {'file': 'BASICS_Total.parquet', 'pid': ['연구별 환자 ID', 'RID'], 'visit_date': ['내원일자'],
               'sex': ['성별', 'Sex', 'SEX', '성별코드'], 'birth': ['생년월', '생년월일', '출생년월', 'Birth', '생년'],
               'visit_type': ['내원구분', '입원외래구분', '외래입원구분', '진료구분'],
               'height': ['키', '신장'], 'weight': ['몸무게', '체중'], 'bmi': ['BMI']},
    'lab': {'files': ['LAB-1.parquet', 'LAB-2.parquet'], 'pid': ['RID', '연구별 환자 ID'], 'date': ['검사시행일'],
            'test': ['검사명'], 'unit': ['검사결과단위'], 'value': ['검사결과']},
    'drug': {'file': 'DRUG_Total.parquet', 'pid': ['RID', '연구별 환자 ID'], 'date': ['처방일자'], 'code': ['약품코드'],
             'name': ['일반성분명'], 'days': ['투약일수'], 'prn': ['PRN처방여부']},
    'dx': {'file': '[CKD_AI]DIAGNOSIS_ICD10.xlsx', 'pid': ['연구별 환자 ID', 'RID'],
           'code': ['ICD10', 'ICD-10', 'ICD10코드', 'ICD10_CODE', '진단코드', '상병코드', 'KCD', 'KCD코드'],
           'date': ['진단일자', '진단일', '상병일자'],
           'pairs': None,           # list of [code column, date column] for a wide layout
           'sheet_codes': True,     # False: the sheet carries no diagnosis code column (the real extract: dates and English names only)
           'events': [],            # [[label, date column]]: one diagnosis event per patient and date under a constant label, e.g.
                                    # [["KIDNEYDS", "진단일자_KIDNEYDS"]] (the first kidney-disease diagnosis); the label is the source value
           'birth': ['생년월일', '생년월', '출생년월', 'Birth', '생년'],    # sheet columns of birth and sex; used for persons
           'sex': ['성별', 'Sex', 'SEX', '성별코드'],                      # whose BASICS rows carry no birth value (the real BASICS has none)
           'basics_name': [],       # BASICS columns of visit-level diagnosis names (real extract: 기타진단명); empty = not used
           'basics_date': ['내원일자']},   # the date of such a name (the visit date; maps/raw_layout.json can change it)
    'base_csv': 'ML/Base_file/SNUH_CKD_Analysis_Base.csv',
}


def _merge(a, b):
    out = copy.deepcopy(a)
    for k, v in b.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_layout(maps_dir=MAPS):
    p = os.path.join(maps_dir, 'raw_layout.json')
    return _merge(RAW_LAYOUT, json.load(open(p, encoding='utf-8'))) if os.path.exists(p) else copy.deepcopy(RAW_LAYOUT)


# ───────────────────────── small helpers ─────────────────────────
def require_irb(irb):
    if not re.fullmatch(IRB_RE, (irb or '').strip()):
        sys.exit("SNUH data not read: give this study's IRB exemption number, e.g. --irb E-2610-123-4567")
    return irb.strip()


def cdm_dir():
    return os.environ.get('PILOT_CDM_DIR', os.path.join(L.DATA_DIR, 'cdm'))


def out_dir():
    d = os.environ.get('PILOT_CDM_OUT', os.path.join(HERE, 'out'))
    os.makedirs(d, exist_ok=True)
    return d


def db_path(name, base=None):
    base = base or cdm_dir()
    if name == 'central':
        return os.path.join(base, '_central.duckdb')
    if name == HOLDOUT:
        return os.path.join(base, 'holdout.duckdb')
    return os.path.join(base, f'site_{name}.duckdb')


def fix(c):
    """Column names of the R/CP949-written parquets arrive as mojibake (same repair as CKD_ML code)."""
    try:
        return c.encode('latin1').decode('cp949')
    except Exception:
        return c


def q(c):
    return '"' + str(c).replace('"', '""') + '"'


def lit(s):
    return "'" + str(s).replace("'", "''") + "'"


def sqlpath(p):
    return lit(p.replace('\\', '/'))


def cell(n):
    return L.cell(int(n)) if n is not None and not (isinstance(n, float) and np.isnan(n)) else ''


def pct(a, b):
    return f'{100 * a / b:5.1f}%' if b else '   - '


def date_sql(expr):
    """Any of DATE / TIMESTAMP[TZ] / 'YYYY-MM-DD...' / 'YYYYMMDD' / 20150302 -> DATE (NULL if unparseable).
    TIMESTAMPTZ renders in the session time zone (set to Asia/Seoul by connect())."""
    return (f"TRY_STRPTIME(SUBSTR(REGEXP_REPLACE(CAST({expr} AS VARCHAR), '[^0-9]', '', 'g'), 1, 8), '%Y%m%d')::DATE")


def icd3_sql(expr):
    """ICD-10/KCD source code -> first three characters, upper case, punctuation removed ('i10.0' -> 'I10')."""
    return f"SUBSTR(UPPER(REGEXP_REPLACE(CAST({expr} AS VARCHAR), '[^A-Za-z0-9]', '', 'g')), 1, 3)"


def icd_norm_sql(expr):
    return f"UPPER(REGEXP_REPLACE(CAST({expr} AS VARCHAR), '[^A-Za-z0-9]', '', 'g'))"


def dx_layout(con):
    """'names' when P3 built this CDM from diagnosis names (CDM_SOURCE.source_description carries dx_layout=names), else 'icd'."""
    try:
        d = con.execute('SELECT source_description FROM cdm_source LIMIT 1').fetchone()
    except Exception:
        return 'icd'
    return 'names' if d and 'dx_layout=names' in str(d[0]) else 'icd'


def norm_icd(s):
    return re.sub(r'[^A-Za-z0-9]', '', str(s)).upper()


def connect(path=None, read_only=False):
    import duckdb
    con = duckdb.connect(path or ':memory:', read_only=read_only)
    con.execute(f'PRAGMA threads={L.N_THREADS}')
    try:
        con.execute("SET TimeZone='Asia/Seoul'")
    except Exception:
        pass
    return con


def parquet_cols(con, path):
    raw = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet({sqlpath(path)})").fetchall()]
    return {fix(c): c for c in raw}


class LayoutError(Exception):
    """Raw-extract layout problem. The message holds file and column names only (schema, no data), so the
    scripts print it even when pilot_lib.guard would suppress messages."""


def pick(cols, candidates, what, required=True):
    """cols: {fixed name: raw name}. Returns the raw name of the first candidate present."""
    for c in candidates:
        if c in cols:
            return cols[c]
    if required:
        raise LayoutError(f'{what}: none of {candidates} in columns {sorted(cols)} -- set it in maps/raw_layout.json')
    return None


def egfr_ckdepi2021(scr, age, male):
    """CKD-EPI 2021 (race-free); male = 1/0 (0 and unknown -> female, as in the published code)."""
    scr = np.asarray(scr, float)
    fem = np.asarray(male) != 1
    k = np.where(fem, 0.7, 0.9)
    a = np.where(fem, -0.241, -0.302)
    f = np.where(fem, 1.012, 1.0)
    s = scr / k
    return 142 * np.minimum(s, 1) ** a * np.maximum(s, 1) ** -1.2 * 0.9938 ** np.asarray(age, float) * f


# ───────────────────────── CDM v5.3 DDL (subset) ─────────────────────────
CDM_TABLES = {
    'person': """person_id BIGINT NOT NULL, gender_concept_id INTEGER NOT NULL, year_of_birth INTEGER NOT NULL,
        month_of_birth INTEGER, day_of_birth INTEGER, birth_datetime TIMESTAMP, race_concept_id INTEGER NOT NULL,
        ethnicity_concept_id INTEGER NOT NULL, location_id BIGINT, provider_id BIGINT, care_site_id BIGINT,
        person_source_value VARCHAR, gender_source_value VARCHAR, gender_source_concept_id INTEGER,
        race_source_value VARCHAR, race_source_concept_id INTEGER, ethnicity_source_value VARCHAR,
        ethnicity_source_concept_id INTEGER""",
    'observation_period': """observation_period_id BIGINT NOT NULL, person_id BIGINT NOT NULL,
        observation_period_start_date DATE NOT NULL, observation_period_end_date DATE NOT NULL,
        period_type_concept_id INTEGER NOT NULL""",
    'visit_occurrence': """visit_occurrence_id BIGINT NOT NULL, person_id BIGINT NOT NULL, visit_concept_id INTEGER NOT NULL,
        visit_start_date DATE NOT NULL, visit_start_datetime TIMESTAMP, visit_end_date DATE NOT NULL,
        visit_end_datetime TIMESTAMP, visit_type_concept_id INTEGER NOT NULL, provider_id BIGINT, care_site_id BIGINT,
        visit_source_value VARCHAR, visit_source_concept_id INTEGER, admitting_source_concept_id INTEGER,
        admitting_source_value VARCHAR, discharge_to_concept_id INTEGER, discharge_to_source_value VARCHAR,
        preceding_visit_occurrence_id BIGINT""",
    'condition_occurrence': """condition_occurrence_id BIGINT NOT NULL, person_id BIGINT NOT NULL,
        condition_concept_id INTEGER NOT NULL, condition_start_date DATE NOT NULL, condition_start_datetime TIMESTAMP,
        condition_end_date DATE, condition_end_datetime TIMESTAMP, condition_type_concept_id INTEGER NOT NULL,
        stop_reason VARCHAR, provider_id BIGINT, visit_occurrence_id BIGINT, visit_detail_id BIGINT,
        condition_source_value VARCHAR, condition_source_concept_id INTEGER, condition_status_source_value VARCHAR,
        condition_status_concept_id INTEGER""",
    'procedure_occurrence': """procedure_occurrence_id BIGINT NOT NULL, person_id BIGINT NOT NULL,
        procedure_concept_id INTEGER NOT NULL, procedure_date DATE NOT NULL, procedure_datetime TIMESTAMP,
        procedure_type_concept_id INTEGER NOT NULL, modifier_concept_id INTEGER, quantity INTEGER, provider_id BIGINT,
        visit_occurrence_id BIGINT, visit_detail_id BIGINT, procedure_source_value VARCHAR,
        procedure_source_concept_id INTEGER, modifier_source_value VARCHAR""",
    'measurement': """measurement_id BIGINT NOT NULL, person_id BIGINT NOT NULL, measurement_concept_id INTEGER NOT NULL,
        measurement_date DATE NOT NULL, measurement_datetime TIMESTAMP, measurement_time VARCHAR,
        measurement_type_concept_id INTEGER NOT NULL, operator_concept_id INTEGER, value_as_number DOUBLE,
        value_as_concept_id INTEGER, unit_concept_id INTEGER, range_low DOUBLE, range_high DOUBLE, provider_id BIGINT,
        visit_occurrence_id BIGINT, visit_detail_id BIGINT, measurement_source_value VARCHAR,
        measurement_source_concept_id INTEGER, unit_source_value VARCHAR, value_source_value VARCHAR""",
    'drug_exposure': """drug_exposure_id BIGINT NOT NULL, person_id BIGINT NOT NULL, drug_concept_id INTEGER NOT NULL,
        drug_exposure_start_date DATE NOT NULL, drug_exposure_start_datetime TIMESTAMP,
        drug_exposure_end_date DATE NOT NULL, drug_exposure_end_datetime TIMESTAMP, verbatim_end_date DATE,
        drug_type_concept_id INTEGER NOT NULL, stop_reason VARCHAR, refills INTEGER, quantity DOUBLE,
        days_supply INTEGER, sig VARCHAR, route_concept_id INTEGER, lot_number VARCHAR, provider_id BIGINT,
        visit_occurrence_id BIGINT, visit_detail_id BIGINT, drug_source_value VARCHAR, drug_source_concept_id INTEGER,
        route_source_value VARCHAR, dose_unit_source_value VARCHAR""",
    'concept': """concept_id INTEGER NOT NULL, concept_name VARCHAR, domain_id VARCHAR, vocabulary_id VARCHAR,
        concept_class_id VARCHAR, standard_concept VARCHAR, concept_code VARCHAR, valid_start_date DATE,
        valid_end_date DATE, invalid_reason VARCHAR""",
    'concept_ancestor': """ancestor_concept_id INTEGER NOT NULL, descendant_concept_id INTEGER NOT NULL,
        min_levels_of_separation INTEGER, max_levels_of_separation INTEGER""",
    'concept_relationship': """concept_id_1 INTEGER NOT NULL, concept_id_2 INTEGER NOT NULL, relationship_id VARCHAR,
        valid_start_date DATE, valid_end_date DATE, invalid_reason VARCHAR""",
    'cdm_source': """cdm_source_name VARCHAR, cdm_source_abbreviation VARCHAR, cdm_holder VARCHAR,
        source_description VARCHAR, source_documentation_reference VARCHAR, cdm_etl_reference VARCHAR,
        source_release_date DATE, cdm_release_date DATE, cdm_version VARCHAR, vocabulary_version VARCHAR""",
}
CLINICAL = ['person', 'observation_period', 'visit_occurrence', 'condition_occurrence', 'procedure_occurrence',
            'measurement', 'drug_exposure']
EVENT_ID = {'observation_period': 'observation_period_id', 'visit_occurrence': 'visit_occurrence_id',
            'condition_occurrence': 'condition_occurrence_id', 'procedure_occurrence': 'procedure_occurrence_id',
            'measurement': 'measurement_id', 'drug_exposure': 'drug_exposure_id'}
CONCEPT_COL = {'condition_occurrence': 'condition_concept_id', 'procedure_occurrence': 'procedure_concept_id',
               'measurement': 'measurement_concept_id', 'drug_exposure': 'drug_concept_id',
               'visit_occurrence': 'visit_concept_id'}


def create_cdm(con, schema=''):
    s = f'{schema}.' if schema else ''
    for t, cols in CDM_TABLES.items():
        con.execute(f'CREATE TABLE IF NOT EXISTS {s}{t} ({cols})')


# ───────────────────────── vocabulary ─────────────────────────
VOCAB_FILES = {'concept': 'CONCEPT.csv', 'concept_ancestor': 'CONCEPT_ANCESTOR.csv',
               'concept_relationship': 'CONCEPT_RELATIONSHIP.csv'}


def vocab_file(vdir, table):
    for name in (VOCAB_FILES[table], VOCAB_FILES[table].lower()):
        p = os.path.join(vdir, name)
        if os.path.exists(p):
            return p
    return None


def read_vocab_sql(path, columns):
    """SELECT over an Athena (tab, unquoted, YYYYMMDD) or OHDSI-sample (comma, quoted, ISO date) vocab file."""
    with open(path, encoding='utf-8', errors='replace') as f:
        header = f.readline()
    if '\t' in header:
        src = f"read_csv({sqlpath(path)}, delim='\t', header=true, quote='', escape='', all_varchar=true)"
    else:
        src = f"read_csv({sqlpath(path)}, header=true, all_varchar=true)"
    out = []
    for c, typ in columns:
        if typ == 'INTEGER':
            out.append(f'TRY_CAST({c} AS INTEGER) AS {c}')
        elif typ == 'DATE':
            out.append(f'{date_sql(c)} AS {c}')
        else:
            out.append(f"NULLIF({c}, '') AS {c}")
    return f"SELECT {', '.join(out)} FROM {src}"


CONCEPT_COLS = [('concept_id', 'INTEGER'), ('concept_name', 'VARCHAR'), ('domain_id', 'VARCHAR'),
                ('vocabulary_id', 'VARCHAR'), ('concept_class_id', 'VARCHAR'), ('standard_concept', 'VARCHAR'),
                ('concept_code', 'VARCHAR'), ('valid_start_date', 'DATE'), ('valid_end_date', 'DATE'),
                ('invalid_reason', 'VARCHAR')]
ANCESTOR_COLS = [('ancestor_concept_id', 'INTEGER'), ('descendant_concept_id', 'INTEGER'),
                 ('min_levels_of_separation', 'INTEGER'), ('max_levels_of_separation', 'INTEGER')]
REL_COLS = [('concept_id_1', 'INTEGER'), ('concept_id_2', 'INTEGER'), ('relationship_id', 'VARCHAR'),
            ('valid_start_date', 'DATE'), ('valid_end_date', 'DATE'), ('invalid_reason', 'VARCHAR')]


def write_text(path, lines):
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
