"""Baseline: module schemas, grants, RLS helper functions, job-queue schema.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-06

Runs as app_owner. Roles (app_owner, app_api, app_worker, app_ingest, app_readonly) and extensions
(vector, pg_trgm, citext) already exist: they are created by infra/postgres/initdb (or by the admin role on
managed Postgres, ADR-0012). This revision never creates extensions (.claude/rules/migrations.md).

Privilege model (data-model.md §2):
- app_api and app_worker get USAGE on every module schema and, through default privileges, DML on tables
  app_owner creates later. Append-only tables (audit.events, ai.calls) revoke UPDATE/DELETE in their own
  revisions.
- app_ingest gets DML on the knowledge schema only.
- app_readonly gets nothing yet; pilot metrics views grant it SELECT explicitly (M14).
"""

from collections.abc import Sequence

from alembic import op
from procrastinate.schema import SchemaManager

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MODULE_SCHEMAS = (
    "identity",
    "tenancy",
    "audit",
    "facts",
    "rules",
    "obligations",
    "knowledge",
    "ai",
    "copilot",
    "explainer",
    "documents",
    "launchpad",
    "notifications",
    "platform",
)
SERVICE_ROLES = "app_api, app_worker"


def upgrade() -> None:
    for schema in MODULE_SCHEMAS:
        op.execute(f"CREATE SCHEMA {schema} AUTHORIZATION app_owner")
        op.execute(f"REVOKE ALL ON SCHEMA {schema} FROM PUBLIC")
        op.execute(f"GRANT USAGE ON SCHEMA {schema} TO {SERVICE_ROLES}")
        op.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA {schema} "
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {SERVICE_ROLES}"
        )
        op.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA {schema} "
            f"GRANT USAGE, SELECT ON SEQUENCES TO {SERVICE_ROLES}"
        )

    op.execute("GRANT USAGE ON SCHEMA knowledge, platform TO app_ingest")
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA knowledge "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_ingest"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA knowledge "
        "GRANT USAGE, SELECT ON SEQUENCES TO app_ingest"
    )

    # Readiness check reads the migration version.
    op.execute(f"GRANT SELECT ON public.alembic_version TO {SERVICE_ROLES}")

    # RLS context helpers (data-model.md §3). Unset settings return NULL, so policies fail closed.
    op.execute(
        """
        CREATE FUNCTION platform.current_user_id() RETURNS uuid
        LANGUAGE sql STABLE PARALLEL SAFE
        AS $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform.current_org_id() RETURNS uuid
        LANGUAGE sql STABLE PARALLEL SAFE
        AS $$ SELECT NULLIF(current_setting('app.org_id', true), '')::uuid $$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION platform.current_user_id(), platform.current_org_id() FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION platform.current_user_id(), platform.current_org_id() "
        f"TO {SERVICE_ROLES}, app_ingest"
    )

    # Job queue (ADR-0004): Procrastinate's own schema SQL, installed into a dedicated schema.
    # Upgrading Procrastinate later = a new revision that applies its migration files in order.
    op.execute("CREATE SCHEMA procrastinate AUTHORIZATION app_owner")
    op.execute("REVOKE ALL ON SCHEMA procrastinate FROM PUBLIC")
    op.execute(f"GRANT USAGE ON SCHEMA procrastinate TO {SERVICE_ROLES}")
    op.execute("SET LOCAL search_path TO procrastinate")
    # Executed through the raw driver connection: the SQL contains ':' and '%' that bind-parameter
    # parsing would misread.
    raw = op.get_bind().connection.driver_connection
    if raw is None:
        raise RuntimeError("no driver connection available")
    raw.execute(SchemaManager.get_schema())  # type: ignore[union-attr]
    op.execute("SET LOCAL search_path TO DEFAULT")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA procrastinate TO {SERVICE_ROLES}"
    )
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA procrastinate TO {SERVICE_ROLES}")
    op.execute(f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA procrastinate TO {SERVICE_ROLES}")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS procrastinate CASCADE")
    op.execute(f"REVOKE SELECT ON public.alembic_version FROM {SERVICE_ROLES}")
    for schema in reversed(MODULE_SCHEMAS):
        op.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA {schema} REVOKE ALL ON TABLES FROM {SERVICE_ROLES}"
        )
        op.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA {schema} REVOKE ALL ON SEQUENCES FROM {SERVICE_ROLES}"
        )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA knowledge REVOKE ALL ON TABLES FROM app_ingest"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA knowledge REVOKE ALL ON SEQUENCES FROM app_ingest"
    )
    for schema in reversed(MODULE_SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
