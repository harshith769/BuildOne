# ADR-0009: Rules-as-code — YAML rules in git, custom evaluator, published to Postgres

- **Status:** Proposed
- **Date:** 2026-09-28
- **Decision makers:** @harshith769
- **Confidence:** To be set by owner on acceptance (proposer's view: Medium — validated by spike S3)

## Decision

**Author rules as YAML files in the repository, validated by JSON Schema, reviewed through pull requests, tested by the scenario suite in CI, and published into Postgres as immutable versions; evaluate them with a small custom Python evaluator that produces explanation traces.** Git gives versioning, review, and history for free; a custom evaluator gives date arithmetic, `needs_info` handling, and citation-aware traces that generic engines do not.

## Context

Rules are the product's moat and its liability. Requirements: deterministic evaluation, three-valued logic (true / false / unknown → `needs_info`), due-date computation in `Asia/Kolkata`, versioning with effective dates, reviewer sign-off, and traces that the Explainer can render.

## Candidates

### A. YAML + JSON Schema + custom evaluator (git as source of truth)
- Fits review workflow and CI gates; traces designed for explanations.
- We own the evaluator (kept small; property-tested).

### B. JsonLogic-style generic rule format
- Existing format and evaluators.
- No native unknown-value semantics or date-offset primitives; traces would be bolted on.

### C. Policy engine (e.g., Open Policy Agent / Rego)
- Powerful, well-tested policy evaluation.
- Separate language and runtime for a Python-first solo developer; built for authorization, not due-date computation.

### D. Rules edited in a database UI
- Friendly for non-developers.
- Loses git review/history; UI must be built first. Revisit when CA reviewers need direct editing.

## Evaluation

Not measured → spike S3: express 30 real obligations in the schema; all must evaluate correctly on CA-verified scenarios.

## Consequences

- Rule Studio in MVP = repository + CLI + CI, not a web UI.
- Rule file records reviewer identity and review date (FR-RS-03).
- Each rule carries a CA-approved plain-language summary and "what to do" text; the deterministic Explainer renders these with the evaluation trace ([requirements.md FR-CORE-04](../requirements.md#fr-core-04-why-this-applies-explainer-c4--must)).
- Publication triggers re-evaluation jobs for affected organisations.

## Re-evaluation Triggers

- Spike S3 finds obligations the schema cannot express cleanly.
- CA reviewers need to edit rules directly at volume.
