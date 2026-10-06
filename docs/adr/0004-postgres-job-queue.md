# ADR-0004: Postgres-backed job queue (Procrastinate)

- **Status:** Accepted (architecture freeze requested by owner, 2026-09-28)
- **Date:** 2026-09-28
- **Decision makers:** @harshith769
- **Confidence:** To be set by owner on acceptance (proposer's view: Medium)

## Decision

**Run background jobs and scheduled tasks through Procrastinate, a Postgres-backed Python task queue, instead of adding Redis/RabbitMQ.** Jobs (re-evaluation, reminders, ingestion, explanation generation) are low-volume and must be transactional with the data they act on.

## Context

Needed: reliable background jobs, periodic schedules (daily reminder scans, nightly backups), retries, and the ability to enqueue a job in the same transaction as a data change (outbox behaviour).

## Candidates

### A. Procrastinate (Postgres)
- Uses Postgres locking (`SKIP LOCKED`) and `LISTEN/NOTIFY`; supports async and periodic tasks; no new infrastructure.
- Smaller community than Celery.

### B. Celery + Redis
- Most widely used Python queue; mature tooling.
- Adds Redis (cost, backups, monitoring) and loses transactional enqueue.

### C. arq / Dramatiq + Redis
- Lighter than Celery; same Redis cost and non-transactional enqueue.

## Evaluation

Not measured. Expected load (thousands of jobs/day) is far below Postgres queue limits.

## Consequences

- Job handlers must be idempotent (NFR-REL-04); reminders use a unique key per (obligation, type, due date).
- Queue lag and failure counts are exported as metrics.

## Re-evaluation Triggers

- Sustained queue lag or DB load attributable to the queue.
- Procrastinate maintenance stalls (no release in 12 months).
