"""Identity: users, sessions, consents (data-model.md §4.1).

Revision ID: 0002_identity
Revises: 0001_baseline
Create Date: 2026-10-06

These tables are user-scoped, not tenant-scoped (no `org_id`). RLS is enabled with a policy that shows a row
only to its own user (`platform.current_user_id()`), and is deliberately NOT forced: the two SECURITY DEFINER
functions below run as the table owner (app_owner) and must see rows before the user is known (a session
cookie arrives, an identity-provider callback arrives). Services never connect as app_owner, so app_api and
app_worker are always subject to the policies.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_identity"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SERVICE_ROLES = "app_api, app_worker"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE identity.users (
            id uuid PRIMARY KEY,
            email citext NOT NULL UNIQUE,
            display_name text NOT NULL,
            idp_user_id text NOT NULL UNIQUE,
            status text NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'deletion_pending')),
            deletion_requested_at timestamptz NULL,
            age_confirmed_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT users_deletion_requested_iff_pending
                CHECK ((status = 'deletion_pending') = (deletion_requested_at IS NOT NULL))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE identity.sessions (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES identity.users (id) ON DELETE CASCADE,
            token_hash bytea NOT NULL UNIQUE,
            csrf_token_hash bytea NOT NULL,
            last_seen_at timestamptz NOT NULL,
            idle_expires_at timestamptz NOT NULL,
            absolute_expires_at timestamptz NOT NULL,
            ip inet NULL,
            user_agent text NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT sessions_idle_within_absolute CHECK (idle_expires_at <= absolute_expires_at)
        )
        """
    )
    op.execute("CREATE INDEX sessions_user_id_idx ON identity.sessions (user_id)")
    op.execute(
        """
        CREATE TABLE identity.consents (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES identity.users (id) ON DELETE CASCADE,
            document text NOT NULL CHECK (document IN ('terms', 'privacy')),
            version text NOT NULL,
            accepted_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT consents_user_document_version_key UNIQUE (user_id, document, version)
        )
        """
    )
    # The unique constraint's index leads with user_id, so it also serves the FK.

    for table, column in (("users", "id"), ("sessions", "user_id"), ("consents", "user_id")):
        op.execute(f"ALTER TABLE identity.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY user_isolation ON identity.{table} "
            f"USING ({column} = platform.current_user_id()) "
            f"WITH CHECK ({column} = platform.current_user_id())"
        )

    # Lookups that happen before the user is known. They return only what the caller already proves it holds
    # (a session token hash, or an identity-provider user ID from a verified code exchange).
    op.execute(
        """
        CREATE FUNCTION identity.find_session(p_token_hash bytea)
        RETURNS TABLE (
            session_id uuid,
            user_id uuid,
            csrf_token_hash bytea,
            last_seen_at timestamptz,
            idle_expires_at timestamptz,
            absolute_expires_at timestamptz,
            user_status text
        )
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
            SELECT s.id, s.user_id, s.csrf_token_hash, s.last_seen_at, s.idle_expires_at,
                   s.absolute_expires_at, u.status
            FROM identity.sessions s
            JOIN identity.users u ON u.id = s.user_id
            WHERE s.token_hash = p_token_hash
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION identity.find_user_by_idp(p_idp_user_id text)
        RETURNS TABLE (user_id uuid, user_status text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
            SELECT u.id, u.status FROM identity.users u WHERE u.idp_user_id = p_idp_user_id
        $$
        """
    )
    for fn in ("identity.find_session(bytea)", "identity.find_user_by_idp(text)"):
        op.execute(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO {SERVICE_ROLES}")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS identity.find_user_by_idp(text)")
    op.execute("DROP FUNCTION IF EXISTS identity.find_session(bytea)")
    op.execute("DROP TABLE IF EXISTS identity.consents")
    op.execute("DROP TABLE IF EXISTS identity.sessions")
    op.execute("DROP TABLE IF EXISTS identity.users")
