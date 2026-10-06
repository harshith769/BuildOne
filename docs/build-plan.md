# BuildOne — Build Plan for Claude Code

> **Status:** v1.0 · 2026-09-28 · Owner: @harshith769
> Schedule and gates: [roadmap.md](roadmap.md). This file is the execution guide: what is frozen, how to run Claude Code sessions, and the milestone briefs to paste.

**What this document answers**
- Which decisions are frozen and which may still change (and where)
- The exact working protocol for every Claude Code session
- Accounts and setup the owner must do by hand, and when
- Milestones M0–M14: scope, docs to read, done criteria, and the prompt to paste

---

## 1. Architecture freeze

### 1.1 Frozen (change only via a new ADR approved by the owner)

Modular monolith and module boundaries ([architecture.md §3](architecture.md#3-backend-modules)) · Python/FastAPI/SQLAlchemy/Alembic · single Postgres with RLS, roles, schemas, conventions ([data-model.md](data-model.md)) · Procrastinate jobs · sessions/CSRF/tenancy model ([auth-and-tenancy.md](auth-and-tenancy.md)) · API conventions ([api-conventions.md](api-conventions.md)) · rule/fact formats and three-valued logic ([rules-engine.md](rules-engine.md)) · retrieval algorithm ([data-pipeline.md §6](data-pipeline.md#6-retrieval-frozen-algorithm-parameters-tunable-via-evaluation)) · AI gateway, routing policy, budgets, verifier ([ai-system.md](ai-system.md)) · one-box deployment and backups ([deployment.md](deployment.md)) · portability rules ([ADR-0011](adr/0011-portability-rules.md)).

### 1.2 Open seams (decided by spikes; implementation swaps behind a fixed interface)

| Seam | Interface | Decided by |
|---|---|---|
| Document parser | `Parser` | S1 |
| Embedding model + dimension `D` | `Embedder` | S2 (fix `D` before M5 migration) |
| Reranker (on/off, which) | `Reranker` | S2 |
| Model per AI task | task registry config | S4 |
| Thresholds `τ` (retrieval confidence), `σ` (citation similarity) | config | S2/S4 |
| Email provider | `EmailSender` | M8 |

### 1.3 Change control

If Claude Code (or you) believes a frozen decision is wrong: **stop implementing**, write `docs/adr/NNNN-<slug>.md` with status `Proposed`, and decide before continuing. Never "just refactor" a frozen area.

---

## 2. Claude Code working protocol

**Before the first session:** repository contains this scaffold; `CLAUDE.md` imports `AGENTS.md`; `.claude/settings.json` denies reading `.env` files.

**Every session:**
1. One milestone (or one slice of it) per session, one git branch per milestone: `m<N>-<slug>`.
2. Start in **plan mode**. Paste the session template (§2.1) + the milestone brief (§4). Review the plan; approve or correct.
3. Logic first with tests (evaluator, dates, permissions, budgets); integration tests for every endpoint and table.
4. Run `make check` before declaring done. Never mark done with failing checks.
5. If behaviour diverges from a doc, update the doc in the same branch (one fact, one home).
6. Commit in small steps with conventional messages (`feat(rules): …`, `fix(tenancy): …`); open a PR so CI runs; merge when green.
7. Use `/clear` between unrelated tasks to keep context focused.

### 2.1 Session template (paste first)

```
Read AGENTS.md. Then read the documents listed in the brief below before proposing anything.
Rules for this session:
- Do not change anything listed as Frozen in docs/build-plan.md §1.1. If you think a frozen decision is wrong, stop and draft an ADR instead.
- Work only on the scope in the brief. List anything out of scope you notice as follow-ups at the end.
- Write tests for logic and integration tests for every endpoint/table. Never mock the database.
- Finish by running `make check` and reporting results, files changed, docs updated, and follow-ups.
Brief:
<paste milestone brief>
```

---

## 3. Owner setup (manual)

| When | Task |
|---|---|
| Now | GitHub repo (private) with branch protection on `main` (require CI); GitHub Student Developer Pack |
| Now | Cloudflare account + domain (Student Pack domain offer or existing) |
| Now | WorkOS account (dev environment) — redirect `http://localhost:8000/v1/auth/callback` |
| Now | Groq account → **enable Zero Data Retention** in Data Controls → note per-model limits from the console Limits page |
| Now | Google AI Studio key (Gemini free tier — public text only) |
| Now | Sentry account (free) |
| Now | Password manager for all secrets (Student Pack offers one) |
| Now | Cloudflare R2: buckets `buildone-files-dev`, `buildone-sources`, `buildone-backups-dev` + scoped API tokens |
| Phase 0 | Interviews; find CA reviewer; contact a lawyer for pilot terms/privacy |
| Optional | Azure for Students signup → record whether *Free services* lists Postgres B1MS and VMs |
| **M4 only** | Sign up for Azure for Students (12-month free services start at signup) per ADR-0012, or the paid fallback; production buckets/tokens |

---

## 4. Milestones

Each brief lists: **Read** (docs), **Build**, **Done when**. Weeks follow [roadmap.md](roadmap.md).

### M0 — Spikes S1–S5 (weeks 1–4) · throwaway code in `spikes/` (gitignored except reports)
- **Read:** roadmap.md Phase 0, tech-stack.md §3, data-pipeline.md, ai-system.md §7, deployment.md §5, docs/spikes/TEMPLATE.md
- **Build:** one session per spike. S1 parser comparison on 20 real sources · S2 retrieval (50 labelled questions; lexical vs vector vs hybrid ± reranker; RAM/latency on 2 GB) · S3 express 30 real obligations in the rule schema + 10 scenarios · S4 Groq models on Q&A/clause/rephrase sets; tokens per task · S5 local one-box Compose: Postgres+pgvector+wal-g → R2, restore drill, RAM profile
- **Done when:** five reports in `docs/spikes/`; `tech-stack.md §3` decisions recorded; `D`, `τ`, `σ` set; ADR-0009 accepted or revised

### M1 — Scaffold, platform, CI (week 5)
- **Read:** AGENTS.md, architecture.md §3–4 §6, data-model.md §1–3 §7, api-conventions.md, testing-strategy.md, deployment.md §1–4
- **Build:** backend package per layout; `platform` (config, UUIDv7, clock, JSON logging, request ID, problem-details errors, DB session that sets `app.user_id/app.org_id` per transaction); `/healthz`, `/readyz`; Alembic baseline: roles, schemas, extensions (`vector`, `pg_trgm`, `citext`), helper functions; worker entry with Procrastinate; import-linter contracts; CI checks for RLS/extension allowlist; frontend scaffold (Vite React TS, Tailwind, shadcn/ui, TanStack Router/Query, generated client, Playwright set up); `make openapi` drift check
- **Done when:** `make dev` starts the full local topology; `make check` green locally and in CI

### M2 — Identity and sessions (week 6)
- **Read:** auth-and-tenancy.md §1–3 §8, data-model.md §4.1, ADR-0007
- **Build:** `IdentityProvider` interface; fake + WorkOS adapters; login/callback/logout with PKCE+state; sessions (hash, idle/absolute expiry, rotation); CSRF double-submit + Origin check; consent + 18+ screen; `/v1/me`, sessions list/revoke; S1, S2 screens
- **Done when:** integration tests for expiry, revocation, replay, CSRF rejection, open-redirect rejection; E2E sign-in with fake IdP

### M3 — Tenancy, audit, idempotency (week 7)
- **Read:** auth-and-tenancy.md §4–6 §9, data-model.md §3 §4.2–4.3 §4.11, api-conventions.md §4
- **Build:** organisations, memberships (last-owner trigger), invitations, permission matrix `require()`, org dependency, RLS on all tenant tables, audit module, idempotency middleware; S3, S4 screens
- **Done when:** cross-tenant suite covers every tenant table and endpoint and is green; audit entries asserted in tests

### M4 — One-box production, backups, observability (week 8)
- **Read:** deployment.md, security-design.md §3–4, ADR-0006, NFR-SEC-12
- **Build:** `infra/scripts/provision.sh`; hardened server; Caddy with Cloudflare-only origin; deploy workflow with rollback; wal-g + nightly dumps; restore script; Sentry wiring; ops-check job; runbooks `deploy-and-rollback`, `restore`, `server-hardening-and-patching`
- **Done when:** deploy from `main` works end to end; **restore drill onto a fresh server** meets RPO ≤ 15 min and RTO ≤ 4 h (recorded)

### M5 — Knowledge ingestion and retrieval (weeks 9–10)
- **Read:** data-pipeline.md, data-model.md §4.7, S1/S2 reports, evaluation.md
- **Build:** source registry loader; ingest CLI (fetch, R2 raw store, parser seam, chunking policy, embedder seam, transactional load, supersede); retrieval service; `make eval-retrieval` in CI; load initial MVP sources
- **Done when:** retrieval recall@10 ≥ 90% on the labelled set; p95 retrieval < 300 ms on production hardware

### M6 — Rules engine, fact registry, publication, scenarios (weeks 10–12)
- **Read:** rules-engine.md, rule-operations.md, data-model.md §4.4–4.6, S3 report
- **Build:** `rule.schema.json` finalised; Pydantic models; evaluator (three-valued logic, schedules, overrides, traces); Hypothesis property tests; publication job; scenario runner (`make eval-rules`) as CI gate; `facts.yaml` for MVP scope
- **Parallel (owner + CA):** draft and review 30–50 rules and ≥ 30 scenarios
- **Done when:** property tests green; scenario recall ≥ 98% with zero critical misses

### M7 — AI gateway (weeks 12–13)
- **Read:** ai-system.md, ADR-0008, S4 report, NFR-PRV-02/05, NFR-COST-02/04
- **Build:** gateway, task registry, prompt files, Groq + Gemini adapters, routing policy enforcement (`user_data_allowed`), budget/quota via `ai.calls`, scrubber, citation verifier, fake provider, `make eval-ai`, `make rule-draft`
- **Done when:** tests prove user-data tasks cannot route to non-allowed providers; budget exhaustion raises before any network call; verifier unit tests cover all four checks

### M8 — Facts intake, obligations, reminders (weeks 14–15)
- **Read:** requirements.md FR-CORE-01/03/06, data-model.md §4.4 §4.6 §4.11 §6, ux-screens.md S9 S10 S12 S15 S16
- **Build:** facts service (form, unknown, history, proposals); evaluation orchestration jobs (on fact change, on publication); obligations API with derived urgency; mark done; in-app reminders job (via SECURITY DEFINER scan + per-org transactions); ICS feed; email channel (SHOULD); screens
- **Done when:** end-to-end: confirm facts → obligations with correct due dates → reminders created exactly once under replay

### M9 — Explainer and Launch Planner (week 16)
- **Read:** requirements.md FR-CORE-02/04, architecture.md §5.2, ux-screens.md S11 S13
- **Build:** deterministic explanation renderer from trace + rule text + citations; optional rephrase with verification and cache; Launch Planner; screens
- **Done when:** deterministic output identical across runs (tests); rephrase falls back correctly when verification fails or budget is spent

### M10 — Copilot (weeks 17–18)
- **Read:** requirements.md FR-CORE-05, architecture.md §5.3, ai-system.md, api-conventions.md §5, ux-screens.md S14
- **Build:** conversations/messages, routing, determination route (no generation of facts), interpretive route with retrieval + abstention, SSE streaming, verification, quotas, feedback; screen
- **Done when:** Copilot eval meets NFR-AI-02/03/04 on the on-demand set; `limit_reached` path covered by E2E

### M11 — Launchpad and documents (weeks 19–20)
- **Read:** requirements.md FR-LP-01..03, data-model.md §4.10, auth-and-tenancy.md §4, ux-screens.md S5–S8
- **Build:** team profile, member facts, risk_check/roadmap_trigger rules evaluation into `launchpad.check_results`, document upload (signed URLs), clause extraction job with privacy defaults, Launch Roadmap, incorporation handoff (facts as proposals); screens
- **Done when:** document privacy enforced by RLS tests; handoff creates company with proposals, not confirmed facts

### M12 — Data rights, settings, marketing site (week 21)
- **Read:** requirements.md FR-PLT-06..08, auth-and-tenancy.md §8, ux-screens.md S16 S17 §3
- **Build:** exports, deletion lifecycle + sweeper (DB + R2), preferences, settings screens, disclaimer component everywhere, Astro site + free tool, accessibility pass
- **Done when:** deletion removes DB rows and R2 objects after grace period (integration test with frozen clock); axe checks pass on all screens

### M13 — Hardening (weeks 22–23)
- **Read:** security-design.md, nfr.md, testing-strategy.md
- **Build:** security checklist fixes, rate limits, chaos tests (AI blocked, budget exhausted), light load test (pilot ×5), remaining runbooks, restore drill #2
- **Done when:** all NFR-SEC MVP items verified; drills logged; lawyer-reviewed terms/privacy in place 🔒

### M14 — Pilot launch (week 24)
- **Build:** pilot onboarding checklist, read-only metrics views (`app_readonly`), feedback triage routine
- **Done when:** 10 design-partner companies + 1 campus cohort onboarded
