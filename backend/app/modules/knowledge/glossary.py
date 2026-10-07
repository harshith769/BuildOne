"""Query abbreviation expansion (ADR-0014; data-pipeline.md §6 step 0).

Founders write "TCS", "PT", "MoA"; statutes write the words out. The first occurrence of each abbreviation in
`knowledge/query-glossary.yaml` (versioned; whole word, case-sensitive) gets its expansion appended in brackets:
"When does TCS apply" -> "When does TCS (tax collected at source, collection of tax at source) apply".
Deterministic, no AI: works with AI down (AGENTS.md rule 5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.modules.knowledge.registry import REPO_ROOT

DEFAULT_GLOSSARY = REPO_ROOT / "knowledge" / "query-glossary.yaml"


@dataclass(frozen=True)
class Glossary:
    version: int
    terms: dict[str, str]

    @property
    def _pattern(self) -> re.Pattern[str]:
        return _compile(tuple(sorted(self.terms, key=len, reverse=True)))

    def expand(self, question: str) -> str:
        seen: set[str] = set()

        def sub(m: re.Match[str]) -> str:
            abbr = m.group(1)
            if abbr in seen:
                return abbr
            seen.add(abbr)
            return f"{abbr} ({self.terms[abbr]})"

        return self._pattern.sub(sub, question) if self.terms else question


@lru_cache(maxsize=8)
def _compile(terms: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"\b(" + "|".join(map(re.escape, terms)) + r")\b")


@lru_cache(maxsize=4)
def load_glossary(path: Path = DEFAULT_GLOSSARY) -> Glossary:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    terms = data.get("terms") or {}
    if not isinstance(terms, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in terms.items()
    ):
        raise ValueError(f"{path}: terms must map abbreviations to expansions")
    return Glossary(version=int(data["version"]), terms=dict(terms))
