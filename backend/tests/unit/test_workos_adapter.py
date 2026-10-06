"""WorkOS adapter against a stubbed HTTP transport (no live keys, no network)."""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.modules.identity.providers.base import IdentityError
from app.modules.identity.providers.workos import WorkOSIdentityProvider


def _user(**overrides: object) -> dict[str, object]:
    user: dict[str, object] = {
        "object": "user",
        "id": "user_01TEST",
        "first_name": "Asha",
        "last_name": "Test",
        "profile_picture_url": None,
        "email": "asha@example.test",
        "email_verified": True,
        "external_id": None,
        "last_sign_in_at": None,
        "created_at": "2026-10-06T04:30:00.000Z",
        "updated_at": "2026-10-06T04:30:00.000Z",
    }
    user.update(overrides)
    return user


def _provider(handler: httpx.MockTransport) -> WorkOSIdentityProvider:
    client = httpx.AsyncClient(transport=handler)
    return WorkOSIdentityProvider(api_key="sk_test_x", client_id="client_test", http_client=client)


def test_authorization_url_uses_authkit_with_pkce_s256() -> None:
    provider = _provider(httpx.MockTransport(lambda _: httpx.Response(500)))
    url = provider.authorization_url(
        state="state-1",
        code_challenge="challenge-1",
        redirect_uri="http://localhost:8000/v1/auth/callback",
    )
    query = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    assert urlsplit(url).netloc == "api.workos.com"
    assert query["provider"] == "authkit"
    assert query["state"] == "state-1"
    assert query["code_challenge"] == "challenge-1"
    assert query["code_challenge_method"] == "S256"
    assert query["client_id"] == "client_test"
    assert query["redirect_uri"] == "http://localhost:8000/v1/auth/callback"


async def test_exchange_sends_the_verifier_and_maps_the_profile() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"user": _user(), "access_token": "at", "refresh_token": "rt"}
        )

    profile = await _provider(httpx.MockTransport(handler)).exchange_code(
        code="code-1", code_verifier="verifier-1"
    )
    assert seen["path"] == "/user_management/authenticate"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["grant_type"] == "authorization_code"
    assert body["code"] == "code-1"
    assert body["code_verifier"] == "verifier-1"
    assert body["client_id"] == "client_test"
    assert profile.idp_user_id == "user_01TEST"
    assert profile.email == "asha@example.test"
    assert profile.display_name == "Asha Test"


async def test_exchange_rejects_unverified_email() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"user": _user(email_verified=False), "access_token": "a", "refresh_token": "r"},
        )

    with pytest.raises(IdentityError, match="not verified"):
        await _provider(httpx.MockTransport(handler)).exchange_code(code="c", code_verifier="v")


async def test_exchange_maps_api_errors_to_identity_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant", "error_description": "bad code"})

    with pytest.raises(IdentityError):
        await _provider(httpx.MockTransport(handler)).exchange_code(code="c", code_verifier="v")


async def test_exchange_maps_network_failures_to_identity_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(IdentityError):
        await _provider(httpx.MockTransport(handler)).exchange_code(code="c", code_verifier="v")
