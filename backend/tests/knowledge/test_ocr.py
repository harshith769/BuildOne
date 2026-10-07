"""OCR path (S1 decision): pages without a text layer go through Tesseract at 300 dpi; the page's mean word
confidence decides review (< 93) and low lines (< 90) are listed. Fixtures: public Gazette/Act pages rasterised
without their text layer (signed scans are not committed); the reference is the same page's publisher text."""

from __future__ import annotations

import pytest
from rapidfuzz.distance import Levenshtein

from app.modules.knowledge.parsing.model import Line, Page
from app.modules.knowledge.parsing.ocr import _page_from_tsv
from app.modules.knowledge.parsing.text import normalise
from tests.knowledge.conftest import FIXTURES, parsed_fixture, requires_tesseract


@requires_tesseract
@pytest.mark.parametrize("key", ["ocr_companies_act_p24", "ocr_epf_scheme_p66"])
def test_ocr_reads_a_clean_page_within_two_percent_cer(key: str) -> None:
    doc = parsed_fixture(key)
    assert [p.source for p in doc.pages] == ["ocr"]
    hyp = normalise(" ".join(ln.text for ln in doc.lines() if ln.lang == "en"))
    ref = normalise((FIXTURES / "gold" / f"{key}.ref.txt").read_text(encoding="utf-8"))
    assert Levenshtein.distance(hyp, ref) / len(ref) <= 0.02
    assert doc.pages[0].confidence is not None and doc.pages[0].confidence >= 93
    assert not doc.needs_review
    assert "tesseract" in doc.parser


TSV_HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"


def _tsv(*words: tuple[int, float, str]) -> str:
    rows = [
        f"5\t1\t1\t1\t{line}\t{i}\t0\t{line * 50}\t10\t10\t{conf}\t{text}"
        for i, (line, conf, text) in enumerate(words)
    ]
    return TSV_HEADER + "\n".join(rows) + "\n"


def test_low_confidence_page_needs_review_and_low_lines_are_listed() -> None:
    page = _page_from_tsv(
        _tsv((1, 95, "Clean"), (1, 97, "line"), (2, 60, "~__Smudged"), (2, 70, "stamp")), 1
    )
    assert page.confidence is not None and page.confidence < 93
    assert page.needs_review
    assert [ln.text for ln in page.lines] == ["Clean line", "Smudged stamp"]  # debris stripped
    assert [ln.text for ln in page.low_confidence_lines] == ["Smudged stamp"]


def test_confident_page_passes_but_keeps_its_weak_lines_for_the_report() -> None:
    page = _page_from_tsv(_tsv((1, 99, "Section"), (1, 99, "3."), (2, 89, "maybe")), 1)
    assert page.confidence is not None and page.confidence >= 93
    assert not page.needs_review
    assert [ln.text for ln in page.low_confidence_lines] == ["maybe"]


def test_text_and_html_pages_never_need_review() -> None:
    assert not Page(number=1, source="text", lines=[Line("x", 1)]).needs_review
    assert not Page(number=1, source="html", lines=[Line("x", 1)]).needs_review
