"""The identity-provider seam (ADR-0007, ADR-0011). Adapters: `fake` (local dev, tests, E2E) and `workos`.

A provider only authenticates people. Sessions, users and organisations belong to BuildOne.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class IdentityProfile:
    """A verified identity returned by a code exchange."""

    idp_user_id: str
    email: str
    display_name: str


class IdentityError(Exception):
    """The provider rejected the code, could not be reached, or returned an unusable profile."""


class IdentityProvider(Protocol):
    def authorization_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        """Where to send the browser to authenticate (Authorization Code + PKCE S256)."""
        ...

    async def exchange_code(self, *, code: str, code_verifier: str) -> IdentityProfile:
        """Exchange a single-use authorization code. Raises IdentityError on any failure."""
        ...
