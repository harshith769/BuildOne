"""Audit log: append-only `audit.events` (data-model.md §4.3, FR-PLT-05, NFR-SEC-06).

Revision ID: 0004_audit
Revises: 0003_tenancy
Create Date: 2026-10-06

Insert policy (ADR-0013): anyone acting in an organisation writes audit rows, including viewers and active
grantees, so the org write check is NOT used. A user row needs `actor_user_id = current user` and, when it
names an org, read access to that org. A system row (NULL actor) is allowed only for the worker role. Nobody
can UPDATE or DELETE: no policies, and the privileges are revoked. There is no SELECT policy yet (no reader
in the MVP API), so reads fail closed.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_audit"
down_revision: str | None = "0003_tenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        r"""
        CREATE TABLE audit.events (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            occurred_at timestamptz NOT NULL DEFAULT now(),
            actor_user_id uuid NULL,
            org_id uuid NULL,
            request_id text NOT NULL,
            action text NOT NULL CHECK (action ~ '^[a-z_]+\.[a-z_]+$'),
            target_table text NOT NULL,
            target_id text NOT NULL,
            metadata jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(metadata) = 'object')
        )
        """
    )
    # actor_user_id and org_id are deliberately loose references: audit rows outlive their targets.
    op.execute("CREATE INDEX events_org_id_occurred_at_idx ON audit.events (org_id, occurred_at)")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit.events FROM app_api, app_worker")
    op.execute("ALTER TABLE audit.events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit.events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_insert ON audit.events FOR INSERT WITH CHECK (
          (actor_user_id = platform.current_user_id()
             AND (org_id IS NULL OR tenancy.can_read(org_id)))
          OR (actor_user_id IS NULL AND current_user = 'app_worker'
             AND (org_id IS NULL OR org_id = platform.current_org_id()))
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit.events")
