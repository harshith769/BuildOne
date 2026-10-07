"""Parser output: pages of reading-order lines, tables, and OCR confidence (no PDF library imported here).

Every parser (PDF text layer, Tesseract OCR, HTML) produces a `ParsedDocument`. The tree builder
(`parsing.structure`) turns its lines into a `DocumentTree`; the regression tests score the lines against the
S1 gold outlines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

LineKind = Literal["body", "note", "footnote"]
PageSource = Literal["text", "ocr", "publisher_ocr", "html"]

# S1 thresholds (data-pipeline.md §7): an OCR'd page below this mean word confidence waits for review; inside
# other pages, lines below LINE_REVIEW_CONFIDENCE are listed in the ingestion report.
PAGE_REVIEW_CONFIDENCE = 93.0
LINE_REVIEW_CONFIDENCE = 90.0


@dataclass(frozen=True, slots=True)
class Table:
    """A table found on one page; `rows` as extracted (cells may be empty strings)."""

    page: int
    rows: tuple[tuple[str, ...], ...]

    @property
    def header(self) -> tuple[str, ...]:
        return self.rows[0] if self.rows else ()


@dataclass(frozen=True, slots=True)
class Line:
    """One reading-order line. `note`: a margin note (a section heading printed beside its section).
    `footnote`: small-type text at the foot of the page (amendment history, never structure). `table`: index
    into the page's tables when the line lies inside one. `lang` is "hi" for a Devanagari line."""

    text: str
    page: int
    kind: LineKind = "body"
    table: int | None = None
    lang: Literal["en", "hi"] = "en"
    confidence: float | None = None
    top: float | None = None  # y of the line's top in PDF points (PDF pages only)


@dataclass(slots=True)
class Page:
    number: int
    source: PageSource
    lines: list[Line] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    confidence: float | None = None  # mean OCR word confidence (OCR pages only)

    @property
    def needs_review(self) -> bool:
        if self.source == "publisher_ocr":
            return True
        return self.source == "ocr" and (
            self.confidence is None or self.confidence < PAGE_REVIEW_CONFIDENCE
        )

    @property
    def low_confidence_lines(self) -> list[Line]:
        return [
            ln
            for ln in self.lines
            if ln.confidence is not None and ln.confidence < LINE_REVIEW_CONFIDENCE
        ]


@dataclass(slots=True)
class ParsedDocument:
    parser: str  # name@version, stored on the source version
    pages: list[Page]
    warnings: list[str] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return any(p.needs_review for p in self.pages)

    def lines(self) -> list[Line]:
        return [ln for p in self.pages for ln in p.lines]

    def table_at(self, page_number: int, index: int) -> Table | None:
        page = next((p for p in self.pages if p.number == page_number), None)
        return page.tables[index] if page is not None and index < len(page.tables) else None
