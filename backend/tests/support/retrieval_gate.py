"""CI retrieval gate (`make eval-retrieval`): fresh database -> fixture corpus -> `knowledge.eval` -> drop.

Needs TEST_DATABASE_ADMIN_URL (as the test suite). Passage vectors are cached on disk by (model id, text) in
`EMBEDDING_CACHE` (CI keeps it in actions/cache), so the corpus is embedded once per fixture/model change; query
vectors are always computed. Set EVAL_RECORD=1 to append the result to evals/results/.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import numpy as np
import yaml
from sqlalchemy import create_engine

from app.modules.knowledge import eval as retrieval_eval
from app.modules.knowledge.embedding.onnx import OnnxEmbedder
from app.modules.knowledge.ingest import FIXTURES, ingest_source
from app.modules.knowledge.registry import load_registry
from app.platform.db import CONNECT_OPTIONS
from tests.support.db import create_database, drop_database

CACHE = Path(
    os.environ.get(
        "EMBEDDING_CACHE", Path.home() / ".cache" / "buildone" / "fixture-embeddings.npz"
    )
)


class CachingEmbedder:
    def __init__(self, base: OnnxEmbedder, path: Path) -> None:
        self.base = base
        self.path = path
        self.cache: dict[str, np.ndarray] = dict(np.load(path)) if path.exists() else {}
        self.misses = 0

    @property
    def model_id(self) -> str:
        return self.base.model_id

    def _key(self, text: str) -> str:
        return hashlib.sha256(f"{self.model_id}\n{text}".encode()).hexdigest()

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        missing = [t for t in texts if self._key(t) not in self.cache]
        if missing:
            self.misses += len(missing)
            for text, vector in zip(missing, self.base.embed_passages(missing), strict=True):
                self.cache[self._key(text)] = np.asarray(vector, dtype=np.float32)
        return [self.cache[self._key(t)].astype(float).tolist() for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.base.embed_query(text)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(self.path, **self.cache)


def main(argv: list[str]) -> int:
    labels = (
        Path(argv[1])
        if len(argv) > 1
        else Path(__file__).resolve().parents[3] / "evals" / "retrieval.jsonl"
    )
    registry = load_registry()
    db = create_database("buildone_eval")
    try:
        engine = create_engine(db.url_for("app_ingest"), connect_args={"options": CONNECT_OPTIONS})
        embedder = CachingEmbedder(OnnxEmbedder(), CACHE)
        for entry in yaml.safe_load((FIXTURES / "fixtures.yaml").read_text(encoding="utf-8")):
            if entry.get("raster_of"):
                continue
            data = (FIXTURES / entry["file"]).read_bytes()
            ingest_source(
                engine,
                registry[entry["key"]],
                data,
                embedder=embedder,
                store=None,
                approve=True,
                report=False,
            )
        engine.dispose()
        embedder.save()
        print(f"fixture corpus loaded ({embedder.misses} passages embedded, rest cached)")  # noqa: T201
        os.environ["DATABASE_URL"] = db.url_for("app_api")
        args = [str(labels), "--corpus", "fixtures"]
        if not os.environ.get("EVAL_RECORD"):
            args.append("--no-write")
        return retrieval_eval.main(args)
    finally:
        drop_database(db)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
