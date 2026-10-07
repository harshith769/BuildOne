# BuildOne — Status

> **Owner:** @harshith769 (Harshith, sole owner and builder) · **Updated:** 2026-10-07
> This file is the single place for current phase, decisions and the next action. Update it when a milestone or spike merges.

## Current state

- **Phase:** 0 (validation). Gate **G0 not met**.
- **Repo:** fresh start on 2026-10-05 from starter bundle v2. The earlier `harshith769/BuildOne` repo was deleted; nothing in it was lost that isn't in this bundle.
- **Code:** M1 (foundation), M2 (sign-in and sessions) and M3 (tenancy, grants, audit) done on 2026-10-06, started before G0 on purpose: M1–M3 are needed whatever the interviews show. Rules content (M6) still waits for a CA reviewer.
- **Build order (local-first, 6 Oct):** M1 ✓, M2 ✓, M3 ✓, M5, M6, M7, M8, M9, M10, M11, M12, M13, then M4 and M14 when hosting is approved. Spikes: S1 and S2 right before M5, S3 before real rules in M6, S4 before M7, S5 before M4. Detail: [roadmap.md](roadmap.md), [build-plan.md](build-plan.md).
- **Next action:** M5 (knowledge ingestion and retrieval; S1 and S2 reports done, 2026-10-07), with the interview kit in parallel. Before M5 ships: CA review of the S2 labels and the first interview questions in `evals/retrieval.jsonl`.

## Direction (Refined Plan v3, 2026-10-05)

- B2B2C. **Incubators are the first payer** (cohort licence, hypothesis ₹1–3 lakh per cohort per year after a free pilot).
- **CA firms are free** design partners and rule reviewers in Phases 1–2; a paid CA firm plan is deferred ([deferred.md](deferred.md)). No referral fees or fee-sharing of any kind (CA Act).
- Founders use the core free. Fundraise-ready pack (₹4,999–9,999) price is a hypothesis to test in interviews; **pack v0 is built in M10 regardless**. Founder Pro stays in Phase 2.
- MVP = 6 screens: smart intake; obligation plan; obligation detail (with effective date); reminders + ICS; **incubator and CA view (MUST)**; fundraise-ready pack v0 (**MUST**, built in M10 regardless). The Launch Planner keeps its own screen (M9) and Launchpad lite stays at its current priority (M11).
- Copilot → Phase 2. Situation Check → questionnaire-only lite in Phase 1; clause extraction deferred ([deferred.md](deferred.md)). Document fact extraction at intake is a stretch goal; full scope in [deferred.md](deferred.md).
- **No cut list.** Nothing is removed to save time; anything that slips moves to [deferred.md](deferred.md) with its full scope and the trigger that brings it back. Non-negotiables: incubator view, tenant isolation, audit log, `needs_info`, CA review, citations, backups and restore drills, disclaimers.

> The product docs were brought in line with this file on 2026-10-06 (session A, branch `docs/v3-local-first`). If they drift again, **this file wins**.

## Gates and dates

| Gate | Target | Criteria |
|---|---|---|
| G0 | 13 Dec 2026 | Pain confirmed (flip rule), 3 pilot letters, CA reviewer signed, spike reports S1–S4 (S5's report is an entry condition of M4, D-25) |
| G1a | ~Feb–Mar 2027 (build started 6 Oct; M1–M3 before G0, rules after a CA reviewer signs) | Local MVP complete: all MUST screens pass acceptance locally; local restore drill passes; zero critical misses on CA-reviewed scenarios |
| G1b | After M4 + M14 (hosting approved, pilot live) | Zero critical missed obligations; ≥ 60% of pilot companies generate a plan; production restore drill passes; 1 pilot converts to paid |
| G2 | end Sep 2027 | ~₹10L ARR run-rate; 20 CA firms active; incubators ready to renew |
| G3 | end of Phase 3 (Scale, Oct 2027–Sep 2028) | Customers renew and expand; 2 platform partners in active talks; ~₹60L ARR |

Phases: 0 Validate (to 13 Dec 2026) · 1 MVP (14 Dec 2026 – ~May 2027) · 2 Paid pilots (~May–Sep 2027) · 3 Scale (Oct 2027–Sep 2028; Karnataka + Maharashtra rules, LLP/OPC, Gazette change tracking, public changelog, Copilot, Benefits finder; seed round) · 4 Platform (2028+, no gate). Detail: [roadmap.md](roadmap.md).

Exam weeks: _add your semester exam dates here and leave those weeks empty._

## Decisions

| ID | Decision | Status |
|---|---|---|
| D-1 | Direction as above; sequence CAs → incubators → founders | Decided |
| D-2 | Harshith is sole owner and builder | Decided |
| D-3 | Repo: fresh `harshith769/BuildOne` from starter bundle v2 (old repo deleted) | Decided |
| D-4 | Copilot in Phase 2 | Decided |
| D-5 | Situation Check questionnaire-only lite in Phase 1 | Decided |
| D-6 | "K Capital" = most likely Kae Capital; park until a live cohort | Decided |
| D-7 | Prices to test: incubator ₹1–3L/cohort; pack ₹4,999–9,999; CA free; Pro later | Decided |
| D-8 | Spike outcomes (parser, embeddings, `D`, reranker, τ, σ, models) | Parser decided by S1 (partial pass: PyMuPDF + heuristic, Tesseract for scans with review below confidence 93, stdlib HTML; Docling rejected; [report](spikes/S1-parsing.md)). Embeddings decided by S2: `bge-base-en-v1.5` int8, `D = 768`, vector-only ranking + query glossary, no reranker, τ deferred (D-30; [report](spikes/S2-retrieval.md)). σ and models open — S4 |
| D-9 | `superseded` rule-version status | Open — recommend yes; decide at M6 |
| D-10 | Final fact list, incl. small-company thresholds as versioned facts | Open — S3 with CA |
| D-11 | Email provider | Open — M8 |
| D-12 | Personal repo, not an org (no gitleaks licence needed) | Decided |
| D-13 | Ruleset: block force push and deletion, require PR (0 approvals), require up-to-date branches, required checks | Decided — set up at repo creation |
| D-14 | Hosting credit: DigitalOcean Pack credit ended 1 Aug 2026 → ADR-0012 (Azure for Students, Proposed) | Decided to replace; host decided by S5 |
| D-15 | Incorporation after G0, or earlier if a pilot needs an invoice | Open — G0 |
| D-16 | CA reviewer: free firm plan + public credit; advisor equity only after incorporation, lawyer-drafted | Open — Phase 0 |
| D-17 | CA firm plan free in Phases 1–2; paid CA plan deferred ([deferred.md](deferred.md)) | Decided 2026-10-06 |
| D-18 | Founder Pro stays in Phase 2 | Decided 2026-10-06 |
| D-19 | Fundraise-ready pack v0 is built in M10 regardless (MUST); its price stays a hypothesis | Decided 2026-10-06 |
| D-20 | Launch Planner keeps its own screen (M9) | Decided 2026-10-06 |
| D-21 | Document fact extraction at intake is a stretch goal; full scope in [deferred.md](deferred.md) | Decided 2026-10-06 |
| D-22 | No cut list; deferred work keeps its full scope in [deferred.md](deferred.md); never remove, shrink or change a feature or the business model without the owner's explicit OK (AGENTS.md rule 19) | Decided 2026-10-06 |
| D-23 | Local-first build order: M1, M2, M3, M5–M13, then M4 and M14 when hosting is approved. S1 + S2 before M5, S3 before real rules in M6, S4 before M7, S5 before M4 | Decided 2026-10-06 |
| D-24 | G1 split into G1a (local MVP complete) and G1b (the original G1 criteria, after M4 + M14); G3 defined | Decided 2026-10-06 |
| D-25 | G0 requires spike reports S1–S4; S5's report becomes an entry condition of M4 (option a) | Decided 2026-10-06 |
| D-26 | Phase 0 interview targets: 30 founders, 10 CAs, 3 incubators, plus 1 CA reviewer and 1 lawyer; ~10 pre-founders optional. Pilot (M14) = one incubator cohort (10–20 companies) + 2–3 CA firms | Decided 2026-10-06 |
| D-27 | Founder Pro price hypothesis ₹1,499–2,499/yr (refines D-7 "Pro later") | Decided 2026-10-06 |
| D-29 | `manage` access grants reserved: a valid scope, but the DB write check never accepts any grant and the API refuses to create `manage` (422 `grant_scope_not_available`); write scope decided with the CA Workspace via an ADR ([deferred.md §12](deferred.md)) | Decided 2026-10-06 (M3) |
| D-30 | Retrieval after S2 ([ADR-0014](adr/0014-retrieval-query-glossary-and-vector-only-ranking.md), Accepted): query abbreviations expanded from the versioned `knowledge/query-glossary.yaml`; vector-only ranking in the MVP (frozen AND lexical step found 6%; the owner's idf5 OR variant lost one question); query embedder in a sidecar process; τ not gated in the MVP, calibrated on held-out interview questions before the Copilot ([deferred.md §13](deferred.md)) | Decided 2026-10-07 (S2) |
| D-28 | No user row before 18+ and terms acceptance: a new user's verified profile waits in a signed 30-minute cookie; under-18 stores nothing. `identity.users.age_confirmed_at` stays `NOT NULL` ([auth-and-tenancy.md §1](auth-and-tenancy.md)) | Decided 2026-10-06 (M2) |

## Carry-forward notes

- **M3 membership check — solved** by [ADR-0013](adr/0013-rls-check-functions-and-read-write-split.md): check functions owned by `app_rls_check` (NOLOGIN, BYPASSRLS). **S5 must confirm** the managed host's admin can create that role; otherwise apply ADR-0013's fallback.
- **M10 (share screens):** an unverified organisation can call itself an incubator (or CA firm) and ask companies to share. The share/accept screen must show clearly who is asking (name, type, who created it, when) before a founder accepts.
- **M8:** every company-data table uses `app.platform.rls.company_data_policies()`; the schema guard fails on any table it can't classify.
- **Before M6 (labour law changed; no feature change):** the Code on Social Security, 2020 is in force from 21 Nov 2025 (S.O. 5319(E); [PIB](https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2192463)) and subsumes the ESI Act 1948 and the EPF & MP Act 1952; the EPF Scheme, 2026 (G.S.R. 525(E), 29 Jun 2026, in force on Gazette publication) supersedes the EPF Scheme 1952. Section 164 (repeal and savings) commenced only in part, so the CA must confirm which provisions of the old Acts still apply. Before rules are drafted in M6, check every doc that mentions PF/ESI (today: product-vision.md §4 wedge "threshold-based labour (PF/ESI)" and §6.3 A2 "review PF/ESI") and every PF/ESI rule and fact against the Code and the 2026 Scheme. Found during spike S1 (2026-10-06).

## Stack versions (checked 2026-10-05)

Python 3.14 · FastAPI 0.142 · Pydantic 2.13 · SQLAlchemy 2.1 · Alembic 1.20 · psycopg 3.3 · Procrastinate 3.10 · PostgreSQL 18 + pgvector 0.8.7 (`pgvector/pgvector:0.8.7-pg18-trixie`) · wal-g 3.0.9 (SHA-256 pinned) · uv 0.12 · ruff 0.16 · mypy 2.4 · Node 24 LTS · pnpm · Vite 8 · React 19 · Tailwind 4 · TanStack Router/Query · **TypeScript 6.0** (not 7: typescript-eslint supports < 6.1) · Playwright 1.63 · Astro 7. CI actions: checkout v7, setup-uv v10, setup-node v7, pnpm/action-setup v6, gitleaks-action v3 (all on the Node 24 runtime).

## Contradictions from the old repo

| ID | Status |
|---|---|
| C1 owner handle | Fixed in bundle v2 |
| C2 team model | Fixed: one developer (this file) |
| C3 Python 3.13 vs 3.12 tooling | Fixed: 3.14 everywhere |
| C4 `superseded` status | = D-9 |
| C5 spike order | Superseded by D-23/D-25: S1, S2 before M5; S3 before real rules in M6; S4 before M7 (S1–S4 by G0); S5 before M4 |
| C6 `.env` location | Canonical: `infra/compose/.env` |
| C7 `app/tools/export_openapi` missing | Fixed in M1 |
| C8 CI file drift | Fixed: single `ci.yml` with a `detect` job |
| C9 old pricing in repo docs | Fixed in session A (2026-10-06); superseded prices kept for history in product-vision.md §9.5 |
| C10 entity counts | Always quote with their base |
| C11 SISFS | Closed to new applications (31 May 2026) |

## Lessons learned (keep)

1. Work in the WSL2 Linux filesystem (`~/code/BuildOne`), never OneDrive.
2. `.gitattributes` forces LF; keep it.
3. `.env` lives only at `infra/compose/.env`, recreated per machine from `.env.example`, never committed.
4. `hashFiles()` is not allowed in `jobs.<id>.if` → the `detect` job pattern.
5. gitleaks-action on PRs in a private repo needs job-level `contents: read, pull-requests: read`; organisations also need `GITLEAKS_LICENSE`.
6. Required checks block direct pushes → always branch → PR → merge. Skipped jobs count as passing.
7. Free tiers change without notice (Oracle in June 2026, DigitalOcean Pack credit in August 2026) → portability rules and re-checks at each milestone.
8. SSH keys need passphrases and `ssh-agent`.
9. Postgres 18 images mount at `/var/lib/postgresql`.
10. `astral-sh/setup-uv` publishes no floating major tag (`@v10` fails); pin a full version such as `@v10.2.0`.
11. gitleaks-action fails on the very first push of a new repo (it scans `<root>^..HEAD`); later pushes and PRs scan normally.
12. MinIO removed its images from Docker Hub (Sep 2026). Local and CI S3 now use SeaweedFS (`chrislusf/seaweedfs:4.48`, `weed mini`). Pin image tags, and consider a registry mirror if another image disappears.

## Log

| Date | Event |
|---|---|
| 2026-10-07 | S2 (retrieval) report: 50 founder questions + 10 out-of-scope over 904 real chunks. `bge-base-en-v1.5` int8 (`D = 768`) + query glossary, vector-only: recall@10 94%, p95 2.6 ms at 50k chunks (1-vCore 2 GiB Postgres), query embedder 269 MiB / p95 21 ms. Without the glossary the best is 84%; rerankers 1.2–2.6 GiB and 1.8–11 s per query; τ not calibratable, deferred. ADR-0014 Accepted. Owner spot check not done; CA review of labels pending |
| 2026-10-07 | S1 (parsing) report: partial pass on 21 official sources. Born-digital PyMuPDF + layout heuristic: 99.4% recall, 97.7% precision, 0 order errors, 97 MB. Scans: 48.7% recall, 4.3% CER, so they go to manual review (page confidence < 93). Docling rejected (3.19 GB, OOM under a 2 GB cap). India Code returned 504: the Code on Social Security came from the Gazette, the Telangana Acts from official HTML; one CBIC notification is missing |
| 2026-10-06 | M3 done: organisations, memberships (last-owner trigger), invitations (token in fragment and body, link once), access grants (company → CA firm/incubator, either side initiates, read-only at the DB), audit log, idempotency keys, hourly session and idempotency sweepers, identity audit events, screens S3/S4 + invite page + org switcher; ADR-0013 (check functions owned by `app_rls_check`, read/write policy split); D-29; cross-tenant suite at the DB and over every org endpoint; 310 backend tests and 9 E2E tests green |
| 2026-10-06 | M2 done: identity seam (fake + WorkOS adapters), sign-in with PKCE + state, server-side sessions (hash only, 30 d idle / 90 d absolute, rotation), CSRF double-submit + Origin check, 18+ and terms consent with no user row before acceptance (D-28), `/v1/me`, sessions list/revoke, screens S1/S2; 132 backend tests and 7 E2E tests green. Local test DB access via the `buildone_test` role (`make test-role`, local dev only, never CI or hosted) so `infra/compose/.env` is never read |
| 2026-10-06 | Session A: docs brought in line with this file; owner decisions D-17…D-27 recorded; local-first build order; [deferred.md](deferred.md) created; AGENTS.md rule 19 |
| 2026-10-06 | M1 done: platform kernel, health checks, baseline migration, worker, RLS and extension gates, frontend skeleton with generated client; 43 backend tests and 4 E2E tests green |
| 2026-10-05 | Fresh start: starter bundle v2 created (stack re-verified, CI rebuilt, ADR-0012 proposed) |
