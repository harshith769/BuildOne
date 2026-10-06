"""Database engine and the tenant-context transaction (data-model.md §3).

Every request or job runs its queries inside `tenant_transaction()`, which starts a transaction and sets
`app.user_id` / `app.org_id` with `set_config(..., is_local => true)` — the parameterised form of SET LOCAL.
The settings vanish when the transaction ends, and RLS policies read them through
`platform.current_user_id()` / `platform.current_org_id()`. Unset means NULL, so policies fail closed.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.platform.config import Settings

# Procrastinate's tables and functions are unqualified, so connections look them up in its schema.
# Module tables are always schema-qualified (identity.users, tenancy.organizations, ...).
SEARCH_PATH = "procrastinate,public"

_SET_CONTEXT = text(
    "SELECT set_config('app.user_id', :user_id, true), set_config('app.org_id', :org_id, true)"
)


def create_engine(settings: Settings) -> AsyncEngine:
    """Async engine for the API or worker role. Never pass the app_owner URL here (AGENTS.md pitfalls)."""
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        connect_args={"options": f"-c search_path={SEARCH_PATH}"},
    )


def libpq_conninfo(sqlalchemy_url: str) -> str:
    """Turn `postgresql+psycopg://...` into a plain libpq URL for psycopg / Procrastinate."""
    return (
        make_url(sqlalchemy_url).set(drivername="postgresql").render_as_string(hide_password=False)
    )


@asynccontextmanager
async def tenant_transaction(
    engine: AsyncEngine, *, user_id: uuid.UUID | None = None, org_id: uuid.UUID | None = None
) -> AsyncIterator[AsyncConnection]:
    """One transaction with the RLS context set first. Commits on success, rolls back on error."""
    async with engine.begin() as conn:
        await conn.execute(
            _SET_CONTEXT,
            {"user_id": str(user_id) if user_id else "", "org_id": str(org_id) if org_id else ""},
        )
        yield conn
