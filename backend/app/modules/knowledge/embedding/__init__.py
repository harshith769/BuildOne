"""The `Embedder` seam (build-plan.md §1.2; S2 decision, ADR-0014).

Model: `bge-base-en-v1.5`, int8 ONNX (`Xenova/bge-base-en-v1.5`, `onnx/model_int8.onnx`), CLS pooling, normalised,
`D = 768`. Passages are embedded as stored; queries get the bge query prefix after glossary expansion. The ONNX
runtime is loaded only by the ingestion CLI and the sidecar process (`embedding.sidecar`), never by the API or
the worker: the API asks the sidecar over a Unix socket (`embedding.client`).
"""

from __future__ import annotations

from typing import Protocol

DIMENSION = 768
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder(Protocol):
    @property
    def model_id(self) -> str:
        """Stored with every vector (`chunk_embeddings.model_id`): model name plus pinned revision."""
        ...

    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]:
        """Embed one (already glossary-expanded) question; the query prefix is added here."""
        ...
