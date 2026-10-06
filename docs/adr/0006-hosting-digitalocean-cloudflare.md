# ADR-0006: One-box hosting on a single DigitalOcean server (Bangalore) behind Cloudflare; Azure as optional bonus

- **Status:** Superseded in part by [ADR-0012](0012-hosting-after-student-pack-change.md) (Proposed, 2026-10-05): the DigitalOcean Student Pack credit this ADR relies on ended on 1 Aug 2026. Cloudflare edge and Pages decisions still stand.
- **Date:** 2026-09-28 (revised same day: one-box, verified-only)
- **Decision makers:** @harshith769
- **Confidence:** To be set by owner (re-check after spike S5)

## Decision

**Run the entire MVP backend — Caddy, API, worker, PostgreSQL + pgvector, backup agent — with Docker Compose on one ~2 GB DigitalOcean server in Bangalore, paid by the GitHub Student Pack credit; put Cloudflare (DNS, CDN, firewall, TLS) in front; host both frontends on Cloudflare Pages.** Every item on this path is verified; the same Compose file runs on any Linux server, so hosting is interchangeable.

## Context

Owner constraints: ₹0 for the MVP, one operator, production-grade engineering, and a "verified-only" rule for the critical path. The GitHub Student Developer Pack offers $200 DigitalOcean credit for 1 year ([GitHub Education](https://education.github.com/pack)). At about $12/month for one server, the credit covers roughly a full year; the separate-managed-database design (~$27–39/month) would last only 5–7 months.

## Candidates

### A. One DigitalOcean server running everything (chosen)
- Verified credit, India region, predictable price shown at checkout.
- Single point of failure; owner patches OS and containers.

### B. DigitalOcean server + managed Postgres
- Less operations work. Consumes credit about twice as fast → stage 2.

### C. Azure for Students VMs + free managed Postgres
- Potentially ₹0 for 12 months with managed backups.
- Eligibility for Indian students' 12-month services and the free VM sizes are **unverified** → optional bonus only (staging or month-12 landing spot), checked on the portal's Free services page.

### D. Oracle Cloud Always Free
- Rejected: the Arm allowance was halved without announcement in June 2026 ([InfoQ](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/)), and idle instances may be reclaimed ([Oracle docs](https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm)).

## Evaluation

Server price: shown at checkout — confirm before creating. RAM headroom on 2 GB: not measured → spike S5 and Phase 1 monitoring.

## Consequences

- Claim the DigitalOcean credit only when the pilot is deployed (Phase 1, ~week 8); all earlier work runs locally.
- Scripted rebuild: a new server can be provisioned and restored from backups in about an hour (target, measured in drills).
- Origin accepts traffic only from Cloudflare; SSH key-only; unattended security upgrades; monthly container image updates.
- No permanent staging server in MVP; CI uses ephemeral containers. If the Azure bonus is confirmed, it hosts staging.

## Re-evaluation Triggers

- Sustained memory pressure → resize to 4 GB (~$24/month; credit then lasts ~8 months).
- Credit expiry (~month 11) → move to Azure bonus if confirmed, pay for the server (~₹1,000–2,100/month), or go to stage 2.
- First paying customer → stage 2 (managed Postgres), per [architecture.md §7.2](../architecture.md#72-growth-path).
