"""Audit table (private to this module; other modules call audit.service). Schema: migration 0004."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData(schema="audit")

events = Table(
    "events",
    metadata,
    # `id` (bigint identity) is left out: this module only appends, and naming it would make SQLAlchemy
    # fetch it (RETURNING needs a SELECT policy; a pre-fetched value is refused by GENERATED ALWAYS).
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("actor_user_id", Uuid),
    Column("org_id", Uuid),
    Column("request_id", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column("target_table", Text, nullable=False),
    Column("target_id", Text, nullable=False),
    Column("metadata", JSONB, nullable=False),
    implicit_returning=False,
)
