"""Write the OpenAPI document to a file: `python -m app.tools.export_openapi <path>` (used by `make openapi`).

Needs no database: the engine is created lazily and never connects.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.main import create_app
from app.platform.config import Settings


def export(path: Path) -> None:
    settings = Settings(
        database_url="postgresql+psycopg://openapi@localhost:5432/openapi", log_level="WARNING"
    )
    schema = create_app(settings).openapi()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m app.tools.export_openapi <output.json>", file=sys.stderr)  # noqa: T201
        return 2
    export(Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
