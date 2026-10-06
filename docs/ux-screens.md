# BuildOne — MVP Screen Inventory

> **Status:** v1.1 · 2026-10-06 (v3: 6 MVP screens) · Owner: @harshith769
> Behaviour lives in [requirements.md](requirements.md). This file lists the screens, their data, and required states so the frontend has a fixed scope.
> The prototype website is only a rough visual idea, **not a spec**; where it differs from this file or requirements.md, these documents win.

**What this document answers**
- The 6 MVP screens and how they map to the full screen list
- Which screens exist in the MVP app, per persona
- Which API data each screen needs
- Which states every screen must handle

## 1. Global

- **Shell:** org switcher, nav (Launchpad, Company, CA firm or Incubator sections by org type), notifications bell, account menu.
- **Every data screen handles:** loading, empty, error (with request ID), no-permission (viewer), and — where AI is involved — `limit_reached` and `ai_unavailable`.
- **Disclaimer component** (FR-PLT-08) on every guidance screen.
- Mobile-first responsive ≥ 360 px; WCAG 2.2 AA.

## 2. The 6 MVP screens

From [status.md](status.md). Each maps to one or more rows of the full list in §3.

| # | MVP screen | Screens (§3) | Priority | Milestone |
|---|---|---|---|---|
| 1 | Smart intake | S9, S10 | MUST (document upload: stretch) | M8 |
| 2 | Obligation plan | S12 | MUST | M8 |
| 3 | Obligation detail (with effective date) | S13 | MUST | M8–M9 |
| 4 | Reminders + ICS | S15, S16 (calendar feed) | MUST | M8 |
| 5 | Incubator and CA view | S18, S19, S20 | MUST | M10 |
| 6 | Fundraise-ready pack v0 | S21 | MUST (built regardless, D-19) | M10 |

Also in the MVP at their existing priority: platform screens (S1–S4, S16, S17), Launch Planner on its own screen (S11, M9), Launchpad lite (S5–S8, M11; S7 questionnaire results only — document upload is deferred). Copilot (S14) is Phase 2.

## 3. Screens

| # | Screen | Persona | Main data / actions | Req |
|---|---|---|---|---|
| S1 | Sign-in / callback | All | Redirect to AuthKit | FR-PLT-01 |
| S2 | Consent + 18+ confirmation | All (first sign-in) | Terms/privacy versions | FR-PLT-01/06 |
| S3 | Create organisation (team or company) | All | Type, name | FR-PLT-02 |
| S4 | Members & invitations | Owner | List, invite, roles, remove | FR-PLT-03/04 |
| S5 | Launchpad home | Pre-founder | Idea, members' profiles, check results summary, roadmap status | FR-LP-01 |
| S6 | My situation profile + questionnaire | Pre-founder | Member facts form | FR-LP-01/02 |
| S7 | Situation Check results + document upload | Pre-founder | Flags with reasons. **Later (Phase 2, [deferred.md §8](deferred.md#8-situation-check-clause-extraction-document-check)):** upload; clause findings; privacy toggle | FR-LP-02 |
| S8 | Launch Roadmap | Pre-founder | Triggers, structure comparison, cost breakdown, "We're incorporating" | FR-LP-03 |
| S9 | Company profile (form-first intake) | Founder | Fact form grouped by section; "I don't know"; optional free-text → proposals review; stretch: upload COI/MoA/PAN → proposals | FR-CORE-01 |
| S10 | Proposals review | Founder | Proposed facts with source sentence; accept/edit/reject | FR-CORE-01 |
| S11 | Launch Planner | Founder (pre-incorporation) | Ordered steps, documents | FR-CORE-02 |
| S12 | Obligation plan (list + calendar views) | Founder | Filters: urgency, domain, state; `needs_info` banner linking to missing facts | FR-CORE-03 |
| S13 | Obligation detail | Founder | Deterministic explanation (conditions vs company values), rule version, **effective date**, CA reviewer, citations drawer, documents, mark done, history, "Explain in simpler words" | FR-CORE-03/04 |
| S14 | Copilot (**Phase 2**) | Founder | Chat with streaming, citations, route badges, quota indicator, feedback | FR-CORE-05 |
| S15 | Notifications panel | All | In-app reminders; mark read | FR-CORE-06 |
| S16 | Settings | All | Profile, sessions (revoke), notification preferences, calendar feed (copy/rotate), data export, delete account | FR-PLT-06/07, FR-CORE-06 |
| S17 | Organisation settings | Owner | Rename, export, delete | FR-PLT-06 |
| S18 | Sharing (company side) | Founder (owner) | Share with a CA firm; accept an incubator cohort invitation; list and revoke grants | FR-PART-01/02 |
| S19 | CA firm clients | CA firm member | Shared client companies with overdue / due soon / `needs_info` counts; open a client's plan and obligation detail read-only | FR-PART-01 |
| S20 | Incubator cohort dashboard | Incubator member | Cohort companies: plan generated, overdue and `needs_info` counts, pack status; invite companies; open a plan read-only | FR-PART-02 |
| S21 | Fundraise-ready pack v0 | Founder | Preview, generate and download the pack; gaps list linking to missing facts | FR-CORE-13 |

## 4. Marketing site (Astro)

Landing page · "What do I owe after incorporation?" free tool (public, uses `/v1/public/...` with a generic fact set, no sign-in) · Privacy · Terms · Contact/grievance.
