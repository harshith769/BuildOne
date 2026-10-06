"""ASGI middleware: request ID on every request, response header and log line; one access log per request."""

from __future__ import annotations

import time

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.platform.context import request_id_from_header, set_request_id
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
