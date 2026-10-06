"""Ephemeral test databases on a real Postgres (AGENTS.md rule 14). Used by conftest.py and the E2E server.

TEST_DATABASE_ADMIN_URL points at a superuser on a Postgres server (CI: the pgvector service container;
locally: the compose `postgres` service). `create_database()`:
1. creates the five service roles if missing (mirrors infra/postgres/initdb, fixed test passwords),
2. creates a fresh database owned by app_owner, with the three allowed extensions,
3. runs `alembic upgrade head` as app_owner.
`drop_database()` removes it.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL, make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROLES = ("app_owner", "app_api", "app_worker", "app_ingest", "app_readonly")
ROLE_PASSWORD = "test-only-password"  # noqa: S105 - throwaway role password for an ephemeral test database
# Local default mirrors the Makefile (`make test-role`, local dev only); CI exports its own URL.
DEFAULT_ADMIN_URL = "postgresql+psycopg://buildone_test:buildone-test-only@localhost:5432/buildone"


@dataclass(frozen=True)
class EphemeralDatabase:
    name: str
    admin_url: URL

    def url_for(self, role: str) -> str:
        return self.admin_url.set(
            username=role, password=ROLE_PASSWORD, database=self.name
        ).render_as_string(hide_password=False)

    def admin_url_for_db(self) -> str:
        return self.admin_url.set(database=self.name).render_as_string(hide_password=False)


def _libpq(url: URL) -> str:
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def alembic_config(owner_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", owner_url.replace("%", "%%"))
    config.attributes["configure_logging"] = False
    return config


RLS_CHECK_ROLE_SQL = BACKEND_DIR.parent / "infra" / "postgres" / "initdb" / "10-rls-check-role.sql"


def _ensure_roles(conn: psycopg.Connection) -> None:
    for role in ROLES:
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
        bypass = "" if role == "app_owner" else " NOBYPASSRLS"
        if exists is None:
            conn.execute(f"CREATE ROLE {role} LOGIN PASSWORD '{ROLE_PASSWORD}'{bypass}")
        else:
            conn.execute(f"ALTER ROLE {role} LOGIN PASSWORD '{ROLE_PASSWORD}'{bypass}")
    # The same idempotent SQL that initdb and `make db-roles` run (ADR-0013).
    conn.execute(RLS_CHECK_ROLE_SQL.read_text())  # type: ignore[arg-type]


def create_database(prefix: str = "buildone_test") -> EphemeralDatabase:
    admin_url = make_url(os.environ.get("TEST_DATABASE_ADMIN_URL", DEFAULT_ADMIN_URL))
    name = f"{prefix}_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(_libpq(admin_url), autocommit=True) as conn:
        _ensure_roles(conn)
        conn.execute(f'CREATE DATABASE "{name}" OWNER app_owner')
    db = EphemeralDatabase(name=name, admin_url=admin_url)
    with psycopg.connect(_libpq(make_url(db.admin_url_for_db())), autocommit=True) as conn:
        for ext in ("vector", "pg_trgm", "citext"):
            conn.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")
    command.upgrade(alembic_config(db.url_for("app_owner")), "head")
    return db


def drop_database(db: EphemeralDatabase) -> None:
    with psycopg.connect(_libpq(db.admin_url), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{db.name}" WITH (FORCE)')


def owner_connection(db: EphemeralDatabase) -> psycopg.Connection:
    """Sync connection as app_owner, for catalog checks and setting up test fixtures."""
    return psycopg.connect(_libpq(make_url(db.url_for("app_owner"))), autocommit=True)


def admin_connection(db: EphemeralDatabase) -> psycopg.Connection:
    return psycopg.connect(_libpq(make_url(db.admin_url_for_db())), autocommit=True)


def role_connection(db: EphemeralDatabase, role: str) -> psycopg.Connection:
    """Sync connection as a service role (RLS applies), autocommit off."""
    return psycopg.connect(_libpq(make_url(db.url_for(role))))
