"""FastAPI dependencies that authenticate the caller (docs/auth-and-tenancy.md §5, middleware layer).

`current_session` is what every authenticated route uses: it resolves the `bo_session` cookie, rejects
`consent_required`, and enforces the CSRF double-submit token on unsafe methods. The Origin check runs
earlier, in `app.platform.middleware.OriginCheckMiddleware`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.modules.identity.service import IdentityService, SessionContext
from app.platform.errors import ConsentRequired, Forbidden

SESSION_COOKIE = "bo_session"
CSRF_COOKIE = "bo_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def get_identity_service(request: Request) -> IdentityService:
    service: IdentityService = request.app.state.identity
    return service


async def _resolve(request: Request, *, allow_consent_pending: bool) -> SessionContext:
    service = get_identity_service(request)
    ctx = await service.resolve_session(request.cookies.get(SESSION_COOKIE))
    if request.method not in SAFE_METHODS and not service.csrf_matches(
        ctx, header=request.headers.get(CSRF_HEADER), cookie=request.cookies.get(CSRF_COOKIE)
    ):
        raise Forbidden("CSRF check failed. Reload the page and try again.")
    if ctx.consent_required and not allow_consent_pending:
        raise ConsentRequired()
    return ctx


async def current_session(request: Request) -> SessionContext:
    return await _resolve(request, allow_consent_pending=False)


async def current_session_allow_consent_pending(request: Request) -> SessionContext:
    """Only for /v1/me, accepting consent, and signing out."""
    return await _resolve(request, allow_consent_pending=True)


CurrentSession = Annotated[SessionContext, Depends(current_session)]
CurrentSessionConsentPending = Annotated[
    SessionContext, Depends(current_session_allow_consent_pending)
]
Identity = Annotated[IdentityService, Depends(get_identity_service)]
