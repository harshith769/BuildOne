"""Idempotency keys (api-conventions.md §4) and ID-only sweep functions for the worker (data-model.md §6).

Revision ID: 0005_idempotency_and_sweeps
Revises: 0004_audit
Create Date: 2026-10-06

`platform.idempotency_keys` is an own-row table: RLS enabled with `user_id = current user`, not forced (like
the identity tables), so the app_owner-owned sweep functions below can list expired rows. The functions return
only IDs; the worker then deletes per user with that user's RLS context. EXECUTE goes to app_worker only.
`response_body` never holds secrets (an invitation replay stores the invitation without its link).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_idempotency_and_sweeps"
down_revision: str | None = "0004_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFINER = "LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE platform.idempotency_keys (
            user_id uuid NOT NULL REFERENCES identity.users (id) ON DELETE CASCADE,
            key uuid NOT NULL,
            request_sha256 text NOT NULL,
            response_status int NULL,
            response_body jsonb NULL,
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, key)
        )
        """
    )
    op.execute(
        "CREATE INDEX idempotency_keys_expires_at_idx ON platform.idempotency_keys (expires_at)"
    )
    op.execute("ALTER TABLE platform.idempotency_keys ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY user_isolation ON platform.idempotency_keys "
        "USING (user_id = platform.current_user_id()) "
        "WITH CHECK (user_id = platform.current_user_id())"
    )

    op.execute("CREATE INDEX sessions_idle_expires_at_idx ON identity.sessions (idle_expires_at)")
    op.execute(
        "CREATE INDEX sessions_absolute_expires_at_idx ON identity.sessions (absolute_expires_at)"
    )
    op.execute(
        f"""
        CREATE FUNCTION identity.expired_sessions(p_now timestamptz, p_limit int)
        RETURNS TABLE (session_id uuid, user_id uuid) {_DEFINER} AS $$
          SELECT s.id, s.user_id FROM identity.sessions s
          WHERE s.idle_expires_at <= p_now OR s.absolute_expires_at <= p_now
          ORDER BY s.user_id, s.id LIMIT p_limit
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION platform.expired_idempotency_keys(p_now timestamptz, p_limit int)
        RETURNS TABLE (user_id uuid, key uuid) {_DEFINER} AS $$
          SELECT k.user_id, k.key FROM platform.idempotency_keys k
          WHERE k.expires_at <= p_now ORDER BY k.user_id, k.key LIMIT p_limit
        $$
        """
    )
    for fn in (
        "identity.expired_sessions(timestamptz, int)",
        "platform.expired_idempotency_keys(timestamptz, int)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO app_worker")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS platform.expired_idempotency_keys(timestamptz, int)")
    op.execute("DROP FUNCTION IF EXISTS identity.expired_sessions(timestamptz, int)")
    op.execute("DROP INDEX IF EXISTS identity.sessions_absolute_expires_at_idx")
    op.execute("DROP INDEX IF EXISTS identity.sessions_idle_expires_at_idx")
    op.execute("DROP TABLE IF EXISTS platform.idempotency_keys")
