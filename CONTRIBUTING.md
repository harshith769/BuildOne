# Contributing

## Workflow
- Branch per milestone or change: `m<N>-<slug>` or `fix/<slug>`; never commit to `main` directly (branch protection requires CI).
- Conventional commits: `feat(<module>): …`, `fix(<module>): …`, `docs: …`, `rules: …`, `ci: …`, `chore: …`.
- Every PR: `make check` green, tests for new logic and endpoints, docs updated where behaviour changed.

## PR checklist
- [ ] No frozen decision changed (see `docs/build-plan.md §1.1`) — or an ADR is attached
- [ ] New tenant tables: RLS forced + policy + cross-tenant tests
- [ ] Migrations reviewed as SQL, backward compatible
- [ ] No secrets, no real personal data
- [ ] Prompt/model/retrieval changes include before/after eval numbers

## Rule PRs (`rules/**`)
- Description must include a `## Rule changes` section (becomes the publication changelog).
- `review.reviewed_by` / `reviewed_on` filled by the CA reviewer only.
- Scenarios added or updated; `make rules-validate eval-rules` green.
- Procedure: [docs/rule-operations.md](docs/rule-operations.md).
