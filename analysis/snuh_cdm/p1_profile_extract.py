# -*- coding: utf-8 -*-
"""P1 -- profile the SNUH CKD CDW extract for the OMOP CDM mapping (aggregates only).

Reads the extract in place with DuckDB (parquets: CKD_ML PROJECT\\Data\\parquets; the diagnosis and RID xlsx: the raw-extract
folder, see pilot_lib.raw_xlsx_dir), so the 11 GB lab file is aggregated without loading it into memory. Writes to analysis/snuh_cdm/out/:
  p1_schema.txt          per table: rows, patients, columns (fixed names), distinct count, null %,
                         date range as year-month
  p1_catalog_lab.csv     test name x unit: rows, patients, numeric-parse rate, p05/p50/p95
  p1_catalog_dx.csv      ICD-10 code (+ name column if present): rows, patients; or, when the DIAGNOSIS sheet has no ICD-10
                         column (the real extract: dates + English diagnosis names), the diagnosis-name catalog of the sheet
                         and of BASICS, names with >= 11 patients only
  p1_catalog_drug.csv    drug code + ingredient name: rows, patients
In p1_schema.txt, for that name-only layout: share of names that carry an ICD-10-like token, rows and distinct KIDNEYDS dates
per patient, KIDNEYDS before the first other diagnosis, birth-value format and decades, sex values.
These are code catalogs and counts -- no row, patient ID, date of a person or free text of a person. A patient-name column
(환자명) is never catalogued. Counts below 11 are written as "<11"; percentiles only where >= 11 patients.

Date window (user decision 2026-10-14): every statistic and catalogue is computed on the rows inside the approved data period of
DRB-E(I)-2025-08-01 (pilot_lib.DRB_DATE_RANGE, 2000-01-01..2025-07-31; --date-range overrides). The event date of a table is
BASICS 내원일자, DRUG 처방일자, LAB 검사시행일, DIAGNOSIS 진단일자_OTHER (the same dates, parsed the same way, that P3 cuts on);
rows outside the window or without a parseable date are only counted. Other date columns (the first-diagnosis date KIDNEYDS, birth)
are not event dates and are not cut.

    python p1_profile_extract.py --irb E-XXXX-XXX-XXXX [--date-range 2000-01-01:2025-07-31]
"""
import argparse
import os
import re
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'snuh_pilot'))
sys.path.insert(0, HERE)
import pilot_lib as L  # noqa: E402
import cdm_lib as C  # noqa: E402

OUT = os.environ.get('PILOT_CDM_OUT', os.path.join(HERE, 'out'))     # tests point this at a scratch folder
PID_NAMES = ('RID', '연구별 환자 ID')
ICD = re.compile(r'^[A-Z][0-9]{2}')
EVENT_DATE = {'BASICS': ['내원일자'], 'DRUG': ['처방일자'], 'LAB': ['검사시행일']}   # event date column of a parquet table (fixed names)


def fix(c):
    """Column names of the R/CP949-written parquets arrive as mojibake (same repair as CKD_ML code)."""
    try:
        return c.encode('latin1').decode('cp949')
    except Exception:
        return c


def q(c):
    return '"' + c.replace('"', '""') + '"'


def cnt(n):
    return L.cell(int(n)) if pd.notna(n) else ''


def parquet_cols(con, path):
    raw = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()]
    return {fix(c): c for c in raw}


NAME_COL = re.compile(r'진단명|dx.?name|diagnosis.?name', re.I)       # diagnosis-name columns
PATIENT_COL = re.compile(r'환자|patient', re.I)                        # patient-name columns: never catalogued
ICD_TOKEN = re.compile(r'(?<![A-Za-z0-9])[A-Z][0-9]{2}(?:\.?[0-9A-Za-z]{1,4})?(?![A-Za-z0-9])')   # indicative only (B12 matches too)


def name_columns(cols):
    return [c for c in cols if NAME_COL.search(c) and not PATIENT_COL.search(c)]


def pct(a, b):
    return f'{100 * a / b:.1f}%' if b else 'n/a'


def profile_parquet(con, name, path, lines, win):
    """Statistics of one parquet table on the rows inside the date window. Creates the view w_<name> that the catalogues read."""
    lo, hi = win
    cols = parquet_cols(con, path)
    pid = next((cols[k] for k in PID_NAMES if k in cols), None)
    ev_fixed = next((k for k in EVENT_DATE[name.split('-')[0]] if k in cols), None)
    src_all = f"read_parquet('{path}')"
    view = 'w_' + re.sub(r'\W', '_', name)
    if ev_fixed:
        d = C.date_sql(q(cols[ev_fixed]))
        n_all, n_nodate, n_out = con.execute(f"""SELECT count(*), count(*) FILTER (WHERE {d} IS NULL),
            count(*) FILTER (WHERE {d} IS NOT NULL AND {d} NOT BETWEEN DATE '{lo}' AND DATE '{hi}') FROM {src_all}""").fetchone()
        con.execute(f"CREATE OR REPLACE VIEW {view} AS SELECT * FROM {src_all} WHERE {d} BETWEEN DATE '{lo}' AND DATE '{hi}'")
    else:
        n_all = con.execute(f'SELECT count(*) FROM {src_all}').fetchone()[0]
        n_nodate = n_out = None
        con.execute(f'CREATE OR REPLACE VIEW {view} AS SELECT * FROM {src_all}')
    n = con.execute(f'SELECT count(*) FROM {view}').fetchone()[0]
    npat = con.execute(f'SELECT count(DISTINCT {q(pid)}) FROM {view}').fetchone()[0] if pid else None
    lines += [f'## {name}  ({os.path.basename(path)})', f'rows {cnt(n)}  patients {cnt(npat) if npat else "?"}']
    if ev_fixed:
        lines.append(f'  date window {lo}..{hi} on {ev_fixed!r}: {cnt(n_out)} of {cnt(n_all)} rows outside the window, '
                     f'{cnt(n_nodate)} without a parseable date (not profiled)')
    else:
        lines.append(f'  no event-date column found: the window is not applied to this table')
    lines.append(f'  {"column":<22} {"distinct":>10} {"null %":>7}  range')
    for fixed, raw in cols.items():
        dist, nul = con.execute(f'SELECT count(DISTINCT {q(raw)}), avg(({q(raw)} IS NULL)::INT) FROM {view}').fetchone()
        rng = ''
        if re.search(r'일자|일$|시행일|date', fixed, re.I) and raw != pid:
            a, b = con.execute(f'SELECT min(CAST({q(raw)} AS VARCHAR)), max(CAST({q(raw)} AS VARCHAR)) FROM {view}').fetchone()
            ym = lambda s: re.sub(r'\D', '', str(s))[:6] if s else ''  # noqa: E731
            rng = f'{ym(a)[:4]}-{ym(a)[4:6]} .. {ym(b)[:4]}-{ym(b)[4:6]}'
        lines.append(f'  {fixed:<22} {"(id)" if raw == pid else f"{dist:,}":>10} {100 * (nul or 0):6.1f}%  {rng}')   # distinct = kinds of values, not people
    lines.append('')
    return cols, pid, view


def dx_names_report(con, x, pid, meta, lines):
    """DIAGNOSIS sheet without an ICD-10 code column: catalogue the diagnosis names of the sheet and of BASICS (names carried by
    >= 11 patients only; the rest is counted, not listed) and describe the sheet's structure. Aggregates only."""
    xc = name_columns([c for c in x.columns if c != pid])
    b = meta.get('BASICS')
    bc = name_columns(list(b[1])) if b else []
    lines += ['', '## Diagnosis names (no ICD-10 code column in the DIAGNOSIS sheet)']
    if not xc and not bc:
        lines.append('  no diagnosis-name column found')
        return
    parts = {}
    if xc:
        s = x[[pid, xc[0]]].dropna()
        s[xc[0]] = s[xc[0]].astype(str).str.strip()
        parts['xlsx'] = s.groupby(xc[0]).agg(n_rows=(pid, 'size'), n_pat=(pid, 'nunique')).reset_index().rename(columns={xc[0]: 'dx_name'})
        lines.append(f"  DIAGNOSIS sheet column {xc[0]!r}: {len(parts['xlsx']):,} distinct names")
    if bc:
        _, cols, bpid, bview = b
        raw = cols[bc[0]]
        parts['basics'] = con.execute(f"""SELECT trim(CAST({q(raw)} AS VARCHAR)) AS dx_name, count(*) AS n_rows,
                                                 count(DISTINCT {q(bpid)}) AS n_pat
                                          FROM {bview} WHERE {q(raw)} IS NOT NULL GROUP BY 1""").df()
        lines.append(f"  BASICS column {bc[0]!r}: {len(parts['basics']):,} distinct names")
    for k, g in parts.items():
        total = int(g.n_rows.sum())
        big = g.n_pat >= L.MIN_CELL
        icd = g.n_rows[g.dx_name.str.contains(ICD_TOKEN, na=False)].sum()
        lines.append(f"  {k}: names with >= {L.MIN_CELL} patients {int(big.sum()):,} of {len(g):,}, covering {pct(g.n_rows[big].sum(), total)} of "
                     f"{total:,} rows; ICD-10-like token inside the name in {pct(icd, total)} of rows")
    if len(parts) == 2:
        a, c = set(parts['xlsx'].dx_name), set(parts['basics'].dx_name)
        lines.append(f'  distinct names in both: {len(a & c):,}; only in the sheet: {len(a - c):,}; only in BASICS: {len(c - a):,}')
    m = None
    for k, g in parts.items():
        g = g.rename(columns={'n_rows': f'n_rows_{k}', 'n_pat': f'n_pat_{k}'})
        m = g if m is None else m.merge(g, on='dx_name', how='outer')
    pat_cols = [c for c in m.columns if c.startswith('n_pat_')]
    keep = (m[pat_cols].fillna(0) >= L.MIN_CELL).any(axis=1)
    out = m[keep].copy()
    out['_k'] = out[pat_cols].fillna(0).max(axis=1)
    out = out.sort_values('_k', ascending=False).drop(columns='_k')
    for c in [c for c in out.columns if c.startswith('n_')]:
        out[c] = out[c].map(lambda n: '' if pd.isna(n) else cnt(n))
    out['dx_name'] = out['dx_name'].astype(str).str.slice(0, 200)
    out.to_csv(os.path.join(OUT, 'p1_catalog_dx.csv'), index=False, encoding='utf-8-sig')
    lines.append(f'  name catalog: {len(out):,} names -> p1_catalog_dx.csv')

    # --- structure of the sheet ---
    lines += ['', '## DIAGNOSIS sheet structure (patients; counts below 11 shown as <11)']
    gp = x.groupby(pid)
    rpp = gp.size()
    lines.append(f'  rows per patient: median {rpp.median():.0f}, p95 {rpp.quantile(.95):.0f}')

    def dates(c):
        return pd.to_datetime(x[c].astype(str).str.replace(r'\D', '', regex=True).str[:8], format='%Y%m%d', errors='coerce')
    dcol = [c for c in x.columns if c != pid and re.search(r'일자|date', c, re.I)]
    for c in dcol:
        nun = gp[c].nunique()
        lines.append(f"  distinct values of {c!r} per patient: 1 -> {cnt((nun == 1).sum())}, 2 -> {cnt((nun == 2).sum())}, "
                     f"3 or more -> {cnt((nun >= 3).sum())}")
    kc = next((c for c in dcol if 'KIDNEYDS' in c), None)
    oc = next((c for c in dcol if 'OTHER' in c), None)
    if kc and oc:
        d = pd.DataFrame({'p': x[pid], 'k': dates(kc), 'o': dates(oc)}).groupby('p').agg(k=('k', 'min'), o=('o', 'min')).dropna()
        lines.append(f"  first {kc!r} vs first {oc!r} per patient ({len(d):,} patients with both): before -> {cnt((d.k < d.o).sum())}, "
                     f"same day -> {cnt((d.k == d.o).sum())}, after -> {cnt((d.k > d.o).sum())}")
        kd = dates(kc)
        lines.append(f"  rows whose {kc!r} lies before the window: {cnt((kd < pd.Timestamp(WIN[0])).sum())} of {cnt(len(x))} "
                     f"(first-diagnosis dates are not cut; P3 drops the CKD event of such a row)")
    bcol = next((c for c in x.columns if re.search(r'생년', c)), None)
    if bcol:
        v = x[[pid, bcol]].dropna()
        digits = v[bcol].astype(str).str.replace(r'\D', '', regex=True)
        ln = digits.str.len().value_counts()
        lines.append(f"  birth column {bcol!r}: digits per value " + ', '.join(f'{k} -> {pct(n, len(digits))}' for k, n in ln.head(4).items()))
        nun = v.groupby(pid)[bcol].nunique()
        lines.append(f'  patients with one distinct birth value: {pct((nun == 1).sum(), len(nun))}')
        first = v.groupby(pid)[bcol].first().astype(str).str.replace(r'\D', '', regex=True).str[:4]
        dec = (pd.to_numeric(first, errors='coerce') // 10 * 10).dropna().astype(int).value_counts().sort_index()
        lines.append('  patients by birth decade: ' + ', '.join(f'{k}s -> {cnt(n)}' for k, n in dec.items()))
    sc = next((c for c in x.columns if c in ('성별', 'Sex', 'SEX', '성별코드')), None)
    if sc:
        first = x[[pid, sc]].dropna().groupby(pid)[sc].first().astype(str).value_counts()
        lines.append('  sex values in the sheet (one per patient): ' + ', '.join(f'{k!r} -> {cnt(n)}' for k, n in first.head(6).items()))
    if b:
        _, cols, bpid, bview = b
        vis, sx = cols.get('내원일자'), cols.get('성별')
        extra_sel = ', quantile_cont(dd, 0.5), quantile_cont(dd, 0.95)' if vis else ''
        extra_col = f', count(DISTINCT {q(vis)}) AS dd' if vis else ''
        r = con.execute(f"""SELECT quantile_cont(n, 0.5), quantile_cont(n, 0.95){extra_sel}
                            FROM (SELECT count(*) AS n{extra_col} FROM {bview} GROUP BY {q(bpid)})""").fetchone()
        lines.append(f'  BASICS rows per patient: median {r[0]:.0f}, p95 {r[1]:.0f}' +
                     (f'; distinct visit dates per patient: median {r[2]:.0f}, p95 {r[3]:.0f}' if vis else ''))
        if sx:
            rs = con.execute(f"""SELECT CAST({q(sx)} AS VARCHAR) AS v, count(DISTINCT {q(bpid)}) AS n FROM {bview}
                                 WHERE {q(sx)} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 6""").fetchall()
            lines.append('  sex values in BASICS (patients with the value on any row): ' + ', '.join(f'{v!r} -> {cnt(n)}' for v, n in rs))
        basics_dates_report(con, x, pid, b, kc, oc, lines)


PIDX = "REGEXP_REPLACE(TRIM(CAST({} AS VARCHAR)), '\\.0$', '')"      # same patient-id normalisation as P3
DX_PATTERNS = {                                   # name patterns of the published pipeline (diagnosis_config) and of dialysis / transplant
    'History_HTN': r'hypertension|high blood pressure',
    'History_DM': r'diabetes|mellitus',
    'Subgroup_DKD': r'diabetic kidney|diabetic nephropathy|diabetes.*kidney|diabetes.*renal',
    'Subgroup_GN': r'glomerulonephritis|nephrotic|nephritic|iga nephropathy|lupus nephritis',
    'CKD-like name': r'kidney disease|renal failure|renal insufficiency|\bckd\b|\bcrf\b|esrd|end.stage (renal|kidney)',
    'dialysis name': r'dialysis',
    'kidney transplant name': r'(kidney|renal) transplant',
}


def basics_dates_report(con, x, pid, b, kc, oc, lines):
    """What the two date columns of BASICS are (visit date or diagnosis date), how they relate to the sheet's dates, when the first visit
    and the first CKD diagnosis fall, what the date window does to the CKD diagnosis, and how many patients carry the diagnosis names
    behind the published History flags. Aggregates only."""
    _, cols, bpid, bview = b
    vis_f, odt_f = '내원일자', '기타진단일자'                       # fixed names, used in the text; the SQL needs the raw (mojibake) names
    vis, odt = cols.get(vis_f), cols.get(odt_f)
    nm_f = next(iter(name_columns(list(cols))), None)
    nm = cols[nm_f] if nm_f else None
    lines += ['', '## BASICS dates and diagnosis names (patients / rows; counts below 11 shown as <11)']
    pb = PIDX.format(q(bpid))
    if vis and odt:
        dv, do = C.date_sql(q(vis)), C.date_sql(q(odt))
        r = con.execute(f"""SELECT count(*) FILTER (WHERE {do} < {dv}), count(*) FILTER (WHERE {do} = {dv}), count(*) FILTER (WHERE {do} > {dv}),
                                   count(*) FILTER (WHERE {do} IS NULL) FROM {bview}""").fetchone()
        lines.append(f"  per row, {odt_f!r} against {vis_f!r}: before -> {cnt(r[0])}, same day -> {cnt(r[1])}, after -> {cnt(r[2])}, no date -> {cnt(r[3])}")
        r = con.execute(f"""SELECT count(*) FILTER (WHERE n = 1), count(*) FILTER (WHERE n = 2), count(*) FILTER (WHERE n >= 3)
                            FROM (SELECT count(DISTINCT {do}) AS n FROM {bview} GROUP BY {pb})""").fetchone()
        lines.append(f"  distinct values of {odt_f!r} per patient: 1 -> {cnt(r[0])}, 2 -> {cnt(r[1])}, 3 or more -> {cnt(r[2])}")
        bp = con.execute(f"SELECT {pb} AS p, min({dv}) AS first_visit, min({do}) AS first_odt FROM {bview} GROUP BY 1").df()
        con.register('basics_pat', bp)
        if kc and oc:
            def dd(c):
                return pd.to_datetime(x[c].astype(str).str.replace(r'\D', '', regex=True).str[:8], format='%Y%m%d', errors='coerce')
            sp = pd.DataFrame({'p': x[pid].astype(str).str.replace(r'\.0$', '', regex=True).str.strip(), 'k': dd(kc), 'o': dd(oc)}
                              ).groupby('p').agg(k=('k', 'min'), o=('o', 'min')).reset_index()
            con.register('sheet_pat', sp)
            for lab, a, bcol in (("first BASICS " + repr(odt_f) + " against the sheet's first " + repr(kc), 'first_odt', 'k'),
                                 ("first BASICS " + repr(vis_f) + " against the sheet's first " + repr(oc), 'first_visit', 'o')):
                r = con.execute(f"""SELECT count(*) FILTER (WHERE s.{bcol} < t.{a}), count(*) FILTER (WHERE s.{bcol} = t.{a}),
                                           count(*) FILTER (WHERE s.{bcol} > t.{a}), count(*) FILTER (WHERE s.{bcol} IS NULL OR t.{a} IS NULL)
                                    FROM basics_pat t JOIN sheet_pat s ON s.p = t.p""").fetchone()
                lines.append(f"  per patient, {lab}: sheet earlier -> {cnt(r[0])}, equal -> {cnt(r[1])}, sheet later -> {cnt(r[2])}, no date -> {cnt(r[3])}")
            ky = sp.assign(y=sp.k.dt.year).y.dropna().astype(int).value_counts().sort_index()
            lines.append("  patients by year of the sheet's first " + repr(kc) + ": " + ', '.join(f'{y} -> {cnt(n)}' for y, n in ky.items()))
            vy = bp.assign(y=pd.to_datetime(bp.first_visit).dt.year).y.dropna().astype(int).value_counts().sort_index()
            lines.append(f"  patients by year of the first BASICS {vis_f!r}: " + ', '.join(f'{y} -> {cnt(n)}' for y, n in vy.items()))
            lo = pd.Timestamp(WIN[0])
            early = set(sp.loc[sp.k < lo, 'p'])
            if nm:
                ck = con.execute(f"""SELECT DISTINCT {pb} FROM {bview} WHERE regexp_matches(lower(CAST({q(nm)} AS VARCHAR)), '{DX_PATTERNS['CKD-like name']}')""").df().iloc[:, 0]
                lines.append(f"  patients whose first {kc!r} lies before {WIN[0]}: {cnt(len(early))}; of them with a CKD-like diagnosis name inside the window: "
                             f"{cnt(len(early & set(ck)))}; all patients with such a name: {cnt(len(set(ck)))}")
    if nm:
        parts = []
        for k, p in DX_PATTERNS.items():
            n = con.execute(f"SELECT count(DISTINCT {pb}) FROM {bview} WHERE regexp_matches(lower(CAST({q(nm)} AS VARCHAR)), '{p}')").fetchone()[0]
            parts.append(f'{k} -> {cnt(n)}')
        lines.append('  patients with a diagnosis name that matches (published patterns; indicative): ' + ', '.join(parts))


WIN = L.DRB_DATE_RANGE       # set from --date-range in main(); read by dx_names_report


def main():
    global WIN
    ap = argparse.ArgumentParser()
    ap.add_argument('--irb', default=os.environ.get('PILOT_IRB', ''))
    ap.add_argument('--date-range', default=':'.join(L.DRB_DATE_RANGE),
                    help='data period to profile, LO:HI (default = the approved period of DRB-E(I)-2025-08-01)')
    a = ap.parse_args()
    if not re.fullmatch(r'E-\d{4}-\d{3}-\d{4}', a.irb.strip()):
        sys.exit("SNUH data not read: give this study's IRB exemption number, e.g. --irb E-2610-123-4567")
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}:\d{4}-\d{2}-\d{2}', a.date_range):
        sys.exit('--date-range must look like 2000-01-01:2025-07-31')
    lo, hi = a.date_range.split(':')
    WIN = (lo, hi)
    root = L.CKD_ROOT
    pq_dir = os.path.join(root, 'Data', 'parquets')
    xl_dir = L.raw_xlsx_dir(root, 'Data/CSV')
    os.makedirs(OUT, exist_ok=True)
    con = C.connect()
    lines = ['# P1 extract profile (aggregates only)', '',
             f'parquet folder : {pq_dir}  ({"found" if os.path.isdir(pq_dir) else "NOT FOUND"})',
             f'xlsx folder    : {xl_dir}  ({"found" if os.path.isdir(xl_dir) else "NOT FOUND"})',
             f'date window    : {lo} .. {hi}  (approved data period of DRB-E(I)-2025-08-01; rows outside it are counted, not profiled)', '']

    # --- parquet tables -------------------------------------------------
    tables = {'BASICS': 'BASICS_Total.parquet', 'DRUG': 'DRUG_Total.parquet',
              'LAB-1': 'LAB-1.parquet', 'LAB-2': 'LAB-2.parquet'}
    meta = {}
    for name, f in tables.items():
        p = os.path.join(pq_dir, f).replace('\\', '/')
        if os.path.exists(p):
            meta[name] = (p,) + profile_parquet(con, name, p, lines, WIN)
        else:
            lines += [f'## {name}: {f} not found', '']

    # --- lab catalog ----------------------------------------------------
    labs = [m for k, m in meta.items() if k.startswith('LAB')]
    if labs:
        parts = []
        for p, cols, pid, view in labs:
            parts.append(f"SELECT {q(pid)} AS pid, {q(cols['검사명'])} AS test, {q(cols['검사결과단위'])} AS unit, "
                         f"TRY_CAST({q(cols['검사결과'])} AS DOUBLE) AS v FROM {view}")
        df = con.execute(f"""
            SELECT test, unit, count(*) AS n_rows, count(DISTINCT pid) AS n_pat, avg((v IS NOT NULL)::INT) AS numeric_rate,
                   quantile_cont(v, 0.05) AS p05, quantile_cont(v, 0.5) AS p50, quantile_cont(v, 0.95) AS p95
            FROM ({' UNION ALL '.join(parts)}) GROUP BY test, unit ORDER BY n_pat DESC""").df()
        small = df['n_pat'] < L.MIN_CELL
        df.loc[small, ['p05', 'p50', 'p95']] = None
        for c in ('n_rows', 'n_pat'):
            df[c] = df[c].map(cnt)
        df.to_csv(os.path.join(OUT, 'p1_catalog_lab.csv'), index=False, encoding='utf-8-sig')
        lines.append(f'lab catalog: {len(df):,} test x unit pairs -> p1_catalog_lab.csv')

    # --- drug catalog ---------------------------------------------------
    if 'DRUG' in meta:
        p, cols, pid, view = meta['DRUG']
        code, ing = cols.get('약품코드'), cols.get('일반성분명')
        df = con.execute(f"""SELECT {q(code)} AS drug_code, {q(ing)} AS ingredient_name, count(*) AS n_rows,
                                    count(DISTINCT {q(pid)}) AS n_pat
                             FROM {view} GROUP BY 1, 2 ORDER BY n_pat DESC""").df()
        for c in ('n_rows', 'n_pat'):
            df[c] = df[c].map(cnt)
        df.to_csv(os.path.join(OUT, 'p1_catalog_drug.csv'), index=False, encoding='utf-8-sig')
        lines.append(f'drug catalog: {len(df):,} code x name pairs -> p1_catalog_drug.csv')

    # --- diagnosis / RID_LIST xlsx ----------------------------------------
    for label, f in (('DIAGNOSIS_ICD10', '[CKD_AI]DIAGNOSIS_ICD10.xlsx'), ('RID_LIST', '[CKD_AI]RID_LIST.xlsx')):
        path = os.path.join(xl_dir, f)
        if not os.path.exists(path):
            lines += ['', f'## {label}: not found']
            continue
        x = pd.read_excel(path, dtype=str)
        x.columns = [fix(str(c)) for c in x.columns]
        pid = next((c for c in PID_NAMES if c in x.columns), None)
        win_note = ''
        if label == 'DIAGNOSIS_ICD10':        # event date = the date of the (other) diagnosis; the first-diagnosis date KIDNEYDS is not cut
            date_cols = [c for c in x.columns if re.search(r'일자|date', c, re.I)]
            ev = next((c for c in date_cols if 'KIDNEY' not in c.upper()), None) or (date_cols[0] if date_cols else None)
            if ev:
                dts = pd.to_datetime(x[ev].astype(str).str.replace(r'\D', '', regex=True).str[:8], format='%Y%m%d', errors='coerce')
                ok = dts.between(pd.Timestamp(lo), pd.Timestamp(hi))
                win_note = (f'  date window {lo}..{hi} on {ev!r}: {cnt((dts.notna() & ~ok).sum())} of {cnt(len(x))} rows outside the window, '
                            f'{cnt(dts.isna().sum())} without a parseable date (not profiled)')
                x = x[ok].reset_index(drop=True)
        lines += ['', f'## {label}  rows {cnt(len(x))}  patients {cnt(x[pid].nunique()) if pid else "?"}']
        if win_note:
            lines.append(win_note)
        lines.append(f'  {"column":<22} {"distinct":>10} {"null %":>7}  ICD-like %  range')
        icd_cols = []
        for c in x.columns:
            s = x[c].dropna().astype(str).str.strip()
            icd_share = s.str.match(ICD).mean() if len(s) else 0
            if icd_share > 0.9 and c != pid:
                icd_cols.append(c)
            rng = ''
            if re.search(r'일자|일$|date', c, re.I):
                d8 = s.str.replace(r'\D', '', regex=True).str[:6]
                d8 = d8[d8.str.len() == 6]
                rng = f'{d8.min()[:4]}-{d8.min()[4:]} .. {d8.max()[:4]}-{d8.max()[4:]}' if len(d8) else ''
            lines.append(f'  {c:<22} {"(id)" if c == pid else f"{x[c].nunique():,}":>10} {100 * x[c].isna().mean():6.1f}%  {100 * icd_share:5.1f}  {rng}')
        if label == 'DIAGNOSIS_ICD10' and not icd_cols and pid:
            dx_names_report(con, x, pid, meta, lines)
        if label == 'DIAGNOSIS_ICD10' and icd_cols:
            code = icd_cols[0]
            name_col = next((c for c in x.columns if c not in (pid, code) and re.search(r'명|name', c, re.I)
                             and not PATIENT_COL.search(c)), None)
            keys = [code] + ([name_col] if name_col else [])
            g = x.groupby(keys, dropna=False).agg(n_rows=(code, 'size'), n_pat=(pid, 'nunique')).reset_index()
            g = g.sort_values('n_pat', ascending=False)
            tiny = g['n_pat'] < L.MIN_CELL            # codes / names carried by fewer than 11 patients are counted, not listed
            n_tiny_codes, n_tiny_rows = int(g.loc[tiny, code].nunique()), int(g.loc[tiny, 'n_rows'].sum())
            g = g[~tiny].copy()
            for c in ('n_rows', 'n_pat'):
                g[c] = g[c].map(cnt)
            g = g.rename(columns={code: 'icd10_code', **({name_col: 'dx_name'} if name_col else {})})
            if n_tiny_codes:
                g = pd.concat([g, pd.DataFrame([{'icd10_code': f'(other: {n_tiny_codes:,} codes, each with fewer than {L.MIN_CELL} patients)',
                                                 'n_rows': cnt(n_tiny_rows), 'n_pat': ''}])], ignore_index=True)
            g.to_csv(os.path.join(OUT, 'p1_catalog_dx.csv'), index=False, encoding='utf-8-sig')
            lines.append(f'  dx catalog: column {code!r}{" + " + repr(name_col) if name_col else ""}, {len(g):,} lines -> p1_catalog_dx.csv '
                         f'(codes with fewer than {L.MIN_CELL} patients are summed up in one line)')

    open(os.path.join(OUT, 'p1_schema.txt'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    try:
        print('done ->', os.path.relpath(OUT, L.BASE))
    except ValueError:                                  # another drive (scratch folder)
        print('done ->', OUT)


if __name__ == '__main__':
    L.guard(main)
