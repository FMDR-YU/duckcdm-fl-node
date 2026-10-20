"""Write the per-site parquet files that the FLARE job reads (virtual sites).

Takes a pilot matrix (analysis/snuh_pilot) and one scenario (B1 = three equal sites, B2 = unequal sites;
same site definition as run_pilot.py) and writes

    data/federated/<dataset[_tag]>/<scenario>_s<seed>/site-1..3/{train,valid}.parquet
    data/federated/<dataset[_tag]>/<scenario>_s<seed>/manifest.json     (counts only)

The site files are patient-level derivatives and stay under data/. Each site's valid.parquet is a random
third of the common validation rows and is used for monitoring only.

    python make_sites.py --dataset synpuf --scenario B1 --seed 42
    python make_sites.py --dataset snuh --tag cdm --scenario B2 --seed 42     (needs the IRB number upstream)
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "snuh_pilot"))

N_SITES = 3     # replaced by pilot_lib.N_SITES once the matrix is loaded (fixed sites may number more than three)


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="synpuf")
    ap.add_argument("--tag", default="", help="matrix variant, e.g. cdm (reads matrix_<dataset>_<tag>.parquet)")
    ap.add_argument("--scenario", choices=["B1", "B2"], default="B1")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--quick", action="store_true", help="PILOT_QUICK=1: use the quick matrix (smoke tests)")
    return ap.parse_args()


def main(a):
    import pilot_lib as pl

    X, y, split, aux, meta = pl.load_matrix(a.dataset)
    if a.dataset == "snuh" and not meta.get("irb"):
        sys.exit("this SNUH matrix carries no IRB exemption number -- rebuild it with 00_build_matrix.py --irb")
    global N_SITES
    N_SITES = pl.N_SITES
    train_idx = np.where(split == "train")[0]
    val_idx = np.where(split == "val")[0]
    sc = pl.scenarios(train_idx, aux["stratum"].to_numpy(), a.seed)
    sites = [sc[f"{a.scenario}_{k}"][0] for k in range(N_SITES)]

    allrows = np.concatenate(sites)
    left = len(train_idx) - len(allrows)        # B1 cuts n // 3 rows per site, so up to 2 training rows stay in no site
    if len(np.unique(allrows)) != len(allrows) or not np.isin(allrows, train_idx).all() or not 0 <= left < N_SITES:
        sys.exit("sites are not disjoint subsets that cover the training rows")

    rng = np.random.default_rng(a.seed)
    val_parts = np.array_split(rng.permutation(val_idx), N_SITES)
    root = pl.fed_dir(a.dataset, a.scenario, a.seed)
    manifest = {"dataset": a.dataset, "tag": a.tag, "scenario": a.scenario, "seed": a.seed,
                "features": list(X.columns), "sites": {}}
    for k in range(N_SITES):
        name = f"site-{k + 1}"
        d = os.path.join(root, name)
        os.makedirs(d, exist_ok=True)
        for part, idx in (("train", sites[k]), ("valid", val_parts[k])):
            df = X.iloc[idx].copy()
            df["y"] = y[idx]
            df.to_parquet(os.path.join(d, f"{part}.parquet"), index=False)
        manifest["sites"][name] = {"n_train": int(len(sites[k])), "events_train": int(y[sites[k]].sum()),
                                   "n_valid": int(len(val_parts[k]))}
    ytr = y[train_idx]
    manifest["pooled"] = {"n_train": int(len(train_idx)), "events_train": int(ytr.sum()),
                          "n_val": int(len(val_idx)), "events_val": int(y[val_idx].sum())}
    manifest["scale_pos_weight"] = float((ytr == 0).sum() / max((ytr == 1).sum(), 1))
    manifest["pooled"]["rows_in_no_site"] = int(left)
    with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"wrote {N_SITES} sites to {root}")
    for name, s in manifest["sites"].items():
        print(f"  {name}: train {pl.cell(s['n_train'])} (events {pl.cell(s['events_train'])}), valid {pl.cell(s['n_valid'])}")
    print(f"  pooled train {pl.cell(manifest['pooled']['n_train'])}, common val {pl.cell(manifest['pooled']['n_val'])}")


if __name__ == "__main__":
    args = parse_args()
    if args.tag:
        os.environ["PILOT_TAG"] = args.tag      # pilot_lib reads it at import
    if args.quick:
        os.environ["PILOT_QUICK"] = "1"
    import pilot_lib
    pilot_lib.guard(lambda: main(args))
