"""Background jobs on Procrastinate (ADR-0004): a Postgres-backed queue, so there's no Redis to run.

Modules define tasks on their own `procrastinate.Blueprint` in `jobs.py`; `create_queue_app` collects them.
Every task takes IDs (not objects), sets the RLS context itself and is safe to run twice (.claude/rules/backend.md).
"""

from __future__ import annotations

import procrastinate

from app.platform import jobs as platform_jobs
from app.platform.config import Settings
from app.platform.db import SEARCH_PATH, libpq_conninfo

# (namespace, blueprint) pairs. Add each module's blueprint here as modules gain jobs.
BLUEPRINTS: list[tuple[str, procrastinate.Blueprint]] = [
    ("platform", platform_jobs.blueprint),
]


def create_queue_app(settings: Settings) -> procrastinate.App:
    connector = procrastinate.PsycopgConnector(
        conninfo=libpq_conninfo(settings.database_url),
        kwargs={"options": f"-c search_path={SEARCH_PATH}"},
        min_size=1,
        max_size=4,
    )
    app = procrastinate.App(connector=connector)
    for namespace, blueprint in BLUEPRINTS:
        app.add_tasks_from(blueprint, namespace=namespace)
    return app
