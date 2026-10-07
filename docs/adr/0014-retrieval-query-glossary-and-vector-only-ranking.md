# ADR-0014: Retrieval — expand query abbreviations from a versioned glossary; rank by vector search only in the MVP

- **Status:** Accepted (owner, 2026-10-07, on the S2 results)
- **Date:** 2026-10-07
- **Decision makers:** @harshith769
- **Changes:** [data-pipeline.md §6](../data-pipeline.md#6-retrieval-frozen-algorithm-parameters-tunable-via-evaluation) (frozen retrieval algorithm, [build-plan.md §1.1](../build-plan.md)): a new step 0 (query expansion), the lexical list and the confidence step. Evidence: [S2 report](../spikes/S2-retrieval.md).

## Decision

1. **Query abbreviation expansion.** Before retrieval, the question is expanded from [`knowledge/query-glossary.yaml`](../../knowledge/query-glossary.yaml): the first occurrence of each listed abbreviation gets its expansion appended in brackets ("When does TCS apply" → "When does TCS (tax collected at source, collection of tax at source) apply"). The expanded text is what gets embedded.
   - The glossary is a **versioned file** (`version`, `updated`), whole-word and case-sensitive. It holds terminology only, never regulatory facts (AGENTS.md rule 15).
   - A glossary change is a retrieval-parameter change: the PR carries before/after `make eval-retrieval` numbers ([evaluation.md §4](../evaluation.md)).
   - It is deterministic and needs no AI call, so it works with AI down (AGENTS.md rule 5).
2. **Ranking is vector-only in the MVP.** Rank by cosine on the HNSW index (`ef_search = 64`), top 50, keep the top 20 (the same filter as before). The lexical list and RRF fusion are **off**. The `tsvector` column and GIN index stay in the schema, so lexical search can return without a migration.
3. **No reranker** (S2: too slow and too large for the VM).
4. **The confidence threshold τ isn't gated in the MVP.** MVP retrieval serves rule drafting and citations, with a human in the loop. Calibrating τ is required before the Copilot (Phase 2), on held-out real interview questions, not the S2 set ([deferred.md §13](../deferred.md)).

## Context

On S2's labelled set (50 answerable founder questions, real corpus of 904 chunks):
- **The frozen lexical step is unusable for founder questions.** `websearch_to_tsquery` ANDs every term, so it finds a relevant chunk in the top 10 for 6% of questions. The frozen hybrid is therefore vector-only in practice.
- **Founders' abbreviations never appear in the statutes.** "TCS", "RCM", "PT" and "MoA" are written out in the law. Without expansion, the best configuration reaches recall@10 84%. With the glossary, bge-base-en-v1.5 (int8) reaches 94%, against the 90% gate (NFR-AI-06).
- **RRF scores are rank-only**, so the frozen confidence rule ("top chunk in one list and fused score < τ") can't separate answerable from out-of-scope questions:
  - with the AND query, 43 of 50 answerable questions come out `low`;
  - with an OR query, none of them do.

## Options

### Lexical step
| Variant (all with the glossary, bge-base int8) | recall@10 | recall@5 | p95 at 50k chunks | Verdict |
|---|---|---|---|---|
| A. As frozen: `websearch_to_tsquery` (AND) + RRF | 94% | 76% | 3.7 ms | Same result as B; the lexical half adds nothing |
| **B. Vector-only (chosen)** | **94%** | **76%** | **2.6 ms** (70.5 ms just after a Postgres restart) | Simplest; meets the gates |
| C. OR of all query lexemes + RRF | 88% | 78% | 441 ms | Fails NFR-PERF-06 and loses recall |
| D. OR of the ≤ 5 highest-IDF lexemes + RRF (owner's variant) | 92% | 78% | 116 ms | Within latency, but recall drops by one question. Owner rule: use D only if recall doesn't drop |

On exact-identifier questions ("section 393", "INC-1", "rule 8 CGST rules"; 10 questions), B finds 9 of 10 in the top 10 (MRR 0.78) and D also finds 9 of 10 (MRR 0.73). The section path and heading are part of every embedded text, so identifiers are covered without a lexical list.

### Abbreviations
- **A. Glossary expansion, deterministic (chosen).**
- **B. Rewrite the query with an LLM.** Rejected for the MVP: it adds an AI dependency to core retrieval, plus latency and free-tier budget.
- **C. Index the abbreviations into the chunks.** Rejected: it changes the stored text, and every source would need re-embedding whenever a term is added.

## Consequences

- **`D = 768`; model `bge-base-en-v1.5`, int8 ONNX** (`Xenova/bge-base-en-v1.5`, `onnx/model_int8.onnx`, CLS pooling, normalised). The query prefix is "Represent this sentence for searching relevant passages: ".
- **The query embedder runs as a sidecar process on the VM** (owner, 2026-10-07): 269 MiB peak RSS, p95 21 ms per question at 2 threads, p95 17 ms end to end over a Unix socket. It never loads in the API process (AGENTS.md).
  - This replaces [ADR-0012](0012-hosting-after-student-pack-change.md)'s "no embedding model in a long-running process" for the query embedder only.
  - S5 must now show **API + worker + sidecar** within the VM's budget. 269 MiB is about 30% of the ~900 MiB that ADR-0012 allows API + worker.
- **If the lexical list returns** (for example, when interview questions show identifier misses), variant D is the measured candidate. It needs a `lexdf` table (`ts_stat` document counts, rebuilt at ingestion), a new eval run, and an update to this ADR.
- **Re-evaluation triggers:**
  - recall@10 on `evals/retrieval.jsonl` (including the interview group, once added) falls below 90%;
  - a glossary or model change;
  - the corpus grows past 50k chunks;
  - the Copilot starts (τ).
