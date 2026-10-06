"""Every org-scoped endpoint, discovered from the app itself, so new endpoints are covered automatically.

- An outsider (not a member, no grant) gets 404 on every `/v1/orgs/{org_id}/...` route and method.
- A member of an org holding an ACTIVE read grant never gets a 2xx from a write (POST/PUT/PATCH/DELETE).
- After revocation, the grantee gets 404 everywhere, on the next request.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator

import pytest

from app.platform.config import Settings
from tests.integration.auth_support import AuthHarness, auth_harness
from tests.integration.tenancy_support import (
    accept_grant,
    create_org,
    idem,
    new_actor,
    revoke_grant,
    share,
)

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


@pytest.fixture
async def h(api_settings: Settings) -> AsyncIterator[AuthHarness]:
    async with auth_harness(api_settings) as harness:
        yield harness


def org_routes(h: AuthHarness) -> list[tuple[str, str]]:
    """From the OpenAPI document: the public catalogue of endpoints (internal-only routes aren't org-scoped)."""
    routes = [
        (method.upper(), path)
        for path, operations in h.app.openapi()["paths"].items()
        if path.startswith("/v1/orgs/{org_id}")
        for method in operations
    ]
    assert len(routes) >= 11, "route discovery found too little; did the prefix change?"
    return sorted(routes)


def fill(path: str, org_id: uuid.UUID) -> str:
    path = path.replace("{org_id}", str(org_id))
    return re.sub(r"\{[a-z_]+\}", lambda _: str(uuid.uuid4()), path)


BODIES = {
    "/v1/orgs/{org_id}/invitations": {"email": "x@example.com", "role": "member"},
    "/v1/orgs/{org_id}/members/{user_id}": {"role": "owner"},
    "/v1/orgs/{org_id}/access-grants": {
        "other_org_id": str(uuid.uuid4()),
        "direction": "share",
        "scope": "read",
    },
}


async def test_outsiders_get_404_on_every_org_route(h: AuthHarness) -> None:
    owner = await new_actor(h, "owner")
    org_id = await create_org(owner, "company")
    outsider = await new_actor(h, "outsider")
    for method, path in org_routes(h):
        response = await outsider.client.request(
            method,
            fill(path, org_id),
            json=BODIES.get(path) if method in UNSAFE else None,
            headers=outsider.headers(**idem()),
        )
        assert response.status_code == 404, (method, path, response.status_code, response.text)


async def test_grantees_read_but_never_write_and_lose_access_on_revoke(h: AuthHarness) -> None:
    founder = await new_actor(h, "founder")
    company = await create_org(founder, "company")
    ca = await new_actor(h, "ca")
    firm = await create_org(ca, "ca_firm")
    grant = (await share(founder, company, firm)).json()
    assert (await accept_grant(ca, firm, grant["id"])).status_code == 200

    assert (await ca.client.get(f"/v1/orgs/{company}")).status_code == 200
    for method, path in org_routes(h):
        if method not in UNSAFE:
            continue
        response = await ca.client.request(
            method,
            fill(path, company),
            json=BODIES.get(path),
            headers=ca.headers(**idem()),
        )
        assert not 200 <= response.status_code < 300, (method, path, response.text)
        assert response.status_code in (403, 404, 409, 422), (method, path, response.status_code)

    assert (await revoke_grant(founder, company, grant["id"])).status_code == 200
    for method, path in org_routes(h):
        response = await ca.client.request(
            method,
            fill(path, company),
            json=BODIES.get(path) if method in UNSAFE else None,
            headers=ca.headers(**idem()),
        )
        assert response.status_code == 404, (method, path, response.status_code)
