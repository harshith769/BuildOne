# BuildOne — Functional Requirements

> **Status:** Draft v0.2 · 2026-09-28 (revised for ₹0 MVP: AI-optional explainer, intake, reminders) · Owner: @harshith769
> Feature IDs (L1, C3, R2 …) come from [product-vision.md §6](product-vision.md#6-features). Quality targets (latency, uptime, accuracy) live in [nfr.md](nfr.md), not here.

**What this document answers**
- What exactly each MVP feature must do, stated as testable acceptance criteria
- Which platform capabilities (accounts, organisations, roles, data rights) the MVP needs
- What is explicitly out of scope for the MVP
- How each requirement traces to a product feature and a test type

---

## 1. Conventions

- **ID format:** `FR-<area>-<nn>`. Areas: `PLT` platform, `LP` Launchpad, `CORE` BuildOne Core, `RS` Rule Studio.
- **Priority:** `MUST` (MVP blocker) · `SHOULD` (MVP if time allows) · `LATER` (v1/v2).
- **Acceptance criteria** are written as *Given / When / Then* or as checkable statements. A requirement is done only when every criterion passes an automated or documented manual test.
- **"Guidance" rule:** anywhere the product shows regulatory or legal information, the disclaimer component defined in FR-PLT-08 is visible.

---

## 2. Platform requirements

### FR-PLT-01 Sign-in and sessions — MUST
- Users sign in with email (passwordless link or one-time code) or Google, via the identity provider (see [ADR-0007](adr/0007-identity-workos-sessions.md)).
- After identity verification, the backend creates a **server-side session** and sets an `HttpOnly`, `Secure`, `SameSite=Lax` cookie.
- **AC:**
  - Signing out deletes the server-side session; replaying the old cookie returns `401`.
  - Sessions expire after 30 days of inactivity and 90 days absolute (values configurable).
  - A user can list and revoke their active sessions.
  - Users confirm they are **18 or older** at sign-up; under-18 sign-up is blocked (see [nfr.md §6](nfr.md#6-privacy-and-data-protection)).

### FR-PLT-02 Organisations — MUST
- An organisation is the tenant boundary. MVP types: `team` (pre-founder), `company`. Later: `ca_firm`, `incubator`, `campus`.
- A user can belong to several organisations and switch between them.
- **AC:**
  - Every tenant-owned record has an `org_id`; no API returns records from an organisation the caller is not a member of (verified by automated cross-tenant tests).
  - Organisation switching never mixes data from two organisations on one screen.

### FR-PLT-03 Roles — MUST
- MVP roles per organisation: `owner`, `member`, `viewer`.
- **AC:**
  - `owner`: manage members, facts, obligations, billing (later), delete organisation.
  - `member`: edit facts, obligations, evidence; use Copilot.
  - `viewer`: read-only; cannot use Copilot on that organisation.
  - Every organisation has at least one `owner`; the last owner cannot leave or be demoted.

### FR-PLT-04 Invitations — MUST
- **AC:**
  - Owners invite by email with a role; invitations expire after 7 days and are single-use.
  - Accepting an invitation with a different signed-in email requires explicit confirmation.

### FR-PLT-05 Audit log — MUST
- **AC:** An immutable audit entry (actor, org, action, target, timestamp, request ID) is written for: fact changes, obligation status changes, evidence upload/delete, member/role changes, document upload/delete, data export, organisation deletion, rule publication.

### FR-PLT-06 Data rights — MUST
- **AC:**
  - A user can export their personal data and each organisation owner can export organisation data as a ZIP (JSON + uploaded files).
  - Account deletion and organisation deletion are soft-deleted immediately (inaccessible) and hard-deleted after a 30-day grace period, including object-storage files.
  - The terms and privacy-notice version accepted by each user is recorded with a timestamp.
  - A grievance/contact channel is visible in the app footer.

### FR-PLT-07 Notification preferences — MUST
- **AC:** Users can enable/disable each notification type per organisation; every email includes a one-click unsubscribe for that type.

### FR-PLT-08 Guidance disclaimer — MUST
- **AC:** A standard component states that BuildOne provides guidance with sources, not legal or tax advice, and links to "get this reviewed". It appears on every obligation, explanation, Copilot answer, Situation Check result, and Launch Roadmap.

### FR-PLT-09 Internal admin — SHOULD
- **AC:** Staff can look up users and organisations read-only; every admin view is audit-logged. No impersonation in MVP.

---

## 3. Launchpad requirements (pre-founders)

### FR-LP-01 Team Space (L1) — MUST
- **AC:**
  - A user creates a `team` organisation with a name and a one-paragraph idea description.
  - Up to 6 co-founders can be invited (FR-PLT-04).
  - Each member fills a **situation profile**: occupation status (`student`, `employed`, `self_employed`, `other`), state of residence, expected weekly hours, intended capital contribution (optional, range).
  - Situation profiles are visible to all team members; the member can edit only their own.

### FR-LP-02 Situation Check (L2) — MUST
- **Questionnaire flags (rules-driven):**
  - **AC:** Based on the situation profile and a short questionnaire (e.g., "Did you sign an employment contract?", "Is your university providing resources/funding?"), the system shows risk *topics* to check (e.g., IP ownership, outside-work restrictions, university IP policy), each with a plain-language reason.
- **Document check (AI-assisted):**
  - **AC:** A member may upload their own employment contract or university policy (PDF/DOCX, ≤ 10 MB).
  - The system extracts clauses in these categories: IP assignment, outside activities / moonlighting, non-compete / non-solicit, confidentiality, notice period.
  - Each flagged clause shows the **quoted location in the uploaded document** (page and section) and a plain-language explanation.
  - The system never states that the user *is* or *is not* permitted to do something; it states what the clause appears to cover and recommends professional review.
  - If extraction confidence is below the threshold in [nfr.md §7](nfr.md#7-ai-quality-gates), the result says the clause could not be reliably identified.
  - Uploaded documents are **private to the uploader by default**; sharing a summary with the team is an explicit opt-in. The uploader can delete the document at any time (hard delete per FR-PLT-06 rules).
  - Document content is treated strictly as data: instructions inside a document never change system behaviour (see [nfr.md §5](nfr.md#5-security)).
  - Extraction counts against the daily AI budget; when the budget is spent, the user sees "Document check is at today's limit — try tomorrow", and the questionnaire flags still work.

### FR-LP-03 Launch Roadmap (L3) — MUST
- **AC:**
  - Shows **incorporation triggers** (taking investment, hiring, signing customer contracts, receiving revenue, program requirements) and marks which ones the team reports as true.
  - Shows a structure comparison (Private Limited, LLP, OPC) as information; only the **Private Limited** path is fully supported in MVP.
  - Shows a cost breakdown: government fees (cited to source) and professional fees (clearly labelled as estimated ranges).
  - An owner can click **"We're incorporating"**, which creates a `company` organisation pre-filled with team members and relevant facts, and links it to the team.

### FR-LP-04 Founder Alignment (L4) — LATER (v1)
### FR-LP-05 Validation Sprint (L5) — LATER (v1)
### FR-LP-06 Opportunity Finder (L6) — LATER (v1)
### FR-LP-07 Connect (L7) — LATER (v2)

---

## 4. BuildOne Core requirements (incorporated companies)

### FR-CORE-01 Smart Intake (C1) — MUST
- **AC:**
  - The company profile follows a fixed **fact schema** (entity type, incorporation date, state, registered office city, share capital present, number of directors, employees count, expected annual turnover band, GST registration status, business activities, etc.; full schema in data-model.md).
  - **The form is the primary path (MUST)** and works without any AI.
  - Free-text description is an optional convenience (**SHOULD**): AI converts it into **proposed facts**, each shown with the sentence it came from. When the daily AI budget is spent, the free-text option is hidden and the form remains.
  - **No proposed fact is used in any computation until the user confirms it.**
  - Every fact accepts the value **"I don't know"**.
  - Fact changes are versioned (who, when, old value, new value).

### FR-CORE-02 Launch Planner (C2) — MUST
- **AC:** For a company not yet incorporated (or from the Launchpad handoff), shows the ordered incorporation steps, required documents per director/shareholder, and dependencies between steps, each step cited to an official source.

### FR-CORE-03 Obligation Plan and Calendar (C3) — MUST
- **AC:**
  - The rules engine evaluates all **published** rules against confirmed facts and produces obligations.
  - Each obligation shows: title, rule ID and version, authority, form (if any), due date, recurrence, required documents, status.
  - Status values shown to users: `upcoming`, `due_soon`, `overdue`, `done`, `not_applicable` (with reason), **`needs_info`**. Stored states and derived urgency are defined in [data-model.md §4.6](data-model.md#46-obligations).
  - **If a rule's condition depends on a fact whose value is unknown, the obligation is shown as `needs_info` — it is never silently dropped.**
  - Evaluation is deterministic: identical facts and rule versions always produce identical obligations (verified by tests).
  - Obligations recompute automatically after a fact change or rule publication (latency target in [nfr.md §3](nfr.md#3-performance)).
  - Due dates are calendar dates in the Indian timezone (`Asia/Kolkata`), never timestamps.
  - Users can mark an obligation `done` with an optional note and date.
  - Calendar feed and reminders are specified in FR-CORE-06.
  - Obligation history (status changes) is retained.

### FR-CORE-04 "Why this applies" Explainer (C4) — MUST
- **Default explanation is deterministic (no AI):**
  - **AC:** For each obligation, the explanation is assembled from (a) the rule's evaluation trace — the conditions that matched **with the company's actual fact values**, (b) the CA-approved plain-language summary and "what to do" text stored in the rule (FR-RS-03), (c) required documents, penalty text where the rule includes it, and (d) citations that open the exact source span.
  - Identical rule version + facts always produce identical text.
  - Works with every AI provider unavailable.
- **Optional AI rephrasing (SHOULD):**
  - **AC:** A "Explain in simpler words" action may produce an AI rephrasing grounded only in the deterministic explanation and its cited spans. Every sentence passes citation verification; unsupported sentences are removed; if verification fails, the deterministic explanation remains. Rephrasings are cached per (company, rule version, relevant-facts hash). Unavailable when the daily AI budget is spent.

### FR-CORE-05 Founder Copilot (C5) — MUST
- **AC:**
  - Chat interface with streaming responses, scoped to the current organisation.
  - Each question is classified into one route: `determination` (answered from the obligation plan), `explanation` (Explainer), `what_if` (MVP: returns a message that this arrives in v1), `interpretive` (cited retrieval-based answer), `out_of_scope` (refer to a professional).
  - Interpretive answers cite sources for every factual claim; claims without support are not shown.
  - When retrieval confidence is below threshold, the answer abstains and recommends professional review.
  - Users can rate answers (helpful / not helpful + optional comment).
  - Each organisation has a daily question quota (value in [nfr.md §9](nfr.md#9-cost)); the UI shows remaining quota.
  - When the organisation quota or the global daily AI budget is exhausted, Copilot shows "Daily limit reached — try tomorrow" and links to the obligation plan and explanations (which need no AI). The system never switches to a paid AI tier automatically.
  - Only the facts needed for the question are sent to the model provider; names, contact details, and uploaded documents are not sent.

### FR-CORE-06 Reminders (C6) — MUST
- **In-app reminders (MUST):**
  - **AC:** A notifications panel shows obligations at 7 days before, 1 day before, and overdue (defaults, configurable per organisation).
- **Calendar feed (MUST):**
  - **AC:** Each user can subscribe to a private, revocable ICS calendar URL containing their organisations' obligations with due dates and a link back to the obligation, so reminders arrive through the user's own calendar app with no email dependency.
- **Email reminders (SHOULD — depends on the chosen email provider's free tier):**
  - **AC:** Emails at the same thresholds plus an optional weekly digest; one-click unsubscribe per type (FR-PLT-07).
- **For all channels:**
  - **AC:** Reminders are **idempotent** — the same obligation, type, channel, and due date never produce two notifications, even after retries or redeploys.
  - No reminder is generated for obligations marked `done` or `not_applicable`.

### FR-CORE-07 … FR-CORE-12 (C7–C12) — LATER
Event Triggers, What-if Simulator, Evidence Vault, Compliance Health Score, Due-Diligence Pack (v1); Change Radar (v2).

---

## 5. Rule Studio requirements (internal)

### FR-RS-01 Source library (R1) — MUST
- **AC:**
  - Each official source is registered with: title, authority, jurisdiction, document type, official URL, publication date, effective-from/to dates, and the content hash of the stored file.
  - Re-ingesting a changed document creates a new version; old versions remain retrievable.
  - Every chunk used for retrieval is traceable to a source version and section path.

### FR-RS-02 AI-assisted rule drafting (R2) — MUST
- **AC:**
  - A command-line tool takes a topic and/or source sections and produces **draft** rule files in the rule schema, each with citations to chunk IDs.
  - Drafts are written to a `drafts/` location and can never be published without FR-RS-03.

### FR-RS-03 Review and publication (R3) — MUST
- **AC:**
  - Rules are published only through a reviewed change (pull request) that records the reviewer identity and review date in the rule file.
  - Every rule contains a CA-approved plain-language summary and "what to do" text; these power the deterministic Explainer (FR-CORE-04). CI rejects rules without them.
  - Publication loads the new rule versions into the database, keeps old versions, and triggers re-evaluation of affected organisations.
  - Each publication produces a changelog entry (what changed and why).

### FR-RS-04 Evaluation gate (R4) — MUST
- **AC:** Continuous integration runs the scenario suite on every rule change; publication is blocked if obligation recall or any other gate in [nfr.md §7](nfr.md#7-ai-quality-gates) fails.

### FR-RS-05 Change-detection queue (R5) — LATER (v2)

---

## 6. Out of scope for MVP

- States other than Telangana; LLP and OPC compliance tracking (Launch Roadmap may *describe* them)
- Industry-specific licences
- Filing on the user's behalf, payments, or government portal integration
- CA Workspace, incubator/campus features, WhatsApp, billing (all v1)
- Native mobile apps (responsive web only)
- Languages other than English

---

## 7. Traceability matrix (MVP)

| Requirement | Product feature | Key NFRs | Primary test type |
|---|---|---|---|
| FR-PLT-01 | Platform | NFR-SEC-01, NFR-SEC-02 | Integration + security |
| FR-PLT-02/03 | Platform | NFR-SEC-03 | Cross-tenant automated tests |
| FR-PLT-05 | Platform | NFR-SEC-06 | Integration |
| FR-PLT-06 | Platform | NFR-PRV-03 | End-to-end |
| FR-LP-01 | L1 | — | End-to-end |
| FR-LP-02 | L2 | NFR-SEC-07, NFR-AI-04 | Golden-set evaluation + E2E |
| FR-LP-03 | L3 | NFR-AI-01 | Rule scenarios + E2E |
| FR-CORE-01 | C1 | NFR-AI-05 | Golden-set evaluation + E2E |
| FR-CORE-02 | C2 | NFR-AI-01 | Rule scenarios |
| FR-CORE-03 | C3 | NFR-AI-01, NFR-PERF-03 | Rule scenarios + property tests |
| FR-CORE-04 | C4 | NFR-AVL-02, NFR-AI-02, NFR-AI-03, NFR-PERF-04 | Snapshot tests (deterministic) + golden-set evaluation (rephrasing) |
| FR-CORE-05 | C5 | NFR-AI-02–04, NFR-PERF-05, NFR-COST-02, NFR-COST-04 | Golden-set evaluation + E2E (incl. budget-exhausted path) |
| FR-CORE-06 | C6 | NFR-REL-04 | Integration (idempotency, ICS validity) |
| FR-RS-01–04 | R1–R4 | NFR-AI-01 | CI pipeline tests |
