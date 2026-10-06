from __future__ import annotations

import psycopg
from alembic import command

from app.platform.config import Settings
from app.platform.queue import create_queue_app
from tests.conftest import EphemeralDatabase, alembic_config, owner_connection

EXPECTED_SCHEMAS = {
    "identity",
    "tenancy",
    "audit",
    "facts",
    "rules",
    "obligations",
    "knowledge",
    "ai",
    "copilot",
    "explainer",
    "documents",
    "launchpad",
    "notifications",
    "platform",
    "procrastinate",
}


def _schemas(conn: psycopg.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT nspname FROM pg_namespace").fetchall()}


def test_baseline_creates_every_module_schema(test_db: EphemeralDatabase) -> None:
    with owner_connection(test_db) as conn:
        assert EXPECTED_SCHEMAS <= _schemas(conn)


def test_migrations_downgrade_and_upgrade_cleanly(test_db: EphemeralDatabase) -> None:
    config = alembic_config(test_db.url_for("app_owner"))
    command.downgrade(config, "base")
    with owner_connection(test_db) as conn:
        assert not (EXPECTED_SCHEMAS & _schemas(conn))
    command.upgrade(config, "head")
    with owner_connection(test_db) as conn:
        assert EXPECTED_SCHEMAS <= _schemas(conn)


async def test_worker_runs_a_deferred_job(test_db: EphemeralDatabase) -> None:
    settings = Settings(
        environment="ci", database_url=test_db.url_for("app_worker"), log_level="WARNING"
    )
    queue_app = create_queue_app(settings)
    async with queue_app.open_async():
        job_id = await queue_app.configure_task("platform:ping").defer_async(token="hello")  # noqa: S106
        await queue_app.run_worker_async(wait=False, install_signal_handlers=False)
        status = await queue_app.job_manager.get_job_status_async(job_id)
    assert status.value == "succeeded"
