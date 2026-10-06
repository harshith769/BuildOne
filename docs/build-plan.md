# BuildOne — Build Plan for Claude Code

> **Status:** v1.1 · 2026-10-06 (local-first order; M10 = partner views + pack v0; Copilot to Phase 2) · Owner: @harshith769
> Schedule and gates: [roadmap.md](roadmap.md). Deferred milestones and features keep their full scope in [deferred.md](deferred.md). This file is the execution guide: what is frozen, how to run Claude Code sessions, and the milestone briefs to paste.

**What this document answers**
- Which decisions are frozen and which may still change (and where)
- The exact working protocol for every Claude Code session
- Accounts and setup the owner must do by hand, and when
- The local-first build order, with the spike slots
- Milestones M1–M14 and spikes S1–S5: scope, docs to read, done criteria, and the prompt to paste

---

## 1. Architecture freeze

### 1.1 Frozen (change only via a new ADR approved by the owner)

Modular monolith and module boundaries ([architecture.md §3](architecture.md#3-backend-modules)) · Python/FastAPI/SQLAlchemy/Alembic · single Postgres with RLS, roles, schemas, conventions ([data-model.md](data-model.md)) · Procrastinate jobs · sessions/CSRF/tenancy model ([auth-and-tenancy.md](auth-and-tenancy.md)) · API conventions ([api-conventions.md](api-conventions.md)) · rule/fact formats and three-valued logic ([rules-engine.md](rules-engine.md)) · retrieval algorithm ([data-pipeline.md §6](data-pipeline.md#6-retrieval-frozen-algorithm-parameters-tunable-via-evaluation)) · AI gateway, routing policy, budgets, verifier ([ai-system.md](ai-system.md)) · one-box deployment and backups ([deployment.md](deployment.md)) · portability rules ([ADR-0011](adr/0011-portability-rules.md)).

### 1.2 Open seams (decided by spikes; implementation swaps behind a fixed interface)

| Seam | Interface | Decided by |
|---|---|---|
| Document parser | `Parser` | S1 |
| Embedding model + dimension `D` | `Embedder` | S2 (right before M5; fix `D` before the M5 migration) |
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
| Before M4 (deferred) | Cloudflare account + domain (Student Pack domain offer or existing) — [deferred.md §4](deferred.md#4-domain-and-dns) |
| Now | WorkOS account (dev environment) — redirect `http://localhost:8000/v1/auth/callback` |
| Now | Groq account → **enable Zero Data Retention** in Data Controls → note per-model limits from the console Limits page |
| Now | Google AI Studio key (Gemini free tier — public text only) |
| Before M4 (deferred) | Sentry account (free) — [deferred.md §5](deferred.md#5-production-sentry) |
| Now | Password manager for all secrets (Student Pack offers one) |
| Before S1/S5 | Cloudflare R2: buckets `buildone-files-dev`, `buildone-sources`, `buildone-backups-dev` + scoped API tokens (local development uses SeaweedFS) |
| Phase 0 | Interviews; find CA reviewer; contact a lawyer for pilot terms/privacy |
| Optional | Azure for Students signup → record whether *Free services* lists Postgres B1MS and VMs |
| **M4 only** (after hosting is approved) | Sign up for Azure for Students (12-month free services start at signup) per ADR-0012, or the paid fallback; production buckets/tokens ([deferred.md §1, §3](deferred.md)) |

---

## 4. Milestones

Each brief lists: **Read** (docs), **Build**, **Done when**. Dates and gates follow [roadmap.md](roadmap.md).

### 4.0 Build order (local-first, D-23)

**M1 ✓ → M2 → M3 → S1, S2 → M5 → S3 → M6 → S4 → M7 → M8 → M9 → M10 → M11 → M12 → M13 → (hosting approved) S5 → M4 → M14**

Spike slots: S1 and S2 right before M5 · S3 before real rules in M6 · S4 before M7 · S5 before M4. Reports S1–S4 are due by G0 (13 Dec 2026) at the latest; S5's report is an entry condition of M4 (D-25). Everything up to M13 runs locally; M4 and M14 wait until the owner approves hosting ([deferred.md §1–§2](deferred.md)). The briefs below follow this order.

### Spikes S1–S5 · throwaway code in `spikes/` (gitignored except reports)
- **Read:** roadmap.md §3.1, tech-stack.md §3, data-pipeline.md, ai-system.md §7, deployment.md §5, docs/spikes/TEMPLATE.md
- **Build:** one session per spike, each in its slot. **S1** (before M5) parser comparison on 20 real sources · **S2** (before M5) retrieval (50 labelled questions; lexical vs vector vs hybrid ± reranker; RAM/latency on 2 GB) · **S3** (before real rules in M6) express 30 real obligations in the rule schema + 10 scenarios; decide `eligibility` kind, threshold facts (D-10), `superseded` (D-9) · **S4** (before M7) Groq models on Q&A/clause/rephrase sets; tokens per task · **S5** (before M4) local one-box Compose: Postgres+pgvector+wal-g → R2, restore drill, RAM profile; **also checks [ADR-0012](adr/0012-hosting-after-student-pack-change.md) items 1–4** (API + worker within ~900 MiB; `initdb` SQL without superuser, including creating the BYPASSRLS role `app_rls_check` (ADR-0013); `pg_dump` to R2 and timed restore into fresh Postgres 18; Azure *Free services* eligibility)
- **Done when (per spike):** report in `docs/spikes/`; matching `tech-stack.md §3` decision recorded (S2: `D`, `τ`; S4: `σ`); S3: ADR-0009 accepted or revised; S5: ADR-0012 accepted or option B chosen

### M1 — Scaffold, platform, CI ✓ (done 2026-10-06)
- **Read:** AGENTS.md, architecture.md §3–4 §6, data-model.md §1–3 §7, api-conventions.md, testing-strategy.md, deployment.md §1–4
- **Build:** backend package per layout; `platform` (config, UUIDv7, clock, JSON logging, request ID, problem-details errors, DB session that sets `app.user_id/app.org_id` per transaction); `/healthz`, `/readyz`; Alembic baseline: roles, schemas, extensions (`vector`, `pg_trgm`, `citext`), helper functions; worker entry with Procrastinate; import-linter contracts; CI checks for RLS/extension allowlist; frontend scaffold (Vite React TS, Tailwind, shadcn/ui, TanStack Router/Query, generated client, Playwright set up); `make openapi` drift check
- **Done when:** `make dev` starts the full local topology; `make check` green locally and in CI

### M2 — Identity and sessions
- **Read:** auth-and-tenancy.md §1–3 §8, data-model.md §4.1, ADR-0007
- **Build:** `IdentityProvider` interface; fake + WorkOS adapters; login/callback/logout with PKCE+state; sessions (hash, idle/absolute expiry, rotation); CSRF double-submit + Origin check; consent + 18+ screen; `/v1/me`, sessions list/revoke; S1, S2 screens
- **Done when:** integration tests for expiry, revocation, replay, CSRF rejection, open-redirect rejection; E2E sign-in with fake IdP

### M3 — Tenancy, access grants, audit, idempotency
- **Read:** auth-and-tenancy.md §4–6 §9, data-model.md §3 §4.2–4.3 §4.11, api-conventions.md §4, requirements.md FR-PART-01/02
- **Build:** organisations (`team`, `company`, `ca_firm`, `incubator`), memberships (last-owner trigger), invitations, **access grants** (founder shares a company with a CA firm; incubator reads cohort companies; read grants stay read-only at the database — data-model.md §4.2), permission matrix `require()`, org dependency, RLS on all tenant tables, audit module, idempotency middleware; S3, S4 screens
- **Done when:** cross-tenant suite covers every tenant table and endpoint, including grantee access (read allowed only with an active grant; writes always denied) and revocation, and is green; audit entries asserted in tests

### M5 — Knowledge ingestion and retrieval (after S1, S2)
- **Read:** data-pipeline.md, data-model.md §4.7, S1/S2 reports, evaluation.md
- **Build:** source registry loader; ingest CLI (fetch, R2 raw store, parser seam, chunking policy, embedder seam, transactional load, supersede); retrieval service; `make eval-retrieval` in CI; load initial MVP sources
- **Done when:** retrieval recall@10 ≥ 90% on the labelled set; p95 retrieval < 300 ms measured locally under the production memory limits (re-checked on the production host in M4)

### M6 — Rules engine, fact registry, publication, scenarios (real rules after S3)
- **Read:** rules-engine.md, rule-operations.md, data-model.md §4.4–4.6, S3 report
- **Build:** `rule.schema.json` finalised; Pydantic models; evaluator (three-valued logic, schedules, **effective dates**, overrides, traces); `eligibility` kind and threshold facts if S3 confirms them; decide D-9 (`superseded`); Hypothesis property tests; publication job; scenario runner (`make eval-rules`) as CI gate; `facts.yaml` for MVP scope
- **Parallel (owner + CA):** draft and review 30–50 rules and ≥ 30 scenarios
- **Done when:** property tests green; scenario recall ≥ 98% with zero critical misses

### M7 — AI gateway (after S4)
- **Read:** ai-system.md, ADR-0008, S4 report, NFR-PRV-02/05, NFR-COST-02/04
- **Build:** gateway, task registry, prompt files, Groq + Gemini adapters, routing policy enforcement (`user_data_allowed`), budget/quota via `ai.calls`, scrubber, citation verifier, fake provider, `make eval-ai`, `make rule-draft`
- **Stretch:** document fact extraction task ([deferred.md §9](deferred.md#9-document-fact-extraction-at-intake-stretch))
- **Done when:** tests prove user-data tasks cannot route to non-allowed providers; budget exhaustion raises before any network call; verifier unit tests cover all four checks

### M8 — Facts intake, obligations, reminders
- **Read:** requirements.md FR-CORE-01/03/06, data-model.md §4.4 §4.6 §4.11 §6, ux-screens.md S9 S10 S12 S15 S16
- **Build:** facts service (form, unknown, history, proposals); evaluation orchestration jobs (on fact change, on publication); obligations API with derived urgency and rule effective date; mark done; in-app reminders job (via SECURITY DEFINER scan + per-org transactions); ICS feed; email channel (SHOULD); screens
- **Stretch:** document upload at intake → proposals ([deferred.md §9](deferred.md#9-document-fact-extraction-at-intake-stretch))
- **Done when:** end-to-end: confirm facts → obligations with correct due dates → reminders created exactly once under replay

### M9 — Explainer and Launch Planner
- **Read:** requirements.md FR-CORE-02/04, architecture.md §5.2, ux-screens.md S11 S13
- **Build:** deterministic explanation renderer from trace + rule text + citations; optional rephrase with verification and cache; Launch Planner on its own screen (D-20); screens
- **Done when:** deterministic output identical across runs (tests); rephrase falls back correctly when verification fails or budget is spent

### M10 — Incubator cohort view, CA read-only view, fundraise-ready pack v0
Replaces the former M10 Copilot milestone (Copilot is Phase 2, D-4; its brief is kept in [deferred.md §7](deferred.md#7-copilot-phase-2)).
- **Read:** requirements.md FR-PART-01/02, FR-CORE-13, data-model.md §4.2 (access grants), auth-and-tenancy.md §4, ux-screens.md S18–S21
- **Build:** share flow (company → CA firm; incubator cohort invitation → company accepts; revoke); CA firm clients list and read-only plan/detail; incubator cohort dashboard v0; fundraise-ready pack v0 export (deterministic, no AI; plan, status, gaps, citations, eligibility results if published); audit entries; screens
- **Done when:** CA firms and incubators see only companies with an active grant, read-only (RLS tests); revocation takes effect on the next request; the pack is identical across runs for the same inputs (snapshot tests); E2E for share → view → revoke

### M11 — Launchpad lite
- **Read:** requirements.md FR-LP-01..03, data-model.md §4.10, auth-and-tenancy.md §4, ux-screens.md S5–S8
- **Build:** team profile, member facts, Situation Check questionnaire (lawyer-reviewed wording), risk_check/roadmap_trigger rules evaluation into `launchpad.check_results`, Launch Roadmap, incorporation handoff (facts as proposals); screens
- **Deferred to Phase 2 (D-5):** document upload (signed URLs), clause extraction job with privacy defaults, and the done-criterion "document privacy enforced by RLS tests" — full scope in [deferred.md §8](deferred.md#8-situation-check-clause-extraction-document-check)
- **Done when:** handoff creates company with proposals, not confirmed facts

### M12 — Data rights, settings, marketing site
- **Read:** requirements.md FR-PLT-06..08, auth-and-tenancy.md §8, ux-screens.md S16 S17 §4
- **Build:** exports, deletion lifecycle + sweeper (DB + object storage), preferences, settings screens, disclaimer component everywhere, Astro site + free tool (built locally; published once a domain exists, [deferred.md §4](deferred.md#4-domain-and-dns)), accessibility pass
- **Done when:** deletion removes DB rows and stored objects after grace period (integration test with frozen clock); axe checks pass on all screens

### M13 — Hardening → G1a
- **Read:** security-design.md, nfr.md, testing-strategy.md
- **Build:** security checklist fixes, rate limits, chaos tests (AI blocked, budget exhausted), light load test (pilot ×5, locally under production memory limits), runbooks not tied to a host, local restore drill
- **Done when:** all NFR-SEC MVP items verified locally; drills logged; lawyer-reviewed terms/privacy in place 🔒; G1a criteria met ([roadmap.md §1](roadmap.md#1-phases-and-gates))

### M4 — One-box production, backups, observability (after S5, when hosting is approved)
**Entry conditions:** S5 report written and passing (D-25), and the owner approves hosting. Full scope and trigger in [deferred.md §1](deferred.md#1-m4--production-hosting-one-box).
- **Read:** deployment.md, security-design.md §3–4, ADR-0006, ADR-0012, S5 report, NFR-SEC-12
- **Build:** `infra/scripts/provision.sh`; hardened server; Caddy with Cloudflare-only origin; deploy workflow with rollback; wal-g + nightly dumps; restore script; Sentry wiring; ops-check job; runbooks `deploy-and-rollback`, `restore`, `server-hardening-and-patching`
- **Done when:** deploy from `main` works end to end; **restore drill onto a fresh server** meets RPO ≤ 15 min and RTO ≤ 4 h (recorded); M5 retrieval latency and M13 load test re-checked on the production host

### M14 — Pilot launch → G1b
Deferred until M4 is done; full scope and trigger in [deferred.md §2](deferred.md#2-m14--live-pilot).
- **Build:** pilot onboarding checklist, read-only metrics views (`app_readonly`), feedback triage routine
- **Done when:** one incubator cohort (10–20 companies) + 2–3 CA firms onboarded (D-26); G1b tracked from here
