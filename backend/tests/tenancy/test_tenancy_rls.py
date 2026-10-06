"""Cross-tenant suite at the database (ADR-0013): every tenancy table, the company-data template, audit, keys.

Runs as `app_api` with the RLS context set like the app does. The world:
- company C: owner, member, viewer; outsider owns company D
- CA firm F (owner + member): ACTIVE read grant from C
- incubator I: PENDING grant from C; incubator J: REVOKED grant from C
- CA firm G: ACTIVE *manage* grant from C (D-29: reads like read, never writes)
`facts.rls_probe` is a company-data table built with `company_data_policies()`, standing in for the M8 tables
(facts, obligations, ...), which the schema guard forces onto the same template.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import psycopg
import pytest

from app.platform.rls import company_data_policies
from tests.support.db import EphemeralDatabase, admin_connection, role_connection


def _id() -> uuid.UUID:
    return uuid.uuid7()


@dataclass(frozen=True)
class World:
    owner: uuid.UUID
    member: uuid.UUID
    viewer: uuid.UUID
    outsider: uuid.UUID
    ca_owner: uuid.UUID
    ca_member: uuid.UUID
    inc_owner: uuid.UUID
    inc2_owner: uuid.UUID
    ca2_owner: uuid.UUID
    company: uuid.UUID
    other_company: uuid.UUID
    firm: uuid.UUID
    incubator: uuid.UUID
    incubator2: uuid.UUID
    firm2: uuid.UUID
    grant_active: uuid.UUID
    grant_pending: uuid.UUID
    grant_revoked: uuid.UUID
    grant_manage: uuid.UUID
    invitation: uuid.UUID
    invitation_token_hash: bytes
    probe_c: uuid.UUID
    probe_d: uuid.UUID


@pytest.fixture(scope="module")
def world(test_db: EphemeralDatabase) -> Iterator[World]:
    users = {
        name: _id()
        for name in (
            "owner",
            "member",
            "viewer",
            "outsider",
            "ca_owner",
            "ca_member",
            "inc_owner",
            "inc2_owner",
            "ca2_owner",
        )
    }
    orgs = {
        "company": ("company", "owner"),
        "other_company": ("company", "outsider"),
        "firm": ("ca_firm", "ca_owner"),
        "incubator": ("incubator", "inc_owner"),
        "incubator2": ("incubator", "inc2_owner"),
        "firm2": ("ca_firm", "ca2_owner"),
    }
    org_ids = {name: _id() for name in orgs}
    grants = {
        name: _id() for name in ("grant_active", "grant_pending", "grant_revoked", "grant_manage")
    }
    invitation, token_hash = _id(), hashlib.sha256(b"rls-world-token").digest()
    probe_c, probe_d = _id(), _id()

    with admin_connection(test_db) as conn:
        conn.execute(
            "SET session_replication_role = replica"
        )  # set up states the triggers would refuse
        for name, user_id in users.items():
            conn.execute(
                "INSERT INTO identity.users (id, email, display_name, idp_user_id, age_confirmed_at) "
                "VALUES (%s, %s, %s, %s, now())",
                (user_id, f"{name}-{user_id.hex[:8]}@example.com", name, f"rls|{user_id}"),
            )
        for name, (org_type, owner_name) in orgs.items():
            conn.execute(
                "INSERT INTO tenancy.organizations (id, type, name, created_by) VALUES (%s, %s, %s, %s)",
                (org_ids[name], org_type, name, users[owner_name]),
            )
            conn.execute(
                "INSERT INTO tenancy.memberships (org_id, user_id, role) VALUES (%s, %s, 'owner')",
                (org_ids[name], users[owner_name]),
            )
        for user, org, role in (
            ("member", "company", "member"),
            ("viewer", "company", "viewer"),
            ("ca_member", "firm", "member"),
        ):
            conn.execute(
                "INSERT INTO tenancy.memberships (org_id, user_id, role) VALUES (%s, %s, %s)",
                (org_ids[org], users[user], role),
            )
        for grant, grantee, scope, status in (
            ("grant_active", "firm", "read", "active"),
            ("grant_pending", "incubator", "read", "pending"),
            ("grant_revoked", "incubator2", "read", "revoked"),
            ("grant_manage", "firm2", "manage", "active"),
        ):
            conn.execute(
                "INSERT INTO tenancy.access_grants (id, grantor_org_id, grantee_org_id, scope, status, "
                "initiated_by, accepted_at, revoked_at) VALUES (%s, %s, %s, %s, %s, 'grantor', "
                "CASE WHEN %s = 'active' THEN now() END, CASE WHEN %s = 'revoked' THEN now() END)",
                (
                    grants[grant],
                    org_ids["company"],
                    org_ids[grantee],
                    scope,
                    status,
                    status,
                    status,
                ),
            )
        conn.execute(
            "INSERT INTO tenancy.invitations (id, org_id, email, role, token_hash, expires_at, invited_by) "
            "VALUES (%s, %s, 'invitee@example.com', 'viewer', %s, now() + interval '7 days', %s)",
            (invitation, org_ids["company"], token_hash, users["owner"]),
        )
        conn.execute("SET session_replication_role = origin")
        conn.execute(
            "CREATE TABLE facts.rls_probe (id uuid PRIMARY KEY, org_id uuid NOT NULL, v text)"
        )
        for statement in company_data_policies("facts.rls_probe"):
            conn.execute(statement)
        conn.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON facts.rls_probe TO app_api, app_worker"
        )
        conn.execute(
            "INSERT INTO facts.rls_probe VALUES (%s, %s, 'c'), (%s, %s, 'd')",
            (probe_c, org_ids["company"], probe_d, org_ids["other_company"]),
        )

    yield World(
        **users,
        **org_ids,
        **grants,
        invitation=invitation,
        invitation_token_hash=token_hash,
        probe_c=probe_c,
        probe_d=probe_d,
    )

    with admin_connection(test_db) as conn:
        conn.execute("DROP TABLE facts.rls_probe")
        conn.execute("SET session_replication_role = replica")
        conn.execute(
            "DELETE FROM tenancy.organizations WHERE id = ANY(%s)", (list(org_ids.values()),)
        )
        conn.execute("DELETE FROM identity.users WHERE id = ANY(%s)", (list(users.values()),))


@contextmanager
def as_user(
    db: EphemeralDatabase,
    user: uuid.UUID | None,
    org: uuid.UUID | None = None,
    role: str = "app_api",
    token_hash: bytes | None = None,
) -> Iterator[psycopg.Connection]:
    """One transaction as a service role with the RLS context set; always rolled back."""
    with role_connection(db, role) as conn:
        conn.execute(
            "SELECT set_config('app.user_id', %s, true), set_config('app.org_id', %s, true)",
            (str(user) if user else "", str(org) if org else ""),
        )
        if token_hash is not None:
            conn.execute(
                "SELECT set_config('app.invitation_token_hash', %s, true)", (token_hash.hex(),)
            )
        try:
            yield conn
        finally:
            conn.rollback()


def _count(conn: psycopg.Connection, sql: str, *params: object) -> int:
    row = conn.execute(sql, params).fetchone()
    assert row is not None
    return int(row[0])


READERS = ["owner", "member", "viewer", "ca_owner", "ca_member", "ca2_owner"]
NON_READERS = ["outsider", "inc_owner", "inc2_owner"]
EDITORS = ["owner", "member"]
NON_EDITORS = [
    "viewer",
    "ca_owner",
    "ca_member",
    "ca2_owner",
    "outsider",
    "inc_owner",
    "inc2_owner",
]


# --- organisations ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("who", READERS + NON_READERS)
def test_organization_visible_only_to_members_and_active_grantees(
    test_db: EphemeralDatabase, world: World, who: str
) -> None:
    with as_user(test_db, getattr(world, who), world.company) as conn:
        seen = _count(
            conn, "SELECT count(*) FROM tenancy.organizations WHERE id = %s", world.company
        )
    assert seen == (1 if who in READERS else 0)


@pytest.mark.parametrize("who", ["member", "viewer", "ca_owner", "outsider"])
def test_only_owners_update_the_organization(
    test_db: EphemeralDatabase, world: World, who: str
) -> None:
    with as_user(test_db, getattr(world, who), world.company) as conn:
        updated = conn.execute(
            "UPDATE tenancy.organizations SET name = 'hijacked' WHERE id = %s", (world.company,)
        )
        assert updated.rowcount == 0
    with as_user(test_db, world.owner, world.company) as conn:
        assert (
            conn.execute(
                "UPDATE tenancy.organizations SET name = 'renamed' WHERE id = %s", (world.company,)
            ).rowcount
            == 1
        )


# --- memberships -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "who", ["owner", "member", "viewer", "ca_owner", "ca_member", "ca2_owner", "outsider"]
)
def test_roster_visible_to_members_only_never_to_grantees(
    test_db: EphemeralDatabase, world: World, who: str
) -> None:
    with as_user(test_db, getattr(world, who), world.company) as conn:
        seen = _count(
            conn, "SELECT count(*) FROM tenancy.memberships WHERE org_id = %s", world.company
        )
    assert seen == (3 if who in ("owner", "member", "viewer") else 0)


@pytest.mark.parametrize("who", ["member", "viewer", "ca_owner", "ca2_owner", "outsider"])
def test_only_owners_administer_memberships(
    test_db: EphemeralDatabase, world: World, who: str
) -> None:
    actor = getattr(world, who)
    with as_user(test_db, actor, world.company) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO tenancy.memberships (org_id, user_id, role) VALUES (%s, %s, 'owner')",
                (world.company, world.outsider if who != "outsider" else world.inc_owner),
            )
    with as_user(test_db, actor, world.company) as conn:
        assert (
            conn.execute(
                "UPDATE tenancy.memberships SET role = 'owner' WHERE org_id = %s AND user_id = %s",
                (world.company, world.viewer),
            ).rowcount
            == 0
        )
        assert (
            conn.execute(
                "DELETE FROM tenancy.memberships WHERE org_id = %s AND user_id = %s",
                (world.company, world.owner),
            ).rowcount
            == 0
        )


def test_last_owner_cannot_leave_at_commit(test_db: EphemeralDatabase, world: World) -> None:
    with role_connection(test_db, "app_api") as conn:
        conn.execute("SELECT set_config('app.user_id', %s, true)", (str(world.owner),))
        assert (
            conn.execute(
                "DELETE FROM tenancy.memberships WHERE org_id = %s AND user_id = %s",
                (world.company, world.owner),
            ).rowcount
            == 1
        )
        with pytest.raises(psycopg.errors.CheckViolation, match="last_owner"):
            conn.commit()


def test_bootstrap_only_by_the_creator_only_for_themselves_only_once(
    test_db: EphemeralDatabase, world: World
) -> None:
    new_org = _id()
    with as_user(test_db, world.outsider, new_org) as conn:
        conn.execute(
            "INSERT INTO tenancy.organizations (id, type, name, created_by) VALUES (%s, 'team', 'T', %s)",
            (new_org, world.outsider),
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):  # not for someone else
            with conn.transaction():
                conn.execute(
                    "INSERT INTO tenancy.memberships (org_id, user_id, role) VALUES (%s, %s, 'owner')",
                    (new_org, world.viewer),
                )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):  # not as a lesser role
            with conn.transaction():
                conn.execute(
                    "INSERT INTO tenancy.memberships (org_id, user_id, role) VALUES (%s, %s, 'member')",
                    (new_org, world.outsider),
                )
        conn.execute(
            "INSERT INTO tenancy.memberships (org_id, user_id, role) VALUES (%s, %s, 'owner')",
            (new_org, world.outsider),
        )
        conn.execute("SELECT set_config('app.user_id', %s, true)", (str(world.viewer),))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):  # once: no second bootstrap
            conn.execute(
                "INSERT INTO tenancy.memberships (org_id, user_id, role) VALUES (%s, %s, 'owner')",
                (new_org, world.viewer),
            )


def test_nobody_creates_an_org_in_someone_elses_name(
    test_db: EphemeralDatabase, world: World
) -> None:
    with as_user(test_db, world.outsider) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO tenancy.organizations (id, type, name, created_by) VALUES (%s, 'team', 'T', %s)",
                (_id(), world.viewer),
            )


# --- invitations -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["owner", "member", "viewer", "ca_owner", "outsider"])
def test_invitations_visible_to_owners_only(
    test_db: EphemeralDatabase, world: World, who: str
) -> None:
    with as_user(test_db, getattr(world, who), world.company) as conn:
        seen = _count(
            conn, "SELECT count(*) FROM tenancy.invitations WHERE org_id = %s", world.company
        )
    assert seen == (1 if who == "owner" else 0)


@pytest.mark.parametrize("who", ["member", "viewer", "ca_owner"])
def test_non_owners_cannot_create_invitations(
    test_db: EphemeralDatabase, world: World, who: str
) -> None:
    with as_user(test_db, getattr(world, who), world.company) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO tenancy.invitations (id, org_id, email, role, token_hash, expires_at) "
                "VALUES (%s, %s, 'x@example.com', 'owner', %s, now() + interval '1 day')",
                (_id(), world.company, _id().bytes),
            )


def test_accept_needs_the_right_token_and_role(test_db: EphemeralDatabase, world: World) -> None:
    insert = "INSERT INTO tenancy.memberships (org_id, user_id, role) VALUES (%s, %s, %s)"
    with as_user(test_db, world.outsider, world.company, token_hash=b"wrong-token-hash") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(insert, (world.company, world.outsider, "viewer"))
    with as_user(
        test_db, world.outsider, world.company, token_hash=world.invitation_token_hash
    ) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):  # invited as viewer, not owner
            with conn.transaction():
                conn.execute(insert, (world.company, world.outsider, "owner"))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):  # only for oneself
            with conn.transaction():
                conn.execute(insert, (world.company, world.inc_owner, "viewer"))
        conn.execute(insert, (world.company, world.outsider, "viewer"))
        assert (
            conn.execute(
                "UPDATE tenancy.invitations SET accepted_at = now() WHERE id = %s",
                (world.invitation,),
            ).rowcount
            == 1
        )


def test_expired_invitation_cannot_be_accepted_even_by_direct_sql(
    test_db: EphemeralDatabase, world: World
) -> None:
    """Migration 0006: the token check also requires expires_at > now(), whatever the app's clock says."""
    expired_id, token_hash = _id(), hashlib.sha256(b"expired-token").digest()
    with admin_connection(test_db) as conn:
        conn.execute(
            "INSERT INTO tenancy.invitations (id, org_id, email, role, token_hash, expires_at, invited_by) "
            "VALUES (%s, %s, 'late@example.com', 'viewer', %s, now() - interval '1 minute', %s)",
            (expired_id, world.company, token_hash, world.owner),
        )
    try:
        with as_user(test_db, world.outsider, world.company, token_hash=token_hash) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "INSERT INTO tenancy.memberships (org_id, user_id, role) VALUES (%s, %s, 'viewer')",
                    (world.company, world.outsider),
                )
        with as_user(test_db, world.outsider, world.company, token_hash=token_hash) as conn:
            updated = conn.execute(
                "UPDATE tenancy.invitations SET accepted_at = now() WHERE id = %s", (expired_id,)
            )
            assert updated.rowcount == 0
            assert (
                _count(conn, "SELECT count(*) FROM tenancy.invitations WHERE id = %s", expired_id)
                == 0
            )
    finally:
        with admin_connection(test_db) as conn:
            conn.execute("DELETE FROM tenancy.invitations WHERE id = %s", (expired_id,))


@pytest.mark.parametrize(
    "change",
    ["role = 'owner'", "email = 'me@example.com'", "expires_at = now() + interval '1 year'"],
)
def test_token_holder_can_only_set_accepted_at(
    test_db: EphemeralDatabase, world: World, change: str
) -> None:
    with as_user(
        test_db, world.outsider, world.company, token_hash=world.invitation_token_hash
    ) as conn:
        with pytest.raises(psycopg.errors.CheckViolation, match="invitation_guard"):
            conn.execute(
                f"UPDATE tenancy.invitations SET accepted_at = now(), {change} WHERE id = %s",
                (world.invitation,),
            )


def test_token_holder_cannot_accept_twice(test_db: EphemeralDatabase, world: World) -> None:
    with as_user(
        test_db, world.outsider, world.company, token_hash=world.invitation_token_hash
    ) as conn:
        conn.execute(
            "UPDATE tenancy.invitations SET accepted_at = now() WHERE id = %s", (world.invitation,)
        )
        # Accepted: the token no longer matches, so the row is invisible and a second insert is refused.
        assert (
            conn.execute(
                "UPDATE tenancy.invitations SET accepted_at = now() WHERE id = %s",
                (world.invitation,),
            ).rowcount
            == 0
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO tenancy.memberships (org_id, user_id, role) VALUES (%s, %s, 'viewer')",
                (world.company, world.outsider),
            )


# --- access grants ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("who", "expected"),
    [("owner", 4), ("viewer", 4), ("ca_member", 1), ("inc_owner", 1), ("outsider", 0)],
)
def test_grants_visible_to_members_of_either_side(
    test_db: EphemeralDatabase, world: World, who: str, expected: int
) -> None:
    with as_user(test_db, getattr(world, who)) as conn:
        seen = _count(
            conn,
            "SELECT count(*) FROM tenancy.access_grants WHERE grantor_org_id = %s",
            world.company,
        )
    assert seen == expected


def test_grant_transitions_are_enforced(test_db: EphemeralDatabase, world: World) -> None:
    # The sharing side can't accept its own offer.
    with as_user(test_db, world.owner) as conn:
        with pytest.raises(psycopg.errors.CheckViolation, match="grant_transition"):
            conn.execute(
                "UPDATE tenancy.access_grants SET status = 'active', accepted_at = now() WHERE id = %s",
                (world.grant_pending,),
            )
    # A revoked grant never comes back.
    with as_user(test_db, world.owner) as conn:
        with pytest.raises(psycopg.errors.CheckViolation, match="grant_transition"):
            conn.execute(
                "UPDATE tenancy.access_grants SET status = 'active', accepted_at = now(), revoked_at = NULL "
                "WHERE id = %s",
                (world.grant_revoked,),
            )
    # Nobody widens a grant.
    with as_user(test_db, world.ca_owner) as conn:
        with pytest.raises(psycopg.errors.CheckViolation, match="grant_immutable"):
            conn.execute(
                "UPDATE tenancy.access_grants SET scope = 'manage' WHERE id = %s",
                (world.grant_active,),
            )
    # A grantee member who isn't an owner can't change anything.
    with as_user(test_db, world.ca_member) as conn:
        assert (
            conn.execute(
                "UPDATE tenancy.access_grants SET status = 'revoked', revoked_at = now() WHERE id = %s",
                (world.grant_active,),
            ).rowcount
            == 0
        )
    # The invited side's owner accepts.
    with as_user(test_db, world.inc_owner) as conn:
        assert (
            conn.execute(
                "UPDATE tenancy.access_grants SET status = 'active', accepted_at = now() WHERE id = %s",
                (world.grant_pending,),
            ).rowcount
            == 1
        )


# --- company data: read stays read ------------------------------------------------------------------------


@pytest.mark.parametrize("who", READERS + NON_READERS)
def test_company_data_reads(test_db: EphemeralDatabase, world: World, who: str) -> None:
    with as_user(test_db, getattr(world, who), world.company) as conn:
        rows = conn.execute("SELECT id FROM facts.rls_probe").fetchall()
    assert rows == ([(world.probe_c,)] if who in READERS else [])


@pytest.mark.parametrize("who", EDITORS + NON_EDITORS)
def test_company_data_writes_only_by_owners_and_members(
    test_db: EphemeralDatabase, world: World, who: str
) -> None:
    actor = getattr(world, who)
    allowed = who in EDITORS
    with as_user(test_db, actor, world.company) as conn:
        if allowed:
            conn.execute(
                "INSERT INTO facts.rls_probe VALUES (%s, %s, 'new')", (_id(), world.company)
            )
        else:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "INSERT INTO facts.rls_probe VALUES (%s, %s, 'new')", (_id(), world.company)
                )
    with as_user(test_db, actor, world.company) as conn:
        updated = conn.execute(
            "UPDATE facts.rls_probe SET v = 'changed' WHERE id = %s", (world.probe_c,)
        )
        assert updated.rowcount == (1 if allowed else 0)
    with as_user(test_db, actor, world.company) as conn:
        deleted = conn.execute("DELETE FROM facts.rls_probe WHERE id = %s", (world.probe_c,))
        assert deleted.rowcount == (1 if allowed else 0)


def test_company_data_never_crosses_orgs(test_db: EphemeralDatabase, world: World) -> None:
    # Owner of C with the context of D sees nothing of D, and can't write into D.
    with as_user(test_db, world.owner, world.other_company) as conn:
        assert conn.execute("SELECT id FROM facts.rls_probe").fetchall() == []
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO facts.rls_probe VALUES (%s, %s, 'x')", (_id(), world.other_company)
            )
    # Context of C but writing a row tagged D: refused.
    with as_user(test_db, world.owner, world.company) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO facts.rls_probe VALUES (%s, %s, 'x')", (_id(), world.other_company)
            )
    # No context: nothing.
    with as_user(test_db, None) as conn:
        assert conn.execute("SELECT id FROM facts.rls_probe").fetchall() == []


def test_revocation_takes_effect_immediately(test_db: EphemeralDatabase, world: World) -> None:
    with as_user(test_db, world.owner) as conn:
        conn.execute(
            "UPDATE tenancy.access_grants SET status = 'revoked', revoked_at = now() WHERE id = %s",
            (world.grant_active,),
        )
        conn.execute("SELECT set_config('app.user_id', %s, true)", (str(world.ca_member),))
        conn.execute("SELECT set_config('app.org_id', %s, true)", (str(world.company),))
        assert conn.execute("SELECT id FROM facts.rls_probe").fetchall() == []
        assert (
            _count(conn, "SELECT count(*) FROM tenancy.organizations WHERE id = %s", world.company)
            == 0
        )


# --- audit ------------------------------------------------------------------------------------------------

_AUDIT = (
    "INSERT INTO audit.events (actor_user_id, org_id, request_id, action, target_table, target_id) "
    "VALUES (%s, %s, 'r', 'test.event', 't', '1')"
)


@pytest.mark.parametrize("who", ["owner", "viewer", "ca_member", "ca2_owner"])
def test_anyone_acting_in_the_org_writes_audit_rows(
    test_db: EphemeralDatabase, world: World, who: str
) -> None:
    actor = getattr(world, who)
    with as_user(test_db, actor, world.company) as conn:
        conn.execute(_AUDIT, (actor, world.company))
        conn.execute(_AUDIT, (actor, None))


@pytest.mark.parametrize(
    ("who", "actor_of", "org"),
    [
        ("outsider", "outsider", "company"),  # foreign org
        ("inc_owner", "inc_owner", "company"),  # pending grantee
        ("viewer", "owner", "company"),  # spoofed actor
        ("viewer", None, None),  # system row from the API role
    ],
)
def test_audit_refuses_foreign_orgs_spoofed_actors_and_api_system_rows(
    test_db: EphemeralDatabase, world: World, who: str, actor_of: str | None, org: str | None
) -> None:
    with as_user(test_db, getattr(world, who), world.company) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                _AUDIT,
                (
                    getattr(world, actor_of) if actor_of else None,
                    getattr(world, org) if org else None,
                ),
            )


def test_worker_writes_system_rows(test_db: EphemeralDatabase, world: World) -> None:
    with as_user(test_db, None, role="app_worker") as conn:
        conn.execute(_AUDIT, (None, None))
    with as_user(test_db, None, world.company, role="app_worker") as conn:
        conn.execute(_AUDIT, (None, world.company))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(_AUDIT, (None, world.other_company))


@pytest.mark.parametrize(
    "statement", ["UPDATE audit.events SET action = 'x.y'", "DELETE FROM audit.events"]
)
@pytest.mark.parametrize("role", ["app_api", "app_worker"])
def test_audit_is_append_only(
    test_db: EphemeralDatabase, world: World, statement: str, role: str
) -> None:
    with as_user(test_db, world.owner, world.company, role=role) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(statement)


def test_nobody_reads_audit_rows_through_the_app_roles(
    test_db: EphemeralDatabase, world: World
) -> None:
    with as_user(test_db, world.owner, world.company) as conn:
        conn.execute(_AUDIT, (world.owner, world.company))
        assert _count(conn, "SELECT count(*) FROM audit.events") == 0


# --- own-row tables ---------------------------------------------------------------------------------------


def test_idempotency_keys_are_private_to_their_user(
    test_db: EphemeralDatabase, world: World
) -> None:
    key = _id()
    insert = (
        "INSERT INTO platform.idempotency_keys (user_id, key, request_sha256, expires_at) "
        "VALUES (%s, %s, 'x', now() + interval '1 day')"
    )
    with as_user(test_db, world.owner) as conn:
        conn.execute(insert, (world.owner, key))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute(insert, (world.viewer, _id()))
        conn.execute("SELECT set_config('app.user_id', %s, true)", (str(world.viewer),))
        assert _count(conn, "SELECT count(*) FROM platform.idempotency_keys") == 0
