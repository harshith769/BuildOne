"""Database-level gates that every future migration must pass (data-model.md §7, ADR-0011).

1. Every table with an `org_id` column has RLS enabled AND forced, and a `tenant_isolation` policy.
2. Only allowlisted extensions are installed.
These run in CI on every PR, so a migration that forgets RLS cannot merge.
"""

from __future__ import annotations

import psycopg

from tests.conftest import EphemeralDatabase, owner_connection

ALLOWED_EXTENSIONS = {"plpgsql", "vector", "pg_trgm", "citext"}
SYSTEM_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast", "procrastinate")

_UNPROTECTED_TENANT_TABLES = """
SELECT n.nspname || '.' || c.relname
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'org_id' AND NOT a.attisdropped
WHERE c.relkind IN ('r', 'p')
  AND n.nspname <> ALL (%s)
  AND (
    NOT c.relrowsecurity
    OR NOT c.relforcerowsecurity
    OR NOT EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid AND p.polname = 'tenant_isolation')
  )
ORDER BY 1
"""


def unprotected_tenant_tables(conn: psycopg.Connection) -> list[str]:
    return [
        row[0]
        for row in conn.execute(_UNPROTECTED_TENANT_TABLES, (list(SYSTEM_SCHEMAS),)).fetchall()
    ]


def test_every_tenant_table_has_forced_rls_and_policy(test_db: EphemeralDatabase) -> None:
    with owner_connection(test_db) as conn:
        assert unprotected_tenant_tables(conn) == []


def test_guard_catches_a_table_without_forced_rls(test_db: EphemeralDatabase) -> None:
    """The guard itself must fail on a bad table, otherwise a passing run proves nothing."""
    with owner_connection(test_db) as conn:
        conn.execute("BEGIN")
        conn.execute("CREATE TABLE facts.guard_probe (id uuid PRIMARY KEY, org_id uuid NOT NULL)")
        assert unprotected_tenant_tables(conn) == ["facts.guard_probe"]
        conn.execute("ALTER TABLE facts.guard_probe ENABLE ROW LEVEL SECURITY")
        assert unprotected_tenant_tables(conn) == ["facts.guard_probe"], (
            "ENABLE without FORCE is not enough"
        )
        conn.execute("ALTER TABLE facts.guard_probe FORCE ROW LEVEL SECURITY")
        conn.execute(
            "CREATE POLICY tenant_isolation ON facts.guard_probe "
            "USING (org_id = platform.current_org_id()) WITH CHECK (org_id = platform.current_org_id())"
        )
        assert unprotected_tenant_tables(conn) == []
        conn.execute("ROLLBACK")


def test_only_allowlisted_extensions_are_installed(test_db: EphemeralDatabase) -> None:
    with owner_connection(test_db) as conn:
        installed = {row[0] for row in conn.execute("SELECT extname FROM pg_extension").fetchall()}
    assert installed <= ALLOWED_EXTENSIONS, (
        f"extensions outside the allowlist: {installed - ALLOWED_EXTENSIONS}"
    )
    assert {"vector", "pg_trgm", "citext"} <= installed
