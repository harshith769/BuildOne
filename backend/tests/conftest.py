"""Test database lifecycle. Tests hit a real Postgres (AGENTS.md rule 14); see tests/support/db.py."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.platform.config import Settings
from app.platform.db import create_engine
from tests.support.db import EphemeralDatabase, create_database, drop_database


@pytest.fixture(scope="session")
def test_db() -> Iterator[EphemeralDatabase]:
    db = create_database()
    try:
        yield db
    finally:
        drop_database(db)


@pytest.fixture(scope="session")
def api_settings(test_db: EphemeralDatabase) -> Settings:
    return Settings(environment="ci", database_url=test_db.url_for("app_api"), log_level="WARNING")


@pytest.fixture(scope="session")
async def api_engine(api_settings: Settings) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(api_settings)
    try:
        yield engine
    finally:
        await engine.dispose()
