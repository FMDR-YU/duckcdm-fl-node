# -*- coding: utf-8 -*-
"""Environment diagnosis for the pyarrow import failure (reads no data).

Each import order runs in a fresh Python process, and the *real* exception text is recorded
(pandas hides it behind "Unable to find a usable engine"). Also records the interpreter, user-site,
and the PATH entries that come before Python's own folders, where a conflicting DLL could sit.
Writes out/diag_env.txt.

    python diag_env.py
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = {
    'pyarrow alone': 'import pyarrow',
    'pyarrow.parquet alone': 'import pyarrow.parquet',
    'numpy, pandas, then pyarrow': 'import numpy, pandas; import pyarrow.parquet',
    'sklearn, then pyarrow (step 00 order)': 'from sklearn.model_selection import train_test_split; import pyarrow.parquet',
    'xgboost/lightgbm/catboost, then pyarrow': 'import xgboost, lightgbm, catboost; import pyarrow.parquet',
    'pandas.read_parquet engine': 'import pandas.io.parquet as q; q.get_engine("auto")',
}


def main():
    lines = [f'# diag_env  {time.strftime("%Y-%m-%d %H:%M")}',
             f'python      : {sys.executable}  {sys.version.split()[0]}',
             f'cwd         : {os.getcwd()}',
             f'PYTHONPATH  : {os.environ.get("PYTHONPATH", "")!r}',
             f'NOUSERSITE  : {os.environ.get("PYTHONNOUSERSITE", "")!r}', '']
    for name, code in TESTS.items():
        r = subprocess.run([sys.executable, '-c', code + '; print("OK")'], capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        if 'OK' in r.stdout:
            lines.append(f'[ok]   {name}')
        else:
            err = (r.stderr or r.stdout).strip().splitlines()
            lines.append(f'[FAIL] {name}')
            lines += ['         ' + e for e in err[-6:]]
    import site
    lines += ['', 'site:',
              f'  APPDATA           : {os.environ.get("APPDATA", "")}',
              f'  USERPROFILE       : {os.environ.get("USERPROFILE", "")}',
              f'  ENABLE_USER_SITE  : {site.ENABLE_USER_SITE}',
              f'  user site         : {site.getusersitepackages()}  (exists: {os.path.isdir(site.getusersitepackages())})',
              f'  system site       : {site.getsitepackages()}',
              '', 'package versions and locations:']
    for mod in ('numpy', 'pandas', 'scipy', 'sklearn', 'xgboost', 'lightgbm', 'catboost', 'statsmodels',
                'pyarrow', 'joblib'):
        r = subprocess.run([sys.executable, '-c', f'import {mod} as m; print(m.__version__, m.__file__)'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        lines.append(f'  {mod:<12} ' + (r.stdout.strip() or 'MISSING'))
    lines += ['', 'PATH entries in order (DLL search):']
    lines += [f'  {i:>2}. {p}' for i, p in enumerate(os.environ.get('PATH', '').split(os.pathsep)) if p]
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    out = os.path.join(HERE, 'out', 'diag_env.txt')
    open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('done ->', out)


if __name__ == '__main__':
    main()
