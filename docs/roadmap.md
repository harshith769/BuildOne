# BuildOne — Roadmap

> **Status:** Draft v0.3 · 2026-10-06 (v3 direction; local-first build order) · Owner: @harshith769
> **Assumptions:** **one developer** (Harshith, sole owner and builder, D-2), ~25–30 focused hours/week, **₹0 out of pocket** ([tech-stack.md §4](tech-stack.md#4-budget)). Everything is built and run **locally** until hosting is approved; hosting follows [ADR-0012](adr/0012-hosting-after-student-pack-change.md).
> Current phase, decisions and gate dates: [status.md](status.md) (wins if this file disagrees). Feature scope per phase: [product-vision.md §13](product-vision.md#13-roadmap). Milestone briefs for Claude Code: [build-plan.md](build-plan.md). Deferred work: [deferred.md](deferred.md).

**What this document answers**
- Which business phases and gates (G0–G3) the product goes through, and when
- In which order the milestones and spikes are built (local-first)
- Which gates block progress, and who (CA, lawyer, users) must close them
- What must never be dropped, and where slipped work goes

---

## 1. Phases and gates

| Phase | When | What happens | Gate |
|---|---|---|---|
| **0. Validate** ← now | Oct – 13 Dec 2026 | Interviews, CA reviewer, lawyer, rule sources, interview kit; M1–M3 built early on purpose (needed whatever the interviews show) | **G0** (13 Dec 2026): pain confirmed (flip rule), 3 pilot letters, CA reviewer signed, spike reports S1–S4 (S5's report is an M4 entry condition, D-25) |
| **1. MVP** | 14 Dec 2026 – ~May 2027 | Local-first build of the MVP (§3): engine + CA-reviewed Telangana Pvt Ltd rules, 6 MVP screens, Launch Planner, Launchpad lite; then hosting (M4) and the pilot (M14) once hosting is approved | **G1a** (~Feb–Mar 2027): local MVP complete — all MUST screens pass acceptance locally; local restore drill passes; zero critical misses on CA-reviewed scenarios · **G1b** (after M4 + M14): zero critical missed obligations; ≥ 60% of pilot companies generate a plan; production restore drill passes; 1 pilot converts to paid |
| **2. Paid pilots** | ~May – Sep 2027 | Convert pilots; Copilot; CA workspace and events; Founder Pro; billing; incorporate if not done | **G2** (end Sep 2027): ~₹10L ARR run-rate; 20 CA firms active; incubators ready to renew |
| **3. Scale** | Oct 2027 – Sep 2028 | Karnataka + Maharashtra rules, LLP/OPC, Gazette change tracking, public changelog, Copilot, Benefits finder; seed round | **G3**: customers renew and expand; 2 platform partners in active talks; ~₹60L ARR |
| **4. Platform** | 2028+ | Engine API, all states, integrations that fill facts automatically, industry modules | — |

Copilot starts in Phase 2 (D-4); the Phase 3 scope continues it.

---

## 2. Phase 0 — Validation

**Customer validation** (details in [product-vision.md §13](product-vision.md#13-roadmap))
- [ ] 30 founder, 10 CA, 3 incubator/E-cell interviews; ~10 pre-founder interviews optional (D-26)
- [ ] Identify and agree terms with **1 CA reviewer** (design partner) — 🔒 external
- [ ] Identify **1 lawyer** for terms, privacy notice, disclaimers and Situation Check wording — 🔒 external
- [ ] Identify 1 campus E-cell or incubator for the pilot cohort — 🔒 external
- [ ] 3 pilot letters (G0)

**Gate G0 (go / pivot / stop)**
- [ ] Interview go-criteria met ([product-vision.md §13](product-vision.md#13-roadmap)) or buyer pivot decided
- [ ] Spike results recorded; remaining `Proposed` ADRs accepted or rewritten; accepted ADRs re-checked against measurements; reports S1–S4 written (S5 follows before M4, D-25)

---

## 3. Build order (local-first)

**M1 ✓ → M2 → M3 → S1, S2 → M5 → M5.1 → S3 → M6 → S4 → M7 → M8 → M9 → M10 → M11 → M12 → M13 → (hosting approved) S5 → M4 → M14**

| Step | What | Notes |
|---|---|---|
| M1 | Scaffold, platform, CI | ✓ Done 2026-10-06 |
| M2 | Identity and sessions | Next |
| M3 | Tenancy (incl. `ca_firm`, `incubator`, access grants), audit, idempotency | |
| **S1, S2** | Parsing; retrieval (fixes embedding dimension `D`) | Right before M5 |
| M5 | Knowledge ingestion and retrieval | |
| M5.1 | Retrieval at full scale (real-corpus recall@10 ≥ 90%, D-31) | Before M9 |
| **S3** | Rule schema with the CA reviewer (30 real obligations, 10 scenarios; `eligibility` kind, threshold facts) | Before real rules in M6; engine work in M6 can start first |
| M6 | Rules engine, fact registry, publication, scenarios | Rules content waits for a signed CA reviewer |
| **S4** | Model per task | Right before M7 |
| M7 | AI gateway | |
| M8 | Facts intake, obligations, reminders | |
| M9 | Explainer and Launch Planner | |
| M10 | Incubator cohort view + CA read-only view + fundraise-ready pack v0 | Replaces Copilot (now Phase 2) |
| M11 | Launchpad lite | Questionnaire-only Situation Check |
| M12 | Data rights, settings, marketing site | |
| M13 | Hardening | → **G1a** |
| **S5** | One-box walking skeleton + ADR-0012 items 1–4 | Right before M4 |
| M4 | Production hosting, backups, observability | Entry: S5 report (D-25) and hosting approved ([deferred.md §1](deferred.md#1-m4--production-hosting-one-box)) |
| M14 | Pilot | → **G1b** ([deferred.md §2](deferred.md#2-m14--live-pilot)) |

### 3.1 Spikes (throwaway code; results recorded in the linked ADR or tech-stack.md)

Reports S1–S4 are due by G0 (13 Dec 2026); the slots below are the latest points. S5's report is an entry condition of M4 (D-25).

- [ ] **S1 Parsing** (before M5) — parse 20 real official sources (incl. ≥ 3 scanned notifications); measure section-structure fidelity → resolves parser choice ([tech-stack.md §3](tech-stack.md#3-open-decisions-resolved-by-spikes))
- [ ] **S2 Retrieval** (before M5) — 50 labelled questions; compare full-text only, vector only, hybrid, hybrid + reranker; measure recall@10 and latency → [NFR-AI-06](nfr.md#7-ai-quality-gates), [ADR-0003](adr/0003-postgres-single-datastore.md)
- [ ] **S3 Rules schema** (before real rules in M6) — express 30 real obligations in YAML; evaluate against 10 CA-verified scenarios; decide the `eligibility` kind, thresholds as versioned facts (D-10) and `superseded` (D-9) → [ADR-0009](adr/0009-rules-as-code.md)
- [ ] **S4 Model per task** (before M7) — run Groq free-plan open-weight models on 30 Q&A, 20 clause-extraction, and 20 rephrasing items; measure faithfulness, citation precision, **tokens per task**; confirm Groq console limits and enable **Zero Data Retention** → [ADR-0008](adr/0008-llm-gateway-provider-agnostic.md)
- [ ] **S5 One-box walking skeleton (local)** (before M4) — full Compose topology on your machine: SPA → API → Postgres + pgvector with sign-in, `wal-g` archiving to R2, then a **restore drill into a clean environment**; record RAM use and restore time; also checks [ADR-0012](adr/0012-hosting-after-student-pack-change.md) items 1–4 (API + worker within ~900 MiB, `initdb` SQL without superuser, `pg_dump` to R2 + timed restore, Azure *Free services* eligibility) → [ADR-0003](adr/0003-postgres-single-datastore.md), [ADR-0006](adr/0006-hosting-digitalocean-cloudflare.md), [ADR-0007](adr/0007-identity-workos-sessions.md), [ADR-0012](adr/0012-hosting-after-student-pack-change.md)

---

## 4. Engineering checklists

### 4.1 Foundation (M1–M3)

- [x] Batch B/C/D specs written (data model, auth/tenancy, security, API, deployment, testing) — execution briefs in [build-plan.md](build-plan.md)
- [x] Complete scaffold per [architecture.md §4](architecture.md#4-repository-layout) — milestone M1
- [ ] CI: ruff, mypy strict, pytest, import-linter contracts, secret scan, dependency scan, frontend type-check
- [x] `platform`: config, UUIDv7, clock, structured logging, request IDs, problem-details errors
- [ ] `identity`: WorkOS callback, server-side sessions, sign-out, session list/revoke, 18+ confirmation (FR-PLT-01)
- [ ] `tenancy`: organisations (`team`, `company`, `ca_firm`, `incubator`), roles, invitations, access grants (FR-PLT-02–04); RLS policies
- [ ] **Cross-tenant test suite** passing, including access grants (NFR-SEC-03)
- [ ] `audit` module (FR-PLT-05)
- [ ] CI integration tests against an ephemeral Postgres + pgvector container (same image tag as production)

**Exit check:** tenancy tests green, including grants.

### 4.2 Knowledge and rules core (M5–M7)

- [x] Specs written: rules-engine.md, data-pipeline.md, ai-system.md, evaluation.md, rule-operations.md
- [ ] `knowledge`: source registry, ingestion CLI (fetch → parse → chunk → embed → load), versioned sources (FR-RS-01)
- [ ] Load 50–100 official sources for the MVP scope ([product-vision.md §4](product-vision.md#4-initial-scope-wedge))
- [ ] Hybrid retrieval + fusion (+ reranker if S2 justified it)
- [ ] `ai`: gateway, prompt registry, schema validation, citation verifier, cost ledger, redaction
- [ ] `rules`: JSON Schema, evaluator with unknown-value semantics, effective dates and due-date logic, traces; property tests
- [ ] Rule drafting CLI (FR-RS-02); review fields enforced in CI (FR-RS-03)
- [ ] **30–50 rules drafted and CA-reviewed** — 🔒 CA reviewer
- [ ] Scenario suite (≥ 30 CA-verified companies) as CI gate (FR-RS-04)
- [ ] Golden sets for retrieval, explanation, Q&A, fact extraction

**Exit check:** NFR-AI-01 recall gate met on scenarios · AI baselines measured and recorded in evaluation.md.

### 4.3 Product features (M8–M12)

- [ ] `facts`: form-first intake, optional free-text proposals, confirmation, history, "I don't know" (FR-CORE-01); document fact extraction as a stretch goal ([deferred.md §9](deferred.md#9-document-fact-extraction-at-intake-stretch))
- [ ] `obligations`: evaluation on change, statuses incl. `needs_info`, effective date shown, calendar feed (FR-CORE-03)
- [ ] Launch Planner on its own screen (FR-CORE-02)
- [ ] `explainer`: deterministic explanation (MUST) + optional AI rephrasing with verification (FR-CORE-04)
- [ ] `notifications`: in-app reminders + ICS calendar feed (MUST), email + weekly digest (SHOULD), idempotent (FR-CORE-06, FR-PLT-07)
- [ ] Incubator cohort view, CA read-only view and share flow (FR-PART-01/02)
- [ ] Fundraise-ready pack v0 (FR-CORE-13)
- [ ] `launchpad`: Team Space, Situation Check questionnaire, Launch Roadmap, handoff (FR-LP-01–03)
- [ ] Data export and deletion (FR-PLT-06); disclaimer component everywhere (FR-PLT-08)
- [ ] Frontend: onboarding, obligation dashboard, calendar, explainer panel, partner views, pack, Launchpad screens; accessibility pass (NFR-UX-01)
- [ ] Astro site: landing page + one free tool ("What do I owe after incorporation?")
- Phase 2 (scope kept in [deferred.md](deferred.md)): `copilot` with routing, daily quotas, budget-exhausted path, abstention, streaming, feedback (FR-CORE-05); `documents`: signed uploads, clause extraction, private-by-default, deletion (FR-LP-02 document check)

**Exit check:** all MVP `MUST` requirements pass acceptance tests locally.

### 4.4 Hardening (M13) → G1a

- [ ] Terms, privacy notice (sub-processors listed), disclaimers — 🔒 **lawyer review**
- [ ] Security checklist against NFR-SEC-01–09; fix all must-fix items
- [ ] Local restore drill; chaos test with AI providers blocked and with AI budget exhausted (NFR-AVL-02, NFR-COST-04)
- [ ] Light load test at pilot profile ×5 (locally, under the production memory limits)
- [ ] Runbooks: bad-rule revert, provider outage (deploy, rollback and restore runbooks are written in M4)

### 4.5 Production (S5 → M4, when hosting is approved)

Full scope and trigger: [deferred.md §1, §3–§5](deferred.md).

- [ ] Spike S5 report, including ADR-0012 items 1–4
- [ ] **Sign up for Azure for Students and deploy** ([ADR-0012](adr/0012-hosting-after-student-pack-change.md), Proposed); fallback: paid DigitalOcean Bangalore; set billing alerts either way
- [ ] Domain, Cloudflare DNS/CDN/firewall/TLS, Pages
- [ ] One-box hardening (NFR-SEC-12): Cloudflare-only origin, SSH key-only, unattended upgrades, internal-only Postgres
- [ ] Sentry, telemetry, uptime checks, AI budget alerts wired (NFR-OBS-01/02, NFR-COST-04)
- [ ] Continuous archiving (`wal-g`, or the managed provider's point-in-time restore) + nightly dump to R2 + **first production restore drill onto a fresh server** (NFR-REL-01/02/03)
- [ ] Provision-and-restore script committed in `infra/scripts/`
- [ ] Performance targets re-checked on the production host

**Exit check:** deploy from `main` is one command · restore drill completed within RTO and data loss within RPO.

### 4.6 Pilot (M14) → G1b

- [ ] Pilot: onboard one incubator cohort (10–20 companies) + 2–3 CA firms (D-26)
- [ ] Weekly feedback review; log missed/incorrect obligations as P0 bugs
- [ ] Qualitative willingness-to-pay evidence collected

**Exit = G1b** (§1).

---

## 5. Non-negotiables

There is **no cut list** (owner decision, 2026-10-06). Nothing is removed to save time: work that slips moves to [deferred.md](deferred.md) with its full scope and the trigger that brings it back, and only with the owner's OK ([AGENTS.md rule 19](../AGENTS.md)).

Never dropped or deferred: incubator view, tenant isolation, audit log, `needs_info` handling, CA review of rules, citations, continuous backups and restore drills, disclaimers, in-app reminders + calendar feed.

---

## 6. After the pilot

Phase 2–4 features follow [product-vision.md §13](product-vision.md#13-roadmap).

**Infrastructure milestones** (growth path in [architecture.md §7.2](architecture.md#72-growth-path)):
- [ ] **Month ~10 after the M4 signup:** decide the home after the free period ([ADR-0012](adr/0012-hosting-after-student-pack-change.md) re-evaluation triggers) — renew student benefits if still enrolled, pay for the server (~₹1,000–2,100/month), or stage 2
- [ ] **First paying customer:** stage 2 — managed Postgres (dump/restore, connection-string change)
- [ ] **Before paid launch:** stage 4 (standby database, 2 API instances), OWASP ASVS L2 verification, external security review, billing ([deferred.md §6](deferred.md#6-billing-razorpay)), DPDP compliance programme ([NFR-PRV-08](nfr.md#6-privacy-and-data-protection)), and cost-model.md built from pilot measurements

## 7. Future considerations (undecided)

- Whether to hire a part-time CA reviewer vs. revenue-share with partner CAs (any arrangement must avoid fee-sharing, D-1)
- Whether to apply for incubator/startup programs for cloud credits before credits expire
