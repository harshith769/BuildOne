"""Sessions: expiry, idle extension, revocation and replay, CSRF and Origin checks, re-consent (FR-PLT-01)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
from fastapi import APIRouter
from pydantic import SecretStr, ValidationError

from app.main import create_app
from app.modules.identity.dependencies import CurrentSession
from app.platform.config import Settings
from tests.integration.auth_support import (
    AuthHarness,
    auth_harness,
    csrf_headers,
    sign_in,
    sign_up,
)
from tests.support.db import EphemeralDatabase, owner_connection


def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.test"


@pytest.fixture
async def h(api_settings: Settings) -> AsyncIterator[AuthHarness]:
    async with auth_harness(api_settings) as harness:
        yield harness


def _session_rows(db: EphemeralDatabase, email: str) -> list[tuple[object, ...]]:
    with owner_connection(db) as conn:
        return conn.execute(
            "SELECT s.last_seen_at, s.idle_expires_at, s.absolute_expires_at FROM identity.sessions s "
            "JOIN identity.users u ON u.id = s.user_id WHERE u.email = %s",
            (email,),
        ).fetchall()


# --- expiry --------------------------------------------------------------------------------------------


async def test_session_expires_after_30_idle_days(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    email = unique_email()
    await sign_up(h.client, email=email)
    h.clock.advance(timedelta(days=29, hours=23))
    assert (await h.client.get("/v1/me")).status_code == 200  # activity extends the idle window
    h.clock.advance(timedelta(days=29, hours=23))
    assert (await h.client.get("/v1/me")).status_code == 200
    h.clock.advance(timedelta(days=30))
    expired = await h.client.get("/v1/me")
    assert expired.status_code == 401
    assert expired.json()["code"] == "unauthenticated"
    assert _session_rows(test_db, email) == [], "the expired session row is deleted"


async def test_session_expires_after_90_days_even_when_active(h: AuthHarness) -> None:
    await sign_up(h.client, email=unique_email())
    for _ in range(89):
        h.clock.advance(timedelta(days=1))
        assert (await h.client.get("/v1/me")).status_code == 200
    h.clock.advance(timedelta(days=1))
    assert (await h.client.get("/v1/me")).status_code == 401


async def test_idle_extension_writes_at_most_once_per_hour(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    email = unique_email()
    await sign_up(h.client, email=email)
    [(first_seen, first_idle, _)] = _session_rows(test_db, email)

    h.clock.advance(timedelta(minutes=59))
    await h.client.get("/v1/me")
    assert _session_rows(test_db, email)[0][:2] == (first_seen, first_idle)

    h.clock.advance(timedelta(minutes=1))
    await h.client.get("/v1/me")
    [(seen, idle, absolute)] = _session_rows(test_db, email)
    assert seen == h.clock.now()
    assert idle == h.clock.now() + timedelta(days=30)
    assert idle <= absolute  # type: ignore[operator]


async def test_idle_expiry_never_exceeds_absolute_expiry(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    email = unique_email()
    await sign_up(h.client, email=email)
    for _ in range(88):
        h.clock.advance(timedelta(days=1))
        await h.client.get("/v1/me")
    [(_, idle, absolute)] = _session_rows(test_db, email)
    assert idle == absolute


# --- sign-out, revocation and replay -------------------------------------------------------------------


async def test_logout_then_replaying_the_old_cookie_returns_401(h: AuthHarness) -> None:
    await sign_up(h.client, email=unique_email())
    old_session = h.client.cookies.get("bo_session")
    response = await h.client.post("/v1/auth/logout", headers=csrf_headers(h.client))
    assert response.status_code == 204
    assert h.client.cookies.get("bo_session") is None
    async with h.new_client() as replay:
        replayed = await replay.get("/v1/me", headers={"Cookie": f"bo_session={old_session}"})
    assert replayed.status_code == 401


async def test_list_and_revoke_one_session(h: AuthHarness) -> None:
    email = unique_email()
    await sign_up(h.client, email=email)
    async with h.new_client() as laptop:
        await sign_in(laptop, email=email)
        listed = (await h.client.get("/v1/me/sessions")).json()
        assert listed["next_cursor"] is None
        assert len(listed["items"]) == 2
        current = [s for s in listed["items"] if s["is_current"]]
        other = [s for s in listed["items"] if not s["is_current"]]
        assert len(current) == 1 and len(other) == 1
        assert other[0]["ip"] == "203.0.113.7"
        assert other[0]["user_agent"] == "pytest-browser/1.0"

        revoked = await h.client.delete(
            f"/v1/me/sessions/{other[0]['id']}", headers=csrf_headers(h.client)
        )
        assert revoked.status_code == 204
        assert (await laptop.get("/v1/me")).status_code == 401
        assert (await h.client.get("/v1/me")).status_code == 200


async def test_revoke_all_other_sessions(h: AuthHarness) -> None:
    email = unique_email()
    await sign_up(h.client, email=email)
    async with h.new_client() as b, h.new_client() as c:
        await sign_in(b, email=email)
        await sign_in(c, email=email)
        response = await h.client.post(
            "/v1/me/sessions/revoke-others", headers=csrf_headers(h.client)
        )
        assert response.json() == {"revoked": 2}
        assert (await b.get("/v1/me")).status_code == 401
        assert (await c.get("/v1/me")).status_code == 401
    assert (await h.client.get("/v1/me")).status_code == 200


async def test_cannot_revoke_another_users_session(h: AuthHarness) -> None:
    await sign_up(h.client, email=unique_email())
    async with h.new_client() as mallory:
        await sign_up(mallory, email=unique_email())
        victim_session = (await h.client.get("/v1/me/sessions")).json()["items"][0]["id"]
        response = await mallory.delete(
            f"/v1/me/sessions/{victim_session}", headers=csrf_headers(mallory)
        )
        assert response.status_code == 404
    assert (await h.client.get("/v1/me")).status_code == 200


async def test_unauthenticated_requests_get_401(h: AuthHarness) -> None:
    for method, path in (
        ("GET", "/v1/me"),
        ("GET", "/v1/me/sessions"),
        ("POST", "/v1/me/sessions/revoke-others"),
        ("POST", "/v1/auth/logout"),
    ):
        response = await h.client.request(method, path)
        assert response.status_code == 401, (method, path)
        assert response.headers["content-type"].startswith("application/problem+json")
    garbage = await h.client.get("/v1/me", headers={"Cookie": "bo_session=not-a-real-token"})
    assert garbage.status_code == 401


# --- CSRF and Origin -----------------------------------------------------------------------------------


async def test_unsafe_request_without_csrf_header_is_rejected(h: AuthHarness) -> None:
    await sign_up(h.client, email=unique_email())
    response = await h.client.post("/v1/me/sessions/revoke-others")
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_csrf_header_must_match_the_cookie(h: AuthHarness) -> None:
    await sign_up(h.client, email=unique_email())
    response = await h.client.post(
        "/v1/me/sessions/revoke-others", headers={"X-CSRF-Token": "A" * 43}
    )
    assert response.status_code == 403


async def test_csrf_token_from_another_session_is_rejected(h: AuthHarness) -> None:
    """Header and cookie agree, but belong to another session: the session binding catches it."""
    await sign_up(h.client, email=unique_email())
    async with h.new_client() as other:
        await sign_up(other, email=unique_email())
        foreign = other.cookies.get("bo_csrf") or ""
    response = await h.client.post(
        "/v1/me/sessions/revoke-others",
        headers={
            "X-CSRF-Token": foreign,
            "Cookie": f"bo_session={h.client.cookies.get('bo_session')}; bo_csrf={foreign}",
        },
    )
    assert response.status_code == 403


@pytest.mark.parametrize("origin", [None, "https://evil.example", "http://localhost:5174", "null"])
async def test_unsafe_request_from_another_origin_is_rejected(
    h: AuthHarness, origin: str | None
) -> None:
    await sign_up(h.client, email=unique_email())
    headers = {**csrf_headers(h.client)}
    request = h.client.build_request("POST", "/v1/auth/logout", headers=headers)
    del request.headers["Origin"]
    if origin is not None:
        request.headers["Origin"] = origin
    response = await h.client.send(request)
    assert response.status_code == 403
    assert response.json()["detail"] == "Request origin not allowed"
    assert (await h.client.get("/v1/me")).status_code == 200, "the session was not touched"


async def test_safe_requests_do_not_need_csrf_or_origin(h: AuthHarness) -> None:
    await sign_up(h.client, email=unique_email())
    request = h.client.build_request("GET", "/v1/me")
    del request.headers["Origin"]
    assert (await h.client.send(request)).status_code == 200


# --- re-consent when the terms change ------------------------------------------------------------------


async def test_new_terms_version_requires_consent_and_rotates_the_session(
    api_settings: Settings, test_db: EphemeralDatabase
) -> None:
    email = unique_email()
    async with auth_harness(api_settings) as first:
        await sign_up(first.client, email=email)
        cookies = list(first.client.cookies.jar)
        clock = first.clock

    bumped = api_settings.model_copy(update={"terms_version": "2027-01"})
    async with auth_harness(bumped, clock=clock) as h2:
        for cookie in cookies:  # the same browser, now talking to an API with newer terms
            h2.client.cookies.jar.set_cookie(cookie)
        me = await h2.client.get("/v1/me")
        assert me.status_code == 200
        assert me.json()["consent_required"] is True
        assert me.json()["terms_version"] == "2027-01"

        # The /v1/me family and sign-out stay available while consent is pending (so a user can always
        # see and end their sessions); every other authenticated route returns consent_required (next test).
        assert (await h2.client.get("/v1/me/sessions")).status_code == 200

        old_token = h2.client.cookies.get("bo_session")
        accepted = await h2.client.post(
            "/v1/me/consent",
            json={"terms_version": "2027-01", "privacy_version": bumped.privacy_version},
            headers=csrf_headers(h2.client),
        )
        assert accepted.status_code == 204
        assert h2.client.cookies.get("bo_session") != old_token, "session token rotated"
        assert (await h2.client.get("/v1/me")).json()["consent_required"] is False
        async with h2.new_client() as replay:
            old = await replay.get("/v1/me", headers={"Cookie": f"bo_session={old_token}"})
        assert old.status_code == 401

    with owner_connection(test_db) as conn:
        versions = {
            row[0]
            for row in conn.execute(
                "SELECT c.version FROM identity.consents c JOIN identity.users u ON u.id = c.user_id "
                "WHERE u.email = %s AND c.document = 'terms'",
                (email,),
            ).fetchall()
        }
    assert versions == {api_settings.terms_version, "2027-01"}


async def test_consent_required_blocks_gated_routes(api_settings: Settings) -> None:
    """Any route using `current_session` (not the consent-pending variant) returns 403 consent_required."""
    async with auth_harness(api_settings) as first:
        await sign_up(first.client, email=unique_email())
        cookies = list(first.client.cookies.jar)
        clock = first.clock
    bumped = api_settings.model_copy(update={"privacy_version": "2027-02"})
    async with auth_harness(bumped, clock=clock) as h2:
        probe = APIRouter()

        @probe.get("/v1/_test/gated")
        async def gated(ctx: CurrentSession) -> dict[str, str]:
            return {"user_id": str(ctx.user_id)}

        h2.app.include_router(probe)
        for cookie in cookies:  # the same browser, now talking to an API with newer terms
            h2.client.cookies.jar.set_cookie(cookie)
        response = await h2.client.get("/v1/_test/gated")
        assert response.status_code == 403
        assert response.json()["code"] == "consent_required"
        await h2.client.post(
            "/v1/me/consent",
            json={"terms_version": bumped.terms_version, "privacy_version": "2027-02"},
            headers=csrf_headers(h2.client),
        )
        assert (await h2.client.get("/v1/_test/gated")).status_code == 200


# --- fake identity provider exposure -------------------------------------------------------------------


async def test_fake_authorize_route_and_origin_exemption_absent_with_workos(
    api_settings: Settings,
) -> None:
    workos_settings = api_settings.model_copy(
        update={
            "identity_provider": "workos",
            "workos_client_id": "client_test",
            "workos_api_key": SecretStr("sk_test_x"),
        }
    )
    app = create_app(workos_settings)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        get_form = await client.get("/v1/auth/fake/authorize")
        assert get_form.status_code == 404
        # Without the exemption, a cross-origin POST is stopped by the Origin check before routing.
        post_form = await client.post(
            "/v1/auth/fake/authorize",
            data={"email": "a@example.test"},
            headers={"Origin": "http://localhost:8000"},
        )
        assert post_form.status_code == 403
        assert post_form.json()["detail"] == "Request origin not allowed"
    await app.state.engine.dispose()


async def test_fake_authorize_rejects_foreign_redirect_uri(h: AuthHarness) -> None:
    response = await h.client.post(
        "/v1/auth/fake/authorize",
        data={
            "state": "s",
            "code_challenge": "c",
            "redirect_uri": "https://evil.example/cb",
            "email": "a@example.test",
            "display_name": "A",
        },
        headers={"Origin": "http://localhost:8000"},
    )
    assert response.status_code == 400


def test_settings_refuse_fake_provider_in_production() -> None:
    with pytest.raises(ValidationError, match="fake identity provider"):
        Settings(environment="production", database_url="x", secret_key="k" * 40)  # type: ignore[arg-type]
