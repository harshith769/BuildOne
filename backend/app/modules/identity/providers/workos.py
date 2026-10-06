"""WorkOS AuthKit adapter (ADR-0007). The only module that imports the WorkOS SDK (import-linter contract)."""

from __future__ import annotations

from typing import Any

from workos import AsyncWorkOSClient, WorkOSError

from app.modules.identity.providers.base import IdentityError, IdentityProfile


class WorkOSIdentityProvider:
    def __init__(self, *, api_key: str, client_id: str, http_client: Any = None) -> None:
        """`http_client` (an httpx.AsyncClient) is for tests; production uses the SDK's own client."""
        self._client = AsyncWorkOSClient(
            api_key=api_key, client_id=client_id, http_client=http_client, max_retries=1
        )

    def authorization_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        return self._client.user_management.get_authorization_url(
            provider="authkit",
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )

    async def exchange_code(self, *, code: str, code_verifier: str) -> IdentityProfile:
        try:
            response = await self._client.user_management.authenticate_with_code(
                code=code, code_verifier=code_verifier
            )
        except WorkOSError as exc:  # API errors and network failures alike
            raise IdentityError(f"WorkOS code exchange failed: {type(exc).__name__}") from exc
        user = response.user
        if not user.email_verified:
            raise IdentityError("email address is not verified")
        name = " ".join(part for part in (user.first_name, user.last_name) if part)
        return IdentityProfile(
            idp_user_id=user.id,
            email=user.email,
            display_name=name or user.name or user.email.split("@", 1)[0],
        )
