"""Database-level gates every migration must pass (data-model.md §3 §7, ADR-0011, ADR-0013).

1. Every table with `org_id` (and the tenancy tables keyed otherwise) has RLS enabled AND forced, and its
   policies match a known class: the company-data template from `app.platform.rls`, or a registered table.
   A new table that fits neither fails, so no table can skip classification.
2. Read stays read: no INSERT/UPDATE/DELETE/ALL policy references `tenancy.can_read` (audit insert excepted).
3. `app_rls_check` is NOLOGIN, owns only the check functions, and is granted to no service role.
4. Only allowlisted extensions are installed.
"""

from __future__ import annotations

import psycopg

from app.platform.rls import company_data_policies
from tests.support.db import EphemeralDatabase, owner_connection

ALLOWED_EXTENSIONS = {"plpgsql", "vector", "pg_trgm", "citext"}
SYSTEM_SCHEMAS = ["pg_catalog", "information_schema", "pg_toast", "procrastinate"]

COMPANY_DATA = {
    ("tenant_read", "r"),
    ("tenant_insert", "a"),
    ("tenant_update", "w"),
    ("tenant_delete", "d"),
}
# Tables whose policies are designed individually (data-model.md §4.2-4.3). (policy name, command) sets.
REGISTERED: dict[str, set[tuple[str, str]]] = {
    "tenancy.organizations": {("org_read", "r"), ("org_insert", "a"), ("org_update", "w")},
    "tenancy.memberships": {
        ("members_read", "r"),
        ("members_insert", "a"),
        ("members_bootstrap", "a"),
        ("members_accept", "a"),
        ("members_update", "w"),
        ("members_delete", "d"),
        ("members_leave", "d"),
    },
    "tenancy.invitations": {
        ("invitations_owner", "*"),
        ("invitations_token_read", "r"),
        ("invitations_accept", "w"),
    },
    "tenancy.access_grants": {("grants_read", "r"), ("grants_insert", "a"), ("grants_update", "w")},
    "audit.events": {("audit_insert", "a")},
}
# The one deliberate exception (owner decision, ADR-0013): every actor who can read an org, viewers and
# active grantees included, must be able to append audit rows. Audit rows are never company data.
READ_CHECK_IN_WRITE_ALLOWED = {"audit.events:audit_insert"}
CHECK_FUNCTIONS = {
    "is_member",
    "is_owner",
    "can_edit",
    "can_read",
    "is_creator_without_members",
    "shares_org_with",
    "invitation_token_matches",
    "find_invitation",
    "last_owner_guard",
    "invitations_guard",
    "access_grants_guard",
}

_TENANT_TABLES = """
SELECT n.nspname || '.' || c.relname, c.relrowsecurity, c.relforcerowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p') AND n.nspname <> ALL (%s)
  AND (EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attname = 'org_id'
               AND NOT a.attisdropped)
       OR n.nspname || '.' || c.relname = ANY (%s))
ORDER BY 1
"""
_POLICIES = """
SELECT p.polname, p.polcmd::text FROM pg_policy p
WHERE p.polrelid = %s::regclass
"""


def policy_violations(conn: psycopg.Connection) -> list[str]:
    problems = []
    for table, enabled, forced in conn.execute(
        _TENANT_TABLES, (SYSTEM_SCHEMAS, list(REGISTERED))
    ).fetchall():
        if not (enabled and forced):
            problems.append(f"{table}: RLS not enabled and forced")
            continue
        policies = {(name, cmd) for name, cmd in conn.execute(_POLICIES, (table,)).fetchall()}
        if policies != COMPANY_DATA and policies != REGISTERED.get(table):
            problems.append(f"{table}: policies {sorted(policies)} match no known class")
    return problems


def read_check_in_write_policies(conn: psycopg.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT c.relnamespace::regnamespace || '.' || c.relname || ':' || p.polname
        FROM pg_policy p JOIN pg_class c ON c.oid = p.polrelid
        WHERE p.polcmd <> 'r'
          AND (coalesce(pg_get_expr(p.polqual, p.polrelid), '') LIKE '%%can_read%%'
               OR coalesce(pg_get_expr(p.polwithcheck, p.polrelid), '') LIKE '%%can_read%%')
        ORDER BY 1
        """
    ).fetchall()
    return [r[0] for r in rows if r[0] not in READ_CHECK_IN_WRITE_ALLOWED]


def test_every_tenant_table_is_forced_and_classified(test_db: EphemeralDatabase) -> None:
    with owner_connection(test_db) as conn:
        assert policy_violations(conn) == []


def test_read_check_never_appears_in_write_policies(test_db: EphemeralDatabase) -> None:
    with owner_connection(test_db) as conn:
        assert read_check_in_write_policies(conn) == []


def test_guard_catches_unprotected_and_unclassified_tables(test_db: EphemeralDatabase) -> None:
    """The guards must fail on bad tables, otherwise a passing run proves nothing."""
    with owner_connection(test_db) as conn:
        conn.execute("BEGIN")
        conn.execute("CREATE TABLE facts.guard_probe (id uuid PRIMARY KEY, org_id uuid NOT NULL)")
        assert policy_violations(conn) == ["facts.guard_probe: RLS not enabled and forced"]
        conn.execute("ALTER TABLE facts.guard_probe ENABLE ROW LEVEL SECURITY")
        assert policy_violations(conn) == ["facts.guard_probe: RLS not enabled and forced"], (
            "ENABLE without FORCE is not enough"
        )
        conn.execute("ALTER TABLE facts.guard_probe FORCE ROW LEVEL SECURITY")
        conn.execute(
            "CREATE POLICY tenant_isolation ON facts.guard_probe "
            "USING (org_id = platform.current_org_id()) WITH CHECK (org_id = platform.current_org_id())"
        )
        assert policy_violations(conn)[0].startswith("facts.guard_probe: policies")
        conn.execute("DROP POLICY tenant_isolation ON facts.guard_probe")
        for statement in company_data_policies("facts.guard_probe")[2:]:
            conn.execute(statement)
        assert policy_violations(conn) == []
        conn.execute(
            "CREATE POLICY sneaky ON facts.guard_probe FOR UPDATE USING (tenancy.can_read(org_id))"
        )
        assert read_check_in_write_policies(conn) == ["facts.guard_probe:sneaky"]
        conn.execute("ROLLBACK")


def test_rls_check_role_is_minimal(test_db: EphemeralDatabase) -> None:
    with owner_connection(test_db) as conn:
        role = conn.execute(
            "SELECT rolcanlogin, rolbypassrls, rolsuper, rolcreaterole, rolcreatedb "
            "FROM pg_roles WHERE rolname = 'app_rls_check'"
        ).fetchone()
        assert role == (False, True, False, False, False)
        owned = conn.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner "
            "WHERE r.rolname = 'app_rls_check'"
        ).fetchall()
        assert owned == [], "app_rls_check must own no tables"
        functions = conn.execute(
            "SELECT p.proname, p.pronamespace::regnamespace::text, p.prosecdef, p.proconfig "
            "FROM pg_proc p JOIN pg_roles r ON r.oid = p.proowner WHERE r.rolname = 'app_rls_check'"
        ).fetchall()
        assert {f[0] for f in functions} == CHECK_FUNCTIONS
        for name, schema, secdef, config in functions:
            assert schema == "tenancy", name
            assert secdef, f"{name} must be SECURITY DEFINER"
            assert config == ["search_path=pg_catalog, pg_temp"], f"{name} must pin search_path"
        members = conn.execute(
            "SELECT m.rolname FROM pg_auth_members am "
            "JOIN pg_roles g ON g.oid = am.roleid JOIN pg_roles m ON m.oid = am.member "
            "WHERE g.rolname = 'app_rls_check'"
        ).fetchall()
        assert {m[0] for m in members} <= {"app_owner"}, "never granted to a service role"
        inherit = conn.execute(
            "SELECT am.inherit_option FROM pg_auth_members am "
            "JOIN pg_roles g ON g.oid = am.roleid JOIN pg_roles m ON m.oid = am.member "
            "WHERE g.rolname = 'app_rls_check' AND m.rolname = 'app_owner'"
        ).fetchone()
        assert inherit == (False,), "app_owner must not inherit the bypass"


def test_only_allowlisted_extensions_are_installed(test_db: EphemeralDatabase) -> None:
    with owner_connection(test_db) as conn:
        installed = {row[0] for row in conn.execute("SELECT extname FROM pg_extension").fetchall()}
    assert installed <= ALLOWED_EXTENSIONS, (
        f"extensions outside the allowlist: {installed - ALLOWED_EXTENSIONS}"
    )
    assert {"vector", "pg_trgm", "citext"} <= installed
