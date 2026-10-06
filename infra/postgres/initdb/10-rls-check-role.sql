-- Owner of the tenancy RLS check functions (ADR-0013). Idempotent: run by initdb on an empty data directory,
-- by `make db-roles` on existing local volumes, and by the admin role on managed Postgres (spike S5 checks
-- that the admin can create a BYPASSRLS role).
-- NOLOGIN, owns only SECURITY DEFINER read-only check functions, never granted to a service role.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_rls_check') THEN
    CREATE ROLE app_rls_check NOLOGIN BYPASSRLS;
  END IF;
END
$$;
ALTER ROLE app_rls_check NOLOGIN BYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
-- Lets migrations (as app_owner) assign function ownership, without app_owner inheriting the bypass.
GRANT app_rls_check TO app_owner WITH INHERIT FALSE, SET TRUE;
