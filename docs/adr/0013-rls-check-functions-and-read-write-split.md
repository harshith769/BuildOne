# ADR-0013: RLS check functions owned by a dedicated role; read and write policies split

- **Status:** Accepted (owner, 2026-10-06, M3 plan approval)
- **Date:** 2026-10-06
- **Decision makers:** @harshith769
- **Changes:** data-model.md §2 (one new role) and §3 (the standard policy). Everything else in §1–§3 stays frozen.

## Decision

1. **The tenancy check functions are owned by `app_rls_check`, a `NOLOGIN BYPASSRLS` role that owns nothing else.** Every check is `SECURITY DEFINER`, `STABLE`, read-only (SELECT only), uses fully qualified names, and has `SET search_path = pg_catalog, pg_temp`. Each answers a question about the caller (`platform.current_user_id()`) or about a token hash the caller proves it holds. EXECUTE goes only to `app_api` and `app_worker`. `app_owner` is granted the role `WITH INHERIT FALSE, SET TRUE`, only so that migrations can assign ownership.
2. **The standard policy splits into a read policy and write policies.** Company-data tables (facts, obligations and the rest, from M8 on) get:
   - `tenant_read FOR SELECT USING (org_id = platform.current_org_id() AND tenancy.can_read(org_id))`
   - `tenant_insert` / `tenant_update` / `tenant_delete` using `tenancy.can_edit(org_id)` in place of `can_read`

   `can_read` is "member of any role, or a member of an org holding an **active** access grant from this org". `can_edit` is "member with role owner or member". Read grants therefore never write: the write check never consults grants, whatever their scope (D-29). The SQL lives in one helper, `backend/migrations/rls.py::company_data_policies()`, and a catalog test fails if any write policy references `can_read`.

## Context

The M2 carry-forward note found the problem. Under `FORCE ROW LEVEL SECURITY` the table owner is subject to RLS, and `app_owner` has no BYPASSRLS. A `SECURITY DEFINER` function owned by `app_owner` (data-model.md §3 as written) therefore sees only what the memberships policy shows it. Since that policy itself calls `is_member`, the result is nothing at all, or recursion. Access grants (data-model.md §4.2) separately require that a read grant can't satisfy write policies.

## Options

### A. Dedicated BYPASSRLS owner for the check functions (chosen)
- One simple pattern for every table: a policy calls a check function. There is no recursion analysis, because the functions don't pass through policies.
- The bypass is confined to a handful of read-only functions with pinned search paths. The role can't log in, owns no tables, and isn't granted to any service role (catalog test).

### B. Policies based on the user's own memberships (rejected)
`memberships USING (user_id = current_user_id())` lets a definer owned by `app_owner` see the caller's own rows. This was rejected for three reasons:
- `is_member` checks `organizations.status`, and `organizations`' policy calls `is_member`, which is a cycle.
- Letting members see their org's roster means a `memberships` policy that reads `memberships`, which Postgres rejects as infinite recursion.
- The last-owner trigger and the grant checks each need their own workaround. Every future policy would need a recursion review.

## Consequences

- `infra/postgres/roles.sql` (idempotent, plain SQL) creates the role. initdb, `make db-roles` (run by `make dev`) and the test harness all apply it. Migration `0003_tenancy` stops with a clear error if the role is missing.
- Org-admin tables (`memberships`, `invitations`, `access_grants`, `organizations`) use owner-level write checks (`is_owner`), plus three narrow policies: bootstrap of the creator's owner membership, invitation acceptance by token hash, and leaving. Column-level rules that RLS can't express (`WITH CHECK` sees only the new row) are enforced by triggers.
- Tables keyed to a user (`identity.*`, `platform.idempotency_keys`, notification read state, preferences, calendar feeds) use `user_id = platform.current_user_id()` policies, never the org write check.
- `audit.events` accepts inserts from any actor who can read the org, including viewers and active grantees. System rows (NULL actor) are allowed only for `app_worker`. Nobody can UPDATE or DELETE.

## Risk: managed Postgres

Creating a role with `BYPASSRLS` needs a superuser, or on PostgreSQL 16+ a `CREATEROLE` admin that itself has `BYPASSRLS`. Whether the chosen host's admin can do this is **not verified**. Spike S5 checks it (added to [ADR-0012](0012-hosting-after-student-pack-change.md) item 2).

**Fallback if S5 can't create `app_rls_check` with BYPASSRLS:** the four tenancy tables (`organizations`, `memberships`, `invitations`, `access_grants`) get RLS **enabled but not forced**, and the check functions are owned by `app_owner`. This is the same pattern as M2's identity tables. Services never connect as `app_owner`, so policies still apply to them. Option B stays rejected.

## Re-evaluation triggers

- S5 shows the host can't create a BYPASSRLS role → apply the fallback above.
- A check function needs to write, or to return other users' rows → stop and write a new ADR.
