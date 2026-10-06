# BuildOne developer commands. Targets become functional during milestone M1 (docs/build-plan.md).
SHELL := /bin/bash
COMPOSE := docker compose --env-file infra/compose/.env -f infra/compose/compose.yml -f infra/compose/compose.dev.yml
BE := cd backend &&
FE := pnpm --dir frontend/app

.PHONY: setup dev down check lint fmt typecheck contracts test test-tenancy migrate migration openapi \
        rules-validate eval-rules eval-retrieval eval-ai ingest rule-draft frontend-check e2e audit

setup:            ## install backend + frontend deps and git hooks
	$(BE) uv sync
	$(FE) install
	pre-commit install

dev:              ## start local stack (db, minio, migrations, api, worker) + SPA
	$(COMPOSE) build api
	$(COMPOSE) up -d postgres minio
	$(COMPOSE) run --rm migrate
	$(COMPOSE) up -d api worker
	$(FE) dev

down:
	$(COMPOSE) down

check: lint typecheck contracts test rules-validate eval-rules frontend-check  ## everything CI runs (except e2e)

lint:
	$(BE) uv run ruff check . && uv run ruff format --check .

fmt:
	$(BE) uv run ruff check --fix . && uv run ruff format .

typecheck:
	$(BE) uv run mypy app

contracts:
	$(BE) uv run lint-imports

# Tests need a superuser URL for a Postgres server (local: the compose postgres on localhost:5432).
TEST_DATABASE_ADMIN_URL ?= postgresql+psycopg://postgres:postgres@localhost:5432/buildone
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
