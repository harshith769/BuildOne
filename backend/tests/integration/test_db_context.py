from __future__ import annotations

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.platform.db import tenant_transaction
from app.platform.ids import new_id
from tests.support.db import EphemeralDatabase, owner_connection

_CONTEXT = text("SELECT platform.current_user_id(), platform.current_org_id()")


async def test_context_is_set_inside_the_transaction(api_engine: AsyncEngine) -> None:
    user_id, org_id = new_id(), new_id()
    async with tenant_transaction(api_engine, user_id=user_id, org_id=org_id) as conn:
        row = (await conn.execute(_CONTEXT)).one()
    assert row == (user_id, org_id)


async def test_context_does_not_leak_into_the_next_transaction(api_engine: AsyncEngine) -> None:
    async with tenant_transaction(api_engine, user_id=new_id(), org_id=new_id()):
        pass
    # Same pool, possibly the same physical connection: SET LOCAL must not survive the commit.
    for _ in range(3):
        async with api_engine.connect() as conn:
            row = (await conn.execute(_CONTEXT)).one()
            assert row == (None, None)


async def test_missing_context_is_null_so_policies_fail_closed(api_engine: AsyncEngine) -> None:
    async with tenant_transaction(api_engine) as conn:
        assert (await conn.execute(_CONTEXT)).one() == (None, None)


async def test_context_is_rolled_back_with_the_transaction(api_engine: AsyncEngine) -> None:
    with pytest.raises(RuntimeError):
        async with tenant_transaction(api_engine, user_id=new_id()):
            raise RuntimeError("fail the transaction")
    async with api_engine.connect() as conn:
        assert (await conn.execute(_CONTEXT)).one() == (None, None)


async def test_api_role_cannot_change_the_schema(api_engine: AsyncEngine) -> None:
    async with api_engine.connect() as conn:
        with pytest.raises(Exception, match="permission denied"):
            await conn.execute(text("CREATE TABLE tenancy.should_fail (id int)"))


def test_api_role_cannot_bypass_rls(test_db: EphemeralDatabase) -> None:
    with owner_connection(test_db) as conn:
        rows = conn.execute(
            "SELECT rolname, rolbypassrls, rolsuper FROM pg_roles "
            "WHERE rolname IN ('app_api','app_worker','app_ingest','app_readonly')"
        ).fetchall()
    assert len(rows) == 4
    assert all(not bypass and not superuser for _, bypass, superuser in rows)


def test_api_role_can_use_the_job_queue(test_db: EphemeralDatabase) -> None:
    with psycopg.connect(
        test_db.url_for("app_api").replace("postgresql+psycopg", "postgresql"),
        options="-c search_path=procrastinate,public",
    ) as conn:
        assert conn.execute("SELECT count(*) FROM procrastinate_jobs").fetchone() == (0,)


async def test_sessions_run_in_utc(api_engine: AsyncEngine) -> None:
    async with api_engine.connect() as conn:
        assert (await conn.execute(text("SHOW timezone"))).scalar() == "UTC"
