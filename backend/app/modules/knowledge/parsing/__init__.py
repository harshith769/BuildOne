"""The `Parser` seam (build-plan.md §1.2): raw bytes -> `ParsedDocument` -> `DocumentTree`.

Implementations (S1 decision): PyMuPDF text layer + layout heuristic, Tesseract for pages without a usable
layer, the standard-library HTML parser for official HTML. PyMuPDF is imported only inside this package
(import contract), and only the ingestion CLI imports it: it is not installed in the server image.
"""

from __future__ import annotations

from typing import Literal, Protocol

from app.modules.knowledge.parsing.model import ParsedDocument

SourceFormat = Literal["pdf", "html", "html_bundle"]


class Parser(Protocol):
    def __call__(self, data: bytes, *, format: SourceFormat, bilingual: bool) -> ParsedDocument: ...


def parse(data: bytes, *, format: SourceFormat, bilingual: bool = False) -> ParsedDocument:
    """Default parser for a registered source format."""
    if format == "pdf":
        from app.modules.knowledge.parsing.pdf import parse_pdf

        return parse_pdf(data, bilingual=bilingual)
    from app.modules.knowledge.parsing.html import parse_html

    return parse_html(data, bundle=format == "html_bundle")
