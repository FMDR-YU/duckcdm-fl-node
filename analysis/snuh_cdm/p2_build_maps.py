# -*- coding: utf-8 -*-
"""P2 -- code-level mapping tables (maps/*.csv) from the P1 catalogues and the Athena vocabulary.

No patient data: the inputs are out/p1_catalog_*.csv (test / drug / diagnosis names with counts) and the vocabulary. Only entries carried by
at least 11 patients in the catalogue are mapped (the same suppression rule as everywhere else; the others become concept 0 in P3 and
show up in its unmapped lists). Outputs:

  maps/lab_map.csv     exact (test, unit) rows for the 23 laboratory model inputs: LOINC, UCUM unit, multiplier
  maps/drug_map.csv    (drug code, product name) -> RxNorm / RxNorm Extension ingredient(s); exclude flags for investigational products,
                       infusion fluids and topical / ophthalmic / inhaled / nasal / otic products
  maps/dx_map.csv      diagnosis name -> SNOMED (see the dx part; needs out/p1_catalog_dx.csv)
  out/p2_report.txt    coverage (rows / patients of the catalogue), unit problems, class check of the ATC groups P4 uses
  out/p2_unmapped_drug.csv   mapped-nowhere product names with >= 11 patients, most frequent first (next round)
  maps/P2_DONE.txt     written only when all three tables are complete; `run_snuh.ps1 -Stage cdm` refuses to run P3 without it

    python p2_build_maps.py [--only lab,drug,dx] [--vocab DIR] [--maps DIR] [--out DIR]
"""
import argparse
import os
import re
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cdm_lib as C  # noqa: E402
from cdm_lib import L, lit  # noqa: E402
import drug_parse as DP  # noqa: E402

TODAY = '2026-10-14'
ENG = '4180186'            # language_concept_id of English in CONCEPT_SYNONYM


def num(s):
    """'2,206,422' -> 2206422; '<11' or '' -> None (suppressed in the catalogue)."""
    s = str(s).strip()
    return None if s == '' or s.startswith('<') else int(s.replace(',', ''))


def read_catalog(path):
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, encoding='utf-8-sig', dtype=str, keep_default_na=False)
    for c in ('n_rows', 'n_pat'):
        if c in df.columns:
            df[c + '_i'] = df[c].map(num)
    return df


def pct(a, b):
    return f'{100 * a / b:.1f}%' if b else 'n/a'


# ───────────────────────── vocabulary ─────────────────────────
class Vocab:
    def __init__(self, vdir):
        self.dir = vdir
        self.con = C.connect()
        f = C.vocab_file(vdir, 'concept')
        if not f:
            sys.exit(f'Athena vocabulary not found in {vdir} (P0)')
        self.con.execute('CREATE TABLE concept AS ' + C.read_vocab_sql(f, C.CONCEPT_COLS))

    def loinc(self, codes):
        codes = sorted(set(codes))
        rows = self.con.execute(f"""SELECT concept_code, concept_id FROM concept WHERE vocabulary_id = 'LOINC'
            AND concept_code IN ({', '.join(lit(c) for c in codes)}) ORDER BY (invalid_reason IS NULL) DESC, (standard_concept = 'S') DESC""").fetchall()
        out = {}
        for code, cid in rows:
            out.setdefault(code, cid)
        return out

    def ucum(self, codes):
        codes = sorted({c for c in codes if c})
        if not codes:
            return {}
        rows = self.con.execute(f"""SELECT concept_code, concept_id FROM concept WHERE vocabulary_id = 'UCUM'
            AND concept_code IN ({', '.join(lit(c) for c in codes)}) ORDER BY (invalid_reason IS NULL) DESC""").fetchall()
        out = {}
        for code, cid in rows:
            out.setdefault(code, cid)
        return out

    def ingredient_lookup(self):
        """{normalised name: (concept_id, concept_name)} of standard RxNorm / RxNorm Extension ingredients; RxNorm wins; the English
        synonyms of those concepts are added for names that have no key yet."""
        df = self.con.execute("""SELECT concept_id, concept_name, vocabulary_id FROM concept
            WHERE domain_id = 'Drug' AND concept_class_id = 'Ingredient' AND standard_concept = 'S'
              AND vocabulary_id IN ('RxNorm', 'RxNorm Extension') AND invalid_reason IS NULL
            ORDER BY (vocabulary_id = 'RxNorm') DESC, concept_id""").df()
        lut = {}
        for cid, name in zip(df.concept_id, df.concept_name):
            lut.setdefault(DP.clean(name), (int(cid), name))
        p = os.path.join(self.dir, 'CONCEPT_SYNONYM.csv')
        if os.path.exists(p):
            ids = ', '.join(str(int(i)) for i in df.concept_id)
            s = self.con.execute(f"""SELECT concept_id::BIGINT AS concept_id, concept_synonym_name AS n FROM
                read_csv({C.sqlpath(p)}, delim='\t', header=true, quote='', escape='', all_varchar=true)
                WHERE language_concept_id = '{ENG}' AND concept_id::BIGINT IN ({ids})""").df()
            names = dict(zip(df.concept_id, df.concept_name))
            for cid, n in zip(s.concept_id, s.n):
                lut.setdefault(DP.clean(n), (int(cid), names[cid]))
        return lut

    def concept_by_name(self, name, vocabulary='SNOMED'):
        """Standard concept of an exact (case-insensitive) concept name, (concept_id, name, domain) or None."""
        r = self.con.execute("""SELECT concept_id, concept_name, domain_id FROM concept WHERE vocabulary_id = ? AND standard_concept = 'S'
                                AND invalid_reason IS NULL AND lower(concept_name) = lower(?) ORDER BY concept_id LIMIT 1""",
                             [vocabulary, name]).fetchone()
        return tuple(r) if r else None

    def dx_lookup(self):
        """{normalised text: [(concept_id, domain, source)]} for the standard SNOMED Condition / Procedure concepts: their names, their
        English synonyms, and the names of ICD10 / KCD7 concepts that 'Maps to' them."""
        rel = C.vocab_file(self.dir, 'concept_relationship')
        syn = os.path.join(self.dir, 'CONCEPT_SYNONYM.csv')
        self.con.execute("CREATE TABLE maps_to AS SELECT concept_id_1, concept_id_2 FROM (" + C.read_vocab_sql(rel, C.REL_COLS)
                         + ") WHERE relationship_id = 'Maps to' AND invalid_reason IS NULL")
        dom = "('Condition', 'Procedure')"
        parts = [f"""SELECT concept_name AS n, concept_id, domain_id, 'SNOMED name' AS src FROM concept WHERE vocabulary_id = 'SNOMED'
                     AND standard_concept = 'S' AND invalid_reason IS NULL AND domain_id IN {dom}""",
                 f"""SELECT c.concept_name, t.concept_id_2, c2.domain_id, 'ICD10/KCD7 name' FROM concept c JOIN maps_to t ON t.concept_id_1 = c.concept_id
                     JOIN concept c2 ON c2.concept_id = t.concept_id_2 WHERE c.vocabulary_id IN ('ICD10', 'KCD7')
                     AND c2.standard_concept = 'S' AND c2.domain_id IN {dom}"""]
        if os.path.exists(syn):
            self.con.execute(f"""CREATE TABLE synonym AS SELECT concept_id::BIGINT AS concept_id, concept_synonym_name AS n FROM
                read_csv({C.sqlpath(syn)}, delim='\t', header=true, quote='', escape='', all_varchar=true) WHERE language_concept_id = '{ENG}'""")
            parts.append(f"""SELECT s.n, c.concept_id, c.domain_id, 'SNOMED synonym' FROM synonym s JOIN concept c USING (concept_id)
                             WHERE c.vocabulary_id = 'SNOMED' AND c.standard_concept = 'S' AND c.invalid_reason IS NULL AND c.domain_id IN {dom}""")
        df = self.con.execute(' UNION ALL '.join(parts)).df()
        lut = {}
        for n, cid, d, src in zip(df.n, df.concept_id, df.domain_id, df.src):
            lut.setdefault(dx_clean(n), []).append((int(cid), d, src))
        return lut

    def under_atc(self, atc_codes):
        """{atc code: set of descendant concept ids} through CONCEPT_ANCESTOR (RxNorm ingredients sit under the ATC classes)."""
        ids = dict(self.con.execute(f"""SELECT concept_code, concept_id FROM concept WHERE vocabulary_id = 'ATC'
                                        AND concept_code IN ({', '.join(lit(c) for c in atc_codes)})""").fetchall())
        f = C.vocab_file(self.dir, 'concept_ancestor')
        if not ids or not f:
            return {c: set() for c in atc_codes}
        sel = C.read_vocab_sql(f, C.ANCESTOR_COLS)
        rows = self.con.execute(f"SELECT ancestor_concept_id, descendant_concept_id FROM ({sel}) "
                                f"WHERE ancestor_concept_id IN ({', '.join(str(i) for i in ids.values())})").fetchall()
        inv = {v: k for k, v in ids.items()}
        out = {c: set() for c in atc_codes}
        for a, d in rows:
            out[inv[a]].add(int(d))
        return out


# ───────────────────────── laboratory ─────────────────────────
MGDL, MMOLL, GDL, PCT_U = {'mg/dL': ('mg/dL', 1.0)}, {'mmol/L': ('mmol/L', 1.0)}, {'g/dL': ('g/dL', 1.0)}, {'%': ('%', 1.0)}
ENZ = {'IU/L': ('[iU]/L', 1.0), 'U/L': ('[U]/L', 1.0)}      # UCUM: international unit / unit per liter
RATIO = {'': ('', 1.0)}     # ACR reported without a unit; P4 normalises by magnitude (< 0.5 -> x 1000, as the published pipeline)

# Same order and keywords as lab_config of SNUH_CKD_DATAPREP.ipynb cell 1 (a test name goes to the first variable whose keyword is a substring
# of it). Two deliberate differences, both towards the definitions of the model card: LDL-cholesterol is not total cholesterol and
# CSF glucose is not blood glucose. The notebook's substring rule accepts both ('Cholesterol(검사24시간가능)' is inside
# 'LDL-Cholesterol(검사24시간가능)'); the P4 agreement report shows what that changes.
# (feature, LOINC, keywords, excluded substrings, {raw unit: (UCUM of the stored value, multiplier)})
LAB_RULES = [
    ('Creatinine', '2160-0', ['Creatinine(검사24시간가능)', '[처방불가]Creatinine (serum, em)', 'Creatinine (serum)'], [], MGDL),
    ('BUN', '3094-0', ['BUN(검사24시간가능)', '[처방불가]BUN (serum, em)'], [], MGDL),
    ('Uric_Acid', '3084-1', ['Uric Acid(검사24시간가능)'], [], MGDL),
    ('Sodium', '2951-2', ['Sodium (serum)(검사24시간가능)', '[처방불가]Sodium (serum, em)'], [], MMOLL),
    ('Potassium', '2823-3', ['Potassium (serum)(검사24시간가능)', '[처방불가]Potassium (serum, em)'], [], MMOLL),
    ('Potassium', '6298-4', ['[POCT, ABGA]Potassium'], [], MMOLL),                  # whole blood; P4 accepts both LOINC codes
    ('Calcium', '17861-6', ['Calcium(검사24시간가능)'], [], MGDL),
    ('Phosphorus', '2777-1', ['Phosphorus(검사24시간가능)'], [], MGDL),
    ('Bicarbonate', '2028-9', ['CO2, total (serum)', 'CO2, total (serum, em)'], [], MMOLL),   # SNUH test = total CO2
    ('Albumin', '1751-7', ['Albumin(검사24시간가능)', '[처방불가]Albumin (em)'], [], GDL),
    ('Total_Protein', '2885-2', ['Protein, total(검사24시간가능)', '[처방불가]Protein, total (em)'], [], GDL),
    ('Total_Bilirubin', '1975-2', ['Bilirubin, total(검사24시간가능)'], [], MGDL),
    ('AST', '1920-8', ['GOT (AST)(검사24시간가능)'], [], ENZ),
    ('ALT', '1742-6', ['GPT (ALT)(검사24시간가능)', 'GPT(ALT) [piccolo, 과내간이]'], [], ENZ),
    ('GGT', '2324-2', ['GGT(검사24시간가능)', '[처방불가]GGT (em)'], [], ENZ),
    ('Hb', '718-7', ['Hb(검사24시간가능)', '[POCT, ABGA]Hb'], [], GDL),
    ('HbA1c', '4548-4', ['Hb A1c'], [], PCT_U),
    ('Glucose', '2345-7', ['Glucose(검사24시간가능)'], ['CSF'], MGDL),
    ('HDL', '2085-9', ['HDL-Cholesterol(검사24시간가능)'], [], MGDL),
    ('TG', '2571-8', ['Triglyceride'], [], MGDL),
    ('Cholesterol', '2093-3', ['Cholesterol(검사24시간가능)'], ['LDL-', 'HDL-'], MGDL),
    ('UACR_Raw', '14959-1', ['Microalbumin/Creatinine Ratio'], [], RATIO),             # random and 24-h urine variants, as published
    ('Urine_Microalbumin', '14957-5', ['Microalbumin (random urine)'], [], MGDL),
    ('Urine_Creatinine', '2161-8', ['Creatinine (random urine)'], [], MGDL),
]
NOTE_LAB = f'P2 {TODAY}: exact row; keyword of the published lab_config, unit checked against the P1 catalogue'


def lab_rule(test):
    for feat, loinc, kws, excl, units in LAB_RULES:
        if any(k in test for k in kws) and not any(x in test for x in excl):
            return feat, loinc, units
    return None


def build_lab(cat, voc, rep):
    cat = cat[cat['n_pat_i'].notna()].copy()                # >= 11 patients
    rows, bad_unit = [], []
    reported = {}                                           # test name -> a unit the extract reports for it and the rule accepts
    for r in cat.itertuples():
        hit = lab_rule(r.test)
        if hit and r.unit in hit[2]:
            reported.setdefault(r.test, r.unit)
    for r in cat.itertuples():
        hit = lab_rule(r.test)
        if hit is None:
            continue
        feat, loinc, units = hit
        if r.unit in units:
            ucum, mult = units[r.unit]
            note = NOTE_LAB
        elif r.unit == '' and units:
            ucum, mult = units[reported[r.test]] if r.test in reported else next(iter(units.values()))
            note = NOTE_LAB + f'; unit empty in the extract, {ucum} assumed (the unit the extract reports for the same test)'
        else:
            bad_unit.append((feat, r.test, r.unit, r.n_pat))
            continue
        rows.append({'test_name': r.test, 'unit': r.unit, 'match': 'exact', 'priority': '', 'measurement_concept_id': '',
                     'loinc_code': loinc, 'unit_concept_id': '', 'ucum_unit': ucum, 'value_multiplier': mult, 'value_offset': 0,
                     'feature': feat, 'source': note})
    m = pd.DataFrame(rows, columns=['test_name', 'unit', 'match', 'priority', 'measurement_concept_id', 'loinc_code', 'unit_concept_id',
                                    'ucum_unit', 'value_multiplier', 'value_offset', 'feature', 'source'])
    loinc_ok = voc.loinc(m['loinc_code'])
    ucum_ok = voc.ucum(m['ucum_unit'])
    rep += ['## laboratory (lab_map.csv)', f'  catalogue pairs with >= {L.MIN_CELL} patients: {len(cat):,}; mapped to one of the 23 inputs: {len(m):,}']
    miss = sorted({c for c in m['loinc_code'] if c not in loinc_ok})
    rep.append(f'  LOINC codes used: {m["loinc_code"].nunique()}; not found in the vocabulary: {miss or "none"}')
    miss_u = sorted({c for c in m['ucum_unit'] if c and c not in ucum_ok})
    rep.append(f'  UCUM units used: {sorted(u for u in m["ucum_unit"].unique() if u)}; not found in the vocabulary: {miss_u or "none"} '
               f'(the unit concept then falls back to the raw unit string, else 0)')
    rep.append(f'  {"feature":<20}{"pairs":>6}{"rows":>14}{"patients (largest pair)":>26}')
    by = cat.merge(m[['test_name', 'unit', 'feature']], left_on=['test', 'unit'], right_on=['test_name', 'unit'])
    for f, g in by.groupby('feature', sort=False):
        rep.append(f'  {f:<20}{len(g):>6}{int(g.n_rows_i.sum()):>14,}{int(g.n_pat_i.max()):>26,}')
    if bad_unit:
        rep.append('  matched by a keyword but with a unit that is not expected (left unmapped): ' +
                   '; '.join(f'{f}: {t!r} [{u}] {n}' for f, t, u, n in bad_unit))
    # what the published substring rule would have taken in as well (not mapped here)
    pub = []
    for r in cat.itertuples():
        if lab_rule(r.test) is None:
            for feat, _, kws, excl, _ in LAB_RULES:
                if any(k in r.test for k in kws) and any(x in r.test for x in excl):
                    pub.append(f'{r.test!r} [{r.unit}] ({r.n_pat} patients) would have counted as {feat}')
    if pub:
        rep.append('  names that the published substring rule counts as a model input but P2 does not map:')
        rep += [f'    {p}' for p in pub]
    unm = cat[~cat['test'].map(lambda t: lab_rule(t) is not None)].sort_values('n_pat_i', ascending=False)
    rep.append(f'  catalogue pairs left unmapped (concept 0 in P3, not needed by the model): {len(unm):,}; the 12 most frequent:')
    rep += [f'    {r.test!r} [{r.unit}]  {r.n_pat} patients' for r in unm.head(12).itertuples()]
    rep.append('')
    return m


# ───────────────────────── drugs ─────────────────────────
DRUG_COLS = ['drug_code', 'ingredient_name', 'drug_concept_id', 'exclude', 'exclude_reason', 'route', 'source']
NOTE_DRUG = f'P2 {TODAY}: name parsed (drug_parse), ingredient matched to RxNorm'
# classes P4 reads through the ATC ancestors, and the name patterns the published pipeline used for them (drug_dictionary.DRUG_CLASSES)
ATC_GROUPS = {'RAASi': ['C09A', 'C09C'], 'Statins': ['C10AA']}
_ARB = r'(?:lo|val|cande|irbe|telmi|olme|fima|azil|epro|tas)sartan|amosartan'
_ACEI = r'(?:rami|enala|capto|lisino|perindo|imida|benaze|fosino|zofeno|temoca|cilaza|quina|trandola|moexi|alace|dela|spira)pril'
PUBLISHED_PAT = {'RAASi': _ARB + '|' + _ACEI, 'Statins': r'(?:atorva|rosuva|simva|prava|pitava|fluva|lova|ceriva)statin'}


def match_ingredient(ing, lut):
    """RxNorm ingredient (concept_id, name) list for one ingredient string of a product, or []. Stages: the keys of drug_parse.candidates;
    then, for several words none of which is a known name as a whole, each word of four letters or more must be an ingredient
    ('sacubitril valsartan'); that second path is only taken when every such word is found."""
    for k in DP.candidates(ing):
        if k in lut:
            return [lut[k]]
    words = [w for w in DP.strip_salts(DP.clean(ing)).split() if len(w) >= 4]
    if len(words) >= 2:
        found = []
        for w in words:
            h = next((lut[k] for k in DP.candidates(w) if k in lut), None)
            if h is None:
                return []
            found.append(h)
        return found
    return []


def build_drug(cat, voc, rep, unmapped_out):
    lut = voc.ingredient_lookup()
    under = voc.under_atc([c for cs in ATC_GROUPS.values() for c in cs])
    group_ids = {g: set().union(*(under[c] for c in cs)) for g, cs in ATC_GROUPS.items()}
    big = cat[cat['n_pat_i'].notna()].copy()
    rows, status, atc_hit, seen = [], [], {}, {}
    pair_ids = {}
    for r in big.itertuples():
        info = DP.parse(r.ingredient_name)
        base = {'drug_code': r.drug_code, 'ingredient_name': r.ingredient_name, 'route': info['route'] if info['route'] != 'unknown' else ''}
        if info['exclude_reason']:
            rows.append({**base, 'drug_concept_id': '', 'exclude': 1, 'exclude_reason': info['exclude_reason'],
                         'source': NOTE_DRUG + '; excluded product'})
            status.append('excluded')
            continue
        hits = []
        for ing in info['ingredients']:
            for h in match_ingredient(ing, lut):
                if h[0] not in [x[0] for x in hits]:
                    hits.append(h)
        if not hits:
            status.append('unmapped' if info['ingredients'] else 'no_ingredient')
            continue
        for cid, cname in hits:
            rows.append({**base, 'drug_concept_id': cid, 'exclude': 0, 'exclude_reason': '', 'source': NOTE_DRUG + f' ({cname})'})
            seen[int(cid)] = cname
        status.append('mapped' if len(hits) >= len(info['ingredients']) else 'partial')
        pair_ids[(r.drug_code, r.ingredient_name)] = [h[0] for h in hits]
    big['status'] = status
    m = pd.DataFrame(rows, columns=DRUG_COLS)
    sup = []
    cls_re = {'C09C': re.compile(_ARB), 'C09A': re.compile(_ACEI), 'C10AA': re.compile(PUBLISHED_PAT['Statins'])}
    for cid, cname in sorted(seen.items(), key=lambda t: t[1]):
        for code, rx in cls_re.items():
            group = 'RAASi' if code.startswith('C09') else 'Statins'
            if rx.search(cname.lower()) and cid not in group_ids[group]:
                sup.append({'atc_code': code, 'descendant_concept_id': cid, 'ingredient_name': cname,
                            'source': f'P2 {TODAY}: ingredient name matches the {group} pattern of the published pipeline, '
                                      f'the vocabulary has no ATC ancestor for it'})
    supplement = pd.DataFrame(sup, columns=['atc_code', 'descendant_concept_id', 'ingredient_name', 'source'])
    for g in group_ids:                           # the class check below sees the vocabulary plus the supplement, as P3 will
        group_ids[g] = group_ids[g] | {int(c) for c, cd in zip(supplement.descendant_concept_id, supplement.atc_code)
                                       if (g == 'RAASi') == cd.startswith('C09')}
    atc_hit = {k: {g: any(i in ids for i in v) for g, ids in group_ids.items()} for k, v in pair_ids.items()}
    tot_rows, tot_pairs = int(big.n_rows_i.sum()), len(big)
    rep += ['## drugs (drug_map.csv)',
            f'  catalogue: {len(cat):,} code x name pairs, {len(big):,} with >= {L.MIN_CELL} patients (only these are mapped); '
            f'RxNorm / RxNorm Extension standard ingredients in the vocabulary: {len(lut):,} name keys']
    rep.append(f'  {"status":<14}{"pairs":>8}{"rows":>16}{"share of rows":>16}')
    for s, g in big.groupby('status'):
        rep.append(f'  {s:<14}{len(g):>8,}{int(g.n_rows_i.sum()):>16,}{pct(g.n_rows_i.sum(), tot_rows):>16}')
    ex = big[big.status == 'excluded']
    for reason in ('investigational', 'fluid', 'topical'):
        g = ex[pd.Series([reason in DP.parse(n)['exclude_reason'] for n in ex.ingredient_name], index=ex.index, dtype=bool)]
        rep.append(f'    excluded as {reason}: {len(g):,} pairs, {int(g.n_rows_i.sum()):,} rows (a product can carry several reasons)')
    # check of the two ATC groups against the name patterns of the published pipeline
    rep.append('  ATC groups used by P4 (ingredient under the ATC class) against the name patterns of the published pipeline (pairs / rows):')
    for g, pat in PUBLISHED_PAT.items():
        pub = big.ingredient_name.str.lower().str.contains(pat, regex=True, na=False)
        key = list(zip(big.drug_code, big.ingredient_name))
        atc = pd.Series([atc_hit.get(k, {}).get(g, False) for k in key], index=big.index)
        excl = big.status == 'excluded'
        for label, mask in (('both', pub & atc), ('pattern only', pub & ~atc & ~excl), ('ATC only', atc & ~pub),
                            ('pattern, excluded product', pub & excl)):
            rep.append(f'    {g:<8} {label:<26}{int(mask.sum()):>6,} pairs{int(big.loc[mask, "n_rows_i"].sum()):>14,} rows')
        for label, mask in (('pattern only', pub & ~atc & ~excl), ('ATC only', atc & ~pub)):
            for r in big[mask].sort_values('n_rows_i', ascending=False).head(6).itertuples():
                rep.append(f'      {g} {label}: {r.ingredient_name!r}  {r.n_pat} patients, {r.n_rows} rows')
    un = big[big.status.isin(['unmapped', 'partial', 'no_ingredient'])].sort_values('n_rows_i', ascending=False)
    un[['drug_code', 'ingredient_name', 'status', 'n_rows', 'n_pat']].to_csv(unmapped_out, index=False, encoding='utf-8-sig')
    rep.append(f'  not (fully) mapped: {len(un):,} pairs -> {os.path.basename(unmapped_out)}; the 25 most frequent:')
    rep += [f'    {r.ingredient_name!r} [{r.status}] {r.n_pat} patients, {r.n_rows} rows' for r in un.head(25).itertuples()]
    rep.append(f'  ATC supplement (maps/atc_supplement.csv, read by P3 into the site vocabulary): {len(supplement)} ingredient(s)'
               + ''.join(f'; {r.ingredient_name} -> {r.atc_code}' for r in supplement.itertuples()))
    rep.append('')
    return m, supplement


# ───────────────────────── diagnoses ─────────────────────────
DX_COLS = ['icd10_code', 'condition_concept_id', 'domain_id', 'source_concept_id', 'source']
KIDNEYDS_LABEL = 'KIDNEYDS'      # = the label of maps/raw_layout.json dx.events
CTRL = ('_x000D_', '\r', '\n', '\t')


def dx_text(name):
    """A diagnosis name without Excel / line-break artefacts (what the map stores; P3 reduces names to letters and digits anyway)."""
    s = str(name)
    for c in CTRL:
        s = s.replace(c, ' ')
    return re.sub(r'\s+', ' ', s).strip()


def dx_clean(name):
    """Normalised text of a diagnosis name: artefacts and possessive 's out, lower case, punctuation out, spaces collapsed."""
    s = re.sub(r"[\u2019']s\b", '', dx_text(name).lower())
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9\s]', ' ', s)).strip()


# Abbreviations that are the whole name of a diagnosis (expanded before matching; the long form is looked up in the vocabulary)
DX_ABBR = {'crf': 'chronic renal failure', 'ckd': 'chronic kidney disease', 'esrd': 'end stage renal disease', 'eskd': 'end stage renal disease',
           'esrf': 'end stage renal disease', 'dm': 'diabetes mellitus', 'htn': 'hypertension', 'niddm': 'non insulin dependent diabetes mellitus',
           'iddm': 'insulin dependent diabetes mellitus', 'aki': 'acute kidney injury', 'gn': 'glomerulonephritis',
           'adpkd': 'autosomal dominant polycystic kidney disease', 'igan': 'iga nephropathy', 'capd': 'continuous ambulatory peritoneal dialysis'}

# The v205 cohort reads: entry = CKD (46271022 with descendants); exclusion = dialysis / kidney transplant (4032243, 4146536, 4322471, 199991
# with descendants). P4's History flags do not use these concepts: they read the diagnosis text as the published pipeline does.
# PRIORITY rules run before the vocabulary lookup (a name that carries two facts), FALLBACK rules after it (a name the vocabulary does not
# know). A rule is (regex on the normalised text, [SNOMED concept names], excluded regex); a name can get a Condition and a Procedure.
PRIORITY_RULES = [
    (r'(kidney|renal) transplant\w*.*(rejection|failure|dysfunction|disorder)|(rejection|failure|dysfunction).*(kidney|renal) transplant',
     ['Disorder of transplanted kidney'], ''),
    (r'(end stage|esrd|esrf|eskd).*dialysis|dialysis.*(end stage|esrd)', ['End-stage renal disease', 'Renal dialysis'], ''),
]
FALLBACK_RULES = [
    (r'(kidney|renal) transplant|transplantation of (the )?kidney|^kt$', ['Transplant of kidney'], r'liver|lung|heart|bone marrow|cornea|pancrea'),
    (r'continuous ambulatory peritoneal dialysis', ['Continuous ambulatory peritoneal dialysis'], ''),
    (r'peritoneal dialysis|^capd$|^apd$', ['Peritoneal dialysis'], ''),
    (r'hemodialysis|haemodialysis|^hd$', ['Hemodialysis'], ''),
    (r'dialysis', ['Renal dialysis'], r'catheter|access|shunt|fistula|graft|peritonitis|related|amyloid'),
    (r'end stage (renal|kidney)|esrd|esrf|eskd', ['End-stage renal disease'], ''),
    (r'chronic (kidney|renal)|^ckd$|^crf$|renal insufficiency', ['Chronic kidney disease'], r'acute|transplant'),
    (r'diabet\w*.*(nephropath|kidney|renal)|(nephropath|kidney|renal).*diabet', ['Disorder of kidney due to diabetes mellitus'], ''),
    (r'type 1 diabetes|^insulin dependent diabetes|iddm', ['Type 1 diabetes mellitus'], r'non insulin'),
    (r'type 2 diabetes|non insulin dependent diabetes|niddm', ['Type 2 diabetes mellitus'], ''),
    (r'diabet|mellitus', ['Diabetes mellitus'], r'insipidus|gestational'),
    (r'hypertensi|high blood pressure', ['Hypertensive disorder'], r'pulmonary|portal|ocular|intracranial|gestational|pregnan|retinopathy'),
    (r'glomerulonephritis|nephritic', ['Glomerulonephritis'], ''),
    (r'nephrotic', ['Nephrotic syndrome'], ''),
    (r'iga nephropathy|^igan$', ['IgA nephropathy'], ''),
    (r'alport', ['Alport syndrome'], ''),
    (r'disorder of kidney and ureter', ['Disorder of kidney and/or ureter'], ''),
    (r'cirrhosis', ['Cirrhosis of liver'], ''),
]


def dx_rule(text, rules):
    for rx, targets, excl in rules:
        if re.search(rx, text) and not (excl and re.search(excl, text)):
            return targets
    return None


def build_dx(cat, voc, rep):
    cat = cat.copy()
    cat['text'] = cat['dx_name'].map(dx_text)
    cat['key'] = cat['dx_name'].map(dx_clean).map(lambda k: DX_ABBR.get(k, k))
    for c in ('n_rows_xlsx', 'n_pat_xlsx', 'n_rows_basics', 'n_pat_basics'):
        cat[c + '_i'] = cat[c].map(lambda v: num(v) or 0)
    cat['pat'] = cat[['n_pat_xlsx_i', 'n_pat_basics_i']].max(axis=1)
    cat['rows'] = cat['n_rows_basics_i'].where(cat['n_rows_basics_i'] > 0, cat['n_rows_xlsx_i'])
    g = cat.groupby('key', as_index=False).agg(pat=('pat', 'max'), rows=('rows', 'sum'))
    g['rep_name'] = g['key'].map(cat.sort_values('pat', ascending=False).drop_duplicates('key').set_index('key')['text'])
    lut = voc.dx_lookup()
    concepts = {}

    def target(name):
        if name not in concepts:
            concepts[name] = voc.concept_by_name(name)
        return concepts[name]

    mapped, how = {}, []
    for r in g.itertuples():
        out, status = [], ''
        for rules, tag in ((PRIORITY_RULES, 'rule'),):
            tg = dx_rule(r.key, rules)
            if tg:
                out = [(c[0], c[2], f'rule: {n}') for n in tg for c in [target(n)] if c]
                status = tag if out else 'rule_missing'
        if not out:
            cands = lut.get(r.key, [])
            for src in ('SNOMED name', 'SNOMED synonym', 'ICD10/KCD7 name'):
                ids = sorted({(c, d) for c, d, s_ in cands if s_ == src})
                if ids:
                    if len({c for c, _ in ids}) == 1:
                        out = [(ids[0][0], ids[0][1], f'exact: {src}')]
                    break
            if out:
                status = 'exact'
            elif len({c for c, _, _ in cands}) > 1:
                status = 'ambiguous'
        if not out and status != 'ambiguous':
            tg = dx_rule(r.key, FALLBACK_RULES)
            if tg:
                out = [(c[0], c[2], f'rule: {n}') for n in tg for c in [target(n)] if c]
                status = 'rule' if out else 'rule_missing'
        how.append(status or 'unmapped')
        mapped[r.key] = out
    g['how'] = how
    # one row per spelling in the catalogue: P3 reduces a name to its letters and digits, and spellings that differ there (possessive 's,
    # a numeral) need a row each
    rows, seen = [], set()
    for r in cat.itertuples():
        for cid, dom, src in mapped.get(r.key, []):
            k = (C.norm_icd(r.text), cid, dom)
            if k in seen or not C.norm_icd(r.text):
                continue
            seen.add(k)
            rows.append({'icd10_code': r.text, 'condition_concept_id': cid, 'domain_id': dom, 'source_concept_id': '',
                         'source': f'P2 {TODAY}: diagnosis name, {src}'})
    ck = target('Chronic kidney disease')
    if ck:        # the first kidney-disease diagnosis date of the DIAGNOSIS sheet (column ...KIDNEYDS) enters P3 as an event with this label
        rows.append({'icd10_code': KIDNEYDS_LABEL, 'condition_concept_id': ck[0], 'domain_id': ck[2], 'source_concept_id': '',
                     'source': f'P2 {TODAY}: label of the sheet column KIDNEYDS (first kidney-disease diagnosis of the extract), read as the CKD diagnosis'})
    m = pd.DataFrame(rows, columns=DX_COLS)
    tot_rows = int(g.rows.sum())
    rep += ['## diagnoses (dx_map.csv; the key is the diagnosis NAME, the extract has no ICD-10 code)',
            f'  catalogue: {len(cat):,} spellings of names with >= {L.MIN_CELL} patients -> {len(g):,} distinct names after clean-up (artefacts, '
            f"possessive 's, punctuation, case); {len(m):,} map rows, one per spelling and concept"]
    rep.append(f'  {"how":<14}{"names":>8}{"rows":>16}{"share of rows":>16}')
    for h, gg in g.groupby('how'):
        rep.append(f'  {h:<14}{len(gg):>8,}{int(gg.rows.sum()):>16,}{pct(gg.rows.sum(), tot_rows):>16}')
    rep.append(f'  map rows by target domain: {m.groupby("domain_id").size().to_dict()}')
    for label, rx in (('CKD (entry) names', r'chronic kidney|chronic renal|end stage|\bckd\b|\bcrf\b|esrd'),
                      ('dialysis / transplant names', r'dialysis|transplant')):
        sel = g[g.key.str.contains(rx, regex=True)].sort_values('pat', ascending=False)
        rep.append(f'  {label} ({len(sel)} names; the 10 most frequent, mapped to):')
        for r in sel.head(10).itertuples():
            tg = '; '.join(f"{d}:{c}" for c, d, _ in mapped.get(r.key, [])) or 'unmapped'
            rep.append(f'    {r.rep_name!r}  {int(r.pat):,} patients -> {tg}')
    un = g[g.how.isin(['unmapped', 'ambiguous', 'rule_missing'])].sort_values('pat', ascending=False)
    rep.append(f'  not mapped: {len(un):,} names; the 30 most frequent:')
    rep += [f'    {r.rep_name!r} [{r.how}] {int(r.pat):,} patients' for r in un.head(30).itertuples()]
    rep.append('')
    return m, un


# ───────────────────────── main ─────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='lab,drug,dx')
    ap.add_argument('--vocab', default=os.path.join(L.BASE, 'data', 'vocab', 'athena'), help='Athena vocabulary folder (P0)')
    ap.add_argument('--maps', default=C.MAPS)
    ap.add_argument('--p1', default=None, help='folder with the p1_catalog_*.csv files (default: the out folder)')
    a = ap.parse_args()
    out = C.out_dir()
    p1 = a.p1 or out
    todo = set(a.only.split(','))
    os.makedirs(a.maps, exist_ok=True)
    voc = Vocab(a.vocab)
    rep = ['# P2 mapping report (aggregates only)', f'vocabulary: {a.vocab}', f'catalogues: {p1}', '']
    done = {}
    if 'lab' in todo:
        cat = read_catalog(os.path.join(p1, 'p1_catalog_lab.csv'))
        if cat is None:
            sys.exit('out/p1_catalog_lab.csv not found: run P1 first')
        m = build_lab(cat, voc, rep)
        m.to_csv(os.path.join(a.maps, 'lab_map.csv'), index=False, encoding='utf-8')
        done['lab'] = len(m)
    if 'drug' in todo:
        cat = read_catalog(os.path.join(p1, 'p1_catalog_drug.csv'))
        if cat is None:
            sys.exit('out/p1_catalog_drug.csv not found: run P1 first')
        m, supplement = build_drug(cat, voc, rep, os.path.join(out, 'p2_unmapped_drug.csv'))
        m.to_csv(os.path.join(a.maps, 'drug_map.csv'), index=False, encoding='utf-8')
        supplement.to_csv(os.path.join(a.maps, 'atc_supplement.csv'), index=False, encoding='utf-8')
        done['drug'] = len(m)
        done['atc_supplement'] = len(supplement)
    if 'dx' in todo:
        cat = read_catalog(os.path.join(p1, 'p1_catalog_dx.csv'))
        if cat is None or 'dx_name' not in cat.columns:
            rep += ['## diagnoses (dx_map.csv)', '  not built: out/p1_catalog_dx.csv is missing or has no diagnosis-name layout (re-run P1)', '']
        else:
            m, un = build_dx(cat, voc, rep)
            m.to_csv(os.path.join(a.maps, 'dx_map.csv'), index=False, encoding='utf-8')
            un[['rep_name', 'how', 'pat']].rename(columns={'rep_name': 'dx_name', 'pat': 'n_pat'}).to_csv(
                os.path.join(out, 'p2_unmapped_dx.csv'), index=False, encoding='utf-8-sig')
            done['dx'] = len(m)
    C.write_text(os.path.join(out, 'p2_report.txt'), rep)
    if {'lab', 'drug', 'dx'} <= set(done):
        C.write_text(os.path.join(a.maps, 'P2_DONE.txt'), [f'P2 finished {TODAY}: lab_map {done["lab"]:,} rows, drug_map {done["drug"]:,} rows, '
                                                           f'dx_map {done["dx"]:,} rows; atc_supplement {done.get("atc_supplement", 0)} row(s); catalogues in {p1}'])
        done['P2_DONE'] = 1
    print('P2 maps written:', ', '.join(f'{k} {v:,} rows' for k, v in done.items()), '->', os.path.relpath(a.maps, L.BASE))


if __name__ == '__main__':
    L.guard(main)
