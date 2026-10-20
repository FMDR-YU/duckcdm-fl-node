# -*- coding: utf-8 -*-
"""Run steps 00-06 in order for one dataset. Each step is resumable, so re-running after an
interruption continues where it stopped. Console output is aggregate-only (see README).

    python run_pilot.py --dataset snuh            # full run (~5-6 h on 4 threads)
    python run_pilot.py --dataset synpuf --quick  # 3,000-row smoke test (~5 min)
    python run_pilot.py --dataset snuh --from 03  # start at a later step
    python run_pilot.py --dataset snuh --tag cdm  # matrix from analysis/snuh_cdm P4 (fixed sites), step 00 skipped
    python run_pilot.py --dataset synpuf --model xgb   # single-XGBoost family (+ federated models from data/federated if present)
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = ['00_build_matrix.py', '01_train_targets.py', '02_train_shadows.py', '03_attack_audit.py',
         '03b_size_curve.py',            # exposure against training size (H6); xgb family only, skipped otherwise
         '04_gate1_formats.py', '05_gate3_escrow.py', '06_summarize.py']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', choices=['snuh', 'synpuf', 'mimic_ed', 'eicu'], required=True)
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--from', dest='start', default='00')
    ap.add_argument('--irb', default='', help='IRB exemption number of this study (required for snuh)')
    ap.add_argument('--tag', default='', help='matrix variant, e.g. cdm = data/ckd_pilot/matrix_<ds>_cdm.parquet '
                                              'written by analysis/snuh_cdm/p4_site_features.py')
    ap.add_argument('--model', choices=['ensemble', 'xgb'], default='ensemble',
                    help='ensemble = published four-model structure (default); xgb = one XGBoost per target, '
                         'comparable with the federated (FLARE) model; outputs go to <ds>_xgb folders')
    a = ap.parse_args()
    env = dict(os.environ)
    if a.tag:
        env['PILOT_TAG'] = a.tag
    env['PILOT_MODEL'] = a.model
    if a.irb:
        env['PILOT_IRB'] = a.irb
    env['PYTHONIOENCODING'] = 'utf-8'
    if a.quick:
        env['PILOT_QUICK'] = '1'
    # console output is aggregate-only by design (counts, metrics, code locations of errors),
    # so it is also kept in out/<ds>/run_log.txt for Claude to read
    od = os.path.join(os.environ.get('PILOT_OUT_DIR') or os.path.join(HERE, 'out'),
                      a.dataset + (f'_{a.tag}' if a.tag else '') + ('_xgb' if a.model == 'xgb' else '') + ('_quick' if a.quick else ''))
    os.makedirs(od, exist_ok=True)
    logf = open(os.path.join(od, 'run_log.txt'), 'a', encoding='utf-8')

    def say(line):
        print(line, flush=True)
        logf.write(line + '\n'); logf.flush()

    def run(cmd):
        p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding='utf-8', errors='replace')
        for line in p.stdout:
            say(line.rstrip('\n'))
        return p.wait()

    say(f'=== run_pilot {a.dataset}{" tag=" + a.tag if a.tag else ""}{" model=xgb" if a.model == "xgb" else ""}'
        f'{" quick" if a.quick else ""} {time.strftime("%Y-%m-%d %H:%M")} from {a.start}')
    for s in STEPS:
        if s[:2] < a.start:
            continue
        if s.startswith('00') and a.tag and a.dataset == 'snuh':
            m = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'data', 'ckd_pilot', f'matrix_{a.dataset}_{a.tag}.parquet')
            if not os.path.exists(m):
                say(f'[{s}] data/ckd_pilot/matrix_{a.dataset}_{a.tag}.parquet not found -- run analysis/snuh_cdm P4 first')
                sys.exit(1)
            say(f'[{s}] skipped: matrix_{a.dataset}_{a.tag}.parquet comes from analysis/snuh_cdm P4')
            continue
        if s.startswith('00') and a.dataset == 'snuh' and os.path.exists(
                os.path.join(os.path.dirname(os.path.dirname(HERE)), 'data', 'ckd_pilot', 'matrix_snuh.parquet')):
            say(f'[{s}] matrix exists -- skipped (delete data/ckd_pilot/matrix_snuh.parquet to rebuild)')
            continue
        t = time.time()
        say(f'[{s}] start {time.strftime("%H:%M")}')
        rc = run([sys.executable, os.path.join(HERE, s), '--dataset', a.dataset])
        if rc != 0:
            say(f'[{s}] stopped (exit {rc}). Fix and re-run with --from {s[:2]}')
            sys.exit(1)
        say(f'[{s}] done in {(time.time() - t) / 60:.1f} min')
    say('all steps done -> analysis/snuh_pilot/out/')


if __name__ == '__main__':
    main()
