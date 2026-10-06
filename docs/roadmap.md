# BuildOne — Build Roadmap (Solo, MVP to Pilot)

> **Status:** Draft v0.2 · 2026-09-28 (revised for ₹0 one-box MVP) · Owner: @harshith769
> **Assumptions:** one developer, ~25–30 focused hours/week, **₹0 out of pocket** ([tech-stack.md §4](tech-stack.md#4-budget)). Product-level roadmap (v1, v2, platform) is in [product-vision.md §13](product-vision.md#13-roadmap); this file is the engineering build plan to reach the pilot.

> **Milestone briefs for Claude Code (M0–M14):** [build-plan.md](build-plan.md).

**What this document answers**
- What gets built in which order over ~24 weeks, with checkboxes
- Which spikes must pass before committing to a design
- Which gates block progress, and who (CA, lawyer, users) must close them
- What to cut first if the schedule slips

---

## Phase 0 — Validation and spikes (weeks 1–4)

**Customer validation** (details in [product-vision.md §13](product-vision.md#13-roadmap))
- [ ] 15 founder, 10 pre-founder, 5 CA, 2 incubator/E-cell interviews
- [ ] Identify and agree terms with **1 CA reviewer** (design partner) — 🔒 external
- [ ] Identify 1 campus E-cell or incubator for the pilot cohort — 🔒 external

**Technical spikes** (throwaway code; results recorded in the linked ADR or tech-stack.md)
- [ ] **S1 Parsing** — parse 20 real official sources (incl. ≥ 3 scanned notifications); measure section-structure fidelity → resolves parser choice ([tech-stack.md §3](tech-stack.md#3-open-decisions-resolved-by-spikes))
- [ ] **S2 Retrieval** — 50 labelled questions; compare full-text only, vector only, hybrid, hybrid + reranker; measure recall@10 and latency → [NFR-AI-06](nfr.md#7-ai-quality-gates), [ADR-0003](adr/0003-postgres-single-datastore.md)
- [ ] **S3 Rules schema** — express 30 real obligations in YAML; evaluate against 10 CA-verified scenarios → [ADR-0009](adr/0009-rules-as-code.md)
- [ ] **S4 Model per task** — run Groq free-plan open-weight models on 30 Q&A, 20 clause-extraction, and 20 rephrasing items; measure faithfulness, citation precision, **tokens per task**; confirm Groq console limits and enable **Zero Data Retention** → [ADR-0008](adr/0008-llm-gateway-provider-agnostic.md)
- [ ] **S5 One-box walking skeleton (local)** — full Compose topology on your machine: SPA → API → Postgres + pgvector with sign-in, `wal-g` archiving to R2, then a **restore drill into a clean environment**; record RAM use and restore time → [ADR-0003](adr/0003-postgres-single-datastore.md), [ADR-0006](adr/0006-hosting-digitalocean-cloudflare.md), [ADR-0007](adr/0007-identity-workos-sessions.md)
- [ ] **Bonus check (optional):** sign up for Azure for Students; record whether the *Free services* page lists the Postgres B1MS server and VMs

**Gate G0 (go / pivot / stop)**
- [ ] Interview go-criteria met ([product-vision.md §13](product-vision.md#13-roadmap)) or buyer pivot decided
- [ ] S1–S5 results recorded; remaining `Proposed` ADRs accepted or rewritten; accepted ADRs re-checked against measurements

---

## Phase 1 — Foundation (weeks 5–8)

- [x] Batch B/C/D specs written (data model, auth/tenancy, security, API, deployment, testing) — execution briefs in [build-plan.md](build-plan.md)
- [ ] Complete scaffold per [architecture.md §4](architecture.md#4-repository-layout) (AGENTS.md, CLAUDE.md, Makefile, CI, compose already provided) — milestone M1
- [ ] CI: ruff, mypy strict, pytest, import-linter contracts, secret scan, dependency scan, frontend type-check
- [ ] `platform`: config, UUIDv7, clock, structured logging, request IDs, problem-details errors
- [ ] `identity`: WorkOS callback, server-side sessions, sign-out, session list/revoke, 18+ confirmation (FR-PLT-01)
- [ ] `tenancy`: organisations, roles, invitations (FR-PLT-02–04); RLS policies
- [ ] **Cross-tenant test suite** passing (NFR-SEC-03)
- [ ] `audit` module (FR-PLT-05)
- [ ] CI integration tests against an ephemeral Postgres + pgvector container (same image tag as production)
- [ ] **At M4: sign up for Azure for Students and deploy** (ADR-0012, Proposed); fallback: paid DigitalOcean Bangalore; set billing alerts either way
- [ ] One-box hardening (NFR-SEC-12): Cloudflare-only origin, SSH key-only, unattended upgrades, internal-only Postgres
- [ ] Sentry, telemetry, uptime checks, AI budget alerts wired (NFR-OBS-01/02, NFR-COST-04)
- [ ] `wal-g` continuous archiving + nightly dump to R2 + **first production restore drill onto a fresh server** (NFR-REL-01/02/03)
- [ ] Provision-and-restore script committed in `infra/scripts/`

**Gate G1:** tenancy tests green · deploy from `main` is one command · restore drill completed within RTO and data loss within RPO.

---

## Phase 2 — Knowledge and rules core (weeks 9–13)

- [x] Specs written: rules-engine.md, data-pipeline.md, ai-system.md, evaluation.md, rule-operations.md
- [ ] `knowledge`: source registry, ingestion CLI (fetch → parse → chunk → embed → load), versioned sources (FR-RS-01)
- [ ] Load 50–100 official sources for the MVP scope ([product-vision.md §4](product-vision.md#4-initial-scope-wedge))
- [ ] Hybrid retrieval + fusion (+ reranker if S2 justified it)
- [ ] `ai`: gateway, prompt registry, schema validation, citation verifier, cost ledger, redaction
- [ ] `rules`: JSON Schema, evaluator with unknown-value semantics and due-date logic, traces; property tests
- [ ] Rule drafting CLI (FR-RS-02); review fields enforced in CI (FR-RS-03)
- [ ] **30–50 rules drafted and CA-reviewed** — 🔒 CA reviewer
- [ ] Scenario suite (≥ 30 CA-verified companies) as CI gate (FR-RS-04)
- [ ] Golden sets for retrieval, explanation, Q&A, fact extraction

**Gate G2:** NFR-AI-01 recall gate met on scenarios · AI baselines measured and recorded in evaluation.md.

---

## Phase 3 — Product features (weeks 14–20)

- [ ] `facts`: form-first intake, optional free-text proposals, confirmation, history, "I don't know" (FR-CORE-01)
- [ ] `obligations`: evaluation on change, statuses incl. `needs_info`, calendar feed (FR-CORE-03)
- [ ] Launch Planner (FR-CORE-02)
- [ ] `explainer`: deterministic explanation (MUST) + optional AI rephrasing with verification (FR-CORE-04)
- [ ] `copilot` with routing, daily quotas, budget-exhausted path, abstention, streaming, feedback (FR-CORE-05)
- [ ] `notifications`: in-app reminders + ICS calendar feed (MUST), email + weekly digest (SHOULD), idempotent (FR-CORE-06, FR-PLT-07)
- [ ] `launchpad`: Team Space, Situation Check (questionnaire + document), Launch Roadmap, handoff (FR-LP-01–03)
- [ ] `documents`: signed uploads, extraction, private-by-default, deletion
- [ ] Data export and deletion (FR-PLT-06); disclaimer component everywhere (FR-PLT-08)
- [ ] Frontend: onboarding, obligation dashboard, calendar, explainer panel, chat, Launchpad screens; accessibility pass (NFR-UX-01)
- [ ] Astro site: landing page + one free tool ("What do I owe after incorporation?")

**Gate G3:** all MVP `MUST` requirements pass acceptance tests · performance targets checked at pilot load.

---

## Phase 4 — Hardening and pilot (weeks 21–24)

- [ ] Terms, privacy notice (sub-processors listed), disclaimers — 🔒 **lawyer review**
- [ ] Security checklist against NFR-SEC-01–09; fix all must-fix items
- [ ] Second restore drill; chaos test with AI providers blocked and with AI budget exhausted (NFR-AVL-02, NFR-COST-04)
- [ ] Light load test at pilot profile ×5
- [ ] Runbooks: deploy, rollback, restore, bad-rule revert, provider outage
- [ ] Pilot: onboard 10 design-partner companies + 1 campus cohort
- [ ] Weekly feedback review; log missed/incorrect obligations as P0 bugs

**Pilot exit criteria:** zero critical missed obligations reported · ≥ 70% of pilot companies reach "obligation plan generated" · qualitative willingness-to-pay evidence collected.

---

## Cut-lines (apply in order if behind schedule)

1. Situation Check document upload → keep questionnaire only
2. AI rephrasing in the Explainer → keep deterministic explanations
3. Free-text intake → keep the form
4. Email reminders and weekly digest → keep in-app + calendar feed
5. Copilot `interpretive` route → keep determination + explanation routes
6. Astro free tool (keep landing page)

Never cut: tenant isolation, audit log, `needs_info` handling, CA review of rules, continuous backups and restore drills, disclaimers, in-app reminders + calendar feed.

## After the pilot

v1 and v2 features follow [product-vision.md §13](product-vision.md#13-roadmap).

**Infrastructure milestones** (growth path in [architecture.md §7.2](architecture.md#72-growth-path)):
- [ ] **Month ~10 after claiming credit:** decide the post-credit home — Azure bonus (if confirmed), pay for the server (~₹1,000–2,100/month), or stage 2
- [ ] **First paying customer:** stage 2 — managed Postgres (dump/restore, connection-string change)
- [ ] **Before paid launch:** stage 4 (standby database, 2 API instances), OWASP ASVS L2 verification, external security review, billing, DPDP compliance programme ([NFR-PRV-08](nfr.md#6-privacy-and-data-protection)), and cost-model.md built from pilot measurements

## Future considerations (undecided)

- Whether to hire a part-time CA reviewer vs. revenue-share with partner CAs
- Whether to apply for incubator/startup programs for cloud credits before credits expire
