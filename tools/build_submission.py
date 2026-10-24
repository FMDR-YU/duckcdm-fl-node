# -*- coding: utf-8 -*-
"""Build the BMC MIDM submission package: rebuild every docx from the Markdown sources, export the figures to TIFF and copy the
files with submission names into Manuscript/v2/BMC_MIDM/submission/ with a README (file list, SHA-256, journal checklist).

    python tools/build_submission.py [--no-rebuild]

Run with the system python (pypandoc and Pillow). Nothing here reads patient data; the inputs are the manuscript sources.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from datetime import date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, 'Manuscript', 'v2', 'BMC_MIDM')
OUT = os.path.join(SRC, 'submission')
AF_TITLES = {1: 'Policy audit of six platforms', 2: 'Hypotheses, decision rules, verdicts and deviation log', 3: 'Node isolation check',
             4: 'Predictor lists, cohort characteristics and participant flow', 5: 'Utility and exposure of every configuration and route', 6: 'Canary benchmark',
             7: 'Reproduction on public data from the command line (instruction, commands and log)', 8: 'TRIPOD+AI checklist'}
FIG_TITLES = {1: 'One institutional node and the federation', 2: 'ATLAS Data Sources dashboards of the three virtual hospitals',
              3: 'AUROC of each training route minus the central model', 4: 'Federated accuracy and exposure against the number of real hospitals',
              5: 'Export exposure against training size', 6: 'Canary benchmark on six cohorts'}


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def words(md, start, end):
    s = open(md, encoding='utf-8').read()
    a = s.split(start, 1)[1].split(end, 1)[0]
    a = re.sub(r'\*\*(Background|Methods|Results|Conclusions)\.\*\*', '', a)
    return len(a.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-rebuild', action='store_true', help='copy the existing docx and tif files without rebuilding them')
    a = ap.parse_args()
    md = sorted(f for f in os.listdir(SRC) if f.endswith('.md'))
    if not a.no_rebuild:
        subprocess.run([sys.executable, os.path.join(BASE, 'tools', 'md2docx.py')] + [os.path.join(SRC, f) for f in md], check=True)
        subprocess.run([sys.executable, os.path.join(BASE, 'tools', 'figs_to_tiff.py')], check=True)
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    files = []                     # (submission name, source, description)
    files.append(('01_Manuscript.docx', os.path.join(SRC, 'manuscript_BMC.docx'),
                  'Main manuscript: title page, abstract, main text, declarations, references, figure legends, tables'))
    files.append(('02_Cover_letter.docx', os.path.join(SRC, 'cover_letter_BMC.docx'), 'Cover letter to the editors'))
    for k in range(1, 7):
        files.append((f'Fig{k}.tif', os.path.join(SRC, 'figures', f'Fig{k}.tif'), f'Figure {k}. {FIG_TITLES[k]} (TIFF, 170 mm wide, >= 300 dpi)'))
    for k in range(1, 9):
        srcs = [f for f in os.listdir(SRC) if f.startswith(f'additional_file_{k}_') and f.endswith('.docx')]
        if not srcs:
            print(f'  !! additional file {k} docx missing')
            continue
        files.append((f'Additional_file_{k}.docx', os.path.join(SRC, srcs[0]), f'Additional file {k}. {AF_TITLES[k]}'))
    rows = []
    for name, src, desc in files:
        if not os.path.exists(src):
            print(f'  !! missing {src}')
            continue
        dst = os.path.join(OUT, name)
        shutil.copyfile(src, dst)
        rows.append((name, desc, os.path.getsize(dst), sha256(dst)))
    man = os.path.join(SRC, 'manuscript_BMC.md')
    s = open(man, encoding='utf-8').read()
    n_abs = words(man, '**Background.**', '**Keywords.**')
    body = s.split('# Background', 1)[1].split('# List of abbreviations', 1)[0] if '# List of abbreviations' in s else s.split('# Background', 1)[1].split('# Declarations', 1)[0]
    n_body = len(re.sub(r'<!--.*?-->', '', body, flags=re.S).split())
    n_ref = len(re.findall(r'^\d+\. ', s.split('# References', 1)[1].split('# Figure legends', 1)[0], flags=re.M)) if '# References' in s else 0
    placeholders = sorted(set(m.group(0) for m in re.finditer(r'\[(SNUH-FL|verify|postal address|e-mail|address[^\]]*|Confirm with[^\]]*|date|names[^\]]*)[^\]]*\]', s)))
    cl = open(os.path.join(SRC, 'cover_letter_BMC.md'), encoding='utf-8').read()
    placeholders += sorted(set('cover letter: ' + m.group(0) for m in re.finditer(r'\[(date|address[^\]]*|names[^\]]*)[^\]]*\]', cl)))
    lines = [f'# BMC Medical Informatics and Decision Making submission package ({date.today().isoformat()})', '',
             'Built by `tools/build_submission.py` from `Manuscript/v2/BMC_MIDM/*.md` (docx via `tools/md2docx.py`) and `Figures/v2/` (TIFF via '
             '`tools/figs_to_tiff.py`). Rebuild the whole package after any change to the sources; do not edit the files here by hand.', '',
             '| file | content | bytes | SHA-256 |', '|---|---|---|---|']
    for name, desc, size, h in rows:
        lines.append(f'| {name} | {desc} | {size:,} | {h[:16]} |')
    lines += ['', '## Counts', '', f'- Abstract: {n_abs} words (BMC limit 350).', f'- Main text (Background to Conclusions, without tables, legends and references): about {n_body:,} words (no limit for Research articles).',
              f'- References: {n_ref}.', f'- Figures: {sum(1 for r in rows if r[0].startswith("Fig"))} (TIFF). Additional files: {sum(1 for r in rows if r[0].startswith("Additional"))}.',
              f'- Placeholders still in the manuscript source: {", ".join(placeholders) if placeholders else "none"}.', '',
              '## BMC MIDM checklist (Research article)', '',
              '- [ ] Title page: title, full author name, affiliation, e-mail of the corresponding author, ORCID.',
              '- [ ] Abstract structured (Background, Methods, Results, Conclusions), at most 350 words; keywords.',
              '- [ ] Declarations present: Ethics approval and consent to participate (IRB number and exemption dates), Consent for publication, '
              'Availability of data and materials, Competing interests, Funding, Authors\' contributions, Acknowledgements.',
              '- [ ] References in Vancouver style, numbered in order of first citation; every DOI checked.',
              '- [ ] Figures uploaded as separate TIFF files (170 mm wide, at least 300 dpi), legends at the end of the main text.',
              '- [ ] Tables inside the main text with titles; no colour fills.',
              '- [ ] Additional files uploaded separately, each cited in the text as "Additional file N" and listed under "Additional files".',
              '- [ ] Cover letter: statement that the manuscript is not under consideration elsewhere; earlier desk rejection disclosed; suggested reviewers.',
              '- [ ] Reporting guideline: TRIPOD+AI items addressed (prediction-model aspects); a completed checklist may be requested.',
              '- [ ] Data availability: public repository and Zenodo DOI; SNUH extract not shareable (DRB); PhysioNet data under DUA.',
              '- [ ] Author: sole author; competing interests none; funding statement with the grant number.', '']
    open(os.path.join(OUT, 'README.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
    print(f'package: {len(rows)} files -> {OUT}')
    print(f'abstract {n_abs} words; body about {n_body:,} words; references {n_ref}; placeholders: {placeholders or "none"}')


if __name__ == '__main__':
    main()
