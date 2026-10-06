# BuildOne — Evaluation

> **Status:** v1.0 · 2026-09-28 · Owner: @harshith769
> Gates and thresholds live in [nfr.md §7](nfr.md#7-ai-quality-gates); this file defines datasets, metrics, and when each runs.

**What this document answers**
- Which golden sets exist, where they live, and their formats
- How each metric is computed
- Which evaluations run on every PR and which run on demand (to stay inside free AI limits)

---

## 1. Suites

| Suite | Location | Format | Runs | Uses AI |
|---|---|---|---|---|
| Rule scenarios | `rules/scenarios/*.yaml` | [rules-engine.md §9](rules-engine.md#9-scenarios-rulesscenariosyaml) | Every PR (CI) | No |
| Retrieval | `evals/retrieval.jsonl` | `{id, question, filters, relevant_chunk_keys[]}` | Every PR touching `knowledge/` or retrieval code | No (local embeddings) |
| Fact extraction | `evals/fact_extract.jsonl` | `{id, text, expected: {key: value}}` | On demand + before prompt/model change | Yes |
| Clause extraction | `evals/clause_extract/` | Synthetic contracts + `expected.json` | On demand | Yes |
| Copilot Q&A | `evals/copilot.jsonl` | `{id, question, org_facts, answerable: bool, required_chunk_keys[], key_points[]}` | On demand | Yes |
| Rephrase | `evals/rephrase.jsonl` | `{id, obligation_fixture, must_keep: [dates, forms]}` | On demand | Yes |

`relevant_chunk_keys` use stable `source_key + section_path` (not UUIDs) so datasets survive re-ingestion.

**Data rule:** golden sets contain only public legal text, synthetic company facts, and **synthetic** contracts. No real user data, ever.

## 2. Metrics

| Metric | Definition |
|---|---|
| Obligation recall | expected `applies` + `needs_info` items found with correct `period_key` and `due_date` ÷ all expected |
| Obligation precision | correct `applies` ÷ all produced `applies` (reported) |
| Retrieval recall@10 | questions with ≥ 1 relevant chunk in top 10 ÷ questions |
| Citation precision | sentences whose cited chunk supports them (human-labelled sample of 50) ÷ sampled sentences |
| Faithfulness | answers with zero unsupported sentences ÷ answers (verifier + human spot-check of 20%) |
| Abstention correctness | correct abstain on `answerable:false` and correct answer on `answerable:true`, each reported separately |
| Extraction accuracy | field-level exact match (facts) / category+location match (clauses) |

## 3. Commands

```bash
make eval-rules        # scenarios (CI)
make eval-retrieval    # retrieval recall@10 + latency (CI when relevant)
make eval-ai TASK=copilot_answer N=30   # on demand; counts against the free daily budget
```

Results append to `evals/results/<date>-<suite>.json` (committed) so trends are reviewable in PRs.

## 4. Change policy

A PR that changes a prompt version, model route, chunking parameter, or retrieval parameter must include the relevant suite's before/after numbers in its description.
