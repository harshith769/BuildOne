#!/usr/bin/env bash
# Runs once on an empty data directory as the superuser. Creates roles and extensions.
# Schemas, tables, functions, grants and RLS are created by Alembic (as app_owner).
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username postgres --dbname buildone <<SQL
CREATE ROLE app_owner    LOGIN PASSWORD '${APP_OWNER_PASSWORD}';
CREATE ROLE app_api      LOGIN PASSWORD '${APP_API_PASSWORD}'      NOBYPASSRLS;
CREATE ROLE app_worker   LOGIN PASSWORD '${APP_WORKER_PASSWORD}'   NOBYPASSRLS;
CREATE ROLE app_ingest   LOGIN PASSWORD '${APP_INGEST_PASSWORD}'   NOBYPASSRLS;
CREATE ROLE app_readonly LOGIN PASSWORD '${APP_READONLY_PASSWORD}' NOBYPASSRLS;
ALTER DATABASE buildone OWNER TO app_owner;
GRANT CREATE ON DATABASE buildone TO app_owner;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS citext;
SQL
