"""Application settings, read from environment variables (see infra/compose/.env.example)."""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
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

    # Identity (docs/auth-and-tenancy.md). The API's own public URL; the IdP redirects back to
    # `auth_redirect_uri`, and the API then redirects the browser to `app_origin`.
    api_base_url: str = "http://localhost:8000"
    auth_redirect_uri: str = ""  # empty = {api_base_url}/v1/auth/callback
    identity_provider: Literal["fake", "workos"] = "fake"
    workos_api_key: SecretStr = SecretStr("")
    workos_client_id: str = ""
    # HMAC key for the short-lived sign-in cookies and fake-IdP codes. Required in production; elsewhere an
    # empty value means a random per-process key (sign-ins in progress don't survive a restart).
    secret_key: SecretStr = SecretStr("")
    session_idle_days: int = Field(default=30, ge=1)
    session_absolute_days: int = Field(default=90, ge=1)
    # Current terms of use and privacy notice versions; a user must have accepted both (FR-PLT-06).
    terms_version: str = Field(default="2026-10-draft", min_length=1, max_length=64)
    privacy_version: str = Field(default="2026-10-draft", min_length=1, max_length=64)

    sentry_dsn: str = ""

    @model_validator(mode="after")
    def _check_identity(self) -> Self:
        if self.environment == "production":
            if self.identity_provider == "fake":
                raise ValueError("the fake identity provider is never allowed in production")
            if len(self.secret_key.get_secret_value()) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters in production")
        if self.identity_provider == "workos" and not (
            self.workos_api_key.get_secret_value() and self.workos_client_id
        ):
            raise ValueError("WORKOS_API_KEY and WORKOS_CLIENT_ID are required for workos")
        if self.session_idle_days > self.session_absolute_days:
            raise ValueError("SESSION_IDLE_DAYS must not exceed SESSION_ABSOLUTE_DAYS")
        if not self.secret_key.get_secret_value():
            object.__setattr__(self, "secret_key", SecretStr(secrets.token_urlsafe(48)))
        if not self.auth_redirect_uri:
            object.__setattr__(
                self, "auth_redirect_uri", f"{self.api_base_url.rstrip('/')}/v1/auth/callback"
            )
        return self

    @property
    def cookie_domain(self) -> str | None:
        """`.<root-domain>` so app. and api. share cookies; host-only on localhost."""
        return None if self.root_domain == "localhost" else f".{self.root_domain}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings for the running process (cached). Tests build Settings explicitly instead."""
    return Settings()  # database_url comes from the environment (pydantic-settings)
