# BuildOne — Testing Strategy

> **Status:** v1.0 · 2026-09-28 · Owner: @harshith769
> Principle: test where things break in interesting ways; integration over mocks; no network, no real time, no unseeded randomness in tests.

**What this document answers**
- What is tested at which level, and what is deliberately not tested
- Which suites are mandatory gates in CI
- How time, AI providers, identity, and storage are handled in tests

## 1. Levels

| Level | Tooling | Covers | Density |
|---|---|---|---|
| Unit | pytest, Hypothesis | Rules evaluator (three-valued logic, schedules, overrides, month clamping), fact type validation, scrubber, citation verifier, RRF fusion, permission matrix | Dense |
| Integration | pytest + real Postgres (CI service container / local compose) | Every endpoint, RLS, migrations up/down, idempotency keys, job idempotency, notification uniqueness, budget accounting | Every endpoint |
| Cross-tenant suite | `backend/tests/tenancy/` | For every tenant table and endpoint: user of org A cannot read/write org B (API and direct SQL with RLS context) | Mandatory gate |
| Rule scenarios | `rules/scenarios/` | Obligation recall/due dates | Mandatory gate |
| E2E | Playwright (`frontend/app/e2e/`) against the real API (fresh database, fake IdP; `backend/tests/e2e_server.py`) | Sign-in (fake IdP) → intake → obligation plan → explanation → mark done → ICS feed; Launchpad team → handoff | 5–8 flows |
| AI evals | [evaluation.md](evaluation.md) | Prompt/model quality | On demand |

## 2. Test doubles (only at external boundaries)

| Boundary | Double |
|---|---|
| Identity provider | `FakeIdentityProvider` (same interface as WorkOS adapter) |
| AI providers | `FakeProvider` returning recorded fixtures from `backend/tests/fixtures/ai/`; contract tests against real providers run on demand only |
| Object storage | SeaweedFS container in CI/local (S3 API; `weed mini`) |
| Email | In-memory outbox |
| Clock | Injected `Clock`; tests freeze to fixed dates incl. month-end and FY boundaries |

Never mock the database or the module under test.

## 3. Rules

- Bug fix = failing regression test first.
- A test must fail if the feature is removed (spot-check during review).
- Flaky test: fix or delete the same day.
- CI budget: unit + integration < 10 min; E2E on `main` only.
