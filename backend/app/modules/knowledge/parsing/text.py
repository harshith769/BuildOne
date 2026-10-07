"""Text normalisation shared by the parsers and the tree builder (S1 shared tree-builder rules)."""

from __future__ import annotations

import re
import unicodedata

# Stamp and handwriting debris before a scanned line ("~ Sub:«", "__Proc No.") — S1 mapping note 10.
_OCR_LEAD = re.compile(r"^[\s~_'\"=>\\*|.,:;`«»-]+(?=[\w\[(])")
_DASHES = re.compile("[\u2010\u2011\u2012\u2013\u2014\u2212]")  # hyphens, dashes, minus
_QUOTES = re.compile("[\u201c\u201d\u2033\u2036\u2017\u2015]")  # curly and look-alike double quotes
_SPACES = re.compile(r"\s+")


def strip_ocr_debris(text: str) -> str:
    return _OCR_LEAD.sub("", text).strip()


def normalise(text: str) -> str:
    """NFKC, one kind of dash and quote, single spaces. Applied to every line before structure is read."""
    text = unicodedata.normalize("NFKC", text)
    text = _DASHES.sub("-", text)
    text = (
        _QUOTES.sub('"', text)
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u2016", '"')  # CBIC prints ‖ as a closing quote
        .replace("\u201f", '"')
    )
    return _SPACES.sub(" ", text).strip()
