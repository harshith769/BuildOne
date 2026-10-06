"""Sign-in, sign-up with 18+ and terms consent, state/PKCE checks, open-redirect protection (FR-PLT-01)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest

from app.platform.config import Settings
from tests.integration.auth_support import (
    APP_ORIGIN,
    AuthHarness,
    auth_harness,
    begin_login,
    callback,
    csrf_headers,
    fake_idp_code,
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


def _count(db: EphemeralDatabase, sql: str, *params: object) -> int:
    with owner_connection(db) as conn:
        row = conn.execute(sql, params).fetchone()
    assert row is not None
    return int(row[0])


# --- new user ------------------------------------------------------------------------------------------


async def test_new_user_signs_up_after_confirming_age_and_terms(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    email = unique_email()
    signup = await sign_up(h.client, email=email, name="Asha Test", return_to="/plan?tab=open")
    assert signup.json() == {"return_to": "/plan?tab=open"}
    assert h.client.cookies.get("bo_session")
    assert h.client.cookies.get("bo_signup") is None, "the pending sign-up cookie is cleared"

    me = await h.client.get("/v1/me")
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["email"] == email
    assert body["display_name"] == "Asha Test"
    assert body["consent_required"] is False

    assert _count(test_db, "SELECT count(*) FROM identity.users WHERE email = %s", email) == 1
    assert (
        _count(
            test_db,
            "SELECT count(*) FROM identity.consents c JOIN identity.users u ON u.id = c.user_id "
            "WHERE u.email = %s AND c.version = %s",
            email,
            h.settings.terms_version,
        )
        == 2
    )
    assert (
        _count(
            test_db,
            "SELECT count(*) FROM identity.users WHERE email = %s AND age_confirmed_at IS NOT NULL",
            email,
        )
        == 1
    )


async def test_no_user_row_exists_before_consent(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    email = unique_email()
    idp = await begin_login(h.client)
    response = await callback(h.client, await fake_idp_code(h.client, idp, email=email, name="N"))
    assert response.headers["location"] == f"{APP_ORIGIN}/welcome"
    assert _count(test_db, "SELECT count(*) FROM identity.users WHERE email = %s", email) == 0

    pending = await h.client.get("/v1/auth/signup")
    assert pending.status_code == 200
    assert pending.json()["email"] == email
    assert (await h.client.get("/v1/me")).status_code == 401


async def test_under_18_decline_stores_nothing(h: AuthHarness, test_db: EphemeralDatabase) -> None:
    email = unique_email()
    idp = await begin_login(h.client)
    await callback(h.client, await fake_idp_code(h.client, idp, email=email, name="Young"))
    declined = await h.client.post("/v1/auth/signup/decline")
    assert declined.status_code == 204
    assert _count(test_db, "SELECT count(*) FROM identity.users WHERE email = %s", email) == 0
    assert (await h.client.get("/v1/auth/signup")).status_code == 401


async def test_signup_requires_age_confirmation(h: AuthHarness) -> None:
    idp = await begin_login(h.client)
    await callback(h.client, await fake_idp_code(h.client, idp, email=unique_email(), name="N"))
    response = await h.client.post(
        "/v1/auth/signup",
        json={
            "age_confirmed": False,
            "terms_version": h.settings.terms_version,
            "privacy_version": h.settings.privacy_version,
        },
        headers=csrf_headers(h.client),
    )
    assert response.status_code == 400
    assert response.json()["code"] == "validation_error"


async def test_signup_rejects_stale_terms_version(h: AuthHarness) -> None:
    idp = await begin_login(h.client)
    await callback(h.client, await fake_idp_code(h.client, idp, email=unique_email(), name="N"))
    response = await h.client.post(
        "/v1/auth/signup",
        json={"age_confirmed": True, "terms_version": "old", "privacy_version": "old"},
        headers=csrf_headers(h.client),
    )
    assert response.status_code == 409


async def test_signup_expires_after_30_minutes(h: AuthHarness) -> None:
    idp = await begin_login(h.client)
    await callback(h.client, await fake_idp_code(h.client, idp, email=unique_email(), name="N"))
    h.clock.advance(timedelta(minutes=31))
    response = await h.client.post(
        "/v1/auth/signup",
        json={
            "age_confirmed": True,
            "terms_version": h.settings.terms_version,
            "privacy_version": h.settings.privacy_version,
        },
        headers=csrf_headers(h.client),
    )
    assert response.status_code == 401


async def test_signup_requires_csrf_token(h: AuthHarness) -> None:
    idp = await begin_login(h.client)
    await callback(h.client, await fake_idp_code(h.client, idp, email=unique_email(), name="N"))
    body = {
        "age_confirmed": True,
        "terms_version": h.settings.terms_version,
        "privacy_version": h.settings.privacy_version,
    }
    assert (await h.client.post("/v1/auth/signup", json=body)).status_code == 403
    wrong = await h.client.post("/v1/auth/signup", json=body, headers={"X-CSRF-Token": "x" * 43})
    assert wrong.status_code == 403


async def test_email_taken_by_another_identity_is_a_conflict(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    email = unique_email()
    await sign_up(h.client, email=email)
    with owner_connection(
        test_db
    ) as conn:  # the same email now arrives under a different IdP user ID
        conn.execute("UPDATE identity.users SET idp_user_id = 'other|1' WHERE email = %s", (email,))
    async with h.new_client() as other:
        idp = await begin_login(other)
        await callback(other, await fake_idp_code(other, idp, email=email, name="Twin"))
        response = await other.post(
            "/v1/auth/signup",
            json={
                "age_confirmed": True,
                "terms_version": h.settings.terms_version,
                "privacy_version": h.settings.privacy_version,
            },
            headers=csrf_headers(other),
        )
    assert response.status_code == 409


# --- existing user -------------------------------------------------------------------------------------


async def test_existing_user_gets_a_session_and_returns_to_path(h: AuthHarness) -> None:
    email = unique_email()
    await sign_up(h.client, email=email)
    async with h.new_client() as laptop:
        response = await sign_in(laptop, email=email, return_to="/settings")
        assert response.headers["location"] == f"{APP_ORIGIN}/settings"
        cookies = response.headers.get_list("set-cookie")
        session_cookie = next(c for c in cookies if c.startswith("bo_session="))
        for attribute in ("HttpOnly", "Secure", "SameSite=lax", "Path=/"):
            assert attribute.lower() in session_cookie.lower()
        csrf_cookie = next(c for c in cookies if c.startswith("bo_csrf="))
        assert "httponly" not in csrf_cookie.lower()
        assert (await laptop.get("/v1/me")).json()["email"] == email


async def test_signing_in_again_replaces_the_browsers_previous_session(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    email = unique_email()
    await sign_up(h.client, email=email)
    await sign_in(h.client, email=email)
    count = _count(
        test_db,
        "SELECT count(*) FROM identity.sessions s JOIN identity.users u ON u.id = s.user_id "
        "WHERE u.email = %s",
        email,
    )
    assert count == 1


async def test_deletion_pending_user_cannot_sign_in(
    h: AuthHarness, test_db: EphemeralDatabase
) -> None:
    email = unique_email()
    await sign_up(h.client, email=email)
    with owner_connection(test_db) as conn:
        conn.execute(
            "UPDATE identity.users SET status = 'deletion_pending', deletion_requested_at = now() "
            "WHERE email = %s",
            (email,),
        )
    assert (await h.client.get("/v1/me")).status_code == 401
    async with h.new_client() as other:
        response = await sign_in(other, email=email)
    assert response.headers["location"] == f"{APP_ORIGIN}/sign-in?error=account_pending_deletion"


# --- state, PKCE, replay -------------------------------------------------------------------------------


async def test_state_mismatch_is_rejected(h: AuthHarness) -> None:
    idp = await begin_login(h.client)
    url = await fake_idp_code(h.client, idp, email=unique_email(), name="N")
    tampered = url.replace(f"state={idp['state']}", "state=forged-state-value")
    response = await callback(h.client, tampered)
    assert response.headers["location"] == f"{APP_ORIGIN}/sign-in?error=sign_in_failed"
    assert not h.client.cookies.get("bo_session")
    assert not h.client.cookies.get("bo_csrf")


async def test_callback_without_login_cookie_is_rejected(h: AuthHarness) -> None:
    idp = await begin_login(h.client)
    url = await fake_idp_code(h.client, idp, email=unique_email(), name="N")
    async with h.new_client() as attacker:  # a different browser: no bo_login cookie
        response = await callback(attacker, url)
    assert response.headers["location"] == f"{APP_ORIGIN}/sign-in?error=sign_in_expired"


async def test_login_cookie_expires_after_10_minutes(h: AuthHarness) -> None:
    idp = await begin_login(h.client)
    url = await fake_idp_code(h.client, idp, email=unique_email(), name="N")
    h.clock.advance(timedelta(minutes=11))
    response = await callback(h.client, url)
    assert response.headers["location"] == f"{APP_ORIGIN}/sign-in?error=sign_in_expired"


async def test_replayed_callback_is_rejected(h: AuthHarness) -> None:
    email = unique_email()
    await sign_up(h.client, email=email)
    async with h.new_client() as browser:
        idp = await begin_login(browser)
        login_cookie = browser.cookies.get("bo_login")
        url = await fake_idp_code(browser, idp, email=email, name="N")
        first = await callback(browser, url)
        assert first.headers["location"] == f"{APP_ORIGIN}/"
        assert browser.cookies.get("bo_login") is None, "the login cookie is cleared after use"
    # Replaying the same callback URL with the old (still validly signed) login cookie fails, because
    # the authorization code is single-use.
    async with h.new_client() as attacker:
        second = await attacker.get(url, headers={"Cookie": f"bo_login={login_cookie}"})
    assert second.status_code == 303
    assert second.headers["location"] == f"{APP_ORIGIN}/sign-in?error=sign_in_failed"
    assert "bo_session=" not in second.headers.get("set-cookie", "")


async def test_wrong_pkce_verifier_is_rejected(h: AuthHarness) -> None:
    """A code issued for one login cannot be redeemed with another login's verifier."""
    idp_a = await begin_login(h.client)
    url_a = await fake_idp_code(h.client, idp_a, email=unique_email(), name="N")
    idp_b = await begin_login(h.client)  # replaces bo_login with a new state + verifier
    url_with_b_state = url_a.replace(f"state={idp_a['state']}", f"state={idp_b['state']}")
    response = await callback(h.client, url_with_b_state)
    assert response.headers["location"] == f"{APP_ORIGIN}/sign-in?error=sign_in_failed"


async def test_idp_error_redirects_to_sign_in(h: AuthHarness) -> None:
    await begin_login(h.client)
    response = await callback(h.client, "/v1/auth/callback?error=access_denied&state=x")
    assert response.headers["location"] == f"{APP_ORIGIN}/sign-in?error=sign_in_cancelled"


# --- open redirect -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "return_to",
    [
        "https://evil.example/",
        "//evil.example/",
        "/\\evil.example",
        "javascript:alert(1)",
        "evil.example",
        "/ok\r\nSet-Cookie: x=y",
        "/" + "a" * 600,
    ],
)
async def test_open_redirect_is_rejected(h: AuthHarness, return_to: str) -> None:
    response = await h.client.get("/v1/auth/login", params={"return_to": return_to})
    assert response.status_code == 400
    assert response.json()["code"] == "validation_error"
    assert "bo_login" not in response.headers.get("set-cookie", "")


async def test_callback_redirects_to_the_app_origin_with_the_validated_path(h: AuthHarness) -> None:
    email = unique_email()
    await sign_up(h.client, email=email)
    async with h.new_client() as browser:
        response = await sign_in(browser, email=email, return_to="/a/b?c=d")
    assert response.headers["location"] == f"{APP_ORIGIN}/a/b?c=d"
