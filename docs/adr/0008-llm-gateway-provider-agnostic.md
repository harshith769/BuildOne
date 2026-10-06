# ADR-0008: Provider-agnostic LLM gateway; free tiers only where contractually safe; hard daily budget; never auto-spend

- **Status:** Accepted
- **Date:** 2026-09-28 (revised same day: zero-cost AI)
- **Decision makers:** @harshith769
- **Confidence:** To be set by owner (model choice deferred to spike S4)

## Decision

**All model calls go through one in-house gateway that wraps official SDKs and enforces schemas, redaction, logging, a hard daily token budget, and per-task model routing. In the MVP:**
- **Tasks with user data** (Copilot, clause extraction, optional fact extraction, optional explanation rephrasing) use **Groq free-tier open-weight models with Zero Data Retention enabled**.
- **Tasks with public text only** (rule drafting from official sources) may use the **Gemini free tier**.
- **When the free budget is exhausted, features degrade; the gateway never switches to a paid tier automatically.**

## Context

MVP budget is ₹0. Groq's services agreement states it is not permitted to use inputs or outputs for training without customer permission ([Groq Services Agreement](https://console.groq.com/docs/legal/services-agreement)); any customer can enable Zero Data Retention, and retained data is stored in the US ([Groq: Your Data](https://console.groq.com/docs/your-data)). The Gemini free tier uses content to improve Google's products ([Puter pricing guide](https://developer.puter.com/tutorials/gemini-api-pricing/)), so it is limited to public source text.

## Candidates

### A. Thin in-house gateway over official SDKs (chosen)
- Full control of redaction, budgets, fallbacks; small code surface.

### B. LiteLLM as the adapter layer
- Many providers behind one API; still needs our policy layer. Revisit if adapter maintenance grows.

### Models evaluated in spike S4
- Groq free tier: open-weight models (e.g., gpt-oss-120b, Qwen) — free-plan sample limits of 30 requests/min, 1,000 requests/day, 200,000 tokens/day per model ([BenchLM reading of Groq limits](https://benchlm.ai/md/free-tier/groq.md)); the Groq console limits page is authoritative.
- Paid fallbacks for later stages: Claude Haiku 4.5 ($1/$5 per 1M tokens, [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)), Gemini 3.1 Flash-Lite ($0.25/$1.50, [Costgoat](https://costgoat.com/pricing/gemini-api)).

## Evaluation

Quality not measured → spike S4 against [NFR-AI gates](../nfr.md#7-ai-quality-gates). Capacity estimate (not measured): Copilot prompts capped at ~4k tokens → ~50 questions/day per Groq model; two models → ~100/day.

## Consequences

- Core compliance features and the default Explainer use **no AI** ([requirements.md FR-CORE-04](../requirements.md#fr-core-04-why-this-applies-explainer-c4--must)).
- Every AI output stores provider, model, prompt version, input hash.
- Budget exhaustion → Copilot shows "daily limit reached, try tomorrow"; rephrasing and free-text intake are skipped.
- Groq Zero Data Retention must be enabled before any user data is sent (checked at startup via configuration flag and documented in the runbook).

## Re-evaluation Triggers

- Groq terms, limits, or model availability change.
- Pilot usage regularly hits the daily cap → add a paid model for overflow (explicit owner decision).
- Spike S4 shows free models fail quality gates.
