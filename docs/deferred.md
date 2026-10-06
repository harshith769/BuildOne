# BuildOne — Deferred Work

> **Status:** v1.0 · 2026-10-06 · Owner: @harshith769
> Decisions: [status.md](status.md) (D-4, D-5, D-17…D-23). Rule: nothing is cut; deferred work keeps its **full scope** here until a trigger brings it back ([AGENTS.md rule 19](../AGENTS.md)).

**What this document answers**
- Which features and infrastructure are deferred, and why
- The full scope of each, so nothing is lost while it waits
- The trigger that brings each one back, and where its detailed spec lives

Acceptance criteria stay in their owning docs ([requirements.md](requirements.md), [data-model.md](data-model.md), [deployment.md](deployment.md)); this file holds scope, the trigger, and anything that has no other home (such as the former M10 Copilot brief).

When an item comes back: move it into the build order in [roadmap.md](roadmap.md) and [build-plan.md](build-plan.md), record the decision in [status.md](status.md), and mark the item here as **Scheduled** (do not delete it until it ships).

---

## Summary

| # | Item | Deferred because | Trigger to bring it back | Status |
|---|---|---|---|---|
| 1 | M4 production hosting | Local-first build (D-23); hosting not yet approved | S5 report passes (M4 entry condition, D-25) **and** owner approves a host from ADR-0012 | Deferred |
| 2 | M14 live pilot | Needs M4 | M4 done, G1a passed, lawyer-reviewed terms in place | Deferred |
| 3 | Production R2 buckets and backups | Only needed with a production database | Start of M4 | Deferred |
| 4 | Domain and DNS | Only needed for a public deployment | Start of M4 (or earlier if the marketing site or waitlist must go public) | Deferred |
| 5 | Production Sentry | No production to observe | Start of M4 | Deferred |
| 6 | Billing (Razorpay) | No paying customer yet | First pilot ready to pay (G1b) or start of Phase 2 | Deferred |
| 7 | Copilot | D-4: Phase 2 | Start of Phase 2 | Deferred |
| 8 | Situation Check clause extraction | D-5: questionnaire-only lite in Phase 1 | Phase 2, after S4 shows clause extraction meets the quality gates and the lawyer reviews the wording | Deferred |
| 9 | Document fact extraction at intake | D-21: stretch goal | Time left after M7/M8 MUST scope, or start of Phase 2 | Stretch |
| 10 | Paid CA firm plan | D-17: CA firms free in Phases 1–2 | End of Phase 2 (owner decision), or earlier only with the owner's explicit OK | Deferred |
| 11 | Founder Pro | D-18: Phase 2 | Start of Phase 2 | Deferred |

---

## 1. M4 — Production hosting (one-box)

**Why deferred:** the build is local-first (D-23). The DigitalOcean Student Pack credit ended on 1 Aug 2026; the replacement host is still Proposed ([ADR-0012](adr/0012-hosting-after-student-pack-change.md)). Azure for Students' 12 free months start at signup, so signing up early wastes them.

**Full scope** (former M4 brief, unchanged):
- **Read:** deployment.md, security-design.md §3–4, ADR-0006, ADR-0012, NFR-SEC-12.
- **Build:** `infra/scripts/provision.sh`; hardened server (Cloudflare-only origin, SSH key-only, unattended upgrades, internal-only Postgres); Caddy with Cloudflare-only origin; deploy workflow (`.github/workflows/deploy.yml`) with rollback; wal-g continuous archiving + nightly dumps to R2 (or the managed provider's point-in-time restore under ADR-0012 option A); restore script; Sentry wiring; ops-check job; telemetry, uptime checks, AI budget alerts (NFR-OBS-01/02, NFR-COST-04); billing alerts on the host account; runbooks `deploy-and-rollback`, `restore`, `server-hardening-and-patching`.
- **Done when:** deploy from `main` works end to end; **restore drill onto a fresh server** meets RPO ≤ 15 min and RTO ≤ 4 h (recorded).
- **Host options** ([ADR-0012](adr/0012-hosting-after-student-pack-change.md), checked 2026-10-05):
  - **A. Azure for Students, Central India (proposed):** API + worker in Docker Compose on a B2ats v2 VM (2 vCPU, 1 GiB); PostgreSQL 18 on Flexible Server B1MS (2 GiB, 32 GB); files and nightly `pg_dump` in Cloudflare R2. ₹0 for 12 months. Managed Postgres has no superuser: roles, grants and extensions (`vector`, `pg_trgm`, `citext`) come from plain SQL run by the admin role. 1 GiB RAM means one Uvicorn worker, a lean job worker and no embedding model in a long-running process.
  - **B. DigitalOcean Bangalore, paid (fallback):** the original ADR-0006 one-box design without the credit; confirm price at checkout and record it in ADR-0012.
  - Rejected: Hetzner (no India region, prices up after 15 Jun 2026); Oracle Always Free (allowance cut June 2026, idle reclaim).
- **Before M4, spike S5 must show** (ADR-0012 items 1–4): API + worker within ~900 MiB; `initdb` SQL runs without superuser rights; nightly `pg_dump` to R2 and restore into a fresh Postgres 18 both work and are timed; the Azure *Free services* page lists the VM sizes and Flexible Server B1MS for the owner's student account. If any item fails, choose B.

**Trigger:** S5 report written and passing (an M4 entry condition, D-25), and the owner approves a host. M4 then runs after M13 and before M14.

## 2. M14 — Live pilot

**Why deferred:** needs a production host (M4).

**Full scope** (former M14 brief + roadmap pilot items):
- Pilot onboarding checklist; read-only metrics views (`app_readonly`); feedback triage routine.
- Onboard one incubator cohort (10–20 companies) + 2–3 CA firms (D-26).
- Weekly feedback review; log missed or incorrect obligations as P0 bugs.
- Exit = **G1b**: zero critical missed obligations; ≥ 60% of pilot companies generate a plan; production restore drill passes; 1 pilot converts to paid.

**Trigger:** M4 done, G1a passed, lawyer-reviewed terms and privacy notice in place 🔒, CA reviewer signed.

## 3. Production R2 buckets and backups

**Full scope:**
- Production buckets and scoped API tokens (files, backups) alongside the existing dev buckets `buildone-files-dev`, `buildone-sources`, `buildone-backups-dev` ([build-plan.md §3](build-plan.md#3-owner-setup-manual)).
- Continuous WAL archiving with wal-g (option B) or the provider's point-in-time restore (option A), plus a nightly `pg_dump` to R2 in both cases ([deployment.md](deployment.md), [ADR-0010](adr/0010-object-storage-r2.md)).
- Provision-and-restore script in `infra/scripts/`; `restore.md` runbook and `restore-log.md`.
- First production restore drill onto a fresh server (NFR-REL-01/02/03); second drill in M13 (local drills happen before then).
- Re-evaluate: India-pinned storage requirement → Cloudflare R2 to an India-region bucket (ADR-0010).

**Trigger:** start of M4.

## 4. Domain and DNS

**Full scope:**
- Cloudflare account + domain (Student Pack domain offer or an existing domain).
- Cloudflare DNS, CDN, firewall and TLS in front of the server; Cloudflare-only origin (NFR-SEC-12).
- Cloudflare Pages for both frontends (SPA and Astro marketing site) ([ADR-0006](adr/0006-hosting-digitalocean-cloudflare.md) edge decisions still stand).
- WorkOS production redirect URI on the real domain; email sending domain records (SPF/DKIM/DMARC) once the email provider is chosen (D-11).

**Trigger:** start of M4, or earlier if the owner wants the marketing site / waitlist public before the pilot.

## 5. Production Sentry

**Full scope:** production Sentry project for API, worker and SPA; release tracking from the deploy workflow; PII scrubbing (no document contents, no full `/v1/calendar/` URLs); alert routing to email; error-budget review in the M13 checklist (NFR-OBS-01/02).

**Trigger:** start of M4. (Local development does not need Sentry.)

## 6. Billing (Razorpay)

**Full scope:**
- `billing.*` tables (subscriptions, entitlements) reserved in [data-model.md §5](data-model.md#5-reserved-for-v1-design-fixed-now-created-by-additive-migrations-later).
- Payment provider: Razorpay (handoff plan); UPI AutoPay or invoice; annual plans; founding-customer discount for the first 10 incubators/CA firms; **no percentage of anyone's professional fees**.
- Products to bill: incubator cohort licence, fundraise-ready pack (one-off), Founder Pro (Phase 2), paid CA firm plan (if approved, §10).
- `billing.md` and `cost-model.md` (planned docs, [docs/README.md](README.md)); GST invoicing needs incorporation first (D-15).
- Payment-provider SDK only in its adapter module (AGENTS.md rule 6).

**Trigger:** the first pilot ready to pay (G1b) or the start of Phase 2, whichever comes first.

## 7. Copilot (Phase 2)

**Why deferred:** D-4. The deterministic plan and explainer cover "what do I owe" and "why" without AI.

**Full scope:**
- Requirements: [FR-CORE-05](requirements.md#fr-core-05-founder-copilot-c5--later-phase-2) (all acceptance criteria kept there): streaming chat scoped to the org; routes `determination`, `explanation`, `what_if`, `interpretive`, `out_of_scope`; cited interpretive answers; abstention below the confidence threshold; feedback; per-org daily quota; `limit_reached` path; minimal facts to providers.
- Former **M10 — Copilot** brief:
  - **Read:** requirements.md FR-CORE-05, architecture.md §5.3, ai-system.md, api-conventions.md §5, ux-screens.md S14.
  - **Build:** conversations/messages, routing, determination route (no generation of facts), interpretive route with retrieval + abstention, SSE streaming, verification, quotas, feedback; screen S14.
  - **Done when:** Copilot eval meets NFR-AI-02/03/04 on the on-demand set; `limit_reached` path covered by E2E.
- Data: `copilot.conversations`, `copilot.messages` ([data-model.md §4.9](data-model.md#49-copilot-explainer)); AI tasks `copilot_route`, `copilot_answer` ([ai-system.md](ai-system.md)); golden set `evals/copilot.jsonl` ([evaluation.md](evaluation.md)); NFR-PERF-05, NFR-COST-02.
- Phase 3 continues Copilot work (G3 scope in [roadmap.md](roadmap.md)).

**Trigger:** start of Phase 2.

## 8. Situation Check clause extraction (document check)

**Why deferred:** D-5. Phase 1 ships the questionnaire-only lite.

**Full scope:**
- Requirements: the "Document check (AI-assisted)" part of [FR-LP-02](requirements.md#fr-lp-02-situation-check-l2--must-questionnaire--later-document-check) (all acceptance criteria kept there): upload own employment contract or university policy (PDF/DOCX ≤ 10 MB); extract clauses (IP assignment, outside activities, non-compete / non-solicit, confidentiality, notice period) with page/section and plain-language explanation; never says "permitted / not permitted"; low-confidence → "could not be reliably identified"; private to the uploader by default, opt-in team summary, hard delete; document content treated as data; daily budget and `limit_reached`.
- Build (from the former M11 brief): `documents` module, signed upload URLs, clause extraction job with privacy defaults; screen S7 upload half.
- Data: `documents.documents`, `documents.clause_findings` with the extra visibility RLS predicate ([data-model.md §4.10](data-model.md#410-documents-launchpad)).
- Done when: document privacy enforced by RLS tests; extraction golden set meets NFR-AI-04; lawyer-reviewed wording.

**Trigger:** Phase 2, after S4 shows clause extraction meets the quality gates and the lawyer reviews the wording.

## 9. Document fact extraction at intake (stretch)

**Why deferred:** D-21 (stretch goal, not removed).

**Full scope:**
- Founder uploads incorporation documents (Certificate of Incorporation, MoA, PAN); AI extracts **proposed facts**, each with the excerpt it came from; the founder confirms, edits or rejects them in the proposals review (S10). Proposals never reach the rules engine until confirmed (AGENTS.md rule 9).
- Uses the `documents` upload path (signed URLs, size and type limits), `facts.fact_proposals` (`origin = 'ai_extraction'`), the AI gateway with a `user_data` task routed only to providers with `user_data_allowed: true`, and the daily budget (hidden when spent; the form always works).
- Build slots: extraction task in M7, upload + proposals UI in M8.
- Done when: extraction golden set meets NFR-AI-05; no proposal is used in computation before confirmation (test).

**Trigger:** time left after the M7/M8 MUST scope, or the start of Phase 2.

## 10. Paid CA firm plan

**Why deferred:** D-17. CA firms are free design partners and rule reviewers in Phases 1–2.

**Full scope** (handoff hypothesis, not confirmed): multi-client workspace, client event feed, auto-chasing of missing facts, client-facing "why" view, review/sign-off and staff task assignment (A1–A3), later a white-label portal (A4); flat per-firm monthly price (hypothesis ₹999–2,999 per firm per month) so there is no per-client fee and no fee-sharing.

**Trigger:** owner decision at the end of Phase 2; never earlier without the owner's explicit OK.

## 11. Founder Pro (Phase 2)

**Why deferred:** D-18.

**Full scope:** Event Triggers, What-if Simulator, Evidence Vault, Compliance Health Score, full Due-Diligence Pack, Change Radar (when built), WhatsApp reminders, unlimited Copilot, 3 seats ([product-vision.md §9](product-vision.md#9-business-model)). Price hypothesis ₹1,499–2,499/year (D-27).

**Trigger:** start of Phase 2.

---

## 12. `manage` grant write scope

**Why deferred:** D-29 (2026-10-06, M3). `manage` stays a valid access-grant scope in the schema (no CHECK forbids it), but the database write check never accepts any grant, whatever its scope, and the API refuses to create a `manage` grant (422 `grant_scope_not_available`, "This access level isn't available yet"). An existing `manage` grant reads exactly like `read`.

**Full scope:** manage grant write scope — CA Workspace (A2 client event feed, A3 review/sign-off/staff tasks). Needs an ADR before enabling. Open question for the CA interviews: may a CA firm change the company's own data (facts, obligations), or only its own workflow data on the client, with changes to company data going to the founder as suggestions to approve?

**Trigger:** the CA Workspace milestone (Phase 2), after the CA interviews answer the open question; an ADR comes first ([ADR-0013](adr/0013-rls-check-functions-and-read-write-split.md)).

---

## Other later features

Features tagged v1/v2 in [product-vision.md §6](product-vision.md#6-features) and `LATER` in [requirements.md](requirements.md) (Founder Alignment, Validation Sprint, Opportunity Finder, Connect, Event Triggers, What-if, Evidence Vault, Health Score, full DD Pack, Change Radar, change-detection queue, CA Workspace, incubator portfolio view) keep their scope in those documents and come back by phase ([roadmap.md](roadmap.md)).
