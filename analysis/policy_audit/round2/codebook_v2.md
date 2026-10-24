# Policy audit, coding round 2: codebook v2 (draft 2026-10-20, not yet used)

Purpose: recode the export rules of research data platforms with a codebook that separates (a) which artefact types may leave,
(b) the platform's position on trained models, the basis of any condition and the evidence it asks for, (c) who reviews what and
at which stage, (d) what happens to the environment at expiry, (e) the cost basis. Round 1 (v1, six platforms, 30 cells, two coders,
Cohen's κ 0.77) is frozen in `../workbook_v1_frozen.csv`; its two weak dimensions (D1 κ 0.11, D4 κ 0.33) are the reason for v2
(`docs/PLATFORM_EXPORT_MATRIX.md` section 6). Decision 2026-10-20 (user): scope A, ten platforms, second coder Jiyeon Kim, RN.

## Scope (10 platforms)

| # | platform | why |
|---|---|---|
| P01 | UK Biobank Research Analysis Platform | round 1; AI policy and the 2026 closure / phased reopening |
| P02 | All of Us Researcher Workbench | round 1; model rule on a support page |
| P03 | European Health Data Space secure processing environment (Reg. (EU) 2025/327) | round 1; regulation read as a platform rule |
| P04 | CODA (Korea, NIH) | round 1 |
| P05 | K-CURE (Korea) | round 1 |
| P06 | Mayo Clinic Platform | round 1; public documents only, no NDA material |
| P07 | Genomics England Research Environment (Airlock) | model export prohibited (explicit) |
| P08 | UK Longitudinal Linkage Collaboration (UK LLC) | model export prohibited (explicit) |
| P09 | Eastern England SDE | conditional by SOP (Zenodo record) |
| P10 | Findata (Finland) | case-by-case anonymity proof |

## Units

One cell = one platform × one dimension (or sub-dimension). Every cell carries: category (closed list), confidence (h / m / u),
document id(s) from the source register, verbatim excerpt (English or original language; translation beside it), and the
coder's note. Nothing is inferred: where the documents are silent the cell is `not stated`.

## Dimensions and closed lists

**D1. Artefact types that may leave the environment** (one cell per artefact type; status list for each)

| artefact type | status list |
|---|---|
| D1a aggregate statistics, tables, figures | permitted / conditional / prohibited / not stated |
| D1b de-identified or anonymised result files (row-level) | same |
| D1c trained models or fitted parameters | same |
| D1d algorithms and code written inside the environment | same |

Rule: code the most specific statement that applies to the type. "Conditional" needs a stated condition; a bare review step
without a stated condition is "permitted" with D3 recording the review.

**D2. Trained models**

| sub-dimension | list |
|---|---|
| D2a position | prohibited / conditional / platform builds and releases (algorithm-out) / case-by-case anonymity proof / not stated |
| D2b basis of the condition | leakage or re-identification / format or reproducibility / provenance of the training data (summary-level only) / platform validation / none stated / not applicable |
| D2c evidence the platform asks for | none / researcher's own judgement / provenance condition / platform-internal test / submission form or checklist / attack-test report / numeric criterion / not stated / not applicable |

D2c is the cell that the paper's argument rests on: whether any platform states a test, a form or a number.

**D3. Review**

| sub-dimension | list |
|---|---|
| D3a access stage | human committee or permit body / automated / none stated |
| D3b output stage | human output-checking committee / statistical disclosure control rules / automated egress alerts / platform-controlled build and validation / none stated |

**D4. Environment at expiry**

| sub-dimension | list |
|---|---|
| D4a default state when the permit, project or funding ends | deleted or decommissioned / persists / not stated |
| D4b stated upper limit of duration | months or years as written / none stated |

**D5. Cost basis**: access fee or credits / partnership or contract / free (stated) / not stated.

## Document rules (unchanged from v1 where they worked)

- Policy = official documents and official support-center pages. Blogs and community posts corroborate only. Authors' own
  contractual or operational knowledge is never evidence; NDA documents are excluded (Mayo).
- Each document is entered in the source register before coding: id, platform, title, URL, access date, date shown on the page,
  SHA-256 of the local copy (internal, not redistributed). Cells cite document ids.
- Coders work independently from the register and the excerpts, with the closed lists, and do not change a cell after submitting.
  A language model may locate passages and excerpt them; it does not propose categories, and its use is logged in `llm_log.md`.
- Disagreements are resolved by reading the source text together; the record says whose value was adopted and why; confidence is
  re-rated after resolution.
- Reporting: agreement and κ overall; per dimension the list of disagreements (cells are too few for a per-dimension interval).

## Files of this round

| file | content |
|---|---|
| `source_register_v2.csv` | one row per document (filled by the first coder before coding) |
| `coder_sheet_v2.csv` | one row per cell, blank; one copy per coder (`coder_sheet_v2_HY.csv`, `coder_sheet_v2_JK.csv`) |
| `excerpts_v2.md` | document id, location, verbatim excerpt (no categories) |
| `llm_log.md` | what the language model was used for, with dates |
| `reconciled_v2.csv` | final cells with confidence and resolution notes |
