"""Health endpoints (api-conventions.md §8). Both are unauthenticated and return no user data.

- GET /healthz: the process is alive.
- GET /readyz: the database answers, migrations are at head, and the job queue is not lagging.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.platform.db import tenant_transaction
from app.platform.logging import get_logger

router = APIRouter(tags=["health"])
_log = get_logger("app.platform.health")
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

CheckStatus = Literal["ok", "fail"]


class Liveness(BaseModel):
    status: Literal["ok"]


class Readiness(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, CheckStatus]


@lru_cache(maxsize=1)
def migration_heads() -> frozenset[str]:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "migrations"))
    return frozenset(ScriptDirectory.from_config(config).get_heads())


_OLDEST_RUNNABLE_JOB = text(
    """
    SELECT EXTRACT(EPOCH FROM now() - min(e.at))
    FROM procrastinate_jobs j
    JOIN procrastinate_events e ON e.job_id = j.id AND e.type = 'deferred'
    WHERE j.status = 'todo' AND (j.scheduled_at IS NULL OR j.scheduled_at <= now())
    """
)


async def check_readiness(engine: AsyncEngine, max_lag_seconds: int) -> dict[str, CheckStatus]:
    checks: dict[str, CheckStatus] = {"database": "fail", "migrations": "fail", "queue": "fail"}
    try:
        async with tenant_transaction(engine) as conn:
            await conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
            current = {
                row[0]
                for row in await conn.execute(
                    text("SELECT version_num FROM public.alembic_version")
                )
            }
            checks["migrations"] = "ok" if current == set(migration_heads()) else "fail"
            lag = (await conn.execute(_OLDEST_RUNNABLE_JOB)).scalar()
            checks["queue"] = "ok" if lag is None or float(lag) <= max_lag_seconds else "fail"
    except Exception as exc:  # readiness must answer, never raise
        _log.warning("readiness_check_failed", error=type(exc).__name__)
    return checks


@router.get("/healthz", response_model=Liveness)
async def healthz() -> Liveness:
    return Liveness(status="ok")


@router.get("/readyz", response_model=Readiness, responses={503: {"model": Readiness}})
async def readyz(request: Request, response: Response) -> Readiness:
    engine: AsyncEngine = request.app.state.engine
    checks = await check_readiness(engine, request.app.state.settings.queue_max_lag_seconds)
    ready = all(v == "ok" for v in checks.values())
    if not ready:
        response.status_code = 503
    return Readiness(status="ready" if ready else "not_ready", checks=checks)
