# analysis/mimic_ed — MIMIC-IV-ED analysis (credentialed data)

Data: `data/mimic-iv-ed/full-2.2/` (restricted, gitignored) and `demo-2.2/` (open, ODbL).
Loader: `safe-model-bundle/poc/src/mimic_ed_loader.py`.

## Working rule (PhysioNet DUA clause 3 + LLM guidance, since 2026-10-06)

| who | does |
|---|---|
| Claude | writes the `.py`, tests on `demo-2.2` only, reads `out/` |
| user | runs each step on `full-2.2` from PowerShell |

- Scripts write **aggregates only** to `out/` (counts, rates, medians, metrics;
  counts below 11 shown as `<11`; exception messages suppressed). Claude reads
  `out/` and nothing under `data/mimic-iv-ed/full-2.2/`.
- No script may print or write a row, an identifier (`subject_id`, `stay_id`,
  `hadm_id`), a raw value or a free-text field.

## Steps

| step | script | output |
|---|---|---|
| 01 | `01_check_release.py` — checksums + loader summary | `out/01_check_release_{full,demo}.txt` |
| matrix | `matrix_mimic_ed.py` (called by `analysis/snuh_pilot/00_build_matrix.py --dataset mimic_ed`) — one row per person (first ED stay), triage-time features, admission | `data/ckd_pilot/matrix_mimic_ed*.parquet` (restricted) |

Run from anywhere:

    python "<repo>\analysis\mimic_ed\01_check_release.py"

## Insurance cohort for the paper (analysis plan: SNUH is primary, this takes over only if SNUH is late)

`analysis/snuh_pilot/run_pilot.py --dataset mimic_ed [--tag demo|s28k] [--model xgb]` runs the pilot on MIMIC-IV-ED.
`--tag demo` = open demo-2.2 (tests, Claude may run it); `--tag s28k` = full-2.2, stratified sample of 28,209 people (same
size as the SNUH cohort; the three-gate audit); no tag = full-2.2, every person (utility, federated runs). Full runs are
the user's. If `data/mimic-iv/2.2/hosp/patients.csv.gz` exists the matrix gets `age`. The builder keeps the first stay of
each person so that one person is never in training, validation, a site and the audit sets at once; diagnosis, pyxis,
vitalsign, outtime and the chief complaint are not used. Tests: `analysis/snuh_cdm/tests/run_tests.py --only mimic`.
