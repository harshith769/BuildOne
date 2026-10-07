"""API-side query embedding: ask the sidecar over its Unix socket (no model in this process)."""

from __future__ import annotations

import asyncio

from app.modules.knowledge.embedding import DIMENSION
from app.modules.knowledge.embedding.protocol import encode_message, read_message


class EmbedderUnavailableError(RuntimeError):
    """The sidecar is down, slow, or answered with an error. Callers degrade (no retrieval), never fall back."""


class SidecarEmbedder:
    def __init__(self, socket_path: str, *, timeout: float = 2.0) -> None:
        self.socket_path = socket_path
        self.timeout = timeout

    async def embed_query(self, text: str) -> tuple[str, list[float]]:
        """(model_id, vector) for an already glossary-expanded question."""
        try:
            async with asyncio.timeout(self.timeout):
                reader, writer = await asyncio.open_unix_connection(self.socket_path)
                try:
                    writer.write(encode_message({"text": text}))
                    await writer.drain()
                    reply = await read_message(reader)
                finally:
                    writer.close()
        except (OSError, TimeoutError, ValueError, asyncio.IncompleteReadError) as exc:
            raise EmbedderUnavailableError(f"query embedder unavailable: {exc}") from exc
        vector = reply.get("vector")
        if "error" in reply or not isinstance(vector, list) or len(vector) != DIMENSION:
            raise EmbedderUnavailableError(
                f"query embedder error: {reply.get('error', 'bad vector')}"
            )
        return str(reply["model_id"]), [float(x) for x in vector]
