# BuildOne

Compliance and eligibility engine for young Indian companies. Incubators, their startups and their CAs see which obligations and schemes apply to each company, why, and what's missing, using CA-reviewed rules with sources.

**Status:** Phase 0 (validation); M1 (foundation) done, building local-first. See [docs/status.md](docs/status.md). MVP scope: Telangana, Private Limited companies in their first 24 months.

**Licence:** this repository is public but has **no licence — all rights reserved**. No permission is granted to use, copy, modify or distribute the code beyond what GitHub's Terms of Service allow for public repositories.

## Prerequisites

- Windows with **WSL2 (Ubuntu)**; clone into the Linux filesystem (`~/code/BuildOne`), never OneDrive
- Docker Desktop with WSL integration (`docker compose version` works inside WSL)
- `uv` (installs Python 3.14 from `backend/.python-version`): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Node.js 24 LTS and `pnpm` (from M1; version pinned in `frontend/app/package.json`)
- `make`, `git`, `gh` (GitHub CLI), `pre-commit` (`uv tool install pre-commit`)

## Quick start

```bash
cp infra/compose/.env.example infra/compose/.env   # fill local values; never commit
corepack enable    # provides the pnpm version pinned in frontend/app/package.json
make setup
make dev           # migrations run automatically · API http://localhost:8000 · SPA http://localhost:5173
export TEST_DATABASE_ADMIN_URL=postgresql+psycopg://postgres:<POSTGRES_PASSWORD from .env>@localhost:5432/buildone
make check         # all checks (backend tests use a throwaway database)
make e2e           # Playwright (first time: pnpm --dir frontend/app exec playwright install chromium)
```

## Documentation

- Current phase, decisions, next action: [docs/status.md](docs/status.md)
- Product: [docs/product-vision.md](docs/product-vision.md)
- How to build it: [docs/build-plan.md](docs/build-plan.md)
- Deferred work (full scope + triggers): [docs/deferred.md](docs/deferred.md)
- Everything else: [docs/README.md](docs/README.md)
- Coding agents: [AGENTS.md](AGENTS.md)

BuildOne provides guidance with sources, not legal or tax advice.
