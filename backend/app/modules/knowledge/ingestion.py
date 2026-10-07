"""Ingestion core (data-pipeline.md §1, §5, §7): parse -> tree -> chunks -> embed -> one transaction.

Used by the CLI (`knowledge.ingest`) on the laptop as `app_ingest`. Side effects (download, raw-file storage) run
before the transaction (AGENTS.md rule 12); the transaction only writes rows. Nothing is ever deleted: a new
active version supersedes the old one by flipping `status` and `is_active`, so old chunks stay retrievable by
id for citations. A version whose OCR'd or publisher-OCR pages fall below the S1 confidence threshold loads as
`pending_review` (inactive) until `approve()`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import Connection, func, insert, select, update

from app.modules.knowledge import models
from app.modules.knowledge.chunking import ChunkDraft, TokenCounter, build_chunks
from app.modules.knowledge.embedding import Embedder
from app.modules.knowledge.parsing.model import ParsedDocument
from app.modules.knowledge.parsing.structure import build_tree
from app.modules.knowledge.registry import Source
from app.platform.ids import new_id

LoadOutcome = Literal["loaded", "pending_review", "unchanged"]
CONTENT_TYPES = {"pdf": "application/pdf", "html": "text/html", "html_bundle": "application/zip"}


class IngestionError(RuntimeError):
    """A source could not be ingested (nothing was written)."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def storage_key(source: Source, digest: str) -> str:
    return f"sources/{source.key}/{digest}.{source.extension}"


@dataclass
class PreparedVersion:
    """Everything computed outside the transaction."""

    source: Source
    digest: str
    storage_key: str
    document: ParsedDocument
    chunks: list[ChunkDraft]
    vectors: list[list[float]]  # one per non-parent chunk, in order
    model_id: str
    review: dict[str, Any] = field(default_factory=dict)

    @property
    def needs_review(self) -> bool:
        return bool(self.review.get("pages"))


def review_summary(doc: ParsedDocument) -> dict[str, Any]:
    pages = [
        {
            "page": p.number,
            "source": p.source,
            "confidence": round(p.confidence, 1) if p.confidence else None,
        }
        for p in doc.pages
        if p.needs_review
    ]
    low = [
        {"page": ln.page, "confidence": round(ln.confidence or 0, 1), "text": ln.text[:120]}
        for p in doc.pages
        if not p.needs_review
        for ln in p.low_confidence_lines
    ]
    return {"pages": pages, "low_confidence_lines": low[:200]}


def prepare(
    source: Source,
    data: bytes,
    document: ParsedDocument,
    *,
    embedder: Embedder,
    count: TokenCounter,
    offsets: Any,
) -> PreparedVersion:
    digest = sha256(data)
    chunks = build_chunks(build_tree(document), count, offsets)
    ranked = [c for c in chunks if c.kind != "parent"]
    if not ranked:
        raise IngestionError(f"{source.key}: no text found (parser {document.parser})")
    vectors = embedder.embed_passages([c.embed_text(source.title) for c in ranked])
    return PreparedVersion(
        source=source,
        digest=digest,
        storage_key=storage_key(source, digest),
        document=document,
        chunks=chunks,
        vectors=vectors,
        model_id=embedder.model_id,
        review=review_summary(document),
    )


def find_version_by_digest(
    conn: Connection, source_key: str, digest: str
) -> tuple[int, str] | None:
    """(version, status) of an existing non-superseded version with these exact bytes."""
    row = conn.execute(
        select(models.source_versions.c.version, models.source_versions.c.status)
        .join(models.sources, models.sources.c.id == models.source_versions.c.source_id)
        .where(
            models.sources.c.key == source_key,
            models.source_versions.c.content_sha256 == digest,
            models.source_versions.c.status != "superseded",
        )
    ).first()
    return (int(row.version), str(row.status)) if row else None


def _upsert_source(conn: Connection, source: Source) -> Any:
    values = {
        "title": source.title,
        "authority": source.authority,
        "jurisdiction": source.jurisdiction,
        "doc_type": source.doc_type,
        "official_url": source.official_url,
    }
    existing = conn.execute(
        select(models.sources.c.id).where(models.sources.c.key == source.key)
    ).scalar()
    if existing is not None:
        conn.execute(update(models.sources).where(models.sources.c.id == existing).values(**values))
        return existing
    source_id = new_id()
    conn.execute(insert(models.sources).values(id=source_id, key=source.key, **values))
    return source_id


def _supersede_active(conn: Connection, source_id: Any) -> None:
    """Retire the active version (before another one becomes active: one active version per source)."""
    old = [
        row.id
        for row in conn.execute(
            select(models.source_versions.c.id).where(
                models.source_versions.c.source_id == source_id,
                models.source_versions.c.status == "active",
            )
        )
    ]
    if not old:
        return
    conn.execute(
        update(models.source_versions)
        .where(models.source_versions.c.id.in_(old))
        .values(status="superseded")
    )
    conn.execute(
        update(models.chunks)
        .where(models.chunks.c.source_version_id.in_(old))
        .values(is_active=False)
    )


def load(
    conn: Connection, prepared: PreparedVersion, *, fetched_at: datetime, approve: bool = False
) -> int:
    """Write one source version in the caller's transaction; returns the version number."""
    source = prepared.source
    source_id = _upsert_source(conn, source)
    # Serialise concurrent loads of the same source.
    conn.execute(
        select(models.sources.c.id).where(models.sources.c.id == source_id).with_for_update()
    )
    current = conn.execute(
        select(func.coalesce(func.max(models.source_versions.c.version), 0)).where(
            models.source_versions.c.source_id == source_id
        )
    ).scalar_one()
    version = int(current) + 1
    status = "pending_review" if prepared.needs_review and not approve else "active"
    if status == "active":
        _supersede_active(conn, source_id)
    version_id = new_id()
    conn.execute(
        insert(models.source_versions).values(
            id=version_id,
            source_id=source_id,
            version=version,
            content_sha256=prepared.digest,
            storage_key=prepared.storage_key,
            published_on=source.published_on,
            effective_from=source.effective_from,
            effective_to=source.effective_to,
            parser=prepared.document.parser,
            status=status,
            review=prepared.review,
            fetched_at=fetched_at,
        )
    )
    active = status == "active"
    common = {
        "source_version_id": version_id,
        "jurisdiction": source.jurisdiction,
        "doc_type": source.doc_type,
        "effective_from": source.effective_from,
        "effective_to": source.effective_to,
        "is_active": active,
    }
    # Parent chunks first (shallow to deep), so every chunk can point at its parent's id.
    parent_ids: dict[str, Any] = {}
    parents = sorted(
        (c for c in prepared.chunks if c.kind == "parent"),
        key=lambda c: c.section_path.count(" > "),
    )
    ranked = [c for c in prepared.chunks if c.kind != "parent"]
    rows = []
    for chunk in parents:
        chunk_id = new_id()
        parent_ids[chunk.section_path] = chunk_id
        rows.append(_chunk_row(chunk, chunk_id, parent_ids.get(chunk.parent_path or ""), common))
    embeddings = []
    for chunk, vector in zip(ranked, prepared.vectors, strict=True):
        chunk_id = new_id()
        rows.append(_chunk_row(chunk, chunk_id, parent_ids.get(chunk.parent_path or ""), common))
        embeddings.append(
            {"chunk_id": chunk_id, "model_id": prepared.model_id, "embedding": vector}
        )
    conn.execute(insert(models.chunks), rows)
    conn.execute(insert(models.chunk_embeddings), embeddings)
    return version


def _chunk_row(
    chunk: ChunkDraft, chunk_id: Any, parent_id: Any, common: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": chunk_id,
        "parent_id": parent_id,
        "kind": chunk.kind,
        "section_path": chunk.section_path,
        "node_paths": chunk.node_paths,
        "heading": chunk.heading,
        "ordinal": chunk.ordinal,
        "text": chunk.text,
        "token_count": chunk.token_count,
        **common,
    }


def approve(conn: Connection, source_key: str, version: int) -> None:
    """Activate a `pending_review` version after a person checked it, superseding the active one."""
    row = conn.execute(
        select(
            models.source_versions.c.id,
            models.source_versions.c.source_id,
            models.source_versions.c.status,
        )
        .join(models.sources, models.sources.c.id == models.source_versions.c.source_id)
        .where(models.sources.c.key == source_key, models.source_versions.c.version == version)
        .with_for_update()
    ).first()
    if row is None:
        raise IngestionError(f"{source_key}@{version}: no such version")
    if row.status != "pending_review":
        raise IngestionError(f"{source_key}@{version}: status is {row.status}, not pending_review")
    _supersede_active(conn, row.source_id)
    conn.execute(
        update(models.source_versions)
        .where(models.source_versions.c.id == row.id)
        .values(status="active")
    )
    conn.execute(
        update(models.chunks)
        .where(models.chunks.c.source_version_id == row.id)
        .values(is_active=True)
    )
