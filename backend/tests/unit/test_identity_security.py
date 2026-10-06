"""Pure sign-in and session helpers: return_to validation, signed values, PKCE, expiry maths, fake IdP codes."""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.identity.providers.base import IdentityError
from app.modules.identity.providers.fake import FakeIdentityProvider, fake_idp_user_id
from app.modules.identity.security import (
    InvalidSignedValue,
    hash_token,
    is_expired,
    new_pkce_pair,
    new_token,
    next_idle_expiry,
    pkce_challenge,
    sign_value,
    tokens_equal,
    validate_return_to,
    verify_value,
)
from app.platform.clock import FrozenClock

NOW = datetime(2026, 10, 6, 4, 30, tzinfo=UTC)
KEY = b"k" * 32


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "/"),
        ("", "/"),
        ("/", "/"),
        ("/plan?tab=open", "/plan?tab=open"),
        ("/a/b#c", "/a/b#c"),
    ],
)
def test_return_to_accepts_relative_paths(value: str | None, expected: str) -> None:
    assert validate_return_to(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.example",
        "//evil.example",
        "/\\evil.example",
        "/a\\b",
        "javascript:alert(1)",
        "evil.example/path",
        "/ok\nLocation: x",
        "/tab\there",
        "/" + "x" * 600,
    ],
)
def test_return_to_rejects_open_redirects(value: str) -> None:
    with pytest.raises(ValueError):
        validate_return_to(value)


def test_tokens_are_32_random_bytes_and_hashed_with_sha256() -> None:
    token = new_token()
    assert len(base64.urlsafe_b64decode(token + "=")) == 32
    assert token != new_token()
    assert hash_token(token) == hashlib.sha256(token.encode()).digest()


def test_tokens_equal_rejects_missing_values() -> None:
    assert tokens_equal("abc", "abc")
    assert not tokens_equal("abc", "abd")
    assert not tokens_equal(None, None)
    assert not tokens_equal("", "")


def test_pkce_challenge_matches_rfc7636_example() -> None:
    # RFC 7636 Appendix B
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert pkce_challenge(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    pair = new_pkce_pair()
    assert 43 <= len(pair.verifier) <= 128
    assert pkce_challenge(pair.verifier) == pair.challenge


def test_signed_value_round_trip() -> None:
    value = sign_value({"a": 1}, key=KEY, purpose="login", expires_at=NOW + timedelta(minutes=10))
    assert verify_value(value, key=KEY, purpose="login", now=NOW) == {"a": 1}


def test_signed_value_rejects_tampering_wrong_key_purpose_and_expiry() -> None:
    value = sign_value({"a": 1}, key=KEY, purpose="login", expires_at=NOW + timedelta(minutes=10))
    body, mac = value.split(".")
    forged_body = base64.urlsafe_b64encode(b'{"d":{"a":2},"exp":9999999999,"p":"login"}').decode()
    cases = [
        (f"{forged_body.rstrip('=')}.{mac}", KEY, "login", NOW),
        (value, b"x" * 32, "login", NOW),
        (value, KEY, "signup", NOW),
        (value, KEY, "login", NOW + timedelta(minutes=10)),
        (f"{body}.", KEY, "login", NOW),
        ("garbage", KEY, "login", NOW),
        (None, KEY, "login", NOW),
    ]
    for candidate, key, purpose, now in cases:
        with pytest.raises(InvalidSignedValue):
            verify_value(candidate, key=key, purpose=purpose, now=now)


def test_idle_extension_at_most_hourly_and_capped_by_absolute() -> None:
    idle = timedelta(days=30)
    absolute = NOW + timedelta(days=90)
    assert (
        next_idle_expiry(
            now=NOW + timedelta(minutes=59),
            last_seen_at=NOW,
            absolute_expires_at=absolute,
            idle=idle,
        )
        is None
    )
    later = NOW + timedelta(hours=1)
    assert (
        next_idle_expiry(now=later, last_seen_at=NOW, absolute_expires_at=absolute, idle=idle)
        == later + idle
    )
    near_end = NOW + timedelta(days=80)
    assert (
        next_idle_expiry(now=near_end, last_seen_at=NOW, absolute_expires_at=absolute, idle=idle)
        == absolute
    )


def test_is_expired_on_either_boundary() -> None:
    idle, absolute = NOW + timedelta(days=30), NOW + timedelta(days=90)
    assert not is_expired(now=NOW, idle_expires_at=idle, absolute_expires_at=absolute)
    assert is_expired(now=idle, idle_expires_at=idle, absolute_expires_at=absolute)
    assert is_expired(
        now=absolute, idle_expires_at=absolute + timedelta(days=1), absolute_expires_at=absolute
    )


async def test_fake_provider_checks_pkce_expiry_and_single_use() -> None:
    clock = FrozenClock(NOW)
    provider = FakeIdentityProvider(api_base_url="http://localhost:8000", key=KEY, clock=clock)
    pair = new_pkce_pair()
    code = provider.issue_code(
        email="a@example.test", display_name="A", code_challenge=pair.challenge
    )

    with pytest.raises(IdentityError, match="PKCE"):
        await provider.exchange_code(code=code, code_verifier=new_pkce_pair().verifier)
    profile = await provider.exchange_code(code=code, code_verifier=pair.verifier)
    assert profile.idp_user_id == fake_idp_user_id("A@Example.test ")
    assert profile.email == "a@example.test"
    with pytest.raises(IdentityError, match="already used"):
        await provider.exchange_code(code=code, code_verifier=pair.verifier)

    stale = provider.issue_code(
        email="b@example.test", display_name="B", code_challenge=pair.challenge
    )
    clock.advance(timedelta(minutes=5))
    with pytest.raises(IdentityError, match="invalid code"):
        await provider.exchange_code(code=stale, code_verifier=pair.verifier)


def test_fake_provider_authorization_url_carries_state_and_challenge() -> None:
    provider = FakeIdentityProvider(
        api_base_url="http://localhost:8000/", key=KEY, clock=FrozenClock(NOW)
    )
    url = provider.authorization_url(state="s1", code_challenge="c1", redirect_uri="http://cb")
    assert url.startswith("http://localhost:8000/v1/auth/fake/authorize?")
    assert "state=s1" in url and "code_challenge=c1" in url
