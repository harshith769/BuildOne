"""Knowledge service: the public interface other modules call (architecture.md §3).

`search()` implements the retrieval algorithm (data-pipeline.md §6, as changed by ADR-0014):
0. expand abbreviations from the versioned glossary;  1. filter (active, jurisdiction, as_of, doc types);
2. lexical list: off in the MVP;  3. vector: cosine on HNSW (`ef_search = 64`), top 50;  4. keep the top 20;
5. no reranker;  6. select the top 5 and add each one's parent chunk while the total stays <= 3,000 tokens;
7. confidence is not gated in the MVP (deferred.md §13).
`get_chunks()` resolves chunk ids of any version, superseded ones included, so citations keep working.
The query vector comes from the embedder sidecar; this module never loads a model.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.modules.knowledge.glossary import load_glossary

VECTOR_CANDIDATES = 50
KEEP = 20
SELECT_TOP = 5
CONTEXT_TOKEN_BUDGET = 3000
EF_SEARCH = 64


class QueryEmbedder(Protocol):
    async def embed_query(self, text: str) -> tuple[str, list[float]]:
        """(model_id, vector) for an already expanded question."""
        ...


@dataclass(frozen=True)
class SearchFilters:
    as_of: date
    jurisdictions: Sequence[str] = ("IN", "IN-TG")
    doc_types: Sequence[str] | None = None


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    source_key: str
    source_title: str
    official_url: str
    section_path: str  # "<title> > <path>"
    heading: str
    text: str
    score: float  # cosine similarity
    ordinal: int
    node_paths: tuple[str, ...]
    parent_id: uuid.UUID | None
    token_count: int


@dataclass(frozen=True)
class SearchResult:
    expanded_query: str
    glossary_version: int
    ranked: list[RetrievedChunk]  # top 20 by cosine
    selected: list[RetrievedChunk]  # top 5
    context: list[RetrievedChunk]  # parent chunks added for context (never ranked)


_RANK_SQL = text(
    """
    SELECT
    c.id, s.key AS source_key, s.title AS source_title, s.official_url, c.section_path, c.heading, c.text,
    c.ordinal, c.node_paths, c.parent_id, c.token_count, 1 - (e.embedding <=> CAST(:vector AS vector)) AS score
    FROM knowledge.chunk_embeddings e
    JOIN knowledge.chunks c ON c.id = e.chunk_id
    JOIN knowledge.source_versions v ON v.id = c.source_version_id
    JOIN knowledge.sources s ON s.id = v.source_id
    WHERE e.model_id = :model_id
      AND c.is_active
      AND c.kind <> 'parent'
      AND c.jurisdiction = ANY(:jurisdictions)
      AND c.effective_from <= :as_of
      AND (c.effective_to IS NULL OR c.effective_to > :as_of)
      AND (CAST(:doc_types AS text[]) IS NULL OR c.doc_type = ANY(CAST(:doc_types AS text[])))
    ORDER BY e.embedding <=> CAST(:vector AS vector)
    LIMIT :limit
    """
)

_BY_ID_SQL = text(
    """
    SELECT
    c.id, s.key AS source_key, s.title AS source_title, s.official_url, c.section_path, c.heading, c.text,
    c.ordinal, c.node_paths, c.parent_id, c.token_count, 0.0 AS score
    FROM knowledge.chunks c
    JOIN knowledge.source_versions v ON v.id = c.source_version_id
    JOIN knowledge.sources s ON s.id = v.source_id
    WHERE c.id IN :ids
    """
).bindparams(bindparam("ids", expanding=True))


def _row(row: object) -> RetrievedChunk:
    m = row._mapping  # type: ignore[attr-defined]
    path = f"{m['source_title']} > {m['section_path']}" if m["section_path"] else m["source_title"]
    return RetrievedChunk(
        chunk_id=m["id"],
        source_key=m["source_key"],
        source_title=m["source_title"],
        official_url=m["official_url"],
        section_path=path,
        heading=m["heading"],
        text=m["text"],
        score=float(m["score"]),
        ordinal=m["ordinal"],
        node_paths=tuple(m["node_paths"]),
        parent_id=m["parent_id"],
        token_count=m["token_count"],
    )


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"


async def rank(
    conn: AsyncConnection, vector: Sequence[float], model_id: str, filters: SearchFilters
) -> list[RetrievedChunk]:
    """Steps 1-4: the top 20 active chunks by cosine similarity. Runs in the caller's transaction."""
    await conn.execute(text(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}"))
    # Filters (inactive versions, dates) are applied after the index scan: keep scanning until enough rows pass.
    await conn.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    result = await conn.execute(
        _RANK_SQL,
        {
            "vector": _vector_literal(vector),
            "model_id": model_id,
            "jurisdictions": list(filters.jurisdictions),
            "as_of": filters.as_of,
            "doc_types": list(filters.doc_types) if filters.doc_types else None,
            "limit": VECTOR_CANDIDATES,
        },
    )
    rows = [_row(r) for r in result]
    rows.sort(key=lambda c: -c.score)  # relaxed_order may return slightly out of order
    return rows[:KEEP]


async def search(
    conn: AsyncConnection, query: str, filters: SearchFilters, *, embedder: QueryEmbedder
) -> SearchResult:
    glossary = load_glossary()
    expanded = glossary.expand(query)
    model_id, vector = await embedder.embed_query(expanded)
    ranked = await rank(conn, vector, model_id, filters)
    selected = ranked[:SELECT_TOP]
    budget = sum(c.token_count for c in selected)
    parent_ids = list(dict.fromkeys(c.parent_id for c in selected if c.parent_id is not None))
    parents = {c.chunk_id: c for c in await get_chunks(conn, parent_ids)} if parent_ids else {}
    context: list[RetrievedChunk] = []
    for pid in parent_ids:
        parent = parents.get(pid)
        if parent is not None and budget + parent.token_count <= CONTEXT_TOKEN_BUDGET:
            context.append(parent)
            budget += parent.token_count
    return SearchResult(expanded, glossary.version, ranked, selected, context)


async def get_chunks(conn: AsyncConnection, ids: Sequence[uuid.UUID]) -> list[RetrievedChunk]:
    """Chunks by id from any version, active or superseded (citations resolve to the exact text cited)."""
    if not ids:
        return []
    result = await conn.execute(_BY_ID_SQL, {"ids": list(ids)})
    return [_row(r) for r in result]
