"""Audit events for sign-in, sign-out and session revoke (M2 follow-up), and the hourly sweeper jobs."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.modules.identity.jobs import sweep_expired_sessions_once
from app.platform.clock import FrozenClock
from app.platform.config import Settings
from app.platform.db import create_engine
from app.platform.jobs import sweep_idempotency_keys_once
from tests.integration.auth_support import AuthHarness, auth_harness, csrf_headers, sign_in, sign_up
from tests.integration.tenancy_support import audit_rows, unique_email
from tests.support.db import EphemeralDatabase, admin_connection


@pytest.fixture
async def h(api_settings: Settings) -> AsyncIterator[AuthHarness]:
    async with auth_harness(api_settings) as harness:
        yield harness


@pytest.fixture
async def worker_engine(test_db: EphemeralDatabase) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(
        Settings(environment="ci", database_url=test_db.url_for("app_worker"), log_level="WARNING")
    )
    yield engine
    await engine.dispose()


def _user_id(db: EphemeralDatabase, email: str) -> uuid.UUID:
    with admin_connection(db) as conn:
        row = conn.execute("SELECT id FROM identity.users WHERE email = %s", (email,)).fetchone()
    assert row is not None
    return row[0]  # type: ignore[no-any-return]


def _rows_for(db: EphemeralDatabase, action: str, user_id: uuid.UUID) -> list[dict[str, object]]:
    return [r for r in audit_rows(db, action) if r["actor_user_id"] == user_id]


async def test_sign_in_sign_out_and_revoke_are_audited(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    email = unique_email("audited")
    await sign_up(h.client, email=email)
    user_id = _user_id(test_db, email)
    [signup] = _rows_for(test_db, "identity.signed_in", user_id)
    assert signup["metadata"] == {"new_account": True}
    assert signup["org_id"] is None
    assert signup["target_table"] == "identity.sessions"
    assert signup["request_id"]

    async with h.new_client() as laptop, h.new_client() as phone, h.new_client() as tablet:
        for browser in (laptop, phone, tablet):
            await sign_in(browser, email=email)
        assert len(_rows_for(test_db, "identity.signed_in", user_id)) == 4

        sessions = (await laptop.get("/v1/me/sessions")).json()["items"]
        phone_session = next(s["id"] for s in sessions if not s["is_current"])  # any other session
        assert (
            await laptop.delete(f"/v1/me/sessions/{phone_session}", headers=csrf_headers(laptop))
        ).status_code == 204
        [one] = _rows_for(test_db, "identity.session_revoked", user_id)
        assert one["target_id"] == phone_session
        assert one["metadata"] == {}

        revoked = await laptop.post("/v1/me/sessions/revoke-others", headers=csrf_headers(laptop))
        count = revoked.json()["revoked"]
        bulk = [r for r in _rows_for(test_db, "identity.session_revoked", user_id) if r["metadata"]]
        assert len(bulk) == count == 2
        assert all(r["metadata"] == {"bulk": True} for r in bulk)

        current = next(s["id"] for s in (await laptop.get("/v1/me/sessions")).json()["items"])
        assert (
            await laptop.post("/v1/auth/logout", headers=csrf_headers(laptop))
        ).status_code == 204
        [out] = _rows_for(test_db, "identity.signed_out", user_id)
        assert out["target_id"] == current


def _insert_session(
    db: EphemeralDatabase, user_id: uuid.UUID, idle: datetime, absolute: datetime
) -> uuid.UUID:
    session_id = uuid.uuid7()
    with admin_connection(db) as conn:
        conn.execute(
            "INSERT INTO identity.sessions (id, user_id, token_hash, csrf_token_hash, last_seen_at, "
            "idle_expires_at, absolute_expires_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                session_id,
                user_id,
                uuid.uuid4().bytes,
                uuid.uuid4().bytes,
                idle - timedelta(days=30),
                idle,
                absolute,
            ),
        )
    return session_id


def _new_user(db: EphemeralDatabase) -> uuid.UUID:
    user_id = uuid.uuid7()
    with admin_connection(db) as conn:
        conn.execute(
            "INSERT INTO identity.users (id, email, display_name, idp_user_id, age_confirmed_at) "
            "VALUES (%s, %s, 'S', %s, now())",
            (user_id, unique_email("sweep"), f"sweep|{user_id}"),
        )
    return user_id


def _existing(db: EphemeralDatabase, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    with admin_connection(db) as conn:
        rows = conn.execute(
            "SELECT id FROM identity.sessions WHERE id = ANY(%s)", (ids,)
        ).fetchall()
    return {r[0] for r in rows}


async def test_session_sweeper_removes_only_expired_sessions_and_is_rerunnable(
    test_db: EphemeralDatabase, worker_engine: AsyncEngine
) -> None:
    now = datetime(2031, 1, 1, tzinfo=UTC)  # after every other test's sessions
    a, b = _new_user(test_db), _new_user(test_db)
    idle_expired = _insert_session(test_db, a, now - timedelta(seconds=1), now + timedelta(days=10))
    abs_expired = _insert_session(test_db, b, now, now)  # idle never exceeds absolute (CHECK)
    alive = _insert_session(test_db, a, now + timedelta(days=1), now + timedelta(days=60))
    before = len(audit_rows(test_db, "identity.sessions_swept"))

    swept = await sweep_expired_sessions_once(worker_engine, FrozenClock(now), batch=1)
    assert swept >= 2
    assert _existing(test_db, [idle_expired, abs_expired, alive]) == {alive}
    rows = audit_rows(test_db, "identity.sessions_swept")
    assert len(rows) == before + 1
    assert rows[-1]["actor_user_id"] is None
    assert rows[-1]["metadata"] == {"count": swept}
    assert str(rows[-1]["request_id"]).startswith("job-sweep_expired_sessions-")

    assert await sweep_expired_sessions_once(worker_engine, FrozenClock(now)) == 0
    assert len(audit_rows(test_db, "identity.sessions_swept")) == before + 1, (
        "no row when nothing swept"
    )


async def test_idempotency_sweeper_removes_keys_after_24_hours(
    test_db: EphemeralDatabase, worker_engine: AsyncEngine
) -> None:
    now = datetime(2031, 1, 2, tzinfo=UTC)
    user = _new_user(test_db)
    old, fresh = uuid.uuid4(), uuid.uuid4()
    with admin_connection(test_db) as conn:
        for key, expires in ((old, now - timedelta(minutes=1)), (fresh, now + timedelta(hours=1))):
            conn.execute(
                "INSERT INTO platform.idempotency_keys (user_id, key, request_sha256, expires_at) "
                "VALUES (%s, %s, 'x', %s)",
                (user, key, expires),
            )
    assert await sweep_idempotency_keys_once(worker_engine, FrozenClock(now)) >= 1
    with admin_connection(test_db) as conn:
        left = {
            r[0]
            for r in conn.execute(
                "SELECT key FROM platform.idempotency_keys WHERE user_id = %s", (user,)
            ).fetchall()
        }
    assert left == {fresh}
    assert await sweep_idempotency_keys_once(worker_engine, FrozenClock(now)) == 0


def test_sweep_functions_are_worker_only(test_db: EphemeralDatabase) -> None:
    import psycopg

    from tests.support.db import role_connection

    with role_connection(test_db, "app_api") as conn:
        for call in (
            "SELECT * FROM identity.expired_sessions(now(), 1)",
            "SELECT * FROM platform.expired_idempotency_keys(now(), 1)",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(call)
            conn.rollback()
