"""Access grants through the API (FR-PART-01/02, data-model.md §4.2, D-29)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest

from app.platform.config import Settings
from tests.integration.auth_support import AuthHarness, auth_harness
from tests.integration.tenancy_support import (
    Actor,
    accept_grant,
    add_member,
    audit_rows,
    create_org,
    idem,
    new_actor,
    revoke_grant,
    share,
    unique_email,
)
from tests.support.db import EphemeralDatabase


@pytest.fixture
async def h(api_settings: Settings) -> AsyncIterator[AuthHarness]:
    async with auth_harness(api_settings) as harness:
        yield harness


async def _company_and_firm(
    h: AuthHarness, firm_type: str = "ca_firm"
) -> tuple[Actor, object, Actor, object]:
    founder = await new_actor(h, "founder")
    company = await create_org(founder, "company", "Acme")
    ca = await new_actor(h, "ca")
    firm = await create_org(ca, firm_type, "Sharma & Co")
    return founder, company, ca, firm


async def test_share_accept_read_revoke(h: AuthHarness, test_db: EphemeralDatabase) -> None:
    founder, company, ca, firm = await _company_and_firm(h)
    firm_staff = await add_member(h, ca, firm, "viewer")  # any member of the firm reads, read-only

    created = await share(founder, company, firm)
    assert created.status_code == 201, created.text
    grant = created.json()
    assert grant["status"] == "pending"
    assert grant["initiated_by"] == "grantor"

    # Pending: the firm sees nothing of the company.
    assert (await firm_staff.client.get(f"/v1/orgs/{company}")).status_code == 404
    listed = (await ca.client.get(f"/v1/orgs/{firm}/access-grants")).json()["items"]
    assert [g["id"] for g in listed] == [grant["id"]]

    # The sharing company can't accept its own offer; the firm's owner can.
    assert (await accept_grant(founder, company, grant["id"])).status_code == 409
    assert (await accept_grant(firm_staff, firm, grant["id"])).status_code == 403
    accepted = await accept_grant(ca, firm, grant["id"])
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "active"

    seen = await firm_staff.client.get(f"/v1/orgs/{company}")
    assert seen.status_code == 200
    assert seen.json()["access"] == "grantee"
    assert seen.json()["name"] == "Acme"

    # Grantees never see the company's people or invitations, and never write.
    assert (await firm_staff.client.get(f"/v1/orgs/{company}/members")).status_code == 403
    assert (await ca.client.get(f"/v1/orgs/{company}/invitations")).status_code == 403
    write = await ca.client.post(
        f"/v1/orgs/{company}/invitations",
        json={"email": unique_email(), "role": "member"},
        headers=ca.headers(**idem()),
    )
    assert write.status_code == 403
    assert (await ca.client.get(f"/v1/orgs/{company}/access-grants")).status_code == 403

    # Revocation takes effect on the next request.
    revoked = await revoke_grant(founder, company, grant["id"])
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert (await firm_staff.client.get(f"/v1/orgs/{company}")).status_code == 404
    assert (await ca.client.get(f"/v1/orgs/{company}")).status_code == 404

    for action in ("grant.created", "grant.accepted", "grant.revoked"):
        [row] = audit_rows(test_db, action, grant["id"])
        assert row["target_table"] == "tenancy.access_grants"
    assert audit_rows(test_db, "grant.accepted", grant["id"])[0]["actor_user_id"] == ca.user_id
    assert audit_rows(test_db, "grant.revoked", grant["id"])[0]["actor_user_id"] == founder.user_id


async def test_incubator_requests_and_company_accepts(h: AuthHarness) -> None:
    founder, company, incubator_owner, incubator = await _company_and_firm(h, "incubator")
    asked = await incubator_owner.client.post(
        f"/v1/orgs/{incubator}/access-grants",
        json={"other_org_id": str(company), "direction": "request", "scope": "read"},
        headers=incubator_owner.headers(),
    )
    assert asked.status_code == 201, asked.text
    grant = asked.json()
    assert grant["initiated_by"] == "grantee"
    assert (await accept_grant(incubator_owner, incubator, grant["id"])).status_code == 409
    assert (await accept_grant(founder, company, grant["id"])).status_code == 200
    assert (await incubator_owner.client.get(f"/v1/orgs/{company}")).json()["access"] == "grantee"
    # The grantee side may also end the relationship.
    assert (await revoke_grant(incubator_owner, incubator, grant["id"])).status_code == 200
    assert (await incubator_owner.client.get(f"/v1/orgs/{company}")).status_code == 404


async def test_manage_grants_are_not_available_yet(h: AuthHarness) -> None:
    founder, company, _, firm = await _company_and_firm(h)
    response = await share(founder, company, firm, scope="manage")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "grant_scope_not_available"
    assert body["title"] == "This access level isn't available yet"


@pytest.mark.parametrize(
    ("grantor_type", "grantee_type"),
    [
        ("company", "company"),
        ("company", "team"),
        ("ca_firm", "incubator"),
        ("team", "ca_firm"),
        ("incubator", "ca_firm"),
    ],
)
async def test_only_company_to_ca_firm_or_incubator(
    h: AuthHarness, grantor_type: str, grantee_type: str
) -> None:
    owner = await new_actor(h, "owner")
    grantor = await create_org(owner, grantor_type)
    grantee = await create_org(owner, grantee_type)
    response = await share(owner, grantor, grantee)
    assert response.status_code == 422, response.text


async def test_one_open_grant_per_pair_and_only_owners_share(h: AuthHarness) -> None:
    founder, company, _, firm = await _company_and_firm(h)
    member = await add_member(h, founder, company, "member")
    assert (await share(member, company, firm)).status_code == 403
    assert (await share(founder, company, firm)).status_code == 201
    assert (await share(founder, company, firm)).status_code == 409


async def test_unknown_org_looks_the_same_as_a_wrong_type(h: AuthHarness) -> None:
    """The type check runs before the foreign key, so the answer never reveals whether an org exists."""
    founder = await new_actor(h, "founder")
    company = await create_org(founder, "company")
    unknown = await share(founder, company, uuid.uuid4())
    other_company = await create_org(await new_actor(h, "other"), "company")
    wrong_type = await share(founder, company, other_company)
    assert unknown.status_code == wrong_type.status_code == 422
    assert unknown.json()["detail"] == wrong_type.json()["detail"]
