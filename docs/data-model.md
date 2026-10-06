# BuildOne — Data Model

> **Status:** v1.2 (frozen for MVP build) · 2026-10-06 (M3: RLS check functions owned by `app_rls_check`, read/write policy split, [ADR-0013](adr/0013-rls-check-functions-and-read-write-split.md)) · Owner: @harshith769
> Changes to anything marked **Frozen** require an ADR. New tables/columns are allowed via additive migrations.

**What this document answers**
- Which tables exist in the MVP, in which Postgres schema, with which constraints and indexes
- How tenant isolation is enforced (roles, session settings, RLS policies)
- Which tables are reserved for v1 so the MVP schema does not need restructuring later
- Which invariants the database itself guarantees

---

## 1. Frozen conventions

| Concern | Rule |
|---|---|
| IDs | `uuid` primary keys generated as **UUIDv7** by the application; append-only logs use `bigint GENERATED ALWAYS AS IDENTITY` (internal only, never exposed) |
| Time | `timestamptz` (UTC) for instants; **`date`** for legal due dates, interpreted in `Asia/Kolkata` |
| Money | `bigint` paise, column suffix `_paise` |
| Enums | Postgres `CHECK (col IN (...))` constraints (easier to extend than native enums) |
| Nullability | `NOT NULL` by default; every nullable column has a stated meaning |
| Foreign keys | Always declared, with explicit `ON DELETE`; every FK column indexed |
| Tenancy | Every tenant-owned table has `org_id uuid NOT NULL` + RLS enabled and **forced** |
| Deletion | No soft-delete columns. Organisations/users use an explicit lifecycle `status`; scheduled job hard-deletes after 30 days |
| Schemas | One Postgres schema per backend module (`identity`, `tenancy`, `audit`, `facts`, `rules`, `obligations`, `knowledge`, `ai`, `copilot`, `explainer`, `documents`, `launchpad`, `notifications`, `platform`); `procrastinate` schema owned by the job library |
| Extensions | Only `vector`, `pg_trgm`, `citext` ([ADR-0011](adr/0011-portability-rules.md)) |
| Postgres version | 18 (image `pgvector/pgvector:0.8.7-pg18-trixie`); `UNIQUE NULLS NOT DISTINCT` requires ≥ 15; native `uuidv7()` available from 18 |

---

## 2. Database roles (Frozen)

| Role | Purpose | Privileges |
|---|---|---|
| `app_owner` | Owns all schemas/tables; runs migrations | DDL; never used by running services |
| `app_api` | API process | DML on module tables; **RLS enforced** (`NOBYPASSRLS`) |
| `app_worker` | Worker process | Same as `app_api`; cross-org scans only via `SECURITY DEFINER` functions (§6) |
| `app_ingest` | Ingestion CLI (run from developer machine via SSH tunnel) | DML on `knowledge.*` only |
| `app_readonly` | Pilot metrics queries | `SELECT` on non-personal aggregates/views only |
| `app_rls_check` | Owns the tenancy RLS check functions ([ADR-0013](adr/0013-rls-check-functions-and-read-write-split.md)) | `NOLOGIN BYPASSRLS`; owns no tables; `SELECT` on the four tenancy tables only; granted to `app_owner` `WITH INHERIT FALSE, SET TRUE` (migrations only), never to a service role. Created by `infra/postgres/initdb/10-rls-check-role.sql` |

`audit.events` and `ai.calls`: append-only. `app_api`/`app_worker` have no `UPDATE`/`DELETE`; `audit.events` also has no `SELECT` policy yet (no reader in the MVP).

---

## 3. Request context and RLS (Frozen)

Each request/job runs inside a transaction that first executes:

```sql
SET LOCAL app.user_id = '<uuid or empty>';
SET LOCAL app.org_id  = '<uuid or empty>';
```

Helper functions (owned by `app_owner`, `STABLE`):

```sql
CREATE FUNCTION platform.current_user_id() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;
CREATE FUNCTION platform.current_org_id() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.org_id', true), '')::uuid $$;
```

Check functions (owned by `app_rls_check`, `SECURITY DEFINER`, `STABLE`, read-only, `SET search_path = pg_catalog, pg_temp`; each answers a question about the caller or about a token hash the caller holds; all require the organisation `status = 'active'`):

| Function | True when the caller… |
|---|---|
| `tenancy.is_member(org)` | has any membership (owner/member/viewer) |
| `tenancy.is_owner(org)` | is an owner |
| `tenancy.can_edit(org)` | is owner or member (viewers excluded, FR-PLT-03) |
| `tenancy.can_read(org)` | is a member, **or** belongs to an active org holding an **active** access grant from `org` (any scope) |
| `tenancy.shares_org_with(user)` | shares an active organisation with `user` (member lists) |
| `tenancy.is_creator_without_members(org)` | created `org` and it has no members yet (bootstrap of the first owner) |
| `tenancy.invitation_token_matches(org, role)` | holds the token of an unaccepted, **unexpired** (`expires_at > now()`, migration 0006) invitation for `org`/`role` (`SET LOCAL app.invitation_token_hash = <hex>`) |
| `tenancy.find_invitation(token_hash)` | lookup by token hash, like `identity.find_session` |

Standard policies for every **company-data** table `X` (facts, obligations, …), generated by `app.platform.rls.company_data_policies()` so every table gets identical SQL:

```sql
ALTER TABLE X ENABLE ROW LEVEL SECURITY;
ALTER TABLE X FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_read   ON X FOR SELECT USING (org_id = platform.current_org_id() AND tenancy.can_read(org_id));
CREATE POLICY tenant_insert ON X FOR INSERT WITH CHECK (org_id = platform.current_org_id() AND tenancy.can_edit(org_id));
CREATE POLICY tenant_update ON X FOR UPDATE USING (org_id = platform.current_org_id() AND tenancy.can_edit(org_id))
                                          WITH CHECK (org_id = platform.current_org_id() AND tenancy.can_edit(org_id));
CREATE POLICY tenant_delete ON X FOR DELETE USING (org_id = platform.current_org_id() AND tenancy.can_edit(org_id));
```

Missing settings → `NULL` → policy false → **fails closed**. **Read stays read:** `can_read` appears only in `SELECT` policies; the write check never consults grants, whatever their scope (D-29). A schema guard test fails if any write policy references `can_read` (the one exception is the `audit.events` insert policy, §4.3) and if any table with `org_id` matches neither this template nor an individually registered design.

Other policy classes: **org admin** (`memberships`, `invitations`, `access_grants`, `organizations`, §4.2); **own-row** (`user_id = platform.current_user_id()`): `identity.*`, `platform.idempotency_keys`, and later notification read state, `notifications.preferences`, `obligations.calendar_feeds`; `documents.documents` keeps its owner/visibility predicate and is never grant-readable.

---

## 4. MVP tables

Column lists show type and key constraints; `created_at timestamptz NOT NULL DEFAULT now()` and `updated_at timestamptz NOT NULL DEFAULT now()` exist on every mutable table and are omitted below.

### 4.1 `identity`

Identity tables are user-scoped, not tenant-scoped: RLS is **enabled** with a `user_isolation` policy (`id`/`user_id = platform.current_user_id()`) but **not forced**, so two `SECURITY DEFINER` lookups owned by `app_owner` can run before the user is known: `identity.find_session(token_hash)` (session cookie → session and user) and `identity.find_user_by_idp(idp_user_id)` (IdP callback → user). EXECUTE on them is granted only to `app_api` and `app_worker`. Services never connect as `app_owner`, so the policies always apply to them (M2, migration `0002_identity`).

A user row is created only when the person confirms 18+ and accepts the terms (D-28); until then the verified profile lives in a signed cookie ([auth-and-tenancy.md §1](auth-and-tenancy.md#1-sign-in-flow-authorization-code--pkce-via-workos-authkit)).

**`identity.users`** (not tenant-scoped; RLS: row visible when `id = current_user_id()`)
- `id uuid PK`
- `email citext NOT NULL UNIQUE`
- `display_name text NOT NULL`
- `idp_user_id text NOT NULL UNIQUE` — WorkOS user ID
- `status text NOT NULL CHECK (status IN ('active','deletion_pending'))`
- `deletion_requested_at timestamptz NULL` — set iff `status='deletion_pending'` (CHECK)
- `age_confirmed_at timestamptz NOT NULL` — 18+ confirmation (NFR-PRV-04)

**`identity.sessions`**
- `id uuid PK`, `user_id uuid NOT NULL FK users ON DELETE CASCADE` (indexed)
- `token_hash bytea NOT NULL UNIQUE` — SHA-256 of the cookie token; raw token never stored
- `csrf_token_hash bytea NOT NULL`
- `last_seen_at timestamptz NOT NULL`, `idle_expires_at timestamptz NOT NULL`, `absolute_expires_at timestamptz NOT NULL`
- `ip inet NULL`, `user_agent text NULL` — informational
- CHECK `idle_expires_at <= absolute_expires_at`

**`identity.consents`**
- `id uuid PK`, `user_id uuid FK users ON DELETE CASCADE`
- `document text CHECK (document IN ('terms','privacy'))`, `version text NOT NULL`, `accepted_at timestamptz NOT NULL`
- UNIQUE `(user_id, document, version)`

### 4.2 `tenancy`

**`tenancy.organizations`**
- `id uuid PK`
- `type text NOT NULL CHECK (type IN ('team','company','ca_firm','incubator','campus'))` — MVP creates `team`, `company`, `ca_firm`, `incubator`; `campus` later
- `name text NOT NULL`
- `status text NOT NULL CHECK (status IN ('active','deletion_pending'))`, `deletion_requested_at timestamptz NULL` (CHECK pairs with status)
- `source_team_id uuid NULL FK organizations ON DELETE SET NULL` — set when a company was created from a Launchpad team (FR-LP-03)
- `created_by uuid NOT NULL FK identity.users ON DELETE RESTRICT`
- RLS: `SELECT` if `tenancy.can_read(id)` (members and active grantees see name and type); `INSERT` only with `created_by = current user`; `UPDATE` by owners. Inserted without `RETURNING` (the creator isn't a member until the bootstrap membership is inserted in the same transaction)

**`tenancy.memberships`**
- PK `(org_id, user_id)`; `org_id FK organizations ON DELETE CASCADE`; `user_id FK identity.users ON DELETE CASCADE`; index `(user_id)`
- `role text NOT NULL CHECK (role IN ('owner','member','viewer'))` — v1 adds `ca_staff` roles via grants, not here
- Last-owner invariant enforced by a constraint trigger (`DEFERRABLE INITIALLY DEFERRED`, `tenancy.last_owner_guard()`)
- RLS (org admin): `SELECT` for members only (grantees never see a company's people); `INSERT`/`UPDATE`/`DELETE` by owners; plus three narrow policies: **bootstrap** (the creator inserts their own `owner` row while the org has no members), **accept** (the invitation token holder inserts their own row with the invited role), **leave** (a member deletes their own row)

**`tenancy.invitations`**
- `id uuid PK`, `org_id FK ON DELETE CASCADE`, `email citext NOT NULL`, `role text CHECK (...)`
- `token_hash bytea NOT NULL UNIQUE`, `expires_at timestamptz NOT NULL`, `accepted_at timestamptz NULL`, `invited_by uuid NULL FK users ON DELETE SET NULL` (NULL = the inviter's account was deleted)
- Partial UNIQUE `(org_id, email) WHERE accepted_at IS NULL`; an expired open invitation is deleted when the same address is invited again
- RLS (org admin): owners only; the token holder may `SELECT` and `UPDATE` the matching row. Trigger `tenancy.invitations_guard()`: a non-owner may only set `accepted_at`, once; every other column stays the same

**`tenancy.access_grants`** (MVP, created in M3; the v1 reservation plus `id` and lifecycle columns) — lets one organisation read another's data
- `id uuid PK`, `grantor_org_id uuid NOT NULL FK organizations ON DELETE CASCADE` (the `company` sharing its data), `grantee_org_id uuid NOT NULL FK organizations ON DELETE CASCADE` (a `ca_firm` or `incubator`); both indexed
- `scope text NOT NULL CHECK (scope IN ('read','manage'))` — MVP uses only `read`; `manage` is for the later CA Workspace
- `status text NOT NULL CHECK (status IN ('pending','active','revoked'))`, `initiated_by text NOT NULL CHECK (initiated_by IN ('grantor','grantee'))` (a company shares with a CA firm, or an incubator asks a company), `created_by uuid NULL FK identity.users ON DELETE SET NULL` (NULL = creator's account deleted), `accepted_at timestamptz NULL`, `revoked_at timestamptz NULL`; CHECKs: grantor ≠ grantee, `revoked_at` set iff revoked, active ⇒ accepted
- Trigger `tenancy.access_grants_guard()`: grantor type `company`, grantee type `ca_firm` or `incubator`; starts `pending`; only an owner of the invited side accepts (`pending → active`); an owner of either side revokes; revoked is final; orgs, scope and origin never change
- RLS: `SELECT` by members of either side; `INSERT` by an owner of the initiating side; `UPDATE` by owners of either side (rules above); no `DELETE` (history stays)
- Partial UNIQUE `(grantor_org_id, grantee_org_id) WHERE status <> 'revoked'`
- Uses: a founder shares a company with a CA firm (FR-PART-01); an incubator reads its cohort companies (FR-PART-02)
- **Read stays read at the database** (M3, [ADR-0013](adr/0013-rls-check-functions-and-read-write-split.md)): grants count only in `tenancy.can_read`, which appears only in `SELECT` policies (§3). `manage` is a valid scope but reads like `read` and never writes; the API refuses to create it until the CA Workspace defines its write scope (D-29, [deferred.md](deferred.md)).
- Grants never expose `documents.*` rows (the documents visibility predicate in §4.10 still applies).

### 4.3 `audit`

**`audit.events`** (append-only)
- `id bigint IDENTITY PK`, `occurred_at timestamptz NOT NULL DEFAULT now()`
- `actor_user_id uuid NULL` (NULL = system), `org_id uuid NULL`, `request_id text NOT NULL`
- `action text NOT NULL CHECK (action ~ '^[a-z_]+\.[a-z_]+$')` — e.g., `facts.updated`
- `target_table text NOT NULL`, `target_id text NOT NULL` — deliberate loose reference: audit rows must outlive deleted targets
- `metadata jsonb NOT NULL DEFAULT '{}'` — never contains document contents or secrets
- Index `(org_id, occurred_at)`. Retention ≥ 1 year (NFR-SEC-06)
- RLS `INSERT` (the only policy): a user row needs `actor_user_id = current user` and, if it names an org, `tenancy.can_read(org_id)` (viewers and active grantees write audit rows too); a system row (NULL actor) only from `app_worker`, with `org_id` NULL or the current org. No `UPDATE`/`DELETE` privileges, no `SELECT` policy yet. Written without `RETURNING`

### 4.4 `facts`

**`facts.fact_definitions`** (global, read-only to services; seeded from `rules/facts.yaml` at publication)
- `key text PK CHECK (key ~ '^[a-z][a-z0-9_]*$')`
- `subject text NOT NULL CHECK (subject IN ('org','member'))`
- `value_type text NOT NULL CHECK (value_type IN ('bool','int','date','enum','enum_list','money_paise','state_code','text'))`
- `allowed_values jsonb NULL` — required iff enum types (CHECK)
- `org_types text[] NOT NULL`, `label text NOT NULL`, `help text NOT NULL`, `registry_version int NOT NULL`

**`facts.facts`** (tenant) — current confirmed values
- `id uuid PK`, `org_id uuid NOT NULL FK organizations ON DELETE CASCADE`
- `member_user_id uuid NULL FK identity.users ON DELETE CASCADE` — NULL for org-level facts
- `key text NOT NULL FK fact_definitions`
- `value_state text NOT NULL CHECK (value_state IN ('known','unknown'))`
- `value jsonb NULL` — CHECK `(value_state = 'known') = (value IS NOT NULL)`; type-checked by the service against the definition
- `source text NOT NULL CHECK (source IN ('form','ai_proposal_confirmed','handoff_confirmed'))`
- `updated_by uuid NOT NULL FK identity.users`
- `UNIQUE NULLS NOT DISTINCT (org_id, member_user_id, key)`

**`facts.fact_history`** (tenant, append-only) — `id bigint IDENTITY`, `org_id`, `member_user_id`, `key`, `old_value jsonb NULL`, `new_value jsonb NULL`, `old_state`, `new_state`, `changed_by`, `changed_at`

**`facts.fact_proposals`** (tenant) — unconfirmed AI/handoff proposals, never read by the rules engine
- `id uuid PK`, `org_id`, `member_user_id NULL`, `key FK`, `proposed_value jsonb NOT NULL`, `source_excerpt text NOT NULL`, `origin text CHECK (origin IN ('ai_extraction','handoff'))`, `ai_call_id bigint NULL`
- `resolution text NOT NULL CHECK (resolution IN ('pending','accepted','edited','rejected'))`

### 4.5 `rules` (global, read-only to services; written only by the publication job as `app_owner`)

**`rules.publications`** — `id uuid PK`, `git_commit text NOT NULL`, `published_at`, `published_by text NOT NULL`, `changelog text NOT NULL`

**`rules.rule_versions`**
- `id uuid PK`, `rule_id text NOT NULL`, `version int NOT NULL CHECK (version >= 1)`, UNIQUE `(rule_id, version)`
- `status text CHECK (status IN ('published','retired'))` — **Proposed (D-9, decide at M6):** add `superseded` for a version replaced by a newer version of the same rule, keeping `retired` for rules withdrawn entirely
- `subject text CHECK (subject IN ('org','member'))`, `kind text CHECK (kind IN ('obligation','risk_check','roadmap_trigger'))` — **Proposed (S3):** add `eligibility` ([rules-engine.md §3](rules-engine.md#3-rule-file-format))
- `content jsonb NOT NULL` — full validated rule document ([rules-engine.md](rules-engine.md))
- `content_hash text NOT NULL`, `effective_from date NOT NULL`, `effective_to date NULL` (CHECK `effective_to > effective_from`)
- `publication_id uuid NOT NULL FK publications`
- Partial UNIQUE `(rule_id) WHERE status = 'published'` — one live version per rule

**`rules.rule_citations`** — PK `(rule_version_id, chunk_id)`; `chunk_id FK knowledge.chunks ON DELETE RESTRICT` (a cited chunk can never disappear)

### 4.6 `obligations`

**`obligations.obligations`** (tenant)
- `id uuid PK`, `org_id FK ON DELETE CASCADE`
- `rule_id text NOT NULL`, `rule_version_id uuid NOT NULL FK rules.rule_versions ON DELETE RESTRICT`
- `period_key text NOT NULL` — `once` or a period label such as `2026-10`, `FY2026-27`, `2026-Q3`
- `due_date date NULL` — NULL only when `state = 'needs_info'` and the due anchor is unknown (CHECK)
- `state text NOT NULL CHECK (state IN ('open','done','not_applicable','needs_info','superseded'))`
- `unknown_facts text[] NOT NULL DEFAULT '{}'` — non-empty iff `state = 'needs_info'` (CHECK)
- `evaluation_trace jsonb NOT NULL`, `facts_hash text NOT NULL`, `computed_at timestamptz NOT NULL`
- `completed_on date NULL`, `completed_by uuid NULL FK users`, `completion_note text NULL` — CHECK `(state = 'done') = (completed_on IS NOT NULL)`
- UNIQUE `(org_id, rule_id, period_key)`
- Index `(org_id, due_date) WHERE state IN ('open','needs_info')`

Displayed urgency (`upcoming`, `due_soon`, `overdue`) is **derived at read time** from `state='open'`, `due_date`, and today in `Asia/Kolkata`; it is never stored.

**`obligations.obligation_history`** (tenant, append-only) — `id bigint IDENTITY`, `obligation_id FK ON DELETE CASCADE`, `org_id`, `from_state`, `to_state`, `actor_user_id NULL`, `reason text NOT NULL`, `at`

**`obligations.calendar_feeds`** (user-scoped) — `id uuid PK`, `user_id FK ON DELETE CASCADE`, `token_hash bytea UNIQUE NOT NULL`, `revoked_at timestamptz NULL`; exception to "no tokens in URLs" documented in [auth-and-tenancy.md §7](auth-and-tenancy.md#7-calendar-feed-capability-url)

### 4.7 `knowledge` (global; writable by `app_ingest`, read by services)

**`knowledge.sources`** — `id uuid PK`, `key text UNIQUE NOT NULL` (from `knowledge/sources.yaml`), `title`, `authority`, `jurisdiction text CHECK (jurisdiction IN ('IN','IN-TG'))`, `doc_type text CHECK (doc_type IN ('act','rules','notification','circular','form_instructions','guidance'))`, `official_url text NOT NULL`

**`knowledge.source_versions`** — `id uuid PK`, `source_id FK`, `version int`, UNIQUE `(source_id, version)`, `content_sha256 text NOT NULL`, `storage_key text NOT NULL` (R2), `published_on date NULL`, `effective_from date NOT NULL`, `effective_to date NULL`, `parser text NOT NULL` (name@version), `status text CHECK (status IN ('active','superseded'))`, `fetched_at`

**`knowledge.chunks`**
- `id uuid PK`, `source_version_id FK ON DELETE RESTRICT`, `parent_id uuid NULL FK chunks`
- `section_path text NOT NULL` (e.g., `Companies Act, 2013 > Chapter II > Section 10A > (1)`), `heading text NOT NULL`, `ordinal int NOT NULL`
- `text text NOT NULL`, `token_count int NOT NULL CHECK (token_count > 0)`
- Denormalised filters: `jurisdiction`, `doc_type`, `effective_from`, `effective_to`, `is_active bool NOT NULL`
- `tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', heading || ' ' || text)) STORED` + GIN index
- Index `(is_active, jurisdiction, effective_from)`

**`knowledge.chunk_embeddings`** — PK `(chunk_id, model_id)`, `embedding vector(D) NOT NULL`, HNSW index (`vector_cosine_ops`). **`D` is fixed by spike S2 before the first migration.** Changing the model later = new rows under a new `model_id` + backfill + config switch (additive).

### 4.8 `ai`

**`ai.calls`** (append-only; not user-visible)
- `id bigint IDENTITY PK`, `org_id uuid NULL`, `user_id uuid NULL`, `task text NOT NULL`, `prompt_version text NOT NULL`
- `provider text NOT NULL`, `model text NOT NULL`, `data_class text CHECK (data_class IN ('user_data','public_only'))`
- `input_tokens int NOT NULL`, `output_tokens int NOT NULL`, `status text CHECK (status IN ('ok','error','budget_denied','validation_failed'))`
- `latency_ms int NOT NULL`, `input_sha256 text NOT NULL`, `request_id text NOT NULL`, `created_at`
- Index `(created_at)`, `(org_id, created_at)` — budgets and quotas are computed by `SUM`/`COUNT` over this log (no counters)

### 4.9 `copilot`, `explainer`

**`copilot.conversations`** (tenant) — `id`, `org_id`, `user_id FK`, timestamps
**`copilot.messages`** (tenant) — `id`, `conversation_id FK ON DELETE CASCADE`, `org_id`, `role CHECK ('user','assistant')`, `route text NULL CHECK (route IN ('determination','explanation','what_if','interpretive','out_of_scope','limit_reached'))`, `content text NOT NULL`, `citations jsonb NOT NULL DEFAULT '[]'`, `ai_call_id bigint NULL`, `feedback text NULL CHECK (feedback IN ('helpful','not_helpful'))`, `feedback_comment text NULL`

**`explainer.rephrasings`** (tenant) — `id`, `org_id`, `rule_version_id FK`, `facts_hash`, `text`, `citations jsonb`, `ai_call_id bigint`, UNIQUE `(org_id, rule_version_id, facts_hash)`

### 4.10 `documents`, `launchpad`

**`documents.documents`** (tenant)
- `id`, `org_id`, `owner_user_id FK ON DELETE CASCADE`, `kind CHECK (kind IN ('employment_contract','university_policy','other'))`
- `storage_key text NOT NULL`, `filename text NOT NULL`, `mime text NOT NULL`, `size_bytes int CHECK (size_bytes BETWEEN 1 AND 10485760)`
- `visibility text CHECK (visibility IN ('private','team_summary'))`, `status text CHECK (status IN ('uploaded','processing','processed','failed','limit_reached'))`
- **Extra RLS predicate:** `visibility = 'team_summary' OR owner_user_id = platform.current_user_id()`

**`documents.clause_findings`** (tenant; same visibility predicate via join) — `id`, `document_id FK ON DELETE CASCADE`, `org_id`, `category CHECK (category IN ('ip_assignment','outside_activity','non_compete','non_solicit','confidentiality','notice_period'))`, `page int NULL`, `section text NULL`, `excerpt text NOT NULL`, `explanation text NOT NULL`, `confidence numeric(3,2) CHECK (confidence BETWEEN 0 AND 1)`, `ai_call_id bigint`

**`launchpad.team_profiles`** (tenant) — PK `org_id`, `idea_summary text NOT NULL`
**`launchpad.check_results`** (tenant) — results of `risk_check` and `roadmap_trigger` rules: `id`, `org_id`, `member_user_id NULL`, `rule_id`, `rule_version_id FK`, `result CHECK (result IN ('flagged','clear','needs_info'))`, `unknown_facts text[]`, `evaluation_trace jsonb`, `computed_at`, `UNIQUE NULLS NOT DISTINCT (org_id, member_user_id, rule_id)`

Member situation profiles (occupation, state, hours, capital range) are **member-level facts** in `facts.facts`, so Launchpad and Core share one engine.

### 4.11 `notifications`, `platform`

**`notifications.notifications`** (tenant)
- `id`, `org_id`, `user_id FK ON DELETE CASCADE`, `obligation_id FK ON DELETE CASCADE`
- `type CHECK (type IN ('t_minus_7','t_minus_1','overdue'))`, `channel CHECK (channel IN ('in_app','email'))`, `due_date date NOT NULL`
- `status CHECK (status IN ('pending','sent','failed','read'))`, `sent_at NULL`, `read_at NULL`
- UNIQUE `(obligation_id, user_id, type, channel, due_date)` — idempotency (FR-CORE-06)

**`notifications.preferences`** — PK `(user_id, org_id, type, channel)`, `enabled bool NOT NULL`

**`platform.idempotency_keys`** (own-row) — PK `(user_id, key)` (`user_id` FK users ON DELETE CASCADE, `key uuid`), `request_sha256 text NOT NULL`, `response_status int NULL` (NULL while the first request is in flight), `response_body jsonb NULL`, `expires_at timestamptz NOT NULL` (+24 h); RLS enabled with `user_id = current user`, not forced, so the worker's ID-only sweep function can list expired keys. **`response_body` never holds secrets** (an invitation replay stores no link)

---

## 5. Reserved for v1 (design fixed now; created by additive migrations later)

| Table | Purpose | Integration point |
|---|---|---|
| `facts.events` (`org_id`, `type`, `occurred_on date`, `payload jsonb` validated per type) | Event Triggers (C7) | Event → fact changes → re-evaluation |
| `obligations.evidence` (`obligation_id`, `storage_key`, `extracted_reference text`) | Evidence Vault (C9) | Links to `obligations` |
| `billing.*` | Subscriptions, entitlements | `tenancy.organizations.id` |

---

## 6. Cross-org system functions (worker only)

Jobs that must scan all organisations (daily reminder scan, re-evaluation after rule publication, deletion sweeper) call `SECURITY DEFINER` functions owned by `app_owner` that return **only IDs** (e.g., `obligations.due_for_reminder(p_on date) RETURNS TABLE(org_id uuid, obligation_id uuid)`). The worker then processes each organisation in its own transaction with `app.org_id` set, so all reads/writes still pass RLS. Each function call is audit-logged.

Housekeeping of user-scoped rows follows the same pattern per user (M3, hourly): `identity.expired_sessions(p_now, p_limit)` and `platform.expired_idempotency_keys(p_now, p_limit)` return only IDs (EXECUTE for `app_worker` only); the worker deletes each user's rows with `app.user_id` set. The session sweep writes one system audit row (`identity.sessions_swept`, count in metadata) per run that deleted anything; the idempotency-key sweep removes only replay records and is not audited.

---

## 7. Migration policy

- Alembic, one revision per change, **reviewed as SQL**; autogenerate output never merged unreviewed.
- Expand → migrate → contract for any rename/drop (never break the previous app version during deploy).
- Every FK gets an index in the same migration; every tenant table gets RLS + policy in the same migration.
- CI check: fails if a table with `org_id` lacks `FORCE ROW LEVEL SECURITY`, or if a migration creates an extension outside the allowlist.
