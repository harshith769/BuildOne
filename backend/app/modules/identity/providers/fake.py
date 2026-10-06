"""Fake identity provider for local development, tests and E2E. Never allowed in production (Settings).

It behaves like a real Authorization Code + PKCE provider without any network:
- `authorization_url` points at the API's own `/v1/auth/fake/authorize` form;
- `issue_code` (called by that form) returns a signed, 5-minute code that carries the profile and the
  PKCE challenge;
- `exchange_code` checks the signature, expiry, PKCE verifier, and that the code was not used before.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from app.modules.identity.providers.base import IdentityError, IdentityProfile
from app.modules.identity.security import (
    InvalidSignedValue,
    pkce_challenge,
    sign_value,
    tokens_equal,
    verify_value,
)
from app.platform.clock import Clock

CODE_TTL = timedelta(minutes=5)
_PURPOSE = "fake_idp_code"


def fake_idp_user_id(email: str) -> str:
    """Stable per email, so signing in again with the same email finds the same user."""
    return "fake|" + hashlib.sha256(email.strip().lower().encode()).hexdigest()[:24]


class FakeIdentityProvider:
    def __init__(self, *, api_base_url: str, key: bytes, clock: Clock) -> None:
        self._authorize_url = f"{api_base_url.rstrip('/')}/v1/auth/fake/authorize"
        self._key = key
        self._clock = clock
        self._used_codes: set[str] = set()

    def authorization_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        query = urlencode(
            {"state": state, "code_challenge": code_challenge, "redirect_uri": redirect_uri}
        )
        return f"{self._authorize_url}?{query}"

    def issue_code(self, *, email: str, display_name: str, code_challenge: str) -> str:
        payload = {
            "sub": fake_idp_user_id(email),
            "email": email.strip(),
            "name": display_name.strip(),
            "ch": code_challenge,
            "jti": secrets.token_urlsafe(16),
        }
        return sign_value(
            payload, key=self._key, purpose=_PURPOSE, expires_at=self._clock.now() + CODE_TTL
        )

    async def exchange_code(self, *, code: str, code_verifier: str) -> IdentityProfile:
        try:
            data = verify_value(code, key=self._key, purpose=_PURPOSE, now=self._clock.now())
        except InvalidSignedValue as exc:
            raise IdentityError(f"invalid code: {exc}") from exc
        if not tokens_equal(pkce_challenge(code_verifier), str(data.get("ch", ""))):
            raise IdentityError("PKCE verifier does not match the challenge")
        jti = str(data.get("jti", ""))
        if not jti or jti in self._used_codes:
            raise IdentityError("code already used")
        self._used_codes.add(jti)
        return IdentityProfile(
            idp_user_id=str(data["sub"]), email=str(data["email"]), display_name=str(data["name"])
        )
