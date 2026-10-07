"""Parser regression against the S1 gold outlines (docs/spikes/S1-parsing.md; fixtures: tests/fixtures/knowledge).

Floors are the M5 numbers at the time of writing; each is at or above S1's parser (a)/(h) result for the same
source. Line metrics are S1's (structure recall, precision, reading-order errors); tree metrics check the
DocumentTree: gold identifier paths found, and section/sub-section nodes the gold doesn't have.
Known gaps (window artifacts, not parser faults): the CGST Act window starts inside s.2's definitions and the
Code's inside Chapter II, so their first entries have no parent in the window.
"""

from __future__ import annotations

import pytest

from app.modules.knowledge.parsing.structure import build_tree
from tests.knowledge.conftest import gold, parsed_fixture, requires_tesseract
from tests.support.s1_scoring import score_lines, tree_precision, tree_recall

# key: (line recall, line precision or None, max order errors, tree recall, max spurious nodes). S1 in comments.
FLOORS: dict[str, tuple[float, float | None, int, float, int]] = {
    "cbdt_tds_notification": (1.0, None, 0, 1.0, 0),  # S1 100%
    "cgst_act_2017": (1.0, 0.98, 0, 0.65, 0),  # S1 100% / 99%
    "cgst_rules_2017_part_a": (1.0, 0.949, 0, 0.98, 0),  # S1 100% / 94.9%
    "cgst_rules_2017_part_b_forms": (0.909, None, 0, 1.0, 0),  # S1 91%
    "code_on_social_security_2020": (1.0, 1.0, 0, 0.99, 1),  # S1 100% / 100%
    "companies_accounts_rules_2014": (
        1.0,
        0.74,
        0,
        1.0,
        0,
    ),  # S1 100% / 74%; tree: form rows are not rules
    "companies_act_2013": (1.0, 1.0, 0, 1.0, 0),  # S1 100% / 100%
    "companies_amendment_gazette": (1.0, 1.0, 0, 1.0, 0),  # S1 100% / 100%
    "companies_incorporation_rules_2014": (1.0, 1.0, 0, 1.0, 0),  # S1 100% / 100%
    "dpiit_startup_notification_2019": (0.98, 1.0, 0, 1.0, 0),  # S1 99% / 100%
    "epf_scheme_2026": (1.0, 1.0, 0, 1.0, 0),  # S1 100% / 100%
    "esic_circular": (0.66, None, 0, 0.0, 0),  # S1 50%: Hindi lines now OCR'd (eng+hin)
    "income_tax_act_2025": (1.0, 1.0, 0, 1.0, 0),  # S1 100% / 100%
    "mca_general_circular": (1.0, None, 0, 1.0, 0),  # S1 100%
    "ts_government_order": (1.0, None, 0, 1.0, 0),  # S1 100%
    "ts_professional_tax_act_1987": (0.99, 1.0, 1, 0.99, 3),  # S1 99% / 100% / 1
    "ts_shops_establishments_act_1988": (1.0, 1.0, 0, 1.0, 0),  # S1 100% / 100%
}
# Sources whose pages go through Tesseract (Hindi lines of mixed bilingual pages).
NEEDS_OCR = {"companies_amendment_gazette", "esic_circular", "cgst_rules_2017_part_b_forms"}


@pytest.mark.parametrize(
    "key",
    [pytest.param(k, marks=requires_tesseract) if k in NEEDS_OCR else k for k in sorted(FLOORS)],
)
def test_parser_holds_s1_quality(key: str) -> None:
    recall_floor, precision_floor, max_order, tree_floor, max_spurious = FLOORS[key]
    doc = parsed_fixture(key)
    outline = gold(key)
    score = score_lines(doc, outline)
    assert score.recall is not None and score.recall >= recall_floor
    if precision_floor is not None:
        assert score.precision is not None and score.precision >= precision_floor
    assert score.order_errors <= max_order
    root = build_tree(doc)
    found, total = tree_recall(root, outline)
    assert total == 0 or found / total >= tree_floor
    spurious, _ = tree_precision(root, outline)
    assert spurious <= max_spurious


def test_annexed_forms_are_their_own_nodes() -> None:
    root = build_tree(parsed_fixture("companies_accounts_rules_2014"))
    annexes = [n.ident for n in root.walk() if n.kind == "annex"]
    assert {"FORM AOC-I", "FORM No. AOC-2", "FORM AOC-3", "FORM AOC-4"} <= set(annexes)
    inside = [
        n
        for n in root.walk()
        if n.kind == "annex"
        for d in n.walk()
        if d.kind in ("section", "subsection")
    ]
    assert inside == []


def test_margin_notes_become_section_headings() -> None:
    root = build_tree(parsed_fixture("income_tax_act_2025"))
    headings = {n.ident: n.heading for n in root.walk() if n.kind == "section"}
    assert headings["392"].startswith("Salary and accumulated balance due to an employee")
    assert headings["394"] == "Collection of tax at source"


def test_tables_are_kept_whole() -> None:
    root = build_tree(parsed_fixture("cgst_rules_2017_part_a"))
    rule7 = next(n for n in root.walk() if n.path == "CHAPTER II > 7")
    tables = [c for c in rule7.content if not isinstance(c, str)]
    assert tables and len(tables[0].table.rows) >= 5  # header, column numbers, 4 rows (S1 gold)


def test_publisher_ocr_layer_is_reviewed() -> None:
    doc = parsed_fixture("mca_general_circular")
    assert [p.source for p in doc.pages] == ["publisher_ocr"]
    assert doc.needs_review


@requires_tesseract
def test_undecodable_hindi_is_replaced_by_ocr_and_english_kept() -> None:
    doc = parsed_fixture("esic_circular")
    text = " ".join(ln.text for ln in doc.lines())
    assert "परिपत्र" in text  # broken layer printed "परप"
    assert "Notified Districts" in text
    assert not doc.needs_review  # only Hindi (never indexed) came from OCR
