# -*- coding: utf-8 -*-
"""Additional files of the manuscript, generated from the pilot aggregates (no patient-level data).

Additional file 2  hypotheses, decision rules and verdicts per cohort: the "Pre-specified decision rules" table of each
                   06_summary.md, side by side, plus the gate-2 decisions of the main routes.
Additional file 5  utility and exposure of every configuration (published, regularized, over-fitted, plain) and route:
                   AUROC and the three attack quantities with t-based 95% intervals over seeds (01_utility_long.csv,
                   03_attacks_long.csv), and the federated seed means from analysis/federated/out/<cohort>/SUMMARY.md.

    python make_additional_files.py [--out DIR]      (default Manuscript/v2/BMC_MIDM)
"""
import argparse
import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilot_lib as L  # noqa: E402

COHORTS = [('SynPUF (development, virtual sites)', 'synpuf_xgb', 'synpuf'),
           ('eICU-CRD, 3 largest hospitals (h3a)', 'eicu_h3a_xgb', 'eicu_h3a'),
           ('eICU-CRD, hospitals of unequal size (h3b)', 'eicu_h3b_xgb', 'eicu_h3b')]
VARIANT_LABEL = {'xgb_krcp': 'published', 'xgb_regularized': 'regularized', 'xgb_leaky': 'over-fitted (positive control)', 'xgb_plain': 'plain (no sampling)'}
ROUTE_LABEL = {'A_0': 'A central', 'Aprime_0': 'A′ size control', 'B1_0': 'B1 site 1', 'B1_1': 'B1 site 2', 'B1_2': 'B1 site 3',
               'B1_comb': 'B1 averaged predictions', 'F_B1': 'F federated (B1)', 'B2_0': 'B2 site 1', 'B2_1': 'B2 site 2', 'B2_2': 'B2 site 3',
               'B2_comb': 'B2 averaged predictions', 'F_B2': 'F federated (B2)'}
HYP_TEXT = {
    'H1': 'The audit separates an over-fitted from a regularized model: mean shadow-model AUC of the over-fitted central model above 0.55, of the regularized one at most 0.55, and the regularized AUROC not lower.',
    'H2': 'Site models are more exposed than the central model and most of the excess is training size (B1): lower bound of the seed interval of (site mean minus central shadow AUC) above 0 and (A′ minus A) / (site mean minus A) at least 0.5. B2 part: the gap is larger with unequal sites.',
    'H3': 'The averaged site predictions are non-inferior to the central model: lower bound of ΔAUROC above −0.02.',
    'H4': 'Formats and reproduction hold: Gate 1 maximum prediction difference below 10⁻⁶; Gate 3 signature and data hash match and |ΔAUROC| at most 10⁻⁴; federated re-run in a fresh workspace reproduces the model.',
    'H5': 'The federated model is non-inferior (lower bound of F − A above −0.02), no more exposed than the central model (shadow AUC of F at most that of A plus 0.01) and less exposed than the site models (lower bound of site mean minus F above 0).',
    'H6': 'Exposure falls with training size: Spearman correlation of the seed-mean shadow AUC with size below 0 and upper bound of the slope per log10 of size below 0.',
}


def read_verdicts(folder):
    """Parse the 'Pre-specified decision rules' table of 06_summary.md -> DataFrame(hypothesis, role, target, verdict, evidence)."""
    p = os.path.join(L.OUT_ROOT, folder, '06_summary.md')
    if not os.path.exists(p):
        return None
    rows, inside = [], False
    for ln in open(p, encoding='utf-8'):
        if ln.startswith('## Pre-specified decision rules'):
            inside = True
            continue
        if inside and ln.startswith('## '):
            break
        if inside and ln.startswith('| H'):
            c = [x.strip() for x in ln.strip().strip('|').split('|')]
            rows.append({'hypothesis': c[0], 'role': c[1], 'target': c[2], 'verdict': c[3].replace('**', ''), 'evidence': c[4]})
    return pd.DataFrame(rows)


def ci_text(vals, nd=3):
    vals = pd.Series(vals).dropna()
    if vals.empty:
        return ''
    m, lo, hi = L.t_ci(vals)
    if np.isnan(lo):
        return f'{m:.{nd}f}'
    return f'{m:.{nd}f} [{lo:.{nd}f}, {hi:.{nd}f}]'


def additional_file_2(out):
    md = ['# Additional file 2. Hypotheses, decision rules and verdicts per cohort', '',
          'Verdicts are computed by the analysis code (`06_summarize.py`) from the pre-specified decision rules; intervals are t-based over ten seeds. '
          'The two primary verdicts are H5 and the B1 part of H2 for the published configuration with equal-sized sites; every other row is secondary. '
          'Each hypothesis is judged on its own; no multiplicity correction. The SNUH virtual-hospital rows are added after the federated arm is run under the amended ethics approval.', '',
          '## Hypotheses and decision rules', '']
    for h, t in HYP_TEXT.items():
        md.append(f'- **{h}.** {t}')
    md += ['', '## Verdicts', '']
    frames = []
    for name, folder, _ in COHORTS:
        v = read_verdicts(folder)
        if v is None:
            continue
        v = v.assign(cohort=name)
        frames.append(v)
    allv = pd.concat(frames)
    keys = allv[['hypothesis', 'role', 'target']].drop_duplicates()
    hdr = '| hypothesis | role | configuration / target | ' + ' | '.join(n for n, f, _ in COHORTS if read_verdicts(f) is not None) + ' |'
    md += [hdr, '|' + '---|' * (3 + len(frames))]
    for _, k in keys.iterrows():
        cells = []
        for name, folder, _ in COHORTS:
            v = allv[(allv.cohort == name) & (allv.hypothesis == k.hypothesis) & (allv.target == k.target)]
            cells.append(v.verdict.iloc[0] if not v.empty else 'not run')
        md.append(f'| {k.hypothesis} | {k.role} | {k.target} | ' + ' | '.join(cells) + ' |')
    md += ['', '## Evidence behind each verdict', '']
    for name, folder, _ in COHORTS:
        v = allv[allv.cohort == name]
        md += [f'### {name}', '', '| hypothesis | target | verdict | evidence |', '|---|---|---|---|']
        for _, r in v.iterrows():
            md.append(f'| {r.hypothesis} | {r.target} | {r.verdict} | {r.evidence} |')
        md.append('')
    md += ['## Changes to the analysis plan', '',
           'The analysis plan (version 1) was fixed in the study repository before the SNUH analyses; the changes made afterwards, with their dates and whether results had been seen, are:', '',
           '| date | change | reason | after seeing results? |', '|---|---|---|---|',
           '| 2026-10-10 | Wording: the common validation rows are present at each federated site only as a monitoring file; no early stopping is used, so they do not affect training. | The original sentence differed from the implementation; the analysis did not change. | no |',
           '| 2026-10-10 | Decision rules made explicit (H1 target models, H2 scenario and size-share criterion, H3 scenario, H4 components, H5 scenario and seed handling) and computed by code; the third clause of H5 implemented as the lower bound of the per-seed difference. | The summary showed H5 only as a comparison of means and H1, H2, H4 and H6 had no computed verdict. | no (tested on generated data) |',
           '| 2026-10-10 | H4 requires Gate 1 and Gate 3 for every configuration; a hypothesis with one failed clause is "not supported"; the averaged predictor is audited as a black box and the site models are reported next to it. | Gate 3 had run for one configuration only; the averaged predictor was much less exposed than its components, which needed an explicit reading rule. | yes (synthetic rehearsal, not used for verdicts) |',
           '| 2026-10-11 | Primary verdicts fixed to H5 (published configuration, B1) and the B1 part of H2; H2 and H3 split into B1 and B2 parts; the exposure margin of H5 kept at 0.01; LiRA and loss-attack differences reported descriptively. | Removes the freedom to choose the headline after the results; the LiRA low-FPR difference seen on the synthetic cohort (+0.011) is reported, not used for the verdict. | yes (synthetic rehearsal) |',
           '| 2026-10-11 | All pre-specified analyses are reported whatever the verdict; no interim analysis; seeds are not added after results are seen; seed intervals do not include sampling variation of the cohort. | Prevents selective reporting. | no |',
           '| 2026-10-11 | Reference models for the online LiRA and RMIA raised from 64 to 256 (main setting; 64 reported as sensitivity). The shadow-model attack used for the verdict (16 models) is unchanged. | With 64 reference models the tail exposure of models of different training size was inflated (inclusion probability proportional to size); with 256 the site-minus-central TPR@1%FPR fell from +0.032 to +0.010. Verdicts H1 to H6 identical under both settings. | yes (synthetic development data) |',
           '| 2026-10-11 | Added: synthetic-canary robustness run of the 141 settings; transfer summary that applies the development thresholds unchanged; training sizes limited to 75% of the base rows. | To test whether the choice of canary determines the ground truth; a defect found on the small public demo cohort. | yes (after the flipped-label results) |',
           '| 2026-10-19 | eICU real-hospital site configurations (three largest; largest, median and smallest among hospitals with at least 2,000 rows) fixed before the matrices were built. | Real multi-site arm independent of the ethics amendment. | no |']
    with open(os.path.join(out, 'additional_file_2_hypotheses_verdicts.md'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(md) + '\n')
    print('wrote', os.path.join(out, 'additional_file_2_hypotheses_verdicts.md'))


def fl_seed_means(tag):
    """Seed-mean F − A and F − B_avg per configuration from the fl_*.json files (all configurations, including plain)."""
    files = sorted(glob.glob(os.path.join(glob.escape(os.path.join(L.BASE, 'analysis', 'federated', 'out', tag)), 'fl_*.json')))
    rows = []
    for f in files:
        if f.endswith('_nofl.json'):
            continue
        d = json.load(open(f, encoding='utf-8'))
        a = d['arms']
        if 'F' not in a:
            continue
        rows.append({'scenario': d['scenario'], 'config': d['config'], 'seed': d['seed'], 'A': a['A_x']['auroc'], 'F': a['F']['auroc'], 'B_avg': a['B_avg']['auroc'],
                     'B_min': min(a[k]['auroc'] for k in a if k.startswith('B_') and k != 'B_avg'), 'B_max': max(a[k]['auroc'] for k in a if k.startswith('B_') and k != 'B_avg')})
    return pd.DataFrame(rows)


def additional_file_5(out):
    md = ['# Additional file 5. Utility and exposure of every configuration and route', '',
          'AUROC on the common validation set and the Gate 2 audit quantities (shadow-model attack AUC with 16 shadow models; online LiRA AUC and true-positive rate at 1% false-positive rate with 256 reference models on SynPUF and 64 on eICU), mean over ten seeds with t-based 95% interval (a single value where one seed was run). '
          'Decision = prescribed release rule, shadow-model AUC at most 0.55, on the seed mean. The federated rows come from the pilot audit; the last section gives the federated-versus-central differences of every configuration from the federated runs themselves, including the plain configuration (no row or column sampling), which is deterministic (seeds give identical models; the interval collapses to the point) and under which the federated model reproduced the pooled model on the synthetic benchmark but not on the eICU hospitals at the default 256 histogram bins; the cause is the feature-quantile sketch merged from hospitals of different case mix (with 1,024 bins the models are identical, maximum prediction difference 1.2e-7; imputing missing values changes nothing; analysis/federated/out/diag_plain_identity.md).', '']
    for name, folder, tag in COHORTS:
        ut = pd.read_csv(os.path.join(L.OUT_ROOT, folder, '01_utility_long.csv'))
        at = pd.read_csv(os.path.join(L.OUT_ROOT, folder, '03_attacks_long.csv'))
        md += [f'## {name}', '']
        for variant in [v for v in VARIANT_LABEL if v in set(ut.variant)]:
            md += [f'### {VARIANT_LABEL[variant]} configuration (`{variant}`)', '',
                   '| route | n train | AUROC | shadow-model AUC | LiRA AUC | LiRA TPR@1%FPR | decision |', '|---|---|---|---|---|---|---|']
            for t in ROUTE_LABEL:
                u = ut[(ut.variant == variant) & (ut.target == t)]
                a = at[(at.variant == variant) & (at.target == t)]
                if u.empty and a.empty:
                    continue
                ntr = L.cell(int(u.n_train.iloc[0])) if not u.empty else (L.cell(int(a.n_members.iloc[0])) if not a.empty else '')
                dec = '' if a.empty else ('PASS' if a.shadow_auc.mean() <= L.GATE2_THRESHOLD else 'BLOCK')
                md.append(f'| {ROUTE_LABEL[t]} | {ntr} | {ci_text(u.auroc)} | {ci_text(a.shadow_auc) if not a.empty else ""} | '
                          f'{ci_text(a.lira_auc) if not a.empty else ""} | {ci_text(a.lira_tpr1) if not a.empty else ""} | {dec} |')
            md.append('')
    md += ['## Federated minus central, all configurations (federated runs)', '',
           '| cohort | scenario | configuration | seeds | A central | F federated | site models (min to max) | B_avg | F − A | F − B_avg |', '|---|---|---|---|---|---|---|---|---|---|']
    for name, folder, tag in COHORTS:
        fl = fl_seed_means(tag)
        if fl.empty:
            continue
        for (scn, cfg), g in fl.groupby(['scenario', 'config']):
            md.append(f'| {name} | {scn} | {VARIANT_LABEL.get("xgb_" + cfg, cfg)} | {len(g)} | {g.A.mean():.4f} | {g.F.mean():.4f} | {g.B_min.mean():.4f} to {g.B_max.mean():.4f} | {g.B_avg.mean():.4f} | '
                      f'{ci_text(g.F - g.A, 4)} | {ci_text(g.F - g.B_avg, 4)} |')
    with open(os.path.join(out, 'additional_file_5_configurations.md'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(md) + '\n')
    print('wrote', os.path.join(out, 'additional_file_5_configurations.md'))


def additional_file_1(out):
    """Policy audit of six platforms: codebook, reconciled matrix with coder confidence, reliability (round 1, frozen)."""
    w = pd.read_csv(os.path.join(L.BASE, 'analysis', 'policy_audit', 'workbook_v1_frozen.csv'))
    md = ['# Additional file 1. Policy audit of six research data platforms (coding round 1, frozen)', '',
          'Published export and output-checking rules of six platforms were coded by two coders working independently from the primary documents: '
          'the author (first coder) and Jiyeon Kim, RN (second coder, not an author), each assigning one category per platform-by-dimension cell '
          '(6 platforms × 5 dimensions = 30 cells) from a closed list, blind to the other\'s coding. A language model was used only to locate and excerpt '
          'passages; categories were assigned by the coders. Disagreements were resolved by reading the source text together; the reconciled coding is the '
          'one in the manuscript. Documents were retrieved between June and August 2026; five documents carry update dates after May 2026. '
          'The frozen workbook (`analysis/policy_audit/workbook_v1_frozen.csv`) and the reliability script (`check_v1.py`) are in the repository. '
          'A second round with a revised codebook and ten platforms is in preparation (`analysis/policy_audit/round2/codebook_v2.md`).', '',
          '## Codebook (round 1)', '',
          '| dimension | definition | categories | decision rule |', '|---|---|---|---|',
          '| D1 permitted export artifacts | output types a researcher may take out | aggregate statistics, tables, figures only; + de-identified result files; + conditional model release; finished algorithm only | the most permissive tier the policy explicitly allows; models only where explicitly stated |',
          '| D2 trained model as export category | whether a trained model is named as an export and on what basis | not addressed; conditional, leakage basis; algorithm-out (platform-internal); format or reproducibility basis | "addressed" only where a model or algorithm is explicitly named in an export context |',
          '| D3 review mode | principal mechanism by which egress is checked | automated egress alerts; human output-checking committee; platform-controlled build and validate; statistical disclosure control rules | the single principal mechanism named |',
          '| D4 environment persistence | whether the environment persists or is decommissioned | persists; time-limited or decommissioned; workspace persists (with credits) | from explicit statements on environment or credit lifetime |',
          '| D5 cost basis | the basis of charging, not a price | access fee or credits; subscription or seat; partnership or contract; free; not stated | the charging basis the published policy states; "not stated" rather than inferred |', '',
          'Document rule: official documentation and official support-centre pages count as policy; blogs corroborate only; the authors\' contractual or operational knowledge is not evidence; documents under non-disclosure agreement are excluded.', '',
          '## Reconciled matrix with the two codings', '',
          '| platform | dimension | first coder | second coder | reconciled | confidence (second coder) | source |', '|---|---|---|---|---|---|---|']
    kr = [('단락', ' paragraph'), ('말문', ' last sentence'), ('문', ' sentence'), ('탐색 범위', 'searched'), ('확인', 'checked'), ('분석 가이드', 'analysis guide'),
          ('분야 안내', 'field guide'), ('이용', 'use'), ('절', ' section'), ('항', ' item'), ('호', ' subitem'), ('표', ' table'), ('쪽', ' p.')]
    conf = {'h': 'high', 'm': 'medium', 'u': 'uncertain', 'med': 'medium', 'high': 'high', 'low': 'low'}
    for _, r in w.iterrows():
        src = str(r.get('source', '')).replace('|', '/')
        for a, b in kr:
            src = src.replace(a, b)
        src = ''.join(ch if ord(ch) < 0xAC00 or ord(ch) > 0xD7A3 else '' for ch in src)   # drop any remaining Hangul (location notes)
        src = ' '.join(src.split())
        c = conf.get(str(r.confidence).strip().lower(), str(r.confidence))
        md.append(f'| {r.platform} | {r.dimension} | {r.coder_HY} | {r.coder_JL} | {r.reconciled_Table1} | {c} | {src} |')
    md += ['', '## Inter-coder reliability', '',
           '| scope | Cohen\'s κ | 95% CI | cells |', '|---|---|---|---|',
           '| overall (complete pairs) | 0.774 | 0.606 to 0.922 | 29 |', '| D1 | 0.111 | not estimable | 6 |', '| D2 | 1.000 | not estimable | 6 |',
           '| D3 | 1.000 | not estimable | 6 |', '| D4 | 0.333 | not estimable | 6 |', '| D5 | 1.000 | not estimable | 5 |', '',
           'Agreement was 23 of 29 codable cells; the CODA cost cell was left blank by the second coder (the published documents state no fee basis) and is excluded. '
           'All six disagreements were resolved to the second coder\'s category after reading the source text; the second coder rated 8 of 30 cells "uncertain". '
           'The low values of D1 and D4 reflect ambiguity of the round-1 codebook (tiering of permitted outputs; credit-conditional persistence), which the round-2 codebook separates.']
    with open(os.path.join(out, 'additional_file_1_policy_audit.md'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(md) + '\n')
    print('wrote', os.path.join(out, 'additional_file_1_policy_audit.md'))


def additional_file_3(out):
    """Node isolation check (production-mode FLARE on the public benchmark)."""
    p = os.path.join(L.BASE, 'analysis', 'federated', 'out', 't0', 't0_check.json')
    d = json.load(open(p, encoding='utf-8'))
    md = ['# Additional file 3. Node isolation check (NVIDIA FLARE production mode, public benchmark)', '',
          f'Job: {d["dataset"]}, scenario {d["scenario"]}, seed {d["seed"]}, configuration {d["config"]} (100 rounds). Provisioned startup kits with mutual TLS; '
          'one aggregation container and three site containers; each site on its own Docker network with read-only access to its own folder; '
          'checks run from inside the containers (`analysis/federated/t0/t0.py`).', '',
          '| check | result |', '|---|---|',
          f'| aggregation container: mounted data folders | {", ".join(d["server_mounts"])} (no site data; data files visible: {d["server_data_files"]}) |',
          f'| aggregation container: IP forwarding | {d["server_ip_forward"]} (off) |',
          f'| aggregation container: networks | {", ".join(d["server_networks"])} |']
    for k in (1, 2, 3):
        nxt = {1: 2, 2: 3, 3: 1}[k]
        md.append(f'| site {k}: data folders and files | {", ".join(d[f"site{k}_data_dirs"])}: {", ".join(d[f"site{k}_data_files"])} |')
        md.append(f'| site {k}: network | {", ".join(d[f"site{k}_networks"])}; reaches the server: {d[f"site{k}_reaches_server"]} |')
        md.append(f'| site {k} to site {nxt} | by name: {d[f"site{k}_to_site{nxt}_by_name"]}; by IP: {d[f"site{k}_to_site{nxt}_by_ip"]} |')
        md.append(f'| site {k} to the Internet | {d[f"site{k}_to_internet"]} |')
    md += [f'| bytes received / sent per container | ' + '; '.join(f'{k}: {v}' for k, v in d['net_io_received_sent'].items()) + ' |',
           f'| isolation | {"passed" if d["isolation_ok"] else "failed"} |',
           f'| global model files written by the sites | {d["model_files"]}; byte-identical: {"yes" if d["site_models_identical_bytes"] else "no"} |',
           f'| validation AUROC, production mode / simulator | {d["t0_val_auroc"]:.4f} / {d["simulator_val_auroc"]:.4f}; maximum prediction difference {d["max_abs_pred_diff_vs_simulator"]:.1e} |', '',
           'ENETUNREACH = the kernel reported the destination network unreachable; "unresolved" = the container name did not resolve. '
           'Each site exchanged about 48 MB for 100 rounds; the aggregation container about 145 MB in each direction.']
    with open(os.path.join(out, 'additional_file_3_node_isolation.md'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(md) + '\n')
    print('wrote', os.path.join(out, 'additional_file_3_node_isolation.md'))


PREDICTORS = [
    ('Age', 'years at index', 'person'), ('Sex_Male', '1 = male', 'person'),
    ('Creatinine', 'serum creatinine, mg/dL (nearest to index)', 'laboratory'), ('BUN', 'blood urea nitrogen', 'laboratory'), ('Uric_Acid', 'uric acid', 'laboratory'),
    ('Sodium', 'sodium', 'laboratory'), ('Potassium', 'potassium', 'laboratory'), ('Calcium', 'calcium', 'laboratory'), ('Phosphorus', 'phosphorus', 'laboratory'),
    ('Bicarbonate', 'bicarbonate (total CO2)', 'laboratory'), ('Albumin', 'serum albumin', 'laboratory'), ('Total_Protein', 'total protein', 'laboratory'),
    ('Total_Bilirubin', 'total bilirubin', 'laboratory'), ('AST', 'aspartate aminotransferase', 'laboratory'), ('ALT', 'alanine aminotransferase', 'laboratory'),
    ('GGT', 'gamma-glutamyl transferase', 'laboratory'), ('Hb', 'haemoglobin', 'laboratory'), ('HbA1c', 'glycated haemoglobin', 'laboratory'),
    ('Glucose', 'glucose', 'laboratory'), ('HDL', 'HDL cholesterol', 'laboratory'), ('TG', 'triglycerides', 'laboratory'), ('Cholesterol', 'total cholesterol', 'laboratory'),
    ('UACR', 'urine albumin-to-creatinine ratio (measured or derived)', 'laboratory'), ('Urine_Microalbumin', 'urine microalbumin', 'laboratory'),
    ('Urine_Creatinine', 'urine creatinine', 'laboratory'), ('Baseline_eGFR', 'CKD-EPI 2021 from the index creatinine', 'derived'),
    ('eGFR_Slope', 'change of eGFR per year between the index creatinine and the latest creatinine at least 90 days earlier', 'derived'),
    ('History_HTN', 'hypertension on or before index', 'condition'), ('History_DM', 'diabetes on or before index', 'condition'),
    ('Subgroup_DKD', 'diabetic kidney disease', 'condition'), ('Subgroup_GN', 'glomerulonephritis', 'condition'),
    ('BMI', 'body mass index (absent in the extract: 100% missing)', 'measurement'),
    ('Dur_ACE_ARB_days', 'days of renin-angiotensin system inhibitor exposure in the 365 days before index', 'drug'),
    ('Dur_Statin_days', 'days of statin exposure in the 365 days before index', 'drug'),
    ('Drug_RAASi', 'any renin-angiotensin system inhibitor before index', 'drug'), ('Drug_Statins', 'any statin before index', 'drug'),
]


def additional_file_4(out):
    """Predictor list and the three predictors with tie-handling differences against the published pipeline."""
    rep = os.path.join(L.BASE, 'analysis', 'snuh_cdm', 'out', 'p4_site_features_visit.txt')
    miss = {}
    if os.path.exists(rep):
        inside = False
        for ln in open(rep, encoding='utf-8'):
            if ln.startswith('## missing per feature'):
                inside = True
                continue
            if inside and ln.startswith('## '):
                break
            parts = ln.split()
            if inside and len(parts) >= 7 and parts[1].endswith('%'):
                miss[parts[0]] = parts[1:7]
    md = ['# Additional file 4. Predictors of the CKD progression model on the CDM', '',
          'The 36 predictors of the published model [reference 18 of the main text], computed at the index date (first visit) inside each site file from the OMOP CDM tables '
          '(laboratory values: nearest measurement on or before the index, LOINC-mapped; conditions: SNOMED-mapped condition occurrences on or before the index; '
          'drug exposures: RxNorm ingredients grouped by ATC class). Missing values are left missing (XGBoost handles them). Missing shares are those of the '
          'six virtual-hospital files (B1 × 3, B2 × 3), from `analysis/snuh_cdm/out/p4_site_features_visit.txt`.', '',
          '| predictor | definition | source | missing share, six site files |', '|---|---|---|---|']
    for name, definition, src in PREDICTORS:
        m = miss.get(name)
        md.append(f'| {name} | {definition} | {src} | {" / ".join(m) if m else ""} |')
    md += ['', '## The three predictors that differ from the published pipeline at the same index date', '',
           '| predictor | exact agreement | reason |', '|---|---|---|',
           '| UACR | 51.0% | ties on the nearest day between a measured ratio and one derived from urine albumin and creatinine: the published code takes the first row in file order, the CDM code the lower value |',
           '| Bicarbonate | 64.7% | ties on the nearest day between a serum and a point-of-care value, same rule difference |',
           '| Cholesterol | 76.1% | the published substring rule counts LDL-cholesterol as total cholesterol; the CDM mapping does not |', '',
           'All other predictors agree exactly for 96.3% to 100% of the patients present in both cohorts (27,226 of the 28,209 published patients). '
           'The 983 published patients missing from the CDM cohort were removed by the renal replacement therapy and impossible-value exclusions, which the published pipeline did not apply.']
    with open(os.path.join(out, 'additional_file_4_predictors.md'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(md) + '\n')
    print('wrote', os.path.join(out, 'additional_file_4_predictors.md'))


def _section(path, start, stop='## '):
    """Lines of a markdown file from the heading that starts with `start` to the next heading."""
    out, inside = [], False
    for ln in open(path, encoding='utf-8'):
        if ln.startswith(start):
            inside = True
            continue
        if inside and ln.startswith(stop):
            break
        if inside:
            out.append(ln.rstrip('\n'))
    return out


def additional_file_6(out):
    """Canary benchmark: hyper-parameter grid, sensitivity to the exposure definition, synthetic-canary results."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import canary_benchmark as CB
    y = np.array([0, 1])
    named = {k: v for k, v in CB.configs(y, 42).items() if not k.startswith('lhs')}
    md = ['# Additional file 6. Canary benchmark: settings, sensitivity analyses and synthetic canaries', '',
          'Each training setting is an XGBoost hyper-parameter set trained at three sizes (2,000 and 6,000 rows and the largest size the cohort allows). '
          'Each setting-by-size cell holds 48 models, each trained on a random half of 400 label-flipped rows (canaries) added to its training rows, so that '
          'the membership of every canary is known; a leave-one-model-out likelihood-ratio attack on the canaries gives the ground-truth exposure, and the '
          'audit quantities are computed on ordinary rows as an auditor would. The pool of 47 settings is 7 named settings and 40 space-filling settings drawn '
          'by Latin hypercube over depth 2 to 12, 50 to 1,000 rounds, learning rate 0.03 to 0.3, minimum child weight {0, 1, 2, 5, 10, 20, 50}, L2 penalty '
          '{0, 1, 5, 10, 30}, row and column sampling 0.5 to 1.0 (`canary_benchmark.py`, seed 7).', '',
          '## Named settings', '', '| setting | rounds | depth | learning rate | min child weight | L2 | row sampling | column sampling |', '|---|---|---|---|---|---|---|---|']
    for k, v in named.items():
        md.append(f'| {k} | {v["n_estimators"]} | {v["max_depth"]} | {v["learning_rate"]} | {v.get("min_child_weight", 1)} | {v.get("reg_lambda", 1)} | {v["subsample"]} | {v["colsample_bytree"]} |')
    md += ['', 'krcp = the published configuration, leaky = the over-fitted positive control, regularized = the regularized configuration of the main text; the other four span the space between them.', '']
    for name, folder in [('SynPUF (development)', 'synpuf_xgb_canary'), ('MIMIC-IV-ED', 'mimic_ed_s28k_xgb_canary'), ('eICU-CRD, random sample', 'eicu_s28k_xgb_canary'),
                         ('eICU-CRD, 3 largest hospitals', 'eicu_h3a_xgb_canary'), ('eICU-CRD, hospitals of unequal size', 'eicu_h3b_xgb_canary')]:
        p = os.path.join(L.OUT_ROOT, folder, 'canary_summary.md')
        if not os.path.exists(p):
            continue
        md += [f'## Sensitivity to the exposure definition: {name}', '']
        sec = _section(p, '## 1.')
        md += [ln for ln in sec if ln.strip()]
        md += ['']
        sec = _section(p, '## 2.')
        md += [ln for ln in sec if ln.strip()]
        md += ['']
    for title, fname in [('Synthetic canaries: cross-cohort tables', 'canary_cross_cohort_shuffle.md'), ('Flipped-label against synthetic canaries, cell by cell', 'canary_cross_cohort_types.md')]:
        p = os.path.join(L.OUT_ROOT, fname)
        if os.path.exists(p):
            body = [ln.rstrip('\n') for ln in open(p, encoding='utf-8')]
            body = [('#' + ln) if ln.startswith('#') else ln for ln in body[1:]]
            md += [f'## {title}', ''] + body + ['']
    with open(os.path.join(out, 'additional_file_6_canary_benchmark.md'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(md) + '\n')
    print('wrote', os.path.join(out, 'additional_file_6_canary_benchmark.md'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(L.BASE, 'Manuscript', 'v2', 'BMC_MIDM'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    additional_file_1(a.out)
    additional_file_2(a.out)
    additional_file_3(a.out)
    additional_file_4(a.out)
    additional_file_5(a.out)
    additional_file_6(a.out)


if __name__ == '__main__':
    main()
