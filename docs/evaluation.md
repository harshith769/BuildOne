# BuildOne — Evaluation

> **Status:** v1.1 · 2026-10-07 (retrieval gate on a fixture corpus, M5) · Owner: @harshith769
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
| Retrieval | `evals/retrieval.jsonl` | `{id, question, filters, relevant_chunk_keys[], answerable, source: synthetic\|interview, domain, note}`; optional `partial`, `conflict` + `match: every_source`, `near_miss`, `s2_chunk_keys` (the S2 key a re-keyed label replaced) ([S2](spikes/S2-retrieval.md#labelled-set-evalsretrievaljsonl)) | Every PR (CI gate on the fixture corpus); the real corpus on demand | No (local embeddings) |
| Fact extraction | `evals/fact_extract.jsonl` | `{id, text, expected: {key: value}}` | On demand + before prompt/model change | Yes |
| Clause extraction | `evals/clause_extract/` | Synthetic contracts + `expected.json` | On demand | Yes |
| Copilot Q&A | `evals/copilot.jsonl` | `{id, question, org_facts, answerable: bool, required_chunk_keys[], key_points[]}` | On demand | Yes |
| Rephrase | `evals/rephrase.jsonl` | `{id, obligation_fixture, must_keep: [dates, forms]}` | On demand | Yes |

`relevant_chunk_keys` use stable `source_key + section_path` (not UUIDs, no source title) so datasets survive re-ingestion: `"<source_key>::<section_path>"` matches every chunk covering a node at or under that path, and the path's segments only need to appear in order, so a tree level the label leaves out still matches (`CHAPTER III > 23` matches `CHAPTER III > PART I > 23 > (2)`); `"…#<n>"` matches piece n of a split leaf; an empty path (`"esic_circular::"`) matches any chunk of the source (`app/modules/knowledge/labels.py`). A label that matches no active chunk of a loaded source fails the run. In M5, nine S2 labels that pointed at gold-outline-only containers or S2 table pieces were re-keyed to the M5 tree by hand (r010–r013, r025, r026, r029, r031, r039; old keys kept in `s2_chunk_keys`). Retrieval recall is reported per `source` group (synthetic, interview), with `partial` items also reported separately; a `match: every_source` item counts only when every labelled source is in the top k.

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
make eval-retrieval    # CI gate: fresh DB + fixture corpus (backend/tests/fixtures/knowledge), recall@10 >= 90%
make eval-retrieval-real  # the real corpus loaded by `make ingest` (DATABASE_URL); records the result
make eval-ai TASK=copilot_answer N=30   # on demand; counts against the free daily budget
```

Results append to `evals/results/<date>-<suite>.json` (committed) so trends are reviewable in PRs; retrieval writes `<date>-retrieval-<corpus>.json` (the CI gate writes only with `EVAL_RECORD=1`).

**Retrieval gate rules (owner, M5):** the fixture corpus holds the S1 gold windows of every public, unsigned source (signed scans are not committed, so their questions are skipped). The run fails if recall@10 < 90%, if fewer than 40 answerable questions are evaluated, if more than 10 are skipped (the skipped list is printed), or if any label is unresolved. Latency is reported as query embedding + database (in-process model at 2 threads, like the sidecar).

## 4. Change policy

A PR that changes a prompt version, model route, chunking parameter, or retrieval parameter must include the relevant suite's before/after numbers in its description.
