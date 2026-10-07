"""Wire format between the API and the embedder sidecar: one length-prefixed JSON message each way.

Request `{"text": "<expanded question>"}`; reply `{"model_id": "...", "vector": [768 floats]}` or
`{"error": "..."}`. A 4-byte big-endian length precedes each JSON body.
"""

from __future__ import annotations

import asyncio
import json
import struct
from typing import Any

MAX_MESSAGE = 1 << 20


async def read_message(reader: asyncio.StreamReader) -> dict[str, Any]:
    (size,) = struct.unpack(">I", await reader.readexactly(4))
    if size > MAX_MESSAGE:
        raise ValueError("message too large")
    body = json.loads(await reader.readexactly(size))
    if not isinstance(body, dict):
        raise ValueError("message must be a JSON object")
    return body


def encode_message(body: dict[str, Any]) -> bytes:
    data = json.dumps(body).encode()
    return struct.pack(">I", len(data)) + data
