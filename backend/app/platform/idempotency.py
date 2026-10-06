"""Idempotency keys (docs/api-conventions.md §4).

The key row is written in the same transaction as the business write, so either both commit or neither does.
A concurrent duplicate blocks on the primary key until the first transaction ends, then replays its stored
response. The same key with a different request is 409 `idempotency_key_conflict`. Keys are per user and live
for 24 hours; a worker job sweeps expired rows.

Never store secrets in the response body: callers pass a `stored_body` without tokens or links when the
live response contains one (see tenancy invitations).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    Table,
    Text,
    Uuid,
    delete,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from app.platform.errors import Conflict, IdempotencyKeyConflict, ValidationProblem

TTL = timedelta(hours=24)
HEADER = "Idempotency-Key"

_metadata = MetaData(schema="platform")
keys = Table(
    "idempotency_keys",
    _metadata,
    Column("user_id", Uuid, primary_key=True),
    Column("key", Uuid, primary_key=True),
    Column("request_sha256", Text, nullable=False),
    Column("response_status", Integer),
    Column("response_body", JSONB),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)


@dataclass(frozen=True, slots=True)
class StoredResponse:
    status: int
    body: dict[str, Any]


def parse_key(header_value: str | None) -> uuid.UUID:
    if not header_value:
        raise ValidationProblem(
            "This request needs an Idempotency-Key header",
            errors=[{"field": HEADER, "message": "required (a UUID)"}],
        )
    try:
        return uuid.UUID(header_value)
    except ValueError as exc:
        raise ValidationProblem(
            "Idempotency-Key must be a UUID",
            errors=[{"field": HEADER, "message": "must be a UUID"}],
        ) from exc


def fingerprint(method: str, path: str, body: Any) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{method.upper()} {path}\n{canonical}".encode()).hexdigest()


async def begin(
    conn: AsyncConnection, *, user_id: uuid.UUID, key: uuid.UUID, request_sha256: str, now: datetime
) -> StoredResponse | None:
    """Claim the key for this request. Returns the stored response if this is a replay, else None."""
    k = keys.c
    # An expired key that the sweeper hasn't removed yet counts as unused.
    await conn.execute(delete(keys).where(k.user_id == user_id, k.key == key, k.expires_at <= now))
    # RETURNING tells a fresh claim from a conflict (rowcount isn't reliable for INSERT).
    claimed = (
        await conn.execute(
            pg_insert(keys)
            .values(user_id=user_id, key=key, request_sha256=request_sha256, expires_at=now + TTL)
            .on_conflict_do_nothing(index_elements=["user_id", "key"])
            .returning(k.key)
        )
    ).first()
    if claimed is not None:
        return None
    row = (
        await conn.execute(
            select(k.request_sha256, k.response_status, k.response_body).where(
                k.user_id == user_id, k.key == key
            )
        )
    ).one()
    if row.request_sha256 != request_sha256:
        raise IdempotencyKeyConflict()
    if row.response_status is None:
        raise Conflict("The first request with this key is still being processed. Try again.")
    return StoredResponse(status=row.response_status, body=row.response_body)


async def complete(
    conn: AsyncConnection,
    *,
    user_id: uuid.UUID,
    key: uuid.UUID,
    status: int,
    stored_body: dict[str, Any],
) -> None:
    """Store the response to replay. `stored_body` must not contain secrets."""
    await conn.execute(
        update(keys)
        .where(keys.c.user_id == user_id, keys.c.key == key)
        .values(response_status=status, response_body=stored_body)
    )
