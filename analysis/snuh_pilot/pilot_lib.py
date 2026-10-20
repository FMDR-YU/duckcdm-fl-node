# -*- coding: utf-8 -*-
"""Shared code for the SNUH real-data pilot (IRB 심의면제 의뢰 2026-10-06).

Design (IRB protocol §9.5): the KRCP 26-055 ensemble structure trained (A) centrally,
(A') on a site-sized random subsample, (B1) on three equal random virtual sites,
(B2) on three virtual sites of unequal size and skewed baseline-eGFR mix, plus the
site-prediction average of B1/B2. Each in three variants: the published KRCP
hyperparameters, a deliberately overfit one, and a regularised one. Every model then
goes through the three export gates.

Data handling (PhysioNet-style rule applied to SNUH data, analysis/snuh_pilot/README.md):
  data/ckd_pilot/          restricted -- analysis matrix, trained models, shadows, keys
  analysis/snuh_pilot/out/ aggregates only -- the only place Claude reads
Nothing here may print or write a row, an identifier, or a raw value. Counts below 11
are written as "<11"; subgroup metrics need >= 100 people.
"""
from __future__ import annotations

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
# PILOT_DATA_DIR / PILOT_OUT_DIR / PILOT_FED_DIR exist so tests can run in a scratch folder; unset = project folders.
DATA_DIR = os.environ.get("PILOT_DATA_DIR") or os.path.join(BASE, "data", "ckd_pilot")
OUT_ROOT = os.environ.get("PILOT_OUT_DIR") or os.path.join(HERE, "out")
FED_ROOT = os.environ.get("PILOT_FED_DIR") or os.path.join(BASE, "data", "federated")
CKD_ROOT = os.environ.get("PILOT_CKD_ROOT",
                          r"<ckd-ml-project>\PROJECT")
# Raw CDW extract files ([CKD_AI]*.xlsx / *.csv): one copy outside both project folders (decision 2026-10-14, DRB-E(I)-2025-08-01).
CDW_DIR = os.environ.get("PILOT_CDW_DIR") or r"<extract-folder>"


def raw_xlsx_dir(root=None, rel="Data/CSV"):
    """Folder with the raw extract files (the diagnosis and RID xlsx). PILOT_CDW_DIR wins. Otherwise <root>/<rel> if it exists (a CKD_ML-like
    tree, which is also what the test fixtures are), then the neutral folder CDW_DIR, then the old data/ckd_cdw. When PILOT_CKD_ROOT is set
    (tests, a copy of the tree) only <root>/<rel> is tried, so a test never falls through to the real extract. If nothing exists,
    <root>/<rel> is returned and the caller reports the file as missing."""
    if os.environ.get("PILOT_CDW_DIR"):
        return os.environ["PILOT_CDW_DIR"]
    cand = os.path.join(root or CKD_ROOT, *rel.split("/"))
    if os.path.isdir(cand) or "PILOT_CKD_ROOT" in os.environ:
        return cand
    for d in (CDW_DIR, os.path.join(BASE, "data", "ckd_cdw")):
        if os.path.isdir(d):
            return d
    return cand

MIN_CELL = 11
# Approved data period of DRB-E(I)-2025-08-01. Every SNUH-reading step (P1, P3 and so P4) cuts to it (user decision 2026-10-14);
# --date-range overrides it for tests and for public data.
DRB_DATE_RANGE = ("2000-01-01", "2025-07-31")
MIN_SUBGROUP = 100
GATE2_THRESHOLD = 0.55
THRESHOLD_SWEEP = [0.50, 0.52, 0.55, 0.58, 0.60]
SEEDS = list(range(42, 52))          # seed 42 = the published random_state -> scenario A/krcp reproduces v1.3
K_SHADOW_LIRA = int(os.environ.get("PILOT_K_LIRA", "64"))   # IRB: LiRA 64 shadows (PILOT_K_LIRA only for the hardened re-audit)
K_SHADOW_SHOKRI = 16                 # IRB: shadow-model attack 16 shadows (first 16 of the same set)
B2_SIZE_SHARES = (0.5, 0.3, 0.2)     # unequal virtual sites
B2_DIRICHLET_ALPHA = 0.5
N_THREADS = int(os.environ.get("PILOT_THREADS", "4"))
QUICK = os.environ.get("PILOT_QUICK") == "1"   # smoke test: fewer trees/seeds/shadows
DATASETS = ("snuh", "synpuf", "mimic_ed", "eicu")     # mimic_ed: insurance cohort (analysis/mimic_ed/matrix_mimic_ed.py); eicu: replication cohort (analysis/eicu/matrix_eicu.py)
ENSEMBLE_VARIANTS = ("krcp", "leaky", "regularized")
XGB_VARIANTS = ("xgb_krcp", "xgb_leaky", "xgb_regularized")   # single XGBoost, the model class a federated run can reproduce
# Matrix variant (hook for analysis/snuh_cdm P4): PILOT_TAG=cdm reads data/ckd_pilot/matrix_snuh_cdm.parquet
# and keeps work/out in <ds>_cdm folders. Unset = original behaviour.
TAG = os.environ.get("PILOT_TAG", "").strip()
# Model family: "ensemble" = the published four-model soft-voting structure (default, unchanged);
# "xgb" = one XGBoost per target with the same hyper-parameters as the ensemble's XGBoost member. The xgb family also
# audits the federated (FLARE) models, and keeps its work/out in <ds>_xgb folders so it never mixes with the ensemble.
MODEL = os.environ.get("PILOT_MODEL", "ensemble").strip().lower() or "ensemble"
if MODEL not in ("ensemble", "xgb"):
    raise SystemExit(f"PILOT_MODEL must be ensemble or xgb, got {MODEL!r}")
VARIANTS = XGB_VARIANTS if MODEL == "xgb" else ENSEMBLE_VARIANTS
FIXED_SITES = None   # set by load_matrix() when the matrix carries fixed virtual sites (site_b1 / site_b2)
N_SITES = 3          # number of sites per scenario; load_matrix() sets it from the fixed sites (e.g. 14 real eICU hospitals, tag h14)


def set_n_sites(n):
    """Resize the site-dependent tables (COMBINED, FEDERATED) for n sites. Called by load_matrix()."""
    global N_SITES
    N_SITES = int(n)
    COMBINED.clear()
    COMBINED.update({"B1_comb": tuple(f"B1_{k}" for k in range(N_SITES)), "B2_comb": tuple(f"B2_{k}" for k in range(N_SITES))})
    FEDERATED.clear()
    FEDERATED.update({"F_B1": tuple(f"B1_{k}" for k in range(N_SITES)), "F_B2": tuple(f"B2_{k}" for k in range(N_SITES))})


def site_names(scn="B1"):
    return [f"{scn}_{k}" for k in range(N_SITES)]


# ───────────────────────── paths ─────────────────────────
def base_tag(ds):
    """Dataset + matrix variant (+ quick), without the model family: names the matrix and the federated folders."""
    t = f"{ds}_{TAG}" if TAG else ds
    return f"{t}_quick" if QUICK else t


def tag(ds):
    """Quick-mode and xgb-family runs live in their own folders so they never mix with full ensemble runs."""
    t = f"{ds}_{TAG}" if TAG else ds
    if MODEL == "xgb":
        t += "_xgb"
    return f"{t}_quick" if QUICK else t


def matrix_path(ds):
    if TAG:                                   # tagged matrices come from outside step 00; no quick variant
        return os.path.join(DATA_DIR, f"matrix_{ds}_{TAG}.parquet")
    return os.path.join(DATA_DIR, f"matrix_{base_tag(ds)}.parquet")


def work_dir(ds, *parts):
    d = os.path.join(DATA_DIR, "work", tag(ds), *parts)
    os.makedirs(d, exist_ok=True)
    return d


def out_dir(ds):
    d = os.path.join(OUT_ROOT, tag(ds))
    os.makedirs(d, exist_ok=True)
    return d


def fed_dir(ds, scenario, seed):
    """Folder of one federated scenario (site files, FLARE model copies): data/federated/<dataset[_tag]>/<B1|B2>_s<seed>."""
    return os.path.join(FED_ROOT, base_tag(ds), f"{scenario}_s{seed}")


def fed_model_path(ds, scenario, seed, variant):
    """The FLARE global model that analysis/federated/run_fl_xgb.py copies here (XGBoost JSON, no code)."""
    return os.path.join(fed_dir(ds, scenario, seed), f"F_{variant}.model.json")


def seeds():
    return SEEDS[:2] if QUICK else SEEDS


def k_lira():
    return 8 if QUICK else K_SHADOW_LIRA


def k_shokri():
    return min(K_SHADOW_SHOKRI, k_lira())


# ───────────────────────── data ─────────────────────────
def load_matrix(ds):
    """-> X (DataFrame of features), y (int array), split (array 'train'/'val'), aux (DataFrame), meta (dict)."""
    p = matrix_path(ds)
    if not os.path.exists(p):
        sys.exit(f"{p} not found -- run 00_build_matrix.py --dataset {ds} first")
    df = pd.read_parquet(p)
    meta = json.load(open(p.replace(".parquet", ".meta.json"), encoding="utf-8"))
    global FIXED_SITES
    FIXED_SITES = ({"B1": df["site_b1"].to_numpy(int), "B2": df["site_b2"].to_numpy(int)}
                   if meta.get("fixed_sites") else None)
    set_n_sites(int(max(FIXED_SITES["B1"].max(), FIXED_SITES["B2"].max())) + 1 if FIXED_SITES is not None else 3)
    X = df[meta["features"]]
    y = df["y"].to_numpy(int)
    split = df["split"].to_numpy()
    aux = df[["stratum"] + meta["subgroups"]]
    return X, y, split, aux, meta


def cell(n):
    return f"{int(n):,}" if n >= MIN_CELL else "<11"


# ───────────────────────── models ─────────────────────────
def _scale(n):
    return max(20, n // 10) if QUICK else n


def is_xgb(variant):
    return variant.startswith("xgb_")


def _xgb_kwargs(variant, y_tr, seed):
    """XGBoost hyper-parameters of the three variants. One definition for the ensemble's XGBoost member and for the
    single-XGBoost family (and mirrored by analysis/federated/run_fl_xgb.py), so the routes compare like with like."""
    spw = float((y_tr == 0).sum() / max((y_tr == 1).sum(), 1))
    common = dict(random_state=seed, eval_metric="auc", verbosity=0, n_jobs=N_THREADS)
    if variant == "krcp":
        return dict(n_estimators=_scale(500), max_depth=6, learning_rate=0.05, subsample=0.8,
                    colsample_bytree=0.8, scale_pos_weight=spw, **common)
    if variant == "leaky":   # no subsampling, deep trees, many rounds, leaves down to one person
        return dict(n_estimators=_scale(1000), max_depth=12, learning_rate=0.1, subsample=1.0,
                    colsample_bytree=1.0, min_child_weight=0, reg_lambda=0, **common)
    if variant == "regularized":   # shallow, shrunk, >= 11 people per leaf where the library enforces counts
        return dict(n_estimators=_scale(300), max_depth=4, learning_rate=0.05, subsample=0.7,
                    colsample_bytree=0.7, min_child_weight=5, reg_lambda=10, scale_pos_weight=spw, **common)
    raise ValueError(variant)


def build_estimators(variant, y_tr, seed):
    """The four KRCP components. krcp = retrain_v13.py build() verbatim except explicit thread
    counts (for Gate 3 reproducibility) and LightGBM deterministic mode."""
    import xgboost as xgb
    import lightgbm as lgb
    from catboost import CatBoostClassifier
    from sklearn.ensemble import RandomForestClassifier

    common_lgb = dict(random_state=seed, verbose=-1, n_jobs=N_THREADS, deterministic=True, force_row_wise=True)
    if variant == "krcp":
        return [
            ("xgb", xgb.XGBClassifier(**_xgb_kwargs(variant, y_tr, seed))),
            ("lgb", lgb.LGBMClassifier(n_estimators=_scale(500), max_depth=6, learning_rate=0.05, subsample=0.8,
                                       colsample_bytree=0.8, class_weight="balanced", **common_lgb)),
            ("cat", CatBoostClassifier(iterations=_scale(500), depth=6, learning_rate=0.05,
                                       auto_class_weights="Balanced", random_seed=seed, verbose=0,
                                       allow_writing_files=False, thread_count=N_THREADS)),
            ("rf", RandomForestClassifier(n_estimators=_scale(500), max_depth=8, class_weight="balanced",
                                          random_state=seed, n_jobs=N_THREADS)),
        ]
    if variant == "leaky":
        return [
            ("xgb", xgb.XGBClassifier(**_xgb_kwargs(variant, y_tr, seed))),
            ("lgb", lgb.LGBMClassifier(n_estimators=_scale(1000), max_depth=-1, num_leaves=512, learning_rate=0.1,
                                       min_child_samples=2, min_child_weight=1e-3, reg_lambda=0, **common_lgb)),   # 0/1 crash LightGBM 4.6 at n~20k
            ("cat", CatBoostClassifier(iterations=_scale(1000), depth=10, learning_rate=0.1, l2_leaf_reg=0.01,
                                       random_seed=seed, verbose=0, allow_writing_files=False,
                                       thread_count=N_THREADS)),
            ("rf", RandomForestClassifier(n_estimators=_scale(500), max_depth=None, min_samples_leaf=1,
                                          random_state=seed, n_jobs=N_THREADS)),
        ]
    if variant == "regularized":
        return [
            ("xgb", xgb.XGBClassifier(**_xgb_kwargs(variant, y_tr, seed))),
            ("lgb", lgb.LGBMClassifier(n_estimators=_scale(300), max_depth=4, num_leaves=15, learning_rate=0.05,
                                       subsample=0.7, subsample_freq=1, colsample_bytree=0.7, min_child_samples=50,
                                       reg_lambda=10, class_weight="balanced", **common_lgb)),
            # CatBoost 1.2.10 does not enforce a minimum leaf size (min_data_in_leaf ignored for symmetric
            # trees, and leaves of 1-2 people still occur with Depthwise/Lossguide -- checked on SynPUF
            # 2026-10-06); 04_gate1_formats.py reports the share of small leaves instead.
            ("cat", CatBoostClassifier(iterations=_scale(300), depth=4, learning_rate=0.05, l2_leaf_reg=10,
                                       auto_class_weights="Balanced", random_seed=seed, verbose=0,
                                       allow_writing_files=False, thread_count=N_THREADS)),
            ("rf", RandomForestClassifier(n_estimators=_scale(500), max_depth=6, min_samples_leaf=50,
                                          class_weight="balanced", random_state=seed, n_jobs=N_THREADS)),
        ]
    raise ValueError(variant)


def make_model(variant, y_tr, seed):
    """Ensemble family: median imputer fit on the training rows only (as in KRCP) + soft-voting ensemble.
    xgb family (variant xgb_*): one XGBoost with the same hyper-parameters, no imputation (XGBoost reads missing
    values natively -- the federated runs do the same, so every route sees the same inputs)."""
    if is_xgb(variant):
        import xgboost as xgb
        return xgb.XGBClassifier(**_xgb_kwargs(variant[len("xgb_"):], y_tr, seed))
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.ensemble import VotingClassifier
    return Pipeline([("imp", SimpleImputer(strategy="median")),
                     ("ens", VotingClassifier(build_estimators(variant, y_tr, seed), voting="soft"))])


def fit_predict(variant, X, y, idx, seed):
    """Fit on rows idx, return (model, P(y=1) for every row of X as float32)."""
    m = make_model(variant, y[idx], seed)
    m.fit(X.iloc[idx], y[idx])
    return m, m.predict_proba(X)[:, 1].astype(np.float32)


# ───────────────────────── scenarios ─────────────────────────
def site_sizes(n_train):
    b1 = [n_train // N_SITES] * N_SITES
    if N_SITES == 3:
        b2 = [int(round(n_train * s)) for s in B2_SIZE_SHARES]
    else:                                      # more than three virtual sites are only ever fixed sites; B2 = B1 then
        b2 = list(b1)
    b2[0] += n_train - sum(b2)
    return b1, b2


def size_classes(n_train):
    b1, b2 = site_sizes(n_train)
    if FIXED_SITES is not None:               # shadow sizes follow the actual fixed sites
        f1, f2 = (np.bincount(FIXED_SITES[k][FIXED_SITES[k] >= 0], minlength=N_SITES) for k in ("B1", "B2"))
        b1, b2 = [int(round(f1.mean()))] * N_SITES, [int(v) for v in f2]
    out = {"full": n_train, "site": b1[0]}
    out.update({f"b2_{k}": b2[k] for k in range(N_SITES)})
    return out


def scenarios(train_idx, stratum, seed):
    """{target name: (row indices, shadow size class)} for one seed. B2: within each baseline-eGFR
    stratum the site mix follows a Dirichlet draw, then sites are trimmed/filled to exact sizes."""
    rng = np.random.default_rng(seed)
    n = len(train_idx)
    b1, b2 = site_sizes(n)
    perm = rng.permutation(train_idx)
    out = {"A_0": (np.sort(train_idx), "full"),
           "Aprime_0": (np.sort(rng.choice(train_idx, b1[0], replace=False)), "site")}
    for k in range(N_SITES):
        out[f"B1_{k}"] = (np.sort(perm[k * b1[0]:(k + 1) * b1[0]]), "site")
    if FIXED_SITES is not None:               # fixed physical sites (analysis/snuh_cdm, eICU hospitals): same for every seed
        for k in range(N_SITES):
            out[f"B1_{k}"] = (np.sort(train_idx[FIXED_SITES["B1"][train_idx] == k]), "site")
            out[f"B2_{k}"] = (np.sort(train_idx[FIXED_SITES["B2"][train_idx] == k]), f"b2_{k}")
        return out
    if N_SITES != 3:
        raise SystemExit("random virtual sites are defined for three sites only; more sites must be fixed sites of the matrix")

    st = np.asarray(stratum)[train_idx]
    shares = np.array(B2_SIZE_SHARES)
    site = np.empty(n, int)
    for s in np.unique(st):
        w = rng.dirichlet(np.full(3, B2_DIRICHLET_ALPHA)) * shares
        rows = np.where(st == s)[0]
        site[rows] = rng.choice(3, size=len(rows), p=w / w.sum())
    for _ in range(10 * n):                       # move random people from over- to under-full sites
        counts = np.bincount(site, minlength=3)
        over, under = np.argmax(counts - b2), np.argmin(counts - b2)
        if counts[over] == b2[over]:
            break
        j = rng.choice(np.where(site == over)[0])
        site[j] = under
    for k in range(3):
        out[f"B2_{k}"] = (np.sort(train_idx[site == k]), f"b2_{k}")
    return out


COMBINED = {"B1_comb": ("B1_0", "B1_1", "B1_2"), "B2_comb": ("B2_0", "B2_1", "B2_2")}
# Federated targets (xgb family only): one global XGBoost trained across the three sites of B1 / B2 by FLARE
# (analysis/federated). Step 01 reads the model file the federated run left in data/federated/.
FEDERATED = {"F_B1": ("B1_0", "B1_1", "B1_2"), "F_B2": ("B2_0", "B2_1", "B2_2")}


# ───────────────────────── metrics ─────────────────────────
def auc(y, s):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s))


def tpr_at_fpr(y, s, fpr=0.01):
    from sklearn.metrics import roc_curve
    f, t, _ = roc_curve(y, s)
    return float(np.interp(fpr, f, t))


def utility(y, p):
    """AUROC, scaled Brier, calibration intercept (slope fixed at 1) and slope."""
    import statsmodels.api as sm
    from sklearn.metrics import brier_score_loss
    p = np.clip(p.astype(float), 1e-6, 1 - 1e-6)
    lp = np.log(p / (1 - p))
    brier = brier_score_loss(y, p)
    pi = y.mean()
    scaled = 1 - brier / (pi * (1 - pi))
    slope = sm.GLM(y, sm.add_constant(lp), family=sm.families.Binomial()).fit().params[1]
    inter = sm.GLM(y, np.ones_like(lp), family=sm.families.Binomial(), offset=lp).fit().params[0]
    return {"auroc": auc(y, p), "scaled_brier": float(scaled), "cal_intercept": float(inter), "cal_slope": float(slope)}


def paired_boot_delta(y, p1, p2, n=500, seed=0):
    """Bootstrap 95% CI of AUROC(p1) - AUROC(p2) on the same rows."""
    rng = np.random.default_rng(seed)
    d = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() != y[i].max():
            d.append(auc(y[i], p1[i]) - auc(y[i], p2[i]))
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def logit_conf(p, y):
    """Logit of the model's confidence in the true label (LiRA statistic)."""
    pc = np.where(y == 1, p, 1 - p).astype(float)
    pc = np.clip(pc, 1e-7, 1 - 1e-7)
    return np.log(pc / (1 - pc))


def attack_features(p, y):
    """Shokri attack features: confidence on true label, log-loss, entropy, correct@0.5."""
    pc = np.clip(np.where(y == 1, p, 1 - p).astype(float), 1e-7, 1 - 1e-7)
    q = np.clip(p.astype(float), 1e-7, 1 - 1e-7)
    ent = -(q * np.log(q) + (1 - q) * np.log(1 - q))
    return np.column_stack([pc, -np.log(pc), ent, (pc > 0.5).astype(float)])


def t_ci(vals):
    from scipy import stats
    v = np.asarray(vals, float)
    v = v[~np.isnan(v)]
    if len(v) < 2:
        return (float(v.mean()) if len(v) else np.nan, np.nan, np.nan)
    h = stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / np.sqrt(len(v))
    return float(v.mean()), float(v.mean() - h), float(v.mean() + h)


def append_rows(path, rows):
    df = pd.DataFrame(rows)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        if set(pd.read_csv(path, nrows=0).columns) != set(df.columns):    # columns added between runs: rewrite, never mis-align
            pd.concat([pd.read_csv(path), df], ignore_index=True).to_csv(path, index=False, encoding="utf-8")
            return
        df = df[list(pd.read_csv(path, nrows=0).columns)]
    df.to_csv(path, mode="a", header=not (os.path.exists(path) and os.path.getsize(path) > 0), index=False, encoding="utf-8")


SAFE_MESSAGE = (ImportError, MemoryError)   # messages name modules / sizes, never cell values


def guard(main):
    """Run main(); on error print the exception type and *where* it happened (file:line:function of
    each frame -- code locations, not data). The message itself is shown only for exception types
    whose text cannot carry data values (ImportError family, MemoryError)."""
    import traceback
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        if os.environ.get("PILOT_DEBUG") == "1":
            raise
        frames = traceback.extract_tb(e.__traceback__)
        where = [f"{os.path.basename(f.filename)}:{f.lineno}:{f.name}" for f in frames]
        if len(where) > 8:
            where = where[:4] + ["…"] + where[-4:]
        msg = f" -- {e}" if isinstance(e, SAFE_MESSAGE) else " (message suppressed; PILOT_DEBUG=1 shows it locally)"
        sys.exit(f"FAILED: {type(e).__name__}{msg}\n  at " + "\n  at ".join(where))
