"""Federated XGBoost (NVIDIA FLARE, histogram-based, horizontal) against central, local and
prediction-average XGBoost on the same virtual sites, scored on the common validation set.

    python run_fl_xgb.py --dataset synpuf --scenario B1 --seed 42 --config plain

One model class and one set of hyper-parameters in every arm:
  A_x    central   one XGBoost on the pooled training rows
  B_k    local     one XGBoost per site, own rows only
  B_avg  average   mean of the three local predictions (the original EGRESS "B_comb")
  F      federated FLARE XGBHorizontalRecipe over the three sites; rows never leave a site

Configs: plain (no subsampling, 100 rounds: federated and central should agree to float precision) and the
pilot's three XGBoost variants krcp, leaky, regularized. Their hyper-parameters are derived from
analysis/snuh_pilot/pilot_lib._xgb_kwargs, so the federated model has exactly the settings of the pilot's xgb
family (PILOT_MODEL=xgb). The FLARE global model is copied to data/federated/.../F_xgb_<config>.model.json, where
the pilot's steps 01/03/04 pick it up for the utility comparison and the three-gate audit.
--reexec runs the federated job a second time in a fresh workspace and compares predictions (Gate 3 analogue).

The federated arm needs the Linux image (xgboost built with the federated communicator); --skip-fl runs
the other arms anywhere. Run make_sites.py first. Only aggregates are written, to out/<dataset>/.
"""
import argparse
import glob
import json
import os
import platform
import shutil
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "snuh_pilot"))

N_SITES = 3                # replaced by pilot_lib.N_SITES once the matrix is loaded (fixed sites may number more than three)
NI_MARGIN = -0.02          # non-inferiority margin for AUROC(F) - AUROC(A_x), as in the EGRESS protocol

CONFIGS = ("plain", "krcp", "leaky", "regularized")


def native_config(pl, name, y_train, seed):
    """-> (boosting rounds, native xgboost params) for a config. Everything but "plain" comes from the pilot's
    sklearn-style kwargs (one definition), with scale_pos_weight taken from the pooled training labels (in a real
    federation: one count query summing positives and negatives over the sites)."""
    if name == "plain":
        return 100, {"max_depth": 6, "eta": 0.1, "subsample": 1.0, "colsample_bytree": 1.0}
    kw = pl._xgb_kwargs(name, y_train, seed)
    rounds = kw.pop("n_estimators")
    params = {"eta": kw.pop("learning_rate")}
    for k in ("random_state", "n_jobs", "eval_metric", "verbosity"):
        kw.pop(k)
    params.update(kw)            # max_depth, subsample, colsample_bytree, min_child_weight, reg_lambda, scale_pos_weight
    return rounds, params


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="synpuf")
    ap.add_argument("--tag", default="", help="matrix variant, e.g. cdm")
    ap.add_argument("--scenario", choices=["B1", "B2"], default="B1")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--config", choices=CONFIGS, default="plain")
    ap.add_argument("--nthread", type=int, default=4)
    ap.add_argument("--boot", type=int, default=500, help="bootstrap resamples for the F - A_x interval")
    ap.add_argument("--skip-fl", action="store_true", help="run only the non-federated arms")
    ap.add_argument("--reexec", action="store_true", help="run the federated job twice and compare (Gate 3 analogue)")
    ap.add_argument("--quick", action="store_true", help="PILOT_QUICK=1: smoke-test sizes (quick matrix, fewer rounds)")
    return ap.parse_args()


def score(pl, y, p):
    from sklearn.metrics import average_precision_score, brier_score_loss, log_loss
    p = np.clip(np.asarray(p, float), 1e-7, 1 - 1e-7)
    return {"auroc": pl.auc(y, p), "auprc": float(average_precision_score(y, p)),
            "brier": float(brier_score_loss(y, p)), "logloss": float(log_loss(y, p))}


def run_federated(a, rounds, params, folder, ws_root, job_name):
    """-> list of model.json paths written by the three sites."""
    from fl_data import ParquetSiteLoader
    from nvflare.app_opt.xgboost.recipes import XGBHorizontalRecipe
    from nvflare.recipe import SimEnv, set_per_site_config

    names = [f"site-{k + 1}" for k in range(N_SITES)]
    recipe = XGBHorizontalRecipe(name=job_name, min_clients=N_SITES, num_rounds=rounds,
                                 early_stopping_rounds=0, xgb_params=params)
    set_per_site_config(recipe, {n: {"data_loader": ParquetSiteLoader(folder=folder)} for n in names})
    env = SimEnv(clients=names, num_threads=N_SITES, workspace_root=ws_root)
    shutil.rmtree(os.path.join(ws_root, job_name), ignore_errors=True)
    run = recipe.execute(env)
    run.get_result(clean_up=False)
    return sorted(glob.glob(os.path.join(glob.escape(os.path.join(ws_root, job_name)), "**", "model.json"), recursive=True))


def main(a):
    import pilot_lib as pl
    import xgboost as xgb

    X, y, split, aux, meta = pl.load_matrix(a.dataset)
    if a.dataset == "snuh" and not meta.get("irb"):
        sys.exit("this SNUH matrix carries no IRB exemption number -- rebuild it with 00_build_matrix.py --irb")
    global N_SITES
    N_SITES = pl.N_SITES
    train_idx = np.where(split == "train")[0]
    val_idx = np.where(split == "val")[0]
    sc = pl.scenarios(train_idx, aux["stratum"].to_numpy(), a.seed)
    sites = [sc[f"{a.scenario}_{k}"][0] for k in range(N_SITES)]
    folder = pl.fed_dir(a.dataset, a.scenario, a.seed)
    with open(os.path.join(folder, "manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    for k, idx in enumerate(sites):                      # the files the sites read are the rows used here
        s = man["sites"][f"site-{k + 1}"]
        if s["n_train"] != len(idx) or s["events_train"] != int(y[idx].sum()):
            sys.exit(f"site-{k + 1} counts differ from manifest.json -- rerun make_sites.py")

    rounds, native = native_config(pl, a.config, y[train_idx], a.seed)
    params = {"objective": "binary:logistic", "eval_metric": "auc", "tree_method": "hist", "max_bin": 256,
              "nthread": a.nthread, "seed": a.seed, **native}
    Xv, yv = X.iloc[val_idx], y[val_idx]
    dval = xgb.DMatrix(Xv)

    def fit(idx):
        t = time.time()
        bst = xgb.train(params, xgb.DMatrix(X.iloc[idx], label=y[idx]), rounds)
        return bst.predict(dval), time.time() - t

    arms, preds = {}, {}
    preds["A_x"], sec = fit(train_idx)
    arms["A_x"] = {**score(pl, yv, preds["A_x"]), "seconds": round(sec, 1), "n_train": pl.cell(len(train_idx))}
    for k, idx in enumerate(sites):
        preds[f"B_{k}"], sec = fit(idx)
        arms[f"B_{k}"] = {**score(pl, yv, preds[f"B_{k}"]), "seconds": round(sec, 1), "n_train": pl.cell(len(idx))}
    preds["B_avg"] = np.mean([preds[f"B_{k}"] for k in range(N_SITES)], axis=0)
    arms["B_avg"] = score(pl, yv, preds["B_avg"])

    fed = {"use_federated_build": bool(xgb.build_info().get("USE_FEDERATED"))}
    if not a.skip_fl:
        if not fed["use_federated_build"]:
            sys.exit("xgboost here has no federated communicator (USE_FEDERATED False) -- run in the Linux image, "
                     "or pass --skip-fl")
        job = f"xgb_{pl.base_tag(a.dataset)}_{a.scenario}_s{a.seed}_{a.config}"
        ws_root = os.path.join(pl.FED_ROOT, "workspace")

        def federate(job_name):
            t = time.time()
            models = run_federated(a, rounds, params, folder, ws_root, job_name)
            sec = round(time.time() - t, 1)
            if len(models) != N_SITES:
                sys.exit(f"expected {N_SITES} model.json files, found {len(models)} under {ws_root}")
            site_preds = []
            for m in models:
                b = xgb.Booster()
                b.load_model(m)
                site_preds.append(b.predict(dval))
            return models, site_preds, sec

        models, site_preds, fed["seconds"] = federate(job)
        fed["model_files"] = len(models)
        fed["max_abs_pred_diff_between_sites"] = float(max(np.abs(site_preds[0] - p).max() for p in site_preds[1:]))
        # the exported artifact: the pilot's steps 01/03/04 audit this file (variant name = xgb_<config>)
        shutil.copyfile(models[0], pl.fed_model_path(a.dataset, a.scenario, a.seed, f"xgb_{a.config}"))
        preds["F"] = site_preds[0]
        arms["F"] = {**score(pl, yv, preds["F"]), "seconds": fed["seconds"]}
        if a.reexec:      # Gate 3 analogue: the same job again in a fresh workspace must give the same model
            _, again, sec2 = federate(job + "_reexec")
            fed["reexec"] = {"max_abs_pred_diff": float(np.abs(again[0] - preds["F"]).max()),
                             "abs_delta_auroc": abs(pl.auc(yv, again[0]) - pl.auc(yv, preds["F"])),
                             "seconds": sec2}
        d = pl.auc(yv, preds["F"]) - pl.auc(yv, preds["A_x"])
        lo, hi = pl.paired_boot_delta(yv, preds["F"], preds["A_x"], n=a.boot, seed=a.seed)
        fed["delta_auroc_vs_central"] = {"delta": float(d), "ci95": [lo, hi], "margin": NI_MARGIN,
                                         "non_inferior": bool(lo > NI_MARGIN)}
        diff = np.abs(preds["F"] - preds["A_x"])
        fed["pred_fidelity_vs_central"] = {"pearson": float(np.corrcoef(preds["F"], preds["A_x"])[0, 1]),
                                           "mean_abs_diff": float(diff.mean()), "max_abs_diff": float(diff.max())}
        db = pl.auc(yv, preds["F"]) - pl.auc(yv, preds["B_avg"])
        lo, hi = pl.paired_boot_delta(yv, preds["F"], preds["B_avg"], n=a.boot, seed=a.seed)
        fed["delta_auroc_vs_prediction_average"] = {"delta": float(db), "ci95": [lo, hi]}

    out = {"dataset": a.dataset, "tag": a.tag, "scenario": a.scenario, "seed": a.seed, "config": a.config,
           "rounds": rounds, "params": params, "n_val": pl.cell(len(val_idx)), "arms": arms, "federated": fed,
           "versions": {"python": platform.python_version(), "platform": platform.platform(),
                        "xgboost": xgb.__version__}}
    if not a.skip_fl:
        import nvflare
        out["versions"]["nvflare"] = nvflare.__version__
    od = os.path.join(HERE, "out", pl.base_tag(a.dataset))
    os.makedirs(od, exist_ok=True)
    stem = f"fl_{a.scenario}_s{a.seed}_{a.config}" + ("_nofl" if a.skip_fl else "")
    with open(os.path.join(od, stem + ".json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"\n{a.dataset} {a.scenario} seed {a.seed} config {a.config} ({rounds} rounds), common val n={pl.cell(len(val_idx))}")
    for name in ("A_x", "B_0", "B_1", "B_2", "B_avg", "F"):
        if name in arms:
            r = arms[name]
            print(f"  {name:6s} AUROC {r['auroc']:.4f}  AUPRC {r['auprc']:.4f}")
    if "delta_auroc_vs_central" in fed:
        d = fed["delta_auroc_vs_central"]
        print(f"  F - A_x  {d['delta']:+.4f} (95% CI {d['ci95'][0]:+.4f} to {d['ci95'][1]:+.4f}), "
              f"non-inferior at {NI_MARGIN}: {d['non_inferior']}")
        q = fed["pred_fidelity_vs_central"]
        print(f"  prediction agreement F vs A_x: r={q['pearson']:.5f}, mean |diff|={q['mean_abs_diff']:.5f}, "
              f"max |diff|={q['max_abs_diff']:.4f}; sites' models differ by {fed['max_abs_pred_diff_between_sites']:.2e}")
        if "reexec" in fed:
            print(f"  re-execution: max |diff| {fed['reexec']['max_abs_pred_diff']:.2e}, "
                  f"|dAUROC| {fed['reexec']['abs_delta_auroc']:.1e}")
    print(f"  wrote {os.path.join(od, stem + '.json')}")


if __name__ == "__main__":
    args = parse_args()
    if args.tag:
        os.environ["PILOT_TAG"] = args.tag
    if args.quick:
        os.environ["PILOT_QUICK"] = "1"
    import pilot_lib
    pilot_lib.guard(lambda: main(args))
