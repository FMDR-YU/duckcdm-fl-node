# duckcdm-fl-node

Code, public-data demonstration and aggregate results for the paper *A single-file OMOP CDM node reproduces institutional ATLAS cohorts, matches centralized training under federated learning, and audits model export* (manuscript in preparation, 2026).

An institutional node for multi-site analysis on the OMOP Common Data Model that is one DuckDB file and one Python process:

- the OHDSI cohort, characterization and ATLAS components run in pure Python with [duckcdm](https://github.com/vitaldb/duckcdm) (SqlRender, circe-be, Achilles, WebAPI, ATLAS 3.0);
- a federated-learning client (NVIDIA FLARE 2.9, histogram-based XGBoost 3.2) sits next to the same file;
- an export gate (format, membership inference, reproduction) audits every model before it leaves, with release thresholds calibrated against planted canaries.

No patient-level data are in this repository. Every result file holds aggregates only (counts below 11 suppressed). The hospital extract, its mapping tables with local codes, and the credentialed PhysioNet data are not included.

## Quick start (public data only, no database server, no Java)

```bash
pip install duckcdm==0.4.7 duckdb==1.5.2 xgboost==3.2.0 pandas scikit-learn scipy matplotlib
python analysis/node_demo/node_demo.py            # Synthea27Nj CDM 5.4 -> DuckDB node -> two cohort definitions -> Achilles (about 10 s)
```

The demo writes `analysis/node_demo/out/node_demo_log.md` (aggregates) and `demo_cohort.json`. `analysis/node_demo/PROMPT.md` is the instruction an agent received to run the whole validation headless, with the commands it ran.

Full pipeline on the public SynPUF benchmark (download CMS DE-SynPUF 2008 sample 1 into `data/cdm/synpuf/`, see `analysis/snuh_pilot/README.md`):

```bash
python analysis/snuh_pilot/00_build_matrix.py --dataset synpuf
python analysis/snuh_pilot/run_pilot.py --dataset synpuf --model xgb          # routes A, A', site models, averaged, federated; three gates; hypotheses
powershell -ExecutionPolicy Bypass -File analysis/run_canary.ps1 -Dataset synpuf -Quick   # canary benchmark (quick); full = without -Quick
powershell -ExecutionPolicy Bypass -File analysis/federated/run_batch.ps1 -Dataset synpuf -Seeds 42 -Configs plain,krcp -Reexec   # federated jobs (Docker)
```

Tests on generated data: `python analysis/snuh_cdm/tests/run_tests.py` (no restricted data needed; the eICU and MIMIC groups use the open demo releases when present).

## Layout

| folder | content |
|---|---|
| `analysis/node_demo` | the headless node demo on OHDSI's public Synthea27Nj CDM export |
| `analysis/snuh_cdm` | extract -> OMOP CDM v5.3 -> one DuckDB file per site (P3), cohort and predictors inside each file (P4), cohort equivalence against the ATLAS SQL (P4b, duckcdm), node footprint (P6); tests and fixtures on generated data. The hospital-specific mapping tables are not included |
| `analysis/snuh_pilot` | training routes, three-gate export audit, canary benchmark, hypotheses evaluated by code, figures |
| `analysis/federated` | FLARE histogram-based XGBoost across the sites (Docker image), node isolation check (`t0/`), quantile-sketch diagnosis |
| `analysis/eicu`, `analysis/mimic_ed` | cohort adapters for eICU-CRD (real hospitals as sites) and MIMIC-IV-ED (credentialed data; the user runs them) |
| `analysis/policy_audit` | export-rule audit of research data platforms: frozen round-1 workbook, reliability script, round-2 codebook |
| `analysis/cohort` | the ATLAS cohort definition (circe JSON) and its hand translation to DuckDB SQL |
| `Figures/v2` | the figures of the paper |
| `docs` | the eICU real-site plan, the duckcdm validation note, the analysis plan and its deviation log |

## Data

- SynPUF: CMS 2008-2010 Data Entrepreneurs' Synthetic Public Use File (public).
- Synthea27Nj: OHDSI's Synthea CDM 5.4 export (public, in `data/cdm/Synthea27Nj` after download).
- eICU-CRD v2.0 and MIMIC-IV-ED v2.2: PhysioNet, credentialed access.
- The hospital extract cannot be shared.

## Changes in v0.2 (2026-10-25)

- Added the 14-hospital eICU federation (tag h14: federated run records, pilot summary, canary benchmark on the named settings) and the cross-cohort figure `fig_sites_count.py`.
- Added the circe definition of the training cohort (`analysis/cohort/Cohort_OHDSI_CKD_firstvisit.json`, `make_firstvisit_json.py`) and the duckcdm cross-check report `analysis/snuh_cdm/out/p4c_duckcdm_firstvisit.txt`; `p4b_duckcdm_cohort.py` takes `--hand-sql` and `--label`.
- Fixed `06_summarize.py` (the number of sites is taken from the step-01 targets; the first 14-site summary had averaged three sites) and `04_gate1_formats.py` (the native ensemble loader drops the column that the median imputer dropped at fit).
- Added `review_c_items.py` (exposure under two attacks, patient-level bootstrap ranges, calibrated-threshold decisions), `cohort_characteristics.py` (aggregate cohort table) and `build_submission.py`; figure scripts and the additional-file generator follow the revised manuscript (tables and figures renumbered in citation order).
- SNUH aggregate summaries remain excluded from this repository by policy; the eICU and MIMIC-IV-ED aggregates are included.

## Citation

Yu H. duckcdm-fl-node: single-file OMOP CDM node with federated XGBoost and an export audit. Version 0.2. Zenodo; 2026. https://doi.org/10.5281/zenodo.23487070 (concept DOI, all versions; this version: https://doi.org/10.5281/zenodo.23487071). The paper's citation will be added when it is published.

## License

MIT License (see `LICENSE`). duckcdm (Apache-2.0), DuckDB, XGBoost and NVIDIA FLARE are used under their own licences.
