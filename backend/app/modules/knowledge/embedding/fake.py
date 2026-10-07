"""Deterministic stand-in for unit and integration tests that don't measure retrieval quality.

Vectors come from hashed word counts, so texts sharing words are close. Never used outside tests.
"""

from __future__ import annotations

import hashlib
import math
import re

from app.modules.knowledge.embedding import DIMENSION


class FakeEmbedder:
    model_id = "fake-hash-768"

    def _vector(self, text: str) -> list[float]:
        v = [0.0] * DIMENSION
        for word in re.findall(r"\w+", text.lower()):
            h = int.from_bytes(hashlib.blake2b(word.encode(), digest_size=4).digest(), "big")
            v[h % DIMENSION] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
