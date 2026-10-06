# BuildOne — Non-Functional Requirements

> **Status:** Draft v0.2 · 2026-09-28 (revised for ₹0 one-box MVP) · Owner: @harshith769
> Every number here is a **target** unless marked **measured**. Targets are validated by the spikes and load tests in [roadmap.md](roadmap.md). Functional behaviour lives in [requirements.md](requirements.md).

**What this document answers**
- What uptime, latency, recovery, and scale targets apply in MVP versus paid launch
- Which security and privacy controls are mandatory, and which Indian data-protection facts they rest on
- What accuracy gates AI and rules must pass before reaching users
- What the monthly cost ceiling is and how cost is controlled

---

## 1. Conventions

- **Phases:** `MVP` = pilot with design partners · `PAID` = paid launch · `SCALE` = year 2.
- Each target has a **measurement method**. A target without one is not accepted.
- Where a target is limited by budget, the limit is stated explicitly rather than hidden.

---

## 2. Availability and reliability

| ID | Requirement | MVP | PAID | Measurement |
|---|---|---|---|---|
| NFR-AVL-01 | Monthly availability of web app + API | 99.5% (≈3.6 h downtime/month) | 99.9% (≈43 min/month) | External uptime checks every 1 min |
| NFR-AVL-02 | Core compliance features (obligation plan, calendar, reminders) work when AI providers are down | Required | Required | Chaos test: block AI egress, run E2E suite |
| NFR-REL-01 | Recovery point objective (max data loss) | ≤ 15 min (continuous WAL archiving, `archive_timeout` ≤ 60 s) | ≤ 5 min | Restore drill: compare last committed row vs. restored |
| NFR-REL-02 | Recovery time objective | ≤ 4 h (scripted rebuild of a new server + restore; aim ≤ 1 h) | ≤ 1 h | Restore drill (timed) |
| NFR-REL-03 | Backups | Continuous WAL archive + nightly base backup and logical dump to R2 backup bucket, 30-day retention, write-only credentials | Same + managed-provider point-in-time recovery | **Monthly** restore drill onto a fresh server, logged |
| NFR-REL-04 | Background jobs are idempotent and retried with backoff | Required | Required | Integration tests replaying jobs |

**Budget limit (explicit):** the MVP runs everything on one server ([ADR-0006](adr/0006-hosting-digitalocean-cloudflare.md)) — a single point of failure. Recovery relies on continuous backups and a scripted rebuild, which is why the MVP target is 99.5%. The 99.9% PAID target **requires** stage 4 of the growth path (standby database + two API instances; [architecture.md §7.2](architecture.md#72-growth-path)); a standby node is billed at extra cost ([DigitalOcean PostgreSQL pricing](https://docs.digitalocean.com/products/databases/postgresql/details/pricing/)).

---

## 3. Performance

Measured at the API server, p95, excluding client network, under the SCALE load profile in §4.

| ID | Requirement | Target |
|---|---|---|
| NFR-PERF-01 | Non-AI API endpoints | p95 < 500 ms |
| NFR-PERF-02 | App first load on 4G mobile (Largest Contentful Paint) | < 2.5 s |
| NFR-PERF-03 | Full rule evaluation for one company (all published rules) | p95 < 2 s; recompute visible to user < 60 s after a fact change |
| NFR-PERF-04 | Explainer: deterministic (default) / AI-rephrased (optional) | p95 < 300 ms / < 8 s |
| NFR-PERF-05 | Copilot: time to first token / full answer | p95 < 3 s / < 15 s |
| NFR-PERF-06 | Retrieval (hybrid search + fusion, excluding reranker) | p95 < 300 ms |

---

## 4. Scalability

| ID | Profile | Target |
|---|---|---|
| NFR-SCL-01 | SCALE data volume | 10,000 companies, 500 CA firms, ~1M obligation rows, ~5,000 source documents |
| NFR-SCL-02 | SCALE concurrency | 200 concurrent active users; 20 concurrent Copilot streams |
| NFR-SCL-03 | Rule publication | Re-evaluate 10,000 companies within 30 min of a publish |
| NFR-SCL-04 | Horizontal scaling | API and workers are stateless; scale by adding processes without code change |

Load tests against NFR-SCL-01/02 run before PAID ([testing-strategy.md](testing-strategy.md)).

---

## 5. Security

| ID | Requirement | Phase |
|---|---|---|
| NFR-SEC-01 | Authentication delegated to identity provider; app uses server-side sessions with `HttpOnly`, `Secure`, `SameSite=Lax` cookies; CSRF protection on state-changing requests | MVP |
| NFR-SEC-02 | TLS 1.2+ everywhere; HSTS; encryption at rest for database and object storage (provider-managed) | MVP |
| NFR-SEC-03 | Tenant isolation enforced twice: application-level scoping **and** Postgres Row-Level Security; automated cross-tenant tests in CI | MVP |
| NFR-SEC-04 | Secrets never in the repository; secret scanning in CI; least-privilege database roles (app role cannot alter schema) | MVP |
| NFR-SEC-12 | One-box hardening: Postgres reachable only on the internal Docker network; origin accepts only Cloudflare IPs; SSH key-only; unattended OS security updates; container images updated monthly | MVP |
| NFR-SEC-05 | Dependency vulnerability scanning in CI; critical vulnerabilities patched within 7 days | MVP |
| NFR-SEC-06 | Audit log is append-only for the app role; retained ≥ 1 year | MVP |
| NFR-SEC-07 | Uploaded files: type and size validation, stored in private object storage, accessed only via signed URLs expiring ≤ 15 min; malware scanning before processing | MVP (scanning: PAID) |
| NFR-SEC-08 | Prompt-injection defence: user-uploaded and retrieved content is passed to models only as delimited data; models have no tools that change state; all model outputs validated against schemas | MVP |
| NFR-SEC-09 | Rate limiting per user and per IP on auth, upload, and AI endpoints | MVP |
| NFR-SEC-10 | Verification against OWASP ASVS Level 2 | PAID |
| NFR-SEC-11 | External security review / penetration test | PAID |

Threat model and detailed controls: [security-design.md](security-design.md).

---

## 6. Privacy and data protection

### 6.1 Legal facts this section relies on (verify with a lawyer before PAID)

- India's Digital Personal Data Protection Act, 2023 (DPDP Act) and DPDP Rules, 2025 are being commenced in phases. Commencement notifications of November 2025 place most operational obligations — including cross-border transfer (Section 16, Rule 15) — in an 18-month phase expected to take effect on **13 May 2027** ([Legal500, Sep 2026](https://www.legal500.com/intelligence/india/privacy/cross-border-data-transfers-under-indias-dpdp-act-rules-restrictions-and-compliance-roadmap-for-2027)). A consultation proposed shortening this timeline; that was not confirmed by gazette at the time of writing ([Seclore](https://www.seclore.com/fundamentals/dpdp-rules-2025-compliance-guide/)).
- The DPDP Act does **not** impose general data localisation; transfers abroad are allowed unless the government restricts a destination, and sector-specific rules still apply ([miniOrange](https://www.miniorange.com/blog/cross-border-data-transfers-under-the-dpdp-act/)).

**Consequence:** hosting in India is a product choice (latency, customer trust, future-proofing), **not** a current legal requirement. AI providers process prompts outside India; this is permitted today but must be disclosed and minimised.

### 6.2 Requirements

| ID | Requirement | Phase |
|---|---|---|
| NFR-PRV-01 | Primary database hosted in India (one-box in Bangalore). Object storage (R2) and AI providers may process data outside India — permitted today, disclosed in the privacy notice | MVP |
| NFR-PRV-02 | Data minimisation to AI providers: send only facts needed for the task; never send names, contact details, government ID numbers, or financial account numbers | MVP |
| NFR-PRV-03 | Data-principal rights: access/export, correction, erasure, grievance contact (FR-PLT-06) | MVP |
| NFR-PRV-04 | Users must be 18+; under-18 sign-up blocked (avoids the Act's verifiable parental-consent regime — relevant because students are a target segment) | MVP |
| NFR-PRV-05 | User data may go only to AI providers whose terms contractually exclude training on inputs/outputs (e.g., Groq's services agreement — [Groq](https://console.groq.com/docs/legal/services-agreement)) **and** with zero data retention enabled where offered ([Groq: Your Data](https://console.groq.com/docs/your-data)). Free tiers that use content to improve the provider's products (e.g., Gemini free tier — [Puter pricing guide](https://developer.puter.com/tutorials/gemini-api-pricing/)) may receive **public source text only** | MVP |
| NFR-PRV-06 | Privacy notice lists every sub-processor (hosting, identity, AI, email) and its data location | MVP |
| NFR-PRV-07 | Retention: personal documents kept until the user deletes them; deleted accounts hard-deleted after 30 days; logs containing personal data ≤ 90 days | MVP |
| NFR-PRV-08 | Full DPDP compliance programme (consent records, breach-notification process, processor agreements) complete **before 13 May 2027** or before PAID, whichever is earlier | PAID |

---

## 7. AI quality gates

Measured on golden sets defined in [evaluation.md](evaluation.md). A failed gate blocks release of the affected rules, prompts, or models.

| ID | Metric | Gate |
|---|---|---|
| NFR-AI-01 | **Obligation recall** on CA-verified company scenarios (missed obligation = failure) | ≥ 98%; zero misses on "critical" obligations |
| NFR-AI-02 | Citation precision (cited span supports the sentence) | ≥ 95% |
| NFR-AI-03 | Faithfulness (answers with no unsupported claim) | ≥ 95% |
| NFR-AI-04 | Abstention correctness (abstains on unanswerable set; answers on answerable set) | ≥ 90% both |
| NFR-AI-05 | Fact extraction accuracy (Smart Intake, field-level) | ≥ 95%; user confirmation still required |
| NFR-AI-06 | Retrieval recall@10 on labelled questions | ≥ 90% |

Baselines are **not measured yet**; spikes S2–S4 in [roadmap.md](roadmap.md) produce them. Gates may be revised only with a recorded reason.

---

## 8. Usability, accessibility, compatibility

| ID | Requirement |
|---|---|
| NFR-UX-01 | WCAG 2.2 AA for all user-facing screens |
| NFR-UX-02 | Latest two versions of Chrome, Edge, Firefox, Safari; responsive down to 360 px width |
| NFR-UX-03 | English only in MVP; all UI strings externalised for later Telugu/Hindi |
| NFR-UX-04 | Indian formats: dates as `DD MMM YYYY`, currency with Indian digit grouping (₹1,00,000); money stored as integer paise |

---

## 9. Cost

| ID | Requirement | Target |
|---|---|---|
| NFR-COST-01 | Total infra + AI spend during MVP | **₹0/month** out of pocket (free tiers + student benefits, ADR-0012); hard ceiling ₹5,000 if a stage change is forced; breakdown in [tech-stack.md §4](tech-stack.md#4-budget) |
| NFR-COST-02 | Copilot quota | Per organisation: 10 questions/day in MVP; global daily token budget set below the providers' free limits; Copilot prompts ≤ ~4k tokens — tune after measurement |
| NFR-COST-03 | AI cost per active company per month | ≤ ₹50 (≈10% of the Pro price hypothesis); verified in cost-model.md |
| NFR-COST-04 | Alerts at 50% / 80% / 100% of the daily AI budget; at 100% non-essential AI features degrade gracefully; **the system never switches to a paid tier automatically**; cloud billing alerts enabled on every account | MVP |

---

## 10. Maintainability and observability

| ID | Requirement |
|---|---|
| NFR-MNT-01 | Static type checking in strict mode (backend and frontend) passes in CI |
| NFR-MNT-02 | Module boundaries enforced automatically (no cross-module imports of internals) |
| NFR-MNT-03 | Every rule, prompt, and model choice is versioned; every AI output stores the versions that produced it |
| NFR-OBS-01 | Every request carries a request ID propagated to logs, traces, jobs, and AI calls |
| NFR-OBS-02 | Alerts: error rate, job failures, queue lag, AI spend, uptime check failures |
| NFR-OBS-03 | Structured JSON logs; no personal data in logs beyond user/org IDs |
