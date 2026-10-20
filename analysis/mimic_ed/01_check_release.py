#!/usr/bin/env python3
"""Step 01 -- check a MIMIC-IV-ED release: checksums + aggregate summary via the loader.

Writes out/01_check_release.txt. That file holds aggregates only (counts, rates,
medians; any count below 11 shown as "<11") so it can be read by Claude without
moving restricted data to an online service (PhysioNet DUA clause 3 / LLM
guidance). Nothing row-level is printed or written; on error only the exception
type is recorded, because pandas messages can quote cell values.

    python analysis/mimic_ed/01_check_release.py                 # full-2.2 if present, else demo-2.2
    python analysis/mimic_ed/01_check_release.py --release demo  # the open demo
"""
import argparse
import datetime
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "out")
sys.path.insert(0, os.path.join(BASE, "safe-model-bundle", "poc"))
MIN_CELL = 11


def cell(n):
    return f"{n:,}" if n >= MIN_CELL else "<11"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--release", choices=["full", "demo"], default=None)
    a = p.parse_args()

    root = os.path.join(BASE, "data", "mimic-iv-ed")
    rel = a.release or ("full" if os.path.isdir(os.path.join(root, "full-2.2", "ed")) else "demo")
    rel_dir = os.path.join(root, f"{rel}-2.2")
    ed_dir = os.path.join(rel_dir, "ed")
    lines = [f"# 01_check_release  {datetime.datetime.now():%Y-%m-%d %H:%M}",
             f"release            : {rel} ({os.path.relpath(rel_dir, BASE)})", ""]

    # --- checksums -------------------------------------------------------
    sums = os.path.join(rel_dir, "SHA256SUMS.txt")
    ok = bad = 0
    if os.path.exists(sums):
        for line in open(sums, encoding="utf-8").read().splitlines():
            digest, _, name = line.strip().partition(" ")
            name = name.strip()
            if not name:
                continue
            path = os.path.join(rel_dir, name.replace("/", os.sep))
            good = os.path.exists(path) and sha256(path) == digest
            ok += good; bad += not good
            if not good:
                lines.append(f"  MISSING/BAD  {name}")
        lines.append(f"checksums          : {ok} ok, {bad} missing/bad")
    else:
        lines.append("checksums          : SHA256SUMS.txt not found")

    # --- aggregate summary through the loader ----------------------------
    try:
        from src.mimic_ed_loader import (load_mimic_ed_cohort, CONTINUOUS_VARS,
                                         CATEGORICAL_VARS, OUTCOME)
        df = load_mimic_ed_cohort(ed_dir)
    except Exception as e:  # noqa: BLE001 -- message may quote data values
        lines.append(f"loader             : FAILED ({type(e).__name__}; message suppressed)")
    else:
        n = len(df)
        lines += [
            f"ED stays           : {cell(n)}",
            f"features           : {len(CONTINUOUS_VARS) + len(CATEGORICAL_VARS)}",
            f"admitted           : {cell(int(df[OUTCOME].sum()))} ({df[OUTCOME].mean():.1%})",
            "", "continuous (median after imputation)",
        ]
        lines += [f"  {c:<18} {df[c].median():>8.1f}" for c in CONTINUOUS_VARS]
        lines += ["", "categorical (level: stays, cells <11 suppressed)"]
        for c in CATEGORICAL_VARS:
            counts = df[c].value_counts().sort_index()
            lines.append(f"  {c:<18} " + "  ".join(f"{k}: {cell(int(v))}" for k, v in counts.items()))
        if rel == "full" and n < 100_000:
            lines += ["", "WARNING: fewer stays than expected for the full release; check the download."]

    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, f"01_check_release_{rel}.txt")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"done -> {os.path.relpath(out, BASE)}")


if __name__ == "__main__":
    main()
