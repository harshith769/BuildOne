"""Identity tables (private to this module; other modules use identity.service). Schema: migration 0002."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, LargeBinary, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import CITEXT, INET

metadata = MetaData(schema="identity")

users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("email", CITEXT, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("idp_user_id", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("deletion_requested_at", DateTime(timezone=True)),
    Column("age_confirmed_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

sessions = Table(
    "sessions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("user_id", Uuid, nullable=False),
    Column("token_hash", LargeBinary, nullable=False),
    Column("csrf_token_hash", LargeBinary, nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("idle_expires_at", DateTime(timezone=True), nullable=False),
    Column("absolute_expires_at", DateTime(timezone=True), nullable=False),
    Column("ip", INET),
    Column("user_agent", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

consents = Table(
    "consents",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("user_id", Uuid, nullable=False),
    Column("document", Text, nullable=False),
    Column("version", Text, nullable=False),
    Column("accepted_at", DateTime(timezone=True), nullable=False),
)
