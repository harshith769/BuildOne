# BuildOne — Product Vision (Core Idea)

> **Status:** v0.4 · Product definition phase · Last updated: 2026-10-06 (v3 direction from [status.md](status.md): incubators pay first, CA firms free, founders free core)
> **Scope of this document:** the product idea only — problem, users, features, business model, roadmap.
> **Out of scope (separate docs, later):** technology stack, system design, data pipeline, database schema, APIs, infrastructure.

**What this document answers**
- What is BuildOne, who is it for, and what problem does it solve?
- What features does it offer, and in which phase?
- How does it make money, and how does it reach users?
- What makes it different and defensible?
- What is the roadmap from MVP to long-term vision?

---

## 1. One-liner, vision, mission

**One-liner**
> **BuildOne tells an incubator, its startups and their CAs which obligations and schemes apply to each company, why, and what's missing, using CA-reviewed rules.**

**Vision**
> Become the trusted compliance and eligibility layer for Indian startups and SMBs.

**Mission**
> No founder should fail, get penalised, or lose an opportunity because they didn't know what applied to them.

**Positioning statement**
> For **incubators and the early-stage Indian startups in their cohorts** — and the **CAs** who serve them — BuildOne is a **shared, living compliance and eligibility view** that turns each company's situation and official regulations into cited, CA-reviewed next steps. Founders and pre-founders without legal or compliance teams use the core free. **Unlike** filing marketplaces (which use tracking to sell services) or enterprise RegTech (built for compliance officers), BuildOne is **neutral, explainable, event-aware, and priced for startups.**

**Who pays (B2B2C):** incubators pay first (cohort licence); CA firms are free design partners and rule reviewers in Phases 1–2; founders use the core free; a fundraise-ready pack is a paid hypothesis to test (§9).

---

## 2. The problem

### 2.1 Core problem statement

> Early-stage Indian founders get penalised, delayed, or blocked during investor due diligence because **nobody continuously owns their compliance**. Obligations are created by the company's facts and by events (hiring, fundraising, growth, expansion); the rules are fragmented across central and state sources and change frequently. Founders discover what they owed only after a deadline passes.

### 2.2 The pre-founder problem

> Before a company exists, aspiring founders — students, working professionals, friend groups with an idea — have a **clarity problem**: they don't know whether the idea is real, whether the team is aligned, what personal legal risks they carry, which programs they're eligible for, or when and how to launch. Without connections, they either stall or launch on weak foundations that cause problems later.

### 2.3 The five questions every founder needs answered

1. **What applies to me?** — requirements specific to my situation
2. **Why does it apply?** — the condition and the source behind it
3. **What do I need?** — information, documents, registrations
4. **What do I do, and when?** — concrete, ordered actions with deadlines
5. **What changes later?** — events and regulatory updates that create new obligations

### 2.4 Why existing options fall short

| Option | Gap |
|---|---|
| Filing marketplaces (e.g., Zolvit/Vakilsearch, IndiaFilings, LegalWiz) | Service catalogues; tracking is a sales funnel; limited explanation |
| Enterprise RegTech (e.g., TeamLease RegTech) | Built and priced for enterprises with compliance officers |
| The founder's CA | Reactive; depends on the founder reporting events; knowledge not visible to founder |
| Generic AI chatbots / "AI idea validators" | Uncited, non-deterministic, no memory of company state, no accountability |
| Government portals | Authoritative but fragmented and not personalised |

---

## 3. Users

| Persona | Description | Core pain | Role in business |
|---|---|---|---|
| **Pre-founder team** | 1–4 people with an idea: students, working professionals, friends across cities | No validation method, no network, no launch plan, hidden personal legal risks | Free users; acquisition engine |
| **Early-stage founder** | Newly incorporated Pvt Ltd, first 24 months, no compliance staff | Missed deadlines, penalties, DD scramble, no visibility | Free core user; buyer of the fundraise-ready pack (hypothesis); Founder Pro in Phase 2 |
| **CA / small CA firm** | Manages 20–100 client companies | Tracking across clients in spreadsheets; clients don't report events | Free design partner and rule reviewer (Phases 1–2); distribution channel |
| **Incubator / college E-cell** | Runs cohorts of startups or student teams | Portfolio is messy at due diligence; pre-incubation is unstructured | **First payer** (cohort licence) + cohort channel |

---

## 4. Initial scope (wedge)

**In scope (MVP)**
- Geography: **Telangana** (Hyderabad first)
- Entity: **Private Limited** companies in their **first 24 months**, plus **pre-founder teams**
- Obligation domains: company law (ROC, post-incorporation), GST, income tax/TDS basics, Telangana state (professional tax, shops & establishments), threshold-based labour (PF/ESI)

**Out of scope (MVP)**
- Other states, LLP/OPC, public companies
- Industry-specific licences (food, drugs, fintech, etc.)
- Doing filings in-house (execution goes to partner CAs)
- Legal advice (BuildOne provides cited guidance, not legal opinions)

> All rules must be verified by a CA reviewer before publication. No regulatory claim is shipped without a citation.

---

## 5. Product structure: one journey, two products

```
Idea ──► Validated ──► Aligned ──► Launch-ready ──► Incorporated ──► Operating & compliant ──► Growing
└──────────────── Launchpad ─────────────────┘      └─────────────── BuildOne Core ──────────────────┘
```

- **Launchpad** — for pre-founders. Free. Takes a team from idea to launch-ready.
- **BuildOne Core** — for incorporated companies. Freemium. Keeps them compliant and due-diligence-ready.
- **Handoff** — Launchpad's facts (team, roles, structure choice) flow directly into Core at incorporation. No re-entry.

---

## 6. Features

Phase tags: **MVP** = Phase 1 · **v1** = Phase 2 · **v2** = Phase 3 (phases and dates in [roadmap.md](roadmap.md)). Moving a feature between phases needs the owner's OK recorded in [status.md](status.md); deferred scope is kept in [deferred.md](deferred.md).

### 6.1 Launchpad (pre-founders)

| # | Feature | What it does | Phase |
|---|---|---|---|
| L1 | **Team Space** | Shared workspace; each co-founder records their situation (student/employed, location, time and money commitment) | MVP |
| L2 | **Situation Check** ⭐ | Flags personal risks early — e.g., IP-ownership or outside-work clauses in an employment contract, university IP/incubation policies. Explains clauses with citations; always recommends professional review | MVP: questionnaire-only lite · v1: document clause extraction (D-5) |
| L3 | **Launch Roadmap** | When to incorporate (triggers: taking money, hiring, signing contracts, revenue), which structure fits, cost estimate, one-click handoff to Core | MVP |
| L4 | **Founder Alignment** | Guided conversations on roles, commitment, decisions, exits; equity-split framework; vesting explainer; draft founder term sheet for a lawyer to finalise | v1 |
| L5 | **Validation Sprint** | 2–4 week guided plan: hypotheses, interview-script generator, interview log, AI synthesis, evidence-based **go / pivot / stop** gate | v1 |
| L6 | **Opportunity Finder** | Pre-incubation programs, incubators, E-cells, hackathons, grants the team is **eligible for** — with reasons and deadlines | v1 |
| L7 | **Connect** | Office hours with partner CAs, incubators, mentors — through partners, not a social network | v2 |

### 6.2 BuildOne Core (incorporated companies)

| # | Feature | What it does | Phase |
|---|---|---|---|
| C1 | **Smart Intake** | Form-first onboarding (optional free text; document fact extraction as a stretch goal) → structured company facts, confirmed by the founder | MVP |
| C2 | **Launch Planner** | Registration sequence and document checklist for incorporation (own screen) | MVP |
| C3 | **Obligation Plan & Calendar** | Every applicable obligation with due date, form, authority, required documents | MVP |
| C4 | **"Why this applies" Explainer** | Plain-language reasoning tied to the company's facts, with verified source citations | MVP |
| C5 | **Founder Copilot** | Cited Q&A over curated official sources; routes "what do I owe" and "what if" questions to the rules engine; abstains and refers to a CA when unsure | v1 (D-4) |
| C6 | **Reminders** | Email (MVP) → WhatsApp (v1) | MVP |
| C7 | **Event Triggers** | Log hire / raise / new director / new office / turnover change → obligations recompute | v1 |
| C8 | **What-if Simulator** | "If we hire 10 / raise ₹50L / expand to Bengaluru, what changes?" | v1 |
| C9 | **Evidence Vault** | Upload receipts/acknowledgements → auto-extract → mark done → audit trail | v1 |
| C10 | **Compliance Health Score** | On-time, overdue, missing-evidence, upcoming — one view | v1 |
| C11 | **Due-Diligence Pack** | One-click compliance history export for investors and banks. **Fundraise-ready pack v0** (plan, status, gaps, citations; deterministic) ships in the MVP | MVP: v0 · v1: full |
| C12 | **Change Radar** | New regulatory notifications mapped to the company's affected obligations, with explanation | v2 |

### 6.3 CA Workspace

| # | Feature | Phase |
|---|---|---|
| A1 | Multi-client obligation dashboard (due, overdue, at risk) — **read-only view of companies shared by founders** | MVP: read-only · v1: full |
| A2 | Client event feed ("Client X hired 12 people — review PF/ESI") | v1 |
| A3 | Review, sign-off, task assignment to staff | v1 |
| A4 | White-label client portal | v2 |

### 6.4 Incubator & Campus

| # | Feature | Phase |
|---|---|---|
| I1 | Cohort onboarding (Launchpad for pre-incubation, Core for incubated companies) | MVP: invite cohort companies · v1: full |
| I2 | Portfolio compliance-health and DD-readiness view | MVP: cohort view v0 · v2: full |

### 6.5 Internal: Rule Studio (not user-facing)

| # | Feature | Phase |
|---|---|---|
| R1 | Source library of official documents (versioned) | MVP |
| R2 | AI-assisted rule drafting from sources, with citations | MVP |
| R3 | Human review/approval workflow (CA reviewer) + rule versioning | MVP |
| R4 | Evaluation suite run before any rule is published | MVP |
| R5 | Change-detection review queue (feeds C12) | v2 |

---

## 7. Core concept (technology-agnostic)

### 7.1 The engine

```
Situation facts  +  Cited rules  ──►  Personalised outcomes  ──►  Actions  ──►  Evidence
      ▲                  ▲                                                       │
   Events          Regulatory changes  ◄──────────── re-evaluate ◄──────────────┘
```

One engine, many outcomes:
- **Obligations** (Core) — what you must do
- **Eligibility** (Launchpad Opportunity Finder; future Benefits Finder) — what you can get
- **Risks** (Situation Check) — what could hurt you
- **Readiness** (Health Score, DD Pack, fundraise-ready pack) — how prepared you are

### 7.2 Role of AI and RAG

- **RAG is the knowledge backbone**: a curated, versioned corpus of official sources powers rule drafting, explanations, Q&A, and change detection.
- **Rules decide, RAG grounds, humans approve.** Applicability is determined by deterministic, versioned, cited rules — never by free-text LLM generation.
- **LLMs are used for:** optional free-text intake (text → proposed facts), optional rephrasing of explanations, cited Q&A, document/clause extraction, drafting rules for human review, impact summaries of regulatory changes. **Explanations are deterministic by default** (rule trace + CA-approved text + citations), so the core product works without AI.

### 7.3 Product principles (non-negotiable)

1. **Every claim is cited.** No citation → not shown as fact.
2. **Missing an obligation is the worst failure.** Optimise for recall; measure it.
3. **Deterministic where it matters.** Same facts → same obligations, every time.
4. **Abstain when unsure.** "Verify with a CA" beats a confident wrong answer.
5. **Guidance, not legal advice.** Execution and opinions go to licensed professionals.
6. **Neutral.** What is shown as required never depends on what we can sell.
7. **Facts are confirmed by the user.** AI-extracted facts are proposals until confirmed.

---

## 8. Differentiation

| Pillar | Meaning |
|---|---|
| **Personalised determination** | Outcomes computed from the user's actual facts |
| **Cited explainability** | Every item shows *why*, linked to the exact source |
| **Event awareness** | Hiring, raising, crossing thresholds → instant recomputation |
| **Change radar** | Regulatory updates mapped to *your* obligations |
| **Neutrality** | No upsell bias |
| **Idea-to-operating continuity** | One system from pre-founder to growing company |

| | Marketplaces | Enterprise RegTech | CA | **BuildOne** |
|---|---|---|---|---|
| Built for | Selling filings | Compliance teams | Clients who report to them | Founders without staff |
| Explains *why* | Rarely | For experts | Verbally | Always, cited |
| Reacts to company events | No | Partially | Manually | Core feature |
| Pre-founder support | No | No | Ad hoc | Launchpad |
| Startup pricing | Per service | High | Retainer | Freemium |

---

## 9. Business model

Current direction and prices to test: [status.md](status.md) (D-1, D-7, D-17…D-19, D-27). Changes need the owner's explicit OK ([AGENTS.md rule 19](../AGENTS.md)).

### 9.1 Model

**B2B2C: incubator cohort licences (first payer) → CA firms free as design partners and rule reviewers → founders free core + fundraise-ready pack → Founder Pro (Phase 2) → (later) API.** No referral fees or fee-sharing of any kind (CA Act).

### 9.2 Pricing hypotheses (to validate — not confirmed)

| Stream | Offer | Price hypothesis |
|---|---|---|
| **Incubator** (first payer) | Cohort view of every company's plan, gaps and readiness; Pro for cohort companies once Pro exists (Phase 2) | ₹1–3L per cohort per year, after a free pilot |
| **Fundraise-ready pack** | One-off export before a raise (v0 in the MVP; full pack later) | ₹4,999–9,999 one-time (to test in interviews) |
| **Launchpad** | All pre-founder features | Free |
| **Core Free** | Launch Planner, Obligation Plan, calendar, email reminders, limited Copilot (once Copilot ships, Phase 2) | Free |
| **CA firms** | Read-only view of shared clients (MVP); fuller workspace later | **Free in Phases 1–2**; a paid CA plan is deferred ([deferred.md §10](deferred.md#10-paid-ca-firm-plan)) |
| **Founder Pro** (Phase 2) | Events, What-if, Evidence Vault, Health Score, DD Pack, Change Radar, WhatsApp, unlimited Copilot, 3 seats | ₹1,499–2,499/year (D-27) |
| **Campus** | Launchpad for E-cells / pre-incubation cohorts | ₹25k–1L per institution/year (not yet revisited) |
| **API** (later) | Engine for neobanks, incorporation platforms, accounting software | Usage-based |

### 9.3 Why this model

- **Incubators** have a budget line and a reason to care (portfolio due diligence); one contract onboards a whole cohort.
- **CAs** review rules and bring 20–100 companies each; keeping them free in Phases 1–2 avoids competing with their fees.
- **Founders** get the core free, so the plan reaches every cohort company; they pay at the moment of pain (before a raise).
- **Launchpad** captures founders *before* incumbents see them; trust converts later.
- **Founder Pro** upgrades (Phase 2) are triggered by events (first hire, first raise) — when stakes rise.
- **No referrals, no in-house filing** → software margins, preserved neutrality, and no fee-sharing with CAs.

### 9.4 Targets

G2 (end Sep 2027): ~₹10L ARR run-rate, 20 CA firms active, incubators ready to renew. G3 (end of Phase 3): ~₹60L ARR. Gates and dates: [status.md](status.md), [roadmap.md](roadmap.md).

### 9.5 Superseded pricing (for history)

| Item | v1 hypothesis (28 Sep 2026) | Status |
|---|---|---|
| Core Pro | ₹499/month or ₹4,999/year | Superseded: Founder Pro in Phase 2 at ₹1,499–2,499/year (D-18, D-27) |
| CA Workspace | Free ≤ 5 clients; ₹150–250/client/month | Superseded: CA firms free in Phases 1–2 (D-17) |
| Execution referrals | 10–15% referral fee | Removed: no referral fees or fee-sharing (CA Act, D-1) |
| Year-2 target | ~₹79L ARR (Core Pro ₹30L, CA ₹28.8L, incubators ₹10L, campus ₹5L, referrals ~₹5L) | Superseded by the G2/G3 targets above |

### 9.6 Go-to-market (Hyderabad first)

1. **Incubators:** free pilot cohorts at Hyderabad incubators in exchange for feedback and case studies, converting to a paid cohort licence
2. **CA design partners:** 5–10 young CA firms review rules and use the CA view free
3. **Campus:** E-cells and student innovation clubs → Launchpad cohorts; campus ambassadors
4. **Free lead tools:** "What do I owe after incorporation?", "Is my employment contract a risk to my startup?" checkers
5. **Newly incorporated companies:** reach in first 30 days using public incorporation data (confirm data-protection compliance of outreach first)
6. **Founder communities:** plain-language content on real obligations and launch mistakes

---

## 10. Market snapshot (sources; verify before external use)

- FY26: 3,43,527 new entities registered in India (+37.54% YoY); 30 lakh+ registered companies, ~20.87 lakh active; ~2.12 lakh DPIIT-recognised startups — [Razorpay Rize FY25–26 report](https://prod-rize-internal.razorpay.com/rize/blogs/the-next-generation-of-indian-companies-fy-25-26-incorporation-report)
- Telangana is consistently a top-6 state for new companies (838 in June 2026; 1,206 in April 2025); Private Limited ≈ 93% of new companies — [QwikFilings MCA analysis, Jun 2026](https://qwikfilings.com/?p=381591), [Apr 2025](https://qwikfilings.com/?p=379530)
- Rough wedge estimate (unconfirmed): ~10–12k new Telangana companies/year → ~20–25k companies within their first 24 months at any time
- ICAI (June 2022): 3,58,524 members; 93,162 registered CA firms, 67,524 proprietorships — [ICAI Quick Insights 2022](https://pdicai.org/link/Quick-insight-2022/files/basic-html/page20.html)
- Enterprise benchmark: TeamLease RegTech tracks 1,536 Acts / 69,233 compliances with a 35+ legal-expert research team — [teamleaseregtech.com](https://www.teamleaseregtech.com/avantis-legal-research-team/)

---

## 11. Success metrics

| Stage | Metric |
|---|---|
| Launchpad activation | Team created + Situation Check completed |
| Launchpad outcome | % teams passing validation gate; % converting to incorporation via BuildOne |
| Core activation | Company profile confirmed + Obligation Plan generated |
| Engagement | % obligations completed on time with evidence; weekly active companies |
| Monetisation | Cohort contracts and renewals; fundraise-pack purchases; clients per CA firm; Free → Pro conversion (Phase 2) |
| Retention | 12-month logo retention; net revenue retention |
| **Trust (top priority)** | Obligation recall on evaluation set; citation accuracy; CA-flagged errors |

---

## 12. Moat

1. **Cited, versioned rule base** — expensive to build, compounds with every rule
2. **Evaluation datasets** — CA-verified scenarios prove accuracy
3. **Journey data** — how Indian startups actually evolve (idea → hire → raise → expand)
4. **CA and incubator network** — distribution + verification
5. **Trust brand** — "the one that shows its sources"

---

## 13. Roadmap

Phases, gates and dates: [status.md](status.md) and [roadmap.md](roadmap.md) (engineering order in [build-plan.md](build-plan.md)). Feature scope per phase:

### Phase 0 — Validate (Oct – 13 Dec 2026) · gate G0
- [ ] Interview 30 recently incorporated founders
- [ ] Interview 10 CAs and 3 incubator/E-cell managers
- [ ] Sign 1 CA reviewer and 1 lawyer
- [ ] Optional: interview ~10 pre-founders (students + working professionals)
- [ ] Confirm the buyer order (incubators → CAs → founders, D-1) from evidence
- [ ] Interview go-criteria (28 Sep): ≥60% founders report missed/late obligation or DD scramble; ≥2 CAs willing to trial; ≥50% pre-founders cite "don't know how to validate/launch" as top blocker
- [ ] **G0:** pain confirmed (flip rule), 3 pilot letters, CA reviewer signed, spike reports S1–S4 ([status.md](status.md))

### Phase 1 — MVP (14 Dec 2026 – ~May 2027) · gates G1a (local MVP), G1b (live pilot)
- [ ] Rule Studio: source library, rule drafting, review workflow, evaluation suite
- [ ] First ~30–50 CA-reviewed rules for the wedge
- [ ] Core: Smart Intake, Launch Planner, Obligation Plan & Calendar, Explainer, reminders + ICS
- [ ] Incubator cohort view and CA read-only view (shared companies)
- [ ] Fundraise-ready pack v0
- [ ] Launchpad lite: Team Space, Situation Check questionnaire, Launch Roadmap
- [ ] Pilot with one incubator cohort (10–20 companies) + 2–3 CA firms (after hosting is approved; [deferred.md](deferred.md))

### Phase 2 — Paid pilots (~May – Sep 2027) · gate G2
- [ ] Copilot (D-4)
- [ ] Situation Check document clause extraction (D-5)
- [ ] Launchpad: Founder Alignment, Validation Sprint, Opportunity Finder
- [ ] Core: Event Triggers, What-if, Evidence Vault, Health Score, full DD Pack, WhatsApp
- [ ] CA Workspace (A1–A3: event feed, fact-chasing, sign-off); Incubator/Campus cohort onboarding
- [ ] Launch paid tiers: Founder Pro, billing; convert pilots to paid

### Phase 3 — Scale (Oct 2027 – Sep 2028) · gate G3
- [ ] Karnataka + Maharashtra rules, LLP/OPC
- [ ] Gazette change tracking (Change Radar) + re-evaluation; public changelog
- [ ] Copilot (continues from Phase 2)
- [ ] **Benefits & Schemes Finder** (startup recognition, tax incentives, state subsidies) — same engine
- [ ] Connect (partner office hours); white-label CA portal; incubator portfolio view
- [ ] Industry modules: food, import-export, fintech, healthtech
- [ ] Labour-code coverage

### Phase 4 — Platform (2028+)
- [ ] Integrations with accounting, payroll, GST data → auto-derived facts (turnover, headcount)
- [ ] Document generation (board resolutions, registers) and form pre-fill
- [ ] Public API for banks, neobanks, incorporation and accounting platforms
- [ ] All Indian states; Telugu/Hindi voice interface
- [ ] Cross-border setup for Indian founders (e.g., US, Singapore)

### Future considerations (undecided)
- Whether CA Workspace becomes the primary product if founder willingness-to-pay is low
- Whether to license the rule base to other platforms
- Whether to offer an execution guarantee with partner CAs
- Expansion to non-startup SMBs (shops, traders, clinics)

---

## 14. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Wrong guidance / liability | Deterministic rules, citations, abstention, CA review, clear "not legal advice" terms |
| Rule-base maintenance cost | Narrow scope, AI-assisted drafting and change detection, CA design partners |
| Incumbents add AI | Compete on neutrality, event depth, explainability, pre-founder continuity |
| Low founder willingness to pay | Incubators pay first; founder core stays free; pack and Pro tested separately |
| Launchpad scope creep into generic "startup advice" | Keep Launchpad tied to the engine: facts, cited risks, eligibility, evidence |
| Professional-services regulation | Stay software + guidance; licensed partners execute and advise |
| Sensitive user data (contracts, IDs, financials) | Privacy-by-design; data-protection compliance; minimal retention (detail in security doc) |

---

## 15. Example journeys

**Pre-founders — three friends**
Student + software engineer + sales executive in another city → Team Space → Situation Check flags the engineer's contract clauses → reviewed before building → Validation Sprint (20 interviews, **go**) → Founder Alignment (roles, split with vesting) → Opportunity Finder surfaces an eligible pre-incubation program → Launch Roadmap triggers incorporation → handoff to Core → Obligation Plan live on day 1.

**Early-stage founders — two-founder SaaS in Hyderabad**
Incorporated Pvt Ltd → Smart Intake → Obligation Plan with post-incorporation deadlines and "why" → first hire logged → state and labour obligations appear → seed raise simulated in What-if → event logged → new filings tracked → DD Pack exported for investors.

---

## 16. Glossary

| Term | Meaning |
|---|---|
| **Fact** | A confirmed attribute of a team or company (entity type, state, headcount, turnover, etc.) |
| **Event** | A change to facts (hire, raise, new director, new office, threshold crossed) |
| **Rule** | A versioned, cited condition: *if facts match → outcome applies* |
| **Citation** | Link from a rule or explanation to an exact span in an official source |
| **Obligation** | A concrete instance of a rule for one company, with due date, owner, status |
| **Eligibility** | A program, benefit, or opportunity a team/company qualifies for |
| **Evidence** | Proof an obligation was completed (acknowledgement, receipt, reference number) |
| **Launchpad** | Pre-founder product (idea → launch-ready) |
| **Core** | Incorporated-company product (compliance and readiness) |
| **Rule Studio** | Internal tool to draft, review, version, and evaluate rules |

---

## 17. Related documents

Technical and operational decisions live in separate documents. The full index, with status, is in [`docs/README.md`](README.md).
