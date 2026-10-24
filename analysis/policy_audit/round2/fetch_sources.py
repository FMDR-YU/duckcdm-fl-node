# -*- coding: utf-8 -*-
"""Round 2 source register: download each policy document once, keep the raw copy internally (sources/, git-ignored), record
access time, the date shown on the page, size and SHA-256, and write a plain-text rendering (sources_text/) for excerpting.
Help-centre pages (Zendesk) are read through their JSON API, which also returns the page's updated_at; EUR-Lex and Zenodo give
PDFs. Nothing here is executed; downloads are data.

    python fetch_sources.py            (writes source_register_v2.csv and sources_text/*.txt)
"""
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'sources')
TXT = os.path.join(HERE, 'sources_text')
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) policy-audit-round2/1.0'}

# doc_id, platform_id, title, url, kind ('zendesk_article', 'zendesk_post', 'html', 'pdf', 'zenodo')
DOCS = [
    ('S01', 'P01', 'UK Biobank: Use of Artificial Intelligence (AI) applications and models', 'https://community.ukbiobank.ac.uk/api/v2/help_center/en-gb/articles/21922841787293.json', 'zendesk_article'),
    ('S02', 'P01', 'UK Biobank: Guidance on Data Downloads and Exemptions', 'https://community.ukbiobank.ac.uk/api/v2/help_center/en-gb/articles/31972311370013.json', 'zendesk_article'),
    ('S03', 'P01', 'UK Biobank: Ongoing closure of the UKB-RAP (community post)', 'https://community.ukbiobank.ac.uk/api/v2/help_center/community/posts/36090225990173.json', 'zendesk_post'),
    ('S04', 'P01', 'UK Biobank: UKB-RAP phased data access from September (community post)', 'https://community.ukbiobank.ac.uk/api/v2/help_center/community/posts/37286700962717.json', 'zendesk_post'),
    ('S05', 'P02', 'All of Us: Policy Questions', 'https://support.researchallofus.org/api/v2/help_center/en-us/articles/34814131370388.json', 'zendesk_article'),
    ('S06', 'P02', 'All of Us: Frequently Asked Questions', 'https://support.researchallofus.org/api/v2/help_center/en-us/articles/52861503885460.json', 'zendesk_article'),
    ('S07', 'P02', 'All of Us: Data User Code of Conduct', 'https://support.researchallofus.org/api/v2/help_center/en-us/articles/22346176432532.json', 'zendesk_article'),
    ('S08', 'P02', 'All of Us: Egress Alert Policy', 'https://support.researchallofus.org/api/v2/help_center/en-us/articles/4407354684052.json', 'zendesk_article'),
    ('S09', 'P02', 'All of Us: Data and Statistics Dissemination Policy', 'https://support.researchallofus.org/api/v2/help_center/en-us/articles/22346276580372.json', 'zendesk_article'),
    ('S10', 'P03', 'Regulation (EU) 2025/327 (European Health Data Space), Official Journal PDF', 'https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202500327', 'pdf'),
    ('S11', 'P04', 'CODA: introduction', 'https://coda.nih.go.kr/usab/intro/intro.do', 'html'),
    ('S12', 'P04', 'CODA: dissemination procedure', 'https://coda.nih.go.kr/common/procss/selectLttotProcss.do', 'html'),
    ('S13', 'P04', 'CODA: analysis infrastructure', 'https://coda.nih.go.kr/usab/lodbr/intro.do', 'html'),
    ('S14', 'P05', 'K-CURE portal', 'https://k-cure.mohw.go.kr/', 'html'),
    ('S15', 'P06', 'Mayo Clinic Platform: Exploring a federated approach to data management', 'https://www.mayoclinicplatform.org/2023/09/14/exploring-a-federated-approach-to-data-management/', 'html'),
    ('S16', 'P06', 'Mayo Clinic Platform: Connect', 'https://www.mayoclinicplatform.org/mayo-clinic-platform-connect/', 'html'),
    ('S17', 'P07', 'Genomics England Research Environment: trained ML models (Airlock)', 'https://re-docs.genomicsengland.co.uk/airlock_ml/', 'html'),
    ('S18', 'P08', 'UK LLC guidebook: AI policy', 'https://guidebook.ukllc.ac.uk/docs/applying/applying/ai_policy.html', 'html'),
    ('S19', 'P09', 'Eastern England SDE: researcher model disclosure control SOP (Zenodo 19255119)', 'https://zenodo.org/api/records/19255119', 'zenodo'),
    ('S20', 'P10', 'Findata: producing anonymous results', 'https://findata.fi/en/services-and-instructions/producing-anonymous-results/', 'html'),
]


BROWSER = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36',
           'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-GB,en;q=0.9'}
ALT = {'S05': ['https://support.researchallofus.org/hc/en-us/articles/34814131370388-Policy-Questions',
               'https://support.researchallofus.org/api/v2/help_center/articles/34814131370388.json'],
       'S10': ['https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32025R0327', 'https://eur-lex.europa.eu/eli/reg/2025/327/oj/eng'],
       'S15': ['https://www.mayoclinicplatform.org/2023/09/14/exploring-a-federated-approach-to-data-management/'],
       'S16': ['https://www.mayoclinicplatform.org/mayo-clinic-platform-connect/']}


def get(url, timeout=60, headers=None):
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers or UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                if not body:
                    raise ValueError('empty body')
                return body, r.headers.get('Content-Type', '')
        except Exception as e:      # retry on incomplete reads and transient errors
            last = e
    raise last


def strip_html(b):
    s = b.decode('utf-8', errors='replace')
    s = re.sub(r'(?is)<(script|style|noscript).*?</\1>', ' ', s)
    s = re.sub(r'(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>|</tr>', '\n', s)
    s = re.sub(r'(?s)<[^>]+>', ' ', s)
    s = re.sub(r'&nbsp;', ' ', s)
    s = re.sub(r'&amp;', '&', s)
    s = re.sub(r'&lt;', '<', s)
    s = re.sub(r'&gt;', '>', s)
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n\s*\n+', '\n', s)
    return s.strip()


def pdf_text(path):
    try:
        import fitz
        doc = fitz.open(path)
        return '\n'.join(page.get_text() for page in doc)
    except Exception as e:
        return f'[pdf text extraction failed: {e}]'


DATE_PATTERNS = [r'(?i)(last (?:modified|updated)[^\n]{0,40}?\d{1,2}[./ ]\w+[./ ]\d{4})', r'(?i)(updated[^\n]{0,30}?\d{4}-\d{2}-\d{2})',
                 r'(?i)(updated[^\n]{0,30}?\d{1,2}\.\d{1,2}\.\d{4})', r'(?i)(published[^\n]{0,30}?\d{4}-\d{2}-\d{2})',
                 r'(?i)((?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4})']


def date_shown(text):
    for p in DATE_PATTERNS:
        m = re.search(p, text)
        if m:
            return m.group(1).strip()[:60]
    return ''


def main():
    os.makedirs(SRC, exist_ok=True)
    os.makedirs(TXT, exist_ok=True)
    rows = []
    for doc_id, pid, title, url, kind in DOCS:
        accessed = dt.datetime.now().strftime('%Y-%m-%d %H:%M')
        row = {'doc_id': doc_id, 'platform_id': pid, 'title': title, 'url': url, 'accessed': accessed, 'date_shown': '', 'sha256_local_copy': '',
               'bytes': '', 'status': '', 'note': ''}
        try:
            try:
                body, ctype = get(url)
            except Exception as first:
                body = None
                for alt in ALT.get(doc_id, []):
                    try:
                        body, ctype = get(alt, headers=BROWSER)
                        row['note'] = f'retrieved from {alt}'
                        if alt.endswith('.json'):
                            kind = 'zendesk_article'
                        elif kind == 'pdf' and 'PDF' not in alt:
                            kind = 'html'
                        break
                    except Exception:
                        continue
                if body is None:
                    raise first
            text, ext = '', 'html'
            if kind in ('zendesk_article', 'zendesk_post'):
                d = json.loads(body.decode('utf-8'))
                obj = d.get('article') or d.get('post') or {}
                row['date_shown'] = f"updated_at {obj.get('updated_at', '')}; created_at {obj.get('created_at', '')}"
                text = (obj.get('title', '') + '\n\n' + strip_html((obj.get('body') or obj.get('details') or '').encode('utf-8')))
                ext = 'json'
            elif kind == 'zenodo':
                d = json.loads(body.decode('utf-8'))
                row['date_shown'] = f"published {d.get('metadata', {}).get('publication_date', '')}; doi {d.get('doi', '')}"
                files = d.get('files', [])
                pdfs = [f for f in files if f.get('key', '').lower().endswith('.pdf')] or files
                if pdfs:
                    body, _ = get(pdfs[0]['links']['self'], timeout=120)
                    ext = 'pdf'
                    p = os.path.join(SRC, f'{doc_id}.pdf')
                    open(p, 'wb').write(body)
                    text = pdf_text(p)
                    row['note'] = f"file {pdfs[0].get('key')}"
            elif kind == 'pdf':
                ext = 'pdf'
                p = os.path.join(SRC, f'{doc_id}.pdf')
                open(p, 'wb').write(body)
                text = pdf_text(p)
            else:
                text = strip_html(body)
            if ext != 'pdf':
                open(os.path.join(SRC, f'{doc_id}.{ext}'), 'wb').write(body)
            if not row['date_shown']:
                row['date_shown'] = date_shown(text)
            open(os.path.join(TXT, f'{doc_id}.txt'), 'w', encoding='utf-8', newline='\n').write(text)
            row['sha256_local_copy'] = hashlib.sha256(body).hexdigest()
            row['bytes'] = len(body)
            row['status'] = 'ok'
            print(f'{doc_id} ok {len(body):>9,} B  {row["date_shown"][:50]}  {title[:60]}')
        except Exception as e:
            row['status'] = f'failed: {type(e).__name__}: {str(e)[:80]}'
            print(f'{doc_id} FAILED {title[:60]}: {row["status"]}')
        rows.append(row)
    with io.open(os.path.join(HERE, 'source_register_v2.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print('wrote source_register_v2.csv')


if __name__ == '__main__':
    main()
