# BuildOne — MVP Screen Inventory

> **Status:** v1.0 · 2026-09-28 · Owner: @harshith769
> Behaviour lives in [requirements.md](requirements.md). This file lists the screens, their data, and required states so the frontend has a fixed scope.

**What this document answers**
- Which screens exist in the MVP app, per persona
- Which API data each screen needs
- Which states every screen must handle

## 1. Global

- **Shell:** org switcher, nav (Launchpad or Company sections by org type), notifications bell, account menu.
- **Every data screen handles:** loading, empty, error (with request ID), no-permission (viewer), and — where AI is involved — `limit_reached` and `ai_unavailable`.
- **Disclaimer component** (FR-PLT-08) on every guidance screen.
- Mobile-first responsive ≥ 360 px; WCAG 2.2 AA.

## 2. Screens

| # | Screen | Persona | Main data / actions | Req |
|---|---|---|---|---|
| S1 | Sign-in / callback | All | Redirect to AuthKit | FR-PLT-01 |
| S2 | Consent + 18+ confirmation | All (first sign-in) | Terms/privacy versions | FR-PLT-01/06 |
| S3 | Create organisation (team or company) | All | Type, name | FR-PLT-02 |
| S4 | Members & invitations | Owner | List, invite, roles, remove | FR-PLT-03/04 |
| S5 | Launchpad home | Pre-founder | Idea, members' profiles, check results summary, roadmap status | FR-LP-01 |
| S6 | My situation profile + questionnaire | Pre-founder | Member facts form | FR-LP-01/02 |
| S7 | Situation Check results + document upload | Pre-founder | Flags with reasons; upload; clause findings; privacy toggle | FR-LP-02 |
| S8 | Launch Roadmap | Pre-founder | Triggers, structure comparison, cost breakdown, "We're incorporating" | FR-LP-03 |
| S9 | Company profile (form-first intake) | Founder | Fact form grouped by section; "I don't know"; optional free-text → proposals review | FR-CORE-01 |
| S10 | Proposals review | Founder | Proposed facts with source sentence; accept/edit/reject | FR-CORE-01 |
| S11 | Launch Planner | Founder (pre-incorporation) | Ordered steps, documents | FR-CORE-02 |
| S12 | Obligation plan (list + calendar views) | Founder | Filters: urgency, domain, state; `needs_info` banner linking to missing facts | FR-CORE-03 |
| S13 | Obligation detail | Founder | Deterministic explanation, citations drawer, documents, mark done, history, "Explain in simpler words" | FR-CORE-03/04 |
| S14 | Copilot | Founder | Chat with streaming, citations, route badges, quota indicator, feedback | FR-CORE-05 |
| S15 | Notifications panel | All | In-app reminders; mark read | FR-CORE-06 |
| S16 | Settings | All | Profile, sessions (revoke), notification preferences, calendar feed (copy/rotate), data export, delete account | FR-PLT-06/07, FR-CORE-06 |
| S17 | Organisation settings | Owner | Rename, export, delete | FR-PLT-06 |

## 3. Marketing site (Astro)

Landing page · "What do I owe after incorporation?" free tool (public, uses `/v1/public/...` with a generic fact set, no sign-in) · Privacy · Terms · Contact/grievance.
