"""Alembic environment. Runs as app_owner, synchronously, one transaction per migration run.

URL: the `sqlalchemy.url` option if a caller set it (tests), else DATABASE_URL from the environment
(the compose `migrate` service passes the app_owner URL as DATABASE_URL).
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

config = context.config
if config.config_file_name and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name)


def _url() -> str:
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "Set DATABASE_URL to the app_owner connection URL before running migrations"
        )
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        literal_binds=True,
        version_table_schema="public",
        transaction_per_migration=False,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection, version_table_schema="public", transaction_per_migration=False
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
