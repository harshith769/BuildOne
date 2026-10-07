"""Knowledge base against a real Postgres (AGENTS.md rule 14): loading, superseding, review, retrieval, grants.

Embeddings come from the deterministic FakeEmbedder (retrieval quality is gated by `make eval-retrieval`).
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.modules.knowledge import ingestion, service
from app.modules.knowledge.embedding.client import EmbedderUnavailableError, SidecarEmbedder
from app.modules.knowledge.embedding.fake import FakeEmbedder
from app.modules.knowledge.embedding.sidecar import serve
from app.modules.knowledge.parsing.model import Line, Page, ParsedDocument
from app.modules.knowledge.registry import Source
from app.platform.db import CONNECT_OPTIONS
from tests.knowledge.conftest import word_offsets, words
from tests.support.db import EphemeralDatabase, role_connection

NOW = dt.datetime(2026, 10, 7, 6, 0, tzinfo=dt.UTC)
AS_OF = dt.date(2026, 10, 7)


class AsyncFake:
    def __init__(self) -> None:
        self.model = FakeEmbedder()

    async def embed_query(self, text: str) -> tuple[str, list[float]]:
        return self.model.model_id, self.model.embed_query(text)


def _source(key: str, **overrides: object) -> Source:
    data: dict[str, object] = {
        "key": key,
        "title": f"Test {key.replace('_', ' ').title()}",
        "authority": "Test Ministry",
        "jurisdiction": "IN",
        "doc_type": "act",
        "official_url": "https://www.indiacode.nic.in/test",
        "manual": "test",
        "effective_from": dt.date(2020, 1, 1),
    }
    return Source.model_validate({**data, **overrides})


def _doc(*lines: str, source: str = "text", confidence: float | None = None) -> ParsedDocument:
    page = Page(1, source, [Line(t, 1) for t in lines], confidence=confidence)  # type: ignore[arg-type]
    return ParsedDocument(parser="test@1", pages=[page])


def _prepare(source: Source, doc: ParsedDocument, raw: bytes) -> ingestion.PreparedVersion:
    return ingestion.prepare(
        source, raw, doc, embedder=FakeEmbedder(), count=words, offsets=word_offsets
    )


@pytest.fixture(scope="module")
def ingest_engine(test_db: EphemeralDatabase) -> Iterator[Engine]:
    engine = create_engine(test_db.url_for("app_ingest"), connect_args={"options": CONNECT_OPTIONS})
    yield engine
    engine.dispose()


def _load(
    engine: Engine, source: Source, doc: ParsedDocument, raw: bytes, *, approve: bool = False
) -> int:
    with engine.begin() as conn:
        return ingestion.load(conn, _prepare(source, doc, raw), fetched_at=NOW, approve=approve)


async def _search(api_engine: AsyncEngine, query: str, **filters: object) -> service.SearchResult:
    async with api_engine.begin() as conn:
        return await service.search(
            conn,
            query,
            service.SearchFilters(as_of=AS_OF, **filters),
            embedder=AsyncFake(),  # type: ignore[arg-type]
        )


SHOPS_V1 = (
    "CHAPTER II",
    "3. Registration of shops.- (1) Every shop shall be registered with the inspector.",
    "(2) The registration fee is paid online.",
    "4. Renewal of registration.- (1) Registration is renewed every year.",
)
SHOPS_V2 = (
    "CHAPTER II",
    "3. Registration of shops.- (1) Every shop shall be registered online within a day.",
    "(2) The registration fee is paid online.",
    "4. Renewal of registration.- (1) Renewal is not required.",
)


async def test_load_then_search_returns_active_ranked_chunks_with_parents(
    ingest_engine: Engine, api_engine: AsyncEngine
) -> None:
    source = _source("shops_act_a")
    assert _load(ingest_engine, source, _doc(*SHOPS_V1), b"v1-a") == 1
    result = await _search(api_engine, "shop registration inspector")
    mine = [c for c in result.ranked if c.source_key == "shops_act_a"]
    assert mine and all(c.section_path.startswith("Test Shops Act A > CHAPTER II > ") for c in mine)
    assert all(c.parent_id is not None for c in mine)
    assert result.context and all(
        p.chunk_id in {c.parent_id for c in result.selected} for p in result.context
    )
    with ingest_engine.connect() as conn:
        parents = conn.execute(
            text(
                "SELECT count(*) FROM knowledge.chunks c JOIN knowledge.chunk_embeddings e "
                "ON e.chunk_id = c.id WHERE c.kind = 'parent'"
            )
        ).scalar_one()
    assert parents == 0  # parent chunks are never embedded, so never ranked
    with ingest_engine.connect() as conn:  # same bytes again: the CLI skips them as unchanged
        assert ingestion.find_version_by_digest(conn, "shops_act_a", ingestion.sha256(b"v1-a")) == (
            1,
            "active",
        )


async def test_supersede_never_deletes_and_old_chunks_resolve_by_id(
    ingest_engine: Engine, api_engine: AsyncEngine
) -> None:
    source = _source("shops_act_b")
    _load(ingest_engine, source, _doc(*SHOPS_V1), b"v1-b")
    old = [
        c
        for c in (await _search(api_engine, "renewed every year")).ranked
        if c.source_key == "shops_act_b"
    ]
    assert _load(ingest_engine, source, _doc(*SHOPS_V2), b"v2-b") == 2
    with ingest_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT v.version, v.status, count(c.id), bool_or(c.is_active) FROM knowledge.source_versions v "
                "JOIN knowledge.sources s ON s.id = v.source_id JOIN knowledge.chunks c ON c.source_version_id = v.id "
                "WHERE s.key = 'shops_act_b' GROUP BY 1, 2 ORDER BY 1"
            )
        ).all()
    assert [(r[0], r[1], r[3]) for r in rows] == [(1, "superseded", False), (2, "active", True)]
    assert rows[0][2] > 0  # version 1's chunks are still there
    new = [
        c
        for c in (await _search(api_engine, "renewed every year")).ranked
        if c.source_key == "shops_act_b"
    ]
    assert {c.chunk_id for c in new}.isdisjoint({c.chunk_id for c in old})
    async with api_engine.connect() as conn:
        cited = await service.get_chunks(conn, [c.chunk_id for c in old])
    assert {c.chunk_id for c in cited} == {c.chunk_id for c in old}
    assert any("renewed every year" in c.text for c in cited)  # the exact superseded text


def test_nobody_can_delete_knowledge_rows(test_db: EphemeralDatabase) -> None:
    for role in ("app_ingest", "app_api", "app_worker"):
        with (
            role_connection(test_db, role) as conn,
            pytest.raises(psycopg.errors.InsufficientPrivilege),
        ):
            conn.execute("DELETE FROM knowledge.chunks")


@pytest.mark.parametrize("role", ["app_api", "app_worker"])
def test_services_only_read_knowledge(test_db: EphemeralDatabase, role: str) -> None:
    with role_connection(test_db, role) as conn:
        conn.execute("SELECT count(*) FROM knowledge.chunks")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE knowledge.chunks SET is_active = true")


async def test_review_gate_holds_ocr_pages_until_approved(
    ingest_engine: Engine, api_engine: AsyncEngine
) -> None:
    source = _source("scanned_memo", doc_type="circular", scanned=True)
    doc = _doc(
        "Subject: Registration within one day",
        "2. Renewal of registration is dispensed with.",
        source="ocr",
        confidence=88.0,
    )
    assert _load(ingest_engine, source, doc, b"scan") == 1
    with ingest_engine.connect() as conn:
        status, review = conn.execute(
            text(
                "SELECT v.status, v.review FROM knowledge.source_versions v JOIN knowledge.sources s "
                "ON s.id = v.source_id WHERE s.key = 'scanned_memo'"
            )
        ).one()
    assert status == "pending_review" and review["pages"] == [
        {"page": 1, "source": "ocr", "confidence": 88.0}
    ]
    hits = await _search(api_engine, "renewal of registration dispensed")
    assert all(c.source_key != "scanned_memo" for c in hits.ranked)
    with ingest_engine.begin() as conn:
        ingestion.approve(conn, "scanned_memo", 1)
    hits = await _search(api_engine, "renewal of registration dispensed")
    assert any(c.source_key == "scanned_memo" for c in hits.ranked)
    with (
        ingest_engine.begin() as conn,
        pytest.raises(ingestion.IngestionError, match="not pending_review"),
    ):
        ingestion.approve(conn, "scanned_memo", 1)


async def test_filters_jurisdiction_dates_and_doc_types(
    ingest_engine: Engine, api_engine: AsyncEngine
) -> None:
    lines = ("1. Professional tax.- (1) Every employer deducts professional tax from salary.",)
    _load(ingest_engine, _source("tg_pt_act", jurisdiction="IN-TG"), _doc(*lines), b"tg")
    _load(
        ingest_engine,
        _source("future_rules", doc_type="rules", effective_from=dt.date(2027, 4, 1)),
        _doc(*lines),
        b"fut",
    )
    _load(
        ingest_engine,
        _source("expired_rules", doc_type="rules", effective_to=dt.date(2026, 1, 1)),
        _doc(*lines),
        b"exp",
    )
    keys = lambda r: {c.source_key for c in r.ranked}  # noqa: E731
    everything = keys(await _search(api_engine, "employer professional tax salary"))
    assert "tg_pt_act" in everything and not {"future_rules", "expired_rules"} & everything
    assert "tg_pt_act" not in keys(
        await _search(api_engine, "employer professional tax", jurisdictions=("IN",))
    )
    only_rules = keys(await _search(api_engine, "employer professional tax", doc_types=("rules",)))
    assert "tg_pt_act" not in only_rules


def test_a_failed_load_writes_nothing(ingest_engine: Engine) -> None:
    source = _source("broken_load")
    prepared = _prepare(source, _doc(*SHOPS_V1), b"broken")
    prepared.vectors = prepared.vectors[:-1]  # one vector short: the insert fails mid-way
    with pytest.raises(ValueError), ingest_engine.begin() as conn:
        ingestion.load(conn, prepared, fetched_at=NOW)
    with ingest_engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM knowledge.sources WHERE key = 'broken_load'")
            ).scalar_one()
            == 0
        )


def test_empty_documents_are_refused() -> None:
    with pytest.raises(ingestion.IngestionError, match="no text"):
        _prepare(_source("empty_doc"), _doc(), b"")


async def test_sidecar_round_trip_and_errors(tmp_path: Path) -> None:
    socket_path = tmp_path / "embedder.sock"
    server = await serve(socket_path, FakeEmbedder())
    async with server:
        client = SidecarEmbedder(str(socket_path))
        model_id, vector = await client.embed_query(
            "When does TCS (tax collected at source) apply?"
        )
        assert model_id == "fake-hash-768" and len(vector) == 768
        with pytest.raises(EmbedderUnavailableError, match="non-empty"):
            await client.embed_query("   ")
    with pytest.raises(EmbedderUnavailableError):
        await SidecarEmbedder(str(tmp_path / "missing.sock"), timeout=0.5).embed_query("x")


def test_api_process_never_loads_the_model_or_the_parser() -> None:
    code = "import sys, app.main; print(sorted(m for m in ('onnxruntime', 'tokenizers', 'pymupdf', 'fitz') if m in sys.modules))"
    env = {**os.environ, "DATABASE_URL": "postgresql+psycopg://x:y@localhost/z"}
    out = subprocess.run(  # noqa: S603 - our own interpreter and a constant snippet
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env=env,
        cwd=Path(__file__).resolve().parents[2],
    )
    assert out.stdout.strip() == "[]"


@pytest.mark.skipif(
    not os.environ.get("S3_ENDPOINT_URL"), reason="needs an S3 endpoint (CI: SeaweedFS)"
)
def test_raw_sources_round_trip_through_object_storage() -> None:
    from app.platform.storage import S3ObjectStore

    store = S3ObjectStore(
        bucket="buildone-sources-test",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        access_key_id=os.environ.get("S3_ACCESS_KEY_ID", ""),
        secret_access_key=os.environ.get("S3_SECRET_ACCESS_KEY", ""),
    )
    store.ensure_bucket()
    key = f"sources/test/{uuid.uuid4().hex}.pdf"
    assert not store.exists(key)
    store.put(key, b"%PDF-1.7 test", content_type="application/pdf")
    assert store.exists(key) and store.get(key) == b"%PDF-1.7 test"
