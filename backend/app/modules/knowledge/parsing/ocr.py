"""Tesseract OCR for pages without a usable text layer (S1 decision; data-pipeline.md §1, §7).

The page is rendered at 300 dpi in grey and passed to the `tesseract` CLI (Tesseract 5, `eng`, or `eng+hin`
for bilingual sources). Word confidences come from the TSV output: the page's mean decides review, and each
line keeps its own mean for the ingestion report. Runs only in the ingestion CLI (laptop or CI), never on the
server.
"""

from __future__ import annotations

import csv
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

import pymupdf

from app.modules.knowledge.parsing.devanagari import is_hindi_line
from app.modules.knowledge.parsing.model import Line, Page
from app.modules.knowledge.parsing.text import strip_ocr_debris

OCR_DPI = 300


class OcrUnavailableError(RuntimeError):
    """The tesseract binary (or a language pack) is missing."""


def tesseract_version() -> str:
    exe = shutil.which("tesseract")
    if exe is None:
        raise OcrUnavailableError(
            "tesseract is not installed (apt install tesseract-ocr tesseract-ocr-hin)"
        )
    out = subprocess.run([exe, "--version"], capture_output=True, text=True, check=True)  # noqa: S603
    return out.stdout.split()[1] if out.stdout else "unknown"


def ocr_page(page: pymupdf.Page, number: int, *, bilingual: bool) -> Page:
    exe = shutil.which("tesseract")
    if exe is None:
        raise OcrUnavailableError(
            "tesseract is not installed (apt install tesseract-ocr tesseract-ocr-hin)"
        )
    lang = "eng+hin" if bilingual else "eng"
    pix = page.get_pixmap(dpi=OCR_DPI, colorspace=pymupdf.csGRAY)
    with tempfile.TemporaryDirectory() as tmp:
        image = Path(tmp) / "page.png"
        pix.save(str(image))
        result = subprocess.run(  # noqa: S603 - fixed binary, arguments built here
            [exe, str(image), "stdout", "-l", lang, "--psm", "3", "tsv"],
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        raise OcrUnavailableError(f"tesseract failed ({lang}): {result.stderr.strip()[:200]}")
    return _page_from_tsv(result.stdout, number)


def _page_from_tsv(tsv: str, number: int) -> Page:
    words: dict[tuple[int, int, int], list[tuple[str, float]]] = {}
    tops: dict[tuple[int, int, int], float] = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if row["level"] != "5" or not (row["text"] or "").strip():
            continue
        key = (int(row["block_num"]), int(row["par_num"]), int(row["line_num"]))
        words.setdefault(key, []).append((row["text"], float(row["conf"])))
        tops.setdefault(key, int(row["top"]) * 72 / OCR_DPI)
    lines: list[Line] = []
    confidences: list[float] = []
    for key, ws in sorted(words.items()):
        text = strip_ocr_debris(" ".join(w for w, _ in ws))
        confs = [c for _, c in ws if c >= 0]
        confidences.extend(confs)
        if not text:
            continue
        lines.append(
            Line(
                text=text,
                page=number,
                lang="hi" if is_hindi_line(text) else "en",
                confidence=sum(confs) / len(confs) if confs else None,
                top=tops[key],
            )
        )
    mean = sum(confidences) / len(confidences) if confidences else None
    return Page(number=number, source="ocr", lines=lines, confidence=mean)
