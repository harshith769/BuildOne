# BuildOne — Rule Operations SOP

> **Status:** v1.0 · 2026-09-28 · Owner: @harshith769 · 🔒 Requires a CA reviewer
> Format and engine: [rules-engine.md](rules-engine.md). This is the operating procedure for creating, reviewing, publishing, changing, and retiring rules.

**What this document answers**
- The step-by-step procedure for a new rule, and who does each step
- What the CA reviewer must check
- How incidents (a missed or wrong obligation) are handled

## 1. New rule procedure

| # | Step | Who | Output |
|---|---|---|---|
| 1 | Pick topic from the MVP scope list | Owner | Issue `rule: <topic>` |
| 2 | Register official sources in `knowledge/sources.yaml`; ingest | Owner | Active source versions |
| 3 | Draft: `make rule-draft TOPIC="…"` (Gemini free tier, public text only) | Owner | `rules/drafts/<id>.yaml` |
| 4 | Edit draft: tighten conditions, add facts to registry if needed, write plain-language explanation | Owner | Draft ready for review |
| 5 | Add/extend scenarios: ≥ 1 applies + ≥ 1 not_applicable (critical rules: ≥ 2 each) | Owner | `rules/scenarios/*.yaml` |
| 6 | CA review with checklist (§2); reviewer fields filled | CA | Approved draft |
| 7 | Move to `rules/published/<domain>/`; PR with `## Rule changes` section | Owner | PR |
| 8 | CI gates pass → merge → publication job | CI | New rule version live |

## 2. CA review checklist

- [ ] Applicability conditions match the law, including thresholds, entity types, and state scope
- [ ] Exceptions and provisos are represented (or explicitly out of scope and noted)
- [ ] Due-date logic and anchor are correct, including financial-year handling
- [ ] Current extensions/relaxations are captured as overrides with citations
- [ ] Citations point to the operative provision
- [ ] Plain-language summary and "what to do" are accurate and not misleading
- [ ] Penalty text (if present) is accurate and cited
- [ ] `criticality` is correct (critical = serious penalty or blocking consequence)
- [ ] Scenarios reflect real situations and expected outcomes

## 3. Changes

| Trigger | Action |
|---|---|
| Authority extends a deadline | New version with `overrides` entry + citation; publish before the original due date |
| Law/rule amended | New version with new `effective.from`; add scenarios covering before/after |
| Rule found wrong | Treat as incident (§4) |
| Topic out of scope / repealed | Retire with `effective.to` |

## 4. Incidents (missed or wrong obligation)

1. Severity **P0** if a critical obligation was missed or a wrong due date could cause a penalty.
2. Within 24 h: fix rule (new version) → publish → re-evaluation → notify affected organisations in-app with a plain explanation.
3. Add the failing case to scenarios (regression).
4. Log in `docs/runbooks/rule-incidents.md`: what, who affected, root cause, fix, prevention.

## 5. Cadence

- Weekly: check official sources in scope for new notifications/circulars (manual in MVP).
- Monthly: review Copilot "not helpful" feedback for rule gaps.
