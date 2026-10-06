"""Pure security helpers for sign-in and sessions (docs/auth-and-tenancy.md §1-3). No I/O, no clock reads.

- Session and CSRF tokens are 32 random bytes (base64url); only their SHA-256 is stored.
- Short-lived sign-in state (PKCE verifier, return path, a pending sign-up profile) travels in HMAC-signed,
  expiring cookie values, so nothing about an unfinished sign-in is stored in the database.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

TOKEN_BYTES = 32
IDLE_EXTENSION_INTERVAL = timedelta(hours=1)
MAX_RETURN_TO_LENGTH = 512


def new_token() -> str:
    """32 random bytes, base64url without padding (43 characters)."""
    return _b64encode(secrets.token_bytes(TOKEN_BYTES))


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("ascii", errors="replace")).digest()


def tokens_equal(a: str | None, b: str | None) -> bool:
    """Constant-time comparison; False if either side is missing or empty."""
    if not a or not b:
        return False
    return hmac.compare_digest(a.encode(), b.encode())


@dataclass(frozen=True, slots=True)
class PkcePair:
    verifier: str
    challenge: str


def pkce_challenge(verifier: str) -> str:
    """RFC 7636 S256: base64url(SHA-256(verifier)) without padding."""
    return _b64encode(hashlib.sha256(verifier.encode("ascii")).digest())


def new_pkce_pair() -> PkcePair:
    verifier = _b64encode(secrets.token_bytes(48))  # 64 characters, within RFC 7636's 43-128
    return PkcePair(verifier=verifier, challenge=pkce_challenge(verifier))


class InvalidSignedValue(Exception):
    """A signed value was tampered with, malformed, for another purpose, or expired."""


def sign_value(payload: dict[str, Any], *, key: bytes, purpose: str, expires_at: datetime) -> str:
    """`<body>.<mac>`: body = base64url(JSON payload + purpose + expiry), mac = HMAC-SHA256(key, body)."""
    body = _b64encode(
        json.dumps(
            {"p": purpose, "exp": int(expires_at.timestamp()), "d": payload},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    )
    return f"{body}.{_mac(key, body)}"


def verify_value(value: str | None, *, key: bytes, purpose: str, now: datetime) -> dict[str, Any]:
    if not value or value.count(".") != 1:
        raise InvalidSignedValue("missing or malformed")
    body, mac = value.split(".")
    if not hmac.compare_digest(mac, _mac(key, body)):
        raise InvalidSignedValue("bad signature")
    try:
        decoded = json.loads(_b64decode(body))
    except (ValueError, binascii.Error) as exc:
        raise InvalidSignedValue("malformed body") from exc
    if not isinstance(decoded, dict) or decoded.get("p") != purpose:
        raise InvalidSignedValue("wrong purpose")
    exp = decoded.get("exp")
    if not isinstance(exp, int) or now.timestamp() >= exp:
        raise InvalidSignedValue("expired")
    data = decoded.get("d")
    if not isinstance(data, dict):
        raise InvalidSignedValue("malformed payload")
    return data


def validate_return_to(value: str | None) -> str:
    """A same-app relative path, or ValueError (open-redirect protection). None/empty means '/'."""
    if value is None or value == "":
        return "/"
    if len(value) > MAX_RETURN_TO_LENGTH:
        raise ValueError("return_to is too long")
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        raise ValueError("return_to contains control characters")
    if not value.startswith("/") or value.startswith("//") or value.startswith("/\\"):
        raise ValueError("return_to must be a relative path starting with a single '/'")
    if "\\" in value:
        raise ValueError("return_to must not contain backslashes")
    return value


def next_idle_expiry(
    *,
    now: datetime,
    last_seen_at: datetime,
    absolute_expires_at: datetime,
    idle: timedelta,
) -> datetime | None:
    """The new idle expiry if the session should be extended now, else None.

    Extends at most once per hour to limit writes, and never past the absolute expiry.
    """
    if now - last_seen_at < IDLE_EXTENSION_INTERVAL:
        return None
    return min(now + idle, absolute_expires_at)


def is_expired(*, now: datetime, idle_expires_at: datetime, absolute_expires_at: datetime) -> bool:
    return now >= idle_expires_at or now >= absolute_expires_at


def _mac(key: bytes, body: str) -> str:
    return _b64encode(hmac.new(key, body.encode("ascii"), hashlib.sha256).digest())


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
