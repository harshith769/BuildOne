# BuildOne Documentation Index

**What this document answers**
- Which documents exist, what each one owns, and their status
- Which decisions are frozen for the build and which remain open
- Which gates need a human outside engineering (CA, lawyer, users)

Each fact has one home; other documents link to it. **Start here:** [status.md](status.md), then [build-plan.md](build-plan.md).

## Status legend

✅ Ready · 🧊 Frozen for MVP build (changes need an ADR) · 🟡 Proposed (decided by a spike) · ⬜ Planned · 🔒 External gate

## Product and planning

| Document | Owns | Status |
|---|---|---|
| [product-vision.md](product-vision.md) | Problem, users, features, business model, product roadmap | ✅ |
| [requirements.md](requirements.md) | Functional requirements + acceptance criteria | ✅ |
| [nfr.md](nfr.md) | Availability, performance, security, privacy, AI gates, cost | ✅ |
| [roadmap.md](roadmap.md) | Phases, gates, cut-lines, infrastructure milestones | ✅ |
| [status.md](status.md) | Current phase, decisions D-1…D-16, contradictions, lessons, next action (wins over older docs until session A) | ✅ |
| [build-plan.md](build-plan.md) | Architecture freeze, Claude Code protocol, milestone briefs M0–M14 | ✅ |
| [ux-screens.md](ux-screens.md) | MVP screen inventory and required states | ✅ |

## Architecture and design (frozen for the MVP build)

| Document | Owns | Status |
|---|---|---|
| [tech-stack.md](tech-stack.md) | Technologies, ₹0 budget, open seams, deferred tech | ✅ |
| [architecture.md](architecture.md) | Modules, dependencies, flows, deployment topology, growth path | 🧊 |
| [data-model.md](data-model.md) | Tables, constraints, roles, RLS, reserved v1 tables | 🧊 |
| [auth-and-tenancy.md](auth-and-tenancy.md) | Sign-in, sessions, CSRF, role matrix, enforcement layers | 🧊 |
| [api-conventions.md](api-conventions.md) | URLs, errors, pagination, idempotency, streaming, client generation | 🧊 |
| [rules-engine.md](rules-engine.md) | Rule and fact formats, three-valued logic, schedules, publication | 🧊 (validated by S3) |
| [data-pipeline.md](data-pipeline.md) | Ingestion, chunking, retrieval algorithm | 🧊 (parser/embedder by S1/S2) |
| [ai-system.md](ai-system.md) | Gateway, task registry, budgets, privacy, citation verification | 🧊 (models by S4) |
| [deployment.md](deployment.md) | Containers, CI/CD, backups/restore, observability, runbook list | 🧊 (validated by S5) |
| [security-design.md](security-design.md) | Threats, controls, secrets, known limitations | ✅ |
| [testing-strategy.md](testing-strategy.md) | Test levels, doubles, CI budget | ✅ |
| [evaluation.md](evaluation.md) | Golden sets, metrics, when they run | ✅ |
| [rule-operations.md](rule-operations.md) | Rule SOP, CA checklist, incidents | ✅ · 🔒 CA reviewer |
| [adr/](adr/) | ADR-0001…0012: Accepted except ADR-0009 (🟡 until spike S3) and ADR-0012 (🟡 Proposed, decided by S5); ADR-0006 superseded in part | ✅ / 🟡 |
| [spikes/](spikes/) | Spike reports S1–S5 (template provided) | ⬜ Phase 0 |
| [runbooks/](runbooks/) | Operational procedures (list in [deployment.md §7](deployment.md#7-runbooks-written-in-m4-and-m13-under-docsrunbooks)) | ⬜ M4, M13 |

## Repository and agents

| File | Owns | Status |
|---|---|---|
| [../AGENTS.md](../AGENTS.md) + [../CLAUDE.md](../CLAUDE.md) + `../.claude/` | Agent commands, mandatory rules, pitfalls, path-scoped rules, permissions | ✅ |
| [../README.md](../README.md) · [../CONTRIBUTING.md](../CONTRIBUTING.md) | Overview/quick start · workflow and PR checklists | ✅ |

## Planned later

| Document | When |
|---|---|
| integrations.md (email provider, later WhatsApp) | M8 |
| legal/ (terms, privacy notice, disclaimers, DPDP, CA data agreement) | Before pilot · 🔒 lawyer |
| billing.md, cost-model.md, analytics.md | After pilot, before paid launch |

## External gates

| Gate | Owner | Blocks |
|---|---|---|
| Customer interviews (Phase 0) | Founder | Pricing, buyer choice |
| Rule accuracy sign-off | CA reviewer | Any rule reaching users |
| Legal documents and disclaimers | Lawyer | Pilot with real users |
| Security review | External reviewer (recommended) | Paid launch |
| Azure for Students eligibility (bonus only) | Founder, via Azure portal | Nothing — optional staging / month-12 landing spot |
