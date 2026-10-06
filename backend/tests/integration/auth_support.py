"""Drive the real sign-in flow against the API with the fake identity provider (no mocks of our own code).

The client talks to `https://testserver` so `Secure` cookies are stored and sent, and sends the app's
`Origin` on every request like the SPA does. Redirects are followed by hand because they cross origins
(API -> fake IdP form -> callback -> SPA).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi import FastAPI

from app.main import create_app
from app.modules.identity.providers.base import IdentityProvider
from app.platform.clock import FrozenClock
from app.platform.config import Settings

APP_ORIGIN = "http://localhost:5173"
START = datetime(2026, 10, 6, 4, 30, tzinfo=UTC)


@dataclass
class AuthHarness:
    app: FastAPI
    client: httpx.AsyncClient
    clock: FrozenClock
    settings: Settings

    extra_clients: list[httpx.AsyncClient] = field(default_factory=list)

    def new_client(self) -> httpx.AsyncClient:
        """A second browser against the same app (its own cookie jar). Closed with the harness."""
        client = _client(self.app)
        self.extra_clients.append(client)
        return client


def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(
        app=app, raise_app_exceptions=False, client=("203.0.113.7", 4321)
    )
    return httpx.AsyncClient(
        transport=transport,
        base_url="https://testserver",
        headers={"Origin": APP_ORIGIN, "User-Agent": "pytest-browser/1.0"},
    )


@asynccontextmanager
async def auth_harness(
    settings: Settings,
    *,
    clock: FrozenClock | None = None,
    provider_factory: Callable[[FrozenClock], IdentityProvider] | None = None,
) -> AsyncIterator[AuthHarness]:
    clock = clock or FrozenClock(START)
    provider = provider_factory(clock) if provider_factory else None
    app = create_app(settings, clock=clock, identity_provider=provider)
    async with _client(app) as client:
        harness = AuthHarness(app=app, client=client, clock=clock, settings=settings)
        yield harness
        for extra in harness.extra_clients:
            await extra.aclose()
    await app.state.engine.dispose()


def path_and_query(url: str) -> str:
    parts = urlsplit(url)
    return parts.path + (f"?{parts.query}" if parts.query else "")


def query_of(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


async def begin_login(client: httpx.AsyncClient, return_to: str = "/") -> dict[str, str]:
    """GET /v1/auth/login; returns the fake IdP's query (state, code_challenge, redirect_uri)."""
    response = await client.get("/v1/auth/login", params={"return_to": return_to})
    assert response.status_code == 302, response.text
    return query_of(response.headers["location"])


async def fake_idp_code(
    client: httpx.AsyncClient, idp_query: dict[str, str], *, email: str, name: str
) -> str:
    """Submit the fake IdP form; returns the callback URL (path + query) it redirects to."""
    response = await client.post(
        "/v1/auth/fake/authorize",
        data={**idp_query, "email": email, "display_name": name},
        headers={"Origin": "http://localhost:8000"},
    )
    assert response.status_code == 303, response.text
    return path_and_query(response.headers["location"])


async def callback(client: httpx.AsyncClient, callback_url: str) -> httpx.Response:
    response = await client.get(callback_url)
    assert response.status_code == 303, response.text
    return response


def csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("bo_csrf") or ""}


async def sign_up(
    client: httpx.AsyncClient,
    *,
    email: str = "asha@example.test",
    name: str = "Asha Test",
    return_to: str = "/",
    settings: Settings | None = None,
) -> httpx.Response:
    """Full new-user flow: login -> fake IdP -> callback -> accept 18+ and terms. Returns the signup response."""
    idp = await begin_login(client, return_to)
    response = await callback(client, await fake_idp_code(client, idp, email=email, name=name))
    assert response.headers["location"] == f"{APP_ORIGIN}/welcome", response.headers["location"]
    profile = (await client.get("/v1/auth/signup")).json()
    signup = await client.post(
        "/v1/auth/signup",
        json={
            "age_confirmed": True,
            "terms_version": profile["terms_version"],
            "privacy_version": profile["privacy_version"],
        },
        headers=csrf_headers(client),
    )
    assert signup.status_code == 200, signup.text
    return signup


async def sign_in(
    client: httpx.AsyncClient,
    *,
    email: str = "asha@example.test",
    name: str = "Asha Test",
    return_to: str = "/",
) -> httpx.Response:
    """Existing-user flow. Returns the callback response (303 to the app)."""
    idp = await begin_login(client, return_to)
    return await callback(client, await fake_idp_code(client, idp, email=email, name=name))
