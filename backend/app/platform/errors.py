"""Typed domain errors rendered as RFC 9457 problem details (docs/api-conventions.md §2).

Code raises a DomainError subclass; the handlers here turn it, request-validation errors, unknown routes and
unexpected exceptions into `application/problem+json` responses that always carry the request ID.
"""

from __future__ import annotations

from typing import Any, ClassVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.platform.context import get_request_id
from app.platform.logging import get_logger

PROBLEM_CONTENT_TYPE = "application/problem+json"
_log = get_logger("app.platform.errors")


class DomainError(Exception):
    """Base for errors the API reports to clients. Subclasses set status, code and title."""

    status: ClassVar[int] = 500
    code: ClassVar[str] = "internal_error"
    title: ClassVar[str] = "Something went wrong"

    def __init__(self, detail: str | None = None, **extra: Any) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title
        self.extra = extra


class ValidationProblem(DomainError):
    status, code, title = 400, "validation_error", "The request is not valid"


class Unauthenticated(DomainError):
    status, code, title = 401, "unauthenticated", "Sign in to continue"


class Forbidden(DomainError):
    status, code, title = 403, "forbidden", "You don't have permission to do this"


class ConsentRequired(DomainError):
    status, code, title = 403, "consent_required", "Accept the current terms to continue"


class NotFound(DomainError):
    """Also used when the caller is not a member of the org, so existence never leaks."""

    status, code, title = 404, "not_found", "Not found"


class Conflict(DomainError):
    status, code, title = 409, "conflict", "This conflicts with the current state"


class IdempotencyKeyConflict(DomainError):
    status, code, title = (
        409,
        "idempotency_key_conflict",
        "Idempotency key reused with a different request",
    )


class Unprocessable(DomainError):
    status, code, title = 422, "unprocessable", "The request can't be processed"


class RateLimited(DomainError):
    status, code, title = 429, "rate_limited", "Too many requests"


class QuotaExceeded(DomainError):
    status, code, title = 429, "quota_exceeded", "Daily limit reached"


class AIUnavailable(DomainError):
    """Only for AI-only endpoints. Core compliance endpoints never raise this."""

    status, code, title = 503, "ai_unavailable", "The AI assistant is unavailable right now"


def problem_body(
    *, status: int, code: str, title: str, detail: str, root_domain: str, **extra: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": f"https://{root_domain}/problems/{code.replace('_', '-')}",
        "title": title,
        "status": status,
        "code": code,
        "detail": detail,
        "request_id": get_request_id(),
    }
    body.update(extra)
    return body


def _problem(status: int, body: dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM_CONTENT_TYPE)


def install_error_handlers(app: FastAPI, *, root_domain: str) -> None:
    """Register handlers so every error leaves the API in the same shape."""

    async def on_domain_error(_: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, DomainError):
            raise exc
        body = problem_body(
            status=exc.status,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
            root_domain=root_domain,
            **exc.extra,
        )
        return _problem(exc.status, body)

    async def on_validation_error(_: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, RequestValidationError):
            raise exc
        errors = [
            {
                "field": ".".join(str(p) for p in err.get("loc", ()) if p != "body"),
                "message": err.get("msg", ""),
            }
            for err in exc.errors()
        ]
        body = problem_body(
            status=400,
            code="validation_error",
            title=ValidationProblem.title,
            detail="One or more fields are not valid",
            root_domain=root_domain,
            errors=errors,
        )
        return _problem(400, body)

    async def on_http_error(_: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, StarletteHTTPException):
            raise exc
        if exc.status_code == 404:
            code, title = "not_found", NotFound.title
        elif exc.status_code == 405:
            code, title = "method_not_allowed", "Method not allowed"
        else:
            code, title = "http_error", "Request failed"
        body = problem_body(
            status=exc.status_code,
            code=code,
            title=title,
            detail=str(exc.detail),
            root_domain=root_domain,
        )
        response = _problem(exc.status_code, body)
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    async def on_unexpected(_: Request, exc: Exception) -> JSONResponse:
        _log.error("unhandled_exception", exc_info=exc)
        body = problem_body(
            status=500,
            code="internal_error",
            title=DomainError.title,
            detail="Unexpected error. Quote the request ID if you contact support.",
            root_domain=root_domain,
        )
        return _problem(500, body)

    app.add_exception_handler(DomainError, on_domain_error)
    app.add_exception_handler(RequestValidationError, on_validation_error)
    app.add_exception_handler(StarletteHTTPException, on_http_error)
    app.add_exception_handler(Exception, on_unexpected)
