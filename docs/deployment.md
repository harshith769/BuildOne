# BuildOne — Deployment, Backups, and Operations

> **Status:** v1.0 (frozen for MVP build; validated by spike S5) · 2026-09-28 · Owner: @harshith769
> Decisions: [ADR-0006](adr/0006-hosting-digitalocean-cloudflare.md), [ADR-0003](adr/0003-postgres-single-datastore.md). Topology: [architecture.md §7](architecture.md#7-deployment-topology).

**What this document answers**
- Which containers run where, with which configuration
- How code reaches production and how migrations run
- How backups work and how to restore (commands)
- What is monitored and how alerts arrive at ₹0

---

## 1. Environments

| Env | Where | Database | Purpose |
|---|---|---|---|
| `local` | Developer machine, `infra/compose/compose.yml` + `compose.dev.yml` | Local Postgres container | Development; identical topology to production |
| `ci` | GitHub Actions | Service container `pgvector/pgvector:0.8.7-pg18-trixie` | Tests, evals (non-AI) |
| `production` | Proposed (ADR-0012): Azure VM, Central India, Docker Compose. Fallback: one DigitalOcean server (Bangalore) | Proposed: Azure Flexible Server B1MS (managed). Fallback: Postgres container on the same server | Pilot |

## 2. Containers (`infra/compose/compose.yml`)

| Service | Image | Notes |
|---|---|---|
| `caddy` | `caddy:2` | TLS via Cloudflare origin certificate; only Cloudflare IP ranges allowed |
| `api` | `ghcr.io/<owner>/buildone-backend:<sha>` | `uvicorn app.main:app --workers 2` |
| `worker` | same image | `python -m app.worker` (Procrastinate worker + schedules) |
| `migrate` | same image | One-shot: `alembic upgrade head` as `app_owner`, then `python -m app.modules.rules.publish` |
| `postgres` | `infra/postgres/Dockerfile` (pgvector/pgvector:0.8.7-pg18-trixie + wal-g v3.0.9) | Internal network only; volume `pgdata` |

Memory limits (tune in S5): postgres 700 MB, api 450 MB, worker 550 MB (includes embedding model), caddy 50 MB; 2 GB swap file on the host.

## 3. Configuration (environment variables)

All configuration via environment (`app/platform/config.py`, Pydantic Settings). `.env.example` lists every variable; production `.env` lives only on the server (mode 600).

## 4. CI/CD

`.github/workflows/ci.yml` on every push/PR: lint → types → import contracts → unit + integration tests (Postgres service) → rule scenarios → retrieval eval (when relevant) → frontend checks → secret scan → dependency audit.

`.github/workflows/deploy.yml` (added in milestone M4) on push to `main` after CI passes:
1. Build `linux/amd64` image, tag with commit SHA, push to GHCR.
2. SSH as `deploy` user → `docker compose pull` → `docker compose run --rm migrate` → `docker compose up -d api worker` → poll `/readyz` for 60 s → on failure, re-deploy previous SHA and alert.

Migrations must be backward compatible with the previous image (expand → migrate → contract), because the old API briefly runs against the new schema.

## 5. Backups (Frozen targets: NFR-REL-01/02/03)

| Mechanism | Frequency | Retention | Location |
|---|---|---|---|
| WAL archiving (`archive_command = 'wal-g wal-push %p'`, `archive_timeout = 60`) | Continuous | Covers retained base backups | R2 `buildone-backups/wal-g/` |
| Base backup (`wal-g backup-push`) | Nightly 02:00 IST | 7 (`wal-g delete retain FULL 7 --confirm`) | same |
| Logical dump (`pg_dump -Fc`) | Nightly 02:30 IST | 30 days (R2 lifecycle rule) | R2 `buildone-backups/dumps/` |

### Restore (rehearsed monthly; commands validated in S5)
1. Provision new server with `infra/scripts/provision.sh` (Docker, firewall, users, swap).
2. Copy `.env` from password manager; start `postgres` container with an empty volume in restore mode.
3. `wal-g backup-fetch $PGDATA LATEST`; create `recovery.signal`; set `restore_command = 'wal-g wal-fetch %f %p'`; start Postgres and wait for recovery to finish.
4. `docker compose up -d`; verify `/readyz`; switch Cloudflare DNS; record timings in `docs/runbooks/restore-log.md`.

## 6. Observability at ₹0

| Signal | Tool | Alert path |
|---|---|---|
| Errors + traces | Sentry (API, worker, SPA) | Sentry email |
| Uptime of `/healthz` + app | Free external checker, 1-min interval | Email |
| Ops check job (every 15 min) | Worker computes: queue lag, failed jobs (1 h), last WAL push age, last base backup age, AI budget %, disk %, DB size | Emits Sentry events on thresholds |
| Host RAM/CPU/disk | DigitalOcean monitoring agent (verify free alerts at setup) | Email |
| Logs | Structured JSON to stdout → Docker log rotation (100 MB × 5) | Inspected on the server; no personal data in logs |

Log fields: `ts`, `level`, `event`, `request_id`, `user_id`, `org_id`, `route`, `status`, `duration_ms`, `job`, `ai_call_id`.

## 7. Runbooks (written in M4 and M13, under `docs/runbooks/`)

`deploy-and-rollback.md` · `restore.md` + `restore-log.md` · `bad-rule-revert.md` · `ai-provider-outage.md` · `server-hardening-and-patching.md` · `credit-expiry-migration.md` (free-period end, [ADR-0012](adr/0012-hosting-after-student-pack-change.md) re-evaluation triggers) · `stage-2-managed-postgres.md`.
