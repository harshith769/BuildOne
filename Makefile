# BuildOne developer commands. Targets become functional during milestone M1 (docs/build-plan.md).
SHELL := /bin/bash
COMPOSE := docker compose --env-file infra/compose/.env -f infra/compose/compose.yml -f infra/compose/compose.dev.yml
BE := cd backend &&
FE := pnpm --dir frontend/app

.PHONY: setup dev down test-role check lint fmt typecheck contracts test test-tenancy migrate migration openapi \
        rules-validate eval-rules eval-retrieval eval-ai ingest rule-draft frontend-check e2e audit

setup:            ## install backend + frontend deps and git hooks
	$(BE) uv sync
	$(FE) install
	pre-commit install

dev:              ## start local stack (db, s3, migrations, api, worker) + SPA
	$(COMPOSE) build api
	$(COMPOSE) up -d postgres s3
	$(COMPOSE) run --rm migrate
	$(MAKE) test-role
	$(COMPOSE) up -d api worker
	$(FE) dev

down:
	$(COMPOSE) down

# LOCAL DEV ONLY (never CI or any hosted environment): a throwaway superuser for backend tests and E2E, so
# nobody needs the real superuser password from infra/compose/.env. Idempotent; `make dev` recreates it after
# a volume reset. Uses the container's local socket (trust auth), so no password is read.
test-role:        ## create the local-only test superuser buildone_test if missing
	docker exec -i buildone-postgres-1 psql -U postgres -d buildone -v ON_ERROR_STOP=1 -q <<< \
	  "DO \$$\$$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'buildone_test') THEN \
	   CREATE ROLE buildone_test SUPERUSER LOGIN PASSWORD 'buildone-test-only'; END IF; END \$$\$$;"

check: lint typecheck contracts test rules-validate eval-rules frontend-check  ## everything CI runs (except e2e)

lint:
	$(BE) uv run ruff check . && uv run ruff format --check .

fmt:
	$(BE) uv run ruff check --fix . && uv run ruff format .

typecheck:
	$(BE) uv run mypy app

contracts:
	$(BE) uv run lint-imports

# Tests need a superuser URL for a Postgres server. Locally: the compose postgres with the local-only
# `buildone_test` role (`make test-role`); set POSTGRES_HOST_PORT=5433 if your .env uses that port.
# An exported TEST_DATABASE_ADMIN_URL always wins (CI sets its own).
POSTGRES_HOST_PORT ?= 5432
TEST_DATABASE_ADMIN_URL ?= postgresql+psycopg://buildone_test:buildone-test-only@localhost:$(POSTGRES_HOST_PORT)/buildone
export TEST_DATABASE_ADMIN_URL

test:
	$(BE) uv run pytest -q

test-tenancy:
	$(BE) uv run pytest -q tests/tenancy

migrate:          ## apply migrations as app_owner (compose `migrate` service)
	$(COMPOSE) run --rm migrate

migration:
	$(BE) uv run alembic revision -m "$(m)"

openapi:
	$(BE) uv run python -m app.tools.export_openapi ../frontend/app/src/api/openapi.json
	$(FE) run gen:api

rules-validate:
	$(BE) uv run python -m app.modules.rules.validate ../rules

eval-rules:
	$(BE) uv run python -m app.modules.rules.scenarios ../rules

eval-retrieval:
	$(BE) uv run python -m app.modules.knowledge.eval ../evals/retrieval.jsonl

eval-ai:
	$(BE) uv run python -m app.modules.ai.eval --task $(TASK) --n $(N)

ingest:
	$(BE) uv run python -m app.modules.knowledge.ingest --source $(SOURCE)

rule-draft:
	$(BE) uv run python -m app.modules.rules.draft --topic "$(TOPIC)"

frontend-check:
	@if [ -f frontend/app/package.json ]; then $(FE) lint && $(FE) typecheck && $(FE) build; fi

e2e:
	$(FE) exec playwright test

audit:
	$(BE) uv run pip-audit
