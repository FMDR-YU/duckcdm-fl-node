"""Submit the federated XGBoost job to the T0 aggregator and wait for it.

Runs in the t0-admin container, which mounts no patient data: only this code and the counts needed for
scale_pos_weight (in a real federation one count query summing the sites' positives and negatives).

    python t0/submit_job.py --config plain --seed 42 --pos 7477 --neg 12269
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FED = os.path.dirname(HERE)
sys.path.insert(0, FED)
sys.path.insert(0, os.path.join(os.path.dirname(FED), "snuh_pilot"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="plain", choices=["plain", "krcp", "leaky", "regularized"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pos", type=int, required=True, help="pooled training positives (count query)")
    ap.add_argument("--neg", type=int, required=True, help="pooled training negatives (count query)")
    ap.add_argument("--name", default="")
    ap.add_argument("--timeout", type=float, default=3600.0)
    a = ap.parse_args()

    import pilot_lib as pl
    from fl_data import ParquetSiteLoader
    from nvflare.app_opt.xgboost.recipes import XGBHorizontalRecipe
    from nvflare.recipe import ProdEnv, set_per_site_config
    from run_fl_xgb import native_config

    rounds, native = native_config(pl, a.config, np.r_[np.zeros(a.neg, np.int8), np.ones(a.pos, np.int8)], a.seed)
    params = {"objective": "binary:logistic", "eval_metric": "auc", "tree_method": "hist", "max_bin": 256,
              "nthread": 4, "seed": a.seed, **native}
    name = a.name or f"t0_{a.config}_s{a.seed}"
    recipe = XGBHorizontalRecipe(name=name, min_clients=3, num_rounds=rounds, early_stopping_rounds=0, xgb_params=params)
    set_per_site_config(recipe, {f"site-{k}": {"data_loader": ParquetSiteLoader(folder="/data")} for k in (1, 2, 3)})
    env = ProdEnv(startup_kit_location="/fl/admin", username="admin@snuh.local", login_timeout=60)
    run = recipe.execute(env)
    print("JOB_ID", run.get_job_id(), flush=True)
    result = run.get_result(timeout=a.timeout)
    print("RESULT", result, flush=True)


if __name__ == "__main__":
    main()
