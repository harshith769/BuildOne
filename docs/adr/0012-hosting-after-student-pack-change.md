# ADR-0012: Host the pilot on Azure for Students (Central India); paid DigitalOcean as fallback

- **Status:** Proposed (decided by spike S5, confirmed at M4)
- **Date:** 2026-10-05
- **Decision makers:** @harshith769
- **Supersedes in part:** [ADR-0006](0006-hosting-digitalocean-cloudflare.md) — only the "paid by the Student Pack credit" assumption. Cloudflare DNS, CDN, firewall, TLS and Pages still stand.

## Context

ADR-0006 put the whole MVP backend on one ~2 GB DigitalOcean server paid by the GitHub Student Pack credit. That credit is gone: DigitalOcean left the Pack, redemption closed on 31 Jul 2026 and **all Pack credits, including ones already redeemed, expired on 1 Aug 2026** ([GitHub Community discussion](https://github.com/orgs/community/discussions/201240)). Constraints are unchanged: ₹0 for the MVP, one operator, verified-only critical path, India region preferred, portable at every boundary ([ADR-0011](0011-portability-rules.md)).

## Candidates (checked 2026-10-05)

| Option | Monthly cost | RAM | Notes |
|---|---|---|---|
| **A. Azure for Students** (Central India) | ₹0 for 12 months | VM: B2ats v2, 2 vCPU, 1 GiB. Database: Flexible Server B1MS, 2 GiB, 32 GB storage | $100 credit for 12 months, no credit card; 750 h/month each of B1s, B2pts v2 and B2ats v2 VMs and of Flexible Server B1MS for 12 months, new customers only ([Azure for Students](https://azure.microsoft.com/en-in/free/students)). PostgreSQL 18 is GA on Flexible Server ([Microsoft](https://techcommunity.microsoft.com/blog/adforpostgresql/postgresql-18-now-ga-on-azure-postgres-flexible-server/4469802)); pgvector is an allowlisted extension |
| **B. DigitalOcean Bangalore, paid** | List price, confirm at checkout | 2 GB | Same one-box design as ADR-0006, no credit |
| C. Hetzner | Higher after 15 Jun 2026 increase | — | No India region; Singapore prices rose up to 96% ([Hetzner](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)) |
| D. Oracle Always Free | — | — | Still rejected (allowance cut June 2026, idle reclaim) |

## Proposed decision

**A, with B as the fallback.** Run API + worker with Docker Compose on the Azure VM; run PostgreSQL 18 on Azure Flexible Server B1MS; keep files and the nightly `pg_dump` in Cloudflare R2 so leaving Azure is a dump/restore and a connection-string change.

What changes against ADR-0006:

- The database is **managed** in the pilot, which removes wal-g from the critical path (the provider's point-in-time restore replaces it). The self-hosted Postgres image with pinned wal-g stays in `infra/postgres/` for option B and for local development.
- No superuser on managed Postgres: roles, grants and extensions must be created by the admin role from plain SQL, and every extension used (`vector`, `pg_trgm`, `citext`) must be on the allowlist. Spike S5 verifies this.
- The VM has only **1 GiB RAM**: one Uvicorn worker, a lean job worker, and no embedding model in a long-running process. If S2's embedding model doesn't fit, ingestion runs as a CLI on the laptop and loads results over the network.
- **Do not sign up before M4.** The 12 months of free services start at signup.

## What S5 must show before this is Accepted

1. The API + worker containers run within ~900 MiB total with realistic limits.
2. The `initdb` SQL runs on a managed-Postgres-like setup without superuser rights (locally: a non-superuser admin role).
3. Nightly `pg_dump` to R2 and restore into a fresh Postgres 18 both work and are timed.
4. Eligibility: the Azure portal's *Free services* page lists the VM sizes and Flexible Server B1MS for Harshith's student account.

If any item fails, choose B and record the measured monthly cost here.

## Re-evaluation triggers

- 12-month free period ends → renew student benefits if still enrolled, move to B, or go to stage 2 (paid managed Postgres).
- First paying customer → stage 2 per [architecture.md §7.2](../architecture.md).
- Customer or legal requirement for India-only storage → keep Central India and move files from R2 to an India-region bucket.
