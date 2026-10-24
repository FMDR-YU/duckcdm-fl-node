# -*- coding: utf-8 -*-
"""Candidate passages for the round-2 coders: for every document in sources_text/, the sentences that contain a keyword of a
dimension, with document id and sentence number, grouped by platform and dimension. The coders read these first and the full
text when needed; the script proposes no category (codebook_v2.md, document rules). Output: excerpts_v2.md.

    python make_excerpts.py
"""
import csv
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TXT = os.path.join(HERE, 'sources_text')
KEYS = {
    'D1 artefacts': r'\b(export|download|egress|take out|remove|output|result file|results? (?:files?|download)|aggregate|summary statistic|table|figure|row[- ]level|record[- ]level|code|script|algorithm)\b',
    'D2 trained models': r'\b(model|models|algorithm|weights|parameters|machine learning|ML|AI|artificial intelligence|trained)\b',
    'D3 review': r'\b(review|committee|output check|disclosure control|SDC|approv|alert|monitor|validat|qualif|airlock|checker)\w*',
    'D4 environment': r'\b(persist|retain|delete|decommission|expire|expiry|duration|months|years|credit|wallet|close|terminat|archiv)\w*',
    'D5 cost': r'\b(fee|fees|cost|credit|credits|charge|price|pricing|free of charge|free|partnership|contract|subscription)\b',
}


def sentences(text):
    text = re.sub(r'\s+', ' ', text)
    return [s.strip() for s in re.split(r'(?<=[.!?。])\s+(?=[A-Z0-9"(\[가-힣])', text) if len(s.strip()) > 20]


def main():
    reg = list(csv.DictReader(io.open(os.path.join(HERE, 'source_register_v2.csv'), encoding='utf-8', newline='')))
    by_platform = {}
    for r in reg:
        by_platform.setdefault(r['platform_id'], []).append(r)
    md = ['# Round 2 excerpt workbook (candidate passages, no categories)', '',
          'Two parts. Part A: the verbatim excerpts of coding round 1 (six platforms; first coder accessed the documents on 2026-06-07, second coder '
          'in August 2026), carried over from the frozen round-1 workbook so that pages already read then stay usable even where a page has since '
          'changed or disappeared (All of Us "Policy Questions", removed by October 2026). Part B: candidate sentences from the copies fetched on '
          '2026-10-20 (all ten platforms). Each Part B line is one sentence that contains a keyword of the dimension; the coder reads the sentence in '
          'its document (sentence number) and the surrounding text before coding, and may cite any other passage. Keywords only locate text; '
          'they do not decide anything. Round-1 categories are not shown here.', '',
          '# Part A. Round-1 verbatim excerpts (accessed 2026-06-07 and August 2026)', '']
    import csv as _csv
    v1 = list(_csv.DictReader(io.open(os.path.join(HERE, '..', 'workbook_v1_frozen.csv'), encoding='utf-8', newline='')))
    for r in v1:
        ev = (r.get('evidence') or '').strip().replace('\n', ' ')
        src = (r.get('source') or '').strip().replace('\n', ' ')
        if ev:
            md.append(f'- **{r["platform"]} {r["dimension"]}** [{src}] {ev[:900]}')
    md += ['', '# Part B. Sentences from the 2026-10-20 copies', '']
    for pid in sorted(by_platform):
        md += [f'## {pid}', '']
        for r in by_platform[pid]:
            p = os.path.join(TXT, r['doc_id'] + '.txt')
            if not os.path.exists(p) or not r['status'].startswith('ok'):
                md += [f'### {r["doc_id"]} {r["title"]}', '', f'(no text copy: {r["status"]})', '']
                continue
            sents = sentences(open(p, encoding='utf-8').read())
            md += [f'### {r["doc_id"]} {r["title"]}', '', f'accessed {r["accessed"]}; date shown: {r["date_shown"]}; {len(sents)} sentences', '']
            for dim, pat in KEYS.items():
                hits = [(i + 1, s) for i, s in enumerate(sents) if re.search(pat, s, flags=re.I)]
                if not hits:
                    continue
                md += [f'**{dim}** ({len(hits)} sentences)', '']
                for i, s in hits[:60]:
                    md.append(f'- [{r["doc_id"]} s{i}] {s[:400]}')
                if len(hits) > 60:
                    md.append(f'- ... {len(hits) - 60} more in the document')
                md.append('')
    open(os.path.join(HERE, 'excerpts_v2.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')
    print('wrote excerpts_v2.md')


if __name__ == '__main__':
    main()
