"""Tenancy routes: organisations, members, invitations, access grants (docs/auth-and-tenancy.md §4-6)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field

from app.modules.identity.dependencies import CurrentSession
from app.modules.tenancy.dependencies import Org, Tenancy
from app.modules.tenancy.service import Grant
from app.platform import idempotency

orgs_router = APIRouter(prefix="/v1/orgs", tags=["organisations"])
invitations_router = APIRouter(prefix="/v1/invitations", tags=["invitations"])

RoleName = Literal["owner", "member", "viewer"]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


class OrgIn(BaseModel):
    type: Literal["team", "company", "ca_firm", "incubator"]
    name: str = Field(min_length=1, max_length=200)


class OrgOut(BaseModel):
    id: uuid.UUID
    type: str
    name: str
    created_at: datetime


class MyOrgOut(BaseModel):
    id: uuid.UUID
    type: str
    name: str
    role: str


class CreatedOrgOut(OrgOut):
    role: str


class OrgList(BaseModel):
    items: list[MyOrgOut]
    next_cursor: None = None


class OrgDetailOut(OrgOut):
    access: Literal["owner", "member", "viewer", "grantee"]


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str | None
    display_name: str | None
    role: str
    joined_at: datetime


class MemberList(BaseModel):
    items: list[MemberOut]
    next_cursor: None = None


class RoleIn(BaseModel):
    role: RoleName


class InvitationIn(BaseModel):
    email: EmailStr
    role: RoleName = "member"


class InvitationCreatedOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime
    invite_link: str | None = Field(
        description="One-time link, returned only on the first response; null on a replay"
    )
    link_available: bool


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime
    expired: bool


class InvitationList(BaseModel):
    items: list[InvitationOut]
    next_cursor: None = None


class InvitationTokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=128)


class InvitationAcceptIn(InvitationTokenIn):
    confirm_email_mismatch: bool = False


class InvitationPreviewOut(BaseModel):
    org_name: str
    org_type: str
    role: str
    email: str
    email_matches: bool


class GrantIn(BaseModel):
    other_org_id: uuid.UUID
    direction: Literal["share", "request"] = Field(
        description="share: this company shares with the other org; request: this org asks a company"
    )
    scope: Literal["read", "manage"] = "read"


class GrantOut(BaseModel):
    id: uuid.UUID
    grantor_org_id: uuid.UUID
    grantee_org_id: uuid.UUID
    scope: str
    status: str
    initiated_by: str
    created_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


class GrantList(BaseModel):
    items: list[GrantOut]
    next_cursor: None = None


def _grant_out(g: Grant) -> GrantOut:
    return GrantOut(
        id=g.id,
        grantor_org_id=g.grantor_org_id,
        grantee_org_id=g.grantee_org_id,
        scope=g.scope,
        status=g.status,
        initiated_by=g.initiated_by,
        created_at=g.created_at,
        accepted_at=g.accepted_at,
        revoked_at=g.revoked_at,
    )


# --- organisations ---------------------------------------------------------------------------------


@orgs_router.post(
    "",
    status_code=201,
    response_model=CreatedOrgOut,
    summary="Create an organisation (requires Idempotency-Key)",
)
async def create_org(
    request: Request,
    body: OrgIn,
    session: CurrentSession,
    tenancy: Tenancy,
    idempotency_key: IdempotencyKeyHeader = None,
) -> Response:
    key = idempotency.parse_key(idempotency_key)
    status, payload = await tenancy.create_organization(
        user_id=session.user_id,
        org_type=body.type,
        name=body.name,
        idempotency_key=key,
        request_sha256=idempotency.fingerprint("POST", request.url.path, body.model_dump()),
    )
    return JSONResponse(payload, status_code=status)


@orgs_router.get("", summary="Organisations I belong to")
async def list_orgs(session: CurrentSession, tenancy: Tenancy) -> OrgList:
    orgs = await tenancy.list_my_organizations(session.user_id)
    return OrgList(items=[MyOrgOut(id=o.id, type=o.type, name=o.name, role=o.role) for o in orgs])


@orgs_router.get("/{org_id}", summary="One organisation (members and active grantees)")
async def get_org(ctx: Org, tenancy: Tenancy) -> OrgDetailOut:
    org = await tenancy.get_organization(ctx)
    return OrgDetailOut(
        id=org.id, type=org.type, name=org.name, created_at=org.created_at, access=ctx.level
    )


# --- members ---------------------------------------------------------------------------------------


@orgs_router.get("/{org_id}/members", summary="Members of the organisation")
async def list_members(ctx: Org, tenancy: Tenancy) -> MemberList:
    members = await tenancy.list_members(ctx)
    return MemberList(
        items=[
            MemberOut(
                user_id=m.user_id,
                email=m.email,
                display_name=m.display_name,
                role=m.role,
                joined_at=m.joined_at,
            )
            for m in members
        ]
    )


@orgs_router.patch("/{org_id}/members/{user_id}", status_code=204, summary="Change a member's role")
async def change_role(user_id: uuid.UUID, body: RoleIn, ctx: Org, tenancy: Tenancy) -> Response:
    await tenancy.change_role(ctx, user_id, body.role)
    return Response(status_code=204)


@orgs_router.delete(
    "/{org_id}/members/{user_id}",
    status_code=204,
    summary="Remove a member, or leave (own user ID)",
)
async def remove_member(user_id: uuid.UUID, ctx: Org, tenancy: Tenancy) -> Response:
    await tenancy.remove_member(ctx, user_id)
    return Response(status_code=204)


# --- invitations -----------------------------------------------------------------------------------


@orgs_router.post(
    "/{org_id}/invitations",
    status_code=201,
    response_model=InvitationCreatedOut,
    summary="Invite someone by email (requires Idempotency-Key)",
)
async def create_invitation(
    request: Request,
    body: InvitationIn,
    ctx: Org,
    tenancy: Tenancy,
    idempotency_key: IdempotencyKeyHeader = None,
) -> Response:
    key = idempotency.parse_key(idempotency_key)
    status, payload = await tenancy.create_invitation(
        ctx,
        email=str(body.email),
        role=body.role,
        idempotency_key=key,
        request_sha256=idempotency.fingerprint("POST", request.url.path, body.model_dump()),
    )
    return JSONResponse(payload, status_code=status)


@orgs_router.get("/{org_id}/invitations", summary="Open invitations")
async def list_invitations(ctx: Org, tenancy: Tenancy) -> InvitationList:
    rows = await tenancy.list_invitations(ctx)
    return InvitationList(
        items=[
            InvitationOut(
                id=i.id, email=i.email, role=i.role, expires_at=i.expires_at, expired=i.expired
            )
            for i in rows
        ]
    )


@orgs_router.delete(
    "/{org_id}/invitations/{invitation_id}", status_code=204, summary="Revoke an invitation"
)
async def revoke_invitation(invitation_id: uuid.UUID, ctx: Org, tenancy: Tenancy) -> Response:
    await tenancy.revoke_invitation(ctx, invitation_id)
    return Response(status_code=204)


@invitations_router.post("/lookup", summary="Preview an invitation (the token travels in the body)")
async def lookup_invitation(
    body: InvitationTokenIn, session: CurrentSession, tenancy: Tenancy
) -> InvitationPreviewOut:
    p = await tenancy.preview_invitation(user_id=session.user_id, token=body.token)
    return InvitationPreviewOut(
        org_name=p.org_name,
        org_type=p.org_type,
        role=p.role,
        email=p.email,
        email_matches=p.email_matches,
    )


@invitations_router.post("/accept", summary="Accept an invitation")
async def accept_invitation(
    body: InvitationAcceptIn, session: CurrentSession, tenancy: Tenancy
) -> MyOrgOut:
    org = await tenancy.accept_invitation(
        user_id=session.user_id,
        token=body.token,
        confirm_email_mismatch=body.confirm_email_mismatch,
    )
    return MyOrgOut(id=org.id, type=org.type, name=org.name, role=org.role)


# --- access grants (API core; the share screens arrive in M10) -------------------------------------


@orgs_router.post(
    "/{org_id}/access-grants", status_code=201, summary="Share, or ask a company to share"
)
async def create_grant(body: GrantIn, ctx: Org, tenancy: Tenancy) -> GrantOut:
    grant = await tenancy.create_grant(
        ctx, other_org_id=body.other_org_id, direction=body.direction, scope=body.scope
    )
    return _grant_out(grant)


@orgs_router.get("/{org_id}/access-grants", summary="Grants to and from this organisation")
async def list_grants(ctx: Org, tenancy: Tenancy) -> GrantList:
    return GrantList(items=[_grant_out(g) for g in await tenancy.list_grants(ctx)])


@orgs_router.post("/{org_id}/access-grants/{grant_id}/accept", summary="Accept a pending grant")
async def accept_grant(grant_id: uuid.UUID, ctx: Org, tenancy: Tenancy) -> GrantOut:
    return _grant_out(await tenancy.accept_grant(ctx, grant_id))


@orgs_router.post("/{org_id}/access-grants/{grant_id}/revoke", summary="Revoke a grant")
async def revoke_grant(grant_id: uuid.UUID, ctx: Org, tenancy: Tenancy) -> GrantOut:
    return _grant_out(await tenancy.revoke_grant(ctx, grant_id))
