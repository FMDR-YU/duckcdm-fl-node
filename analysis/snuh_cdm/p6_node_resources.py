# -*- coding: utf-8 -*-
"""P6 -- resource footprint of one institutional node (one OMOP CDM DuckDB file + duckcdm), for Table 1 of the ACI paper.

For each site DuckDB: file size, rows per CDM table and in the vocabulary subset, wall time of the duckcdm-compiled v205
cohort (circe-be + SqlRender in Python, executed into a temp table, the database is not modified), and the process peak
working set. With --achilles the Achilles characterization (duckcdm.achilles, 110 analyses) is timed on the copies prepared
for `duckcdm serve` (default <cdm-dir>/atlas; those copies hold the vocabulary tables Achilles needs and their results
schema is rebuilt by the run). The report holds counts and timings only; counts below 11 are shown as '<11'.

    python p6_node_resources.py --irb E-XXXX-XXX-XXXX [--dbs B1_0 ... holdout central] [--achilles] [--out FILE]
"""
import argparse
import ctypes
import os
import platform
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdm_lib as C  # noqa: E402
import pilot_lib as L  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_DEFAULT = os.path.join(os.path.dirname(HERE), 'cohort', 'Cohort_OHDSI_CKD_v205.json')
CDM_TABLES = ['person', 'observation_period', 'visit_occurrence', 'condition_occurrence', 'procedure_occurrence',
              'measurement', 'drug_exposure']
VOCAB_TABLES = ['concept', 'concept_ancestor', 'concept_relationship']
COHORT_ID = 205
MEMORY_LIMIT = '8GB'


def peak_working_set_mb():
    """Peak working set of this process (Windows: GetProcessMemoryInfo; elsewhere: resource.ru_maxrss)."""
    if os.name == 'nt':
        class PMC(ctypes.Structure):
            _fields_ = [('cb', ctypes.c_uint32), ('PageFaultCount', ctypes.c_uint32), ('PeakWorkingSetSize', ctypes.c_size_t),
                        ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t),
                        ('PeakPagefileUsage', ctypes.c_size_t)]
        import ctypes.wintypes as W
        k = ctypes.windll.kernel32
        f = k.K32GetProcessMemoryInfo
        f.argtypes, f.restype = [W.HANDLE, ctypes.POINTER(PMC), W.DWORD], W.BOOL
        k.GetCurrentProcess.restype = W.HANDLE
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        if f(k.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return pmc.PeakWorkingSetSize / 2 ** 20
        return float('nan')
    import resource
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 2 ** 20 if sys.platform == 'darwin' else r / 2 ** 10


def machine():
    cpu, ram = platform.processor(), ''
    if os.name == 'nt':
        try:
            import subprocess
            q = subprocess.run(['powershell', '-NoProfile', '-Command',
                                '(Get-CimInstance Win32_Processor).Name; [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)'],
                               capture_output=True, text=True, timeout=60)
            parts = [s.strip() for s in q.stdout.splitlines() if s.strip()]
            if len(parts) >= 2:
                cpu, ram = parts[0], parts[1] + ' GB'
        except Exception:
            pass
    return cpu, ram


def duckcdm_sql(json_text):
    from duckcdm.circe import build_cohort_query
    from duckcdm.sqlrender import render, translate
    sql = build_cohort_query(json_text, cohort_id=COHORT_ID, cdm_schema='main', vocabulary_schema='main',
                             target_table='cohort_p6', result_schema='main', generate_stats=False)
    return translate(render(sql), 'duckdb')


def statements(sql):
    body = '\n'.join(ln for ln in sql.splitlines() if not ln.strip().startswith('--'))
    return [s.strip() for s in body.split(';') if s.strip()]


def table_rows(con, table):
    try:
        return con.execute(f'SELECT count(*) FROM main."{table}"').fetchone()[0]
    except Exception:
        return None


def measure_db(path, json_text):
    r = {'size_mb': os.path.getsize(path) / 2 ** 20}
    con = C.connect(path, read_only=True)
    try:
        con.execute(f"SET memory_limit='{MEMORY_LIMIT}'")
        for t in CDM_TABLES + VOCAB_TABLES:
            r[t] = table_rows(con, t)
        t0 = time.time()
        sql = duckcdm_sql(json_text)
        r['t_compile_s'] = time.time() - t0
        con.execute('CREATE TEMP TABLE cohort_p6 (cohort_definition_id INTEGER, subject_id BIGINT, cohort_start_date DATE, cohort_end_date DATE)')
        t0 = time.time()
        for stmt in statements(sql):
            con.execute(stmt)
        r['t_cohort_s'] = time.time() - t0
        r['cohort_persons'] = con.execute('SELECT count(DISTINCT subject_id) FROM cohort_p6').fetchone()[0]
    finally:
        con.close()
    r['peak_mb'] = peak_working_set_mb()
    return r


def measure_achilles(path):
    from duckcdm.achilles import run_achilles
    con = C.connect(path)
    try:
        con.execute(f"SET memory_limit='{MEMORY_LIMIT}'")
        con.execute('DROP SCHEMA IF EXISTS results CASCADE')
        t0 = time.time()
        ret = run_achilles(con, cdm_schema='main', results_schema='results', vocab_schema='main', source_name=os.path.basename(path),
                           cdm_version='5.3', small_cell_count=L.MIN_CELL - 1, log=lambda *a: None)
        t = time.time() - t0
        done, failed = ret if isinstance(ret, tuple) else (None, ret)   # duckcdm 0.4.7 returns (done, failed)
        n = len(done) if done is not None else con.execute('SELECT count(DISTINCT analysis_id) FROM results.achilles_results').fetchone()[0]
    finally:
        con.close()
    return {'t_achilles_s': t, 'analyses': n, 'failed': len(failed), 'peak_mb': peak_working_set_mb()}


def fmt_count(n):
    if n is None:
        return '-'
    return '0' if n == 0 else L.cell(int(n))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--irb', required=True)
    ap.add_argument('--dbs', nargs='+', default=C.DBS, help='site names (B1_0 .. holdout, central); default: the six sites and holdout')
    ap.add_argument('--json', default=JSON_DEFAULT)
    ap.add_argument('--cdm-dir', default=None)
    ap.add_argument('--achilles', action='store_true', help='also time Achilles on the duckcdm-serve copies in --achilles-dir')
    ap.add_argument('--achilles-dir', default=None, help='default <cdm-dir>/atlas')
    ap.add_argument('--out', default=None, help='report file (default out/p6_node_resources.txt)')
    a = ap.parse_args()
    C.require_irb(a.irb)
    import duckcdm
    import duckdb
    cdm_dir = a.cdm_dir or C.cdm_dir()
    json_text = open(a.json, encoding='utf-8').read()
    cpu, ram = machine()
    lines = ['p6_node_resources: footprint of one CDM node (DuckDB file + duckcdm)',
             f'machine: {cpu}; RAM {ram}; {platform.platform()}',
             f'python {platform.python_version()}, duckdb {duckdb.__version__}, duckcdm {getattr(duckcdm, "__version__", "?")}; '
             f'PRAGMA threads={L.N_THREADS}, memory_limit={MEMORY_LIMIT}',
             f'cohort: {os.path.basename(a.json)} compiled by duckcdm.circe, executed into a temp table (databases not modified)',
             'peak_mb = peak working set of this process so far (cumulative over the databases in run order)', '']
    hdr = '%-9s %8s %10s %10s %12s %12s %12s %12s %12s %10s %10s %8s %8s %8s %8s' % (
        'db', 'size_MB', 'person', 'obs_period', 'visit', 'condition', 'procedure', 'measurement', 'drug', 'concept',
        'ancestor', 'cohort', 'compile_s', 'cohort_s', 'peak_MB')
    lines.append(hdr)
    print('\n'.join(lines))
    for name in a.dbs:
        path = C.db_path(name, cdm_dir)
        if not os.path.exists(path):
            row = '%-9s missing' % name
            lines.append(row); print(row); continue
        r = measure_db(path, json_text)
        row = '%-9s %8.0f %10s %10s %12s %12s %12s %12s %12s %10s %10s %8s %8.2f %8.2f %8.0f' % (
            name, r['size_mb'], fmt_count(r['person']), fmt_count(r['observation_period']), fmt_count(r['visit_occurrence']),
            fmt_count(r['condition_occurrence']), fmt_count(r['procedure_occurrence']), fmt_count(r['measurement']),
            fmt_count(r['drug_exposure']), fmt_count(r['concept']), fmt_count(r['concept_ancestor']), fmt_count(r['cohort_persons']),
            r['t_compile_s'], r['t_cohort_s'], r['peak_mb'])
        lines.append(row); print(row)
    if a.achilles:
        adir = a.achilles_dir or os.path.join(cdm_dir, 'atlas')
        dbs = sorted(f for f in os.listdir(adir) if f.startswith('site_') and f.endswith('.duckdb')) if os.path.isdir(adir) else []
        lines += ['', f'Achilles (duckcdm.achilles, small-cell {L.MIN_CELL - 1}, results schema rebuilt) on the serve copies in {os.path.relpath(adir, L.BASE)}:',
                  '%-16s %10s %8s %12s %8s' % ('db', 'analyses', 'failed', 'achilles_s', 'peak_MB')]
        print('\n'.join(lines[-3:]))
        for f in dbs:
            r = measure_achilles(os.path.join(adir, f))
            row = '%-16s %10d %8d %12.1f %8.0f' % (f.replace('.duckdb', ''), r['analyses'], r['failed'], r['t_achilles_s'], r['peak_mb'])
            lines.append(row); print(row)
        if not dbs:
            lines.append('(no serve copies found)'); print(lines[-1])
    out = a.out or os.path.join(C.out_dir(), 'p6_node_resources.txt')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    print('wrote', out)


if __name__ == '__main__':
    main()
