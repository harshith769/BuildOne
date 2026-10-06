"""Refuse expired invitation tokens at the database (backstop for the API's expiry check).

Revision ID: 0006_invitation_expiry_backstop
Revises: 0005_idempotency_and_sweeps
Create Date: 2026-10-06

`tenancy.invitation_token_matches` (used by the accept policies on memberships and invitations) now also
requires `expires_at > now()`. The API already refuses expired invitations using the injected Clock; this makes
the database refuse them too, whatever the application does.

The function is owned by app_rls_check (ADR-0013). app_owner holds that role WITH INHERIT FALSE, SET TRUE, so
the replacement runs as app_rls_check; CREATE on the schema is granted only for this step. CREATE OR REPLACE
keeps the owner and the EXECUTE grants; SECURITY DEFINER and the pinned search_path are restated because
OR REPLACE resets every attribute.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_invitation_expiry_backstop"
down_revision: str | None = "0005_idempotency_and_sweeps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHECK_ROLE = "app_rls_check"
_HEAD = """
CREATE OR REPLACE FUNCTION tenancy.invitation_token_matches(p_org uuid, p_role text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $fn$
  SELECT EXISTS (
    SELECT 1 FROM tenancy.invitations i
    JOIN tenancy.organizations o ON o.id = i.org_id AND o.status = 'active'
    WHERE i.token_hash = decode(NULLIF(current_setting('app.invitation_token_hash', true), ''), 'hex')
      AND i.org_id = p_org AND i.role = p_role AND i.accepted_at IS NULL
      AND platform.current_user_id() IS NOT NULL{extra})
$fn$
"""
WITH_EXPIRY = _HEAD.format(extra="\n      AND i.expires_at > now()")
WITHOUT_EXPIRY = _HEAD.format(extra="")


def _replace_as_check_role(sql: str) -> None:
    op.execute(f"GRANT CREATE ON SCHEMA tenancy TO {CHECK_ROLE}")
    op.execute(f"SET LOCAL ROLE {CHECK_ROLE}")
    op.execute(sql)
    op.execute("RESET ROLE")
    op.execute(f"REVOKE CREATE ON SCHEMA tenancy FROM {CHECK_ROLE}")


def upgrade() -> None:
    _replace_as_check_role(WITH_EXPIRY)


def downgrade() -> None:
    _replace_as_check_role(WITHOUT_EXPIRY)
