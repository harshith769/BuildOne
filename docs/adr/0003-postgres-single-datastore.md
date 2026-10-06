# ADR-0003: PostgreSQL as the single datastore — self-hosted on the one-box for MVP, managed from stage 2

- **Status:** Accepted
- **Date:** 2026-09-28 (revised same day: self-hosted for MVP)
- **Decision makers:** @harshith769
- **Confidence:** To be set by owner (re-check after spike S5)

## Decision

**Use one PostgreSQL database for relational data, vector search (`pgvector`), full-text search, the job queue (ADR-0004), and tenant isolation (Row-Level Security). In the MVP it runs as a container (official `pgvector/pgvector` image) on the one-box server (ADR-0006), with continuous backup to object storage; at stage 2 it moves to managed PostgreSQL by dump/restore and a connection-string change.** This keeps the MVP at ₹0 without depending on any unverified free-database offer, and the move to managed Postgres requires no code change.

## Context

The product needs strict relational constraints, hybrid retrieval over thousands of documents, background jobs, and hard tenant isolation, on a ₹0 MVP budget, operated by one person. The owner chose a "verified-only" plan: nothing on the critical path may depend on an unverified free-tier offer.

## Candidates

### A. Self-hosted Postgres + pgvector container on the one-box, continuous WAL backup to R2 (chosen for MVP)
- ₹0 beyond the server; standard Postgres, fully portable.
- Owner is responsible for patching and backups → mitigated by `wal-g` continuous archiving, nightly dumps, monthly restore drills ([nfr.md §2](../nfr.md#2-availability-and-reliability)).
- Single point of failure together with the server.

### B. DigitalOcean managed Postgres
- Backups and patching handled by the provider; about $15.15/month for the smallest single node, pgvector supported ([DO pricing guide](https://github.com/baafxc4/digitalocean-postgresql-pricing)).
- Would consume the student credit roughly twice as fast; **planned for stage 2**.

### C. Azure for Students managed Postgres (free 12 months)
- Microsoft lists a free B1MS flexible server with 32 GB storage for 12 months ([Azure for Students](https://azure.microsoft.com/en-in/free/students)); pgvector is supported after allowlisting `vector` ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/postgresql/extensions/how-to-use-pgvector)).
- Eligibility of Indian student accounts for the 12-month services is **unverified** → used only as an optional bonus (staging or month-12 landing spot).

### D. Neon free tier
- Free compute is suspended when the monthly CU-hour allowance is exhausted ([Neon plans](https://neon.com/docs/introduction/plans)); an always-connected queue worker would keep the database awake and exhaust it. Suitable for development branches only.

## Evaluation

Retrieval quality/latency not yet measured → spike S2. Backup/restore time not yet measured → spike S5.

## Consequences

- Postgres port is never exposed publicly; only containers on the internal Docker network can reach it.
- Only portable extensions are allowed (`vector`, `pg_trgm`) — see [ADR-0011](0011-portability-rules.md).
- CI runs integration tests against an ephemeral Postgres + pgvector container with the same image tag as production.

## Re-evaluation Triggers (move to stage 2 — managed Postgres)

- First paying customer, or
- Database memory pressure on the one-box (sustained swap use), or
- Owner time on database operations exceeds ~2 hours/month.
