# ADR-0010: Cloudflare R2 for object storage

- **Status:** Accepted (architecture freeze requested by owner, 2026-09-28)
- **Date:** 2026-09-28
- **Decision makers:** @harshith769
- **Confidence:** To be set by owner on acceptance (proposer's view: Medium)

## Decision

**Store uploaded documents, evidence files, source documents, and backup dumps in private Cloudflare R2 buckets, accessed via the S3 API and short-lived signed URLs.** R2 has a 10 GB free tier with zero egress fees ([Filebase R2 guide](https://filebase.com/blog/cloudflare-r2-pricing-costs-savings-and-alternatives-in-2026/)), which fits the budget and the download-heavy evidence/DD-pack use case.

## Context

Files must never live on the application server (stateless servers, backups). Needed: private buckets, signed URLs (≤ 15 min, NFR-SEC-07), lifecycle rules, and an S3-compatible API so the provider can be swapped.

## Candidates

### A. Cloudflare R2
- Free tier and zero egress; S3-compatible; same vendor as the edge layer.
- Data location is not pinned to India by default — record this in the privacy notice (NFR-PRV-06).

### B. DigitalOcean Spaces (Bangalore)
- India region; about $5/month for 250 GB ([AIPriceRadar](https://aipriceradar.com/tool/digitalocean-pricing)).
- Paid from day one; egress beyond allowance billed.

## Evaluation

Not measured.

## Consequences

- Storage accessed only through an internal storage interface (S3 API), so switching to Spaces is a configuration change.
- Continuous Postgres WAL archives (`wal-g`) and nightly dumps are written to a separate backup bucket with restricted, write-only credentials from the server ([ADR-0003](0003-postgres-single-datastore.md)).
- Backup volume must stay within the free 10 GB; retention tuned to 30 days and monitored.

## Re-evaluation Triggers

- Customer or legal requirement for India-pinned storage → switch to DigitalOcean Spaces (Bangalore).
- Storage exceeds free tier materially.
