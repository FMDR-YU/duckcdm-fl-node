#!/usr/bin/env python3
"""Step 01 -- check an eICU-CRD release: checksums of the files the adapter reads + an aggregate summary through the adapter.

Writes out/01_check_release_<release>.txt. That file holds aggregates only (counts, rates, medians; any count of people below 11
shown as "<11") so it can be read by Claude without moving restricted data to an online service (PhysioNet DUA / LLM guidance).
Nothing row-level is printed or written, no hospital id is listed, and on error only the exception type is recorded, because pandas
messages can quote cell values.

    python analysis/eicu/01_check_release.py                 # full-2.0 if present, else demo-2.0.1
    python analysis/eicu/01_check_release.py --release demo  # the open demo
    python analysis/eicu/01_check_release.py --release full  # data/eicu/full-2.0 (credentialed; run by the user)

Files needed in data/eicu/full-2.0/: patient.csv.gz, apacheApsVar.csv.gz, apachePredVar.csv.gz (about 18.5 MB together) and, for the
checksum comparison, SHA256SUMS.txt from the same PhysioNet page.
"""
import argparse
import datetime
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
MIN_CELL = 11
REQUIRED = ["patient.csv.gz", "apacheApsVar.csv.gz", "apachePredVar.csv.gz"]
RELEASES = {"full": "full-2.0", "demo": "demo-2.0.1"}
BANDS = (100, 500, 1000, 2000)           # persons per hospital in the analysis matrix


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
    p.add_argument("--release", choices=list(RELEASES), default=None)
    p.add_argument("--data-root", default=os.path.join(BASE, "data", "eicu"))
    p.add_argument("--out-dir", default=os.path.join(HERE, "out"))
    a = p.parse_args()

    rel = a.release or ("full" if os.path.exists(os.path.join(a.data_root, RELEASES["full"], "patient.csv.gz")) else "demo")
    rel_dir = os.path.join(a.data_root, RELEASES[rel])
    lines = [f"# 01_check_release  {datetime.datetime.now():%Y-%m-%d %H:%M}",
             f"release            : {rel} ({RELEASES[rel]})", ""]

    # --- files and checksums ----------------------------------------------------------------------------------------------
    present = [f for f in REQUIRED if os.path.exists(os.path.join(rel_dir, f))]
    lines.append(f"required files     : {len(present)} of {len(REQUIRED)} present" + ("" if len(present) == len(REQUIRED) else
                                                                                       "  MISSING: " + ", ".join(f for f in REQUIRED if f not in present)))
    sums = os.path.join(rel_dir, "SHA256SUMS.txt")
    if os.path.exists(sums):
        expected = {}
        for line in open(sums, encoding="utf-8").read().splitlines():
            digest, _, name = line.strip().partition(" ")
            if name.strip():
                expected[name.strip().replace("/", os.sep)] = digest
        ok = bad = 0
        for f in present:
            good = expected.get(f) == sha256(os.path.join(rel_dir, f))
            ok += good
            bad += not good
            if not good:
                lines.append(f"  BAD or not listed  {f}")
        lines.append(f"checksums          : {ok} ok, {bad} bad (compared for the {len(present)} required files that are present)")
    else:
        lines.append("checksums          : SHA256SUMS.txt not found in the release folder (download it from the same page)")

    # --- aggregate summary through the adapter ----------------------------------------------------------------------------
    if len(present) == len(REQUIRED):
        try:
            import matrix_eicu as E
            m, feats, subs, info = E.build(rel_dir)
        except Exception as e:  # noqa: BLE001 -- message may quote data values
            lines.append(f"adapter            : FAILED ({type(e).__name__}; message suppressed)")
        else:
            n = len(m)
            lines += [
                f"ICU stays          : {cell(info['n_stays_in_release'])}",
                f"people             : {cell(info['n_people'])}  (first stay each)",
                f"analysis rows      : {cell(n)}  (first stay with APACHE IV first-day variables and a known hospital outcome)",
                f"features           : {len(feats)}",
                f"hospital mortality : {cell(int(m['y'].sum()))} ({m['y'].mean():.1%})",
                f"train / validation : {cell(int((m['split'] == 'train').sum()))} / {cell(int((m['split'] == 'val').sum()))}",
                "", "persons per hospital (analysis rows): hospitals and the people in them",
            ]
            sizes = m["hospital_id"][m["hospital_id"] >= 0].value_counts()
            lines.append(f"  hospitals        : {len(sizes)}")
            for b in BANDS:
                big = sizes[sizes >= b]
                lines.append(f"  with >= {b:<5}    : {len(big)} hospitals, {cell(int(big.sum()))} people ({big.sum() / n:.1%} of the rows)" if len(big)
                             else f"  with >= {b:<5}    : 0 hospitals")
            lines += ["", "stratum (unit type group)"]
            lines += [f"  {k:<18} {cell(int(v))}" for k, v in m["stratum"].value_counts().items()]
            lines += ["", "missing per feature (share)"]
            miss = m[feats].isna().mean().sort_values(ascending=False)
            lines += [f"  {k:<22} {v:.1%}" for k, v in miss[miss > 0.10].items()] or ["  none above 10%"]
            if rel == "full" and info["n_stays_in_release"] < 150_000:
                lines += ["", "WARNING: fewer ICU stays than expected for the full release (about 200,000); check the download."]
    os.makedirs(a.out_dir, exist_ok=True)
    out = os.path.join(a.out_dir, f"01_check_release_{rel}.txt")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"done -> {os.path.relpath(out, BASE)}")


if __name__ == "__main__":
    main()
