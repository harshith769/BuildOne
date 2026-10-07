"""Pinned model files: downloaded once over HTTPS, verified by SHA-256, cached on disk.

Changing any value here is a model change: new `model_id`, re-embedding, and before/after `make eval-retrieval`
numbers in the PR (evaluation.md §4, ADR-0014).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

REPO = "Xenova/bge-base-en-v1.5"
REVISION = "4d6cd88e18e51a5e020c2c305726d76ada9c03cf"
MODEL_ID = f"bge-base-en-v1.5-int8@{REVISION[:12]}"
FILES = {
    "tokenizer.json": "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66",
    "onnx/model_int8.onnx": "b83dfe249580ff1c2d0dcebe61ee565b1f6dcd5c2469632773d4508b9efd0889",
}
DEFAULT_CACHE = Path(
    os.environ.get("EMBEDDER_MODEL_DIR", Path.home() / ".cache" / "buildone" / "models")
)


class ModelFileError(RuntimeError):
    """A model file is missing, cannot be downloaded, or fails its checksum."""


@dataclass(frozen=True)
class ModelFiles:
    tokenizer: Path
    model: Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_model_files(cache_dir: Path | None = None, *, download: bool = True) -> ModelFiles:
    root = (cache_dir or DEFAULT_CACHE) / REPO.replace("/", "--") / REVISION
    for name, expected in FILES.items():
        target = root / name
        if target.exists() and _sha256(target) == expected:
            continue
        if not download:
            raise ModelFileError(f"model file missing or corrupt: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(target.suffix + ".part")
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{name}"
        try:
            with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
                response.raise_for_status()
                with partial.open("wb") as f:
                    for block in response.iter_bytes(1 << 20):
                        f.write(block)
        except httpx.HTTPError as exc:
            raise ModelFileError(f"cannot download {url}: {exc}") from exc
        if _sha256(partial) != expected:
            partial.unlink(missing_ok=True)
            raise ModelFileError(f"checksum mismatch for {name}")
        partial.replace(target)
    return ModelFiles(tokenizer=root / "tokenizer.json", model=root / "onnx" / "model_int8.onnx")
