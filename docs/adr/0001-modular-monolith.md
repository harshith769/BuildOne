# ADR-0001: Modular monolith architecture

- **Status:** Accepted (architecture freeze requested by owner, 2026-09-28)
- **Date:** 2026-09-28
- **Decision makers:** @harshith769
- **Confidence:** To be set by owner on acceptance (proposer's view: High)

## Decision

**Build BuildOne as a modular monolith: one codebase, one API process type, one worker process type, one database, with strictly enforced module boundaries.** A solo developer cannot absorb the operational cost of multiple services, and the expected scale ([nfr.md §4](../nfr.md#4-scalability)) fits comfortably in one deployable.

## Context

BuildOne has distinct domains (identity, facts, rules, obligations, knowledge/retrieval, AI, notifications, Launchpad). The team is one person. The MVP must be production-grade (tenant isolation, observability, recoverability) at ₹0 out of pocket for the MVP (one-box on student credit; see [tech-stack.md §4](../tech-stack.md#4-budget)).

## Candidates

### A. Modular monolith
- One deploy, one set of logs, in-process calls, single transaction boundary.
- Risk: boundaries erode over time → mitigated by `import-linter` contracts in CI (NFR-MNT-02).

### B. Microservices (e.g., separate rules, retrieval, and API services)
- Independent scaling and deploys.
- Cost: network calls, distributed transactions, multiple deploy pipelines, more hosting cost; no measured need.

## Evaluation

Not measured. Decision rests on team size and budget constraints.

## Consequences

- Modules expose service interfaces; no module reads another module's tables directly.
- The worker runs the same codebase with a different entry point.
- A module can be extracted later because boundaries are already explicit.

## Re-evaluation Triggers

- A module needs independent scaling measured in production (e.g., retrieval CPU saturating API latency).
- Team grows to ≥ 4 engineers working on separate domains.
