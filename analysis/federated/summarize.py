"""Collect out/<dataset>/fl_*.json into out/<dataset>/SUMMARY.md (aggregates only).

    python summarize.py [dataset] [tag]

One row per run (scenario, seed, config); when a scenario/config has two or more seeds, a second table
gives the seed mean and t interval of F - A_x and of F - B_avg.
"""
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "snuh_pilot"))


def main():
    ds = sys.argv[1] if len(sys.argv) > 1 else "synpuf"
    if len(sys.argv) > 2:
        os.environ["PILOT_TAG"] = sys.argv[2]
    import pilot_lib as pl

    folder = os.path.join(HERE, "out", pl.tag(ds))
    runs = []
    for p in sorted(glob.glob(os.path.join(glob.escape(folder), "fl_*.json"))):
        if p.endswith("_nofl.json"):
            continue
        with open(p, encoding="utf-8") as f:
            runs.append(json.load(f))
    if not runs:
        sys.exit(f"no fl_*.json in {folder}")

    L = [f"# Federated XGBoost vs central, {pl.tag(ds)}", "",
         "AUROC on the common validation set; F = FLARE histogram-based horizontal XGBoost, A_x = central XGBoost, "
         "B_k = single-site XGBoost (min-max), B_avg = mean of the three local predictions. "
         "Delta = difference in AUROC, bootstrap 95% interval; NI = lower bound above -0.02.", "",
         "| scenario | seed | config | A_x | B_k | B_avg | F | F - A_x [95% CI] | NI | F - B_avg [95% CI] | r(F, A_x) |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    by = {}
    for r in sorted(runs, key=lambda r: (r["scenario"], r["config"], r["seed"])):
        a, f = r["arms"], r["federated"]
        loc = [v["auroc"] for k, v in a.items() if k.startswith("B_") and k != "B_avg"]
        d, b = f["delta_auroc_vs_central"], f["delta_auroc_vs_prediction_average"]
        L.append(f"| {r['scenario']} | {r['seed']} | {r['config']} | {a['A_x']['auroc']:.4f} | "
                 f"{min(loc):.4f}-{max(loc):.4f} | {a['B_avg']['auroc']:.4f} | {a['F']['auroc']:.4f} | "
                 f"{d['delta']:+.4f} [{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}] | {'yes' if d['non_inferior'] else 'no'} | "
                 f"{b['delta']:+.4f} [{b['ci95'][0]:+.4f}, {b['ci95'][1]:+.4f}] | "
                 f"{f['pred_fidelity_vs_central']['pearson']:.4f} |")
        by.setdefault((r["scenario"], r["config"]), []).append((d["delta"], b["delta"]))

    multi = {k: v for k, v in by.items() if len(v) >= 2}
    if multi:
        L += ["", "Seed means (t interval over seeds):", "",
              "| scenario | config | seeds | F - A_x | F - B_avg |", "|---|---|---|---|---|"]
        for (scn, cfg), v in sorted(multi.items()):
            m1, lo1, hi1 = pl.t_ci([x[0] for x in v])
            m2, lo2, hi2 = pl.t_ci([x[1] for x in v])
            L.append(f"| {scn} | {cfg} | {len(v)} | {m1:+.4f} [{lo1:+.4f}, {hi1:+.4f}] | {m2:+.4f} [{lo2:+.4f}, {hi2:+.4f}] |")

    r0 = runs[0]
    L += ["", f"n validation {r0['n_val']}; rounds: " +
          ", ".join(f"{c} {next(r['rounds'] for r in runs if r['config'] == c)}" for c in sorted({r['config'] for r in runs})) +
          f"; xgboost {r0['versions']['xgboost']}, nvflare {r0['versions'].get('nvflare', '-')}; {r0['versions']['platform']}.", ""]
    out = os.path.join(folder, "SUMMARY.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n".join(L))
    print(f"wrote {out}")


if __name__ == "__main__":
    import pilot_lib
    pilot_lib.guard(main)
