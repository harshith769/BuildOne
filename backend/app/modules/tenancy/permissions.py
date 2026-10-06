"""Who can do what (docs/auth-and-tenancy.md §4). The only place role checks live; services call `require`.

Access levels: the caller's membership role in the organisation, or `grantee` when they reach it through an
active access grant held by an organisation they belong to. Grantees only ever view (FR-PLT-03, D-29).
"""

from __future__ import annotations

from typing import Literal

from app.platform.errors import Forbidden

AccessLevel = Literal["owner", "member", "viewer", "grantee"]
Role = Literal["owner", "member", "viewer"]

_ALL: frozenset[AccessLevel] = frozenset({"owner", "member", "viewer", "grantee"})
_MEMBERS: frozenset[AccessLevel] = frozenset({"owner", "member", "viewer"})
_EDITORS: frozenset[AccessLevel] = frozenset({"owner", "member"})
_OWNERS: frozenset[AccessLevel] = frozenset({"owner"})

MATRIX: dict[str, frozenset[AccessLevel]] = {
    "org.view": _ALL,  # name and type
    "data.view": _ALL,  # facts, obligations, explanations
    "data.edit": _EDITORS,  # edit facts, confirm proposals, mark obligations done
    "copilot.use": _EDITORS,
    "documents.upload": _EDITORS,
    "members.view": _MEMBERS,
    "members.manage": _OWNERS,  # change roles, remove members
    "invitations.manage": _OWNERS,
    "grants.view": _MEMBERS,
    "grants.manage": _OWNERS,  # share, accept, revoke
    "org.export": _OWNERS,
    "org.delete": _OWNERS,
    "launchpad.handoff": _OWNERS,
}


def allowed(level: AccessLevel, action: str) -> bool:
    try:
        return level in MATRIX[action]
    except KeyError:
        raise ValueError(f"unknown action {action!r}") from None


def require(level: AccessLevel, action: str) -> None:
    if not allowed(level, action):
        raise Forbidden()
