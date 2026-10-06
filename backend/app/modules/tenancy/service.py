"""Tenancy service: organisations, memberships, invitations and access grants (docs/auth-and-tenancy.md §4-6).

Public interface of the tenancy module. Every query runs under RLS with the caller's context
(`tenant_transaction(user_id, org_id)`); the role checks here (`require`) and the database policies
(ADR-0013) enforce the same rules twice. Every change writes an audit row in the same transaction.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from psycopg import errors as pg_errors
from sqlalchemy import delete, func, insert, or_, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.modules.audit import service as audit
from app.modules.identity.security import hash_token, new_token
from app.modules.identity.service import IdentityService
from app.modules.tenancy import models
from app.modules.tenancy.errors import GrantScopeNotAvailable, InvitationEmailMismatch, LastOwner
from app.modules.tenancy.permissions import AccessLevel, Role
from app.modules.tenancy.permissions import require as require_level
from app.platform import idempotency
from app.platform.clock import Clock
from app.platform.config import Settings
from app.platform.db import set_tenant_context, tenant_transaction
from app.platform.errors import Conflict, NotFound, Unprocessable
from app.platform.ids import new_id

INVITATION_TTL = timedelta(days=7)
OrgType = Literal["team", "company", "ca_firm", "incubator"]
GrantDirection = Literal["share", "request"]


@dataclass(frozen=True, slots=True)
class OrgContext:
    """The caller's access to the organisation in the URL path (auth-and-tenancy.md §5)."""

    org_id: uuid.UUID
    user_id: uuid.UUID
    role: Role | None  # None = reached through an access grant
    grant_scope: str | None

    @property
    def level(self) -> AccessLevel:
        return self.role or "grantee"


def require(ctx: OrgContext, action: str) -> None:
    """Raise 403 unless the caller's access level allows `action` (permissions.MATRIX)."""
    require_level(ctx.level, action)


@dataclass(frozen=True, slots=True)
class Organization:
    id: uuid.UUID
    type: str
    name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MyOrganization:
    id: uuid.UUID
    type: str
    name: str
    role: str


@dataclass(frozen=True, slots=True)
class Member:
    user_id: uuid.UUID
    email: str | None
    display_name: str | None
    role: str
    joined_at: datetime


@dataclass(frozen=True, slots=True)
class Invitation:
    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime
    expired: bool


@dataclass(frozen=True, slots=True)
class InvitationPreview:
    org_name: str
    org_type: str
    role: str
    email: str
    email_matches: bool


@dataclass(frozen=True, slots=True)
class Grant:
    id: uuid.UUID
    grantor_org_id: uuid.UUID
    grantee_org_id: uuid.UUID
    scope: str
    status: str
    initiated_by: str
    created_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


def _constraint_message(exc: DBAPIError) -> str:
    diag = getattr(exc.orig, "diag", None)
    primary = getattr(diag, "message_primary", None)
    return str(primary or exc.orig)


class TenancyService:
    def __init__(
        self, *, engine: AsyncEngine, settings: Settings, clock: Clock, identity: IdentityService
    ) -> None:
        self._engine = engine
        self._settings = settings
        self._clock = clock
        self._identity = identity

    # --- organisations -------------------------------------------------------------------------------

    async def create_organization(
        self,
        *,
        user_id: uuid.UUID,
        org_type: OrgType,
        name: str,
        idempotency_key: uuid.UUID,
        request_sha256: str,
    ) -> tuple[int, dict[str, Any]]:
        """Create an organisation with the caller as its first owner. Returns (status, body) for replay."""
        now = self._clock.now()
        org_id = new_id()
        async with tenant_transaction(self._engine, user_id=user_id, org_id=org_id) as conn:
            replay = await idempotency.begin(
                conn, user_id=user_id, key=idempotency_key, request_sha256=request_sha256, now=now
            )
            if replay:
                return replay.status, replay.body
            # No RETURNING: the SELECT policy applies to it and the creator isn't a member yet.
            await conn.execute(
                insert(models.organizations).values(
                    id=org_id,
                    type=org_type,
                    name=name.strip(),
                    status="active",
                    created_by=user_id,
                    created_at=now,
                    updated_at=now,
                )
            )
            await conn.execute(
                insert(models.memberships).values(
                    org_id=org_id, user_id=user_id, role="owner", created_at=now, updated_at=now
                )
            )
            await audit.record(
                conn,
                action="org.created",
                actor_user_id=user_id,
                org_id=org_id,
                target_table="tenancy.organizations",
                target_id=org_id,
                occurred_at=now,
                metadata={"type": org_type},
            )
            org = await self._read_org(conn, org_id)
            body = _org_body(org) | {"role": "owner"}
            await idempotency.complete(
                conn, user_id=user_id, key=idempotency_key, status=201, stored_body=body
            )
        return 201, body

    async def list_my_organizations(self, user_id: uuid.UUID) -> list[MyOrganization]:
        o, m = models.organizations.c, models.memberships.c
        async with tenant_transaction(self._engine, user_id=user_id) as conn:
            rows = (
                await conn.execute(
                    select(o.id, o.type, o.name, m.role)
                    .join(models.memberships, m.org_id == o.id)
                    .where(m.user_id == user_id, o.status == "active")
                    .order_by(o.name, o.id)
                )
            ).all()
        return [MyOrganization(id=r.id, type=r.type, name=r.name, role=r.role) for r in rows]

    async def resolve_access(self, *, user_id: uuid.UUID, org_id: uuid.UUID) -> OrgContext:
        """Membership role, or an active grant held by one of the caller's organisations; else 404."""
        o, m, g = models.organizations.c, models.memberships.c, models.access_grants.c
        async with tenant_transaction(self._engine, user_id=user_id, org_id=org_id) as conn:
            visible = (
                await conn.execute(select(o.id).where(o.id == org_id, o.status == "active"))
            ).first()
            if visible is None:  # RLS hides orgs the caller can't read: no existence leak
                raise NotFound()
            role = (
                await conn.execute(select(m.role).where(m.org_id == org_id, m.user_id == user_id))
            ).scalar_one_or_none()
            if role is not None:
                return OrgContext(org_id=org_id, user_id=user_id, role=role, grant_scope=None)
            my_orgs = select(m.org_id).where(m.user_id == user_id)
            scope = (
                await conn.execute(
                    select(g.scope)
                    .where(
                        g.grantor_org_id == org_id,
                        g.status == "active",
                        g.grantee_org_id.in_(my_orgs),
                    )
                    .order_by(g.scope)
                    .limit(1)
                )
            ).scalar_one_or_none()
        if scope is None:
            raise NotFound()
        return OrgContext(org_id=org_id, user_id=user_id, role=None, grant_scope=scope)

    async def get_organization(self, ctx: OrgContext) -> Organization:
        require(ctx, "org.view")
        async with self._tx(ctx) as conn:
            return await self._read_org(conn, ctx.org_id)

    # --- members -------------------------------------------------------------------------------------

    async def list_members(self, ctx: OrgContext) -> list[Member]:
        require(ctx, "members.view")
        m = models.memberships.c
        async with self._tx(ctx) as conn:
            rows = (
                await conn.execute(
                    select(m.user_id, m.role, m.created_at)
                    .where(m.org_id == ctx.org_id)
                    .order_by(m.created_at, m.user_id)
                )
            ).all()
        profiles = await self._identity.co_member_profiles(ctx.user_id, [r.user_id for r in rows])
        return [
            Member(
                user_id=r.user_id,
                email=profiles[r.user_id].email if r.user_id in profiles else None,
                display_name=profiles[r.user_id].display_name if r.user_id in profiles else None,
                role=r.role,
                joined_at=r.created_at,
            )
            for r in rows
        ]

    async def change_role(self, ctx: OrgContext, target_user_id: uuid.UUID, role: Role) -> None:
        require(ctx, "members.manage")
        m = models.memberships.c
        now = self._clock.now()
        try:
            async with self._tx(ctx) as conn:
                old = (
                    await conn.execute(
                        select(m.role).where(m.org_id == ctx.org_id, m.user_id == target_user_id)
                    )
                ).scalar_one_or_none()
                if old is None:
                    raise NotFound("Member not found")
                if old == role:
                    return
                await conn.execute(
                    update(models.memberships)
                    .where(m.org_id == ctx.org_id, m.user_id == target_user_id)
                    .values(role=role, updated_at=now)
                )
                await audit.record(
                    conn,
                    action="member.role_changed",
                    actor_user_id=ctx.user_id,
                    org_id=ctx.org_id,
                    target_table="tenancy.memberships",
                    target_id=target_user_id,
                    occurred_at=now,
                    metadata={"from": old, "to": role},
                )
        except IntegrityError as exc:
            raise self._map_integrity(exc) from exc

    async def remove_member(self, ctx: OrgContext, target_user_id: uuid.UUID) -> None:
        """Owners remove anyone; any member may leave (remove themselves). The last owner can't go."""
        leaving = target_user_id == ctx.user_id
        if not leaving:
            require(ctx, "members.manage")
        elif ctx.role is None:
            raise NotFound()
        m = models.memberships.c
        now = self._clock.now()
        try:
            async with self._tx(ctx) as conn:
                # Audit first: once a member has left, they can no longer read the org.
                await audit.record(
                    conn,
                    action="member.left" if leaving else "member.removed",
                    actor_user_id=ctx.user_id,
                    org_id=ctx.org_id,
                    target_table="tenancy.memberships",
                    target_id=target_user_id,
                    occurred_at=now,
                )
                result = await conn.execute(
                    delete(models.memberships).where(
                        m.org_id == ctx.org_id, m.user_id == target_user_id
                    )
                )
                if result.rowcount == 0:
                    raise NotFound("Member not found")
        except (
            IntegrityError
        ) as exc:  # includes the deferred last-owner trigger, which fires at COMMIT
            raise self._map_integrity(exc) from exc

    # --- invitations ---------------------------------------------------------------------------------

    async def create_invitation(
        self,
        ctx: OrgContext,
        *,
        email: str,
        role: Role,
        idempotency_key: uuid.UUID,
        request_sha256: str,
    ) -> tuple[int, dict[str, Any]]:
        """Returns (status, body). The live body carries the one-time link; the stored replay body doesn't."""
        require(ctx, "invitations.manage")
        now = self._clock.now()
        i = models.invitations.c
        async with self._tx(ctx) as conn:
            replay = await idempotency.begin(
                conn,
                user_id=ctx.user_id,
                key=idempotency_key,
                request_sha256=request_sha256,
                now=now,
            )
            if replay:
                return replay.status, replay.body
            # An expired, unaccepted invitation to the same address doesn't block a new one.
            await conn.execute(
                delete(models.invitations).where(
                    i.org_id == ctx.org_id,
                    func.lower(i.email) == email.strip().lower(),
                    i.accepted_at.is_(None),
                    i.expires_at <= now,
                )
            )
            token = new_token()
            invitation_id = new_id()
            try:
                async with conn.begin_nested():
                    await conn.execute(
                        insert(models.invitations).values(
                            id=invitation_id,
                            org_id=ctx.org_id,
                            email=email.strip(),
                            role=role,
                            token_hash=hash_token(token),
                            expires_at=now + INVITATION_TTL,
                            invited_by=ctx.user_id,
                            created_at=now,
                            updated_at=now,
                        )
                    )
            except IntegrityError as exc:
                raise Conflict("This person already has an open invitation.") from exc
            await audit.record(
                conn,
                action="invitation.created",
                actor_user_id=ctx.user_id,
                org_id=ctx.org_id,
                target_table="tenancy.invitations",
                target_id=invitation_id,
                occurred_at=now,
                metadata={"role": role},
            )
            stored = {
                "id": str(invitation_id),
                "email": email.strip(),
                "role": role,
                "expires_at": (now + INVITATION_TTL).isoformat(),
                "invite_link": None,
                "link_available": False,
            }
            await idempotency.complete(
                conn, user_id=ctx.user_id, key=idempotency_key, status=201, stored_body=stored
            )
        live = stored | {"invite_link": self._invite_link(token), "link_available": True}
        return 201, live

    async def list_invitations(self, ctx: OrgContext) -> list[Invitation]:
        require(ctx, "invitations.manage")
        i = models.invitations.c
        now = self._clock.now()
        async with self._tx(ctx) as conn:
            rows = (
                await conn.execute(
                    select(i.id, i.email, i.role, i.expires_at)
                    .where(i.org_id == ctx.org_id, i.accepted_at.is_(None))
                    .order_by(i.created_at.desc(), i.id.desc())
                )
            ).all()
        return [
            Invitation(
                id=r.id,
                email=r.email,
                role=r.role,
                expires_at=r.expires_at,
                expired=r.expires_at <= now,
            )
            for r in rows
        ]

    async def revoke_invitation(self, ctx: OrgContext, invitation_id: uuid.UUID) -> None:
        require(ctx, "invitations.manage")
        i = models.invitations.c
        now = self._clock.now()
        async with self._tx(ctx) as conn:
            result = await conn.execute(
                delete(models.invitations).where(
                    i.id == invitation_id, i.org_id == ctx.org_id, i.accepted_at.is_(None)
                )
            )
            if result.rowcount == 0:
                raise NotFound("Invitation not found")
            await audit.record(
                conn,
                action="invitation.revoked",
                actor_user_id=ctx.user_id,
                org_id=ctx.org_id,
                target_table="tenancy.invitations",
                target_id=invitation_id,
                occurred_at=now,
            )

    async def preview_invitation(self, *, user_id: uuid.UUID, token: str) -> InvitationPreview:
        async with tenant_transaction(self._engine, user_id=user_id) as conn:
            row = await self._find_open_invitation(conn, token)
        my_email = (await self._identity.email_of(user_id)).lower()
        return InvitationPreview(
            org_name=row.org_name,
            org_type=row.org_type,
            role=row.role,
            email=row.email,
            email_matches=row.email.lower() == my_email,
        )

    async def accept_invitation(
        self, *, user_id: uuid.UUID, token: str, confirm_email_mismatch: bool
    ) -> MyOrganization:
        my_email = (await self._identity.email_of(user_id)).lower()
        now = self._clock.now()
        async with tenant_transaction(self._engine, user_id=user_id) as conn:
            row = await self._find_open_invitation(conn, token)
            if row.email.lower() != my_email and not confirm_email_mismatch:
                raise InvitationEmailMismatch(
                    f"This invitation was sent to {row.email}. Confirm to accept it with your account."
                )
            await set_tenant_context(conn, user_id=user_id, org_id=row.org_id)
            # The token hash is the capability the accept policies check (ADR-0013).
            await conn.execute(
                text("SELECT set_config('app.invitation_token_hash', :h, true)"),
                {"h": hash_token(token).hex()},
            )
            m = models.memberships.c
            existing = (
                await conn.execute(
                    select(m.role).where(m.org_id == row.org_id, m.user_id == user_id)
                )
            ).scalar_one_or_none()
            if existing is not None:
                raise Conflict("You're already a member of this organisation.")
            # Membership first: the policy checks the invitation is still unaccepted and unexpired.
            try:
                await conn.execute(
                    insert(models.memberships).values(
                        org_id=row.org_id,
                        user_id=user_id,
                        role=row.role,
                        created_at=now,
                        updated_at=now,
                    )
                )
            except DBAPIError as exc:
                # The database refused the token (e.g. expired by its own clock): same answer as the API's.
                if isinstance(exc.orig, pg_errors.InsufficientPrivilege):
                    raise NotFound(
                        "This invitation link is invalid, expired or already used."
                    ) from exc
                raise
            i = models.invitations.c
            await conn.execute(
                update(models.invitations)
                .where(i.id == row.invitation_id)
                .values(accepted_at=now, updated_at=now)
            )
            await audit.record(
                conn,
                action="invitation.accepted",
                actor_user_id=user_id,
                org_id=row.org_id,
                target_table="tenancy.invitations",
                target_id=row.invitation_id,
                occurred_at=now,
                metadata={"role": row.role, "email_matched": row.email.lower() == my_email},
            )
        return MyOrganization(id=row.org_id, type=row.org_type, name=row.org_name, role=row.role)

    # --- access grants -------------------------------------------------------------------------------

    async def create_grant(
        self,
        ctx: OrgContext,
        *,
        other_org_id: uuid.UUID,
        direction: GrantDirection,
        scope: str,
    ) -> Grant:
        """`share`: this org (a company) shares with another; `request`: this org asks a company to share."""
        require(ctx, "grants.manage")
        if scope != "read":
            raise GrantScopeNotAvailable(
                "Only read access can be shared for now. Full CA Workspace access comes later."
            )
        grantor, grantee = (
            (ctx.org_id, other_org_id) if direction == "share" else (other_org_id, ctx.org_id)
        )
        now = self._clock.now()
        grant_id = new_id()
        try:
            async with self._tx(ctx) as conn:
                await conn.execute(
                    insert(models.access_grants).values(
                        id=grant_id,
                        grantor_org_id=grantor,
                        grantee_org_id=grantee,
                        scope=scope,
                        status="pending",
                        initiated_by="grantor" if direction == "share" else "grantee",
                        created_by=ctx.user_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
                await audit.record(
                    conn,
                    action="grant.created",
                    actor_user_id=ctx.user_id,
                    org_id=ctx.org_id,
                    target_table="tenancy.access_grants",
                    target_id=grant_id,
                    occurred_at=now,
                    metadata={
                        "grantor_org_id": str(grantor),
                        "grantee_org_id": str(grantee),
                        "scope": scope,
                    },
                )
                return await self._read_grant(conn, grant_id)
        except IntegrityError as exc:
            raise self._map_integrity(exc) from exc

    async def list_grants(self, ctx: OrgContext) -> list[Grant]:
        require(ctx, "grants.view")
        g = models.access_grants.c
        async with self._tx(ctx) as conn:
            rows = (
                await conn.execute(
                    select(models.access_grants)
                    .where(or_(g.grantor_org_id == ctx.org_id, g.grantee_org_id == ctx.org_id))
                    .order_by(g.created_at.desc(), g.id.desc())
                )
            ).all()
        return [_grant(r) for r in rows]

    async def accept_grant(self, ctx: OrgContext, grant_id: uuid.UUID) -> Grant:
        return await self._transition_grant(ctx, grant_id, to="active")

    async def revoke_grant(self, ctx: OrgContext, grant_id: uuid.UUID) -> Grant:
        return await self._transition_grant(ctx, grant_id, to="revoked")

    # --- internals -----------------------------------------------------------------------------------

    def _tx(self, ctx: OrgContext) -> Any:
        return tenant_transaction(self._engine, user_id=ctx.user_id, org_id=ctx.org_id)

    def _invite_link(self, token: str) -> str:
        # The token travels in the fragment, which browsers never send to a server or put in logs.
        return f"{self._settings.app_origin.rstrip('/')}/invite#token={token}"

    async def _find_open_invitation(self, conn: AsyncConnection, token: str) -> Any:
        row = (
            await conn.execute(
                text(
                    "SELECT invitation_id, org_id, org_name, org_type, email, role, expires_at, "
                    "accepted_at FROM tenancy.find_invitation(:h)"
                ),
                {"h": hash_token(token)},
            )
        ).first()
        if row is None or row.accepted_at is not None or row.expires_at <= self._clock.now():
            raise NotFound("This invitation link is invalid, expired or already used.")
        return row

    async def _read_org(self, conn: AsyncConnection, org_id: uuid.UUID) -> Organization:
        o = models.organizations.c
        row = (
            await conn.execute(select(o.id, o.type, o.name, o.created_at).where(o.id == org_id))
        ).one()
        return Organization(id=row.id, type=row.type, name=row.name, created_at=row.created_at)

    async def _read_grant(self, conn: AsyncConnection, grant_id: uuid.UUID) -> Grant:
        row = (
            await conn.execute(
                select(models.access_grants).where(models.access_grants.c.id == grant_id)
            )
        ).one()
        return _grant(row)

    async def _transition_grant(
        self, ctx: OrgContext, grant_id: uuid.UUID, *, to: Literal["active", "revoked"]
    ) -> Grant:
        require(ctx, "grants.manage")
        g = models.access_grants.c
        now = self._clock.now()
        try:
            async with self._tx(ctx) as conn:
                current = (
                    await conn.execute(
                        select(g.status).where(
                            g.id == grant_id,
                            or_(g.grantor_org_id == ctx.org_id, g.grantee_org_id == ctx.org_id),
                        )
                    )
                ).scalar_one_or_none()
                if current is None:
                    raise NotFound("Grant not found")
                values: dict[str, Any] = {"status": to, "updated_at": now}
                values["accepted_at" if to == "active" else "revoked_at"] = now
                await conn.execute(
                    update(models.access_grants).where(g.id == grant_id).values(**values)
                )
                await audit.record(
                    conn,
                    action="grant.accepted" if to == "active" else "grant.revoked",
                    actor_user_id=ctx.user_id,
                    org_id=ctx.org_id,
                    target_table="tenancy.access_grants",
                    target_id=grant_id,
                    occurred_at=now,
                    metadata={"from": current},
                )
                return await self._read_grant(conn, grant_id)
        except IntegrityError as exc:
            raise self._map_integrity(exc) from exc

    @staticmethod
    def _map_integrity(exc: DBAPIError) -> Exception:
        message = _constraint_message(exc)
        if message.startswith("last_owner"):
            return LastOwner("Make someone else an owner first.")
        if message.startswith("grant_org_types"):
            return Unprocessable(
                "Only a company can share, and only with a CA firm or an incubator."
            )
        if message.startswith("grant_transition") or message.startswith("grant_immutable"):
            return Conflict("This grant can't change that way.")
        if isinstance(exc.orig, pg_errors.ForeignKeyViolation):
            return NotFound("Organisation not found")
        if isinstance(exc.orig, pg_errors.UniqueViolation):
            return Conflict("These organisations already have an open grant.")
        return exc


def _org_body(org: Organization) -> dict[str, Any]:
    return {
        "id": str(org.id),
        "type": org.type,
        "name": org.name,
        "created_at": org.created_at.isoformat(),
    }


def _grant(row: Any) -> Grant:
    return Grant(
        id=row.id,
        grantor_org_id=row.grantor_org_id,
        grantee_org_id=row.grantee_org_id,
        scope=row.scope,
        status=row.status,
        initiated_by=row.initiated_by,
        created_at=row.created_at,
        accepted_at=row.accepted_at,
        revoked_at=row.revoked_at,
    )
