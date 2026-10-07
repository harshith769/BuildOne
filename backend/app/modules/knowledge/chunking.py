"""Chunking policy (data-pipeline.md §4; frozen defaults, tunable only via evaluation).

1. A leaf (sub-section, or a section/paragraph/annex without sub-sections) is one chunk if <= 500 tokens.
2. Longer leaves split at line boundaries into 350-500-token chunks with a 50-token overlap; the pieces share
   the leaf's `section_path` and carry consecutive ordinals.
3. Consecutive sibling units under 80 tokens are merged (up to 500 tokens); `node_paths` lists every node covered.
4. Tables stay whole (rows as `cell | cell` lines); a table over 800 tokens splits by row groups, header repeated.
5. Every node with children also gets a parent chunk (heading + first 200 tokens), for context, never ranked.
6. Embedded text = `<title> > <section_path>` + "\n" + heading + "\n" + text.
A node's own text before its first child (a section's lead-in, a block's paragraph) is a unit of its own,
sibling to its children, so rule 3 usually merges it with the first sub-section.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from app.modules.knowledge.parsing.model import Table
from app.modules.knowledge.parsing.structure import Node, TableBlock

ChunkKind = Literal["section", "annex", "table", "parent"]
MAX_TOKENS, MIN_SPLIT, OVERLAP, SMALL = 500, 350, 50, 80
TABLE_MAX, PARENT_TOKENS = 800, 200

TokenCounter = Callable[[str], int]


@dataclass(slots=True)
class ChunkDraft:
    section_path: str  # without the source title
    heading: str
    ordinal: int
    text: str
    token_count: int
    kind: ChunkKind
    node_paths: list[str] = field(default_factory=list)
    parent_path: str | None = None  # path of the parent chunk (a node with children), if any

    def embed_text(self, title: str) -> str:
        path = f"{title} > {self.section_path}" if self.section_path else title
        return f"{path}\n{self.heading}\n{self.text}"


@dataclass(slots=True)
class _Unit:
    path: str
    group: str  # units with the same group are siblings (rule 3)
    heading: str
    kind: ChunkKind
    content: list[str | TableBlock]
    parent_path: str | None


def render_table(table: Table) -> list[str]:
    """One line per row, empty cells left out (merged cells repeat as empty strings)."""
    return [" | ".join(c.replace("\n", " ") for c in row if c) for row in table.rows if any(row)]


def _heading(node: Node) -> str:
    current: Node | None = node
    while current is not None:
        if current.heading:
            return current.heading
        current = current.parent
    return ""


def _units(root: Node) -> list[_Unit]:
    units: list[_Unit] = []

    def visit(node: Node, parent_chunk: str | None) -> None:
        kind: ChunkKind = "annex" if node.kind == "annex" or _in_annex(node) else "section"
        if node.children:
            if node.content:
                units.append(
                    _Unit(
                        node.path, node.path, _heading(node), kind, node.content, node.path or None
                    )
                )
            child_parent = node.path if node.kind != "root" else parent_chunk
            for child in node.children:
                visit(child, child_parent)
        elif node.content or node.kind != "root":
            group = node.parent.path if node.parent is not None else ""
            units.append(_Unit(node.path, group, _heading(node), kind, node.content, parent_chunk))

    visit(root, None)
    return [u for u in units if u.content]


def _in_annex(node: Node) -> bool:
    current = node.parent
    while current is not None:
        if current.kind == "annex":
            return True
        current = current.parent
    return False


def _split_text(
    lines: list[str], count: TokenCounter, offsets: Callable[[str], list[tuple[int, int]]]
) -> list[str]:
    """Rule 2: 350-500-token pieces at line boundaries, ~50 tokens of overlap; over-long lines are cut."""
    parts: list[str] = []
    for line in lines:
        if count(line) <= MAX_TOKENS:
            parts.append(line)
            continue
        offs = offsets(line)
        for start in range(0, len(offs), MAX_TOKENS - OVERLAP):
            seg = offs[start : start + MAX_TOKENS - OVERLAP]
            parts.append(line[seg[0][0] : seg[-1][1]])
    pieces: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0
    for part in parts:
        tokens = count(part)
        if current and current_tokens + tokens > MAX_TOKENS and current_tokens >= MIN_SPLIT // 2:
            pieces.append(current)
            tail: list[str] = []
            tail_tokens = 0
            for prev in reversed(current):
                tail_tokens += count(prev)
                if tail_tokens > OVERLAP:
                    break
                tail.insert(0, prev)
            current, current_tokens = tail, sum(count(x) for x in tail)
        current.append(part)
        current_tokens += tokens
    if current:
        pieces.append(current)
    return [" ".join(p) for p in pieces]


def _split_table(table: Table, count: TokenCounter) -> list[str]:
    rows = render_table(table)
    whole = "\n".join(rows)
    if count(whole) <= TABLE_MAX or len(rows) < 2:
        return [whole] if whole else []
    header, body = rows[0], rows[1:]
    pieces: list[str] = []
    group: list[str] = []
    for row in body:
        if group and count("\n".join([header, *group, row])) > MAX_TOKENS:
            pieces.append("\n".join([header, *group]))
            group = []
        group.append(row)
    if group:
        pieces.append("\n".join([header, *group]))
    return pieces


def build_chunks(
    root: Node, count: TokenCounter, offsets: Callable[[str], list[tuple[int, int]]]
) -> list[ChunkDraft]:
    units = _units(root)
    texts = [" ".join(c for c in u.content if isinstance(c, str)) for u in units]
    has_table = [any(isinstance(c, TableBlock) for c in u.content) for u in units]
    sizes = [
        count(
            " ".join(
                c if isinstance(c, str) else "\n".join(render_table(c.table)) for c in u.content
            )
        )
        for u in units
    ]
    chunks: list[ChunkDraft] = []
    i = 0
    while i < len(units):
        unit = units[i]
        # Rule 3: merge a run of small sibling units without tables.
        if sizes[i] < SMALL and not has_table[i]:
            j, total = i + 1, sizes[i]
            while (
                j < len(units)
                and units[j].group == unit.group
                and sizes[j] < SMALL
                and not has_table[j]
                and total + sizes[j] <= MAX_TOKENS
            ):
                total += sizes[j]
                j += 1
            if j > i + 1:
                text = " ".join(texts[i:j])
                chunks.append(
                    ChunkDraft(
                        unit.path,
                        unit.heading,
                        0,
                        text,
                        count(text),
                        unit.kind,
                        [u.path for u in units[i:j]],
                        unit.parent_path,
                    )
                )
                i = j
                continue
        chunks.extend(_unit_chunks(unit, texts[i], sizes[i], count, offsets))
        i += 1
    return [c for c in chunks if c.token_count > 0] + _parent_chunks(root, count, offsets)


def _unit_chunks(
    unit: _Unit,
    text: str,
    size: int,
    count: TokenCounter,
    offsets: Callable[[str], list[tuple[int, int]]],
) -> list[ChunkDraft]:
    def draft(ordinal: int, body: str, kind: ChunkKind) -> ChunkDraft:
        return ChunkDraft(
            unit.path, unit.heading, ordinal, body, count(body), kind, [unit.path], unit.parent_path
        )

    if size <= MAX_TOKENS:
        body = " ".join(
            c if isinstance(c, str) else "\n" + "\n".join(render_table(c.table)) + "\n"
            for c in unit.content
        ).strip()
        return [draft(0, body, unit.kind)]
    out: list[ChunkDraft] = []
    run: list[str] = []
    for item in [*unit.content, None]:
        if isinstance(item, str):
            run.append(item)
            continue
        if run:
            out.extend(
                draft(len(out), piece, unit.kind) for piece in _split_text(run, count, offsets)
            )
            run = []
        if isinstance(item, TableBlock):
            out.extend(draft(len(out), piece, "table") for piece in _split_table(item.table, count))
    for ordinal, chunk in enumerate(out):
        chunk.ordinal = ordinal
    return out


def _parent_chunks(
    root: Node, count: TokenCounter, offsets: Callable[[str], list[tuple[int, int]]]
) -> list[ChunkDraft]:
    out: list[ChunkDraft] = []
    for node in root.walk():
        if node.kind == "root" or not node.children:
            continue
        words: list[str] = []
        for item in node.walk():
            words.extend(c for c in item.content if isinstance(c, str))
            if count(" ".join(words)) > PARENT_TOKENS:
                break
        text = " ".join(words)
        offs = offsets(text)
        if len(offs) > PARENT_TOKENS:
            text = text[: offs[PARENT_TOKENS - 1][1]]
        text = f"{node.heading}\n{text}".strip() if node.heading else text
        if not text:
            continue
        parent = (
            node.parent.path if node.parent is not None and node.parent.kind != "root" else None
        )
        out.append(
            ChunkDraft(
                node.path, _heading(node), 0, text, count(text), "parent", [node.path], parent
            )
        )
    return out
