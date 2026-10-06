"""Organisations, members, invitations and idempotency through the API (FR-PLT-02..05, api-conventions §4)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import psycopg
import pytest

from app.platform.config import Settings
from tests.integration.auth_support import AuthHarness, auth_harness
from tests.integration.tenancy_support import (
    accept,
    add_member,
    audit_rows,
    create_org,
    idem,
    invite,
    new_actor,
    token_from_link,
    unique_email,
)
from tests.support.db import EphemeralDatabase, admin_connection, role_connection


@pytest.fixture
async def h(api_settings: Settings) -> AsyncIterator[AuthHarness]:
    async with auth_harness(api_settings) as harness:
        yield harness


# --- organisations -------------------------------------------------------------------------------------


async def test_create_org_makes_the_creator_owner_and_is_audited(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    owner = await new_actor(h, "owner")
    response = await owner.client.post(
        "/v1/orgs",
        json={"type": "company", "name": "  Acme Robotics  "},
        headers=owner.headers(**idem()),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Acme Robotics"
    assert body["role"] == "owner"
    org_id = body["id"]

    listed = (await owner.client.get("/v1/orgs")).json()["items"]
    assert [o["id"] for o in listed] == [org_id]
    detail = (await owner.client.get(f"/v1/orgs/{org_id}")).json()
    assert detail["access"] == "owner"

    [row] = audit_rows(test_db, "org.created", org_id)
    assert row["actor_user_id"] == owner.user_id
    assert str(row["org_id"]) == org_id
    assert row["metadata"] == {"type": "company"}


def test_creator_cannot_insert_org_with_returning(test_db: EphemeralDatabase) -> None:
    """Why the service never uses RETURNING: the SELECT policy applies and the creator isn't a member yet."""
    user_id = uuid.uuid7()
    with admin_connection(test_db) as admin:
        admin.execute(
            "INSERT INTO identity.users (id, email, display_name, idp_user_id, age_confirmed_at) "
            "VALUES (%s, %s, 'R', %s, now())",
            (user_id, unique_email("returning"), f"rls|{user_id}"),
        )
    with role_connection(test_db, "app_api") as conn:
        conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id),))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO tenancy.organizations (id, type, name, created_by) "
                "VALUES (%s, 'company', 'X', %s) RETURNING id",
                (uuid.uuid7(), user_id),
            )
        conn.rollback()
        # The same insert without RETURNING is allowed.
        conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id),))
        conn.execute(
            "INSERT INTO tenancy.organizations (id, type, name, created_by) VALUES (%s, 'company', 'X', %s)",
            (uuid.uuid7(), user_id),
        )
        conn.rollback()


async def test_org_creation_is_idempotent_per_user(h: AuthHarness) -> None:
    owner = await new_actor(h, "owner")
    key = idem()
    body = {"type": "team", "name": "Night owls"}
    first = await owner.client.post("/v1/orgs", json=body, headers=owner.headers(**key))
    replay = await owner.client.post("/v1/orgs", json=body, headers=owner.headers(**key))
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert len((await owner.client.get("/v1/orgs")).json()["items"]) == 1

    different = await owner.client.post(
        "/v1/orgs", json={"type": "team", "name": "Other"}, headers=owner.headers(**key)
    )
    assert different.status_code == 409
    assert different.json()["code"] == "idempotency_key_conflict"

    other_user = await new_actor(h, "other")
    theirs = await other_user.client.post("/v1/orgs", json=body, headers=other_user.headers(**key))
    assert theirs.status_code == 201
    assert theirs.json()["id"] != first.json()["id"], "keys are per user"


async def test_idempotency_key_is_required_and_must_be_a_uuid(h: AuthHarness) -> None:
    owner = await new_actor(h, "owner")
    body = {"type": "team", "name": "T"}
    missing = await owner.client.post("/v1/orgs", json=body, headers=owner.headers())
    assert missing.status_code == 400
    bad = await owner.client.post(
        "/v1/orgs", json=body, headers=owner.headers(**{"Idempotency-Key": "abc"})
    )
    assert bad.status_code == 400


async def test_idempotency_key_expires_after_24_hours(h: AuthHarness) -> None:
    owner = await new_actor(h, "owner")
    key = idem()
    body = {"type": "team", "name": "Again"}
    first = await owner.client.post("/v1/orgs", json=body, headers=owner.headers(**key))
    h.clock.advance(timedelta(hours=24, seconds=1))
    later = await owner.client.post("/v1/orgs", json=body, headers=owner.headers(**key))
    assert later.status_code == 201
    assert later.json()["id"] != first.json()["id"]


async def test_campus_orgs_are_not_created_in_the_mvp(h: AuthHarness) -> None:
    owner = await new_actor(h, "owner")
    response = await owner.client.post(
        "/v1/orgs", json={"type": "campus", "name": "U"}, headers=owner.headers(**idem())
    )
    assert response.status_code == 400


async def test_non_members_get_404_for_existing_and_missing_orgs(h: AuthHarness) -> None:
    owner = await new_actor(h, "owner")
    org_id = await create_org(owner)
    outsider = await new_actor(h, "outsider")
    for path in ("", "/members", "/invitations", "/access-grants"):
        assert (await outsider.client.get(f"/v1/orgs/{org_id}{path}")).status_code == 404
        assert (await outsider.client.get(f"/v1/orgs/{uuid.uuid4()}{path}")).status_code == 404
    write = await outsider.client.post(
        f"/v1/orgs/{org_id}/invitations",
        json={"email": unique_email(), "role": "member"},
        headers=outsider.headers(**idem()),
    )
    assert write.status_code == 404


# --- members -------------------------------------------------------------------------------------------


async def test_members_see_the_roster_with_names(h: AuthHarness) -> None:
    owner = await new_actor(h, "owner", name="Olga Owner")
    org_id = await create_org(owner)
    viewer = await add_member(h, owner, org_id, "viewer")
    roster = (await viewer.client.get(f"/v1/orgs/{org_id}/members")).json()["items"]
    by_user = {m["user_id"]: m for m in roster}
    assert by_user[str(owner.user_id)]["display_name"] == "Olga Owner"
    assert by_user[str(owner.user_id)]["role"] == "owner"
    assert by_user[str(viewer.user_id)]["email"] == viewer.email
    assert by_user[str(viewer.user_id)]["role"] == "viewer"


async def test_only_owners_change_roles_and_it_is_audited(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    owner = await new_actor(h, "owner")
    org_id = await create_org(owner)
    member = await add_member(h, owner, org_id, "member")
    viewer = await add_member(h, owner, org_id, "viewer")

    denied = await member.client.patch(
        f"/v1/orgs/{org_id}/members/{viewer.user_id}",
        json={"role": "owner"},
        headers=member.headers(),
    )
    assert denied.status_code == 403
    ok = await owner.client.patch(
        f"/v1/orgs/{org_id}/members/{viewer.user_id}",
        json={"role": "member"},
        headers=owner.headers(),
    )
    assert ok.status_code == 204
    [row] = audit_rows(test_db, "member.role_changed", viewer.user_id)
    assert row["metadata"] == {"from": "viewer", "to": "member"}
    assert row["actor_user_id"] == owner.user_id


async def test_last_owner_cannot_be_demoted_or_leave(h: AuthHarness) -> None:
    owner = await new_actor(h, "owner")
    org_id = await create_org(owner)
    demote = await owner.client.patch(
        f"/v1/orgs/{org_id}/members/{owner.user_id}",
        json={"role": "member"},
        headers=owner.headers(),
    )
    assert demote.status_code == 409
    assert demote.json()["code"] == "last_owner"
    leave = await owner.client.delete(
        f"/v1/orgs/{org_id}/members/{owner.user_id}", headers=owner.headers()
    )
    assert leave.status_code == 409
    assert (await owner.client.get(f"/v1/orgs/{org_id}")).status_code == 200

    co_owner = await add_member(h, owner, org_id, "owner")
    assert (
        await owner.client.delete(
            f"/v1/orgs/{org_id}/members/{owner.user_id}", headers=owner.headers()
        )
    ).status_code == 204
    assert (await co_owner.client.get(f"/v1/orgs/{org_id}")).json()["access"] == "owner"


async def test_owner_removes_a_member_and_a_member_can_leave(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    owner = await new_actor(h, "owner")
    org_id = await create_org(owner)
    removed = await add_member(h, owner, org_id, "member")
    leaver = await add_member(h, owner, org_id, "viewer")

    other_member_tries = await leaver.client.delete(
        f"/v1/orgs/{org_id}/members/{removed.user_id}", headers=leaver.headers()
    )
    assert other_member_tries.status_code == 403

    assert (
        await owner.client.delete(
            f"/v1/orgs/{org_id}/members/{removed.user_id}", headers=owner.headers()
        )
    ).status_code == 204
    assert (await removed.client.get(f"/v1/orgs/{org_id}")).status_code == 404

    assert (
        await leaver.client.delete(
            f"/v1/orgs/{org_id}/members/{leaver.user_id}", headers=leaver.headers()
        )
    ).status_code == 204
    assert (await leaver.client.get(f"/v1/orgs/{org_id}")).status_code == 404

    assert (
        audit_rows(test_db, "member.removed", removed.user_id)[0]["actor_user_id"] == owner.user_id
    )
    assert audit_rows(test_db, "member.left", leaver.user_id)[0]["actor_user_id"] == leaver.user_id


# --- invitations ---------------------------------------------------------------------------------------


async def test_invitation_flow_end_to_end(h: AuthHarness, test_db: EphemeralDatabase) -> None:
    owner = await new_actor(h, "owner")
    org_id = await create_org(owner, name="Acme")
    invitee = await new_actor(h, "invitee")
    created = await owner.client.post(
        f"/v1/orgs/{org_id}/invitations",
        json={"email": invitee.email, "role": "viewer"},
        headers=owner.headers(**idem()),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["link_available"] is True
    assert body["invite_link"].startswith(f"{h.settings.app_origin}/invite#token=")
    token = token_from_link(body["invite_link"])

    listed = (await owner.client.get(f"/v1/orgs/{org_id}/invitations")).json()["items"]
    assert [i["email"] for i in listed] == [invitee.email]

    preview = await invitee.client.post(
        "/v1/invitations/lookup", json={"token": token}, headers=invitee.headers()
    )
    assert preview.json() == {
        "org_name": "Acme",
        "org_type": "company",
        "role": "viewer",
        "email": invitee.email,
        "email_matches": True,
    }
    accepted = await accept(invitee, token)
    assert accepted.status_code == 200
    assert accepted.json()["role"] == "viewer"
    assert (await invitee.client.get(f"/v1/orgs/{org_id}")).json()["access"] == "viewer"
    assert (await owner.client.get(f"/v1/orgs/{org_id}/invitations")).json()["items"] == []

    again = await accept(invitee, token)
    assert again.status_code == 404, "single use"

    assert audit_rows(test_db, "invitation.created", body["id"])[0]["metadata"] == {
        "role": "viewer"
    }
    [acc] = audit_rows(test_db, "invitation.accepted", body["id"])
    assert acc["actor_user_id"] == invitee.user_id
    assert acc["metadata"] == {"role": "viewer", "email_matched": True}


async def test_only_owners_manage_invitations(h: AuthHarness) -> None:
    owner = await new_actor(h, "owner")
    org_id = await create_org(owner)
    member = await add_member(h, owner, org_id, "member")
    create = await member.client.post(
        f"/v1/orgs/{org_id}/invitations",
        json={"email": unique_email(), "role": "member"},
        headers=member.headers(**idem()),
    )
    assert create.status_code == 403
    assert (await member.client.get(f"/v1/orgs/{org_id}/invitations")).status_code == 403


async def test_email_mismatch_needs_confirmation(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    owner = await new_actor(h, "owner")
    org_id = await create_org(owner)
    token = await invite(owner, org_id, unique_email("someone-else"))
    actor = await new_actor(h, "actual")
    preview = await actor.client.post(
        "/v1/invitations/lookup", json={"token": token}, headers=actor.headers()
    )
    assert preview.json()["email_matches"] is False
    refused = await accept(actor, token)
    assert refused.status_code == 409
    assert refused.json()["code"] == "invitation_email_mismatch"
    confirmed = await accept(actor, token, confirm=True)
    assert confirmed.status_code == 200
    [row] = audit_rows(test_db, "invitation.accepted")[-1:]
    assert row["metadata"]["email_matched"] is False  # type: ignore[index]


async def test_invitations_expire_after_7_days(h: AuthHarness) -> None:
    owner = await new_actor(h, "owner")
    org_id = await create_org(owner)
    invitee = await new_actor(h, "late")
    token = await invite(owner, org_id, invitee.email)
    h.clock.advance(timedelta(days=7, seconds=1))
    assert (await accept(invitee, token)).status_code == 404
    listed = (await owner.client.get(f"/v1/orgs/{org_id}/invitations")).json()["items"]
    assert listed[0]["expired"] is True
    # An expired invitation doesn't block a new one to the same address.
    fresh = await invite(owner, org_id, invitee.email)
    assert (await accept(invitee, fresh)).status_code == 200


async def test_revoked_invitation_cannot_be_used(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    owner = await new_actor(h, "owner")
    org_id = await create_org(owner)
    invitee = await new_actor(h, "revoked")
    created = await owner.client.post(
        f"/v1/orgs/{org_id}/invitations",
        json={"email": invitee.email, "role": "member"},
        headers=owner.headers(**idem()),
    )
    invitation_id = created.json()["id"]
    token = token_from_link(created.json()["invite_link"])
    revoked = await owner.client.delete(
        f"/v1/orgs/{org_id}/invitations/{invitation_id}", headers=owner.headers()
    )
    assert revoked.status_code == 204
    assert (await accept(invitee, token)).status_code == 404
    assert audit_rows(test_db, "invitation.revoked", invitation_id)


async def test_duplicate_open_invitation_and_existing_member(h: AuthHarness) -> None:
    owner = await new_actor(h, "owner")
    org_id = await create_org(owner)
    member = await add_member(h, owner, org_id, "member")
    email = unique_email("dup")
    await invite(owner, org_id, email)
    dup = await owner.client.post(
        f"/v1/orgs/{org_id}/invitations",
        json={"email": email, "role": "member"},
        headers=owner.headers(**idem()),
    )
    assert dup.status_code == 409
    token = await invite(owner, org_id, member.email)
    assert (await accept(member, token)).status_code == 409


async def test_invitation_replay_never_stores_or_returns_the_token(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    owner = await new_actor(h, "owner")
    org_id = await create_org(owner)
    key = idem()
    body = {"email": unique_email("replay"), "role": "member"}
    first = await owner.client.post(
        f"/v1/orgs/{org_id}/invitations", json=body, headers=owner.headers(**key)
    )
    replay = await owner.client.post(
        f"/v1/orgs/{org_id}/invitations", json=body, headers=owner.headers(**key)
    )
    assert first.status_code == replay.status_code == 201
    token = token_from_link(first.json()["invite_link"])
    assert replay.json()["invite_link"] is None
    assert replay.json()["link_available"] is False
    assert replay.json()["id"] == first.json()["id"]

    with admin_connection(test_db) as conn:
        stored = conn.execute(
            "SELECT string_agg(response_body::text, ' ') FROM platform.idempotency_keys"
        ).fetchone()
        token_hash_hex = conn.execute(
            "SELECT encode(token_hash, 'hex') FROM tenancy.invitations WHERE id = %s",
            (first.json()["id"],),
        ).fetchone()
    assert stored is not None and token_hash_hex is not None
    assert token not in stored[0]
    assert "invite#token" not in stored[0]
    assert token_hash_hex[0] not in stored[0]


async def test_invitation_tokens_never_appear_in_urls(h: AuthHarness) -> None:
    """Lookup and accept take the token in the body; GET with a token isn't an endpoint."""
    owner = await new_actor(h, "owner")
    org_id = await create_org(owner)
    token = await invite(owner, org_id, unique_email())
    assert (await owner.client.get(f"/v1/invitations/{token}")).status_code in (404, 405)
