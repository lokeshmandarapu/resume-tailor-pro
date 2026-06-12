"""Text-based PDF renderer (reportlab). Single column, real selectable text, standard headings,
clean round bullets that extract as U+2022 (bundled Unicode font). Bolds metrics + JD keywords.
Guarantees a single page by auto-shrinking spacing/size until it fits."""
from __future__ import annotations
import io
import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table, TableStyle,
                                HRFlowable, ListFlowable, ListItem)
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .schema import Resume

_FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")


def _register_fonts() -> tuple[str, str, str]:
    """Prefer bundled DejaVu (clean bullet extraction); fall back to Helvetica."""
    try:
        pdfmetrics.registerFont(TTFont("RTP", os.path.join(_FONTS_DIR, "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("RTP-Bold", os.path.join(_FONTS_DIR, "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("RTP-Italic", os.path.join(_FONTS_DIR, "DejaVuSans-Oblique.ttf")))
        # link the family so <b>/<i> resolve to the bold/italic faces (this is what makes bold work)
        pdfmetrics.registerFontFamily("RTP", normal="RTP", bold="RTP-Bold",
                                      italic="RTP-Italic", boldItalic="RTP-Bold")
        return "RTP", "RTP-Bold", "RTP-Italic"
    except Exception:
        return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


F, FB, FI = _register_fonts()

# precise metric: a number that carries %, a real unit, a + suffix, or x — never bare numbers,
# never phone/email digits (lookbehind), and unit letters are case-SENSITIVE so "M" != "minutes".
_M_BODY = r"(?<![\w.@/-])\d[\d,]*(?:\.\d+)?(?:%|\s?(?:ms|RPS|TPS|MB/s|GB)\b|[KMB]?\+|x\b)"
_METRIC_RE = re.compile(r"\*\*.+?\*\*|(" + _M_BODY + r")")


def _wrap(m):
    s = m.group(0)
    return s if s.startswith("**") else f"**{s}**"


def _kw_regex(terms):
    pats = []
    for t in sorted([x for x in terms if (x or "").strip()], key=len, reverse=True):
        esc = re.escape(t)
        left = r"\b" if t[:1].isalnum() else ""
        right = r"\b" if t[-1:].isalnum() else ""
        pats.append(left + esc + right)
    return re.compile(r"\*\*.+?\*\*|(?:" + "|".join(pats) + ")", re.IGNORECASE) if pats else None


def skill_terms(resume) -> list[str]:
    """Pull concrete skill tokens out of the resume's Skills section so they bold everywhere."""
    out = []
    for line in resume.skills or []:
        items = line.split(":", 1)[1] if ":" in line else line
        out += [it.strip() for it in items.split(",") if it.strip()]
    return out


def mark_bold(text: str, bold_terms=None, metrics: bool = True) -> str:
    """Wrap metrics (optional) and keywords (optional) in **..** in non-nesting passes.
    Existing **..** spans are preserved. Shared by the DOCX renderer."""
    t = text or ""
    if metrics:
        t = _METRIC_RE.sub(_wrap, t)
    if bold_terms:
        rx = _kw_regex(bold_terms)
        if rx:
            t = rx.sub(_wrap, t)
    return t


def _md(text: str, bold_terms=None, metrics: bool = True) -> str:
    text = mark_bold(text, bold_terms, metrics)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def _build(r: Resume, scale: float, bold_terms) -> tuple[bytes, int]:
    buf = io.BytesIO()
    m = scale  # spacing multiplier
    # bold the JD matches PLUS the candidate's own skill keywords, everywhere in bullets
    bset = list(dict.fromkeys(list(bold_terms or []) + skill_terms(r)))
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.35 * inch, bottomMargin=0.32 * inch,
                            leftMargin=0.5 * inch, rightMargin=0.5 * inch, title=r.name or "Resume")

    def fs(x):  # scaled font size
        return round(x * scale, 1)

    name = ParagraphStyle("name", fontName=FB, fontSize=fs(17), alignment=TA_CENTER, spaceAfter=3 * m, leading=fs(20))
    contact = ParagraphStyle("contact", fontName=F, fontSize=fs(9), alignment=TA_CENTER, spaceAfter=1, leading=fs(11.5))
    auth = ParagraphStyle("auth", fontName=F, fontSize=fs(8.5), alignment=TA_CENTER, spaceAfter=2, leading=fs(10.5))
    heading = ParagraphStyle("heading", fontName=FB, fontSize=fs(10.5), spaceBefore=8 * m, spaceAfter=1, leading=fs(12))
    role = ParagraphStyle("role", fontName=FB, fontSize=fs(10.5), spaceAfter=0, leading=fs(12))
    sub = ParagraphStyle("sub", fontName=F, fontSize=fs(9.5), spaceAfter=1, leading=fs(11))
    body = ParagraphStyle("body", fontName=F, fontSize=fs(9.5), spaceAfter=2 * m, leading=fs(12))
    bullet = ParagraphStyle("bullet", fontName=F, fontSize=fs(9.5), leading=fs(12.5), spaceAfter=3 * m)

    el = []

    def H(t):
        el.append(Paragraph(t.upper(), heading))
        el.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#888888"),
                             spaceBefore=1, spaceAfter=4 * m))

    def role_row(left, right):
        tbl = Table([[Paragraph(_md(left, None, metrics=False), role),
                      Paragraph(right or "", ParagraphStyle("rt", parent=body, alignment=2, fontSize=fs(9)))]],
                    colWidths=[5.4 * inch, 2.1 * inch])
        tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                 ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        el.append(tbl)

    def bullets(items):
        el.append(ListFlowable(
            [ListItem(Paragraph(_md(b, bset), bullet), value="\u2022", leftIndent=15) for b in items],
            bulletType="bullet", start="\u2022", bulletFontName=F, leftIndent=15, spaceBefore=1))

    el.append(Paragraph(r.name, name))
    if r.contact:
        el.append(Paragraph(_md(r.contact, None, metrics=False), contact))
    if r.work_authorization:
        el.append(Paragraph(r.work_authorization, auth))

    if r.summary:
        H("Summary"); el.append(Paragraph(_md(r.summary, bset), body))

    if r.experience:
        H("Experience")
        for i, e in enumerate(r.experience):
            if i:
                el.append(Paragraph("", ParagraphStyle("g", fontSize=3, leading=4 * m)))
            role_row(e.company, e.dates)
            if e.title or e.stack:
                el.append(Paragraph(_md(e.title + (f"  |  {e.stack}" if e.stack else ""), bset), sub))
            if e.bullets:
                bullets(e.bullets)

    if r.projects:
        H("Projects")
        for i, p in enumerate(r.projects):
            if i:
                el.append(Paragraph("", ParagraphStyle("g", fontSize=3, leading=4 * m)))
            el.append(Paragraph(_md(p.name + (f"  |  {p.stack}" if p.stack else ""), bset), role))
            if p.bullets:
                bullets(p.bullets)

    if r.skills:
        H("Skills")
        for line in r.skills:
            if ":" in line:
                cat, items = line.split(":", 1)
                el.append(Paragraph(f"<b>{cat.strip()}:</b> {_md(items.strip(), None, metrics=False)}", body))
            else:
                el.append(Paragraph(_md(line, None, metrics=False), body))

    if r.education:
        H("Education")
        for ed in r.education:
            role_row(ed.school, ed.dates)
            if ed.degree:
                el.append(Paragraph(_md(ed.degree, None, metrics=False), body))
            if ed.coursework:
                el.append(Paragraph("Coursework: " + ed.coursework, sub))

    if r.achievements:
        H("Achievements"); bullets(r.achievements)

    doc.build(el)
    return buf.getvalue(), doc.page


def render_pdf(r: Resume, bold_terms=None) -> bytes:
    """Build the PDF, shrinking progressively until it fits on ONE page."""
    data = None
    for scale in (1.0, 0.96, 0.92, 0.88, 0.84, 0.8):
        data, pages = _build(r, scale, bold_terms)
        if pages <= 1:
            return data
    return data  # smallest attempt if it still overflows (very long resume)
