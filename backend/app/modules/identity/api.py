"""Identity routes: sign-in, sign-up consent, sign-out, /v1/me and sessions (docs/auth-and-tenancy.md §1-3)."""

from __future__ import annotations

import html
import ipaddress
import uuid
from datetime import datetime
from typing import Literal
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.modules.identity.dependencies import (
    CSRF_COOKIE,
    CSRF_HEADER,
    SESSION_COOKIE,
    CurrentSessionConsentPending,
    Identity,
)
from app.modules.identity.providers.fake import FakeIdentityProvider
from app.modules.identity.service import (
    LOGIN_TTL,
    SIGNUP_TTL,
    ClientInfo,
    IssuedSession,
    SignedIn,
    SignInFailed,
)
from app.platform.config import Settings
from app.platform.errors import NotFound, ValidationProblem

LOGIN_COOKIE = "bo_login"
SIGNUP_COOKIE = "bo_signup"
AUTH_COOKIE_PATH = "/v1/auth"
FAKE_AUTHORIZE_PATH = "/v1/auth/fake/authorize"

auth_router = APIRouter(prefix="/v1/auth", tags=["auth"])
me_router = APIRouter(prefix="/v1/me", tags=["me"])
fake_idp_router = APIRouter(include_in_schema=False)


# --- schemas -----------------------------------------------------------------------------------------


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    consent_required: bool
    terms_version: str
    privacy_version: str


class SignupProfileOut(BaseModel):
    email: str
    display_name: str
    terms_version: str
    privacy_version: str


class SignupIn(BaseModel):
    age_confirmed: Literal[True] = Field(description="The user confirms they are 18 or older")
    terms_version: str = Field(min_length=1, max_length=64)
    privacy_version: str = Field(min_length=1, max_length=64)


class SignupOut(BaseModel):
    return_to: str


class ConsentIn(BaseModel):
    terms_version: str = Field(min_length=1, max_length=64)
    privacy_version: str = Field(min_length=1, max_length=64)


class SessionOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    ip: str | None
    user_agent: str | None
    is_current: bool


class SessionList(BaseModel):
    items: list[SessionOut]
    next_cursor: None = None


class RevokeOthersOut(BaseModel):
    revoked: int


# --- cookies -----------------------------------------------------------------------------------------


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _cookie(
    response: Response,
    settings: Settings,
    name: str,
    value: str,
    *,
    max_age: int,
    path: str = "/",
    httponly: bool = True,
) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path=path,
        domain=settings.cookie_domain,
        secure=True,
        httponly=httponly,
        samesite="lax",
    )


def _clear(response: Response, settings: Settings, name: str, *, path: str = "/") -> None:
    response.delete_cookie(
        name, path=path, domain=settings.cookie_domain, secure=True, samesite="lax"
    )


def _set_session_cookies(
    response: Response, request: Request, settings: Settings, issued: IssuedSession
) -> None:
    max_age = max(
        0, int((issued.absolute_expires_at - request.app.state.clock.now()).total_seconds())
    )
    _cookie(response, settings, SESSION_COOKIE, issued.session_token, max_age=max_age)
    _cookie(response, settings, CSRF_COOKIE, issued.csrf_token, max_age=max_age, httponly=False)


def _client(request: Request) -> ClientInfo:
    ip: str | None = request.client.host if request.client else None
    try:
        ip = str(ipaddress.ip_address(ip)) if ip else None
    except ValueError:
        ip = None
    return ClientInfo(ip=ip, user_agent=request.headers.get("user-agent"))


def _app_url(settings: Settings, path: str) -> str:
    return f"{settings.app_origin.rstrip('/')}{path}"


# --- sign-in -----------------------------------------------------------------------------------------


@auth_router.get(
    "/login",
    response_class=RedirectResponse,
    status_code=302,
    summary="Start sign-in (browser navigation)",
)
async def login(request: Request, identity: Identity, return_to: str | None = None) -> Response:
    settings = _settings(request)
    start = identity.start_login(return_to)
    response = RedirectResponse(start.redirect_url, status_code=302)
    _cookie(
        response,
        settings,
        LOGIN_COOKIE,
        start.login_cookie,
        max_age=int(LOGIN_TTL.total_seconds()),
        path=AUTH_COOKIE_PATH,
    )
    return response


@auth_router.get(
    "/callback",
    response_class=RedirectResponse,
    status_code=303,
    summary="Identity-provider callback (browser navigation)",
)
async def callback(
    request: Request,
    identity: Identity,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> Response:
    settings = _settings(request)
    try:
        if error:
            raise SignInFailed("sign_in_cancelled")
        result = await identity.complete_callback(
            code=code,
            state=state,
            login_cookie=request.cookies.get(LOGIN_COOKIE),
            current_session_token=request.cookies.get(SESSION_COOKIE),
            client=_client(request),
        )
    except SignInFailed as exc:
        response = RedirectResponse(
            _app_url(settings, "/sign-in?" + urlencode({"error": exc.reason})), status_code=303
        )
        _clear(response, settings, LOGIN_COOKIE, path=AUTH_COOKIE_PATH)
        return response

    if isinstance(result, SignedIn):
        response = RedirectResponse(_app_url(settings, result.return_to), status_code=303)
        _set_session_cookies(response, request, settings, result.session)
    else:
        response = RedirectResponse(_app_url(settings, "/welcome"), status_code=303)
        max_age = int(SIGNUP_TTL.total_seconds())
        _cookie(
            response,
            settings,
            SIGNUP_COOKIE,
            result.signup_cookie,
            max_age=max_age,
            path=AUTH_COOKIE_PATH,
        )
        _cookie(response, settings, CSRF_COOKIE, result.csrf_token, max_age=max_age, httponly=False)
    _clear(response, settings, LOGIN_COOKIE, path=AUTH_COOKIE_PATH)
    return response


@auth_router.get("/signup", summary="The pending sign-up awaiting 18+ and terms acceptance")
async def get_signup(request: Request, identity: Identity) -> SignupProfileOut:
    profile = identity.read_signup(request.cookies.get(SIGNUP_COOKIE))
    return SignupProfileOut(
        email=profile.email,
        display_name=profile.display_name,
        terms_version=profile.terms_version,
        privacy_version=profile.privacy_version,
    )


@auth_router.post("/signup", summary="Confirm 18+, accept the terms, and create the account")
async def complete_signup(
    request: Request, response: Response, identity: Identity, body: SignupIn
) -> SignupOut:
    settings = _settings(request)
    result = await identity.complete_signup(
        signup_cookie=request.cookies.get(SIGNUP_COOKIE),
        csrf_cookie=request.cookies.get(CSRF_COOKIE),
        csrf_header=request.headers.get(CSRF_HEADER),
        terms_version=body.terms_version,
        privacy_version=body.privacy_version,
        client=_client(request),
    )
    _set_session_cookies(response, request, settings, result.session)
    _clear(response, settings, SIGNUP_COOKIE, path=AUTH_COOKIE_PATH)
    return SignupOut(return_to=result.return_to)


@auth_router.post(
    "/signup/decline",
    status_code=204,
    summary="Under 18: abandon the sign-up; nothing is stored",
)
async def decline_signup(request: Request) -> Response:
    settings = _settings(request)
    response = Response(status_code=204)
    _clear(response, settings, SIGNUP_COOKIE, path=AUTH_COOKIE_PATH)
    _clear(response, settings, CSRF_COOKIE)
    return response


@auth_router.post("/logout", status_code=204, summary="Sign out: delete this session")
async def logout(
    request: Request, identity: Identity, ctx: CurrentSessionConsentPending
) -> Response:
    settings = _settings(request)
    await identity.logout(ctx)
    response = Response(status_code=204)
    _clear(response, settings, SESSION_COOKIE)
    _clear(response, settings, CSRF_COOKIE)
    return response


# --- me ----------------------------------------------------------------------------------------------


@me_router.get("", summary="The signed-in user (works while consent is pending)")
async def get_me(identity: Identity, ctx: CurrentSessionConsentPending) -> MeOut:
    me = await identity.get_me(ctx)
    return MeOut(
        id=me.id,
        email=me.email,
        display_name=me.display_name,
        consent_required=me.consent_required,
        terms_version=me.terms_version,
        privacy_version=me.privacy_version,
    )


@me_router.post("/consent", status_code=204, summary="Accept the current terms and privacy notice")
async def accept_consent(
    request: Request, identity: Identity, ctx: CurrentSessionConsentPending, body: ConsentIn
) -> Response:
    issued = await identity.accept_consent(
        ctx,
        terms_version=body.terms_version,
        privacy_version=body.privacy_version,
        client=_client(request),
    )
    response = Response(status_code=204)
    _set_session_cookies(response, request, _settings(request), issued)
    return response


@me_router.get("/sessions", summary="List my active sessions")
async def list_sessions(identity: Identity, ctx: CurrentSessionConsentPending) -> SessionList:
    sessions = await identity.list_sessions(ctx)
    return SessionList(
        items=[
            SessionOut(
                id=s.id,
                created_at=s.created_at,
                last_seen_at=s.last_seen_at,
                idle_expires_at=s.idle_expires_at,
                absolute_expires_at=s.absolute_expires_at,
                ip=s.ip,
                user_agent=s.user_agent,
                is_current=s.is_current,
            )
            for s in sessions
        ]
    )


@me_router.delete("/sessions/{session_id}", status_code=204, summary="Revoke one of my sessions")
async def revoke_session(
    session_id: uuid.UUID, identity: Identity, ctx: CurrentSessionConsentPending
) -> Response:
    await identity.revoke_session(ctx, session_id)
    return Response(status_code=204)


@me_router.post("/sessions/revoke-others", summary="Revoke all my sessions except this one")
async def revoke_other_sessions(
    identity: Identity, ctx: CurrentSessionConsentPending
) -> RevokeOthersOut:
    return RevokeOthersOut(revoked=await identity.revoke_other_sessions(ctx))


# --- fake identity provider (local development, tests, E2E; never production) -------------------------

_FAKE_FORM = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Fake sign-in (development only)</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{font-family:system-ui,sans-serif;max-width:28rem;margin:4rem auto;padding:0 1rem}}
label{{display:block;margin-top:1rem}}input{{width:100%;padding:.5rem;font-size:1rem}}
button{{margin-top:1.5rem;padding:.6rem 1.2rem;font-size:1rem}}</style></head>
<body><h1>Fake sign-in</h1>
<p>Development identity provider. No password; any email works. Never available in production.</p>
<form method="post" action="{action}">
<input type="hidden" name="state" value="{state}">
<input type="hidden" name="code_challenge" value="{code_challenge}">
<input type="hidden" name="redirect_uri" value="{redirect_uri}">
<label for="email">Email</label><input id="email" name="email" type="email" required>
<label for="display_name">Name</label><input id="display_name" name="display_name" required>
<button type="submit">Sign in</button>
</form></body></html>"""


def _fake_provider(request: Request) -> FakeIdentityProvider:
    provider = request.app.state.identity.provider
    if not isinstance(provider, FakeIdentityProvider):
        raise NotFound()
    return provider


@fake_idp_router.get(FAKE_AUTHORIZE_PATH, response_class=HTMLResponse)
async def fake_authorize_form(
    request: Request, state: str = "", code_challenge: str = "", redirect_uri: str = ""
) -> HTMLResponse:
    _fake_provider(request)
    return HTMLResponse(
        _FAKE_FORM.format(
            action=html.escape(FAKE_AUTHORIZE_PATH),
            state=html.escape(state),
            code_challenge=html.escape(code_challenge),
            redirect_uri=html.escape(redirect_uri),
        )
    )


@fake_idp_router.post(FAKE_AUTHORIZE_PATH)
async def fake_authorize_submit(request: Request) -> Response:
    provider = _fake_provider(request)
    form = {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}
    email = form.get("email", "").strip()
    name = form.get("display_name", "").strip()
    if form.get("redirect_uri") != _settings(request).auth_redirect_uri:
        raise ValidationProblem("redirect_uri does not match the configured callback")
    if "@" not in email or not name or not form.get("state") or not form.get("code_challenge"):
        raise ValidationProblem("email, name, state and code_challenge are required")
    code = provider.issue_code(
        email=email, display_name=name, code_challenge=form["code_challenge"]
    )
    query = urlencode({"code": code, "state": form["state"]})
    return RedirectResponse(f"{form['redirect_uri']}?{query}", status_code=303)
