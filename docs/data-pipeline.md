# BuildOne — Knowledge Data Pipeline (RAG)

> **Status:** v1.2 (frozen for MVP build; parser and embedding model chosen by spikes S1/S2; §6 changed by [ADR-0014](adr/0014-retrieval-query-glossary-and-vector-only-ranking.md); implemented in M5) · 2026-10-07 · Owner: @harshith769
> Code: `backend/app/modules/knowledge/` (`registry`, `parsing/`, `chunking`, `embedding/`, `ingestion`, `ingest` CLI, `service`, `eval`).
> Tables: [data-model.md §4.7](data-model.md#47-knowledge-global-writable-by-app_ingest-read-by-services). Quality gates: [evaluation.md](evaluation.md).

**What this document answers**
- How official sources are registered, fetched, versioned, parsed, chunked, embedded, and loaded
- Where ingestion runs and with which credentials
- Exactly how hybrid retrieval ranks results and when it signals low confidence
- Which parts are swappable after spikes without architecture change

---

## 1. Stages

```
sources.yaml ─► fetch ─► store raw (S3 API) ─► parse ─► normalise tree ─► chunk ─► embed ─► load (transaction) ─► activate (or review)
```

| Stage | Interface (seam) | MVP implementation |
|---|---|---|
| Fetch | `ingest.fetch(source) -> bytes` | `httpx` for `download_url`; otherwise a file dropped by hand into `knowledge/inbox/<key>.<ext>` (sites that block scripts), or `--file` |
| Parse | `parse(bytes, format, bilingual) -> ParsedDocument`, then `build_tree() -> DocumentTree` | Per [spike S1](spikes/S1-parsing.md): **PDF with a text layer:** PyMuPDF text layer + layout heuristic (margin notes as headings, running heads dropped, small-type footnotes kept as notes, never structure) and the PyMuPDF table finder (only tables with visible rules; borderless Word layout grids are body text). **Page without a text layer (< 50 characters):** rendered at 300 dpi and OCR'd with Tesseract 5 (`eng`; `eng+hin` for bilingual sources). **Invisible text over a page image** (the publisher's own OCR) is used but reviewed. **Bilingual pages:** a page that is mostly Devanagari (the Hindi half of a Gazette) is skipped; on a mixed page whose Hindi layer is undecodable (≥ 5% of vowel signs in impossible positions, ≥ 100 Devanagari letters), the lines with Devanagari are replaced by Tesseract `eng+hin` lines at the same height, while English lines and tables keep the text layer (OCR misreads printed numbers). Hindi is never indexed. **Official HTML:** stdlib `html.parser`, `<ol>` numbering kept; an `html_bundle` (zip of an index page plus one page per section) takes section numbers from the index. Tree rules: the S1 report's "DocumentTree mapping notes", implemented in `parsing/structure.py` |
| Chunk | `chunk(tree, policy) -> list[Chunk]` | §4 |
| Embed | `Embedder.embed(texts) -> list[vector]` | Per [spike S2](spikes/S2-retrieval.md): **`bge-base-en-v1.5`, int8 ONNX** (`Xenova/bge-base-en-v1.5`, `onnx/model_int8.onnx`; CLS pooling, normalised; via fastembed/onnxruntime, no PyTorch), **`D = 768`**. Passages are embedded as in §4 rule 6; queries get the prefix "Represent this sentence for searching relevant passages: " after glossary expansion (§6 step 0). No reranker |
| Store raw | `ObjectStore.put(key, bytes)` | S3 API (`app.platform.storage`): SeaweedFS locally and in CI, R2 in production; bucket `S3_BUCKET_SOURCES` |

Swapping a parser or embedder changes only the implementation behind its interface ([ADR-0011](adr/0011-portability-rules.md)).

---

## 2. Where it runs

- **Ingestion CLI runs on the developer machine**, not on the 2 GB server: `make ingest SOURCE=<key>` (`SOURCE=--all` for every source with a file), i.e. `uv run python -m app.modules.knowledge.ingest --source <key>`. `--approve <key>@<version>` activates a version waiting for review; `--fixtures` loads the test corpus. PyMuPDF and Tesseract are needed only here (uv group `ingest`; not in the server image).
- Connects as `app_ingest` (`INGEST_DATABASE_URL`: SELECT/INSERT/UPDATE on `knowledge.*`, no DELETE) — locally the compose Postgres on the host port, in production through an SSH tunnel — and to the sources bucket (`S3_*`: local SeaweedFS during the build, R2 once hosting exists).
- **Query-time embedding** (one short text per question) runs on the server with the same model and version, pinned in configuration, in a **separate sidecar process** (never in the API process): the API sends the expanded question over a local socket and gets the vector back. S2 measured 269 MiB peak RSS and p95 17 ms end to end at 2 threads ([S2](spikes/S2-retrieval.md#embedding-placement-measured-not-decided-by-the-spike); owner decision 2026-10-07). It counts against the VM budget in [ADR-0012](adr/0012-hosting-after-student-pack-change.md).

---

## 3. Source registry (`knowledge/sources.yaml`)

```yaml
- key: companies_act_2013              # stable, snake_case
  title: "Companies Act, 2013"
  authority: "Ministry of Corporate Affairs"
  jurisdiction: IN                     # IN | IN-TG
  doc_type: act                        # act | rules | notification | circular | form_instructions | guidance
  official_url: "<official URL>"       # https, *.gov.in or *.nic.in (validated)
  download_url: "<direct file URL>"    # optional, official domain; else `manual`
  manual: "<where to download by hand>"  # file goes to knowledge/inbox/<key>.<ext>
  format: pdf                          # pdf | html | html_bundle (zip: index.html + section pages)
  bilingual: false                     # OCR uses eng+hin
  scanned: false                       # image-only source (pages reviewed, §7)
  effective_from: 2013-08-30           # as stated by the source
  effective_to: null
  published_on: null
  notes: ""
```

- Only official government sources are registered for citations. Secondary summaries may be read by humans but are never ingested.
- Re-ingestion: if the fetched bytes' SHA-256 equals a version that is active or waiting for review, nothing happens; otherwise a new `source_versions` row is created and the old one marked `superseded` (its chunks remain for existing citations, `is_active = false`; nothing is ever deleted).

---

## 4. Normalisation and chunking

**DocumentTree** node: `{kind, ident, heading, content[text | table], notes[], children[]}`; kinds: chapter, part (also lettered parts such as "B.—Deduction and collection at source"), block (unnumbered containers of circulars and orders: "Subject", "Read", "ORDER", "AMENDMENT", which restart the numbering), section (sections, rules, paragraphs), sub-section, annex ("FORM …", "Annexure", "Appendix", "Schedule": its numbered rows are never rules). `path` uses the printed identifiers: `CHAPTER II > 10A > (1)`; the stored `section_path` is prefixed with the source title. Leaves are sub-sections, or sections/paragraphs/annexes without them; clauses, provisos and explanations stay in their sub-section's text so a chunk always carries its lead-in. A node's own text before its first child is a unit of its own (sibling of the children for rule 3).

Chunking policy (Frozen defaults, tunable only via evaluation):
1. Each **leaf section** is one chunk if ≤ 500 tokens.
2. Longer leaves split at paragraph boundaries into 350–500-token chunks with 50-token overlap; all share the same `section_path` + ordinal.
3. Sibling leaves < 80 tokens under the same parent are merged.
4. Tables are kept whole (one `cell | cell` line per row, empty cells left out); tables > 800 tokens are split by row groups with the header repeated. Inside a leaf over 500 tokens, each table becomes its own chunk (`kind = table`) between the text pieces.
5. Every section with children also gets a **parent chunk** (heading + first 200 tokens) used for context expansion, not for ranking.
6. Text embedded = `section_path + "\n" + heading + "\n" + text`.

---

## 5. Loading

Downloading and storing the raw file happen first, outside the database (AGENTS.md rule 12); the raw file is keyed by SHA-256 (`sources/<key>/<sha256>.<ext>`). Then one transaction per source version: upsert `sources` → set the previous active version `superseded` and its chunks `is_active=false` (only when the new version is active) → insert `source_versions` → `chunks` (parent chunks first, so every chunk points at its parent) → `chunk_embeddings` (ranked chunks only; parent chunks are never embedded). Failure rolls back everything. Rows are never deleted: DELETE and TRUNCATE are revoked from every role, so a citation always resolves to the exact version it cited (`service.get_chunks`). A version that needs review loads as `pending_review` with `is_active=false`; `ingest --approve <key>@<version>` supersedes the active version and activates it.

---

## 6. Retrieval (Frozen algorithm; parameters tunable via evaluation)

Input: `query`, filters `{jurisdictions: [IN, IN-TG], as_of: date, doc_types?: [...]}`. Changed on 2026-10-07 by [ADR-0014](adr/0014-retrieval-query-glossary-and-vector-only-ranking.md) on the [S2](spikes/S2-retrieval.md) results.

0. **Expand abbreviations:** the first occurrence of each abbreviation in [`knowledge/query-glossary.yaml`](../knowledge/query-glossary.yaml) (versioned) gets its expansion appended in brackets ("TCS" → "TCS (tax collected at source, collection of tax at source)"). Deterministic, no AI. The expanded text is embedded.
1. **Filter:** `is_active AND jurisdiction = ANY(:j) AND effective_from <= :as_of AND (effective_to IS NULL OR effective_to > :as_of)`.
2. **Lexical:** **off in the MVP.** S2: `websearch_to_tsquery` (AND of all terms) found a relevant chunk for 6% of founder questions; OR of all terms took p95 441 ms at 50k chunks; OR of the ≤ 5 highest-IDF terms ("idf5") was fast enough (116 ms) but lost one question against vector-only. The `tsv` column and GIN index stay, so idf5 can return via an ADR-0014 update.
3. **Vector:** cosine distance on `chunk_embeddings` for the configured `model_id`, top 50 (`hnsw.ef_search = 64`, `hnsw.iterative_scan = relaxed_order` so the step-1 filter never starves the list). Parent chunks have no embedding, so they are never ranked.
4. **Fuse:** none while there is one list (Reciprocal Rank Fusion, `score = Σ 1/(60 + rank)`, applies if the lexical list returns); keep top 20.
5. **Rerank:** off (S2: 1.8–11 s and 1.2–2.6 GiB per query on 2 vCPU).
6. **Select:** top 5 chunks; add each chunk's parent chunk if the total stays ≤ 3,000 tokens.
7. **Confidence:** **not gated in the MVP** (retrieval serves rule drafting and citations with a human in the loop). S2 showed RRF scores are rank-only and cannot carry `τ`; calibrating a confidence signal on held-out real interview questions is required before the Copilot ([deferred.md §13](deferred.md)). Low confidence → Copilot abstains (FR-CORE-05).

Output: `list[RetrievedChunk(chunk_id, section_path, text, source_title, official_url, score)]` (`score` = cosine similarity).

Measured in S2 (bge-base int8, glossary, vector-only): recall@10 94% on `evals/retrieval.jsonl`; p95 2.6 ms database time at 50k chunks on a 1-vCore, 2 GiB Postgres (70.5 ms right after a restart); query embedding p95 21 ms.

---

## 7. Operational rules

- Ingestion is manual in MVP (run when sources change); v2 Change Radar automates detection.
- Every ingestion run writes a report (`knowledge/reports/<date>-<key>.md`, gitignored): version, status, parser, pages, chunks, tokens, warnings, pages needing review and low-confidence lines. The same review data is stored in `source_versions.review`.
- Scanned PDFs with OCR confidence below the S1 threshold are flagged for manual review before activation. **Threshold ([S1](spikes/S1-parsing.md)):** a page is reviewed when its mean Tesseract word confidence is **< 93**. Inside other pages, lines with mean confidence **< 90** are listed as low-confidence in the ingestion report. Image pages that carry the publisher's own OCR layer are reviewed like scans. In S1, 9 of 10 scanned pages fell below 93, so in practice every scan is reviewed. Numbers read by Hindi (`hin`) OCR are never trusted. A version with any page to review loads as `pending_review` (not searchable); after checking the report, `ingest --approve <key>@<version>` activates it. Hindi lines OCR'd on mixed bilingual pages don't trigger review (they are not indexed).
