"""The org dependency for `/v1/orgs/{org_id}/...` routes (docs/auth-and-tenancy.md §5).

The organisation comes only from the URL path. The caller must be a member, or belong to an org holding an
active access grant from it; otherwise the answer is 404, so existence never leaks.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Request

from app.modules.identity.dependencies import CurrentSession
from app.modules.tenancy.service import OrgContext, TenancyService


def get_tenancy_service(request: Request) -> TenancyService:
    service: TenancyService = request.app.state.tenancy
    return service


Tenancy = Annotated[TenancyService, Depends(get_tenancy_service)]


async def org_context(org_id: uuid.UUID, session: CurrentSession, tenancy: Tenancy) -> OrgContext:
    return await tenancy.resolve_access(user_id=session.user_id, org_id=org_id)


Org = Annotated[OrgContext, Depends(org_context)]
