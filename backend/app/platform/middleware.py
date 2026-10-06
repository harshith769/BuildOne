"""ASGI middleware: request ID and access log on every request; Origin check on unsafe requests."""

from __future__ import annotations

import time

import structlog
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.platform.context import request_id_from_header, set_request_id
from app.platform.errors import PROBLEM_CONTENT_TYPE, problem_body
from app.platform.logging import get_logger, safe_path

REQUEST_ID_HEADER = "x-request-id"
_log = get_logger("app.access")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers") or []).get(REQUEST_ID_HEADER.encode())
        request_id = request_id_from_header(incoming.decode("latin-1") if incoming else None)
        set_request_id(request_id)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        status_code = 500
        started = time.perf_counter()

        async def send_with_header(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            _log.info(
                "request",
                method=scope.get("method"),
                path=safe_path(scope.get("path", "")),
                status=status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )


UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class OriginCheckMiddleware:
    """CSRF layer 2 (docs/auth-and-tenancy.md §3): unsafe requests under /v1 must come from the app origin.

    A missing or different `Origin` header gets 403 before any route runs. `exempt_paths` exists only for the
    fake identity provider's own form (served from the API origin in local development and tests); main.py
    passes it only when that provider is configured, which Settings forbids in production.
    """

    def __init__(
        self, app: ASGIApp, *, allowed_origin: str, root_domain: str, exempt_paths: frozenset[str]
    ) -> None:
        self.app = app
        self.allowed_origin = allowed_origin.rstrip("/")
        self.root_domain = root_domain
        self.exempt_paths = exempt_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope.get("method") in UNSAFE_METHODS
            and scope.get("path", "").startswith("/v1/")
            and scope.get("path") not in self.exempt_paths
        ):
            origin = dict(scope.get("headers") or []).get(b"origin", b"").decode("latin-1")
            if origin.rstrip("/") != self.allowed_origin:
                body = problem_body(
                    status=403,
                    code="forbidden",
                    title="You don't have permission to do this",
                    detail="Request origin not allowed",
                    root_domain=self.root_domain,
                )
                await JSONResponse(body, status_code=403, media_type=PROBLEM_CONTENT_TYPE)(
                    scope, receive, send
                )
                return
        await self.app(scope, receive, send)
