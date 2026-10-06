# BuildOne — AI System

> **Status:** v1.0 (frozen for MVP build; model choice per task by spike S4) · 2026-09-28 · Owner: @harshith769
> Decision record: [ADR-0008](adr/0008-llm-gateway-provider-agnostic.md). Gates: [nfr.md §7](nfr.md#7-ai-quality-gates).

**What this document answers**
- The gateway interface every module must use, and what it enforces
- The task registry: data class, budget, schema, and model route per task
- How budgets and quotas are computed, and what degrades when they run out
- How redaction, prompt-injection defence, and citation verification work

---

## 1. Gateway interface (Frozen)

All model calls go through `backend/app/modules/ai/`. No other module imports a provider SDK (CI-enforced).

```python
class AIGateway(Protocol):
    async def run(self, task: TaskName, inputs: BaseModel, *, ctx: CallContext) -> TaskResult: ...
    async def stream(self, task: TaskName, inputs: BaseModel, *, ctx: CallContext) -> AsyncIterator[StreamEvent]: ...

@dataclass(frozen=True)
class CallContext:
    request_id: str
    org_id: UUID | None
    user_id: UUID | None

# TaskResult: output (validated Pydantic model), call_id, provider, model, prompt_version
# Raises: BudgetExceeded, QuotaExceeded, ProviderUnavailable, OutputValidationFailed
```

Callers must handle every exception by degrading (never by retrying with a paid model).

---

## 2. Task registry (MVP)

| Task | Data class | Used by | Output schema | Budget class |
|---|---|---|---|---|
| `fact_extract` | user_data | Smart Intake (optional) | list of `{key, value, source_excerpt}` | standard |
| `clause_extract` | user_data | Situation Check | list of `{category, page, section, excerpt, explanation, confidence}` | heavy |
| `copilot_route` | user_data | Copilot | `{route, rewritten_query}` | light |
| `copilot_answer` | user_data | Copilot (streamed) | sentences each with `chunk_ids[]` | standard |
| `explain_rephrase` | user_data | Explainer (optional) | sentences each with `chunk_ids[]` | standard |
| `rule_draft` | public_only | Rule Studio CLI | rule YAML draft | offline |

Each task has: `prompt_version`, `max_input_tokens`, `max_output_tokens`, ordered `routes` (provider+model), `temperature` (0–0.2), timeout.

**Routing policy (Frozen):** `user_data` tasks may only use providers configured with `user_data_allowed: true` — set only for providers whose terms exclude training **and** with zero data retention enabled (Groq, ZDR on). `public_only` tasks may use any configured provider, including free tiers that use content for product improvement.

---

## 3. Prompts

- Stored as files: `backend/app/modules/ai/prompts/<task>/<version>.md` with front matter (`task`, `version`, `output_schema`).
- A version is immutable once merged; changes create a new version and must pass the task's eval set ([evaluation.md](evaluation.md)).
- Structure: system instructions → delimited data blocks (`<source id="chunk_id">…</source>`, `<user_document>…</user_document>`) → task instruction → output schema.

---

## 4. Budgets and quotas

- **Usage log:** every call (including denied ones) inserts one `ai.calls` row. No counters; totals are `SUM`/`COUNT` queries over the day in `Asia/Kolkata`.
- **Global daily token budget** per provider model = 80% of that model's free daily token limit (configured from the provider console).
- **Per-organisation quotas:** Copilot 10 questions/day; clause extraction 3 documents/day; configurable.
- **Pre-check:** estimated tokens (input count + `max_output_tokens`) must fit remaining budget; otherwise `BudgetExceeded` before any network call.
- **Alerts:** 50/80/100% of daily budget → Sentry event (NFR-COST-04).

| Exhausted | Behaviour |
|---|---|
| Copilot | Message route `limit_reached`: "Daily limit reached — try tomorrow", links to obligation plan |
| Explainer rephrase | Button disabled; deterministic explanation shown |
| Fact extract | Free-text option hidden; form remains |
| Clause extract | Document status `limit_reached`; questionnaire flags still shown |

---

## 5. Reliability

- Retries: HTTP 429/5xx and timeouts → exponential backoff with jitter, max 2 retries, then next route (a second free model). All routes exhausted → `ProviderUnavailable`.
- Structured output: JSON mode where supported → Pydantic validation → one repair attempt with the validation error → `OutputValidationFailed`.
- Timeouts: 20 s non-streaming; streaming first-token 5 s.

---

## 6. Privacy and safety

- **Field allowlist:** tasks receive typed input models; only facts whose keys are listed in the task's allowlist are included.
- **Scrubber** on all free text before sending (user questions, documents): masks emails, phone numbers, PAN, Aadhaar-format numbers, bank-account-like digit runs; scrub counts logged, content not logged.
- **Prompt-injection defence:** documents and retrieved text are passed only inside data delimiters with instructions to treat them as data; models have **no tools**; outputs are schema-validated; nothing in an output can trigger an action.
- **Logging:** `ai.calls` stores hashes and token counts, never prompt or response text. Copilot messages are stored as product data in `copilot.messages` (user-visible, deletable).

---

## 7. Citation verification (Frozen algorithm)

For each output sentence with `chunk_ids`:
1. **Membership:** every cited `chunk_id` must be in the context sent to the model → else drop sentence.
2. **Literal check:** numbers, dates, form codes (`[A-Z]{2,}-?\d+[A-Z]?`), and section references in the sentence must appear in at least one cited chunk → else drop.
3. **Semantic check:** cosine similarity between the sentence embedding and the best cited chunk ≥ `σ` (local embedding model; `σ` set in S4) → else drop.
4. If more than half the sentences are dropped, discard the answer: Copilot abstains; Explainer falls back to the deterministic explanation.
