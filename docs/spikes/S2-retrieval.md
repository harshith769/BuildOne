# Spike S2: Retrieval over official Indian legal sources

- **Date:** 2026-10-07 · **Time spent:** about 1 day (labelled set, runs, report)
- **Question:**
  - Which embedding model and dimension `D`, and which mode (full-text only, vector only, hybrid RRF, hybrid + reranker), meet [NFR-AI-06](../nfr.md#7-ai-quality-gates) (recall@10 ≥ 90%) and [NFR-PERF-06](../nfr.md) (p95 retrieval < 300 ms, reranker excluded) within the [ADR-0012](../adr/0012-hosting-after-student-pack-change.md) memory limits?
  - Which confidence threshold `τ`?
  - Fixes the `Embedder` and `Reranker` seams ([build-plan.md §1.2](../build-plan.md)).
- **Setup:**
  - **Machine:** laptop, AMD Ryzen 7 7435HS (16 threads), WSL2 with 9.7 GiB RAM.
  - **Database:** PostgreSQL 18.6 + pgvector 0.8.6 (conda-forge build, because Docker and sudo aren't available in this WSL distro), run as a systemd user service capped at `MemoryMax=2G`, `MemorySwapMax=0`, `CPUQuota=100%`. That mimics a 1-vCore, 2 GiB managed server (B1MS). Settings: `shared_buffers=512MB`, `effective_cache_size=1536MB`, `maintenance_work_mem=256MB`, `work_mem=4MB`.
  - **Query-time model processes** ran under `CPUQuota=200%` with 2 ONNX threads (the VM has 2 vCPU).
  - **Libraries:** Python 3.13.15, fastembed 0.8.1, onnxruntime 1.30.0, psycopg 3.3.6.
  - **Data:** public legal text only, no personal data. Spike code is in `spikes/s2/` (gitignored, kept locally).

## Result in one paragraph

**Pass, after two owner-approved changes to the frozen retrieval algorithm ([ADR-0014](../adr/0014-retrieval-query-glossary-and-vector-only-ranking.md)).**
- **Winning configuration:** bge-base-en-v1.5 quantised to int8 (`D = 768`), with query abbreviations expanded from a versioned glossary, ranked by vector search only.
- **Quality:** recall@10 **94%**, recall@5 76%, MRR 0.60 on 50 founder questions over the real corpus (904 chunks from 21 official sources).
- **Speed:** p95 **2.6 ms** of database time at 50k chunks (70.5 ms just after a restart). The query embedder adds p95 21 ms.
- **Memory:** **269 MiB** peak for the query embedder, under 300 MiB.
- **What didn't work as frozen:**
  - The frozen lexical step (`websearch_to_tsquery`, AND of all terms) finds a relevant chunk for 6% of questions. The frozen hybrid is therefore vector-only in practice.
  - Without the glossary, nothing passes: the best result is 84%. Founders write "TCS", "RCM", "PT" or "MoA", and the statutes never do.
  - Rerankers add up to 8 recall points without the glossary but cost 1.8–11 s and 1.2–2.6 GiB per query on 2 vCPU, so the reranker is **off**.
  - `τ` can't be calibrated: RRF scores are rank-only, and no absolute signal met the τ rule robustly. Per the owner it **isn't gated in the MVP** and moves to [deferred.md §13](../deferred.md), before the Copilot.

## Method

### Corpus: S1's parsed output, chunked as data-pipeline §4
- **Text:** the S1-chosen parser per source ([S1 report](S1-parsing.md)): PyMuPDF + heuristic + Tesseract for PDFs, stdlib HTML for HTML. Text is restricted to each source's S1 window, giving 21 sources (the CBIC notification is still missing).
- **Structure:** S1's gold outline anchors each node. A gold entry starts where S1's scorer matched it, and its text runs to the next matched entry. Entries that weren't found fold into the previous node, as an M5 tree builder would leave them.
- **Chunking:** the frozen policy (data-pipeline §4).
  - A leaf of ≤ 500 tokens is one chunk.
  - Longer leaves split at line boundaries into 350–500-token pieces with a 50-token overlap.
  - Sibling leaves under 80 tokens are merged.
  - Embedded text is `title > section_path` + heading + text.
  - Tokens are counted with the bge tokenizer.
- **Size:** **904 chunks, 121,809 tokens** (median 94, maximum 500).
- **Caveats:**
  - Tables flatten to text, and the s.393 and s.394 TDS/TCS tables come out with their columns interleaved.
  - Hindi text layers are kept as extracted (the ESIC circular is mostly broken Hindi).
  - Parent chunks (rule 5) are context only and weren't built.

### Labelled set: `evals/retrieval.jsonl`
- **Contents:** 50 answerable questions and 10 out-of-scope ones.
  - By domain: company law 13 (4 of them DPIIT startup), GST 11, income tax 7, labour 9, Telangana 10.
  - All carry `source: synthetic`. No interview questions yet, so recall by group (synthetic, interview) currently has one group.
- **Questions first:** all 70 drafts were written from the founder's point of view before any chunk text was read (`spikes/s2/questions_draft.yaml`). Only the source list was known.
  - 5 drafts were dropped because the corpus can't answer them (see *Corpus gaps*).
  - 15 more were dropped before any retrieval ran, to balance domains (the 13 answerable ones are kept as reserves).
  - 4 are Hinglish. Abbreviations used: ROC, OPC, MoA, RCM, TDS, TCS, PF, ESIC, PT, CCFS.
- **Labels:** `source_key::section_path` matches any chunk at or under that path; `source_key::section_path#n` matches one piece of a split section (used for the long s.393 tables).
- **Tags (owner decisions, 2026-10-07):**
  - `partial: true` (r034, r035, r044, r048): only the governing provision is in the corpus, not the rates or schedule. Recall is reported separately.
  - `conflict: true` (r045, Telangana shops renewal): a hit only when **both** the Act (s.4, renewal) and the later Memo 337 (renewal dispensed with) are in the top 10. An answer must show the later memo next to the Act.
  - `near_miss: true` (o009, the GST rate on SaaS): s.9(1) is in the corpus, but the rate isn't. It's used in τ calibration.
- **Review status:** **owner spot check not done; CA review of labels pending.**

### Configurations
- **Embedders (ONNX via fastembed, CPU):**

  | Id | Model | Dim | Notes |
  |---|---|---|---|
  | bge-small | `BAAI/bge-small-en-v1.5` | 384 | |
  | e5-small | `intfloat/e5-small-v2` | 384 | `query:` / `passage:` prefixes |
  | minilm | `sentence-transformers/all-MiniLM-L6-v2` | 384 | |
  | me5-small | `intfloat/multilingual-e5-small` | 384 | for the Hinglish questions and Hindi text |
  | bge-base | `BAAI/bge-base-en-v1.5` | 768 | |
  | me5-small-q, bge-base-q | int8 dynamic-quantised exports of me5-small and bge-base (`Xenova/…/onnx/model_int8.onnx`) | 384, 768 | added after the fp32 models broke 300 MiB |

- **Retrieval steps** (data-pipeline §6): filter, then lexical top 50 (`ts_rank_cd`), then HNSW cosine top 50 (`m=16`, `ef_construction=64`, `ef_search=64`), then RRF k=60, then top 20.
- **Lexical variants:**
  - `ws`: the frozen `websearch_to_tsquery('english')`.
  - `or`: the same lexemes, ORed.
  - `idf5` (owner's variant): OR over at most the 5 highest-IDF lexemes of the expanded query, stopwords removed, with IDF from `ts_stat` document counts.
- **Modes:** full-text only, vector only, hybrid, and hybrid + reranker (`Xenova/ms-marco-MiniLM-L-6-v2` or `BAAI/bge-reranker-base`, reranking the top 20).
- **Glossary:** `knowledge/query-glossary.yaml` v1, 26 common Indian compliance abbreviations, written as a general list rather than fitted to the misses: it includes terms no question uses, and it's applied to every question.

### Metrics (how each number is measured)
- **recall@k:** a question counts as answered when a labelled chunk is in the top k (r045 needs both sources). Reported over the 50 answerable questions; partial items are also shown separately.
- **MRR:** 1 / the rank at which the question first counts as answered, within the top 20; 0 if never.
- **Latency:**
  - One SQL round trip running the whole pipeline, measured from the client on the same machine.
  - 200 timed queries (the 60 questions cycled) after 20 warm-up queries.
  - Query vectors are precomputed, so this is database time only.
  - "Cold" means just after a Postgres restart (empty shared buffers; the OS page cache couldn't be dropped without sudo), with no warm-up.
- **50k corpus (latency, index size and RAM only):**
  - Built from 904 real chunks plus 49,096 perturbed copies: 25% of words dropped or replaced by random corpus words, and vectors given Gaussian noise (σ = 0.03 per dimension) then re-normalised.
  - Recall, MRR and τ are measured on the **real corpus only** (owner rule).
- **Query embedder and reranker:**
  - Run in their own process under `CPUQuota=200%` with 2 threads.
  - p50/p95 over 200 single questions (the reranker scores 20 chunks per question; bge-reranker was run for 30 questions because each takes seconds).
  - Peak RSS from `getrusage` and `/usr/bin/time`.
- **Index build time and size:** wall time of `CREATE INDEX` on the capped server; `pg_relation_size`.

## Results

### Recall and MRR, real corpus (50 answerable questions)

recall@10 / recall@5 / MRR. Without the glossary, then with it.

| Model | Full-text `ws` | Full-text `or` | Vector | Hybrid `ws` | Hybrid `or` | Hybrid `idf5` |
|---|---|---|---|---|---|---|
| bge-small | 6 / 6 / 0.05 | 68 / 38 / 0.30 | 70 / 66 / 0.56 | 70 / 66 / 0.54 | 72 / 58 / 0.45 | – |
| e5-small | 〃 | 〃 | 78 / 70 / 0.49 | 78 / 70 / 0.48 | 80 / 74 / 0.50 | – |
| minilm | 〃 | 〃 | 80 / 68 / 0.52 | 80 / 68 / 0.53 | 84 / 78 / 0.54 | – |
| me5-small | 〃 | 〃 | 74 / 64 / 0.47 | 72 / 64 / 0.45 | 80 / 64 / 0.49 | – |
| bge-base | 〃 | 〃 | 84 / 78 / 0.56 | 84 / 78 / 0.56 | 84 / 72 / 0.49 | – |
| me5-small-q | 〃 | 〃 | 78 / 62 / 0.45 | 78 / 62 / 0.45 | 82 / 74 / 0.50 | – |
| bge-base-q | 〃 | 〃 | 84 / 74 / 0.58 | 84 / 74 / 0.57 | 80 / 68 / 0.48 | 82 / 64 / 0.48 |
| **With glossary:** | | | | | | |
| bge-small | 6 / 6 / 0.05 | 58 / 34 / 0.26 | 84 / 76 / 0.61 | 84 / 76 / 0.60 | 84 / 66 / 0.47 | – |
| e5-small | 〃 | 〃 | 78 / 74 / 0.55 | 78 / 74 / 0.54 | 84 / 74 / 0.53 | – |
| minilm | 〃 | 〃 | 86 / 70 / 0.60 | 86 / 70 / 0.59 | 88 / 76 / 0.52 | – |
| me5-small | 〃 | 〃 | 82 / 66 / 0.47 | 80 / 66 / 0.45 | 90 / 74 / 0.49 | – |
| bge-base | 〃 | 〃 | 92 / 78 / 0.60 | 92 / 78 / 0.60 | 86 / 80 / 0.53 | – |
| me5-small-q | 〃 | 〃 | 86 / 64 / 0.47 | 84 / 64 / 0.46 | 90 / 74 / 0.51 | – |
| **bge-base-q** | 〃 | 〃 | **94 / 76 / 0.60** | 94 / 76 / 0.59 | 88 / 78 / 0.51 | 92 / 78 / 0.56 |

- **Chosen configuration, by group:**
  - synthetic 94% (47/50); interview: no questions yet.
  - The 46 non-partial questions: 95.7% recall@10. The 4 partial ones: 3 of 4 (r034 rank 4, r044 rank 1, r048 rank 1; r035 missed).
  - r045 (conflict): both sources in the top 10, at rank 5.
- **By domain (chosen):** company law 12/13, GST 11/11, income tax 7/7, labour 8/9, Telangana 9/10. Without the glossary, income tax drops to 4/7.
- **Hinglish (chosen):** r024 rank 4, r031 rank 8, r048 rank 1; r035 missed. multilingual-e5-small didn't beat the English models on these questions, and it costs 3.4× the RAM (below).

### Rerankers (no glossary; top 20 of the hybrid reranked)

| Model | `ws` + MiniLM-CE | `or` + MiniLM-CE | `ws` + bge-reranker | `or` + bge-reranker |
|---|---|---|---|---|
| bge-small | 78 / 68 / 0.51 | 88 / 76 / 0.58 | 78 / 64 / 0.54 | 86 / 70 / 0.60 |
| e5-small | 78 / 70 / 0.54 | 88 / 78 / 0.57 | 78 / 68 / 0.56 | 86 / 72 / 0.59 |
| minilm | 82 / 72 / 0.55 | 88 / 74 / 0.58 | 80 / 72 / 0.57 | 84 / 76 / 0.61 |
| me5-small | 84 / 76 / 0.55 | 86 / 76 / 0.56 | 86 / 72 / 0.60 | 86 / 74 / 0.61 |
| bge-base | 86 / 72 / 0.55 | 86 / 76 / 0.57 | 82 / 74 / 0.60 | 88 / 76 / 0.62 |

**Cost of a reranker (2 vCPU, 20 chunks per question):**
- MiniLM-CE: p50 1,765 ms, peak RSS 1,246 MiB.
- bge-reranker-base: p50 11,302 ms, peak RSS 2,670 MiB.

Both are far over the plan's reranker gate (≤ 250 MiB extra, ≤ 300 ms extra p95), so neither is used.

### Latency by corpus size (database time, p95 / p50 ms, 1-vCore 2 GiB Postgres)

| Query (bge-base-q, glossary) | 904 chunks | 50k chunks | 50k, cold |
|---|---|---|---|
| **Vector-only (chosen)** | **2.7 / 1.9** | **2.6 / 1.4** | **70.5 / 1.5** (max 256) |
| Hybrid `ws` | 3.0 / 2.3 | 3.7 / 2.7 | 8.8 / 2.5 |
| Hybrid `idf5` | 4.4 / 3.2 | 116.1 / 57.2 | – |
| Hybrid `or` | 10.3 / 5.9 | 440.8 / 191.3 | – |

- **Without the glossary:**
  - hybrid `ws` at 50k: p95 4.3 ms;
  - hybrid `or` at 50k: p95 194.9 ms (bge-base-q), 199.9 ms (bge-base), 243.6 ms (me5-small).
- **Why the OR variants are slow:** they score every matching row with `ts_rank_cd`.
- **Plans:** at 904 rows the planner uses sequential scans. At 50k, `EXPLAIN` shows the HNSW and GIN indexes in use.

### Query embedder (2 vCPU, 2 threads, own process)

| Model | Peak RSS | Model's share (peak − 83 MiB baseline) | p50 / p95 ms per question | Load |
|---|---|---|---|---|
| bge-small | 266 MiB | 183 MiB | 7.5 / 10.8 | 0.7 s |
| e5-small | 293 MiB | 210 MiB | 5.8 / 7.7 | 1.0 s |
| minilm | 224 MiB | 141 MiB | 2.8 / 4.1 | 0.8 s |
| me5-small | 909 MiB | 826 MiB | 6.4 / 7.7 | 4.5 s |
| bge-base | 646 MiB | 563 MiB | 24.5 / 34.4 | 2.0 s |
| me5-small-q | 506 MiB | 424 MiB | 3.9 / 6.0 | 1.0 s |
| **bge-base-q** | **269 MiB** | **186 MiB** | **13.4 / 20.9** | **0.5 s** |

- multilingual-e5-small's 250k-token vocabulary dominates its size, even when quantised.
- Corpus embedding time on the laptop (16 threads, 904 chunks):
  - small models: 17–77 s;
  - bge-base: 192 s;
  - bge-base-q: 108 s.

### Index size and build time (capped server)

| Corpus | HNSW 384-d | HNSW 768-d | Embedding table total, 768-d | Chunks + GIN | HNSW build, 768-d |
|---|---|---|---|---|---|
| 904 chunks | 1.8 MiB | 3.5 MiB | 7.3 MiB | 2.6 MiB | 0.2 s |
| 50k chunks | 98 MiB | 195 MiB | 396 MiB | 101 MiB | 16–18 s |

**Postgres memory:**
- Loading the 50k corpus and building three HNSW indexes took the cgroup to its 2 GiB cap. Most of that was reclaimable page cache; the service was never OOM-killed and every statement completed.
- After a restart, the latency runs peaked at 410 MiB (403 MiB of it file cache).
- So 50k chunks at 768-d fits B1MS with room to spare. The index is 195 MiB against 512 MiB of shared buffers.

### Embedding placement (measured, not decided by the spike)

End-to-end time to embed one question from the API's side (bge-base-q, model process at 2 threads):

| Placement | p50 | p95 |
|---|---|---|
| Sidecar process, Unix socket | 12.9 ms | 16.9 ms |
| Worker reached through a Postgres queue (insert, then NOTIFY, then the worker embeds and writes back, then NOTIFY) | 16.2 ms | 19.8 ms |

- The queue path is a lower bound for Procrastinate, which adds job bookkeeping.
- Both keep the model out of the API process.
- **The owner chose the sidecar.** It changes [ADR-0012](../adr/0012-hosting-after-student-pack-change.md)'s VM budget (see Follow-ups).

### `τ` (confidence) data

- **The frozen rule** (`low` when the top chunk is in only one list and the fused score < τ) **can't be calibrated.** RRF scores depend only on rank:
  - with the AND lexical query, 43 of 50 answerable and 10 of 10 out-of-scope questions come out `low` at any τ;
  - with OR, the top chunk is always in both lists, so nothing is `low`.
- **Absolute signals.** For each signal, the best threshold under the plan's rule (≥ 80% of out-of-scope `low` and ≤ 10% of answerable `low`):

  | Signal | Answerable `low` | Out-of-scope `low` | Meets rule |
  |---|---|---|---|
  | Top-1 cosine, me5-small + glossary (t = 0.8446) | 10% | 80% | Exactly at the edge, fitted on the same 60 questions |
  | Top-1 cosine, bge-base-q + glossary (t = 0.6431) | 20% | 90% | No |
  | Top-1 cosine, every other model | 8–54% | 60–100% | No |
  | Reranker top score (all 10 runs) | 24–34% | 90–100% | No |

  With 10 out-of-scope questions, one question moves the out-of-scope rate by 10 points.
- **Decision (owner):** τ isn't gated in the MVP and goes to deferred.md §13 (below).

### Owner's lexical variant `idf5` and exact-identifier questions

- **`idf5` with the glossary:** recall@10 92% against 94% for vector-only, recall@5 78% against 76%, and p95 116 ms at 50k (within 300 ms).
  - Recall dropped by one question, so under the owner's rule the MVP uses **vector-only + glossary**.
  - `idf5` is recorded in ADR-0014 as the candidate if a lexical list is needed again.
- **Exact identifiers:** 10 identifier questions (`spikes/s2/identifiers.jsonl`), for example "What does section 393 of the Income-tax Act cover?", "What is form INC-1 used for?", "rule 8 CGST rules", "What did G.S.R. 300(E) change?".

  | Mode (bge-base-q, glossary) | recall@10 | recall@5 | MRR |
  |---|---|---|---|
  | **Vector-only** | **9/10** | 9/10 | 0.78 |
  | Hybrid `idf5` | 9/10 | 7/10 | 0.73 |
  | Hybrid `ws` | 9/10 | 9/10 | 0.78 |
  | Full-text `ws` | 4/10 | 4/10 | 0.40 |

  - The vector miss is "section 5 of the Telangana PT Act" (s.1 and s.4 rank above s.5).
  - Section paths and headings are in every embedded text, which is why the vector search handles identifiers.

## Failure analysis (chosen configuration)

| Question | Rank | Why |
|---|---|---|
| r002 "What has to go into the MoA when we incorporate?" | 11 | Near misses rank above it: Incorporation Rules 16(1) (subscriber particulars) and 13(3) (signing of the memorandum). Act s.4(1) is just outside the top 10; check in M5 whether parent-chunk context (rule 5) helps |
| r035 "ESIC ka employer contribution kitna hota hai?" (partial) | – | The top results are EPF Scheme 18(2) and Code s.25(4): PF contributions instead of ESI. The rates aren't in the corpus (partial). The glossary made this one worse (rank 17 → missed): expanding "ESIC" pulled in "employees'…" terms shared with EPF |
| r046 "What is the fee for shops registration in Telangana?" | 17 | The G.O. 54 amendment chunk is mostly a fee table of bare figures, with little text to match. Memo 337 and Act s.3(1) ("such fees as may be prescribed") rank first |

**Before the glossary**, the systematic misses were abbreviations: TCS (r030; s.394 never says "TCS"), RCM, PT, MoA, and Hinglish TDS (r031). Every model missed TCS (r030) without the glossary.

## Decision

| Item | Decision | Why |
|---|---|---|
| Embedding model | **`bge-base-en-v1.5`, int8 ONNX** (`Xenova/bge-base-en-v1.5`, `onnx/model_int8.onnx`, CLS pooling, normalised; query prefix "Represent this sentence for searching relevant passages: ") | The only model at ≥ 90% within 300 MiB: 94% recall@10, 269 MiB, p95 21 ms |
| `D` | **768** | Fixed for the M5 migration (`knowledge.chunk_embeddings.embedding vector(768)`) |
| Mode | **Vector-only + query glossary** ([ADR-0014](../adr/0014-retrieval-query-glossary-and-vector-only-ranking.md), Accepted) | The frozen lexical step adds nothing (6% alone). OR is too slow. `idf5` loses one question |
| Reranker | **Off** | 1.2–2.6 GiB and 1.8–11 s per query on 2 vCPU |
| `τ` | **Not gated in the MVP; deferred** ([deferred.md §13](../deferred.md)) | Not calibratable on this set; MVP retrieval has a human in the loop |
| Query embedding placement | **Sidecar process** (owner) | p95 17 ms; the model stays out of the API process |

**Outcome against the plan:** pass on recall, latency and RAM after ADR-0014. `τ` isn't met and is deferred by the owner.

## Corpus gaps for M5

Dropped as unanswerable from the S1 windows (from the draft set):
1. GST on an advance received for services: CGST Act s.13 (the window ends at s.12).
2. Discounts after the invoice: CGST Act s.15 (valuation).
3. Women on night shifts in Telangana: TS Shops and Establishments Act, the chapter after s.19.
4. Voluntary PF coverage for a small establishment: Code on Social Security s.1(4) and the related notification.
5. The due date for depositing deducted PT: TS PT Rules.

Partial items: the provision is in the corpus, the numbers aren't.
- **ESI coverage threshold and contribution rates:** Code s.1(4), the ESI rules and notifications (r034, r035).
- **The PT First Schedule, with its rates:** r048. The HTML source had the 37 sections only.
- **Overtime rate rules:** TS Shops Rules (r044).

Other gaps: the CBIC Central Tax notification (still missing from S1); a current consolidated Companies Act (the corpus copy predates s.10A).

## Reproduce

```bash
cd spikes/s2
uv sync
# Postgres 18 + pgvector without Docker/sudo, capped like B1MS:
mamba/bin/micromamba create -y -r mamba/root -p pgenv -c conda-forge 'postgresql=18' pgvector
pgenv/bin/initdb -D pgdata -U postgres --auth=trust -E UTF8 --locale=C.UTF-8   # then append the settings in Setup
systemd-run --user --unit=s2-pg -p MemoryMax=2G -p MemorySwapMax=0 -p CPUQuota=100% $PWD/pgenv/bin/postgres -D $PWD/pgdata
pgenv/bin/psql -h 127.0.0.1 -p 55432 -U postgres -c "create database s2" && pgenv/bin/psql -h 127.0.0.1 -p 55432 -U postgres -d s2 -c "create extension vector"
uv run python chunk.py                       # corpus/chunks.jsonl (needs spikes/s1 outputs)
uv run python build_labels.py                # evals/retrieval.jsonl (validates every label)
uv run python embed.py && uv run python embed.py --gloss
uv run python load.py real                   # all models; HNSW + GIN + lexdf
uv run python load.py syn 50000 me5-small bge-base bge-base-q
uv run python evaluate.py [--gloss] [--rerank] [--set=identifiers.jsonl]   # results/quality_*.json
uv run python latency.py <real|syn> <model> [ws|or|idf5|vec] [--gloss] [--cold]
systemd-run --user --scope -p CPUQuota=200% .venv/bin/python qembed.py embed bge-base-q   # also: rerank minilm-ce
uv run python placement.py bge-base-q
uv run python tau.py results/quality_bge-base-q_gx.json ws && uv run python tau_abs.py
```

## Follow-ups

- **Doc updates in this change:**
  - [ADR-0014](../adr/0014-retrieval-query-glossary-and-vector-only-ranking.md) (Accepted)
  - [`knowledge/query-glossary.yaml`](../../knowledge/query-glossary.yaml) v1
  - [data-pipeline.md](../data-pipeline.md) §1 (embedder), §2 (query-time embedding in a sidecar) and §6 (retrieval)
  - [tech-stack.md §3](../tech-stack.md#3-open-decisions-resolved-by-spikes) (embedder, reranker, `D`, `τ`)
  - [data-model.md §4.7](../data-model.md) (`D = 768`)
  - [architecture.md](../architecture.md) (embedding placement)
  - [evaluation.md §1](../evaluation.md) (labelled-set fields)
  - [build-plan.md §1.2](../build-plan.md) (τ)
  - [deferred.md §13](../deferred.md) (τ calibration)
  - [ADR-0012](../adr/0012-hosting-after-student-pack-change.md) (sidecar in the VM budget)
  - [status.md](../status.md) (D-8, D-30)
- **S5 (before M4):** measure API + worker + **embedding sidecar** together on the 1 GiB VM. The sidecar alone is 269 MiB, against ADR-0012's ~900 MiB for API + worker. Re-check query-embedding latency on the VM's CPU too: this laptop's cores are faster than the VM's.
- **Before M5 ships:**
  - Add the interview questions as `source: interview` (no names or personal details) and report recall by group.
  - Get the CA review of the labels.
  - Re-run the set on the M5 ingestion of current consolidated texts.
- **M5:**
  - Build parent chunks (rule 5) and check whether they fix near misses like r002.
  - Keep tables whole (rule 4). The flattened TDS tables still retrieve, but they're unreadable as citations.
  - Fill the corpus gaps above.
- **Phase 2 (Copilot):** τ calibration on held-out interview questions ([deferred.md §13](../deferred.md)).
