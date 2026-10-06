"""Identity tables are user-scoped by RLS: a user sees only their own rows, nothing without context.

These tables have no `org_id`, so the tenant schema guard doesn't cover them; this suite does.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from app.platform.ids import new_id
from tests.support.db import EphemeralDatabase, owner_connection, role_connection

IDENTITY_TABLES = ("identity.users", "identity.sessions", "identity.consents")
NOW = datetime(2026, 10, 6, tzinfo=UTC)


def _make_user(conn: psycopg.Connection, label: str) -> uuid.UUID:
    user_id = new_id()
    conn.execute(
        "INSERT INTO identity.users (id, email, display_name, idp_user_id, age_confirmed_at) "
        "VALUES (%s, %s, %s, %s, %s)",
        (user_id, f"{label}-{user_id.hex[:8]}@example.test", label, f"rls|{user_id}", NOW),
    )
    conn.execute(
        "INSERT INTO identity.sessions (id, user_id, token_hash, csrf_token_hash, last_seen_at, "
        "idle_expires_at, absolute_expires_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            new_id(),
            user_id,
            new_id().bytes,
            new_id().bytes,
            NOW,
            NOW + timedelta(days=30),
            NOW + timedelta(days=90),
        ),
    )
    conn.execute(
        "INSERT INTO identity.consents (id, user_id, document, version, accepted_at) "
        "VALUES (%s, %s, 'terms', 'v1', %s)",
        (new_id(), user_id, NOW),
    )
    return user_id


@pytest.fixture(scope="module")
def two_users(test_db: EphemeralDatabase) -> Iterator[tuple[uuid.UUID, uuid.UUID]]:
    with owner_connection(test_db) as conn:
        a, b = _make_user(conn, "alice"), _make_user(conn, "bob")
    yield a, b
    with owner_connection(test_db) as conn:
        conn.execute("DELETE FROM identity.users WHERE id IN (%s, %s)", (a, b))


def _as(conn: psycopg.Connection, user_id: uuid.UUID | None) -> None:
    conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id) if user_id else "",))


def _owner_column(table: str) -> str:
    return "id" if table == "identity.users" else "user_id"


@pytest.mark.parametrize("table", IDENTITY_TABLES)
def test_user_sees_only_own_rows(
    test_db: EphemeralDatabase, two_users: tuple[uuid.UUID, uuid.UUID], table: str
) -> None:
    alice, _bob = two_users
    col = _owner_column(table)
    with role_connection(test_db, "app_api") as conn:
        _as(conn, alice)
        owners = {row[0] for row in conn.execute(f"SELECT {col} FROM {table}").fetchall()}
        assert owners == {alice}
        conn.rollback()


@pytest.mark.parametrize("table", IDENTITY_TABLES)
def test_no_context_sees_nothing(
    test_db: EphemeralDatabase, two_users: tuple[uuid.UUID, uuid.UUID], table: str
) -> None:
    with role_connection(test_db, "app_api") as conn:
        _as(conn, None)
        assert conn.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)
        conn.rollback()


@pytest.mark.parametrize("table", IDENTITY_TABLES)
def test_user_cannot_change_or_delete_another_users_rows(
    test_db: EphemeralDatabase, two_users: tuple[uuid.UUID, uuid.UUID], table: str
) -> None:
    alice, bob = two_users
    col = _owner_column(table)
    with role_connection(test_db, "app_api") as conn:
        _as(conn, alice)
        updated = conn.execute(
            f"UPDATE {table} SET created_at = created_at WHERE {col} = %s",
            (bob,),
        )
        assert updated.rowcount == 0
        deleted = conn.execute(f"DELETE FROM {table} WHERE {col} = %s", (bob,))
        assert deleted.rowcount == 0
        conn.rollback()


def test_user_cannot_insert_rows_for_another_user(
    test_db: EphemeralDatabase, two_users: tuple[uuid.UUID, uuid.UUID]
) -> None:
    alice, bob = two_users
    with role_connection(test_db, "app_api") as conn:
        _as(conn, alice)
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="row-level security"):
            conn.execute(
                "INSERT INTO identity.consents (id, user_id, document, version, accepted_at) "
                "VALUES (%s, %s, 'privacy', 'v9', %s)",
                (new_id(), bob, NOW),
            )
        conn.rollback()


def test_identity_tables_have_rls_enabled_with_user_policy(test_db: EphemeralDatabase) -> None:
    with owner_connection(test_db) as conn:
        rows = conn.execute(
            "SELECT n.nspname || '.' || c.relname, c.relrowsecurity, "
            "EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid AND p.polname = 'user_isolation') "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'identity' AND c.relkind = 'r' ORDER BY 1"
        ).fetchall()
    assert {r[0] for r in rows} == set(IDENTITY_TABLES)
    assert all(r[1] and r[2] for r in rows), rows


@pytest.mark.parametrize("role", ["app_ingest", "app_readonly"])
def test_lookup_functions_are_not_executable_by_other_roles(
    test_db: EphemeralDatabase, role: str
) -> None:
    with role_connection(test_db, role) as conn:
        for call in (
            "SELECT * FROM identity.find_session('\\x00'::bytea)",
            "SELECT * FROM identity.find_user_by_idp('x')",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(call)
            conn.rollback()


def test_session_lookup_returns_only_the_matching_session(
    test_db: EphemeralDatabase, two_users: tuple[uuid.UUID, uuid.UUID]
) -> None:
    alice, _ = two_users
    with owner_connection(test_db) as owner:
        row = owner.execute(
            "SELECT token_hash FROM identity.sessions WHERE user_id = %s", (alice,)
        ).fetchone()
    assert row is not None
    with role_connection(test_db, "app_api") as conn:
        found = conn.execute("SELECT user_id FROM identity.find_session(%s)", (row[0],)).fetchall()
        assert found == [(alice,)]
        assert conn.execute(
            "SELECT count(*) FROM identity.find_session(%s)", (b"no-such-hash",)
        ).fetchone() == (0,)
        conn.rollback()
