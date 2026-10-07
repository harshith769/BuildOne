"""DocumentTree: parser lines -> a tree of chapters, sections and sub-sections (data-pipeline.md §4).

Implements the S1 "DocumentTree mapping notes" (docs/spikes/S1-parsing.md):
1. margin notes are section headings;  2. inline units are split ("14. (1) ...");  3. a "(n)" that wraps a
cross-reference continues its line;  4. numbering is monotone (a table serial "1." inside s.393 is text);
5. "FORM ...", "Annexure" and "Schedule" start an annex node whose numbered rows are never rules;
6. running heads, footnotes and tables of contents never become structure (footnotes stay as notes);
7. printed identifiers are normalised ("CHAPTER - I", "5-A:", "A B S T R A C T");  8. HTML list numbers are
sub-sections;  9. Hindi lines are not indexed;  10. OCR debris is stripped.

Leaves are sub-sections (or sections, paragraphs and annexes without them); clauses, provisos and
explanations stay in their sub-section's text, so a chunk always carries its lead-in. Unnumbered blocks of
circulars and orders ("Subject", "Read", "ORDER", "AMENDMENT") are containers that restart the numbering.
Paths look like `CHAPTER II > 3 > (1)`; the source title is prefixed when chunks are made.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal

from app.modules.knowledge.parsing.model import LineKind, ParsedDocument, Table
from app.modules.knowledge.parsing.text import normalise, strip_ocr_debris

NodeKind = Literal["root", "chapter", "part", "block", "section", "subsection", "annex"]


@dataclass(slots=True)
class TableBlock:
    """A table kept whole inside a node's text (chunking rule 4)."""

    table: Table


Content = str | TableBlock


@dataclass(slots=True)
class Node:
    kind: NodeKind
    ident: str
    heading: str = ""
    page: int | None = None
    content: list[Content] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    children: list[Node] = field(default_factory=list)
    parent: Node | None = field(default=None, repr=False)

    def add(self, child: Node) -> Node:
        child.parent = self
        self.children.append(child)
        return child

    @property
    def path(self) -> str:
        parts: list[str] = []
        node: Node | None = self
        while node is not None and node.kind != "root":
            parts.append(node.ident)
            node = node.parent
        return " > ".join(reversed(parts))

    def walk(self) -> Iterator[Node]:
        yield self
        for child in self.children:
            yield from child.walk()

    def leaves(self) -> Iterator[Node]:
        for node in self.walk():
            if not node.children and node.kind != "root":
                yield node


# ---------------------------------------------------------------------------------------------------------
# Line preparation: the S1 scorer's shared tree-builder rules (also used by the parser regression tests).

_SPLIT = re.compile(
    r"^(\[?\s*\d{1,3}[A-Z]{0,3}\s*\.(?:[^()]{0,200}?(?:[.:]\s*-+|:|-{2,}|\.-))?)\s*(?=\(\d{1,2}\))"
)
_LABEL_FIRST_ITEM = re.compile(r"^([^\W\d][\w .]{0,12}[:\-]+)\s*(?=1\s*\.\s)")
_REFERENCE_END = re.compile(
    r"\b(?:sub-rules?|sub-sections?|sub-paragraphs?|clauses?|columns?|rules?|sections?|paragraphs?)$",
    re.IGNORECASE,
)
_HEADING_ONLY = re.compile(r"^\[?\s*\d{1,3}[A-Z]{0,3}\s*\.\s+[^()]{1,150}$")
_HEADING_TAIL = re.compile(
    r"^(?!\[?\s*\d{1,3}[A-Z]{0,3}\s*\.)[^()]{0,160}?(?:[.:]\s*-+|-{2,})\s*\(\d{1,2}\)"
)
_SPACED_CAPS = re.compile(r"^((?:[A-Z] ){2,}[A-Z])\b")


@dataclass(frozen=True, slots=True)
class PreparedLine:
    text: str
    page: int
    kind: LineKind
    table: int | None


def split_units(text: str) -> list[str]:
    """ "14. (1) The ..." and "3. Registration :- (1) Every ..." carry a section and its first sub-section."""
    if m := _LABEL_FIRST_ITEM.match(text):
        return [m.group(1).strip(), *split_units(text[m.end() :])]
    m = _SPLIT.match(text)
    return [m.group(1).strip(), text[m.end() :]] if m else [text]


def _collapse_spaced_caps(text: str) -> str:
    m = _SPACED_CAPS.match(text)
    return m.group(1).replace(" ", "") + text[m.end() :] if m else text


def prepare_lines(doc: ParsedDocument, *, include_hindi: bool = False) -> list[PreparedLine]:
    """Normalised English lines with wrapped references and headings joined, and inline units split.
    Hindi lines are left out (not indexed) unless `include_hindi` (parser scoring only)."""
    raw: list[PreparedLine] = []
    for line in doc.lines():
        if line.lang == "hi" and not include_hindi:
            continue
        text = _collapse_spaced_caps(normalise(strip_ocr_debris(line.text)))
        if text:
            raw.append(PreparedLine(text, line.page, line.kind, line.table))
    joined: list[PreparedLine] = []
    for item in raw:
        prev = joined[-1] if joined else None
        if prev is not None and item.kind == prev.kind == "body" and item.table == prev.table:
            if (
                item.text.startswith("(")
                and _REFERENCE_END.search(prev.text)
                and not _HEADING_ONLY.match(prev.text)
            ):
                joined[-1] = PreparedLine(
                    f"{prev.text} {item.text}", prev.page, prev.kind, prev.table
                )
                continue
            if _HEADING_ONLY.match(prev.text) and _HEADING_TAIL.match(item.text):
                joined[-1] = PreparedLine(
                    f"{prev.text} {item.text}", prev.page, prev.kind, prev.table
                )
                continue
        joined.append(item)
    out: list[PreparedLine] = []
    for item in joined:
        if item.kind != "body":
            out.append(item)
            continue
        out.extend(
            PreparedLine(part, item.page, item.kind, item.table) for part in split_units(item.text)
        )
    return out


# ---------------------------------------------------------------------------------------------------------
# Tree building.

_ROMAN_UNITS = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
_CHAPTER = re.compile(r"^CHAPTER\s*[-:]?\s*([IVXLC]+)\s*-?\s*([A-Z]?)\b\.?\s*[-:]*\s*(.*)$")
_PART = re.compile(r"^PART\s*[-:]?\s*([IVX]+|[A-Z])\b\.?\s*[-:]*\s*([^a-z].*)?$")
_LETTER_PART = re.compile(r"^([A-Z])\s*\.\s*-+\s*(\S.*)$")
_SECTION = re.compile(r"^\[?\s*(\d{1,3})\s*-?\s*([A-Z]{0,3})\s*(?:\.(?!\d)|:(?=\s|$))\s*(.*)$")
_SUBSECTION = re.compile(r"^\[?\s*\((\d{1,3})([A-Z]{0,2})\)\s*(.*)$")
_ANNEX = re.compile(
    r"^\[?\s*((?:FORM|Form)\s+(?:No\.?\s*)?[A-Z][A-Z0-9]*(?:[ .-]+[A-Z0-9]+){0,3}|(?:ANNEXURE|Annexure|APPENDIX|Appendix)(?:[ -]+[A-Z0-9]+)?"
    r"|(?:THE\s+)?(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH)?\s*SCHEDULE(?:\s+[IVX]+)?)\s*\]?(?:\s+([A-Z(\[].*))?$"
)
_BLOCK_LABEL = re.compile(
    r"^(Subject|Sub|Ref|Reference|Read(?: the following)?|Copy forwarded to|Copy to|To)\s*[:.,-]*\s*(.*)$"
)
_CANONICAL_LABEL = {"Sub": "Subject", "Reference": "Ref", "Read the following": "Read"}
# CBIC prints amendment history in body-size type ("(2) Vide Notf no.94/2020 - CT ..."): a note, never structure.
_AMENDMENT_NOTE = re.compile(
    r"^(?:\[?\(?\d{0,3}[A-Z]?\)?\s*)?(?:Vide|Substituted|Inserted|Omitted|Added)\b.{0,80}?\b(?:Notf|Notification)",
    re.IGNORECASE,
)
_HEADING_SEPARATOR = re.compile(r"^(.{2,200}?)(?:\s*[.:]\s*-+|\s*-{2,}|\s*:-|\.-)\s*(.*)$")


def roman_value(numeral: str) -> int:
    total = 0
    for i, ch in enumerate(numeral):
        value = _ROMAN_UNITS[ch]
        total += -value if i + 1 < len(numeral) and _ROMAN_UNITS[numeral[i + 1]] > value else value
    return total


# Document-type captions printed above the text: not containers.
_NOT_BLOCKS = (
    "NOTIFICATION",
    "THE GAZETTE OF INDIA",
    "EXTRAORDINARY",
    "MINISTRY OF",
    "GOVERNMENT OF",
)


def _is_block_heading(text: str) -> bool:
    """A short unnumbered all-caps line ("NOTIFICATION", "ORDER:-", "AMENDMENT")."""
    bare = text.rstrip(":- ")
    return (
        not bare.startswith(_NOT_BLOCKS)
        and 3 <= len(bare) <= 40
        and bare.upper() == bare
        and any(ch.isalpha() for ch in bare)
        and not any(ch.isdigit() for ch in bare)
        and len(bare.split()) <= 4
    )


def _split_heading(rest: str) -> tuple[str, str]:
    """ "Formation of company.- (text)" -> ("Formation of company", "(text)"); no separator -> ("", rest)."""
    m = _HEADING_SEPARATOR.match(rest)
    if m and not m.group(1).startswith("("):
        return m.group(1).strip(" .:"), m.group(2).strip()
    return "", rest


class _Builder:
    def __init__(self, doc: ParsedDocument) -> None:
        self.doc = doc
        self.root = Node(kind="root", ident="")
        self.container: Node = self.root  # chapter, part, block or annex holding sections
        self.section: Node | None = None
        self.subsection: Node | None = None
        self.last_section: tuple[int, str] | None = None
        self.last_sub: tuple[int, str] | None = None
        self.pending_note: str | None = None
        self.chapter_needs_heading = False
        self.last_table: tuple[int, int] | None = None
        self.last_text: str | None = None  # text appended by the line being fed
        self.previous_text: str | None = None  # text appended by the line before it

    # -- helpers ------------------------------------------------------------------------------------------
    @property
    def current(self) -> Node:
        return self.subsection or self.section or self.container

    @property
    def in_annex(self) -> bool:
        node: Node | None = self.container
        while node is not None:
            if node.kind == "annex":
                return True
            node = node.parent
        return False

    def _text(self, text: str) -> None:
        self.current.content.append(text)
        self.last_text = text

    def _flush_note(self) -> None:
        if self.pending_note is not None:
            self._text(self.pending_note)
            self.pending_note = None

    def _open_container(self, node: Node, parent: Node) -> None:
        self.container = parent.add(node)
        self.section = self.subsection = None
        self.last_section = self.last_sub = None

    def _top_level_parent(self) -> Node:
        """Blocks and annexes hang off the root, or off the current chapter when there is one."""
        node: Node | None = self.container
        while node is not None and node.kind not in ("chapter", "root"):
            node = node.parent
        return node or self.root

    # -- line handlers ------------------------------------------------------------------------------------
    def feed(self, line: PreparedLine) -> None:
        self.previous_text, self.last_text = self.last_text, None
        if line.kind == "footnote":
            self.current.notes.append(line.text)
            return
        if line.kind == "note":
            self.pending_note = (
                f"{self.pending_note} {line.text}" if self.pending_note else line.text
            )
            return
        if line.table is not None:
            self._flush_note()
            key = (line.page, line.table)
            if key != self.last_table and self._annex(line.text, line.page, titled=True):
                self.last_table = None  # a form title printed in the table's first cell
            if key != self.last_table:
                table = self.doc.table_at(line.page, line.table)
                if table is not None:
                    self.current.content.append(TableBlock(table))
                self.last_table = key
            return
        self.last_table = None
        text = line.text
        if _AMENDMENT_NOTE.match(text):
            self.current.notes.append(text)
            return
        if self.chapter_needs_heading:
            self.chapter_needs_heading = False
            if not _SECTION.match(text) and not _CHAPTER.match(text) and text.upper() == text:
                self.container.heading = text.strip(" .")
                return
        for handler in (
            self._chapter,
            self._annex,
            self._part,
            self._block,
            self._section,
            self._subsection,
        ):
            if handler(text, line.page):
                return
        self._flush_note()
        self._text(text)

    def _chapter(self, text: str, page: int) -> bool:
        m = _CHAPTER.match(text)
        if not m:
            return False
        self._flush_note()
        ident = f"CHAPTER {m.group(1)}{m.group(2)}"
        self._open_container(
            Node(kind="chapter", ident=ident, heading=m.group(3).strip(" .-"), page=page), self.root
        )
        self.chapter_needs_heading = not m.group(3).strip()
        return True

    def _annex(self, text: str, page: int, *, titled: bool = False) -> bool:
        """A form, annexure or schedule heading on a line of its own; a title may follow it only in a table's
        first cell ("FORM NO. INC.1 Application for"), never in running text ("FORM GST REG-06 has been ...")."""
        m = _ANNEX.match(text)
        if not m or (m.group(2) and not titled):
            return False
        self._flush_note()
        ident = re.sub(r"\s+", " ", m.group(1)).strip(" .")
        ident = re.sub(r"^Form\b", "FORM", ident)
        heading = (m.group(2) or "").strip()
        self._open_container(
            Node(kind="annex", ident=ident, heading=heading, page=page), self._top_level_parent()
        )
        return True

    def _part(self, text: str, page: int) -> bool:
        if self.in_annex:
            return False
        if m := _PART.match(text):
            ident, heading = f"PART {m.group(1)}", m.group(2) or ""
        elif m := _LETTER_PART.match(text):
            ident, heading = m.group(1), m.group(2)
        else:
            return False
        if len(heading) > 120:
            return False
        self._flush_note()
        parent = self._top_level_parent()
        node = Node(kind="part", ident=ident, heading=heading.strip(" .-"), page=page)
        self.container = parent.add(node)
        self.subsection = self.section = (
            None  # sections continue their numbering across lettered parts
        )
        return True

    def _block(self, text: str, page: int) -> bool:
        if self.container.kind not in ("root", "block"):
            return False
        if m := _BLOCK_LABEL.match(text):
            label = _CANONICAL_LABEL.get(m.group(1), m.group(1))
            rest = m.group(2).strip()
            if label in ("To", "Copy to", "Copy forwarded to") and len(rest) > 60:
                return False
        elif _is_block_heading(text):
            label, rest = text.rstrip(":- ").strip(), ""
        else:
            return False
        self._flush_note()
        self._open_container(Node(kind="block", ident=label, page=page), self.root)
        if rest:
            self._text(rest)
        return True

    def _section(self, text: str, page: int) -> bool:
        if self.in_annex:
            return False
        m = _SECTION.match(text)
        if not m:
            return False
        number, suffix = int(m.group(1)), m.group(2)
        if self.last_section is not None:
            last_n, last_suffix = self.last_section
            if not (last_n < number <= last_n + 3 or (number == last_n and suffix > last_suffix)):
                return False
        heading, rest = _split_heading(m.group(3).strip())
        if not heading and self.pending_note is None:
            heading = self._take_side_heading()
        if self.pending_note is not None:
            heading, rest = (
                self.pending_note.strip(" .-"),
                m.group(3).strip() if not heading else rest,
            )
            self.pending_note = None
        node = Node(kind="section", ident=f"{number}{suffix}", heading=heading, page=page)
        self.section = self.container.add(node)
        self.subsection = None
        self.last_section, self.last_sub = (number, suffix), None
        if rest:
            self._text(rest)
        return True

    def _take_side_heading(self) -> str:
        """A side heading printed on its own full-width line just before an unheaded paragraph ("Exemption for the
        purpose of clause (viib) ..." above "4. A Startup shall ..."): short, capitalised, unpunctuated."""
        node = self.current
        last = node.content[-1] if node.content else None
        if (
            isinstance(last, str)
            and last is self.previous_text
            and 3 <= len(last) <= 140
            and last[0].isupper()
            and last[-1] not in ".:;,-)"
            and not _SECTION.match(last)
        ):
            node.content.pop()
            return last
        return ""

    def _subsection(self, text: str, page: int) -> bool:
        if self.in_annex:
            return False
        parent = self.section or (self.container if self.container.kind == "block" else None)
        if parent is None:
            return False
        m = _SUBSECTION.match(text)
        if not m:
            return False
        number, suffix = int(m.group(1)), m.group(2)
        if self.last_sub is None:
            if number > 2:
                return False
        else:
            last_n, last_suffix = self.last_sub
            if not (last_n < number <= last_n + 2 or (number == last_n and suffix > last_suffix)):
                return False
        self._flush_note()
        node = Node(kind="subsection", ident=f"({number}{suffix})", page=page)
        self.subsection = parent.add(node)
        self.last_sub = (number, suffix)
        node.content.append(text)
        return True


def build_tree(doc: ParsedDocument) -> Node:
    builder = _Builder(doc)
    for line in prepare_lines(doc):
        builder.feed(line)
    builder._flush_note()
    return builder.root
