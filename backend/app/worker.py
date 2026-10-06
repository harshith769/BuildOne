"""Worker entry point: `python -m app.worker` runs queued and periodic jobs."""

from __future__ import annotations

import asyncio

from app.platform.config import get_settings
from app.platform.logging import configure_logging, get_logger
from app.platform.queue import create_queue_app


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("app.worker")
    queue_app = create_queue_app(settings)
    async with queue_app.open_async():
        log.info("worker_started")
        await queue_app.run_worker_async(install_signal_handlers=True)


if __name__ == "__main__":
    asyncio.run(run())
