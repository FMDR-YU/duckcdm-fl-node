# -*- coding: utf-8 -*-
"""Headless node demo on a public OMOP CDM (no ATLAS screen, no database server, no Java): the use case of the manuscript's
Additional file 7. Everything is a Python call or a file, so a script or an agent can drive it.

    python node_demo.py [--cdm-dir data/cdm/Synthea27Nj] [--out out]

Steps (each prints one line of aggregates; counts below 11 are shown as '<11'):
  1. node   : load the CDM CSV files (OMOP CDM 5.4 export of Synthea27Nj, OHDSI's public test set) into one DuckDB file
  2. cohort : compile two ATLAS cohort definitions with duckcdm (circe-be port), translate to DuckDB SQL (SqlRender port), run them
             a) the institutional CKD definition of the study (v205) as exported from ATLAS
             b) a generated one-concept definition (most frequent condition of the data) so that the demo has a non-empty cohort
  3. achilles: the 110 Achilles analyses, results schema in the same file
  4. serve  : how to open the ATLAS 3.0 interface on the file (command printed, not run)
  5. next   : the commands that continue to the federated and export-audit steps on the public SynPUF benchmark
The run writes out/node_demo_log.md (aggregates only) and out/demo_cohort.json (the generated definition).
"""
import argparse
import copy
import json
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
V205 = os.path.join(BASE, 'analysis', 'cohort', 'Cohort_OHDSI_CKD_v205.json')
MIN_CELL = 11


def cell(n):
    return f'{int(n):,}' if n >= MIN_CELL else '<11'


def log(lines, s):
    print(s)
    lines.append(s)


def load_cdm(con, cdm_dir, cdm_version):
    """Every CSV of the folder becomes a table of the same (lower-case) name. Columns known to the CDM specification get the
    specification's type (duckcdm.omop.cdm_fields), so that an empty CSV does not become an all-VARCHAR table; other columns
    are typed by DuckDB's sniffer."""
    from duckcdm.omop import cdm_fields
    spec = {t: dict(cols) for t, cols in cdm_fields((cdm_version,)).items()}
    n = 0
    for f in sorted(os.listdir(cdm_dir)):
        if not f.lower().endswith('.csv'):
            continue
        t = os.path.splitext(f)[0].lower()
        p = os.path.join(cdm_dir, f).replace('\\', '/').replace("'", "''")
        types = spec.get(t, {})
        tdict = ', '.join(f"'{c}': '{typ}'" for c, typ in types.items())
        opts = f', types={{{tdict}}}' if types else ''
        con.execute(f'CREATE OR REPLACE TABLE main."{t}" AS SELECT * FROM read_csv(\'{p}\', header=true, sample_size=-1{opts})')
        n += 1
    return n


def demo_definition(con):
    """A one-concept cohort (most frequent condition by persons): first occurrence, 0 days prior observation, end = start + 30 d."""
    cid, name = con.execute("""SELECT co.condition_concept_id, c.concept_name FROM main.condition_occurrence co
                               JOIN main.concept c ON c.concept_id = co.condition_concept_id
                               WHERE co.condition_concept_id <> 0 GROUP BY 1, 2 ORDER BY count(DISTINCT co.person_id) DESC, 1 LIMIT 1""").fetchone()
    d = copy.deepcopy(json.load(open(V205, encoding='utf-8')))
    d['ConceptSets'] = [{'id': 0, 'name': name, 'expression': {'items': [{'concept': {'CONCEPT_ID': int(cid), 'CONCEPT_NAME': name},
                                                                             'isExcluded': False, 'includeDescendants': True, 'includeMapped': False}]}}]
    d['PrimaryCriteria'] = {'CriteriaList': [{'ConditionOccurrence': {'CodesetId': 0}}], 'ObservationWindow': {'PriorDays': 0, 'PostDays': 0},
                            'PrimaryCriteriaLimit': {'Type': 'First'}}
    d['QualifiedLimit'] = {'Type': 'First'}
    d['ExpressionLimit'] = {'Type': 'First'}
    d['InclusionRules'] = []
    d['EndStrategy'] = {'DateOffset': {'DateField': 'StartDate', 'Offset': 30}}
    return d, name


def run_cohort(con, json_text, cohort_id, table):
    from duckcdm.circe import build_cohort_query
    from duckcdm.sqlrender import render, translate
    t0 = time.time()
    sql = build_cohort_query(json_text, cohort_id=cohort_id, cdm_schema='main', vocabulary_schema='main', target_table=table,
                             result_schema='main', generate_stats=False)
    sql = translate(render(sql), 'duckdb')
    t_compile = time.time() - t0
    con.execute(f'CREATE OR REPLACE TABLE main."{table}" (cohort_definition_id INTEGER, subject_id BIGINT, cohort_start_date DATE, cohort_end_date DATE)')
    body = '\n'.join(ln for ln in sql.splitlines() if not ln.strip().startswith('--'))
    t0 = time.time()
    for stmt in [s.strip() for s in body.split(';') if s.strip()]:
        con.execute(stmt)
    t_run = time.time() - t0
    n = con.execute(f'SELECT count(DISTINCT subject_id) FROM main."{table}"').fetchone()[0]
    return n, t_compile, t_run, len(sql)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cdm-dir', default=os.path.join(BASE, 'data', 'cdm', 'Synthea27Nj'))
    ap.add_argument('--out', default=os.path.join(HERE, 'out'))
    ap.add_argument('--cdm-version', default='5.4')
    a = ap.parse_args()
    import duckcdm
    import duckdb
    os.makedirs(a.out, exist_ok=True)
    db = os.path.join(a.out, 'node_demo.duckdb')
    if os.path.exists(db):
        os.remove(db)
    L = [f'# Headless node demo on a public OMOP CDM ({os.path.basename(a.cdm_dir)}, CDM {a.cdm_version})', '',
         f'python {platform.python_version()}, duckdb {duckdb.__version__}, duckcdm {getattr(duckcdm, "__version__", "?")}; {platform.platform()}', '']
    con = duckdb.connect(db)
    con.execute('PRAGMA threads=4')
    t0 = time.time()
    n_tables = load_cdm(con, a.cdm_dir, a.cdm_version)
    persons = con.execute('SELECT count(*) FROM main.person').fetchone()[0]
    rows = {t: con.execute(f'SELECT count(*) FROM main."{t}"').fetchone()[0] for t in ('condition_occurrence', 'drug_exposure', 'measurement', 'concept')}
    log(L, f'1. node: {n_tables} tables loaded into {os.path.basename(db)} in {time.time() - t0:.1f} s; persons {cell(persons)}; rows condition {rows["condition_occurrence"]:,}, '
           f'drug {rows["drug_exposure"]:,}, measurement {rows["measurement"]:,}, concept {rows["concept"]:,}; file {os.path.getsize(db) / 2 ** 20:.1f} MB')

    n, tc, tr, nchar = run_cohort(con, open(V205, encoding='utf-8').read(), 205, 'cohort_v205')
    log(L, f'2a. cohort v205 (institutional CKD definition, ATLAS export): compiled by duckcdm.circe in {tc:.2f} s ({nchar:,} characters of DuckDB SQL), run in {tr:.2f} s, persons {cell(n) if n else "0"}')
    d, name = demo_definition(con)
    jp = os.path.join(a.out, 'demo_cohort.json')
    json.dump(d, open(jp, 'w', encoding='utf-8'), indent=1)
    n, tc, tr, nchar = run_cohort(con, json.dumps(d), 1, 'cohort_demo')
    log(L, f'2b. cohort demo (first occurrence of "{name}", generated definition {os.path.basename(jp)}): compiled in {tc:.2f} s, run in {tr:.2f} s, persons {cell(n)}')

    from duckcdm.achilles import run_achilles
    t0 = time.time()
    ret = run_achilles(con, cdm_schema='main', results_schema='results', vocab_schema='main', source_name='node_demo', cdm_version=a.cdm_version,
                       small_cell_count=MIN_CELL - 1, log=lambda *x: None)
    done, failed = ret if isinstance(ret, tuple) else (None, ret)
    log(L, f'3. achilles: {len(done) if done is not None else "?"} analyses, {len(failed)} failed, {time.time() - t0:.1f} s, small-cell {MIN_CELL - 1}'
           + (f'; failed ids {[i for i, _ in failed]}' if failed else ''))
    con.close()
    log(L, f'4. serve (not run here): duckcdm serve "{db}"  then open http://127.0.0.1:8000/atlas/ in a browser; the same file answers the WebAPI calls')
    log(L, '5. next (public SynPUF benchmark, existing commands): federated = central: analysis/federated/run_batch.ps1 -Dataset synpuf -Seeds 42 -Configs plain,krcp -Reexec; '
           'export audit and canary benchmark: analysis/snuh_pilot/run_pilot.py --dataset synpuf --model xgb, analysis/run_canary.ps1 -Dataset synpuf -Quick')
    with open(os.path.join(a.out, 'node_demo_log.md'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(L) + '\n')
    print('wrote', os.path.join(a.out, 'node_demo_log.md'))


if __name__ == '__main__':
    main()
