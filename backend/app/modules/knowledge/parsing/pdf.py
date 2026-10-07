"""PDF parser: PyMuPDF text layer + the S1 layout heuristic, Tesseract for pages without a usable layer.

Per page (S1 decision, data-pipeline.md §1):
- **Text layer** (born-digital): narrow blocks in the outer 24% of the page are margin notes (section headings),
  emitted just before the body line they sit beside, unless they start with a list number; fragments on one
  baseline are joined left to right; small-type blocks in the lower half are footnotes (kept as notes, never
  structure); lines inside a table found by PyMuPDF's table finder carry the table's index.
- **No text layer** (< 50 characters): OCR (`ocr.ocr_page`).
- **Invisible text over a page image** (the publisher's own OCR): the layer is used but the page is reviewed.
- **Bilingual pages:** a page that is mostly Devanagari belongs to the Hindi half and is skipped (citations use
  the English text); a mixed page whose Hindi layer is undecodable is OCR'd with `eng+hin` instead (S1).
After all pages: running heads and feet (text repeated in the top or bottom two lines of >= 3 pages, digits
ignored) are dropped, keeping a real chapter heading that repeats the running head on its first page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Literal

import pymupdf

from app.modules.knowledge.parsing import devanagari
from app.modules.knowledge.parsing.model import Line, LineKind, Page, ParsedDocument, Table
from app.modules.knowledge.parsing.ocr import ocr_page, tesseract_version

pymupdf.no_recommend_layout()  # the optional ML layout package is not used (S1: heuristic + text layer)
pymupdf.TOOLS.mupdf_display_errors(
    False
)  # malformed-content noise from official PDFs; text is unaffected

PARSER_NAME = "pymupdf-layout"
PARSER_VERSION = "1"
TEXT_LAYER_MIN_CHARS = 50
SAME_LINE_PT = (
    6.0  # an OCR line within this many points of a text-layer line is the same printed line
)
MARGIN = 0.24  # outer share of the page width where margin notes sit
NOTE_MAX_WIDTH = 0.25
FOOTNOTE_SIZE = 0.85  # footnote spans are set below this share of the page's median font size
_LIST_START = re.compile(r"^(\d{1,3}[.)]|\(\w{1,4}\)|[ivxIVX]{1,4}[.)])")


@dataclass(slots=True)
class _Fragment:
    top: float
    bottom: float
    x0: float
    x1: float
    text: str
    kind: LineKind


def parse_pdf(data: bytes, *, bilingual: bool = False) -> ParsedDocument:
    doc = pymupdf.open(stream=data, filetype="pdf")
    pages: list[Page] = []
    warnings: list[str] = []
    ocr_used = False
    for index in range(doc.page_count):
        page = doc[index]
        number = index + 1
        text = page.get_text()
        if len(text.strip()) < TEXT_LAYER_MIN_CHARS:
            pages.append(ocr_page(page, number, bilingual=bilingual))
            ocr_used = True
            continue
        if devanagari.is_hindi_page(text):
            warnings.append(f"page {number}: Hindi half of a bilingual source, not indexed")
            continue
        parsed = _text_layer_page(page, number)
        if devanagari.has_undecodable_hindi(text):
            _replace_hindi_with_ocr(parsed, ocr_page(page, number, bilingual=True))
            warnings.append(
                f"page {number}: undecodable Hindi text layer; Hindi lines OCR'd with eng+hin"
            )
            ocr_used = True
        if _is_publisher_ocr(page):
            parsed.source = "publisher_ocr"
        pages.append(parsed)
    _drop_running_lines(pages)
    version = f"{PARSER_NAME}@{PARSER_VERSION}+pymupdf-{pymupdf.VersionBind}"
    if ocr_used:
        version += f"+tesseract-{tesseract_version()}"
    return ParsedDocument(parser=version, pages=pages, warnings=warnings)


def _replace_hindi_with_ocr(parsed: Page, ocr: Page) -> None:
    """S1 follow-up: Hindi from a legacy-encoded or broken layer is replaced by Tesseract `eng+hin`. A text-layer line
    with any Devanagari is swapped for the OCR line(s) at the same height; Hindi-only OCR lines fill the rest.
    English-only lines and tables keep the text layer (OCR misreads printed numbers: "(iii)" -> "(11)"). Hindi is
    never indexed, so the page needs no review for its OCR'd part."""
    used: set[int] = set()
    merged: list[Line] = []
    for line in parsed.lines:
        if line.top is None or not any(devanagari.is_devanagari(ch) for ch in line.text):
            merged.append(line)
            continue
        twins = [
            i
            for i, o in enumerate(ocr.lines)
            if i not in used and o.top is not None and abs(o.top - line.top) < SAME_LINE_PT
        ]
        if not twins:
            merged.append(line)
            continue
        used.update(twins)
        merged.extend(replace(ocr.lines[i], kind=line.kind, table=line.table) for i in twins)
    merged.extend(o for i, o in enumerate(ocr.lines) if i not in used and o.lang == "hi")
    parsed.lines = sorted(merged, key=lambda ln: ln.top if ln.top is not None else 0.0)


def _is_publisher_ocr(page: pymupdf.Page) -> bool:
    """Most characters drawn invisibly (render mode 3) over an image: an OCR layer, not born-digital text."""
    traces = page.get_texttrace()
    chars = sum(len(t["chars"]) for t in traces)
    invisible = sum(len(t["chars"]) for t in traces if t["type"] == 3)
    return chars > 0 and invisible / chars > 0.8 and bool(page.get_images())


def _text_layer_page(page: pymupdf.Page, number: int) -> Page:
    width, height = page.rect.width, page.rect.height
    blocks = [b for b in page.get_text("dict")["blocks"] if b.get("type") == 0]
    sizes = sorted(
        span["size"]
        for b in blocks
        for ln in b["lines"]
        for span in ln["spans"]
        if span["text"].strip()
    )
    body_size = sizes[len(sizes) // 2] if sizes else 0.0
    body: list[_Fragment] = []
    notes: list[_Fragment] = []
    for block in blocks:
        spans = [span for ln in block["lines"] for span in ln["spans"] if span["text"].strip()]
        if not spans:
            continue
        x0, y0, x1, _ = block["bbox"]
        wide = x1 - x0 >= NOTE_MAX_WIDTH * width
        footnote = (
            wide and y0 > height / 2 and max(sp["size"] for sp in spans) < FOOTNOTE_SIZE * body_size
        )
        first = "".join(span["text"] for span in block["lines"][0]["spans"]).strip()
        is_note = (
            not wide
            and (x1 < MARGIN * width or x0 > (1 - MARGIN) * width)
            and not _LIST_START.match(first)
        )
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"]).strip()
            if not text:
                continue
            lx0, ly0, lx1, ly1 = line["bbox"]
            kind: LineKind = "footnote" if footnote else "note" if is_note else "body"
            (notes if is_note else body).append(_Fragment(ly0, ly1, lx0, lx1, text, kind))
    tables = []
    rects = []
    drawings = page.get_drawings()
    for found in page.find_tables().tables:
        if not _is_ruled(drawings, pymupdf.Rect(found.bbox)):
            continue  # borderless layout grid (white cell fills): its text is ordinary body text
        rows = tuple(tuple((c or "").strip() for c in row) for row in found.extract())
        tables.append(Table(page=number, rows=rows))
        rects.append(pymupdf.Rect(found.bbox))
    lines = _merge_baselines(body, number, rects)
    _insert_notes(lines, notes, number)
    return Page(
        number=number,
        source="text",
        lines=[ln for _, ln in lines],
        tables=tables,
    )


def _visible(color: object) -> bool:
    return isinstance(color, (tuple, list)) and len(color) > 0 and min(color) < 0.9


def _is_ruled(drawings: list[dict[str, object]], rect: pymupdf.Rect) -> bool:
    """A data table has visible rules; Word layout tables found by the finder are white rectangles."""
    return any(
        rect.intersects(d["rect"]) and (_visible(d.get("color")) or _visible(d.get("fill")))
        for d in drawings
    )


def _table_of(fragment: _Fragment, rects: list[pymupdf.Rect]) -> int | None:
    cx, cy = (fragment.x0 + fragment.x1) / 2, (fragment.top + fragment.bottom) / 2
    return next((i for i, r in enumerate(rects) if r.contains(pymupdf.Point(cx, cy))), None)


def _merge_baselines(
    body: list[_Fragment], number: int, rects: list[pymupdf.Rect]
) -> list[tuple[float, Line]]:
    """Join fragments that share a baseline (within 3 pt), left to right."""
    body.sort(key=lambda f: (f.top, f.x0))
    groups: list[list[_Fragment]] = []
    for frag in body:
        if groups and abs(frag.top - groups[-1][0].top) < 3 and frag.kind == groups[-1][0].kind:
            groups[-1].append(frag)
        else:
            groups.append([frag])
    out: list[tuple[float, Line]] = []
    for group in groups:
        group.sort(key=lambda f: f.x0)
        text = " ".join(f.text for f in group)
        table = _table_of(group[0], rects)
        lang: Literal["en", "hi"] = "hi" if devanagari.is_hindi_line(text) else "en"
        out.append(
            (
                group[0].top,
                Line(
                    text=text,
                    page=number,
                    kind=group[0].kind,
                    table=table,
                    lang=lang,
                    top=group[0].top,
                ),
            )
        )
    return out


def _insert_notes(lines: list[tuple[float, Line]], notes: list[_Fragment], number: int) -> None:
    """A margin note is one heading split over short lines: join each note block and insert it before the body
    line nearest to its top."""
    blocks: list[_Fragment] = []
    for frag in sorted(notes, key=lambda f: (f.top, f.x0)):
        last = blocks[-1] if blocks else None
        if last is not None and frag.top - last.bottom < 4 and abs(frag.x0 - last.x0) < 40:
            last.bottom = frag.bottom
            last.text = f"{last.text} {frag.text}"
        else:
            blocks.append(_Fragment(frag.top, frag.bottom, frag.x0, frag.x1, frag.text, "note"))
    for block in reversed(blocks):
        note = Line(text=block.text, page=number, kind="note", top=block.top)
        if not lines:
            lines.append((block.top, note))
            continue
        nearest = min(range(len(lines)), key=lambda k: abs(lines[k][0] - block.top))
        lines.insert(nearest, (lines[nearest][0], note))


def _running_key(text: str) -> str:
    return re.sub(r"[\d\s]+", " ", text).strip().lower()


def _drop_running_lines(pages: list[Page]) -> None:
    edges = [p for p in pages if p.source != "ocr"]
    counts: dict[str, int] = {}
    for page in edges:
        texts = [ln.text for ln in page.lines]
        for key in {_running_key(t) for t in texts[:2] + texts[-2:]}:
            counts[key] = counts.get(key, 0) + 1
    running = {k for k, n in counts.items() if n >= 3 and k}
    for page in edges:
        lines = page.lines
        n = len(lines)
        page.lines = [
            ln
            for i, ln in enumerate(lines)
            if not (
                (i < 2 or i >= n - 2)
                and _running_key(ln.text) in running
                and not (i > 0 and _running_key(lines[i - 1].text) == _running_key(ln.text))
            )
        ]
