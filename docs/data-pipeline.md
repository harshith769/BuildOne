# BuildOne — Knowledge Data Pipeline (RAG)

> **Status:** v1.0 (frozen for MVP build; parser and embedding model chosen by spikes S1/S2) · 2026-09-28 · Owner: @harshith769
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
| Parse | `Parser.parse(bytes, mime) -> DocumentTree` | Winner of spike S1 |
| Chunk | `chunk(tree, policy) -> list[Chunk]` | §4 |
| Embed | `Embedder.embed(texts) -> list[vector]` | Winner of spike S2 (local CPU model) |
| Store raw | `ObjectStore.put(key, bytes)` | R2 via S3 API |

Swapping a parser or embedder changes only the implementation behind its interface ([ADR-0011](adr/0011-portability-rules.md)).

---

## 2. Where it runs

- **Ingestion CLI runs on the developer machine**, not on the 2 GB server: `uv run python -m app.modules.knowledge.ingest --source <key>` (or `--all`).
- Connects to production Postgres through an SSH tunnel using the `app_ingest` role (DML on `knowledge.*` only) and to R2 with a sources-bucket key.
- **Query-time embedding** (one short text per question) runs on the server with the same model and version, pinned in configuration.

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

Input: `query`, filters `{jurisdictions: [IN, IN-TG], as_of: date, doc_types?: [...]}`.

1. **Filter:** `is_active AND jurisdiction = ANY(:j) AND effective_from <= :as_of AND (effective_to IS NULL OR effective_to > :as_of)`.
2. **Lexical:** `websearch_to_tsquery('english', :q)` ranked by `ts_rank_cd`, top 50.
3. **Vector:** cosine distance on `chunk_embeddings` for the configured `model_id`, top 50 (`hnsw.ef_search = 64`).
4. **Fuse:** Reciprocal Rank Fusion, `score = Σ 1/(60 + rank)`; keep top 20.
5. **Rerank (optional):** only if spike S2 shows gain within RAM/latency budget.
6. **Select:** top 5 chunks; add each chunk's parent chunk if the total stays ≤ 3,000 tokens.
7. **Confidence:** `low` if the top chunk appears in only one of the two lists **and** its fused score < threshold `τ` (set from S2/S4 data). Low confidence → Copilot abstains (FR-CORE-05).

Output: `list[RetrievedChunk(chunk_id, section_path, text, source_title, official_url, score)]`.

---

## 7. Operational rules

- Ingestion is manual in MVP (run when sources change); v2 Change Radar automates detection.
- Every ingestion run writes a report (`knowledge/reports/<date>-<key>.md`, gitignored): pages, chunks, tokens, warnings (e.g., OCR confidence).
- Scanned PDFs with OCR confidence below the S1 threshold are flagged for manual review before activation.
