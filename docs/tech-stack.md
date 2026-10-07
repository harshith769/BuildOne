# BuildOne — Technology Stack

> **Status:** v0.2 · 2026-09-28 · Owner: @harshith769
> **Constraints:** solo developer · Python-first · **₹0 MVP** · production-grade engineering · **verified-only critical path** (nothing essential depends on an unverified free-tier offer). Each choice links to its ADR.

**What this document answers**
- Which technology is used for each layer, and why (via ADR links)
- Which choices are still open and which spike resolves each
- How the MVP runs at ₹0, what it costs afterwards, and what is merely a bonus
- Which technologies are deliberately deferred, and what triggers adopting them

---

## 1. Principles

1. **Boring by default.** One datastore (Postgres), one backend language (Python), one deployable backend (modular monolith).
2. **Verified-only critical path.** Unverified free offers (e.g., Azure student 12-month services) are optional bonuses, never dependencies.
3. **Portable at every boundary.** Standard Postgres, Docker, S3 API, OIDC, one AI gateway — growth is configuration, not rewrite ([ADR-0011](adr/0011-portability-rules.md)).
4. **No AI on the critical path.** Obligations, calendar, reminders, and the default Explainer work with every AI provider offline ([NFR-AVL-02](nfr.md#2-availability-and-reliability)).
5. **Never auto-spend.** When a free limit is reached, features degrade; nothing silently switches to paid ([ADR-0008](adr/0008-llm-gateway-provider-agnostic.md)).
6. **Buy commodity, build the moat.** Identity, storage, email, error tracking are bought (free tiers). Rules engine, retrieval, evaluation are built.

---

## 2. Stack

| Layer | Choice | ADR |
|---|---|---|
| Architecture style | Modular monolith (API process + worker process, one codebase) | [0001](adr/0001-modular-monolith.md) |
| Backend | Python 3.14 (fallback 3.13), FastAPI, Pydantic v2, Uvicorn | [0002](adr/0002-python-fastapi-backend.md) |
| Data access | SQLAlchemy 2.1 + psycopg 3; Alembic migrations reviewed as SQL | [0002](adr/0002-python-fastapi-backend.md) |
| Datastore (MVP) | PostgreSQL 18 + `pgvector` 0.8.7 (official `pgvector/pgvector:0.8.7-pg18-trixie` image), self-hosted or managed (see [ADR-0012](adr/0012-hosting-after-student-pack-change.md)); full-text search; Row-Level Security | [0003](adr/0003-postgres-single-datastore.md) |
| Datastore (stage 2) | Managed PostgreSQL (dump/restore + connection-string change) | [0003](adr/0003-postgres-single-datastore.md) |
| Backups | Self-hosted: `wal-g` v3.0.9 continuous WAL archiving + nightly `pg_dump` → Cloudflare R2. Managed (if ADR-0012 is accepted): the provider's point-in-time backups + nightly `pg_dump` → R2 as the exit path | [0003](adr/0003-postgres-single-datastore.md), [0010](adr/0010-object-storage-r2.md) |
| Background jobs | Procrastinate (Postgres-backed queue, periodic tasks) | [0004](adr/0004-postgres-job-queue.md) |
| Frontend (app) | React + TypeScript + Vite SPA; TanStack Router + Query; Tailwind + shadcn/ui; client generated from OpenAPI | [0005](adr/0005-frontend-react-spa-astro.md) |
| Frontend (marketing + free tools) | Astro (static) | [0005](adr/0005-frontend-react-spa-astro.md) |
| Hosting (MVP) | **Proposed:** Azure for Students (Central India): API + worker on a small VM with Docker Compose, PostgreSQL on Azure Flexible Server B1MS. Fallback: one-box DigitalOcean Bangalore, paid. Decided by S5 | [0012](adr/0012-hosting-after-student-pack-change.md) (supersedes the credit assumption in [0006](adr/0006-hosting-digitalocean-cloudflare.md)) |
| Edge | Cloudflare DNS, CDN, firewall, TLS; Cloudflare Pages for both frontends | [0006](adr/0006-hosting-digitalocean-cloudflare.md) |
| Identity | WorkOS AuthKit → server-side sessions; authorization in-house; fallback: direct Google OIDC (Authlib) | [0007](adr/0007-identity-workos-sessions.md) |
| AI with user data | Groq free-tier open-weight models, **Zero Data Retention enabled**, via in-house gateway with hard daily budget | [0008](adr/0008-llm-gateway-provider-agnostic.md) |
| AI with public text only | Gemini free tier (rule drafting from official sources) | [0008](adr/0008-llm-gateway-provider-agnostic.md) |
| Explanations | **Deterministic by default** (rule trace + CA-approved summary + citations); AI rephrasing optional | [0009](adr/0009-rules-as-code.md) |
| Embeddings | Small open-source embedding model running locally on the one-box (exact model chosen in spike S2) | [0003](adr/0003-postgres-single-datastore.md) |
| Rules | YAML in git, JSON Schema, custom Python evaluator, published to Postgres | [0009](adr/0009-rules-as-code.md) |
| Object storage | Cloudflare R2 via S3 API, private buckets, signed URLs | [0010](adr/0010-object-storage-r2.md) |
| Reminders | In-app notifications + private calendar feed (ICS) as primary; email as secondary channel | [requirements.md FR-CORE-06](requirements.md#fr-core-06-reminders-c6--must) |
| CI/CD | GitHub Actions (tests against ephemeral Postgres + pgvector container) → GitHub Container Registry → deploy to one-box | [deployment.md](deployment.md) |
| Error tracking | Sentry free tier | [deployment.md §6](deployment.md#6-observability-at-0) |
| Uptime | Free external uptime checker (1-min interval) | [deployment.md §6](deployment.md#6-observability-at-0) |
| Email | Free tier of a transactional provider (Resend, Brevo, or Amazon SES) — chosen at implementation after checking limits | integrations.md (planned, M8) |
| Portability enforcement | `import-linter` contracts + allowed-extension check in CI | [0011](adr/0011-portability-rules.md) |
| Later | Razorpay (billing), WhatsApp Cloud API, OpenTofu (IaC) | billing.md / integrations.md / deployment.md (planned) |

### Developer tooling

`uv` · `ruff` · `mypy --strict` · `pytest` + `hypothesis` · `import-linter` · `pre-commit` · `pnpm` + `eslint` + `tsc --strict` · Docker Compose (local = production topology).

---

## 3. Open decisions (resolved by spikes)

| Decision | Candidates | Resolved by | Criteria |
|---|---|---|---|
| Document parser | ~~Docling~~ · PyMuPDF · Tesseract OCR | **Decided by [S1](spikes/S1-parsing.md) (partial pass):** PyMuPDF text layer + layout heuristic for born-digital PDFs; Tesseract 5 (`eng`/`eng+hin`, 300 dpi) for pages without a text layer, with manual review below mean word confidence 93; stdlib `html.parser` for official HTML. Docling rejected (3.19 GB peak, OOM under a 2 GB cap; merges Gazette pages) | Structure fidelity on 20 real sources; OCR on scans; RAM on 2 GB |
| Embedding model | Small open-source models runnable on CPU within the one-box RAM budget | Spike S2 | Recall@10 ([NFR-AI-06](nfr.md#7-ai-quality-gates)), latency, RAM |
| Reranker | None (fusion only) · small CPU cross-encoder | Spike S2 | Quality gain vs latency and RAM |
| Groq models per task | Open-weight models available on the Groq free plan | Spike S4 | Faithfulness, citation precision, tokens per task |
| Email provider | Resend · Brevo · Amazon SES | At implementation | Free-tier limits, Indian inbox deliverability |

---

## 4. Budget

**MVP target: ₹0/month** ([NFR-COST-01](nfr.md#9-cost)).

### 4.1 What runs free, and on what basis

| Item | Cost | Basis |
|---|---|---|
| Local development (weeks 1–8) | ₹0 | Your machine |
| Production host | ₹0 for 12 months (proposed) | **The DigitalOcean Student Pack credit ended: redemption closed 31 Jul 2026 and all credits expired 1 Aug 2026** ([GitHub Community](https://github.com/orgs/community/discussions/201240)). Proposed: Azure for Students free services ([ADR-0012](adr/0012-hosting-after-student-pack-change.md)). Fallback: paid DigitalOcean Bangalore — confirm price at checkout |
| Postgres, worker, embeddings | ₹0 | Same server (self-hosted) or Azure Flexible Server B1MS (managed, ADR-0012); embeddings may run as a CLI on the laptop if RAM is short |
| Cloudflare DNS/CDN/Pages | ₹0 | Static assets on Pages are free ([Makerkit calculator](https://makerkit.dev/pricing-calculator/cloudflare)) |
| Cloudflare R2 (files + backups) | ₹0 up to 10 GB | [Filebase R2 guide](https://filebase.com/blog/cloudflare-r2-pricing-costs-savings-and-alternatives-in-2026/) |
| WorkOS AuthKit | ₹0 up to 1,000,000 MAU | [Clerk comparison citing WorkOS pricing](https://clerk.com/articles/clerk-pricing-explained) |
| Groq (user-data AI) | ₹0 within free limits | Sample limits: 30 req/min, 1,000 req/day, 200,000 tokens/day per model ([BenchLM](https://benchlm.ai/md/free-tier/groq.md)); console is authoritative |
| Gemini (public-text AI only) | ₹0 within free limits | Free tier; content used to improve Google products → public text only |
| Sentry, uptime, email | ₹0 | Free tiers at pilot volume — confirm each at signup |
| Domain | ₹0 for year 1 | Student Pack domain offers ([GitHub Education](https://education.github.com/pack)) |

### 4.2 AI capacity plan (estimate — measure in spike S4)

- Copilot prompts capped at ~4k tokens (top-5 chunks + instructions) → ~50 questions/day per Groq model; two models → ~100/day.
- Default Explainer uses **no AI**; free-text intake and rephrasing are optional and skipped when the daily budget is spent.
- Situation Check clause extraction (~10k tokens per contract) is rare; counts against the same daily budget.

### 4.3 Timeline

| Period | Cost | Action |
|---|---|---|
| Until M4 | ₹0 | Local only. Do **not** sign up for Azure for Students yet: its 12 months of free services start at signup |
| M4 → +12 months | ₹0 (proposed) | Sign up for Azure for Students, deploy the pilot (ADR-0012) |
| Month ~10 after M4 | — | Decide: renew student benefits if still enrolled, pay for a server, or stage 2 |
| Paid launch | Measured | Budget from cost-model.md (written after the pilot), built on measurements |

### 4.4 Azure for Students (now the proposed primary host, ADR-0012)

- **Azure for Students:** $100 credit, no card, and — per Microsoft's page — 12 months of free services including a managed Postgres B1MS server and small VMs ([Azure for Students](https://azure.microsoft.com/en-in/free/students)). Confirm eligibility on the portal's *Free services* page; if confirmed, use for staging or as the month-12 landing spot.

### 4.5 Known cost step-ups (stages in [architecture.md §7.2](architecture.md#72-growth-path))

| Step-up | When | Approximate cost |
|---|---|---|
| 4 GB server | Sustained memory pressure | ~$24/month on the paid fallback; hosting terms in [ADR-0012](adr/0012-hosting-after-student-pack-change.md) |
| Managed Postgres (stage 2) | First paying customer | ~$15/month smallest node ([DO pricing guide](https://github.com/baafxc4/digitalocean-postgresql-pricing)) |
| Paid AI overflow | Daily cap regularly hit — explicit owner decision | Claude Haiku 4.5 $1/$5 or Gemini 3.1 Flash-Lite $0.25/$1.50 per 1M tokens ([Anthropic](https://platform.claude.com/docs/en/about-claude/pricing), [Costgoat](https://costgoat.com/pricing/gemini-api)) |
| HA standby database (stage 4) | Paid-launch 99.9% target | Roughly doubles database cost ([DO pricing guide](https://github.com/diudllkq/digitalocean-postgresql-comparison)) |

---

## 5. Deliberately deferred technologies

| Technology | Why not now | Adopt when (trigger) |
|---|---|---|
| Managed Postgres | ₹0 MVP; one-box with continuous backup is sufficient for pilot | Stage 2 triggers in [ADR-0003](adr/0003-postgres-single-datastore.md) |
| Permanent staging server | RAM/cost; CI uses ephemeral containers | Stage 2, or Azure bonus confirmed |
| Redis | Postgres covers queue and rate limits | Measured need |
| Kubernetes | Too much operations for one person | > 5 services or team ≥ 4 |
| Dedicated search/vector engine | Corpus is thousands of documents | Retrieval p95 > 300 ms at SCALE or ranking limits |
| Workflow engine | Jobs are short and idempotent | Multi-day workflows |
| Microservices / message broker | One developer, one deploy | Measured independent-scaling need |
| Next.js / server rendering | No SEO need inside the app; Vercel Hobby forbids commercial use ([Vercel fair-use](https://vercel.com/docs/limits/fair-use-guidelines)) | Measured UX need |
| Native mobile apps | Responsive web covers MVP | Mobile-first usage data |
| Rejected free hosts | Oracle Always Free (unannounced limit cuts, idle reclaim); Neon free as primary DB (compute suspended when allowance runs out) | Not planned — see [ADR-0006](adr/0006-hosting-digitalocean-cloudflare.md), [ADR-0003](adr/0003-postgres-single-datastore.md) |
