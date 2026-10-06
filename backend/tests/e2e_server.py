"""API server for Playwright E2E: a fresh migrated database, the fake identity provider, port 8001.

Started by frontend/app/playwright.config.ts (`uv run python -m tests.e2e_server`). Needs
TEST_DATABASE_ADMIN_URL like the backend tests. Ports 8001/5174 keep clear of `make dev` (8000/5173).
The database is dropped on exit; databases left by a killed run are dropped on the next start.
"""

from __future__ import annotations

import os

import psycopg
import uvicorn
from sqlalchemy.engine import make_url

from app.main import create_app
from app.platform.config import Settings
from tests.support.db import DEFAULT_ADMIN_URL, create_database, drop_database

PREFIX = "buildone_e2e"
API_PORT = int(os.environ.get("E2E_API_PORT", "8001"))
APP_ORIGIN = os.environ.get("E2E_APP_ORIGIN", "http://localhost:5174")


def _drop_stale_databases() -> None:
    admin = make_url(os.environ.get("TEST_DATABASE_ADMIN_URL", DEFAULT_ADMIN_URL))
    libpq = admin.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(libpq, autocommit=True) as conn:
        names = [
            row[0]
            for row in conn.execute(
                "SELECT datname FROM pg_database WHERE datname LIKE %s", (f"{PREFIX}\\_%",)
            ).fetchall()
        ]
        for name in names:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def main() -> None:
    _drop_stale_databases()
    db = create_database(PREFIX)
    try:
        settings = Settings(
            environment="ci",
            database_url=db.url_for("app_api"),
            app_origin=APP_ORIGIN,
            api_base_url=f"http://localhost:{API_PORT}",
            identity_provider="fake",
            log_level="WARNING",
        )
        uvicorn.run(create_app(settings), host="127.0.0.1", port=API_PORT, log_level="warning")
    finally:
        drop_database(db)


if __name__ == "__main__":
    main()
