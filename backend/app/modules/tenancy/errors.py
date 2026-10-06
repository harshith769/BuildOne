"""Tenancy-specific problem types (rendered by app.platform.errors)."""

from __future__ import annotations

from app.platform.errors import Conflict, DomainError


class GrantScopeNotAvailable(DomainError):
    """`manage` grants are reserved for the CA Workspace (D-29); the API never creates them yet."""

    status, code, title = 422, "grant_scope_not_available", "This access level isn't available yet"


class InvitationEmailMismatch(Conflict):
    code, title = (
        "invitation_email_mismatch",
        "This invitation was sent to a different email address",
    )


class LastOwner(Conflict):
    code, title = "last_owner", "An organisation needs at least one owner"
