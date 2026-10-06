"""Application settings, read from environment variables (see infra/compose/.env.example)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Secrets come only from the environment, never from files in git."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore", frozen=True)

    environment: Literal["local", "ci", "production"] = "local"
    root_domain: str = "localhost"
    app_origin: str = "http://localhost:5173"
    legal_timezone: str = "Asia/Kolkata"
    log_level: str = "INFO"

    # SQLAlchemy URL with the psycopg 3 driver, e.g. postgresql+psycopg://app_api:...@postgres:5432/buildone
    database_url: str
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)

    # Readiness: oldest runnable job older than this means the worker is not keeping up.
    queue_max_lag_seconds: int = Field(default=300, ge=1)

    identity_provider: Literal["fake", "workos"] = "fake"
    sentry_dsn: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings for the running process (cached). Tests build Settings explicitly instead."""
    return Settings()  # database_url comes from the environment (pydantic-settings)
