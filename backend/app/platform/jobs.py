"""Platform-level jobs."""

from __future__ import annotations

import procrastinate

from app.platform.logging import get_logger

blueprint = procrastinate.Blueprint()
_log = get_logger("app.platform.jobs")


@blueprint.task(name="ping")
async def ping(token: str) -> str:
    """No-op job used by tests and operators to check the worker end to end."""
    _log.info("ping", token=token)
    return token
