"""Audit log (FR-PLT-05, data-model.md §4.3): one append-only row per audited action.

`record` runs inside the caller's transaction, so the audit row commits or rolls back with the change it
describes. The database accepts a row only when the actor is the current user (and can read the org it names),
or, for system rows with no actor, only from the worker role. Metadata never holds secrets, tokens or document
contents; keep it to IDs, roles, counts and states.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from app.modules.audit import models
from app.platform.context import get_request_id
from app.platform.ids import new_id

_ACTION = re.compile(r"^[a-z_]+\.[a-z_]+$")


def system_request_id(job: str) -> str:
    """Request ID for rows written by a job (there is no HTTP request)."""
    return f"job-{job}-{new_id()}"


async def record(
    conn: AsyncConnection,
    *,
    action: str,
    actor_user_id: uuid.UUID | None,
    target_table: str,
    target_id: str | uuid.UUID,
    occurred_at: datetime,
    org_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> None:
    if not _ACTION.fullmatch(action):
        raise ValueError(f"audit action must look like 'module.verb': {action!r}")
    await conn.execute(
        insert(models.events).values(
            occurred_at=occurred_at,
            actor_user_id=actor_user_id,
            org_id=org_id,
            request_id=request_id or get_request_id() or system_request_id("unknown"),
            action=action,
            target_table=target_table,
            target_id=str(target_id),
            metadata=metadata or {},
        )
    )
