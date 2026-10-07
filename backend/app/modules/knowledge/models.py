"""Knowledge tables (private to this module; other modules call knowledge.service). Schema: migration 0007."""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from app.modules.knowledge.embedding import DIMENSION

metadata = MetaData(schema="knowledge")

sources = Table(
    "sources",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("key", Text, nullable=False, unique=True),
    Column("title", Text, nullable=False),
    Column("authority", Text, nullable=False),
    Column("jurisdiction", Text, nullable=False),
    Column("doc_type", Text, nullable=False),
    Column("official_url", Text, nullable=False),
)

source_versions = Table(
    "source_versions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("source_id", Uuid, ForeignKey("knowledge.sources.id"), nullable=False),
    Column("version", Integer, nullable=False),
    Column("content_sha256", Text, nullable=False),
    Column("storage_key", Text, nullable=False),
    Column("published_on", Date),
    Column("effective_from", Date, nullable=False),
    Column("effective_to", Date),
    Column("parser", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("review", JSONB, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
)

chunks = Table(
    "chunks",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("source_version_id", Uuid, ForeignKey("knowledge.source_versions.id"), nullable=False),
    Column("parent_id", Uuid, ForeignKey("knowledge.chunks.id")),
    Column("kind", Text, nullable=False),
    Column("section_path", Text, nullable=False),
    Column("node_paths", ARRAY(Text), nullable=False),
    Column("heading", Text, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("token_count", Integer, nullable=False),
    Column("jurisdiction", Text, nullable=False),
    Column("doc_type", Text, nullable=False),
    Column("effective_from", Date, nullable=False),
    Column("effective_to", Date),
    Column("is_active", Boolean, nullable=False),
    # `tsv` (generated) is left out: nothing writes it, and the lexical list is off in the MVP (ADR-0014).
)

chunk_embeddings = Table(
    "chunk_embeddings",
    metadata,
    Column("chunk_id", Uuid, ForeignKey("knowledge.chunks.id"), primary_key=True),
    Column("model_id", Text, primary_key=True),
    Column("embedding", Vector(DIMENSION), nullable=False),
)
