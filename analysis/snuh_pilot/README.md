# analysis/snuh_pilot — SNUH real-data pilot of the Safe Model Bundle

IRB: 신규 심의면제 의뢰 2026-10-06 (`IRB/v1.0_면제신청/EGRESS_연구계획서_v1.0_서식5.docx`), PI 유호준 단독.
**Run on SNUH data only after the exemption is confirmed.** Development and tests use public
CMS DE-SynPUF through the same code path.

## Who does what

| | |
|---|---|
| Claude | writes and tests code on SynPUF; reads `out/` only |
| user | runs the SNUH commands below in PowerShell |

- `data/ckd_pilot/` (gitignored) holds everything derived from patients: the matrix, trained
  models, shadow models, Gate 1/3 artifacts, the escrow HMAC key. Claude does not open it for snuh.
- `out/<dataset>/` holds aggregates only (metrics, counts ≥ 11, subgroups ≥ 100). No row, ID,
  raw value or free text is ever printed or written. Errors show the exception type only
  (`PILOT_DEBUG=1` shows the message locally).
- Quick-mode runs write to `<dataset>_quick` folders and never mix with full runs.

## Environment (once)

The user's own terminal and Claude's sessions see different Python packages: the Claude app's
sandbox virtualises writes to `AppData`, so packages installed from Claude sessions are invisible
to the user's terminal (diagnosed 2026-10-07 with `diag_env.py`: user's terminal has sklearn 1.9.0 /
pandas 3.0.3 and no lightgbm, catboost, statsmodels or pyarrow). The pilot therefore runs in its own
venv outside the project folder (no brackets in the path), pinned by `requirements-pilot.txt`:

    python -m venv <home>\.venvs\egress-pilot
    python -m pip install -r "<repo>\analysis\snuh_pilot\requirements-pilot.txt"

## Commands (SNUH, after IRB exemption) — run with the venv's python

    python "<repo>\analysis\snuh_pilot\run_pilot.py" --dataset snuh --irb E-XXXX-XXX-XXXX

`--irb` takes this study's exemption number (format E-NNNN-NNN-NNNN). Without it step 00 stops
before reading any SNUH file; the number is stored in the matrix metadata. Console output is
also appended to `out/snuh/run_log.txt`.

Resumable: if it stops, run the same line again (or add `--from 02` etc.). Threads default to 4
(`$env:PILOT_THREADS = "8"` before the line to change; keep it fixed across a run, Gate 3 checks it).

## Steps

| step | what | output (out/<ds>/) |
|---|---|---|
| 00 | matrix: snuh = v1.3 definitions copied from CKD_ML `ML\v1.3\retrain_v13.py` L41–83 (no RID kept); synpuf = 28,209-row sample | `00_build_matrix.txt` |
| 01 | targets: A, A′, B1 (3 equal sites), B2 (3 sites 50/30/20%, Dirichlet α 0.5 eGFR-stage mix) × krcp/leaky/regularized × 10 seeds (42–51); combined = mean of site predictions | `01_utility_long.csv` |
| 02 | `PILOT_K_LIRA` shadows (default 64; analysis plan v2 proposes 256) per variant × size class (full/site/b2_0–2), random subsets of the whole cohort, shared across seeds | — |
| 03 | Gate 2: loss-threshold, shadow-model (first 16 shadows), online LiRA, LiRA with global variance and RMIA (all `PILOT_K_LIRA` reference models); TPR@1%FPR; subgroups. Rows record `k_lira` and `k_shokri`, and the summary states them | `03_attacks_long.csv`, `03_subgroups_long.csv` |
| 04 | Gate 1: XGB JSON / LGBM text / CatBoost CBM / RF tree JSON, reload without pickle, max abs Δp; leaf-size audit | `04_gate1.csv`, `04_leaf_audit.csv` |
| 05 | Gate 3: signed manifest (HMAC-SHA256, local key), re-execution in a new process | `05_gate3.csv` |
| 06 | seed means and 95% CI, Gate 2 decision and threshold sweep, H1–H4 tables | `06_summary.md` |

Seed 42 with variant krcp and target A_0 is the published configuration and should land near the
v1.3 validation AUROC (0.930); it is not bit-identical (row order and explicit thread counts differ).

## Model families: ensemble (default) and xgb

`run_pilot.py --model xgb` (or `PILOT_MODEL=xgb`) runs the same steps with **one XGBoost per target** instead of the
four-model ensemble. Variants `xgb_krcp`, `xgb_leaky`, `xgb_regularized` use exactly the hyper-parameters of the
ensemble's XGBoost member (one definition, `pilot_lib._xgb_kwargs`; a test checks this) and no imputation (XGBoost
reads missing values). Work and out folders are `<ds>_xgb`, so the two families never mix.

Why: a federated histogram XGBoost (analysis/federated) reproduces a single XGBoost, not a soft-voting ensemble, so the
export routes can only be compared like with like in this family. Targets in the xgb family:

| target | what |
|---|---|
| A_0, Aprime_0, B1_k, B2_k, B1_comb, B2_comb | as in the ensemble family |
| F_B1, F_B2 | the federated global model trained by FLARE across the three sites of B1 / B2. Step 01 reads the model file `data/federated/<ds>/<B1\|B2>_s<seed>/F_<variant>.model.json` (written by `analysis/federated/run_fl_xgb.py`), scores every row from the XGBoost JSON itself, and treats the union of the three sites as members |

Step 01 reports F's utility with a paired bootstrap against A_0 (H5), step 03 audits F against full-size shadows, step 04
reloads the FLARE JSON without pickle and runs the leaf audit, step 06 adds an H5 table. F targets appear only when the
model files exist, so run the federated jobs first. Gate 3 for F is `run_fl_xgb.py --reexec` (the job run twice in fresh
workspaces); step 05 covers A_0 and the other locally trained targets.

Order for one dataset: `make_sites.py` + `run_fl_xgb.py` in the container for each seed, scenario and config, then
`run_pilot.py --dataset <ds> --model xgb`. Tests: `analysis/snuh_cdm/tests/run_tests.py --only xgbfam`.

## Canary benchmark: release rules against planted-canary ground truth

`canary_benchmark.py` trains many single-XGBoost models per cell (a cell = setting × training size; 7 named settings and 40
Latin-hypercube settings, 2,000 / 6,000 / 19,746 rows) on random subsets of the cohort plus a random half of 400 canaries.
Canaries are label-flipped real rows (`--canary-type flip`, main) or synthetic rows whose features are drawn from their own
marginals with a random label (`--canary-type shuffle`, robustness check). Each canary is in each model with probability 1/2,
so membership is known, and a leave-one-model-out LiRA on the canaries gives the cell's ground-truth tail exposure (canary
TPR at 1% FPR). For six models per cell the ordinary-row audit quantities are computed (shadow-model AUC, LiRA, leaf
support, member / non-member AUROC gap). `--summarize` asks how well each release rule separates exposed from unexposed
cells (`canary_summary.md`; thresholds calibrated to block 90% of exposed cells in `canary_thresholds.json`).

    python canary_benchmark.py --dataset synpuf --sizes 2000 --out-tag n2000              # 7 named settings
    python canary_benchmark.py --dataset synpuf --lhs --sizes 2000 --out-tag lhs_n2000    # 40 space-filling settings
    python canary_benchmark.py --dataset synpuf --summarize [--tau 0.10] [--boot 2000] [--thresholds <dev canary_thresholds.json>]
    python canary_benchmark.py --dataset synpuf --canary-type shuffle ...                 # same grid with synthetic canaries (robustness)
    python canary_screen.py --dataset synpuf                                              # exploratory: can structure predict tail exposure? (q3_screen.md)
    python canary_cohorts.py [--figure]                                                   # SynPUF, MIMIC-IV-ED and eICU side by side: out/canary_cross_cohort.md, Fig6

For another cohort use `analysis/run_canary.ps1` (see its header): it builds the matrix if needed, runs the grid and applies the
development thresholds unchanged.

Outputs go to `out/<ds>_xgb_canary/` (flip) and `out/<ds>_xgb_canary_shuffle/`. Subsampled XGBoost models are reproducible
only at the same thread count (checked: same seed gives identical predictions, 4 threads and 1 thread give different
models), so every row records `threads` and the xgboost version. The SynPUF cells were run with `PILOT_THREADS=2`; the same
nine cells run with 4 threads moved the canary TPR by at most 0.014 (`out/synpuf_xgb_canary/canary_replicate_threads4.csv`).
Tests: `analysis/snuh_cdm/tests/run_tests.py --only canary`.

## Known limits (checked on SynPUF 2026-10-06)

- CatBoost 1.2.10 does not enforce a minimum leaf size (symmetric, Depthwise or Lossguide), so the
  regularised variant still has CatBoost leaves under 11 people; the leaf audit reports the share.
  Post-hoc suppression (set those leaf values to 0) is not implemented yet.
- skops cannot import in this environment (stray `sklearn/callback` from a development build in the
  scikit-learn 1.8.0 install), so the forest is exported as plain tree JSON instead.
- LightGBM 4.6 crashes with min_child_weight 0 / min_child_samples 1 at n≈20k; the leaky variant
  uses 1e-3 / 2.
- Gate 3 re-execution is a fresh process in the same environment, not a rebuilt environment.
- Shadow models are drawn from the whole cohort (a strong attacker who knows part of the
  population); combined-model shadows are averages of site shadows. Audit results are lower bounds
  for the attacks run.

Runtime on SynPUF at full size, 4 threads: ensemble fit krcp 6 s, leaky 46 s, regularised 4 s
(19,746 rows). Full SNUH run estimate ≈ 5–6 h, dominated by leaky shadows.
