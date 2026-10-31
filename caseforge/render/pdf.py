"""PDF case study and one-page summary (BT-6), built with ReportLab.

Layout survives any input length: the case study flows over as many pages as it needs,
and the one-page summary shrinks to fit exactly one page.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepInFrame,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from ..models import SECTION_TITLES, ProjectRecord
from . import BRAND, require_approved

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
HEADER_H = 48 * mm


# ------------------------------------------------------------------ fonts
def _fonts() -> tuple[str, str, str]:
    """Use DejaVu (covers far more characters than Helvetica) when the machine has it."""
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/Library/Fonts"),
        Path("C:/Windows/Fonts"),
    ]
    for d in candidates:
        reg, bold, it = d / "DejaVuSans.ttf", d / "DejaVuSans-Bold.ttf", d / "DejaVuSans-Oblique.ttf"
        if reg.exists() and bold.exists() and it.exists():
            try:
                pdfmetrics.registerFont(TTFont("CF", str(reg)))
                pdfmetrics.registerFont(TTFont("CF-Bold", str(bold)))
                pdfmetrics.registerFont(TTFont("CF-It", str(it)))
                return "CF", "CF-Bold", "CF-It"
            except Exception:
                break
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


FONT, BOLD, ITALIC = _fonts()
INK, ACCENT, MUTED = colors.HexColor(BRAND["ink"]), colors.HexColor(BRAND["accent"]), colors.HexColor(BRAND["muted"])
SOFT, LINE = colors.HexColor(BRAND["soft"]), colors.HexColor(BRAND["line"])


def _styles(scale: float = 1.0) -> dict[str, ParagraphStyle]:
    s = lambda v: v * scale  # noqa: E731
    return {
        "body": ParagraphStyle("body", fontName=FONT, fontSize=s(10.5), leading=s(15.5), textColor=INK, alignment=TA_LEFT),
        "small": ParagraphStyle("small", fontName=FONT, fontSize=s(8.5), leading=s(11.5), textColor=MUTED),
        "h2": ParagraphStyle("h2", fontName=BOLD, fontSize=s(13), leading=s(17), textColor=INK, spaceBefore=s(12), spaceAfter=s(5)),
        "summary": ParagraphStyle("summary", fontName=FONT, fontSize=s(12), leading=s(17.5), textColor=INK),
        "caption": ParagraphStyle("caption", fontName=ITALIC, fontSize=s(8.5), leading=s(11), textColor=MUTED, spaceBefore=3),
        "chip": ParagraphStyle("chip", fontName=BOLD, fontSize=s(9), leading=s(11), textColor=INK),
        "title1": ParagraphStyle("title1", fontName=BOLD, fontSize=s(20), leading=s(24), textColor=INK),
        "kicker": ParagraphStyle("kicker", fontName=BOLD, fontSize=s(8), leading=s(10), textColor=ACCENT),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def _section_texts(record: ProjectRecord, key: str) -> list[str]:
    return [c.text for c in record.active_claims(key)]


def _image(record: ProjectRecord, image_dir: Path, filename: str, max_w: float, max_h: float):
    path = image_dir / filename
    if not path.exists():
        return None
    try:
        img = Image(str(path))
    except Exception:
        return None
    ratio = min(max_w / img.imageWidth, max_h / img.imageHeight, 1.0 if img.imageWidth > max_w / 3 else 3.0)
    img.drawWidth, img.drawHeight = img.imageWidth * ratio, img.imageHeight * ratio
    img.hAlign = "LEFT"
    return img


def _section_heading(title: str, st: dict) -> Table:
    t = Table([["", _p(title, st["h2"])]], colWidths=[3, None])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), ACCENT),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
        ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    t.spaceBefore, t.spaceAfter = 14, 6
    return t


def _chips(items: list[str], st: dict, width: float) -> Table:
    # tools as a wrapped row of chips; claims stay whole sentences so they remain checkable
    cells = [[_p(x, st["body"])] for x in items]
    t = Table(cells, colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _bullets(items: list[str], st: dict) -> ListFlowable:
    return ListFlowable(
        [ListItem(_p(x, st["body"]), leftIndent=12, value="•") for x in items],
        bulletType="bullet", bulletColor=ACCENT, leftIndent=12, bulletFontSize=9,
    )


def _footer_text(record: ProjectRecord, draft: bool) -> str:
    if draft:
        return f"DRAFT — NOT APPROVED — do not send · {record.id}"
    date = record.approved_at[:10] if record.approved_at else ""
    return f"Reviewed and approved by {record.approved_by} on {date} · {record.id}"


def _decorate(record: ProjectRecord, draft: bool, kicker: str):
    def first(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(INK)
        canvas.rect(0, PAGE_H - HEADER_H, PAGE_W, HEADER_H, stroke=0, fill=1)
        canvas.setFillColor(ACCENT)
        canvas.rect(0, PAGE_H - HEADER_H, PAGE_W, 2.2 * mm, stroke=0, fill=1)
        canvas.setFont(BOLD, 8.5)
        canvas.drawString(MARGIN, PAGE_H - 14 * mm, kicker.upper())
        canvas.setFillColor(colors.white)
        title = record.input.title or "Untitled project"
        size = 22 if len(title) <= 42 else 17 if len(title) <= 60 else 14
        canvas.setFont(BOLD, size)
        _wrap_draw(canvas, title, MARGIN, PAGE_H - 26 * mm, PAGE_W - 2 * MARGIN, BOLD, size, max_lines=2)
        canvas.setFont(FONT, 10)
        canvas.setFillColor(colors.HexColor("#C9D1DC"))
        client = record.input.client_name or "Client confidential"
        canvas.drawString(MARGIN, PAGE_H - HEADER_H + 8 * mm, f"Client: {client}")
        canvas.restoreState()
        rest(canvas, doc)

    def rest(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.line(MARGIN, 14 * mm, PAGE_W - MARGIN, 14 * mm)
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, 9 * mm, _footer_text(record, draft))
        canvas.drawRightString(PAGE_W - MARGIN, 9 * mm, f"{BRAND['name']} · page {doc.page}")
        if draft:
            canvas.setFillColor(colors.Color(0.85, 0.2, 0.2, alpha=0.10))
            canvas.setFont(BOLD, 90)
            canvas.translate(PAGE_W / 2, PAGE_H / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "DRAFT")
        canvas.restoreState()

    return first, rest


def _wrap_draw(canvas, text, x, y, width, font, size, max_lines=2):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if pdfmetrics.stringWidth(trial, font, size) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    lines = lines[:max_lines]
    for i, line in enumerate(lines):
        canvas.drawString(x, y - i * size * 1.15, line)


def _doc(path: Path, record: ProjectRecord, draft: bool, kicker: str) -> BaseDocTemplate:
    doc = BaseDocTemplate(str(path), pagesize=A4, title=record.input.title or "Case study",
                          author=BRAND["name"], leftMargin=MARGIN, rightMargin=MARGIN)
    first_frame = Frame(MARGIN, 18 * mm, PAGE_W - 2 * MARGIN, PAGE_H - HEADER_H - 26 * mm, id="first")
    later_frame = Frame(MARGIN, 18 * mm, PAGE_W - 2 * MARGIN, PAGE_H - 34 * mm, id="later")
    on_first, on_rest = _decorate(record, draft, kicker)
    doc.addPageTemplates([
        PageTemplate(id="First", frames=[first_frame], onPage=on_first, autoNextPageTemplate="Later"),
        PageTemplate(id="Later", frames=[later_frame], onPage=on_rest),
    ])
    return doc


# ------------------------------------------------------------------ case study
def render_case_study(record: ProjectRecord, image_dir: Path, out: Path, draft: bool = False) -> Path:
    require_approved(record, draft)
    st = _styles()
    width = PAGE_W - 2 * MARGIN
    story: list = []

    summary = _section_texts(record, "summary")
    if summary:
        box = Table([[_p(" ".join(summary), st["summary"])]], colWidths=[width])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SOFT), ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
            ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        story += [box, Spacer(1, 4)]

    images_by_section: dict[str, list] = {}
    for img in record.input.images:
        images_by_section.setdefault(img.section, []).append(img)

    for key in ["client_problem", "work_done", "technical_approach", "tools", "challenges", "results"]:
        texts = _section_texts(record, key)
        if not texts:
            continue  # a missing section is left out, never filled in
        heading = _section_heading(SECTION_TITLES[key], st)
        if key == "tools":
            body = _chips(texts, st, width)
        elif key in ("challenges", "results"):
            body = _bullets(texts, st)
        else:
            body = _p(" ".join(texts), st["body"])
        story.append(KeepTogether([heading, body]))
        # images sit next to the section they belong to (Stretch T-16)
        for img in images_by_section.get(key, []):
            flow = _image(record, image_dir, img.filename, width, 95 * mm)
            if flow:
                parts = [Spacer(1, 8), flow]
                if img.caption:
                    parts.append(_p(img.caption, st["caption"]))
                story.append(KeepTogether(parts))

    # images attached to a section that has no text still appear, at the end
    placed = {"client_problem", "work_done", "technical_approach", "tools", "challenges", "results"}
    leftovers = [i for s, imgs in images_by_section.items() if s not in placed or not _section_texts(record, s) for i in imgs]
    for img in leftovers:
        flow = _image(record, image_dir, img.filename, width, 95 * mm)
        if flow:
            story.append(KeepTogether([Spacer(1, 10), flow] + ([_p(img.caption, st["caption"])] if img.caption else [])))

    out.parent.mkdir(parents=True, exist_ok=True)
    _doc(out, record, draft, "Case study").build(story)
    return out


# ------------------------------------------------------------------ one-pager
def render_one_pager(record: ProjectRecord, image_dir: Path, out: Path, draft: bool = False) -> Path:
    """Exactly one page, whatever the input length: content is shrunk to fit the frame."""
    require_approved(record, draft)
    width = PAGE_W - 2 * MARGIN
    frame_h = PAGE_H - HEADER_H - 26 * mm
    st = _styles()
    story: list = []

    summary = _section_texts(record, "summary")
    if summary:
        story += [_p(" ".join(summary), st["summary"]), Spacer(1, 8)]

    def block(key: str, limit: int | None, as_bullets: bool) -> list:
        texts = _section_texts(record, key)[:limit] if limit else _section_texts(record, key)
        if not texts:
            return []
        body = _bullets(texts, st) if as_bullets else _p(" ".join(texts), st["body"])
        return [_section_heading(SECTION_TITLES[key], st), body]

    left = block("client_problem", 3, False) + block("work_done", 3, False) + block("technical_approach", 2, False)
    right = block("results", None, True) + block("tools", None, True) + block("challenges", 2, True)
    col_w = (width - 8 * mm) / 2
    cols = Table([[left or [Spacer(1, 1)], right or [Spacer(1, 1)]]], colWidths=[col_w, col_w])
    cols.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (0, 0), 8 * mm), ("RIGHTPADDING", (1, 0), (1, 0), 0)]))
    story.append(cols)

    if record.input.images:
        first_img = record.input.images[0]
        flow = _image(record, image_dir, first_img.filename, width, 60 * mm)
        if flow:
            story += [Spacer(1, 10), flow]
            if first_img.caption:
                story.append(_p(first_img.caption, st["caption"]))

    out.parent.mkdir(parents=True, exist_ok=True)
    doc = _doc(out, record, draft, "One-page summary")
    doc.build([KeepInFrame(width, frame_h - 4, story, mode="shrink")])
    return out


def export_name(record: ProjectRecord, kind: str, draft: bool) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    return f"{record.id}_{kind}{'_DRAFT' if draft else ''}_{stamp}.pdf"
