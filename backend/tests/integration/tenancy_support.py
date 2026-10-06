"""Build tenancy scenarios through the real API (fake IdP, real Postgres)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from tests.integration.auth_support import AuthHarness, csrf_headers, sign_up
from tests.support.db import EphemeralDatabase, admin_connection


def unique_email(label: str = "user") -> str:
    # example.com, not example.test: invitation emails are validated and `.test` is a reserved name.
    return f"{label}-{uuid.uuid4().hex[:10]}@example.com"


@dataclass
class Actor:
    client: httpx.AsyncClient
    email: str
    user_id: uuid.UUID

    def headers(self, **extra: str) -> dict[str, str]:
        return csrf_headers(self.client) | extra


async def new_actor(h: AuthHarness, label: str = "user", name: str | None = None) -> Actor:
    client = h.new_client()
    email = unique_email(label)
    await sign_up(client, email=email, name=name or label.title())
    me = (await client.get("/v1/me")).json()
    return Actor(client=client, email=email, user_id=uuid.UUID(me["id"]))


def idem() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


async def create_org(actor: Actor, org_type: str = "company", name: str | None = None) -> uuid.UUID:
    response = await actor.client.post(
        "/v1/orgs",
        json={"type": org_type, "name": name or f"{org_type} {uuid.uuid4().hex[:6]}"},
        headers=actor.headers(**idem()),
    )
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


def token_from_link(link: str) -> str:
    fragment = urlsplit(link).fragment
    assert fragment.startswith("token=")
    return fragment.removeprefix("token=")


async def invite(owner: Actor, org_id: uuid.UUID, email: str, role: str = "member") -> str:
    response = await owner.client.post(
        f"/v1/orgs/{org_id}/invitations",
        json={"email": email, "role": role},
        headers=owner.headers(**idem()),
    )
    assert response.status_code == 201, response.text
    return token_from_link(response.json()["invite_link"])


async def accept(actor: Actor, token: str, *, confirm: bool = False) -> httpx.Response:
    return await actor.client.post(
        "/v1/invitations/accept",
        json={"token": token, "confirm_email_mismatch": confirm},
        headers=actor.headers(),
    )


async def add_member(h: AuthHarness, owner: Actor, org_id: uuid.UUID, role: str) -> Actor:
    actor = await new_actor(h, role)
    token = await invite(owner, org_id, actor.email, role)
    response = await accept(actor, token)
    assert response.status_code == 200, response.text
    return actor


async def share(
    company_owner: Actor, company_id: uuid.UUID, other_id: uuid.UUID, scope: str = "read"
) -> httpx.Response:
    return await company_owner.client.post(
        f"/v1/orgs/{company_id}/access-grants",
        json={"other_org_id": str(other_id), "direction": "share", "scope": scope},
        headers=company_owner.headers(),
    )


async def accept_grant(owner: Actor, org_id: uuid.UUID, grant_id: str) -> httpx.Response:
    return await owner.client.post(
        f"/v1/orgs/{org_id}/access-grants/{grant_id}/accept", headers=owner.headers()
    )


async def revoke_grant(owner: Actor, org_id: uuid.UUID, grant_id: str) -> httpx.Response:
    return await owner.client.post(
        f"/v1/orgs/{org_id}/access-grants/{grant_id}/revoke", headers=owner.headers()
    )


def audit_rows(
    db: EphemeralDatabase, action: str, target_id: object | None = None
) -> list[dict[str, object]]:
    """Audit rows, read as the superuser (the app roles have no SELECT policy on audit.events)."""
    sql = (
        "SELECT actor_user_id, org_id, action, target_table, target_id, metadata, request_id "
        "FROM audit.events WHERE action = %s"
    )
    params: list[object] = [action]
    if target_id is not None:
        sql += " AND target_id = %s"
        params.append(str(target_id))
    with admin_connection(db) as conn:
        cur = conn.execute(sql + " ORDER BY id", params)
        columns = [c.name for c in cur.description or []]
        return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]
