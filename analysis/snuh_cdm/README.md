# analysis/snuh_cdm — SNUH CKD extract → OMOP CDM v5.3, three virtual-site DuckDBs

Purpose: preparatory work for a federated-learning benchmark. The SNUH CKD CDW extract (already
held under DRB-E(I)-2025-08-01, use period to 2027-12-31) is mapped to OMOP CDM by the research team
and split by patient into three virtual hospitals, each its own CDM. Each site then runs the
ATLAS cohort (v205) and the 36-feature extraction locally. Not a re-extraction from the CDW and not
the hospital's institutional CDM.

## Decisions (user, 2026-10-07)

| | |
|---|---|
| site split | **fixed** physical split: one B1 (equal) and one B2 (50/30/20 %, Dirichlet α 0.5 baseline-eGFR mix); MIA repetitions vary model seeds only |
| CDM scope | **minimal**: PERSON, OBSERVATION_PERIOD, VISIT_OCCURRENCE (minimal), CONDITION_OCCURRENCE, MEASUREMENT, DRUG_EXPOSURE. FUN/RAD reports excluded |
| storage | **one DuckDB file per site** (SqlRender/DatabaseConnector can run the v205 cohort SQL) |

## State of existing assets (survey 2026-10-07, code/docs only)

- No OMOP vocabulary on disk → P0.
- No code-level map exists. Feature-level concept ids are in KRCP Supplementary Table S1 — **several are
  wrong** (Phosphorus, Uric acid, Total protein, GGT point at other tests; see `maps/README.md`), so P4 uses
  LOINC codes instead. Lab test-name lists for 23 variables in `SNUH_CKD_DATAPREP.ipynb` (`lab_config`,
  now the seed of `maps/lab_map.csv`); drug parser and an RxNorm/ATC mapper that has never run
  (`Code\SNUHUB\drug_dictionary.py`, `map_rxnorm_atc`).
- Published History_* flags came from English diagnosis text, not ICD codes; DIAGNOSIS_ICD10.xlsx
  was never read by any code.
- Not in the extract: death, blood pressure, smoking, dialysis/transplant procedures, BMI (the published
  BMI came from `BMI_Total.parquet`, which exists only on SNUHUB). ESRD stays eGFR < 15 as in the published
  pipeline.

## Steps

| step | what | who runs | output |
|---|---|---|---|
| P0 | Athena vocabulary (SNOMED, LOINC, UCUM, ICD10/KCD7, RxNorm, RxNorm Extension, ATC, Type Concept, Visit, Gender) → `data/vocab/athena/` | user (Athena login + licence) | — |
| P1 | `p1_profile_extract.py`: schema + code catalogs (lab name × unit, drug name; ICD-10 codes, or diagnosis names when the sheet has no ICD-10 column), counts < 11 suppressed | user | `out/p1_*` |
| P2 | `p2_build_maps.py`: mapping tables (lab → LOINC/UCUM, diagnosis → SNOMED, ingredient → RxNorm) from vocabulary + P1 catalogs, entries with >= 11 patients; schema and method in `maps/README.md` | Claude (no patient data; user decision 2026-10-14: inside the exemption scope) | `maps/*.csv`, `out/p2_report.txt` |
| P3 | `p3_build_cdm.py`: ETL of every patient → central CDM, fixed split → 7 DuckDBs | user | `data/ckd_pilot/cdm/*.duckdb`, `out/p3_*` |
| P4 | `p4_site_features.py`: per site v205 cohort + 36 features; pilot matrix; `--agreement` with v1.3 | user | `data/ckd_pilot/matrix_snuh_cdm.parquet`, `out/p4_*` |
| P5 | `analysis/snuh_pilot/run_pilot.py --tag cdm` (fixed sites) | user | pilot `out/snuh_cdm/` |

All SNUH-reading steps require this study's IRB exemption number (`--irb E-NNNN-NNN-NNNN`); without it they
stop before opening any file. Claude reads only `out/` and `maps/` (code catalogs and mapping tables, no
patient rows) and the vocabulary (no patient data).

## Where the extract is read from

IRB number of this study: E-2610-060-1785. P1 is the only step inside the approved plan v1.0; P3 onwards wait for the change review v1.1.

- **Parquet tables** (BASICS, LAB-1, LAB-2, DRUG) and the files under `ML\` are CKD_ML's derived files, read in place and read-only
  (`pilot_lib.CKD_ROOT`, default `[EARLY_ADOPTER] CKD_ML\PROJECT`; override with `PILOT_CKD_ROOT`).
- **Raw files** (the diagnosis and RID xlsx): one copy, `<extract-folder>\`, found by
  `pilot_lib.raw_xlsx_dir` in this order: `PILOT_CDW_DIR`, `<CKD_ROOT>\Data\CSV`, the folder above, the old `data\ckd_cdw`.
  `p1_schema.txt` starts with the two folders that were used. The copy is made once with `relocate_cdw.ps1` (compare SHA256, then
  `-Execute` to move; it never deletes).

## Run (after IRB exemption; venv from analysis/snuh_pilot/README.md)

    $py = "python"
    $d  = "<repo>\analysis"
    & $py "$d\snuh_cdm\p1_profile_extract.py" --irb E-2610-060-1785
    & $py "$d\snuh_cdm\p3_build_cdm.py"       --irb E-2610-060-1785
    & $py "$d\snuh_cdm\p4_site_features.py"   --irb E-2610-060-1785 --agreement
    & $py "$d\snuh_pilot\run_pilot.py" --dataset snuh --tag cdm --irb E-2610-060-1785

P3 options: `--vocab DIR` (default `data/vocab/athena`), `--maps DIR`, `--site-scope mapped` (leave
concept-0 measurement/drug rows out of the site DBs; central keeps everything — saves disk, the LAB files are
11 GB), `--date-range LO:HI` (default 2000-01-01:2025-07-31, the approved data period of DRB-E(I)-2025-08-01: events outside are
dropped and counted in `out/p3_build_cdm.txt`; the extract itself spans 1995-03..2025-10). P3 rebuilds all DuckDBs from scratch on every run. P4 options: `--baseline pre`,
`--window all`, `--rrt-icd Z49,Z99.2,Z94.0`, `--dbs B1_0 …`, `--v13-matrix`, `--matrix-out`.
Errors print the exception type and code location only (`PILOT_DEBUG=1` shows the message locally), except
raw-layout errors, which name the missing column and list the columns found.

## P3 — what it builds

| file (restricted, `data/ckd_pilot/cdm/`) | content |
|---|---|
| `_central.duckdb` | every patient of the extract (BASICS ∪ LAB ∪ DRUG ∪ DIAGNOSIS with a valid birth year), global person_ids |
| `site_B1_{0,1,2}.duckdb`, `site_B2_{0,1,2}.duckdb` | the two fixed splits; fresh person_ids 1..n and event ids per file |
| `holdout.duckdb` | the published 30 % validation patients (common validation set, in no site) |
| `crosswalk.parquet` | RID ↔ global person_id, group (train / val / other), site_b1, site_b2 — **never copy out** |
| `crosswalk_sites.parquet` | db, global person_id, site person_id |

Each DuckDB holds PERSON, OBSERVATION_PERIOD, VISIT_OCCURRENCE, CONDITION_OCCURRENCE, PROCEDURE_OCCURRENCE,
MEASUREMENT, DRUG_EXPOSURE, CONCEPT, CONCEPT_ANCESTOR, CONCEPT_RELATIONSHIP (`Maps to`), CDM_SOURCE.

Design decisions:

- **Hold-out.** The published split is rebuilt exactly as `00_build_matrix.py` does (Base.csv row order,
  `train_test_split(test_size=0.3, stratify=Outcome_40, random_state=42)`, asserts 19,746 / 8,463).
  Published-train patients are split into sites with `pilot_lib.scenarios(train_idx, stratum, 42)` itself, so
  B1/B2 are the pilot's seed-42 sites (stratum = published Baseline_eGFR stage). Validation patients go only
  to `holdout.duckdb`. Patients outside the published cohort go to a random site (B1 uniform, B2 with
  p = 0.5/0.3/0.2, seed 1042), so each site holds a hospital-like population and runs the cohort itself.
  Persons that v205 selects but the published cohort did not are training data of their site.
- **PERSON.** year/month of birth and sex from BASICS (mode per patient; `M/남/1` → 8507, `F/여/2` → 8532,
  else 0). No source id in PERSON (person_source_value NULL). Patients without a valid birth year are dropped
  (CDM requires it; counted).
- **VISIT_OCCURRENCE.** One row per patient × BASICS 내원일자 (× visit type if a type column exists:
  입원 → 9201, 응급 → 9203, 외래 → 9202). Without a type column every visit is 9202 Outpatient (an
  assumption: no visit-type column is known yet; change `cdm_lib.DEFAULT_VISIT_CONCEPT` or add the column
  in `maps/raw_layout.json` after P1). Visits are not used by v205 or the features (only for the observation
  period and the agreement's "first visit" index). Clinical rows carry no visit_occurrence_id.
- **OBSERVATION_PERIOD.** First to last event *start* date over all tables (a prescription's end date can
  run past the extract).
- **CONDITION / PROCEDURE.** Diagnosis codes routed by the domain of their mapped concept: Procedure-domain
  codes (e.g. Z49 dialysis encounters) go to PROCEDURE_OCCURRENCE. Other-domain codes stay condition rows
  with concept 0. Source code always in `*_source_value`.
- **MEASUREMENT.** value_as_number = numeric 검사결과 × multiplier + offset (non-numeric → NULL, raw text in
  value_source_value). No range filtering here.
- **DRUG_EXPOSURE.** start = 처방일자, end = start + max(투약일수, 1) − 1 (0 days = one day, as
  drug_dictionary), days_supply = 투약일수, one row per ingredient. PRN → `sig = 'PRN'`. Products flagged
  `exclude` in drug_map → concept 0, `route_source_value = 'excluded:<reason>'`.
- **Unmapped** → concept 0, source values kept, listed in `out/p3_unmapped_*.csv`.
- **Vocabulary subset.** Concepts used in the data, the v205 / feature / ATC concepts, all their ancestors;
  CONCEPT_ANCESTOR rows whose descendant is kept; `Maps to` rows into kept concepts — enough for circe-style
  concept sets with descendants.
- Event ids come from `row_number()` and are not stable across rebuilds; nothing downstream depends on them.

## P4 — cohort and features

`sql/v205_cohort_duckdb.sql` is a hand translation of the circe 1.11.1 rendering of
`Cohort_OHDSI_CKD_v205.json` (same concept sets incl. descendants and `Maps to`, observation window 0/730,
first qualifying event, four inclusion rules, end = index + 730). It writes `cohort` and `cohort_inclusion`
into each site DuckDB; the report gives the attrition per rule (compare with the ATLAS Inclusion Report).

- **RRT.** The extract has no procedure table, so the v205 RRT rule sees only (a) diagnosis codes whose map
  points to the Procedure domain (routed by P3) and (b) conditions under 199991. Default = pure v205. The
  report counts cohort members with Z49 / Z99.2 / Z94.0 / T86.1 / N18.6 on/before index; `--rrt-icd` turns
  chosen prefixes into an extra exclusion (decision for the user after the first run).
- **Features** = v1.3 definitions (model card): baseline lab = closest to index on either side (ties: earlier
  date, then lower value — value-based so every site and rebuild agree), lab_config ranges, UACR rule,
  CKD-EPI 2021, 2-point slope, outcome ≥ 40 % decline or < 15 within 730 d, drugs = union of prescription
  days up to and including index for ingredients under ATC C09A/C09C and C10AA (distinct (start, end) rows, so
  the block sorts are total). History_* from ICD-10
  source codes (S1 ranges) on/before index; BMI = mean on/before index (`--window all` = whole record, as
  published). See the docstring of `p4_site_features.py`.
- **Pilot matrix** `data/ckd_pilot/matrix_snuh_cdm.parquet` (+ `.meta.json`, `fixed_sites: true`): B1-site
  cohort rows (split = train) + holdout cohort rows (split = val), columns as `00_build_matrix.py` plus
  `site_b1`, `site_b2`. No ids. B2 sites are recomputed and must give bit-identical features (checked).
- **Agreement** (`--agreement`): CDM rows ↔ v1.3 matrix rows through the crosswalk (RID); cohort overlap,
  CDM index vs first BASICS visit, per feature n / missing / Pearson or kappa / Spearman / median |Δ| /
  exact share (overall and among persons with the same index). Uses `data/ckd_pilot/matrix_snuh.parquet`
  (pilot step 00) or builds it with `00_build_matrix.build_snuh()`.
- **Cohort rules** (`--entry`, 2026-10-15). `ckd` (default) is `sql/v205_cohort_duckdb.sql`, ATLAS v205 as shared with CKD_ML: index = first CKD
  diagnosis with 730 d of observation after it, >= 2 serum creatinine in index +0..+730 d. `visit` is `sql/v205_firstvisit_cohort_duckdb.sql`, the
  rules that built the published 28,209-person cohort (`SNUH_CKD_DATAPREP.ipynb`, step 1: index = first visit, adults, >= 2 creatinine records whose
  first and last dates are >= 730 d apart, measured on the creatinine record and not after the index) with the v205 age rule and the v205
  exclusions (RRT before the index, impossible K / Hb in the year before); a CKD record is not required (the extract is a CKD cohort by selection;
  the report counts the members without one). `visit` writes `features_visit/`, `data/ckd_pilot/matrix_snuh_cdmv.parquet` (`PILOT_TAG=cdmv`) and
  `out/p4_*_visit.txt`; the default outputs stay. The site databases hold the `cohort` table of the last run.
- Every report has a section "baseline creatinine and eGFR_Slope availability" (counts only): where the baseline creatinine lies relative
  to the index, how many persons have a creatinine on or before the index and one >= 90 d before the baseline creatinine.

## P5 — hook in analysis/snuh_pilot (backward compatible)

`run_pilot.py --tag cdm` sets `PILOT_TAG=cdm`: `pilot_lib.matrix_path('snuh')` → `matrix_snuh_cdm.parquet`,
work/out folders `snuh_cdm[_quick]`, step 00 skipped (matrix must exist). When the matrix meta says
`fixed_sites`, `pilot_lib.scenarios()` returns the fixed B1/B2 sites for every seed (A, A′ unchanged) and
`size_classes()` sizes the B2 shadows to the actual sites. Without `--tag` nothing changes (checked against
the pre-edit `pilot_lib.py`).

## Tests (public / generated data only)

    python analysis\snuh_cdm\tests\run_tests.py            # ~30 s; work dir $env:CDM_TEST_DIR or %TEMP%\snuh_cdm_tests

- `cohort`: hand-made mini CDM, every v205 branch (window, age, Cr count incl. same-day pairs, RRT before /
  after index / before observation, K/Hb unit and window, NULL values, descendants, deprecated concepts).
- `synthea`: Synthea27Nj reverse-mapped into the raw layout (mojibake column names) → P3 round-trip counts,
  site partitions, fresh ids, IRB and layout guards → P4.
- `synthetic`: 400 generated CKD-like patients → P3 → P4; cohort, index dates and all 36 features + y equal an
  independent pandas port of DATAPREP / retrain_v13 / compute_exposure run on the raw tables; agreement mode;
  no source id in `out/`.
- `hook`: PILOT_TAG paths, fixed sites, unchanged default behaviour (set `PILOT_LIB_ORIG` to a copy of the
  original `pilot_lib.py` to run that last check).
- `p1`, `p2`, `names`: the real extract layout seen on 2026-10-14 (name-only diagnosis sheet, empty BASICS birth) through the profile, the
  maps and P3 → P4 on generated data (see the docstring of `tests/run_tests.py`).
- `drugdays`: `drug_days` against a brute-force union of generated prescription intervals (duplicate rows, PRN, rows after the index), same
  rows in two shuffled orders with 4 threads (fails without the `DISTINCT`).

## Date window (user decision 2026-10-14)

The extract holds records outside the approved data period of DRB-E(I)-2025-08-01 (2000-01-01..2025-07-31): labs from 1999-09,
labs and drugs to 2025-10, first-diagnosis dates from 1995-03. Every SNUH-reading step cuts to the approved period:
`pilot_lib.DRB_DATE_RANGE` is the default of P1 and P3 (`--date-range LO:HI` overrides; tests and public data use it). P1 profiles only
the rows inside the window and reports how many rows lie outside; P3 drops events outside and counts them per table. The event date
of a table is the date P3 cuts on (BASICS 내원일자, DRUG 처방일자, LAB 검사시행일, DIAGNOSIS 진단일자_OTHER); the first-diagnosis
date (KIDNEYDS) and birth are not event dates. P4 inherits the cut through the CDM, so the cohort and the agreement with the published
v1.3 matrix, which used all dates, will differ for patients whose records lie outside the window.

## What P1 showed (2026-10-14; `out/p1_schema.txt`, `out/p1_catalog_*.csv`; second run inside the date window with the name catalogue)

- BASICS (CKD_ML parquet): 2,629,061 rows, 37,885 patients, median 24 rows and 18 visit dates per patient. Columns: patient id, 환자명 (a
  name field with 170 distinct values; no code reads it and P1 never catalogues it), 성별, 생년월일 (**100 % null**; the SNUHUB `Birth`
  the published pipeline used is not in this copy), 병원코드 (one value), 내원일자 (2010-01..2025-07), 기타진단일자 (8,648 distinct dates,
  1995-03..2025-07, the same number as the KIDNEYDS dates of the sheet), 기타진단명 (5,634 names). No visit-type, height, weight or BMI.
- DIAGNOSIS_ICD10.xlsx: 60,243 rows (median 1 per patient), 37,885 patients. Columns: patient id, 환자명, 성별, 생년월일 (YYYYMM, no null,
  one value per patient), 진단일자_OTHER (one date per patient), 진단일자_KIDNEYDS (**one date per patient**, 1995-03..2025-07; never after
  the OTHER date: before for 31,048 patients, the same day for 6,837), 진단명_OTHER (5,634 names). **No ICD-10 code column.** The names
  are English and clinician-typed (case variants, abbreviations such as CRF / CKD, Excel `_x000D_` and `\r\n` artefacts); 737 spellings
  are carried by at least 11 patients and cover about 80 % of the rows. 5,632 names are the same in the sheet and in BASICS.
- Window 2000-01-01..2025-07-31: rows outside it are 526,100 of the drug rows (1.3 %), 189,903 of LAB-1 (20 %, the file begins 1999-09)
  and 1,686,227 of LAB-2 (1.2 %); BASICS and the sheet have none. 8,799 sheet rows carry a KIDNEYDS date before 2000.
- LAB: 2,764 test × unit pairs in the window. Every laboratory model input has a source test (UACR = "Microalbumin/Creatinine Ratio
  (random urine)", unit empty). No height, weight or BMI test.
- DRUG: 12,271 code × name pairs; ACE inhibitors, ARBs and statins are present.
- The published pipeline (`SNUH_CKD_DATAPREP.ipynb`) set the **index date to the first visit** (min 내원일자), took age from `Birth`, flagged
  History_* by text search on the diagnosis column over the whole record, and never used the sheet or an ICD-10 code.

What this means for the CDM version, as built (generated data only; P3 onwards waits for the change review v1.1):

1. PERSON: birth year/month and sex come from the sheet when BASICS has none (`dx.birth`, `dx.sex` in the layout); P3 would otherwise
   drop every person.
2. CONDITION: the sheet column KIDNEYDS is read as the first CKD diagnosis (the DRB extract is a CKD cohort): one event per patient under the
   label `KIDNEYDS`, mapped to CKD 46271022 (`dx.events`). The diagnosis names come from the visit-level BASICS rows with the visit date
   (`dx.basics_name`, `dx.basics_date`; the sheet's own OTHER rows duplicate them). `maps/dx_map.csv` is keyed by the name. P3 reduces a name
   to letters and digits (`condition_source_value` keeps the text, line breaks and the Excel artefact blanked).
3. P4: when CDM_SOURCE says `dx_layout=names`, History_* are the text patterns of the published pipeline on the source text, and the RRT
   report counts dialysis / transplant names. The v205 RRT exclusion works through the mapped procedure concepts (hemodialysis, peritoneal
   dialysis, kidney transplant) and 'Disorder of transplanted kidney'.
4. BMI is absent; P4 BMI stays missing.
5. The date window removes the CKD event of the patients whose KIDNEYDS lies before 2000; they enter the cohort only through a CKD-named
   diagnosis inside the window, and the cohort index date (first CKD diagnosis) differs from the published index (first visit) anyway. The
   P4 agreement report quantifies both.

`maps/raw_layout.json` holds this layout for the real extract. Test group `names` runs it end to end on generated data (cohort equal to the
reference of the codes version, History flags from the text, the rows before 1998 cut).

## What P3 and P4 showed (2026-10-14, `run_snuh.ps1 -Stage cdm`, 15.5 + 4.3 min; `out/p3_build_cdm.txt`, `out/p4_site_features.txt`, `out/p4_agreement.txt`)

P3 (inside the approved period, vocabulary subset with 6,007 concepts):
- 37,885 persons (the extract has 37,886; fewer than 11 without a birth year). Central CDM rows: visits 1,539,147, conditions 2,580,694,
  procedures 82,464, measurements 142,655,565, drug exposures 40,048,184. Rows outside the period were dropped: 1,876,130 lab, 526,100 drug,
  4,663 diagnosis.
- Mapped to a standard concept (rows): conditions 68.5 %, drugs 70.8 % (7,272,722 drug rows are investigational / fluid / topical products and
  keep concept 0; 6,673,229 PRN rows are kept with sig = PRN), procedures 100 %, measurements 24.3 % (39 of 2,781 test × unit pairs, exact rows
  only: the rest are tests that are not model inputs). `-Stage cdm` writes only mapped measurements and drugs to the site databases.
- Split as published: 28,209 = train 19,746 / val 8,463, all in the extract. Site databases: B1 9,792 / 9,803 / 9,827 persons, B2 14,805 /
  8,734 / 5,883, holdout 8,463.

P4 (v205 cohort per site database, 36 features):
- Cohort per site: B1 4,449 / 4,603 / 4,508, B2 6,988 / 3,875 / 2,697 (the same 13,560 persons as B1), holdout 5,497. Pilot matrix 19,057 rows
  (train 13,560, val 5,497), outcome rate 35.7 %. The rule that removes the most is `>= 2 creatinine in 0..730 d after index`
  (1,523-2,222 persons per site fail it alone), then age >= 19 (126-566), RRT (19-86), implausible K/Hb (< 11). Dialysis / transplant names on
  or before the index: < 11 persons.
- Missing before imputation: BMI 100 %, eGFR_Slope 97-98 %, GGT 35-38 %, UACR / urine microalbumin 36-43 %, HbA1c 18-24 %, HDL 10-12 %,
  TG 9-12 %, every other feature <= 2 %.
- **Fixed in this run:** B1 and B2 copies of the same person differed in `Dur_ACE_ARB_days` (up to 61 d, fewer than 11 persons). Cause:
  `drug_days` built the prescription blocks with two windows over the same `ORDER BY s, e`; exact duplicate rows at the start of a block could
  fall into the previous block in the second sort (multi-threaded DuckDB, another row order in the other site database), and the overlap was
  counted twice. `iv` is now `SELECT DISTINCT`. Generated data: 30 of 60,000 persons off by up to 491 d before, 0 after (test `drugdays`).
  Consistency report now: max |Δ feature| 0, no feature differs. The report names the features that differ, with person counts.

Agreement with the published v1.3 matrix (`out/p4_agreement.txt`):
- Overlap 18,178 persons; CDM only 879; v1.3 only 10,031 (published persons who fail a v205 rule on the CDM, mostly `>= 2 creatinine in 0..730 d`).
- **The index date differs.** The CDM index is the first CKD diagnosis (KIDNEYDS / CKD-named diagnosis), the published index is the first
  visit: same day 13.7 %, within 30 d 20.0 %, CDM earlier 86.3 %, median |Δ| 1,260 d. Age and everything measured near the index follow.
- **With the same index the CDM features equal the published ones** (exact share 97.7-100 % for every feature but five), so the P2 maps and the
  P4 feature code reproduce the published pipeline. The five: Cholesterol 75.9 %, UACR 54.9 %, Bicarbonate 84.1 %, urine creatinine 95.9 %,
  eGFR_Slope 97.0 % (424 persons). Cholesterol is the documented P2 difference (the published substring rule counts LDL-cholesterol as total
  cholesterol, P2 does not). The others are unexplained; same-day duplicate values and the tie rule are the first thing to check. BMI cannot
  be compared (absent).
- eGFR_Slope (needs a creatinine >= 90 d before the baseline creatinine) is available for 424 of the 18,178 overlapping persons because the
  CDM index lies years before the first laboratory value for most persons.

### Which cohort rules: v205 as shared, or the published ones (2026-10-15)

The three runs on the real extract (counts from the reports; the published cohort is the 28,209 persons of the v1.3 matrix):

| | v205 as shared (`ckd`) | v205 rules, first visit, 730 d observation after it (tried) | published rules, first visit (`visit`, chosen) |
|---|---|---|---|
| cohort (train + val) | 19,057 (13,560 + 5,497) | 17,136 (12,197 + 4,939) | 27,228 (19,049 + 8,179) |
| overlap with the published cohort | 18,178 (64 %) | 16,578 (59 %) | 27,226 (96.5 %) |
| index the same day as the published index | 13.7 % | 100 % | 100 % |
| eGFR_Slope available | 2.3 % | 66.3 % | 76.9 % |
| outcome rate (published 34.3 %) | 35.7 % | 38.0 % | 33.4 % |

The slope is (baseline eGFR - eGFR of the latest creatinine >= 90 d before the baseline creatinine) / years, so it needs a creatinine well before
the baseline creatinine, the one nearest the index. With the first CKD diagnosis as the index the laboratory history has hardly begun (53.9 % have
a creatinine on or before the index, 2.3 % one more than 90 d before the baseline creatinine), so there is nothing to look back on. With the
first visit (BASICS visits begin in 2010-01) 96.0 % have a creatinine on or before the index and 81.0 % one >= 90 d before the baseline. The
slope code is not the cause: at the same index it agrees with the published values (exact share 96.1 %, r 0.992, 20,910 persons).

Why not "v205 rules with the first visit": the published cohort measures its two years on the creatinine record (first to last value), which
may lie before the first visit. Asking for 730 d of observation after the first visit instead drops 45 % of the persons at entry and leaves 17,136
(overlap 59 %); dropping any observation rule leaves 25,268 (overlap 74 %) with outcome windows that may be cut short. The published rules give
27,226 of 28,209 persons (96.5 %), the 983 published persons that are missing are mostly excluded by the RRT rule (the v1.0 exclusion criterion,
which the published pipeline did not apply), the impossible K / Hb rule (added in v1.1) or the serum-creatinine definition (the published code
counted every test with "creatinine" in its name).

At the same index the features agree exactly for 96.3-100 % of the persons in both cohorts for every feature but three: UACR 51.0 %,
Bicarbonate 64.7 % and Cholesterol 76.1 % (the LDL exclusion of P2). UACR and Bicarbonate are probably ties on the nearest day between a measured and a derived value
(UACR) or a serum and a point-of-care value (Bicarbonate): the published rule takes the first row in file order, P4 the lower value (not checked).
In the `visit` cohort 15 % of the members (4,074 of 27,228) have no CKD record on or before the index in the CDM: their only CKD record lies
before 2000 (outside the approved period) or their diagnosis names are not mapped to CKD.

## P4b — duckcdm cross-check of the v205 cohort (2026-10-17)

`p4b_duckcdm_cohort.py --irb ...` compiles `analysis/cohort/Cohort_OHDSI_CKD_v205.json` with
[duckcdm](https://github.com/vitaldb/duckcdm) (Hyung-Chul Lee's pure-Python port of circe-be and SqlRender, `pip install duckcdm`
in the pilot venv, 0.4.7), translates it to the DuckDB dialect and runs it on every site DuckDB next to the hand translation
`sql/v205_cohort_duckdb.sql`; both land in temp tables (the databases are not modified) and are compared person by person.
Report `out/p4b_duckcdm_cohort.txt` (counts only). The duckcdm SQL is a newer circe-be than the in-house ATLAS (1.11.1): the
concept-set descendant query, the era-collapse (window function instead of the cteEnds self-join) and the inclusion-rule
wrappers differ in text, not in logic.

What it showed (real data, the seven DuckDBs of the `ckd` entry): identical cohorts — the same persons, start and end dates in
every database (B1 4,449 / 4,603 / 4,508, B2 6,988 / 3,875 / 2,697, holdout 5,497; 0 persons in only one engine, 0 start-date
differences), 0.1–0.3 s per engine and database. The generated-data smoke test (fixtures.build_synthetic → P3 → P4b) agrees too.
So the hand translation reproduces the circe engine, and the cohort step can be run from the JSON inside a node container
without Java or WebAPI. The `visit` entry (`v205_firstvisit_cohort_duckdb.sql`) has no circe equivalent and is not covered.

## P6 — resource footprint of one node (2026-10-19, `p6_node_resources.py`, `out/p6_node_resources*.txt`)

`p6_node_resources.py --irb ... [--achilles]` measures what Table 1 of the ACI paper needs: per site DuckDB the file size,
rows per CDM table and in the vocabulary subset, wall time of the duckcdm-compiled v205 cohort (temp table, database not
modified) and the process peak working set; with `--achilles` the 110 Achilles analyses (`duckcdm.achilles`, small-cell 10)
are timed on the `duckcdm serve` copies in `data/ckd_pilot/cdm/atlas/`. Counts only, cells below 11 suppressed. Test group `p6`
(generated data → P3 → report; 7 checks).

What it showed (real data, laptop: Intel Core Ultra 7 155H, 31.6 GB, Windows 11; python 3.14.3, duckdb 1.5.2, duckcdm 0.4.7;
4 threads, memory limit 8 GB):

| DB | file (MB) | persons | visits | conditions | measurements | drug exposures | v205 cohort | compile + run (s) | peak RSS (MB) |
|---|---|---|---|---|---|---|---|---|---|
| B1_0 / B1_1 / B1_2 | 211 / 216 / 219 | 9,792 / 9,803 / 9,827 | 366–376 k | 618–647 k | 8.27–8.50 M | 6.65–7.02 M | 4,449 / 4,603 / 4,508 | 0.1 + 0.2 | 219–225 |
| B2_0 / B2_1 / B2_2 | 362 / 165 / 122 | 14,805 / 8,734 / 5,883 | 673 / 246 / 196 k | 1,134 / 437 / 327 k | 13.8 / 6.6 / 4.8 M | 12.0 / 4.9 / 3.7 M | 6,988 / 3,875 / 2,697 | 0.1 + 0.1–0.3 | ≤ 282 |
| holdout | 244 | 8,463 | 424 k | 683 k | 9.4 M | 7.8 M | 5,497 | 0.1 + 0.2 | 282 |
| central | 3,852 | 37,885 | 1,539 k | 2,581 k | 142.7 M | 40.0 M | 19,057 | 0.2 + 1.2 | 1,320 |

The vocabulary subset is the same in every file (concept 6,007, concept_ancestor 29,500). The central file holds every extract row;
the site files hold the rows whose concepts are mapped (`site_scope: mapped` in `build.json`), which is why the site measurements
sum to 60 M rather than 143 M. Achilles on a site copy: 110 analyses, 0 failures, 16–18 s, peak working set about 600 MB.
So one institutional node is a file of a few hundred MB that answers an ATLAS cohort definition in under a second and a full
Achilles characterization in under 20 s on 4 threads and well under 1 GB of memory. Building the files from the extract
(P3 + P4) took 15.5 + 4.3 min once.

## Open before the first SNUH run

1. Cohort for the pilot: `visit` (`matrix_snuh_cdmv`, `PILOT_TAG=cdmv`) is the main matrix (user 2026-10-15: consistency with the published model;
   confirmed by the numbers above); `ckd` (`matrix_snuh_cdm`) stays as the sensitivity cohort with the first CKD diagnosis as the index. The v1.1
   protocol and change table were rebuilt for this (selection criteria 1-4, index = first visit).
2. P1 once more with the BASICS date section: it tells whether 기타진단일자 is the KIDNEYDS date repeated on every row (expected) and shows
   the CKD events lost to the window. P3 uses the visit date for the names either way.
3. UACR (51.0 %) and Bicarbonate (64.7 %) agree less than the rest at the same index: look for same-day duplicate values and the tie rule
   (aggregate diagnostics in the agreement report, no rows).
4. BMI is absent locally → P4 BMI is missing for everyone unless BASICS has height/weight/BMI columns.
5. After the change review v1.1 is approved: federated learning, the pilot on the CDM matrix, the canary (`run_snuh.ps1` refuses them until
   `governance/CHANGE_REVIEW_v1.1_APPROVED.txt` exists).
