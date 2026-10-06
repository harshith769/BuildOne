# ADR-0011: Portability rules — every layer must be movable by configuration, not rewrite

- **Status:** Accepted
- **Date:** 2026-09-28
- **Decision makers:** @harshith769
- **Confidence:** To be set by owner

## Decision

**BuildOne uses only open standards at every infrastructure boundary — standard PostgreSQL, Docker containers, S3-protocol object storage, OIDC identity, and one AI gateway — and bans provider-specific services in application code.** This guarantees that growth from the ₹0 one-box MVP to a scaled SaaS is a sequence of configuration and deployment changes, never a rewrite.

## Context

The MVP runs on free tiers and credits that can change without notice; for example, Oracle halved its Always Free Arm allowance in June 2026 without announcement ([InfoQ](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/)). The owner requires that upgrades never force a total technology replacement.

## The rules

**Allowed at boundaries**
| Boundary | Standard | Movable to |
|---|---|---|
| Database | PostgreSQL wire protocol; extensions limited to `vector` and `pg_trgm` | Any managed or self-hosted Postgres |
| Compute | OCI/Docker images, configuration via environment variables | Any VM, container platform, or Kubernetes |
| Files | S3 API through the internal storage interface | R2, S3, DigitalOcean Spaces, MinIO |
| Identity | OIDC through the `identity` module adapter; internal user IDs | Any OIDC provider or direct Google sign-in |
| AI | `ai` gateway module only | Any provider by configuration |
| Frontend | Static build output | Any static host / CDN |
| Email | SMTP or provider adapter in `notifications` | Any provider |

**Banned in application code**
- Provider-proprietary databases or data APIs (Firestore, DynamoDB, Cosmos DB, Supabase client-side data API)
- Platform-only runtimes or triggers (Azure Functions, Cloudflare Workers backend code, Vercel edge functions)
- Provider SDKs for storage or queues outside their adapter (e.g., Azure Blob SDK, Service Bus)
- Provider-specific Postgres extensions (e.g., `azure_ai`, `pg_diskann`)
- Files written to the server's local disk as a system of record
- AI provider SDK imports outside `app/modules/ai/`
- Identity provider as owner of the user table

## Enforcement

- `import-linter` contracts: provider SDKs importable only from their adapter module.
- CI check: allowed Postgres extension list in migrations.
- CI runs the full test suite against a plain Postgres container, proving no managed-only features are used.

## Consequences

- Slightly more adapter code in exchange for freedom to move.
- Growth stages in [architecture.md §7.2](../architecture.md#72-growth-path) change configuration and deployment only.

## Re-evaluation Triggers

- A provider-specific feature offers an irreplaceable, measured benefit — requires a new ADR with an exit plan.
