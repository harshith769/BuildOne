"""Official source registry: `knowledge/sources.yaml` (data-pipeline.md §3).

Only government sources are registered for citations. Each entry says where the file comes from: a direct
`download_url`, or `manual` instructions when the site blocks scripts (the file is then dropped into
`knowledge/inbox/<key>.<ext>` by hand). The registry holds metadata only; regulatory facts never live here.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REGISTRY = REPO_ROOT / "knowledge" / "sources.yaml"

# Government domains accepted as official (NIC-hosted and *.gov.in sites).
OFFICIAL_SUFFIXES = (".gov.in", ".nic.in")

Jurisdiction = Literal["IN", "IN-TG"]
DocType = Literal["act", "rules", "notification", "circular", "form_instructions", "guidance"]
SourceFormat = Literal["pdf", "html", "html_bundle"]


def is_official_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return urlparse(url).scheme == "https" and any(
        host == s[1:] or host.endswith(s) for s in OFFICIAL_SUFFIXES
    )


class Source(BaseModel):
    """One registered source. `bilingual` means OCR uses `eng+hin`; `scanned` means review is expected."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{2,62}$")
    title: str = Field(min_length=3)
    authority: str = Field(min_length=2)
    jurisdiction: Jurisdiction
    doc_type: DocType
    official_url: str
    download_url: str | None = None
    manual: str | None = None
    format: SourceFormat = "pdf"
    bilingual: bool = False
    scanned: bool = False
    effective_from: dt.date
    effective_to: dt.date | None = None
    published_on: dt.date | None = None
    notes: str = ""

    @field_validator("official_url", "download_url")
    @classmethod
    def _official(cls, value: str | None) -> str | None:
        if value is not None and not is_official_url(value):
            raise ValueError(f"not an official government https URL: {value}")
        return value

    @model_validator(mode="after")
    def _origin(self) -> Source:
        if not (self.download_url or self.manual):
            raise ValueError(f"{self.key}: needs download_url or manual instructions")
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError(f"{self.key}: effective_to must be after effective_from")
        return self

    @property
    def extension(self) -> str:
        return {"pdf": "pdf", "html": "htm", "html_bundle": "zip"}[self.format]


def _normalise(value: object) -> object:
    """PyYAML turns ISO dates into `date` objects already; leave them, but reject datetimes."""
    if isinstance(value, dt.datetime):
        raise ValueError("registry dates must be plain dates, not datetimes")
    return value


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Source]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected a list of sources")
    sources: dict[str, Source] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: every source must be a mapping")
        source = Source.model_validate({k: _normalise(v) for k, v in entry.items()})
        if source.key in sources:
            raise ValueError(f"{path}: duplicate key {source.key}")
        sources[source.key] = source
    return sources
