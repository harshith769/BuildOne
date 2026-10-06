"""The role x action matrix (docs/auth-and-tenancy.md §4) and idempotency fingerprints."""

from __future__ import annotations

import pytest

from app.modules.tenancy.permissions import MATRIX, AccessLevel, allowed, require
from app.platform.errors import Forbidden, ValidationProblem
from app.platform.idempotency import fingerprint, parse_key

EXPECTED: dict[str, set[AccessLevel]] = {
    "org.view": {"owner", "member", "viewer", "grantee"},
    "data.view": {"owner", "member", "viewer", "grantee"},
    "data.edit": {"owner", "member"},
    "copilot.use": {"owner", "member"},
    "documents.upload": {"owner", "member"},
    "members.view": {"owner", "member", "viewer"},
    "members.manage": {"owner"},
    "invitations.manage": {"owner"},
    "grants.view": {"owner", "member", "viewer"},
    "grants.manage": {"owner"},
    "org.export": {"owner"},
    "org.delete": {"owner"},
    "launchpad.handoff": {"owner"},
}
LEVELS: list[AccessLevel] = ["owner", "member", "viewer", "grantee"]


def test_matrix_matches_the_documented_table() -> None:
    assert {action: set(levels) for action, levels in MATRIX.items()} == EXPECTED


@pytest.mark.parametrize("action", sorted(EXPECTED))
@pytest.mark.parametrize("level", LEVELS)
def test_require_follows_the_matrix(level: AccessLevel, action: str) -> None:
    if level in EXPECTED[action]:
        require(level, action)
    else:
        with pytest.raises(Forbidden):
            require(level, action)


def test_grantees_only_ever_view() -> None:
    assert {a for a in MATRIX if allowed("grantee", a)} == {"org.view", "data.view"}


def test_unknown_actions_are_programming_errors() -> None:
    with pytest.raises(ValueError, match="unknown action"):
        allowed("owner", "org.teleport")


def test_fingerprint_is_stable_and_body_sensitive() -> None:
    a = fingerprint("post", "/v1/orgs", {"name": "A", "type": "team"})
    assert a == fingerprint("POST", "/v1/orgs", {"type": "team", "name": "A"})
    assert a != fingerprint("POST", "/v1/orgs", {"type": "team", "name": "B"})
    assert a != fingerprint("POST", "/v1/orgs/x", {"type": "team", "name": "A"})


@pytest.mark.parametrize("value", [None, "", "not-a-uuid"])
def test_idempotency_key_must_be_a_uuid(value: str | None) -> None:
    with pytest.raises(ValidationProblem):
        parse_key(value)
