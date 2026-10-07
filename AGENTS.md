# AGENTS.md — BuildOne

BuildOne is a compliance copilot for Indian startups: a Python 3.14 / FastAPI modular monolith on PostgreSQL 18 (pgvector, RLS) with a Procrastinate worker, a deterministic YAML rules engine, a RAG knowledge base, and a React + TypeScript SPA. MVP runs on one server via Docker Compose.

## Commands

| Task | Command |
|---|---|
| Install everything | `make setup` |
| Start local stack (Postgres, local S3 (SeaweedFS), API with reload, worker, SPA) | `make dev` · stop: `make down` |
| All checks (run before declaring any task done) | `make check` |
| Backend tests only / tenancy suite | `make test` · `make test-tenancy` |
| Lint + format / types / import contracts | `make lint` · `make typecheck` · `make contracts` |
| New migration (then review the SQL) / apply | `make migration m="<message>"` · `make migrate` |
| Regenerate OpenAPI + frontend client | `make openapi` |
| Rule schema validation / scenario suite | `make rules-validate` · `make eval-rules` |
| Retrieval eval / AI eval (uses free daily budget) | `make eval-retrieval` · `make eval-ai TASK=<task> N=<n>` |
| Ingest a source / draft a rule | `make ingest SOURCE=<key>` · `make rule-draft TOPIC="<topic>"` |
| Frontend E2E | `make e2e` |

Targets become functional during milestone M1 ([docs/build-plan.md](docs/build-plan.md)).

## Mandatory rules

1. **Do not change frozen decisions** listed in `docs/build-plan.md §1.1` — draft an ADR in `docs/adr/` with status Proposed and stop instead.
2. **Every tenant table has `org_id NOT NULL`, RLS enabled and forced, and the standard policy** in the same migration — tenant isolation fails closed only at the database ([docs/data-model.md §3](docs/data-model.md)).
3. **Take `org_id` only from the URL path after the membership check**, never from request bodies — prevents cross-tenant writes.
4. **Access another module only through its `service.py`**; never import another module's `models.py` or query its tables — keeps modules extractable.
5. **`app/modules/rules`, `obligations`, and `notifications` must not import `app/modules/ai`** — core compliance must work with AI down (CI-enforced).
6. **Provider SDKs (groq, google-genai, workos, boto3) are imported only in their adapter modules** — portability ([docs/adr/0011-portability-rules.md](docs/adr/0011-portability-rules.md)).
7. **Never switch an AI call to a paid tier or another provider class on failure**; raise and let the caller degrade — the MVP must never auto-spend.
8. **Tasks marked `user_data` may route only to providers with `user_data_allowed: true`** — privacy rule ([docs/ai-system.md §2](docs/ai-system.md)).
9. **The rules engine reads only confirmed facts** from `facts.facts`; proposals never influence obligations.
10. **Unknown facts produce `needs_info`, never silent exclusion** — a missed obligation is the worst failure.
11. **Legal due dates are `date` values computed in `Asia/Kolkata`**; instants are UTC `timestamptz`; money is integer paise; IDs are UUIDv7.
12. **No side effects inside a DB transaction** (email, HTTP, AI calls); enqueue a job in the same transaction and make the job idempotent.
13. **Migrations are reviewed SQL and backward compatible** (expand → migrate → contract); never edit a merged migration.
14. **Tests hit a real Postgres**; mock only external boundaries (identity, AI, email, clock). Never mock the database.
15. **Never write regulatory facts (thresholds, dates, forms) into code**; they live only in cited rule files under `rules/`.
16. **No real personal data in fixtures, evals, logs, or commits**; use synthetic data.
17. **Do not read or print `.env` files or secrets.**
18. **Update the owning doc in the same change** when behaviour differs from `docs/` (each fact has one home).
19. **Never remove, shrink or change a product feature or the business model without the owner's explicit OK** (recorded in `docs/status.md`). Anything deferred keeps its full scope in [docs/deferred.md](docs/deferred.md).

## Known pitfalls

- **`SET LOCAL` is per transaction**: set `app.user_id`/`app.org_id` at the start of every transaction, including in jobs; `current_setting(name, true)` returns NULL when unset (fails closed).
- **Table owner bypasses RLS unless `FORCE ROW LEVEL SECURITY`** is set; services must never connect as `app_owner`.
- **Tenancy checks are owned by `app_rls_check`** (NOLOGIN, BYPASSRLS; ADR-0013): new company-data tables use `app.platform.rls.company_data_policies()`; `tenancy.can_read` goes only in SELECT policies. Never use `RETURNING` on a table whose SELECT policy the writer can't pass yet (`organizations`, `audit.events`). Existing local volumes need `make db-roles` (run by `make dev`).
- **pgvector's extension name is `vector`**, and extensions are created by the superuser in `infra/postgres/initdb/`, not in Alembic.
- **Procrastinate lives in its own `procrastinate` schema** and its SQL is unqualified: every connection sets `search_path=procrastinate,public` and `timezone=UTC` (`app.platform.db.CONNECT_OPTIONS`). Module tables are always schema-qualified.
- **IDs come from `app.platform.ids.new_id()`** (stdlib `uuid.uuid7()`, Python 3.14); never `uuid4()` for stored IDs.
- **Backend tests need `TEST_DATABASE_ADMIN_URL`** (a superuser URL); each run creates and drops its own database and the five roles if missing. Locally the Makefile defaults it to the `buildone_test` role that `make test-role` creates (local dev only, never used in CI or any hosted environment); set `POSTGRES_HOST_PORT=5433` if your `.env` uses that port.
- **`UNIQUE NULLS NOT DISTINCT`** is required where `member_user_id` may be NULL.
- **Month arithmetic clamps to month end**; financial year runs 1 Apr–31 Mar; test month-end and FY boundaries with a frozen clock.
- **The server is small (1–2 GB RAM, ADR-0012)**: never load ML models in the API process; embeddings/parsing run in the worker or the ingestion CLI.
- **Postgres 18 images store data in `/var/lib/postgresql/18/docker`**: mount volumes at `/var/lib/postgresql`, never `/var/lib/postgresql/data`.
- **Managed Postgres has no superuser**: extensions must be on the provider's allowlist; keep everything in `infra/postgres/initdb/` reproducible as plain SQL run by the admin role.
- **Income tax rules cite the Income-tax Act, 2025** (in force from 1 Apr 2026; TDS is in sections 392–394), never the 1961 Act.
- **Gemini free tier is for public source text only**; Groq requires Zero Data Retention enabled (`GROQ_ZDR_ENABLED=true`) before user data is sent.
- **Calendar feed URLs carry a capability token** (documented exception); never log full request URLs for `/v1/calendar/`.
- **PyYAML parses dates into `date` objects**: normalise to ISO strings before JSON Schema validation.
- **`rules/examples/` is illustrative**, not legal content; the scenario runner ignores it.
- **Knowledge rows are never deleted**: a new source version supersedes the old one (`status`, `is_active`); DELETE is revoked so citations keep resolving. Ingestion (PyMuPDF, Tesseract, uv group `ingest`) runs only on the laptop and in CI, never in the server image; the embedding model loads only in the ingestion CLI and the embedder sidecar.
- **Retrieval labels use M5 tree paths** (`<source_key>::CHAPTER II > 3 > (1)`); a parser or tree change that moves paths fails `make eval-retrieval` with "unresolved label" — fix the label, don't loosen the matcher.

## Related documentation

Start at [docs/README.md](docs/README.md). Key: [build-plan.md](docs/build-plan.md) · [architecture.md](docs/architecture.md) · [data-model.md](docs/data-model.md) · [rules-engine.md](docs/rules-engine.md) · [ai-system.md](docs/ai-system.md) · [api-conventions.md](docs/api-conventions.md) · [auth-and-tenancy.md](docs/auth-and-tenancy.md) · [testing-strategy.md](docs/testing-strategy.md) · [CONTRIBUTING.md](CONTRIBUTING.md).
