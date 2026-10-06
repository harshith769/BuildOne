# BuildOne — Rules Engine

> **Status:** v1.0 (frozen for MVP build; validated by spike S3) · 2026-09-28 · Owner: @harshith769
> Decision record: [ADR-0009](adr/0009-rules-as-code.md). Machine-readable schema: [`rules/schema/rule.schema.json`](../rules/schema/rule.schema.json). Review process: [rule-operations.md](rule-operations.md).

**What this document answers**
- The exact format of a rule file and of the fact registry
- How conditions are evaluated, including unknown facts (three-valued logic)
- How due dates and recurring periods are computed
- How versions, deadline extensions, and publication work
- What an evaluation trace contains and how scenarios test rules

---

## 1. Files and locations

| Path | Content |
|---|---|
| `rules/facts.yaml` | Fact registry: every fact key a rule may reference |
| `rules/schema/rule.schema.json` | JSON Schema for rule files (CI-enforced) |
| `rules/drafts/**.yaml` | AI- or human-drafted rules; never published |
| `rules/published/<domain>/<rule_id>.yaml` | Reviewed rules; the only input to publication |
| `rules/scenarios/**.yaml` | CA-verified company scenarios with expected outcomes |
| `rules/examples/` | Illustrative format examples; never published; ignored by the scenario runner |

Engine code: `backend/app/modules/rules/` — `schema.py` (Pydantic models mirroring the JSON Schema), `evaluator.py` (pure functions), `dates.py`, `publish.py`.

---

## 2. Fact registry (`rules/facts.yaml`)

```yaml
registry_version: 1
facts:
  - key: entity_type
    subject: org            # org | member
    value_type: enum        # bool | int | date | enum | enum_list | money_paise | state_code | text
    allowed_values: [pvt_ltd, llp, opc, not_incorporated]
    org_types: [company]
    label: "Legal structure"
    help: "The structure on your certificate of incorporation."
```

Rules: keys are immutable once published; removing a key requires retiring every rule that uses it; the registry is loaded into `facts.fact_definitions` at publication.

---

## 3. Rule file format

```yaml
id: mca.example_commencement_declaration   # ^[a-z0-9_]+(\.[a-z0-9_]+)+$ ; never reused
version: 1
title: "Declaration of commencement of business"
domain: company_law        # company_law | gst | income_tax | labour | state_tg | launchpad
kind: obligation           # obligation | risk_check | roadmap_trigger
subject: org               # org | member
applies_to_org_types: [company]
jurisdiction: IN           # IN | IN-TG
authority: "MCA / ROC"
effective: { from: 2000-01-01, to: null }   # EXAMPLE dates only
criticality: critical      # critical | standard  (critical = zero-miss gate)

applies_if:                # condition (§4)
  all:
    - { fact: entity_type, op: in, value: [pvt_ltd] }
    - { fact: has_share_capital, op: is_true }

obligation:                # required when kind = obligation
  form: "INC-20A"          # optional
  schedule:                # §5
    type: one_time
    due: { anchor: incorporation_date, offset: { days: 180 } }
  documents: ["Board resolution", "Proof of subscription money received"]
  overrides: []            # deadline extensions (§6)

explanation:               # CA-approved; powers the deterministic Explainer
  summary: "Companies with share capital must file a declaration that subscribers have paid for their shares before starting business."
  what_to_do:
    - "Collect proof that each subscriber paid for their shares."
    - "File the declaration on the MCA portal before the due date."
  penalty: null            # optional plain text, must be cited

citations:                 # at least one; each must resolve to a chunk
  - { source_key: companies_act_2013, section_path: "Companies Act, 2013 > Section 10A", chunk_id: null }

review:
  drafted_by: "ai:rule_draft@v1"      # or human:<name>
  reviewed_by: "CA <name or ID>"      # required for rules/published/
  reviewed_on: 2026-10-15
  notes: ""
```

The example above is **illustrative only**; its content is not a verified legal statement.

`chunk_id` is filled by the publication job from `source_key` + `section_path` (latest active version). Publication fails if any citation does not resolve.

---

## 4. Conditions

### 4.1 Grammar

```
condition := { all: [condition, ...] } | { any: [condition, ...] } | { not: condition } | leaf
leaf      := { fact: <key>, op: <op>, value?: <literal> }
```

| op | Fact types | Meaning |
|---|---|---|
| `eq`, `ne` | any scalar | equality |
| `in`, `not_in` | enum, state_code, int | membership in a literal list |
| `contains`, `contains_any` | enum_list | list contains value / any of values |
| `gt`, `gte`, `lt`, `lte` | int, money_paise, date | comparison with a literal |
| `between` | int, money_paise, date | inclusive `[low, high]` |
| `is_true`, `is_false` | bool | boolean test |
| `is_known` | any | TRUE if value_state is `known` (never UNKNOWN) |

The schema rejects ops that do not match the fact's `value_type`.

### 4.2 Three-valued logic (Frozen)

Each leaf yields `T`, `F`, or `U` (unknown). A leaf is `U` when the fact is missing or `value_state = 'unknown'`.

| Operator | Result |
|---|---|
| `all` | `F` if any child `F`; else `U` if any `U`; else `T` |
| `any` | `T` if any child `T`; else `U` if any `U`; else `F` |
| `not` | swaps `T`/`F`; `U` stays `U` |

Outcome mapping:

| Root | `kind: obligation` | `kind: risk_check` / `roadmap_trigger` |
|---|---|---|
| `T` | `applies` → obligation(s) `open` | `flagged` |
| `F` | `not_applicable` (reason = decisive `F` leaf) | `clear` |
| `U` | `needs_info` with `unknown_facts` = unknown leaves that could flip the result | `needs_info` |

`needs_info` is **never** silently dropped (FR-CORE-03).

---

## 5. Schedules and due dates

All dates are computed as calendar dates in `Asia/Kolkata`. The evaluator receives `as_of: date` from an injected clock.

| `schedule.type` | Fields | Occurrences |
|---|---|---|
| `one_time` | `due: {anchor: <date fact>, offset: {days?, months?, years?}}` | One, `period_key = "once"` |
| `recurring` | `frequency: monthly \| quarterly \| annual`; `period_basis: calendar \| financial_year` (FY = 1 Apr–31 Mar); `due: {after_period_end: {days?, months?}}` or `due: {day_of_following_month: 1–28}` | Every period whose end is ≥ `start` (below) and whose due date ≤ `as_of + 365 days` |

- Rules with `kind: risk_check` or `roadmap_trigger` have no schedule; they produce a result (`flagged` / `clear` / `needs_info`), not dated obligations.
- `start` for recurring = latest of rule `effective.from`, and `start_anchor` fact (default `incorporation_date`).
- Period keys: monthly `YYYY-MM`; quarterly calendar `YYYY-Qn`; FY quarter `FYYYYY-YY-Qn`; annual `YYYY` or `FYYYYY-YY`.
- If the anchor fact is unknown → occurrence state `needs_info`, `due_date = NULL`.
- Month arithmetic uses end-of-month clamping (31 Jan + 1 month = 28/29 Feb).

---

## 6. Versions, effective dates, and deadline extensions

- **Content change** (conditions, schedule) → new `version` with a new `effective.from`. Occurrences with `due_date < new effective.from` keep their original `rule_version_id` and are **not** recomputed; later occurrences are recomputed with the new version.
- **One-off deadline extension** by an authority → an entry in `obligation.overrides` of the same rule, published as a new version:
  ```yaml
  overrides:
    - { period_key: "FY2026-27", due: 2027-11-30, citation: { source_key: mca_circular_x, section_path: "..." } }
  ```
- **Retirement** → `status: retired` with `effective.to`; open future occurrences become `superseded` with reason.
- Exactly one published version per `rule_id` at a time (database constraint).

---

## 7. Evaluation API (pure, deterministic)

```python
def evaluate(rule: Rule, facts: FactSnapshot, as_of: date) -> Evaluation: ...
# Evaluation = outcome (applies|not_applicable|needs_info|flagged|clear),
#              occurrences: list[Occurrence(period_key, due_date|None, state)],
#              unknown_facts: list[str], trace: Trace
```

- No I/O, no clock access, no randomness. `facts_hash` = SHA-256 of the canonical JSON of facts referenced by the rule.
- Property tests (Hypothesis): same inputs → same output; changing an unreferenced fact never changes the output; replacing a `U` by any value never turns a `T` root into `U`.

### 7.1 Trace format (stored in `evaluation_trace`, rendered by the Explainer)

```json
{"rule_id":"…","version":1,"root":"T","nodes":[
  {"path":"all[0]","fact":"entity_type","op":"in","expected":["pvt_ltd"],"actual":"pvt_ltd","result":"T"},
  {"path":"all[1]","fact":"has_share_capital","op":"is_true","actual":true,"result":"T"}],
 "schedule":{"anchor":"incorporation_date","anchor_value":"2026-06-01","offset":{"days":180},"due_date":"2026-11-28"}}
```

---

## 8. Publication pipeline

1. PR modifies `rules/published/**` or `rules/facts.yaml`.
2. CI: JSON Schema validation → Pydantic parse → op/type check against registry → `review.reviewed_by` present → explanation fields present → scenario suite (§9) → recall gate ([NFR-AI-01](nfr.md#7-ai-quality-gates)).
3. Merge to `main` → deploy job runs `python -m app.modules.rules.publish` (as `app_owner`): upsert registry, insert new `rule_versions` + `rule_citations`, flip statuses, write `rules.publications`, enqueue re-evaluation for affected organisations.
4. Changelog text comes from the PR description (required section `## Rule changes`).

---

## 9. Scenarios (`rules/scenarios/*.yaml`)

```yaml
id: scn_two_founder_saas_tg
reviewed_by: "CA <name>"
as_of: 2026-10-01
org_type: company
facts:
  entity_type: pvt_ltd
  has_share_capital: true
  incorporation_date: 2026-06-01
  state_code: TG
  employee_count: unknown        # literal 'unknown' → value_state unknown
expected:
  applies:
    - { rule_id: mca.example_commencement_declaration, period_key: once, due_date: 2026-11-28 }
  not_applicable: [ ]
  needs_info:
    - { rule_id: labour.example_threshold_rule, unknown_facts: [employee_count] }
  must_not_include: [ ]
```

- A scenario fails if any expected item is missing (**recall**), has the wrong due date, or if an unexpected `applies` appears (precision, reported but gated separately).
- Every `criticality: critical` rule must appear in ≥ 2 scenarios (one applies, one not_applicable).
