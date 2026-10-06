"""Tenancy: organisations, memberships, invitations, access grants, and the RLS check functions (ADR-0013).

Revision ID: 0003_tenancy
Revises: 0002_identity
Create Date: 2026-10-06

Check functions are owned by `app_rls_check` (NOLOGIN BYPASSRLS, owns nothing else), so they see the rows they
need under FORCE RLS without passing through policies (no recursion). Each is SECURITY DEFINER, STABLE,
read-only, with `search_path = pg_catalog, pg_temp`, and answers a question about the caller
(`platform.current_user_id()`) or about a token hash the caller holds.

Policy classes (data-model.md §3-§4.2):
- organizations: read = members and active grantees; insert = the creator; update = owners.
- memberships, invitations: org admin (owners), plus narrow bootstrap / accept / leave policies.
- access_grants: visible to members of either side; owners of the right side create, accept and revoke;
  transitions and org types enforced by a trigger.
Column rules RLS can't express (WITH CHECK sees only the new row) are triggers.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_tenancy"
down_revision: str | None = "0002_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SERVICE_ROLES = "app_api, app_worker"
CHECK_ROLE = "app_rls_check"
TABLES = (
    "tenancy.organizations",
    "tenancy.memberships",
    "tenancy.invitations",
    "tenancy.access_grants",
)
# (signature, body). All owned by app_rls_check; see module docstring.
_DEFINER = "LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp"
CHECK_FUNCTIONS: tuple[tuple[str, str], ...] = (
    (
        "tenancy.is_member(p_org uuid) RETURNS boolean",
        """SELECT EXISTS (
             SELECT 1 FROM tenancy.memberships m
             JOIN tenancy.organizations o ON o.id = m.org_id AND o.status = 'active'
             WHERE m.org_id = p_org AND m.user_id = platform.current_user_id())""",
    ),
    (
        "tenancy.is_owner(p_org uuid) RETURNS boolean",
        """SELECT EXISTS (
             SELECT 1 FROM tenancy.memberships m
             JOIN tenancy.organizations o ON o.id = m.org_id AND o.status = 'active'
             WHERE m.org_id = p_org AND m.user_id = platform.current_user_id() AND m.role = 'owner')""",
    ),
    (
        "tenancy.can_edit(p_org uuid) RETURNS boolean",
        """SELECT EXISTS (
             SELECT 1 FROM tenancy.memberships m
             JOIN tenancy.organizations o ON o.id = m.org_id AND o.status = 'active'
             WHERE m.org_id = p_org AND m.user_id = platform.current_user_id()
               AND m.role IN ('owner', 'member'))""",
    ),
    (
        "tenancy.can_read(p_org uuid) RETURNS boolean",
        """SELECT tenancy.is_member(p_org) OR EXISTS (
             SELECT 1 FROM tenancy.access_grants g
             JOIN tenancy.organizations gr ON gr.id = g.grantor_org_id AND gr.status = 'active'
             JOIN tenancy.organizations ge ON ge.id = g.grantee_org_id AND ge.status = 'active'
             JOIN tenancy.memberships m
               ON m.org_id = g.grantee_org_id AND m.user_id = platform.current_user_id()
             WHERE g.grantor_org_id = p_org AND g.status = 'active')""",
    ),
    (
        # Does the caller share an active organisation with p_user? (Lets members see each other's names.)
        "tenancy.shares_org_with(p_user uuid) RETURNS boolean",
        """SELECT EXISTS (
             SELECT 1 FROM tenancy.memberships mine
             JOIN tenancy.memberships theirs ON theirs.org_id = mine.org_id AND theirs.user_id = p_user
             JOIN tenancy.organizations o ON o.id = mine.org_id AND o.status = 'active'
             WHERE mine.user_id = platform.current_user_id())""",
    ),
    (
        "tenancy.is_creator_without_members(p_org uuid) RETURNS boolean",
        """SELECT EXISTS (
             SELECT 1 FROM tenancy.organizations o
             WHERE o.id = p_org AND o.status = 'active' AND o.created_by = platform.current_user_id()
               AND NOT EXISTS (SELECT 1 FROM tenancy.memberships m WHERE m.org_id = p_org))""",
    ),
    (
        "tenancy.invitation_token_matches(p_org uuid, p_role text) RETURNS boolean",
        """SELECT EXISTS (
             SELECT 1 FROM tenancy.invitations i
             JOIN tenancy.organizations o ON o.id = i.org_id AND o.status = 'active'
             WHERE i.token_hash = decode(NULLIF(current_setting('app.invitation_token_hash', true), ''), 'hex')
               AND i.org_id = p_org AND i.role = p_role AND i.accepted_at IS NULL
               AND platform.current_user_id() IS NOT NULL)""",
    ),
    (
        """tenancy.find_invitation(p_token_hash bytea) RETURNS TABLE (
             invitation_id uuid, org_id uuid, org_name text, org_type text, email text, role text,
             expires_at timestamptz, accepted_at timestamptz)""",
        """SELECT i.id, i.org_id, o.name, o.type, i.email::text, i.role, i.expires_at, i.accepted_at
           FROM tenancy.invitations i
           JOIN tenancy.organizations o ON o.id = i.org_id AND o.status = 'active'
           WHERE i.token_hash = p_token_hash""",
    ),
)
_PLPGSQL_DEFINER = "LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp"
TRIGGER_FUNCTIONS: tuple[tuple[str, str], ...] = (
    (
        # Deferred constraint trigger: every active organisation keeps at least one owner (FR-PLT-03).
        "tenancy.last_owner_guard() RETURNS trigger",
        """
        BEGIN
          IF OLD.role <> 'owner' THEN RETURN NULL; END IF;
          IF NOT EXISTS (SELECT 1 FROM tenancy.organizations o
                         WHERE o.id = OLD.org_id AND o.status = 'active') THEN
            RETURN NULL;  -- organisation deleted or being deleted
          END IF;
          IF NOT EXISTS (SELECT 1 FROM tenancy.memberships m
                         WHERE m.org_id = OLD.org_id AND m.role = 'owner') THEN
            RAISE EXCEPTION 'last_owner: an organisation must keep at least one owner'
              USING ERRCODE = 'check_violation';
          END IF;
          RETURN NULL;
        END
        """,
    ),
    (
        # RLS WITH CHECK sees only the new row: a non-owner (the token holder) may only set accepted_at once.
        "tenancy.invitations_guard() RETURNS trigger",
        """
        BEGIN
          IF tenancy.is_owner(OLD.org_id) THEN RETURN NEW; END IF;
          IF NEW.id <> OLD.id OR NEW.org_id <> OLD.org_id OR NEW.email <> OLD.email
             OR NEW.role <> OLD.role OR NEW.token_hash <> OLD.token_hash
             OR NEW.expires_at <> OLD.expires_at
             OR NEW.invited_by IS DISTINCT FROM OLD.invited_by
             OR NEW.created_at <> OLD.created_at
             OR OLD.accepted_at IS NOT NULL OR NEW.accepted_at IS NULL THEN
            RAISE EXCEPTION 'invitation_guard: only accepted_at may be set, once'
              USING ERRCODE = 'check_violation';
          END IF;
          RETURN NEW;
        END
        """,
    ),
    (
        # Org types and lifecycle of access grants (data-model.md §4.2, FR-PART-01/02).
        "tenancy.access_grants_guard() RETURNS trigger",
        """
        DECLARE
          grantor_type text;
          grantee_type text;
          accepting_side uuid;
        BEGIN
          IF TG_OP = 'INSERT' THEN
            SELECT type INTO grantor_type FROM tenancy.organizations WHERE id = NEW.grantor_org_id;
            SELECT type INTO grantee_type FROM tenancy.organizations WHERE id = NEW.grantee_org_id;
            IF grantor_type IS DISTINCT FROM 'company'
               OR grantee_type IS NULL OR grantee_type NOT IN ('ca_firm', 'incubator') THEN
              RAISE EXCEPTION 'grant_org_types: only a company can share, only with a CA firm or incubator'
                USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.status <> 'pending' OR NEW.accepted_at IS NOT NULL OR NEW.revoked_at IS NOT NULL THEN
              RAISE EXCEPTION 'grant_transition: a grant starts as pending'
                USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
          END IF;

          IF NEW.id <> OLD.id OR NEW.grantor_org_id <> OLD.grantor_org_id
             OR NEW.grantee_org_id <> OLD.grantee_org_id OR NEW.scope <> OLD.scope
             OR NEW.initiated_by <> OLD.initiated_by
             OR NEW.created_by IS DISTINCT FROM OLD.created_by OR NEW.created_at <> OLD.created_at THEN
            RAISE EXCEPTION 'grant_immutable: orgs, scope and origin of a grant never change'
              USING ERRCODE = 'check_violation';
          END IF;
          accepting_side := CASE OLD.initiated_by WHEN 'grantor' THEN OLD.grantee_org_id
                                                  ELSE OLD.grantor_org_id END;
          IF OLD.status = 'pending' AND NEW.status = 'active' THEN
            IF NOT tenancy.is_owner(accepting_side) OR NEW.accepted_at IS NULL THEN
              RAISE EXCEPTION 'grant_transition: only an owner of the invited side can accept'
                USING ERRCODE = 'check_violation';
            END IF;
          ELSIF OLD.status IN ('pending', 'active') AND NEW.status = 'revoked' THEN
            IF NOT (tenancy.is_owner(OLD.grantor_org_id) OR tenancy.is_owner(OLD.grantee_org_id))
               OR NEW.revoked_at IS NULL THEN
              RAISE EXCEPTION 'grant_transition: only an owner of either side can revoke'
                USING ERRCODE = 'check_violation';
            END IF;
          ELSE
            RAISE EXCEPTION 'grant_transition: % -> % is not allowed', OLD.status, NEW.status
              USING ERRCODE = 'check_violation';
          END IF;
          RETURN NEW;
        END
        """,
    ),
)


def _name(signature: str) -> str:
    """`tenancy.f(p_org uuid, p_role text) RETURNS ...` -> `tenancy.f(uuid, text)` for ALTER/GRANT."""
    head = signature.split(")")[0]
    name, args = head.split("(", 1)
    types = [part.strip().split()[-1] for part in args.split(",") if part.strip()]
    return f"{name}({', '.join(types)})"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{CHECK_ROLE}') THEN
            RAISE EXCEPTION 'role {CHECK_ROLE} is missing: run infra/postgres/initdb/10-rls-check-role.sql '
                            '(make db-roles locally) before migrating (ADR-0013)';
          END IF;
        END $$
        """
    )

    op.execute(
        """
        CREATE TABLE tenancy.organizations (
            id uuid PRIMARY KEY,
            type text NOT NULL CHECK (type IN ('team', 'company', 'ca_firm', 'incubator', 'campus')),
            name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'deletion_pending')),
            deletion_requested_at timestamptz NULL,
            source_team_id uuid NULL REFERENCES tenancy.organizations (id) ON DELETE SET NULL,
            created_by uuid NOT NULL REFERENCES identity.users (id) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT organizations_deletion_requested_iff_pending
                CHECK ((status = 'deletion_pending') = (deletion_requested_at IS NOT NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX organizations_source_team_id_idx ON tenancy.organizations (source_team_id)"
    )
    op.execute("CREATE INDEX organizations_created_by_idx ON tenancy.organizations (created_by)")

    op.execute(
        """
        CREATE TABLE tenancy.memberships (
            org_id uuid NOT NULL REFERENCES tenancy.organizations (id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES identity.users (id) ON DELETE CASCADE,
            role text NOT NULL CHECK (role IN ('owner', 'member', 'viewer')),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (org_id, user_id)
        )
        """
    )
    op.execute("CREATE INDEX memberships_user_id_idx ON tenancy.memberships (user_id)")

    op.execute(
        """
        CREATE TABLE tenancy.invitations (
            id uuid PRIMARY KEY,
            org_id uuid NOT NULL REFERENCES tenancy.organizations (id) ON DELETE CASCADE,
            email citext NOT NULL,
            role text NOT NULL CHECK (role IN ('owner', 'member', 'viewer')),
            token_hash bytea NOT NULL UNIQUE,
            expires_at timestamptz NOT NULL,
            accepted_at timestamptz NULL,
            invited_by uuid NULL REFERENCES identity.users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX invitations_org_id_idx ON tenancy.invitations (org_id)")
    op.execute("CREATE INDEX invitations_invited_by_idx ON tenancy.invitations (invited_by)")
    op.execute(
        "CREATE UNIQUE INDEX invitations_one_open_per_email ON tenancy.invitations (org_id, email) "
        "WHERE accepted_at IS NULL"
    )

    op.execute(
        """
        CREATE TABLE tenancy.access_grants (
            id uuid PRIMARY KEY,
            grantor_org_id uuid NOT NULL REFERENCES tenancy.organizations (id) ON DELETE CASCADE,
            grantee_org_id uuid NOT NULL REFERENCES tenancy.organizations (id) ON DELETE CASCADE,
            scope text NOT NULL CHECK (scope IN ('read', 'manage')),
            status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'revoked')),
            initiated_by text NOT NULL CHECK (initiated_by IN ('grantor', 'grantee')),
            created_by uuid NULL REFERENCES identity.users (id) ON DELETE SET NULL,
            accepted_at timestamptz NULL,
            revoked_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT access_grants_distinct_orgs CHECK (grantor_org_id <> grantee_org_id),
            CONSTRAINT access_grants_revoked_at_iff_revoked
                CHECK ((status = 'revoked') = (revoked_at IS NOT NULL)),
            CONSTRAINT access_grants_active_was_accepted
                CHECK (status <> 'active' OR accepted_at IS NOT NULL)
        )
        """
    )
    op.execute("CREATE INDEX access_grants_grantor_idx ON tenancy.access_grants (grantor_org_id)")
    op.execute("CREATE INDEX access_grants_grantee_idx ON tenancy.access_grants (grantee_org_id)")
    op.execute("CREATE INDEX access_grants_created_by_idx ON tenancy.access_grants (created_by)")
    op.execute(
        "CREATE UNIQUE INDEX access_grants_one_open_pair ON tenancy.access_grants "
        "(grantor_org_id, grantee_org_id) WHERE status <> 'revoked'"
    )

    # --- check functions, owned by app_rls_check (ADR-0013) ---------------------------------------------
    op.execute(f"GRANT USAGE ON SCHEMA tenancy, platform TO {CHECK_ROLE}")
    op.execute(f"GRANT SELECT ON {', '.join(TABLES)} TO {CHECK_ROLE}")
    op.execute(
        f"GRANT EXECUTE ON FUNCTION platform.current_user_id(), platform.current_org_id() TO {CHECK_ROLE}"
    )
    for signature, body in CHECK_FUNCTIONS:
        op.execute(f"CREATE FUNCTION {signature} {_DEFINER} AS $fn$ {body} $fn$")
    for signature, body in TRIGGER_FUNCTIONS:
        op.execute(f"CREATE FUNCTION {signature} {_PLPGSQL_DEFINER} AS $fn$ {body} $fn$")
    # --- triggers (created while app_owner still owns, and may execute, the functions) ------------------------------------------------------------------------------------
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER memberships_last_owner
        AFTER UPDATE OR DELETE ON tenancy.memberships
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION tenancy.last_owner_guard()
        """
    )
    op.execute(
        "CREATE TRIGGER invitations_guard BEFORE UPDATE ON tenancy.invitations "
        "FOR EACH ROW EXECUTE FUNCTION tenancy.invitations_guard()"
    )
    op.execute(
        "CREATE TRIGGER access_grants_guard BEFORE INSERT OR UPDATE ON tenancy.access_grants "
        "FOR EACH ROW EXECUTE FUNCTION tenancy.access_grants_guard()"
    )

    # Privileges first, while app_owner still owns the functions (the ACL moves with ownership).
    for signature, _ in CHECK_FUNCTIONS + TRIGGER_FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {_name(signature)} FROM PUBLIC")
    for signature, _ in CHECK_FUNCTIONS:
        op.execute(f"GRANT EXECUTE ON FUNCTION {_name(signature)} TO {SERVICE_ROLES}")
    # ALTER ... OWNER needs CREATE on the schema for the new owner; granted only for this step.
    op.execute(f"GRANT CREATE ON SCHEMA tenancy TO {CHECK_ROLE}")
    for signature, _ in CHECK_FUNCTIONS + TRIGGER_FUNCTIONS:
        op.execute(f"ALTER FUNCTION {_name(signature)} OWNER TO {CHECK_ROLE}")
    op.execute(f"REVOKE CREATE ON SCHEMA tenancy FROM {CHECK_ROLE}")
    # identity.co_member_profiles (owned by app_owner, below) calls this check. Granted by the new owner:
    # ALTER OWNER rewrites the old owner's ACL entries, so a grant to app_owner made before it is lost.
    op.execute(f"SET LOCAL ROLE {CHECK_ROLE}")
    op.execute("GRANT EXECUTE ON FUNCTION tenancy.shares_org_with(uuid) TO app_owner")
    op.execute("RESET ROLE")

    # Names and emails of people the caller shares an organisation with (member lists). Owned by app_owner,
    # like the other identity lookups: identity.users is RLS-enabled but not forced (migration 0002).
    op.execute(
        """
        CREATE FUNCTION identity.co_member_profiles(p_user_ids uuid[])
        RETURNS TABLE (user_id uuid, email text, display_name text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $fn$
          SELECT u.id, u.email::text, u.display_name FROM identity.users u
          WHERE u.id = ANY (p_user_ids)
            AND (u.id = platform.current_user_id() OR tenancy.shares_org_with(u.id))
        $fn$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION identity.co_member_profiles(uuid[]) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION identity.co_member_profiles(uuid[]) TO {SERVICE_ROLES}")

    # --- RLS -----------------------------------------------------------------------------------------
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    me = "platform.current_user_id()"
    policies = [
        # organizations: members and active grantees read; the creator inserts; owners update.
        "CREATE POLICY org_read ON tenancy.organizations FOR SELECT USING (tenancy.can_read(id))",
        f"CREATE POLICY org_insert ON tenancy.organizations FOR INSERT "
        f"WITH CHECK (created_by = {me} AND status = 'active')",
        "CREATE POLICY org_update ON tenancy.organizations FOR UPDATE "
        "USING (tenancy.is_owner(id)) WITH CHECK (tenancy.is_owner(id))",
        # memberships: roster for members; owners administer; bootstrap, accept and leave are narrow.
        "CREATE POLICY members_read ON tenancy.memberships FOR SELECT USING (tenancy.is_member(org_id))",
        "CREATE POLICY members_insert ON tenancy.memberships FOR INSERT "
        "WITH CHECK (tenancy.is_owner(org_id))",
        f"CREATE POLICY members_bootstrap ON tenancy.memberships FOR INSERT "
        f"WITH CHECK (user_id = {me} AND role = 'owner' AND tenancy.is_creator_without_members(org_id))",
        f"CREATE POLICY members_accept ON tenancy.memberships FOR INSERT "
        f"WITH CHECK (user_id = {me} AND tenancy.invitation_token_matches(org_id, role))",
        "CREATE POLICY members_update ON tenancy.memberships FOR UPDATE "
        "USING (tenancy.is_owner(org_id)) WITH CHECK (tenancy.is_owner(org_id))",
        "CREATE POLICY members_delete ON tenancy.memberships FOR DELETE USING (tenancy.is_owner(org_id))",
        f"CREATE POLICY members_leave ON tenancy.memberships FOR DELETE USING (user_id = {me})",
        # invitations: owners only, plus the token holder setting accepted_at (column rule: trigger).
        "CREATE POLICY invitations_owner ON tenancy.invitations FOR ALL "
        "USING (tenancy.is_owner(org_id)) WITH CHECK (tenancy.is_owner(org_id))",
        # An UPDATE with a WHERE clause must also pass SELECT policies, so the token holder sees that row.
        "CREATE POLICY invitations_token_read ON tenancy.invitations FOR SELECT "
        "USING (tenancy.invitation_token_matches(org_id, role))",
        "CREATE POLICY invitations_accept ON tenancy.invitations FOR UPDATE "
        "USING (tenancy.invitation_token_matches(org_id, role)) "
        "WITH CHECK (tenancy.invitation_token_matches(org_id, role))",
        # access grants: members of either side see them; owners create/accept/revoke (rules: trigger).
        "CREATE POLICY grants_read ON tenancy.access_grants FOR SELECT "
        "USING (tenancy.is_member(grantor_org_id) OR tenancy.is_member(grantee_org_id))",
        "CREATE POLICY grants_insert ON tenancy.access_grants FOR INSERT WITH CHECK ("
        "status = 'pending' AND ("
        "(initiated_by = 'grantor' AND tenancy.is_owner(grantor_org_id)) OR "
        "(initiated_by = 'grantee' AND tenancy.is_owner(grantee_org_id))))",
        "CREATE POLICY grants_update ON tenancy.access_grants FOR UPDATE "
        "USING (tenancy.is_owner(grantor_org_id) OR tenancy.is_owner(grantee_org_id)) "
        "WITH CHECK (tenancy.is_owner(grantor_org_id) OR tenancy.is_owner(grantee_org_id))",
    ]
    for policy in policies:
        op.execute(policy)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS identity.co_member_profiles(uuid[])")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    # app_owner holds app_rls_check WITH INHERIT FALSE, SET TRUE: drop its functions as that role.
    op.execute(f"GRANT CREATE ON SCHEMA tenancy TO {CHECK_ROLE}")
    op.execute(f"SET LOCAL ROLE {CHECK_ROLE}")
    for signature, _ in reversed(CHECK_FUNCTIONS + TRIGGER_FUNCTIONS):
        op.execute(f"DROP FUNCTION IF EXISTS {_name(signature)}")
    op.execute("RESET ROLE")
    op.execute(f"REVOKE CREATE ON SCHEMA tenancy FROM {CHECK_ROLE}")
    op.execute(
        f"REVOKE EXECUTE ON FUNCTION platform.current_user_id(), platform.current_org_id() "
        f"FROM {CHECK_ROLE}"
    )
    op.execute(f"REVOKE USAGE ON SCHEMA tenancy, platform FROM {CHECK_ROLE}")
