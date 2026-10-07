"""Rebuild the knowledge fixtures from the S1 corpus (maintainer-only; needs the local, gitignored spikes/s1).

For each S1 source with a gold outline: keep only the gold window pages (re-based to page 1), redact signature
images, copy the gold outline with page numbers re-based, and record provenance in SOURCES.md. Signed scans and
image letters are excluded (no personal names or signatures in fixtures, AGENTS.md rule 16); the OCR path is
tested on public Gazette and Act pages rasterised without their text layer instead.

Usage (from backend/): uv run python tests/fixtures/knowledge/build.py
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import pymupdf
import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
S1 = REPO / "spikes" / "s1"
REGISTRY = REPO / "knowledge" / "sources.yaml"

# Scans and image letters carrying officers' signatures: not committed (owner, M5 plan).
EXCLUDED = {
    "ts_shops_holidays_2021_scan": "phone scan with signatures and stamps",
    "ts_shops_registration_memo_2019_scan": "scan with a signature",
    "epfo_circular": "scan with a signature",
    "cbdt_circular": "image page with signatures",
}
# Signature images on otherwise born-digital pages: (key, page in the original, text the signature sits between).
REDACT = {"mca_general_circular": (1, "Yours faithfully", "Nupur")}
# Rasterised public pages (no text layer) for the OCR path: (name, key, original page, bilingual).
RASTER = [
    ("ocr_companies_act_p24", "companies_act_2013", 24, False),
    ("ocr_epf_scheme_p66", "epf_scheme_2026", 66, True),
]


def rebase_gold(gold: dict, first: int) -> dict:
    gold = dict(gold)
    lo, hi = gold["window"]["pages"]
    gold["window"] = {**gold["window"], "pages": [lo - first + 1, hi - first + 1]}
    gold["outline"] = [
        {**e, "page": e["page"] - first + 1} if e.get("page") else dict(e) for e in gold["outline"]
    ]
    if gold.get("tables"):
        gold["tables"] = [{**t, "page": t["page"] - first + 1} for t in gold["tables"]]
    return gold


def redact_signature(doc: pymupdf.Document, page_no: int, above: str, below: str) -> None:
    page = doc[page_no]
    top = page.search_for(above)[0].y1
    bottom = page.search_for(below)[0].y0
    rect = pymupdf.Rect(page.rect.width * 0.55, top, page.rect.width, bottom)
    page.add_redact_annot(rect, fill=(1, 1, 1))
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS, text=pymupdf.PDF_REDACT_TEXT_NONE)


def main() -> None:
    registry = {s["key"]: s for s in yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))}
    out_files, out_gold = HERE / "files", HERE / "gold"
    for d in (out_files, out_gold):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir()
    rows, manifest = [], []
    for gold_path in sorted((S1 / "gold").glob("*.yaml")):
        gold = yaml.safe_load(gold_path.read_text(encoding="utf-8"))
        key = gold["source"]
        if key in EXCLUDED:
            continue
        src = registry[key]
        first, last = gold["window"]["pages"]
        if (S1 / "data" / f"{key}.pdf").exists():
            doc = pymupdf.open(S1 / "data" / f"{key}.pdf")
            doc.select(list(range(first - 1, last)))
            if key in REDACT:
                page, above, below = REDACT[key]
                redact_signature(doc, page - first, above, below)
            doc.rewrite_images(dpi_threshold=160, dpi_target=150, quality=70)
            target = out_files / f"{key}.pdf"
            doc.save(target, garbage=4, deflate=True, clean=True)
            fmt = "pdf"
        elif (S1 / "data" / f"{key}.htm").exists():
            target = out_files / f"{key}.htm"
            shutil.copy(S1 / "data" / f"{key}.htm", target)
            first, fmt = 1, "html"
        else:
            target = out_files / f"{key}.zip"
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
                for f in sorted((S1 / "data" / key).iterdir()):
                    z.write(f, f.name)
            first, fmt = 1, "html_bundle"
        (out_gold / f"{key}.yaml").write_text(
            yaml.safe_dump(rebase_gold(gold, first), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        for extra in sorted((S1 / "gold").glob(f"{key}.*.txt")):
            shutil.copy(extra, out_gold / extra.name)
        window = (
            f"pp. {gold['window']['pages'][0]}-{gold['window']['pages'][1]}"
            if fmt == "pdf"
            else "whole"
        )
        manifest.append({"key": key, "file": f"files/{target.name}", "format": fmt})
        url = src.get("download_url") or src["official_url"]
        note = " Signature image redacted." if key in REDACT else ""
        rows.append(
            f"| `{target.name}` | {src['title']} | {src['authority']} | {url} | "
            f"{src.get('published_on') or src['effective_from']} | {window}{note} |"
        )
    for name, key, page_no, bilingual in RASTER:
        doc = pymupdf.open(S1 / "data" / f"{key}.pdf")
        pix = doc[page_no - 1].get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
        image_doc = pymupdf.open()
        page = image_doc.new_page(
            width=doc[page_no - 1].rect.width, height=doc[page_no - 1].rect.height
        )
        page.insert_image(page.rect, pixmap=pix)
        target = out_files / f"{name}.pdf"
        image_doc.save(target, garbage=4, deflate=True)
        # Reference text for the CER check: the same page's publisher text layer.
        (out_gold / f"{name}.ref.txt").write_text(
            doc[page_no - 1].get_text(sort=True), encoding="utf-8"
        )
        manifest.append(
            {
                "key": name,
                "file": f"files/{target.name}",
                "format": "pdf",
                "raster_of": key,
                "bilingual": bilingual,
            }
        )
        src = registry[key]
        rows.append(
            f"| `{target.name}` | {src['title']}, p. {page_no} rasterised at 300 dpi (no text layer) | "
            f"{src['authority']} | {src.get('download_url') or src['official_url']} | "
            f"{src.get('published_on') or src['effective_from']} | p. {page_no} |"
        )
    (HERE / "fixtures.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    excluded = "\n".join(f"- `{k}`: {why}." for k, why in EXCLUDED.items())
    (HERE / "SOURCES.md").write_text(
        "# Knowledge fixtures: provenance\n\n"
        "Public official documents only, trimmed to the spike S1 gold windows ([S1 report]"
        "(../../../../docs/spikes/S1-parsing.md)). Rebuilt by `build.py` from the local S1 corpus. "
        "Used by the parser regression tests and the CI retrieval gate (`make eval-retrieval`).\n\n"
        "| File | Title | Issuing authority | Official URL | Date | Pages kept (of the original) |\n"
        "|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n\n"
        "**Excluded** (personal names or signatures; AGENTS.md rule 16):\n" + excluded + "\n\n"
        "Printed names of signing officers in born-digital Gazette notifications and circulars are kept as "
        "published; signature images are redacted.\n",
        encoding="utf-8",
    )
    total = sum(f.stat().st_size for f in out_files.iterdir())
    print(f"{len(manifest)} fixtures, {total / 1e6:.1f} MB")  # noqa: T201


if __name__ == "__main__":
    main()
