# BuildOne — Knowledge Data Pipeline (RAG)

> **Status:** v1.1 (frozen for MVP build; parser and embedding model chosen by spikes S1/S2; §6 changed by [ADR-0014](adr/0014-retrieval-query-glossary-and-vector-only-ranking.md)) · 2026-10-07 · Owner: @harshith769
> Tables: [data-model.md §4.7](data-model.md#47-knowledge-global-writable-by-app_ingest-read-by-services). Quality gates: [evaluation.md](evaluation.md).

**What this document answers**
- How official sources are registered, fetched, versioned, parsed, chunked, embedded, and loaded
- Where ingestion runs and with which credentials
- Exactly how hybrid retrieval ranks results and when it signals low confidence
- Which parts are swappable after spikes without architecture change

---

## 1. Stages

```
sources.yaml ─► fetch ─► store raw (R2) ─► parse ─► normalise tree ─► chunk ─► embed ─► load (transaction) ─► activate
```

| Stage | Interface (seam) | MVP implementation |
|---|---|---|
| Fetch | `Fetcher.fetch(url) -> bytes` | `httpx`; manual file drop for sources that block automated download |
| Parse | `Parser.parse(bytes, mime) -> DocumentTree` | Per [spike S1](spikes/S1-parsing.md): **PDF with a text layer:** PyMuPDF text layer + layout heuristic (margin notes as headings, running heads and footnotes dropped) and the PyMuPDF table finder. **Page without a text layer:** rendered at 300 dpi and OCR'd with Tesseract 5 (`eng`; `eng+hin` for bilingual sources). **Official HTML:** stdlib `html.parser`, with `<ol>` numbering kept. The adapter rules for building the tree are in the S1 report ("DocumentTree mapping notes") |
| Chunk | `chunk(tree, policy) -> list[Chunk]` | §4 |
| Embed | `Embedder.embed(texts) -> list[vector]` | Per [spike S2](spikes/S2-retrieval.md): **`bge-base-en-v1.5`, int8 ONNX** (`Xenova/bge-base-en-v1.5`, `onnx/model_int8.onnx`; CLS pooling, normalised; via fastembed/onnxruntime, no PyTorch), **`D = 768`**. Passages are embedded as in §4 rule 6; queries get the prefix "Represent this sentence for searching relevant passages: " after glossary expansion (§6 step 0). No reranker |
| Store raw | `ObjectStore.put(key, bytes)` | R2 via S3 API |

Swapping a parser or embedder changes only the implementation behind its interface ([ADR-0011](adr/0011-portability-rules.md)).

---

## 2. Where it runs

- **Ingestion CLI runs on the developer machine**, not on the 2 GB server: `uv run python -m app.modules.knowledge.ingest --source <key>` (or `--all`).
- Connects to production Postgres through an SSH tunnel using the `app_ingest` role (DML on `knowledge.*` only) and to R2 with a sources-bucket key.
- **Query-time embedding** (one short text per question) runs on the server with the same model and version, pinned in configuration, in a **separate sidecar process** (never in the API process): the API sends the expanded question over a local socket and gets the vector back. S2 measured 269 MiB peak RSS and p95 17 ms end to end at 2 threads ([S2](spikes/S2-retrieval.md#embedding-placement-measured-not-decided-by-the-spike); owner decision 2026-10-07). It counts against the VM budget in [ADR-0012](adr/0012-hosting-after-student-pack-change.md).

---

## 3. Source registry (`knowledge/sources.yaml`)

```yaml
- key: companies_act_2013              # stable, snake_case
  title: "Companies Act, 2013"
  authority: "Ministry of Corporate Affairs"
  jurisdiction: IN                     # IN | IN-TG
  doc_type: act                        # act | rules | notification | circular | form_instructions | guidance
  official_url: "<official URL>"       # must be a government domain
  effective_from: 2013-08-30           # as stated by the source
  published_on: null
  notes: ""
```

- Only official government sources are registered for citations. Secondary summaries may be read by humans but are never ingested.
- Re-ingestion: if the fetched bytes' SHA-256 equals the active version, nothing happens; otherwise a new `source_versions` row is created and the old one marked `superseded` (its chunks remain for existing citations, `is_active = false`).

---

## 4. Normalisation and chunking

**DocumentTree** node: `{heading, level, path, text_blocks[], tables[], children[]}`; `path` built as `"<Title> > Chapter II > Section 10A > (1)"`.

Chunking policy (Frozen defaults, tunable only via evaluation):
1. Each **leaf section** is one chunk if ≤ 500 tokens.
2. Longer leaves split at paragraph boundaries into 350–500-token chunks with 50-token overlap; all share the same `section_path` + ordinal.
3. Sibling leaves < 80 tokens under the same parent are merged.
4. Tables are kept whole; tables > 800 tokens are split by row groups with the header repeated.
5. Every section with children also gets a **parent chunk** (heading + first 200 tokens) used for context expansion, not for ranking.
6. Text embedded = `section_path + "\n" + heading + "\n" + text`.

---

## 5. Loading

One transaction per source version: insert `source_versions` → `chunks` → `chunk_embeddings` → set previous version `superseded` and its chunks `is_active=false`. Failure rolls back everything; the raw file stays in R2 keyed by SHA-256 (`sources/<key>/<sha256>.<ext>`).

---

## 6. Retrieval (Frozen algorithm; parameters tunable via evaluation)

Input: `query`, filters `{jurisdictions: [IN, IN-TG], as_of: date, doc_types?: [...]}`. Changed on 2026-10-07 by [ADR-0014](adr/0014-retrieval-query-glossary-and-vector-only-ranking.md) on the [S2](spikes/S2-retrieval.md) results.

0. **Expand abbreviations:** the first occurrence of each abbreviation in [`knowledge/query-glossary.yaml`](../knowledge/query-glossary.yaml) (versioned) gets its expansion appended in brackets ("TCS" → "TCS (tax collected at source, collection of tax at source)"). Deterministic, no AI. The expanded text is embedded.
1. **Filter:** `is_active AND jurisdiction = ANY(:j) AND effective_from <= :as_of AND (effective_to IS NULL OR effective_to > :as_of)`.
2. **Lexical:** **off in the MVP.** S2: `websearch_to_tsquery` (AND of all terms) found a relevant chunk for 6% of founder questions; OR of all terms took p95 441 ms at 50k chunks; OR of the ≤ 5 highest-IDF terms ("idf5") was fast enough (116 ms) but lost one question against vector-only. The `tsv` column and GIN index stay, so idf5 can return via an ADR-0014 update.
3. **Vector:** cosine distance on `chunk_embeddings` for the configured `model_id`, top 50 (`hnsw.ef_search = 64`).
4. **Fuse:** none while there is one list (Reciprocal Rank Fusion, `score = Σ 1/(60 + rank)`, applies if the lexical list returns); keep top 20.
5. **Rerank:** off (S2: 1.8–11 s and 1.2–2.6 GiB per query on 2 vCPU).
6. **Select:** top 5 chunks; add each chunk's parent chunk if the total stays ≤ 3,000 tokens.
7. **Confidence:** **not gated in the MVP** (retrieval serves rule drafting and citations with a human in the loop). S2 showed RRF scores are rank-only and cannot carry `τ`; calibrating a confidence signal on held-out real interview questions is required before the Copilot ([deferred.md §13](deferred.md)). Low confidence → Copilot abstains (FR-CORE-05).

Output: `list[RetrievedChunk(chunk_id, section_path, text, source_title, official_url, score)]` (`score` = cosine similarity).

Measured in S2 (bge-base int8, glossary, vector-only): recall@10 94% on `evals/retrieval.jsonl`; p95 2.6 ms database time at 50k chunks on a 1-vCore, 2 GiB Postgres (70.5 ms right after a restart); query embedding p95 21 ms.

---

## 7. Operational rules

- Ingestion is manual in MVP (run when sources change); v2 Change Radar automates detection.
- Every ingestion run writes a report (`knowledge/reports/<date>-<key>.md`, gitignored): pages, chunks, tokens, warnings (e.g., OCR confidence).
- Scanned PDFs with OCR confidence below the S1 threshold are flagged for manual review before activation. **Threshold ([S1](spikes/S1-parsing.md)):** a page is reviewed when its mean Tesseract word confidence is **< 93**. Inside other pages, lines with mean confidence **< 90** are listed as low-confidence in the ingestion report. Image pages that carry the publisher's own OCR layer are reviewed like scans. In S1, 9 of 10 scanned pages fell below 93, so in practice every scan is reviewed. Numbers read by Hindi (`hin`) OCR are never trusted.
