"""bge-base-en-v1.5 int8 on onnxruntime (CPU). The only module that imports onnxruntime and tokenizers.

Loaded by the ingestion CLI (passages, all cores) and the sidecar (queries, 2 threads); never by the API.
S2 measured 269 MiB peak RSS and p95 21 ms per question at 2 threads.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from app.modules.knowledge.embedding import QUERY_PREFIX
from app.modules.knowledge.embedding.files import MODEL_ID, ensure_model_files

MAX_TOKENS = 512
BATCH = 16


@lru_cache(maxsize=1)
def load_tokenizer(cache_dir: Path | None = None) -> Tokenizer:
    tokenizer = Tokenizer.from_file(str(ensure_model_files(cache_dir).tokenizer))
    tokenizer.no_padding()
    tokenizer.no_truncation()
    return tokenizer


def count_tokens(text: str) -> int:
    """Tokens of `text` without special tokens (the chunking unit, data-pipeline.md §4)."""
    return len(load_tokenizer().encode(text, add_special_tokens=False).ids)


def token_offsets(text: str) -> list[tuple[int, int]]:
    return list(load_tokenizer().encode(text, add_special_tokens=False).offsets)


class OnnxEmbedder:
    def __init__(self, *, threads: int | None = None, cache_dir: Path | None = None) -> None:
        files = ensure_model_files(cache_dir)
        self._tokenizer = Tokenizer.from_file(str(files.tokenizer))
        self._tokenizer.enable_truncation(max_length=MAX_TOKENS)
        options = ort.SessionOptions()
        if threads:
            options.intra_op_num_threads = threads
            options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(files.model), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self._inputs = {i.name for i in self._session.get_inputs()}

    @property
    def model_id(self) -> str:
        return MODEL_ID

    def _run(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), BATCH):
            batch = texts[start : start + BATCH]
            self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")  # noqa: S106 - a token, not a secret
            encodings = self._tokenizer.encode_batch(batch)
            feed = {
                "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
                "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
                "token_type_ids": np.array([e.type_ids for e in encodings], dtype=np.int64),
            }
            hidden = self._session.run(None, {k: v for k, v in feed.items() if k in self._inputs})[
                0
            ]
            cls = hidden[:, 0, :]
            cls = cls / np.linalg.norm(cls, axis=1, keepdims=True)
            out.extend(cls.astype(float).tolist())
        return out

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return self._run(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._run([QUERY_PREFIX + text])[0]
