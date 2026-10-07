"""Official HTML parser: the standard library's `html.parser` (S1 decision; data-pipeline.md §1).

Block elements end a line; `<ol>` items get their rendered marker ("(1)", "(a)", "(i)") because the sub-section
numbers often exist only as list markup (S1 mapping note 8). Layout tables are containers: each cell's text is
just more lines. An `html_bundle` is a zip of `index.html` plus one page per section, where the index is the only
place a section number is printed (the Telangana PT Act): the number is prefixed to the section page's first
line. An "Arrangement of Sections" table of contents is dropped.
"""

from __future__ import annotations

import io
import re
import zipfile
from html.parser import HTMLParser

from app.modules.knowledge.parsing.devanagari import is_hindi_line
from app.modules.knowledge.parsing.model import Line, Page, ParsedDocument

PARSER_NAME = "stdlib-html"
PARSER_VERSION = "1"

_ROMAN = [
    "i",
    "ii",
    "iii",
    "iv",
    "v",
    "vi",
    "vii",
    "viii",
    "ix",
    "x",
    "xi",
    "xii",
    "xiii",
    "xiv",
    "xv",
]
_SKIP = {"script", "style", "head", "title"}
_BLOCK = {
    "p",
    "div",
    "br",
    "tr",
    "center",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "ol",
    "ul",
    "span",
}
_INDEX_ROW = re.compile(
    r"<td[^>]*>\s*(\d+[A-Z]?)\.+\s*</td>\s*<td[^>]*>\s*<a[^>]*href=\"(?:[^\"]*/)?([^\"/]+)\"",
    re.IGNORECASE,
)


class _Renderer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.lists: list[list[object]] = []  # [type, counter]
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self.skip += 1
        if tag == "ol":
            self.lists.append([dict(attrs).get("type") or "1", 0])
        if tag == "li":
            self.out.append("\n")
            if self.lists:
                kind, n = str(self.lists[-1][0]), int(self.lists[-1][1]) + 1  # type: ignore[call-overload]
                self.lists[-1][1] = n
                marker = {
                    "1": str(n),
                    "a": chr(96 + n),
                    "A": chr(64 + n),
                    "i": _ROMAN[n - 1] if n <= len(_ROMAN) else str(n),
                }.get(kind, str(n))
                self.out.append(f"({marker}) ")
        elif tag in _BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self.skip -= 1
        if tag == "ol" and self.lists:
            self.lists.pop()
        if tag in _BLOCK or tag == "li":
            self.out.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.out.append(re.sub(r"\s+", " ", data))


def decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def html_lines(markup: str) -> list[str]:
    renderer = _Renderer()
    renderer.feed(markup)
    return [" ".join(ln.split()) for ln in "".join(renderer.out).splitlines() if ln.strip()]


def drop_toc(lines: list[str]) -> list[str]:
    """Drop an "ARRANGEMENT OF SECTIONS" block up to the body's first CHAPTER line followed by section 1."""
    start = next(
        (i for i, ln in enumerate(lines) if ln.upper().startswith("ARRANGEMENT OF SECTIONS")), None
    )
    if start is None:
        return lines
    for j in range(start + 1, len(lines)):
        if lines[j].upper().startswith("CHAPTER") and any(
            re.match(r"^1\.\s", ln) for ln in lines[j + 1 : j + 4]
        ):
            return lines[:start] + lines[j:]
    return lines


def _bundle_lines(data: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        names = set(bundle.namelist())
        index = decode(bundle.read("index.html"))
        lines: list[str] = []
        for number, name in _INDEX_ROW.findall(index):
            if name not in names:
                continue
            got = drop_toc(html_lines(decode(bundle.read(name))))
            if got:
                got[0] = f"{number}. {got[0]}"
            lines.extend(got)
        return lines


def parse_html(data: bytes, *, bundle: bool = False) -> ParsedDocument:
    texts = _bundle_lines(data) if bundle else drop_toc(html_lines(decode(data)))
    lines = [Line(text=t, page=1, lang="hi" if is_hindi_line(t) else "en") for t in texts]
    return ParsedDocument(
        parser=f"{PARSER_NAME}@{PARSER_VERSION}", pages=[Page(number=1, source="html", lines=lines)]
    )
