"""Identity jobs: sweep expired sessions (hourly).

`identity.expired_sessions()` (SECURITY DEFINER, worker only) returns IDs only; each user's sessions are then
deleted in that user's own RLS context (data-model.md §6). Safe to run twice and concurrently: a second run
finds nothing left to delete. Each run that deletes something writes one system audit row.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

import procrastinate
from sqlalchemy import delete, or_, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.modules.audit import service as audit
from app.modules.identity import models
from app.platform.clock import Clock, SystemClock
from app.platform.db import job_engine, tenant_transaction
from app.platform.logging import get_logger

blueprint = procrastinate.Blueprint()
BATCH = 500
_log = get_logger("app.identity.jobs")


async def sweep_expired_sessions_once(
    engine: AsyncEngine, clock: Clock, *, batch: int = BATCH
) -> int:
    now = clock.now()
    s = models.sessions.c
    total = 0
    while True:
        async with engine.begin() as conn:
            rows = (
                await conn.execute(
                    text("SELECT session_id, user_id FROM identity.expired_sessions(:now, :limit)"),
                    {"now": now, "limit": batch},
                )
            ).all()
        if not rows:
            break
        by_user: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for session_id, user_id in rows:
            by_user[user_id].append(session_id)
        deleted = 0
        for user_id, session_ids in by_user.items():
            async with tenant_transaction(engine, user_id=user_id) as conn:
                result = await conn.execute(
                    delete(models.sessions).where(
                        s.id.in_(session_ids),
                        or_(s.idle_expires_at <= now, s.absolute_expires_at <= now),
                    )
                )
                deleted += result.rowcount
        total += deleted
        if deleted == 0 or len(rows) < batch:
            break
    if total:
        async with tenant_transaction(engine) as conn:
            await audit.record(
                conn,
                action="identity.sessions_swept",
                actor_user_id=None,
                target_table="identity.sessions",
                target_id=now.isoformat(),
                occurred_at=now,
                metadata={"count": total},
                request_id=audit.system_request_id("sweep_expired_sessions"),
            )
    _log.info("sessions_swept", count=total)
    return total


@blueprint.periodic(cron="7 * * * *")
@blueprint.task(name="sweep_expired_sessions", queueing_lock="sweep_expired_sessions")
async def sweep_expired_sessions(timestamp: int) -> int:
    return await sweep_expired_sessions_once(job_engine(), SystemClock())
