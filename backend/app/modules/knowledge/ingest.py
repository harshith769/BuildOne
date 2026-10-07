"""Ingestion CLI (data-pipeline.md §2): `python -m app.modules.knowledge.ingest` (`make ingest SOURCE=<key>`).

Runs on the developer laptop (never on the server) as `app_ingest` (`INGEST_DATABASE_URL`, else `DATABASE_URL`).
For each source: get the bytes (`download_url`, or a file dropped into `knowledge/inbox/<key>.<ext>`, or `--file`),
skip if the same bytes are already loaded, store the raw file in the sources bucket (SeaweedFS locally, R2 in
production) keyed by SHA-256, parse, chunk, embed, load in one transaction, and write a report to
`knowledge/reports/<date>-<key>.md`.

  --source KEY [--file PATH]   one source          --all            every registered source with a file
  --approve KEY@VERSION        activate a version waiting for review (after checking its report)
  --force                      re-load unchanged bytes as a new version (after a parser or chunking change)
  --fixtures [DIR]             load the test fixture corpus (CI retrieval gate); fixtures are approved
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
import yaml
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.modules.knowledge import ingestion
from app.modules.knowledge.embedding import Embedder
from app.modules.knowledge.embedding.onnx import OnnxEmbedder, count_tokens, token_offsets
from app.modules.knowledge.parsing import parse
from app.modules.knowledge.registry import DEFAULT_REGISTRY, REPO_ROOT, Source, load_registry
from app.platform.clock import SystemClock
from app.platform.config import Settings
from app.platform.db import CONNECT_OPTIONS
from app.platform.storage import S3ObjectStore

INBOX = REPO_ROOT / "knowledge" / "inbox"
REPORTS = REPO_ROOT / "knowledge" / "reports"
FIXTURES = REPO_ROOT / "backend" / "tests" / "fixtures" / "knowledge"
USER_AGENT = "BuildOne-ingest/1 (+official sources only)"


def _out(message: str) -> None:
    print(message, flush=True)  # noqa: T201 - CLI output


def database_engine() -> Engine:
    url = os.environ.get("INGEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("set INGEST_DATABASE_URL (app_ingest) or DATABASE_URL")
    return create_engine(url, connect_args={"options": CONNECT_OPTIONS})


def fetch(source: Source, file: Path | None) -> bytes:
    if file is not None:
        return file.read_bytes()
    dropped = INBOX / f"{source.key}.{source.extension}"
    if dropped.exists():
        return dropped.read_bytes()
    if source.download_url:
        response = httpx.get(
            source.download_url,
            follow_redirects=True,
            timeout=120,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        return response.content
    raise ingestion.IngestionError(
        f"{source.key}: download by hand ({source.manual}) into {dropped}"
    )


def _bullets(lines: list[str]) -> list[str]:
    return lines or ["- none"]


def write_report(
    prepared: ingestion.PreparedVersion, version: int | None, status: str, now: datetime
) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"{now.date().isoformat()}-{prepared.source.key}.md"
    ranked = [c for c in prepared.chunks if c.kind != "parent"]
    lines = [
        f"# Ingestion report: {prepared.source.key}",
        "",
        f"- Title: {prepared.source.title}",
        f"- Version: {version} ({status}); sha256 `{prepared.digest}`; raw `{prepared.storage_key}`",
        f"- Parser: {prepared.document.parser}; embedder: {prepared.model_id}",
        f"- Pages: {len(prepared.document.pages)}; chunks: {len(ranked)} ranked + "
        f"{len(prepared.chunks) - len(ranked)} parent; tokens: {sum(c.token_count for c in ranked)}",
        "",
        "## Warnings",
        *(_bullets([f"- {w}" for w in prepared.document.warnings])),
        "",
        "## Pages needing review (OCR confidence < 93, or publisher OCR layer)",
        *_bullets(
            [
                f"- page {p['page']}: {p['source']}, confidence {p['confidence']}"
                for p in prepared.review["pages"]
            ]
        ),
        "",
        "## Low-confidence lines (< 90) on other pages",
        *_bullets(
            [
                f"- p{ln['page']} ({ln['confidence']}): {ln['text']}"
                for ln in prepared.review["low_confidence_lines"]
            ]
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def ingest_source(
    engine: Engine,
    source: Source,
    data: bytes,
    *,
    embedder: Embedder,
    store: S3ObjectStore | None,
    approve: bool = False,
    report: bool = True,
    force: bool = False,
) -> str:
    clock = SystemClock()
    digest = ingestion.sha256(data)
    with engine.connect() as conn:
        existing = ingestion.find_version_by_digest(conn, source.key, digest)
    if existing is not None and not force:
        return f"{source.key}: unchanged (version {existing[0]}, {existing[1]})"
    document = parse(data, format=source.format, bilingual=source.bilingual)
    prepared = ingestion.prepare(
        source, data, document, embedder=embedder, count=count_tokens, offsets=token_offsets
    )
    if store is not None:
        if not store.exists(prepared.storage_key):
            store.put(
                prepared.storage_key, data, content_type=ingestion.CONTENT_TYPES[source.format]
            )
    else:
        prepared.storage_key = f"fixtures/{source.key}.{source.extension}"
    now = clock.now()
    with engine.begin() as conn:
        version = ingestion.load(conn, prepared, fetched_at=now, approve=approve)
    status = "pending_review" if prepared.needs_review and not approve else "active"
    where = f"; report {write_report(prepared, version, status, now)}" if report else ""
    ranked = sum(1 for c in prepared.chunks if c.kind != "parent")
    return f"{source.key}: version {version} {status}, {ranked} chunks{where}"


def _store(settings: Settings) -> S3ObjectStore:
    store = S3ObjectStore(
        bucket=settings.s3_bucket_sources,
        endpoint_url=settings.s3_endpoint_url or None,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        region=settings.s3_region,
    )
    if settings.environment != "production":
        store.ensure_bucket()
    return store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.modules.knowledge.ingest",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source")
    group.add_argument("--all", action="store_true")
    group.add_argument("--approve", metavar="KEY@VERSION")
    group.add_argument("--fixtures", nargs="?", const=str(FIXTURES), metavar="DIR")
    parser.add_argument("--file", type=Path)
    parser.add_argument(
        "--force",
        action="store_true",
        help="load a new version even if the bytes are unchanged (parser change)",
    )
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args(argv)
    registry = load_registry(args.registry)
    engine = database_engine()
    if args.approve:
        key, _, version = args.approve.partition("@")
        with engine.begin() as conn:
            ingestion.approve(conn, key, int(version))
        _out(f"{key}@{version}: approved and active")
        return 0
    embedder = OnnxEmbedder()
    failures = 0
    if args.fixtures:
        root = Path(args.fixtures)
        manifest = yaml.safe_load((root / "fixtures.yaml").read_text(encoding="utf-8"))
        for entry in manifest:
            if entry.get("raster_of"):
                continue  # parser-only fixtures
            source = registry[entry["key"]]
            data = (root / entry["file"]).read_bytes()
            _out(
                ingest_source(
                    engine, source, data, embedder=embedder, store=None, approve=True, report=False
                )
            )
        return 0
    store = _store(
        Settings(database_url=os.environ.get("INGEST_DATABASE_URL") or os.environ["DATABASE_URL"])
    )
    keys = [args.source] if args.source else list(registry)
    for key in keys:
        if key not in registry:
            raise SystemExit(f"unknown source {key!r} (see {args.registry})")
        try:
            data = fetch(registry[key], args.file if args.source else None)
            _out(
                ingest_source(
                    engine, registry[key], data, embedder=embedder, store=store, force=args.force
                )
            )
        except (ingestion.IngestionError, httpx.HTTPError) as exc:
            failures += 1
            _out(f"{key}: FAILED: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
