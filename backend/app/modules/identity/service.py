"""Identity service: sign-in, sign-up with 18+ and terms consent, sessions (docs/auth-and-tenancy.md §1-3).

Public interface of the identity module. Other modules call this, never models.py.

Sign-in (Authorization Code + PKCE):
1. `start_login` validates `return_to` and returns the IdP URL plus a signed `bo_login` value
   (state, PKCE verifier, return path; 10 minutes).
2. `complete_callback` checks the state against that value, exchanges the code, and either creates a
   session for an existing user, or (new user) returns a signed `bo_signup` value that holds the verified
   profile for 30 minutes. No user row exists until 18+ and the terms are accepted (owner decision D-28).
3. `complete_signup` creates the user, both consents and a session in one transaction.
"""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.modules.audit import service as audit
from app.modules.identity import models
from app.modules.identity.providers.base import IdentityError, IdentityProvider
from app.modules.identity.security import (
    InvalidSignedValue,
    hash_token,
    is_expired,
    new_pkce_pair,
    new_token,
    next_idle_expiry,
    sign_value,
    tokens_equal,
    validate_return_to,
    verify_value,
)
from app.platform.clock import Clock
from app.platform.config import Settings
from app.platform.db import set_tenant_context, tenant_transaction
from app.platform.errors import (
    Conflict,
    Forbidden,
    NotFound,
    Unauthenticated,
    ValidationProblem,
)
from app.platform.ids import new_id

LOGIN_TTL = timedelta(minutes=10)
SIGNUP_TTL = timedelta(minutes=30)
_LOGIN_PURPOSE = "login"
_SIGNUP_PURPOSE = "signup"
_USER_AGENT_MAX = 512


class SignInFailed(Exception):
    """The callback could not complete. `reason` is a short code shown on the sign-in screen."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class LoginStart:
    redirect_url: str
    login_cookie: str


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """A new session. The raw tokens go into cookies and are never stored."""

    session_id: uuid.UUID
    session_token: str
    csrf_token: str
    absolute_expires_at: datetime


@dataclass(frozen=True, slots=True)
class SignedIn:
    session: IssuedSession
    return_to: str


@dataclass(frozen=True, slots=True)
class SignupPending:
    signup_cookie: str
    csrf_token: str
    return_to: str


@dataclass(frozen=True, slots=True)
class SignupProfile:
    email: str
    display_name: str
    terms_version: str
    privacy_version: str


@dataclass(frozen=True, slots=True)
class SessionContext:
    """The authenticated caller, resolved from the session cookie."""

    session_id: uuid.UUID
    user_id: uuid.UUID
    csrf_token_hash: bytes
    consent_required: bool


@dataclass(frozen=True, slots=True)
class Me:
    id: uuid.UUID
    email: str
    display_name: str
    consent_required: bool
    terms_version: str
    privacy_version: str


@dataclass(frozen=True, slots=True)
class SessionInfo:
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    ip: str | None
    user_agent: str | None
    is_current: bool


@dataclass(frozen=True, slots=True)
class Profile:
    user_id: uuid.UUID
    email: str
    display_name: str


@dataclass(frozen=True, slots=True)
class ClientInfo:
    ip: str | None
    user_agent: str | None


class IdentityService:
    def __init__(
        self, *, engine: AsyncEngine, settings: Settings, clock: Clock, provider: IdentityProvider
    ) -> None:
        self._engine = engine
        self._settings = settings
        self._clock = clock
        self._provider = provider
        self._key = settings.secret_key.get_secret_value().encode()

    @property
    def provider(self) -> IdentityProvider:
        return self._provider

    # --- sign-in -------------------------------------------------------------------------------------

    def start_login(self, return_to: str | None) -> LoginStart:
        try:
            safe_return_to = validate_return_to(return_to)
        except ValueError as exc:
            raise ValidationProblem(
                "return_to must be a path inside the app",
                errors=[{"field": "return_to", "message": str(exc)}],
            ) from exc
        state = new_token()
        pkce = new_pkce_pair()
        cookie = sign_value(
            {"state": state, "verifier": pkce.verifier, "return_to": safe_return_to},
            key=self._key,
            purpose=_LOGIN_PURPOSE,
            expires_at=self._clock.now() + LOGIN_TTL,
        )
        url = self._provider.authorization_url(
            state=state,
            code_challenge=pkce.challenge,
            redirect_uri=self._settings.auth_redirect_uri,
        )
        return LoginStart(redirect_url=url, login_cookie=cookie)

    async def complete_callback(
        self,
        *,
        code: str | None,
        state: str | None,
        login_cookie: str | None,
        current_session_token: str | None,
        client: ClientInfo,
    ) -> SignedIn | SignupPending:
        try:
            login = verify_value(
                login_cookie, key=self._key, purpose=_LOGIN_PURPOSE, now=self._clock.now()
            )
        except InvalidSignedValue as exc:
            raise SignInFailed("sign_in_expired") from exc
        if not code or not tokens_equal(state, str(login.get("state", ""))):
            raise SignInFailed("sign_in_failed")
        try:
            profile = await self._provider.exchange_code(
                code=code, code_verifier=str(login["verifier"])
            )
        except IdentityError as exc:
            raise SignInFailed("sign_in_failed") from exc
        return_to = validate_return_to(str(login.get("return_to", "/")))

        async with self._engine.begin() as conn:
            row = (
                await conn.execute(
                    text("SELECT user_id, user_status FROM identity.find_user_by_idp(:idp)"),
                    {"idp": profile.idp_user_id},
                )
            ).first()
            if row is None:
                csrf = new_token()
                signup_cookie = sign_value(
                    {
                        "idp_user_id": profile.idp_user_id,
                        "email": profile.email,
                        "display_name": profile.display_name,
                        "return_to": return_to,
                        "csrf_hash": hash_token(csrf).hex(),
                    },
                    key=self._key,
                    purpose=_SIGNUP_PURPOSE,
                    expires_at=self._clock.now() + SIGNUP_TTL,
                )
                return SignupPending(
                    signup_cookie=signup_cookie, csrf_token=csrf, return_to=return_to
                )
            user_id, status = row
            if status != "active":
                raise SignInFailed("account_pending_deletion")
            await self._drop_session_by_token(conn, current_session_token)
            await set_tenant_context(conn, user_id=user_id)
            issued = await self._create_session(conn, user_id, client)
            await self._audit_session(conn, "identity.signed_in", user_id, issued.session_id)
        return SignedIn(session=issued, return_to=return_to)

    def read_signup(self, signup_cookie: str | None) -> SignupProfile:
        data = self._verify_signup(signup_cookie)
        return SignupProfile(
            email=str(data["email"]),
            display_name=str(data["display_name"]),
            terms_version=self._settings.terms_version,
            privacy_version=self._settings.privacy_version,
        )

    async def complete_signup(
        self,
        *,
        signup_cookie: str | None,
        csrf_cookie: str | None,
        csrf_header: str | None,
        terms_version: str,
        privacy_version: str,
        client: ClientInfo,
    ) -> SignedIn:
        data = self._verify_signup(signup_cookie)
        if not tokens_equal(csrf_header, csrf_cookie) or not hmac.compare_digest(
            hash_token(csrf_header or "").hex(), str(data.get("csrf_hash", ""))
        ):
            raise Forbidden("CSRF check failed")
        self._check_versions(terms_version, privacy_version)
        now = self._clock.now()
        user_id = new_id()
        try:
            async with tenant_transaction(self._engine, user_id=user_id) as conn:
                await conn.execute(
                    insert(models.users).values(
                        id=user_id,
                        email=str(data["email"]),
                        display_name=str(data["display_name"]),
                        idp_user_id=str(data["idp_user_id"]),
                        status="active",
                        age_confirmed_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                )
                await self._record_consents(conn, user_id, terms_version, privacy_version)
                issued = await self._create_session(conn, user_id, client)
                await self._audit_session(
                    conn, "identity.signed_in", user_id, issued.session_id, new_account=True
                )
        except IntegrityError as exc:
            raise Conflict(
                "An account with this email or sign-in already exists. Sign in again."
            ) from exc
        return SignedIn(session=issued, return_to=str(data.get("return_to", "/")))

    # --- sessions ------------------------------------------------------------------------------------

    async def resolve_session(self, session_token: str | None) -> SessionContext:
        """Validate the session cookie, expire or extend it, and report whether consent is pending."""
        if not session_token:
            raise Unauthenticated()
        now = self._clock.now()
        async with self._engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT session_id, user_id, csrf_token_hash, last_seen_at, idle_expires_at, "
                        "absolute_expires_at, user_status FROM identity.find_session(:h)"
                    ),
                    {"h": hash_token(session_token)},
                )
            ).first()
            if row is None:
                raise Unauthenticated()
            await set_tenant_context(conn, user_id=row.user_id)
            if row.user_status != "active" or is_expired(
                now=now,
                idle_expires_at=row.idle_expires_at,
                absolute_expires_at=row.absolute_expires_at,
            ):
                await conn.execute(
                    delete(models.sessions).where(models.sessions.c.id == row.session_id)
                )
                expired = True
            else:
                expired = False
                new_idle = next_idle_expiry(
                    now=now,
                    last_seen_at=row.last_seen_at,
                    absolute_expires_at=row.absolute_expires_at,
                    idle=timedelta(days=self._settings.session_idle_days),
                )
                if new_idle is not None:
                    await conn.execute(
                        update(models.sessions)
                        .where(models.sessions.c.id == row.session_id)
                        .values(last_seen_at=now, idle_expires_at=new_idle, updated_at=now)
                    )
                consent_required = await self._consent_required(conn, row.user_id)
        if expired:  # raised after commit, so the expired row is really deleted
            raise Unauthenticated("Your session has expired. Sign in again.")
        return SessionContext(
            session_id=row.session_id,
            user_id=row.user_id,
            csrf_token_hash=bytes(row.csrf_token_hash),
            consent_required=consent_required,
        )

    @staticmethod
    def csrf_matches(ctx: SessionContext, *, header: str | None, cookie: str | None) -> bool:
        """Double-submit (header equals cookie) and bound to this session (hash matches)."""
        if not tokens_equal(header, cookie):
            return False
        return hmac.compare_digest(hash_token(header or ""), ctx.csrf_token_hash)

    async def logout(self, ctx: SessionContext) -> None:
        async with tenant_transaction(self._engine, user_id=ctx.user_id) as conn:
            await conn.execute(
                delete(models.sessions).where(models.sessions.c.id == ctx.session_id)
            )
            await self._audit_session(conn, "identity.signed_out", ctx.user_id, ctx.session_id)

    async def get_me(self, ctx: SessionContext) -> Me:
        async with tenant_transaction(self._engine, user_id=ctx.user_id) as conn:
            user = (
                await conn.execute(
                    select(
                        models.users.c.id, models.users.c.email, models.users.c.display_name
                    ).where(models.users.c.id == ctx.user_id)
                )
            ).one()
        return Me(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            consent_required=ctx.consent_required,
            terms_version=self._settings.terms_version,
            privacy_version=self._settings.privacy_version,
        )

    async def accept_consent(
        self, ctx: SessionContext, *, terms_version: str, privacy_version: str, client: ClientInfo
    ) -> IssuedSession:
        """Record acceptance of the current versions and rotate the session (new token and CSRF token)."""
        self._check_versions(terms_version, privacy_version)
        async with tenant_transaction(self._engine, user_id=ctx.user_id) as conn:
            await self._record_consents(conn, ctx.user_id, terms_version, privacy_version)
            await conn.execute(
                delete(models.sessions).where(models.sessions.c.id == ctx.session_id)
            )
            return await self._create_session(conn, ctx.user_id, client)

    async def list_sessions(self, ctx: SessionContext) -> list[SessionInfo]:
        s = models.sessions.c
        async with tenant_transaction(self._engine, user_id=ctx.user_id) as conn:
            rows = (
                await conn.execute(
                    select(
                        s.id,
                        s.created_at,
                        s.last_seen_at,
                        s.idle_expires_at,
                        s.absolute_expires_at,
                        func.host(s.ip).label("ip"),
                        s.user_agent,
                    )
                    .where(s.user_id == ctx.user_id)
                    .order_by(s.last_seen_at.desc(), s.id.desc())
                )
            ).all()
        return [
            SessionInfo(
                id=r.id,
                created_at=r.created_at,
                last_seen_at=r.last_seen_at,
                idle_expires_at=r.idle_expires_at,
                absolute_expires_at=r.absolute_expires_at,
                ip=r.ip,
                user_agent=r.user_agent,
                is_current=r.id == ctx.session_id,
            )
            for r in rows
        ]

    async def revoke_session(self, ctx: SessionContext, session_id: uuid.UUID) -> None:
        async with tenant_transaction(self._engine, user_id=ctx.user_id) as conn:
            result = await conn.execute(
                delete(models.sessions).where(
                    models.sessions.c.id == session_id, models.sessions.c.user_id == ctx.user_id
                )
            )
            if result.rowcount == 0:
                raise NotFound("Session not found")
            await self._audit_session(conn, "identity.session_revoked", ctx.user_id, session_id)

    async def revoke_other_sessions(self, ctx: SessionContext) -> int:
        async with tenant_transaction(self._engine, user_id=ctx.user_id) as conn:
            revoked = (
                (
                    await conn.execute(
                        delete(models.sessions)
                        .where(
                            models.sessions.c.user_id == ctx.user_id,
                            models.sessions.c.id != ctx.session_id,
                        )
                        .returning(models.sessions.c.id)
                    )
                )
                .scalars()
                .all()
            )
            for session_id in revoked:
                await self._audit_session(
                    conn, "identity.session_revoked", ctx.user_id, session_id, bulk=True
                )
        return len(revoked)

    # --- profiles (for other modules) ----------------------------------------------------------------

    async def email_of(self, user_id: uuid.UUID) -> str:
        async with tenant_transaction(self._engine, user_id=user_id) as conn:
            email = (
                await conn.execute(select(models.users.c.email).where(models.users.c.id == user_id))
            ).scalar_one()
        return str(email)

    async def co_member_profiles(
        self, viewer_id: uuid.UUID, user_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, Profile]:
        """Names and emails of the given users that share an organisation with `viewer_id`."""
        if not user_ids:
            return {}
        async with tenant_transaction(self._engine, user_id=viewer_id) as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT user_id, email, display_name "
                        "FROM identity.co_member_profiles(CAST(:ids AS uuid[]))"
                    ),
                    {"ids": [str(u) for u in user_ids]},
                )
            ).all()
        return {
            r.user_id: Profile(user_id=r.user_id, email=r.email, display_name=r.display_name)
            for r in rows
        }

    # --- internals -----------------------------------------------------------------------------------

    def _verify_signup(self, signup_cookie: str | None) -> dict[str, Any]:
        try:
            return verify_value(
                signup_cookie, key=self._key, purpose=_SIGNUP_PURPOSE, now=self._clock.now()
            )
        except InvalidSignedValue as exc:
            raise Unauthenticated("Your sign-up has expired. Sign in again.") from exc

    def _check_versions(self, terms_version: str, privacy_version: str) -> None:
        if (terms_version, privacy_version) != (
            self._settings.terms_version,
            self._settings.privacy_version,
        ):
            raise Conflict("The terms changed while you were reading them. Reload and try again.")

    async def _create_session(
        self, conn: AsyncConnection, user_id: uuid.UUID, client: ClientInfo
    ) -> IssuedSession:
        now = self._clock.now()
        absolute = now + timedelta(days=self._settings.session_absolute_days)
        idle = min(now + timedelta(days=self._settings.session_idle_days), absolute)
        token, csrf = new_token(), new_token()
        session_id = new_id()
        await conn.execute(
            insert(models.sessions).values(
                id=session_id,
                user_id=user_id,
                token_hash=hash_token(token),
                csrf_token_hash=hash_token(csrf),
                last_seen_at=now,
                idle_expires_at=idle,
                absolute_expires_at=absolute,
                ip=client.ip,
                user_agent=(client.user_agent or None) and client.user_agent[:_USER_AGENT_MAX],
                created_at=now,
                updated_at=now,
            )
        )
        return IssuedSession(
            session_id=session_id,
            session_token=token,
            csrf_token=csrf,
            absolute_expires_at=absolute,
        )

    async def _audit_session(
        self,
        conn: AsyncConnection,
        action: str,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        **metadata: Any,
    ) -> None:
        await audit.record(
            conn,
            action=action,
            actor_user_id=user_id,
            target_table="identity.sessions",
            target_id=session_id,
            occurred_at=self._clock.now(),
            metadata=metadata,
        )

    async def _drop_session_by_token(self, conn: AsyncConnection, token: str | None) -> None:
        """Signing in again replaces the browser's previous session instead of orphaning it."""
        if not token:
            return
        row = (
            await conn.execute(
                text("SELECT session_id, user_id FROM identity.find_session(:h)"),
                {"h": hash_token(token)},
            )
        ).first()
        if row is None:
            return
        await set_tenant_context(conn, user_id=row.user_id)
        await conn.execute(delete(models.sessions).where(models.sessions.c.id == row.session_id))

    async def _record_consents(
        self, conn: AsyncConnection, user_id: uuid.UUID, terms_version: str, privacy_version: str
    ) -> None:
        now = self._clock.now()
        for document, version in (("terms", terms_version), ("privacy", privacy_version)):
            await conn.execute(
                pg_insert(models.consents)
                .values(
                    id=new_id(),
                    user_id=user_id,
                    document=document,
                    version=version,
                    accepted_at=now,
                )
                .on_conflict_do_nothing(index_elements=["user_id", "document", "version"])
            )

    async def _consent_required(self, conn: AsyncConnection, user_id: uuid.UUID) -> bool:
        c = models.consents.c
        accepted = (
            (
                await conn.execute(
                    select(c.document).where(
                        c.user_id == user_id,
                        ((c.document == "terms") & (c.version == self._settings.terms_version))
                        | (
                            (c.document == "privacy")
                            & (c.version == self._settings.privacy_version)
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        return set(accepted) != {"terms", "privacy"}
