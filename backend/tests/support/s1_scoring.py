"""Spike S1's scorer (docs/spikes/S1-parsing.md, "Metrics"), ported for the parser regression tests.

Scores the parser's prepared lines (`structure.prepare_lines`: normalised, wrapped references joined, inline
units split, Hindi lines and footnotes left out) against a gold outline: structure recall (gold identifiers
found at a line start, in order, within their page bounds), reading-order errors, and precision (matched over
matched + unexplained structure-looking lines that a monotone tree builder would accept). Also the
DocumentTree check: the share of gold identifier paths (to sub-section depth) that exist in the built tree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.modules.knowledge.parsing.model import ParsedDocument
from app.modules.knowledge.parsing.structure import Node, prepare_lines
from app.modules.knowledge.parsing.text import normalise

STRUCTURED_UNITS = ("section", "rule", "paragraph")
FORWARD_LIMIT = 2000
SECTION_START = re.compile(r"^\[?\s*(\d{1,3})[A-Z]{0,3}\s*\.(?!\d)")
STRUCTURAL = re.compile(r"^\[?\s*(\d{1,3}[A-Z]{0,2}\s*\.(?!\d)|\(\d{1,3}[A-Z]?\)|CHAPTER\b)")


@dataclass(frozen=True)
class LineScore:
    recall: float | None
    order_errors: int
    precision: float | None
    scorable: int


def anchor(segment: str) -> re.Pattern[str] | None:
    seg = re.sub(r"^p\d+ ", "", segment)
    if seg.startswith("¶") or seg.endswith("(hi)") or seg.endswith("(en)"):
        return None
    if m := re.fullmatch(r"CHAPTER ([IVXLC]+[A-Z]?)", seg):
        return re.compile(rf"^CHAPTER[\s-]*{m.group(1)}\b")
    if m := re.fullmatch(r"PART ([IVX]+|[A-Z])", seg):
        return re.compile(rf"^PART\s*{m.group(1)}\b")
    if re.fullmatch(r"\d{1,3}[A-Z]{0,3}", seg):
        return re.compile(rf"^\[?\s*{seg}\s*\.(?!\d)")
    if re.fullmatch(r"[A-Z]", seg):
        return re.compile(rf"^{seg}\s*\.\s*-")
    if m := re.fullmatch(r"\((\w{1,4})\)", seg):
        return re.compile(rf"^\[?\s*\({re.escape(m.group(1))}\)")
    if re.fullmatch(r"[ivx]{1,4}", seg):
        return re.compile(rf"^\(?{seg}[.)]")
    if seg in ("Proviso", "Second proviso"):
        return re.compile(r"^Provided")
    if seg == "Explanation":
        return re.compile(r"^Explanation")
    return re.compile(
        r"^\[?\s*" + r"\s*".join(re.escape(ch) for ch in normalise(seg).replace(" ", "")),
        re.IGNORECASE,
    )


def _bounds(outline: list[dict[str, Any]]) -> tuple[int, int] | None:
    nums = [
        int(m.group(1))
        for e in outline
        if (m := re.fullmatch(r"(\d{1,3})[A-Z]{0,3}", e["path"].split(" > ")[-1]))
    ]
    return (min(nums), max(nums)) if nums else None


def _plausible(text: str, bounds: tuple[int, int] | None) -> bool:
    m = SECTION_START.match(text)
    return bool(m) and (bounds is None or bounds[0] - 1 <= int(m.group(1)) <= bounds[1] + 1)


def _page_bounds(gold: dict[str, Any]) -> list[tuple[int, int]]:
    first, last = gold["window"]["pages"]
    outline = gold["outline"]
    out, prev = [], first
    for n, entry in enumerate(outline):
        if entry.get("page"):
            prev = entry["page"]
            out.append((prev, prev))
            continue
        nxt = next((e["page"] for e in outline[n + 1 :] if e.get("page")), last)
        out.append((prev, nxt))
    return out


def score_lines(doc: ParsedDocument, gold: dict[str, Any]) -> LineScore:
    lines = [
        (ln.page, ln.text) for ln in prepare_lines(doc, include_hindi=True) if ln.kind != "footnote"
    ]
    if stop := gold["window"].get("stop"):
        cut = next((i for i, (_, t) in enumerate(lines) if re.match(stop, t)), len(lines))
        lines = lines[:cut]
    texts = [t for _, t in lines]
    bounds = _bounds(gold["outline"])
    pages = _page_bounds(gold)
    pos, used = 0, set()
    matched = order_err = scorable = 0
    for n, entry in enumerate(gold["outline"]):
        lo_page, hi_page = pages[n]
        segment = entry["path"].split(" > ")[-1]
        pattern = anchor(segment)
        if pattern is None:
            continue
        scorable += 1
        sub = re.fullmatch(r"\(\w{1,4}\)", segment) is not None
        hit = None
        for i in range(pos, min(len(texts), pos + FORWARD_LIMIT)):
            if lines[i][0] > hi_page:
                break
            if i not in used and pattern.match(texts[i]) and lines[i][0] >= lo_page:
                hit = i
                break
            if sub and i > pos and _plausible(texts[i], bounds):
                break
        if hit is not None:
            matched += 1
            used.add(hit)
            pos = hit + 1
        elif any(pattern.match(t) for i, t in enumerate(texts) if i not in used):
            order_err += 1
    precision = None
    if str(gold["window"].get("unit", "")).split(";")[0].strip() in STRUCTURED_UNITS:
        lo = min(used) if used else 0
        hi = next(
            (
                i
                for i in range(max(used, default=0) + 1, len(texts))
                if (m := SECTION_START.match(texts[i])) and bounds and int(m.group(1)) > bounds[1]
            ),
            len(texts),
        )
        spurious, current = 0, None
        for i in range(lo, hi):
            m = SECTION_START.match(texts[i])
            if i in used:
                current = int(m.group(1)) if m else current
                continue
            if m:
                n_ = int(m.group(1))
                if _plausible(texts[i], bounds) and (
                    current is None or current <= n_ <= current + 1
                ):
                    spurious += 1
            elif STRUCTURAL.match(texts[i]):
                spurious += 1
        precision = matched / (matched + spurious) if matched + spurious else None
    return LineScore(matched / scorable if scorable else None, order_err, precision, scorable)


_ID = re.compile(
    r"^(CHAPTER [IVXLC]+[A-Z]?|PART \w+|[A-Z]|\d{1,3}[A-Z]{0,3}|\(\d{1,3}[A-Z]{0,2}\)|FORM .+)$"
)
_CLAUSE_TAIL = re.compile(r"\((?:[a-z]+|[ivx]+)\)$")


def _id_path(path: str) -> list[str]:
    return [s for s in path.split(" > ") if _ID.match(re.sub(r"^p\d+ ", "", s))]


def tree_recall(root: Node, gold: dict[str, Any]) -> tuple[int, int]:
    """(found, total) gold identifier paths to sub-section depth whose segments appear, in order, in a tree node path
    ending at the same identifier (extra tree levels such as "PART I" are allowed)."""
    mine = [_id_path(n.path) for n in root.walk() if n.kind != "root"]
    wanted = list(
        dict.fromkeys(
            " > ".join(p)
            for e in gold["outline"]
            if (p := _id_path(e["path"])) and not _CLAUSE_TAIL.search(p[-1])
        )
    )

    def found(path: str) -> bool:
        g = path.split(" > ")
        for node in mine:
            if node and node[-1] == g[-1]:
                it = iter(node[:-1])
                if all(seg in it for seg in g[:-1]):
                    return True
        return False

    return sum(found(p) for p in wanted), len(wanted)


def tree_precision(root: Node, gold: dict[str, Any]) -> tuple[int, int]:
    """(spurious, total) section and sub-section nodes whose identifier path is not in the gold outline (any depth).
    Form rows read as rules (S1: Accounts Rules, 74% line precision) show up here."""
    wanted = [_id_path(e["path"]) for e in gold["outline"]]
    bounds = _bounds(gold["outline"])

    def in_scope(node: Node) -> bool:
        number = next(
            (
                int(m.group(1))
                for s in _id_path(node.path)
                if (m := re.fullmatch(r"(\d{1,3})[A-Z]{0,3}", s))
            ),
            None,
        )
        return bounds is None or (number is not None and bounds[0] <= number <= bounds[1])

    nodes = [n for n in root.walk() if n.kind in ("section", "subsection") and in_scope(n)]

    def known(node: Node) -> bool:
        mine = _id_path(node.path)
        for g in wanted:
            if g and mine and g[-1] == mine[-1]:
                it = iter(mine[:-1])
                if all(seg in it for seg in g[:-1]):
                    return True
        return False

    return sum(not known(n) for n in nodes), len(nodes)
