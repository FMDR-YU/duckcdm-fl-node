#!/usr/bin/env python3
"""Convert manuscript.md / supplement -> .docx with journal-style formatting:
Times New Roman 11 pt, black & white, double line spacing, continuous line
numbering, centred page numbers, no page breaks (--- dividers stripped),
tables single-spaced 10 pt with no shading."""
import os
import re
import shutil
import tempfile
import pypandoc
from docx import Document
from docx.shared import Pt, RGBColor, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGDIR = os.path.join(BASE, "Figures")
BODY_FONT = "Times New Roman"
BODY_PT = 12
TABLE_PT = 9
BLACK = RGBColor(0, 0, 0)


def pandoc_convert(src, out, embed_figs=False):
    md = open(src, encoding="utf-8").read()
    md = re.sub(r"<!--.*?-->", "", md, flags=re.DOTALL)
    md = re.sub(r"(?m)^-{3,}\s*$", "", md)
    if embed_figs:
        for n in (1, 2, 3):
            p = os.path.join(FIGDIR, f"Fig{n}.png").replace("\\", "/")
            md = md.replace(f"**Fig {n}. ",
                            f"![Figure {n}]({p}){{width=6in}}\n\n**Fig {n}. ", 1)
    # pypandoc globs the source path internally, so a directory name containing
    # "[...]" (a glob character class) makes it resolve to nothing. Stage the
    # intermediate markdown in a bracket-free temp dir.
    tmpdir = tempfile.mkdtemp(prefix="md2docx_")
    tmp = os.path.join(tmpdir, "input.md")
    open(tmp, "w", encoding="utf-8").write(md)
    pypandoc.convert_file(
        tmp, "docx", outputfile=out,
        extra_args=["--from=markdown+pipe_tables+tex_math_dollars", "--standalone",
                    f"--resource-path={FIGDIR}"])
    shutil.rmtree(tmpdir, ignore_errors=True)


def _set_rfonts(rpr):
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs"):
        rfonts.set(qn(a), BODY_FONT)


def set_run(run, size, bold=None, italic=None):
    _set_rfonts(run._element.get_or_add_rPr())
    run.font.name = BODY_FONT
    run.font.size = Pt(size)
    run.font.color.rgb = BLACK
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic


def clear_shading(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    for shd in tcPr.findall(qn("w:shd")):
        tcPr.remove(shd)


def add_line_numbers(section):
    sectPr = section._sectPr
    ln = sectPr.find(qn("w:lnNumType"))
    if ln is None:
        ln = OxmlElement("w:lnNumType")
        sectPr.append(ln)
    ln.set(qn("w:countBy"), "1")
    ln.set(qn("w:restart"), "continuous")
    ln.set(qn("w:distance"), "360")


def add_page_number(section):
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    run = p.add_run()
    for typ, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        if typ:
            fld = OxmlElement("w:fldChar"); fld.set(qn("w:fldCharType"), typ)
            run._r.append(fld)
        else:
            it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve")
            it.text = txt; run._r.append(it)
    set_run(run, BODY_PT)


def format_doc(path):
    doc = Document(path)
    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(BODY_PT)
    normal.font.color.rgb = BLACK
    normal.paragraph_format.line_spacing = 2.0
    _set_rfonts(normal.element.get_or_add_rPr())

    for p in doc.paragraphs:
        sn = (p.style.name or "").lower()
        heading = sn.startswith("heading") or sn.startswith("title")
        p.paragraph_format.line_spacing = 2.0
        for run in p.runs:
            set_run(run, BODY_PT, bold=True if heading else None)

    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                clear_shading(cell)
                for p in cell.paragraphs:
                    p.paragraph_format.line_spacing = 1.0
                    for run in p.runs:
                        set_run(run, TABLE_PT)

    for section in doc.sections:
        # HIR: "double spaced on 21.6 x 27.9 cm (letter size) or 21.0 x 29.7 cm
        # (A4) paper with margins of 1 inch". Pandoc leaves these unset, so the
        # result would depend on whoever opens the file.
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        for side in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
            setattr(section, side, Inches(1))
        add_line_numbers(section)
        add_page_number(section)

    doc.save(path)


def convert(src, out, embed_figs=False):
    pandoc_convert(src, out, embed_figs=embed_figs)
    format_doc(out)
    return out


# --- HIR single-file assembly -----------------------------------------------
# Healthcare Informatics Research, Instructions for Authors (2025-01-01):
#   "The manuscript should be prepared in the following sequence: cover letter,
#    title page ..., abstract and keywords, main text, acknowledgments,
#    references, tables, figure legends, followed by figures. Cover letter,
#    title page, and figures should be on separate files."
#   "All manuscript pages are to be numbered consecutively, beginning with the
#    abstract as page 1. Neither the author's names nor their affiliations
#    should appear on the manuscript pages."
#   "Each table should be prepared on a separate page ... Vertical lines are
#    not used."
# Review is double-blinded, so identifying text is redacted from this file and
# carried on the separate title page.

ROMAN = ["I", "II", "III", "IV", "V", "VI"]

REDACTIONS = [
    ("https://github.com/FMDR-YU/safe-model-bundle",
     "[repository URL withheld for blinded review; given on the title page]"),
]


def _split_sections(md):
    """Return an ordered list of (name, body) for level-2 sections."""
    out, name, buf = [], None, []
    for line in md.split("\n"):
        if line.startswith("## "):
            if name is not None:
                out.append((name, "\n".join(buf).strip("\n")))
            name, buf = line[3:].strip(), []
        elif name is not None:
            buf.append(line)
    out.append((name, "\n".join(buf).strip("\n")))
    return out


def _pull_tables(text):
    """Lift '**Table N. ...**' captions plus their pipe tables out of a section."""
    lines, kept, tables, i = text.split("\n"), [], [], 0
    while i < len(lines):
        if lines[i].startswith("**Table ") and "." in lines[i]:
            block = [lines[i]]
            i += 1
            while i < len(lines) and (lines[i].strip() == "" or lines[i].startswith("|")):
                block.append(lines[i])
                i += 1
            tables.append("\n".join(block).strip("\n"))
        else:
            kept.append(lines[i])
            i += 1
    return "\n".join(kept), tables


def _number_headings(body, roman):
    """I. Section / 1. Subsection, per the HIR subheading scheme."""
    out, n = [], 0
    for line in body.split("\n"):
        if line.startswith("### "):
            n += 1
            out.append("### %d. %s" % (n, line[4:].strip()))
        else:
            out.append(line)
    return "\n".join(out)


def build_hir(src, main_md, title_md):
    md = open(src, encoding="utf-8").read()
    sec = dict(_split_sections(md))

    tables = []
    body = []
    for i, name in enumerate(["Introduction", "Methods", "Results", "Discussion"]):
        text, found = _pull_tables(sec[name])
        tables += found
        body.append("## %s. %s\n\n%s" % (ROMAN[i], name, _number_headings(text, ROMAN[i])))

    # Acknowledgements, funding and the AI note travel together (HIR p.3);
    # the personal acknowledgement identifies an affiliation, so it is withheld.
    decl = sec["Declarations"]

    def field(label):
        m = [l for l in decl.split("\n") if l.startswith("**%s" % label)]
        return m[0] if m else ""

    ack = ("## Acknowledgments\n\n"
           "Personal acknowledgements are withheld for blinded review and are given on the "
           "title page.\n\n"
           + field("Funding") + "\n\n"
           + field("Use of generative artificial intelligence") + "\n\n"
           + field("Ethics approval") + "\n\n"
           + field("Competing interests") + "\n\n"
           + field("Data availability"))

    main = "\n\n".join(
        ["## Abstract\n\n" + sec["Abstract"]]
        + body
        + [ack,
           "## References\n\n" + sec["References"],
           "## Tables\n\n" + "\n\n".join(tables),
           "## Figure legends\n\n" + sec["Figure legends"],
           "## Supporting information\n\n" + sec["Supporting information"]])

    for old, new in REDACTIONS:
        main = main.replace(old, new)
    open(main_md, "w", encoding="utf-8", newline="\n").write(main + "\n")

    # HIR wants the AI notice in Methods (with name, version, model, source)
    # and in Acknowledgments. The title page does not need a third copy.
    tp_decl = "\n\n".join(
        b for b in decl.split("\n\n")
        if not b.startswith("**Use of generative artificial intelligence"))

    open(title_md, "w", encoding="utf-8", newline="\n").write(
        "## Title page\n\n" + sec["Title page"].strip()
        + "\n\n## Declarations\n\n" + tp_decl.strip() + "\n")
    return main_md, title_md


def hir_table_rules(path):
    """Horizontal rules only, and start each table in the Tables section anew."""
    doc = Document(path)
    for t in doc.tables:
        tblPr = t._tbl.tblPr
        for old in tblPr.findall(qn("w:tblBorders")):
            tblPr.remove(old)
        b = OxmlElement("w:tblBorders")
        for edge, val in (("top", "single"), ("bottom", "single"),
                          ("left", "none"), ("right", "none"),
                          ("insideH", "single"), ("insideV", "none")):
            e = OxmlElement("w:%s" % edge)
            e.set(qn("w:val"), val)
            e.set(qn("w:sz"), "4")
            e.set(qn("w:color"), "000000")
            b.append(e)
        tblPr.append(b)

    in_tables = False
    for p in doc.paragraphs:
        txt = p.text.strip()
        if txt == "Tables":
            in_tables = True
            p.paragraph_format.page_break_before = True
            continue
        if txt in ("Figure legends", "Supporting information"):
            in_tables = False
            p.paragraph_format.page_break_before = True
        if in_tables and re.match(r"^Table \d+\.", txt):
            p.paragraph_format.page_break_before = True
    doc.save(path)


def convert(src, out, embed_figs=False):
    pandoc_convert(src, out, embed_figs=embed_figs)
    format_doc(out)
    return out


SUBMISSION_README = """# Submission set — Healthcare Informatics Research

Regenerate with `python tools/md2docx.py` (no arguments). Do not edit these; edit
`Manuscript/v2/BMC_MIDM/*.md` (the old v1 set is under `Archive/manuscript_v1_egress/`) and rebuild.

Upload in this order:

| # | File | Editorial Manager item |
|---|---|---|
| 1 | 1_Manuscript.docx | Manuscript (the single file; blinded, abstract is page 1) |
| 2 | 2_Title_page.docx | Title page (not sent to reviewers) |
| 3 | 3_Cover_letter.docx | Cover letter |
| 4 | 4_S1_File.docx | Supplementary material |
| 5 | 5_Figure_1.tif … 7_Figure_3.tif | Figures, one file each |

1_Manuscript.docx and 4_S1_File.docx carry no author, affiliation or
repository identifiers; review is double-blinded.

`build/manuscript_authorcopy.docx` is the unblinded read-through copy. It is
not part of the submission.
"""


def build_all():
    ms = os.path.join(BASE, "Manuscript")
    build = os.path.join(ms, "build")
    sub = os.path.join(ms, "Submission")
    for d in (build, sub):
        os.makedirs(d, exist_ok=True)

    src = os.path.join(ms, "manuscript.md")
    main_md = os.path.join(build, "manuscript_blinded.md")
    title_md = os.path.join(build, "title_page.md")
    build_hir(src, main_md, title_md)

    main_docx = convert(main_md, os.path.join(sub, "1_Manuscript.docx"))
    hir_table_rules(main_docx)
    outs = [main_docx,
            convert(title_md, os.path.join(sub, "2_Title_page.docx")),
            convert(os.path.join(ms, "cover_letter.md"),
                    os.path.join(sub, "3_Cover_letter.docx")),
            convert(os.path.join(BASE, "Supplement", "S1_File_supplement.md"),
                    os.path.join(sub, "4_S1_File.docx"))]

    for i, n in enumerate((1, 2, 3), start=5):
        src_tif = os.path.join(BASE, "Figures", "Fig%d.tif" % n)
        dst = os.path.join(sub, "%d_Figure_%d.tif" % (i, n))
        shutil.copyfile(src_tif, dst)
        outs.append(dst)

    open(os.path.join(sub, "README.md"), "w", encoding="utf-8",
         newline="\n").write(SUBMISSION_README)

    # unblinded read-through copy, kept out of the submission folder
    outs.append(convert(src, os.path.join(build, "manuscript_authorcopy.docx")))
    return outs


if __name__ == "__main__":
    import sys

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        for p in build_all():
            print("->", os.path.relpath(p, BASE))
        sys.exit(0)

    for src in args:
        if not os.path.exists(src):
            print("skip (missing):", src)
            continue
        print("->", convert(src, os.path.splitext(src)[0] + ".docx"))
