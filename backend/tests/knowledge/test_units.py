"""Unit tests: registry, glossary, label keys, Devanagari checks, tree rules, chunking policy."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.modules.knowledge.chunking import MAX_TOKENS, build_chunks, render_table
from app.modules.knowledge.glossary import Glossary, load_glossary
from app.modules.knowledge.labels import LabelKey, matches
from app.modules.knowledge.parsing import devanagari
from app.modules.knowledge.parsing.model import Line, Page, ParsedDocument, Table
from app.modules.knowledge.parsing.structure import build_tree, split_units
from app.modules.knowledge.registry import Source, is_official_url, load_registry
from tests.knowledge.conftest import document, word_offsets, words

# --- registry ---------------------------------------------------------------------------------------------


def _source(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "key": "example_act",
        "title": "Example Act",
        "authority": "Ministry",
        "jurisdiction": "IN",
        "doc_type": "act",
        "domains": ["company_law"],
        "official_url": "https://www.indiacode.nic.in/handle/1",
        "manual": "by hand",
        "effective_from": dt.date(2020, 1, 1),
    }
    return {**base, **overrides}


def test_registry_file_is_valid_and_official() -> None:
    registry = load_registry()
    assert len(registry) >= 21
    assert all(is_official_url(s.official_url) for s in registry.values())


@pytest.mark.parametrize(
    "url",
    [
        "http://www.mca.gov.in/",
        "https://example.com/act.pdf",
        "https://gov.in.example.com/",
        "https://cleartax.in/",
    ],
)
def test_registry_rejects_unofficial_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        Source.model_validate(_source(official_url=url))


def test_registry_needs_an_origin_and_ordered_dates() -> None:
    with pytest.raises(ValidationError, match="download_url or manual"):
        Source.model_validate(_source(manual=None))
    with pytest.raises(ValidationError, match="effective_to"):
        Source.model_validate(_source(effective_to=dt.date(2019, 1, 1)))


def test_registry_rejects_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    entry = (
        "- {key: a_act, title: A Act, authority: MCA, jurisdiction: IN, doc_type: act, domains: [company_law], "
        "official_url: 'https://x.gov.in/', manual: m, effective_from: 2020-01-01}\n"
    )
    path.write_text(entry * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_registry(path)


# --- glossary (ADR-0014) ------------------------------------------------------------------------------------


def test_glossary_expands_first_whole_word_case_sensitive_occurrence() -> None:
    g = Glossary(version=1, terms={"TCS": "tax collected at source", "PT": "professional tax"})
    assert (
        g.expand("When does TCS apply? TCS again")
        == "When does TCS (tax collected at source) apply? TCS again"
    )
    assert g.expand("PTO and pt are not PT") == "PTO and pt are not PT (professional tax)"


def test_repository_glossary_is_terminology_only() -> None:
    g = load_glossary()
    assert g.version >= 1 and "TDS" in g.terms
    assert not any(
        ch.isdigit() for v in g.terms.values() for ch in v
    )  # no thresholds, rates or dates


# --- label keys (evaluation.md §1) --------------------------------------------------------------------------


def test_label_matches_at_or_under_and_allows_extra_levels() -> None:
    key = LabelKey.parse("companies_act_2013::CHAPTER III > 23")
    assert matches(
        key,
        "companies_act_2013",
        "CHAPTER III > PART I > 23 > (2)",
        0,
        ["CHAPTER III > PART I > 23 > (2)"],
    )
    assert not matches(
        key, "companies_act_2013", "CHAPTER III > PART I > 24", 0, ["CHAPTER III > PART I > 24"]
    )
    assert not matches(key, "other_source", "CHAPTER III > 23", 0, ["CHAPTER III > 23"])


def test_label_piece_selects_one_ordinal_and_empty_path_any_chunk() -> None:
    key = LabelKey.parse("income_tax_act_2025::B > 393 > (1)#7")
    path = "CHAPTER XIX > B > 393 > (1)"
    assert matches(key, "income_tax_act_2025", path, 7, [path])
    assert not matches(key, "income_tax_act_2025", path, 6, [path])
    assert matches(LabelKey.parse("esic_circular::"), "esic_circular", "", 0, [""])


def test_merged_chunk_matches_every_node_it_covers() -> None:
    key = LabelKey.parse("x_act::4 > (2)")
    assert matches(key, "x_act", "4 > (1)", 0, ["4 > (1)", "4 > (2)", "4 > (3)"])


# --- Devanagari ---------------------------------------------------------------------------------------------


def test_broken_hindi_layer_is_detected_and_clean_hindi_is_not() -> None:
    broken = "अिधसूिचत िारा " * 20  # signs after vowels/spaces: a legacy or broken ToUnicode layer
    clean = "अधिसूचित धारा सरकार " * 20
    assert devanagari.has_undecodable_hindi(broken)
    assert not devanagari.has_undecodable_hindi(clean)
    assert not devanagari.has_undecodable_hindi(
        "भारत का राजपत्र  THE GAZETTE OF INDIA " + "English text " * 50
    )


def test_hindi_lines_and_pages() -> None:
    assert devanagari.is_hindi_line("सामाजिक सुरक्षा संहिता")
    assert not devanagari.is_hindi_line("परिपत्र / Notification under Section 1(4) of the Code")
    assert devanagari.is_hindi_page("कर्मचारी राज्य बीमा निगम " * 10 + "ESIC")


# --- tree rules (S1 mapping notes) --------------------------------------------------------------------------


def _paths(doc: ParsedDocument) -> list[str]:
    return [n.path for n in build_tree(doc).walk() if n.kind != "root"]


def test_inline_units_split_and_wrapped_references_join() -> None:
    assert split_units("14. (1) The company shall") == ["14.", "(1) The company shall"]
    assert split_units("3. Registration :- (1) Every") == ["3. Registration :-", "(1) Every"]
    doc = document(
        "CHAPTER II",
        "3. Formation.- (1) A company under sub-section",
        "(2) of section 4 may",
        "(2) Second.",
    )
    assert _paths(doc) == [
        "CHAPTER II",
        "CHAPTER II > 3",
        "CHAPTER II > 3 > (1)",
        "CHAPTER II > 3 > (2)",
    ]


def test_margin_note_is_the_section_heading() -> None:
    doc = document(Line("Formation of company.", 1, kind="note"), "3. (1) A company may be formed")
    section = next(n for n in build_tree(doc).walk() if n.kind == "section")
    assert section.heading == "Formation of company"


def test_numbering_is_monotone_so_table_serials_stay_text() -> None:
    doc = document(
        "392. Salary.- (1) Deduct.",
        "393. Tax.- (1) Where",
        "1. Commission or brokerage",
        "394. TCS.- (1) Collect",
    )
    assert _paths(doc) == ["392", "392 > (1)", "393", "393 > (1)", "394", "394 > (1)"]


def test_forms_annexures_and_schedules_hold_no_rules() -> None:
    doc = document(
        "8. Rule eight.- (1) Text.",
        "FORM AOC-1",
        "1. Sl. No.",
        "(1) Column one",
        "THE FIRST SCHEDULE",
        "2. Item",
    )
    assert _paths(doc) == ["8", "8 > (1)", "FORM AOC-1", "THE FIRST SCHEDULE"]


def test_amendment_notes_and_footnotes_are_notes_not_structure() -> None:
    doc = document(
        "9. Verification.- (1) The application",
        "(2) Vide Notf no.94/2020 - CT dt. 22.12.2020 inserted",
        "(2) Where the application",
        Line("1. Subs. by Act 7 of 2017", 1, kind="footnote"),
    )
    tree = build_tree(doc)
    assert [n.path for n in tree.walk() if n.kind != "root"] == ["9", "9 > (1)", "9 > (2)"]
    assert any("Vide Notf" in note for n in tree.walk() for note in n.notes)


def test_unnumbered_blocks_restart_numbering() -> None:
    doc = document(
        "Read the following:-",
        "1. G.O.Ms.No.4",
        "2. Letter",
        "3. Letter",
        "O R D E R:-",
        "Government have adapted the rules.",
        "2. In the circumstances",
        "AMENDMENT",
        "(1) In Schedule I",
    )
    assert _paths(doc) == [
        "Read",
        "Read > 1",
        "Read > 2",
        "Read > 3",
        "ORDER",
        "ORDER > 2",
        "AMENDMENT",
        "AMENDMENT > (1)",
    ]


def test_side_heading_line_heads_an_unheaded_paragraph() -> None:
    doc = document(
        "3. A Startup may apply.",
        "Exemption for the purpose of section 56 of the Act",
        "4. A Startup shall be eligible",
    )
    para = next(n for n in build_tree(doc).walk() if n.path == "4")
    assert para.heading == "Exemption for the purpose of section 56 of the Act"


def test_hindi_lines_are_not_indexed() -> None:
    doc = document("1. Title.- (1) English text", Line("हिंदी पाठ यहाँ है", 1, lang="hi"))
    assert "हिंदी" not in " ".join(str(c) for n in build_tree(doc).walk() for c in n.content)


# --- chunking (data-pipeline.md §4) -------------------------------------------------------------------------


def test_leaves_chunk_small_siblings_merge_and_parents_are_context() -> None:
    doc = document(
        "CHAPTER I",
        "1. Short title.- (1) This Act may be called the Act.",
        "(2) It extends to India.",
        "2. Definitions.- (1) " + "word " * 120,
    )
    chunks = build_chunks(build_tree(doc), words, word_offsets)
    ranked = [c for c in chunks if c.kind != "parent"]
    assert ranked[0].node_paths == ["CHAPTER I > 1 > (1)", "CHAPTER I > 1 > (2)"]  # rule 3
    assert ranked[1].section_path == "CHAPTER I > 2 > (1)"
    parents = {c.section_path for c in chunks if c.kind == "parent"}
    assert parents == {"CHAPTER I", "CHAPTER I > 1", "CHAPTER I > 2"}
    assert all(c.parent_path for c in ranked)
    assert (
        ranked[0]
        .embed_text("Example Act")
        .startswith("Example Act > CHAPTER I > 1 > (1)\nShort title\n")
    )


def test_long_leaves_split_with_overlap() -> None:
    lines = [f"(1) {'alpha ' * 5}"] + [f"line{i} " + "beta " * 39 for i in range(30)]
    doc = document("5. Long.- " + lines[0], *lines[1:])
    pieces = [c for c in build_chunks(build_tree(doc), words, word_offsets) if c.kind != "parent"]
    assert len(pieces) >= 3
    assert [c.ordinal for c in pieces] == list(range(len(pieces)))
    assert all(c.token_count <= MAX_TOKENS for c in pieces)
    assert pieces[1].text.split()[0] in pieces[0].text  # ~50 tokens of overlap


def test_tables_stay_whole_or_split_by_rows_with_header() -> None:
    small = Table(page=1, rows=(("Sl.", "Nature", "Rate"), ("1.", "Rent", "10%"), ("", "", "")))
    assert render_table(small) == ["Sl. | Nature | Rate", "1. | Rent | 10%"]
    big = Table(
        page=1,
        rows=(("Sl.", "Nature", "Rate"), *[(f"{i}.", "word " * 40, "1%") for i in range(30)]),
    )
    doc = ParsedDocument(
        parser="t",
        pages=[
            Page(1, "text", [Line("7. Rates.- (1) Table:", 1), Line("cell", 1, table=0)], [big])
        ],
    )
    tables = [c for c in build_chunks(build_tree(doc), words, word_offsets) if c.kind == "table"]
    assert len(tables) > 1 and all(c.text.startswith("Sl. | Nature | Rate") for c in tables)
