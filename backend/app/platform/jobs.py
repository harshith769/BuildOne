"""Platform-level jobs: ping (end-to-end check) and the hourly idempotency-key sweep."""

from __future__ import annotations

import uuid
from collections import defaultdict

import procrastinate
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.platform import idempotency
from app.platform.clock import Clock, SystemClock
from app.platform.db import job_engine, tenant_transaction
from app.platform.logging import get_logger

blueprint = procrastinate.Blueprint()
_log = get_logger("app.platform.jobs")


@blueprint.task(name="ping")
async def ping(token: str) -> str:
    """No-op job used by tests and operators to check the worker end to end."""
    _log.info("ping", token=token)
    return token


async def sweep_idempotency_keys_once(
    engine: AsyncEngine, clock: Clock, *, batch: int = 500
) -> int:
    """Delete idempotency keys older than 24 hours, per user in that user's RLS context."""
    now = clock.now()
    k = idempotency.keys.c
    total = 0
    while True:
        async with engine.begin() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT user_id, key FROM platform.expired_idempotency_keys(:now, :limit)"
                    ),
                    {"now": now, "limit": batch},
                )
            ).all()
        if not rows:
            break
        by_user: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for user_id, key in rows:
            by_user[user_id].append(key)
        deleted = 0
        for user_id, user_keys in by_user.items():
            async with tenant_transaction(engine, user_id=user_id) as conn:
                result = await conn.execute(
                    delete(idempotency.keys).where(
                        k.user_id == user_id, k.key.in_(user_keys), k.expires_at <= now
                    )
                )
                deleted += result.rowcount
        total += deleted
        if deleted == 0 or len(rows) < batch:
            break
    _log.info("idempotency_keys_swept", count=total)
    return total


@blueprint.periodic(cron="37 * * * *")
@blueprint.task(name="sweep_idempotency_keys", queueing_lock="sweep_idempotency_keys")
async def sweep_idempotency_keys(timestamp: int) -> int:
    return await sweep_idempotency_keys_once(job_engine(), SystemClock())
