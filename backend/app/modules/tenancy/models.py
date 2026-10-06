"""Tenancy tables (private to this module; other modules use tenancy.service). Schema: migration 0003."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, LargeBinary, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import CITEXT

metadata = MetaData(schema="tenancy")

organizations = Table(
    "organizations",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("type", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("deletion_requested_at", DateTime(timezone=True)),
    Column("source_team_id", Uuid),
    Column("created_by", Uuid, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    # Never RETURNING: the SELECT policy applies to it, and the creator isn't a member yet at insert.
    implicit_returning=False,
)

memberships = Table(
    "memberships",
    metadata,
    Column("org_id", Uuid, primary_key=True),
    Column("user_id", Uuid, primary_key=True),
    Column("role", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

invitations = Table(
    "invitations",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("org_id", Uuid, nullable=False),
    Column("email", CITEXT, nullable=False),
    Column("role", Text, nullable=False),
    Column("token_hash", LargeBinary, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("accepted_at", DateTime(timezone=True)),
    Column("invited_by", Uuid),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

access_grants = Table(
    "access_grants",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("grantor_org_id", Uuid, nullable=False),
    Column("grantee_org_id", Uuid, nullable=False),
    Column("scope", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("initiated_by", Text, nullable=False),
    Column("created_by", Uuid),
    Column("accepted_at", DateTime(timezone=True)),
    Column("revoked_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
