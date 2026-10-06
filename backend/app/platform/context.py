"""Per-request context carried in context variables (request ID; user and org arrive in M2/M3)."""

from __future__ import annotations

import re
from contextvars import ContextVar

from app.platform.ids import new_id

_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="")
_VALID_INCOMING = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def get_request_id() -> str:
    return _REQUEST_ID.get()


def set_request_id(value: str) -> None:
    _REQUEST_ID.set(value)


def request_id_from_header(header_value: str | None) -> str:
    """Reuse a well-formed incoming X-Request-ID (e.g. from Cloudflare or a test); otherwise mint a UUIDv7."""
    if header_value and _VALID_INCOMING.fullmatch(header_value):
        return header_value
    return str(new_id())
