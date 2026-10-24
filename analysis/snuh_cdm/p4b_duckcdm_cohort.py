# -*- coding: utf-8 -*-
"""P4b -- cross-check of the v205 cohort: duckcdm (pure-Python circe-be + SqlRender, vitaldb/duckcdm) against the hand
translation sql/v205_cohort_duckdb.sql, on every site DuckDB.

For each DuckDB the cohort JSON (analysis/cohort/Cohort_OHDSI_CKD_v205.json) is compiled by duckcdm.circe, rendered and
translated to the DuckDB dialect by duckcdm.sqlrender, and executed; the hand SQL is executed in the same connection.
Both results are temp tables (the site database is not modified) and are compared person by person. The report holds
counts only (cells below 11 are shown as '<11').

    python p4b_duckcdm_cohort.py --irb E-XXXX-XXX-XXXX [--dbs B1_0 ... holdout central] [--out FILE]
"""
import argparse
import hashlib
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdm_lib as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_DEFAULT = os.path.join(os.path.dirname(HERE), 'cohort', 'Cohort_OHDSI_CKD_v205.json')
HAND_SQL = os.path.join(C.SQL_DIR, 'v205_cohort_duckdb.sql')
COHORT_ID = 205


def md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def statements(sql):
    """Drop comment-only lines first (a comment may contain ';'), then split on ';'."""
    body = '\n'.join(ln for ln in sql.splitlines() if not ln.strip().startswith('--'))
    return [s.strip() for s in body.split(';') if s.strip()]


def duckcdm_sql(json_text):
    from duckcdm.circe import build_cohort_query
    from duckcdm.sqlrender import render, translate
    sql = build_cohort_query(json_text, cohort_id=COHORT_ID, cdm_schema='main', vocabulary_schema='main',
                             target_table='cohort_duckcdm', result_schema='main', generate_stats=False)
    return translate(render(sql), 'duckdb')


def hand_sql_as_temp(text):
    """The hand SQL writes tables cohort / cohort_inclusion; run it into temp tables cohort_v205 / cohort_inclusion_v205."""
    text = re.sub(r'\bcohort_inclusion\b', 'cohort_inclusion_v205', text)
    text = re.sub(r'\bcohort\b', 'cohort_v205', text)
    return text.replace('CREATE OR REPLACE TABLE cohort_v205', 'CREATE OR REPLACE TEMP TABLE cohort_v205') \
               .replace('CREATE OR REPLACE TABLE cohort_inclusion_v205', 'CREATE OR REPLACE TEMP TABLE cohort_inclusion_v205')


def run(con, sql):
    t0 = time.time()
    n = 0
    for stmt in statements(sql):
        con.execute(stmt)
        n += 1
    return n, time.time() - t0


def compare(con):
    one = lambda q: con.execute(q).fetchone()[0]  # noqa: E731
    r = {}
    r['n_duckcdm'] = one('SELECT count(*) FROM cohort_duckcdm')
    r['persons_duckcdm'] = one('SELECT count(DISTINCT subject_id) FROM cohort_duckcdm')
    r['n_hand'] = one('SELECT count(*) FROM cohort_v205')
    r['persons_hand'] = one('SELECT count(DISTINCT subject_id) FROM cohort_v205')
    r['persons_both'] = one('SELECT count(*) FROM (SELECT subject_id FROM cohort_duckcdm INTERSECT SELECT subject_id FROM cohort_v205)')
    r['persons_duckcdm_only'] = one('SELECT count(*) FROM (SELECT subject_id FROM cohort_duckcdm EXCEPT SELECT subject_id FROM cohort_v205)')
    r['persons_hand_only'] = one('SELECT count(*) FROM (SELECT subject_id FROM cohort_v205 EXCEPT SELECT subject_id FROM cohort_duckcdm)')
    r['rows_same_start'] = one("""SELECT count(*) FROM cohort_duckcdm d JOIN cohort_v205 h
                                  ON h.subject_id = d.subject_id AND h.cohort_start_date = d.cohort_start_date""")
    r['rows_same_start_and_end'] = one("""SELECT count(*) FROM cohort_duckcdm d JOIN cohort_v205 h
                                  ON h.subject_id = d.subject_id AND h.cohort_start_date = d.cohort_start_date
                                  AND h.cohort_end_date = d.cohort_end_date""")
    r['persons_both_start_differs'] = one("""SELECT count(*) FROM (SELECT subject_id FROM cohort_duckcdm INTERSECT SELECT subject_id FROM cohort_v205) b
                                  WHERE NOT EXISTS (SELECT 1 FROM cohort_duckcdm d JOIN cohort_v205 h
                                        ON h.subject_id = d.subject_id AND h.cohort_start_date = d.cohort_start_date WHERE d.subject_id = b.subject_id)""")
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--irb', required=True)
    ap.add_argument('--dbs', nargs='+', default=C.DBS, help='site names (B1_0 .. holdout, central); default: the six sites and holdout')
    ap.add_argument('--json', default=JSON_DEFAULT)
    ap.add_argument('--cdm-dir', default=None)
    ap.add_argument('--out', default=None, help='report file (default out/p4b_duckcdm_cohort.txt)')
    ap.add_argument('--hand-sql', default=HAND_SQL, help='hand-written DuckDB cohort SQL to compare with (default sql/v205_cohort_duckdb.sql)')
    ap.add_argument('--label', default='v205', help='label of the definition in the report')
    a = ap.parse_args()
    C.require_irb(a.irb)
    import duckcdm
    json_text = open(a.json, encoding='utf-8').read()
    d_sql = duckcdm_sql(json_text)
    h_sql = hand_sql_as_temp(open(a.hand_sql, encoding='utf-8').read())
    lines = ['p4b_duckcdm_cohort: %s by duckcdm vs the hand DuckDB translation' % a.label,
             'duckcdm %s, cohort json %s (md5 %s), hand sql md5 %s' % (getattr(duckcdm, '__version__', '?'), os.path.basename(a.json),
                                                                      md5(a.json), md5(a.hand_sql)),
             'duckcdm SQL: %d statements, %d chars (md5 %s)' % (len(statements(d_sql)), len(d_sql), hashlib.md5(d_sql.encode()).hexdigest()),
             'both results are temp tables; the site databases are not modified', '']
    print('\n'.join(lines))
    hdr = '%-9s %8s %8s %8s %8s %8s %8s %8s %10s %8s %8s' % ('db', 'duckcdm', 'hand', 'both', 'dc_only', 'hd_only', 'sameSt', 'sameEnd',
                                                           'both_dif', 't_dc_s', 't_hd_s')
    lines.append(hdr)
    print(hdr)
    for name in a.dbs:
        path = C.db_path(name, a.cdm_dir)
        if not os.path.exists(path):
            row = '%-9s missing' % name
            lines.append(row); print(row); continue
        con = C.connect(path)
        try:
            con.execute('CREATE TEMP TABLE cohort_duckcdm (cohort_definition_id INTEGER, subject_id BIGINT, cohort_start_date DATE, cohort_end_date DATE)')
            n1, t1 = run(con, d_sql)
            n2, t2 = run(con, h_sql)
            r = compare(con)
        finally:
            con.close()
        c = lambda n: '0' if n == 0 else C.cell(n)  # noqa: E731  (0 persons is a statement about the two queries, not about patients)
        row = '%-9s %8s %8s %8s %8s %8s %8s %8s %10s %8.1f %8.1f' % (
            name, c(r['persons_duckcdm']), c(r['persons_hand']), c(r['persons_both']), c(r['persons_duckcdm_only']), c(r['persons_hand_only']),
            c(r['rows_same_start']), c(r['rows_same_start_and_end']), c(r['persons_both_start_differs']), t1, t2)
        if r['n_duckcdm'] != r['persons_duckcdm'] or r['n_hand'] != r['persons_hand']:
            row += '   rows != persons (duckcdm %s, hand %s)' % (c(r['n_duckcdm']), c(r['n_hand']))
        lines.append(row)
        print(row, flush=True)
    lines += ['', 'columns: distinct persons in each cohort; both / only-in-one; rows with the same start date (and the same end date);',
              'persons in both whose start date differs; seconds per engine. Counts from 1 to 10 are shown as <11; 0 is shown as 0.']
    out = a.out or os.path.join(C.out_dir(), 'p4b_duckcdm_cohort.txt')
    C.write_text(out, lines)
    print('report:', out)


if __name__ == '__main__':
    main()
