"""Shared helpers for the knowledge tests: fixture corpus access and tiny synthetic documents."""

from __future__ import annotations

import os
import shutil
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.modules.knowledge.parsing import parse
from app.modules.knowledge.parsing.model import Line, Page, ParsedDocument
from app.modules.knowledge.registry import load_registry

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "knowledge"

# Tesseract is installed in CI (apt) and on the ingestion laptop; elsewhere OCR tests skip, never in CI.
requires_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None and not os.environ.get("CI"), reason="tesseract not installed"
)


@cache
def manifest() -> list[dict[str, Any]]:
    return list(yaml.safe_load((FIXTURES / "fixtures.yaml").read_text(encoding="utf-8")))


@cache
def parsed_fixture(key: str) -> ParsedDocument:
    entry = next(m for m in manifest() if m["key"] == key)
    registry = load_registry()
    bilingual = entry.get("bilingual", registry[key].bilingual if key in registry else False)
    return parse(
        (FIXTURES / entry["file"]).read_bytes(), format=entry["format"], bilingual=bilingual
    )


@cache
def gold(key: str) -> dict[str, Any]:
    return dict(yaml.safe_load((FIXTURES / "gold" / f"{key}.yaml").read_text(encoding="utf-8")))


def document(*lines: str | Line, page: int = 1) -> ParsedDocument:
    """A one-page text-layer document from plain strings (body lines) or ready-made Lines."""
    built = [ln if isinstance(ln, Line) else Line(text=ln, page=page) for ln in lines]
    return ParsedDocument(parser="test@1", pages=[Page(number=page, source="text", lines=built)])


def words(text: str) -> int:
    """Whitespace token counter for chunking tests (the real one is the bge tokenizer)."""
    return len(text.split())


def word_offsets(text: str) -> list[tuple[int, int]]:
    out, pos = [], 0
    for w in text.split():
        start = text.index(w, pos)
        out.append((start, start + len(w)))
        pos = start + len(w)
    return out
