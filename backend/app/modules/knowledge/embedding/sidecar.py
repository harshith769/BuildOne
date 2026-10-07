"""Query-embedder sidecar process (ADR-0014; data-pipeline.md §2): `python -m app.modules.knowledge.embedding.sidecar`.

Holds the ONNX model so the API process never loads it. Listens on a Unix socket (`EMBEDDER_SOCKET`), embeds one
question per request with 2 threads (sized like the VM, S2). Only question text crosses the socket.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Protocol

from app.modules.knowledge.embedding.onnx import OnnxEmbedder
from app.modules.knowledge.embedding.protocol import encode_message, read_message

log = logging.getLogger("embedder")


class QueryModel(Protocol):
    @property
    def model_id(self) -> str: ...

    def embed_query(self, text: str) -> list[float]: ...


MAX_QUERY_CHARS = 4000


async def serve(socket_path: Path, embedder: QueryModel) -> asyncio.Server:
    lock = (
        asyncio.Lock()
    )  # one inference at a time: the session already uses every thread it is given

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                try:
                    request = await read_message(reader)
                except asyncio.IncompleteReadError:
                    break
                text = request.get("text")
                if not isinstance(text, str) or not text.strip() or len(text) > MAX_QUERY_CHARS:
                    reply: dict[str, object] = {"error": "text must be a non-empty string"}
                else:
                    async with lock:
                        vector = await asyncio.to_thread(embedder.embed_query, text)
                    reply = {"model_id": embedder.model_id, "vector": vector}
                writer.write(encode_message(reply))
                await writer.drain()
        except (ValueError, ConnectionError) as exc:
            log.warning("embedder request failed: %s", exc)
        finally:
            writer.close()

    # Once at start-up, before serving: blocking file calls are fine here.
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    socket_path.unlink(missing_ok=True)  # noqa: ASYNC240
    server = await asyncio.start_unix_server(handle, path=str(socket_path))
    os.chmod(socket_path, 0o660)
    return server


async def _main(socket_path: Path, threads: int) -> None:
    embedder = OnnxEmbedder(threads=threads)
    embedder.embed_query("warm up")
    server = await serve(socket_path, embedder)
    log.info("embedder listening on %s (%s)", socket_path, embedder.model_id)
    async with server:
        await server.serve_forever()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--socket", default=os.environ.get("EMBEDDER_SOCKET", "/run/embedder/embedder.sock")
    )
    parser.add_argument("--threads", type=int, default=int(os.environ.get("EMBEDDER_THREADS", "2")))
    args = parser.parse_args()
    asyncio.run(_main(Path(args.socket), args.threads))


if __name__ == "__main__":
    main()
