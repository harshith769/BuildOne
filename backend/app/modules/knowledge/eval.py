"""Retrieval evaluation (evaluation.md §1-3): `python -m app.modules.knowledge.eval <retrieval.jsonl>`.

Runs every labelled question through `service.search` against the database in `DATABASE_URL` (CI: the fixture
corpus loaded by `ingest --fixtures`; locally: the real corpus) and reports recall@10, recall@5 and MRR (within the
top 20), by group, for partial items, and latency (query embedding + database) p50/p95.

Gate (NFR-AI-06): recall@10 >= 90% over the answerable questions evaluated. A question is skipped only when one
of its labelled sources is not loaded; more than 10 skipped answerable questions, or fewer than 40 evaluated,
fails the run (owner rule, M5). A label that matches no active chunk of a loaded source is an error, never a skip.
Results are appended to `evals/results/<date>-retrieval.json`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.modules.knowledge import service
from app.modules.knowledge.embedding.client import SidecarEmbedder
from app.modules.knowledge.embedding.onnx import OnnxEmbedder
from app.modules.knowledge.labels import LabelKey, matches
from app.modules.knowledge.registry import REPO_ROOT
from app.platform.clock import SystemClock
from app.platform.db import CONNECT_OPTIONS

RECALL_GATE = 0.90
MIN_EVALUATED = 40
MAX_SKIPPED = 10
RESULTS = REPO_ROOT / "evals" / "results"


def _out(message: str) -> None:
    print(message, flush=True)  # noqa: T201 - CLI output


class LocalEmbedder:
    """In-process query embedder for the eval CLI, sized like the sidecar (2 threads)."""

    def __init__(self) -> None:
        self._model = OnnxEmbedder(threads=2)

    async def embed_query(self, text: str) -> tuple[str, list[float]]:
        return self._model.model_id, self._model.embed_query(text)


@dataclass
class ItemResult:
    id: str
    answerable: bool
    rank: (
        int | None
    )  # 1-based rank at which the item first counts as answered (top 20), None if never
    group: str
    partial: bool
    seconds: float


def first_hit(item: dict[str, Any], ranked: list[service.RetrievedChunk]) -> int | None:
    keys = [LabelKey.parse(k) for k in item["relevant_chunk_keys"]]
    every_source = item.get("match") == "every_source"
    needed = {k.source_key for k in keys}
    seen: set[str] = set()
    for position, chunk in enumerate(ranked, start=1):
        for key in keys:
            if matches(key, chunk.source_key, _path(chunk), chunk.ordinal, list(chunk.node_paths)):
                if not every_source:
                    return position
                seen.add(key.source_key)
        if every_source and seen == needed:
            return position
    return None


def _path(chunk: service.RetrievedChunk) -> str:
    prefix = f"{chunk.source_title} > "
    return chunk.section_path[len(prefix) :] if chunk.section_path.startswith(prefix) else ""


async def _loaded(engine: AsyncEngine) -> dict[str, list[tuple[str, int, list[str]]]]:
    """Active ranked chunks per loaded source: (section_path, ordinal, node_paths)."""
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT s.key, c.section_path, c.ordinal, c.node_paths
                FROM knowledge.chunks c
                JOIN knowledge.source_versions v ON v.id = c.source_version_id
                JOIN knowledge.sources s ON s.id = v.source_id
                WHERE c.is_active AND c.kind <> 'parent'
                """
            )
        )
        out: dict[str, list[tuple[str, int, list[str]]]] = {}
        for key, path, ordinal, nodes in rows:
            out.setdefault(key, []).append((path, ordinal, list(nodes)))
        return out


def unresolved_labels(
    items: list[dict[str, Any]], loaded: dict[str, list[tuple[str, int, list[str]]]]
) -> list[str]:
    bad = []
    for item in items:
        for raw in item["relevant_chunk_keys"]:
            key = LabelKey.parse(raw)
            if key.source_key in loaded and not any(
                matches(key, key.source_key, path, ordinal, nodes)
                for path, ordinal, nodes in loaded[key.source_key]
            ):
                bad.append(f"{item['id']}: {raw}")
    return bad


def _rate(results: list[ItemResult], k: int) -> float | None:
    return (
        sum(r.rank is not None and r.rank <= k for r in results) / len(results) if results else None
    )


def load_items(labels: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in labels.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


async def run(
    labels: Path, engine: AsyncEngine, *, corpus: str, sidecar: str | None = None
) -> dict[str, Any]:
    items = await asyncio.to_thread(load_items, labels)
    loaded = await _loaded(engine)
    bad = unresolved_labels(items, loaded)
    embedder: service.QueryEmbedder = SidecarEmbedder(sidecar) if sidecar else LocalEmbedder()
    answerable = [i for i in items if i["answerable"]]
    skipped = [
        i["id"]
        for i in answerable
        if any(LabelKey.parse(k).source_key not in loaded for k in i["relevant_chunk_keys"])
    ]
    evaluated: list[ItemResult] = []
    latencies: list[float] = []
    async with engine.connect() as conn:
        for item in items[:5]:  # warm-up (model, connection, index pages); not timed
            async with conn.begin():
                await service.search(conn, item["question"], _filters(item), embedder=embedder)
        for item in items:
            if item["id"] in skipped:
                continue
            start = time.perf_counter()
            async with conn.begin():
                result = await service.search(
                    conn, item["question"], _filters(item), embedder=embedder
                )
            seconds = time.perf_counter() - start
            latencies.append(seconds)
            if item["answerable"]:
                evaluated.append(
                    ItemResult(
                        item["id"],
                        True,
                        first_hit(item, result.ranked),
                        item.get("source", "synthetic"),
                        bool(item.get("partial")),
                        seconds,
                    )
                )
    latencies.sort()
    by_group: dict[str, Any] = {}
    for group in sorted({r.group for r in evaluated}):
        rows = [r for r in evaluated if r.group == group]
        by_group[group] = {"n": len(rows), "recall@10": _rate(rows, 10)}
    partial = [r for r in evaluated if r.partial]
    recall10 = _rate(evaluated, 10) or 0.0
    report = {
        "date": SystemClock().legal_today().isoformat(),
        "suite": "retrieval",
        "corpus": corpus,
        "labels": str(labels.relative_to(REPO_ROOT))
        if labels.is_relative_to(REPO_ROOT)
        else str(labels),
        "answerable": len(answerable),
        "evaluated": len(evaluated),
        "skipped": skipped,
        "unresolved_labels": bad,
        "recall@10": recall10,
        "recall@5": _rate(evaluated, 5),
        "mrr": statistics.fmean(1 / r.rank if r.rank else 0.0 for r in evaluated)
        if evaluated
        else None,
        "by_group": by_group,
        "partial": {"n": len(partial), "recall@10": _rate(partial, 10)},
        "misses": [r.id for r in evaluated if r.rank is None or r.rank > 10],
        "latency_ms": {
            "p50": round(1000 * statistics.median(latencies), 1) if latencies else None,
            "p95": round(1000 * latencies[int(0.95 * (len(latencies) - 1))], 1)
            if latencies
            else None,
            "n": len(latencies),
            "includes": "glossary + query embedding ("
            + ("sidecar over its socket" if sidecar else "in-process, 2 threads")
            + ") + database",
        },
    }
    report["passed"] = (
        not bad
        and len(evaluated) >= MIN_EVALUATED
        and len(skipped) <= MAX_SKIPPED
        and recall10 >= RECALL_GATE
    )
    return report


def _filters(item: dict[str, Any]) -> service.SearchFilters:
    f = item.get("filters") or {}
    return service.SearchFilters(
        as_of=date.fromisoformat(f.get("as_of", "2026-10-07")),
        jurisdictions=tuple(f.get("jurisdictions", ("IN", "IN-TG"))),
        doc_types=tuple(f["doc_types"]) if f.get("doc_types") else None,
    )


async def _run_with_engine(
    url: str, labels: Path, corpus: str, sidecar: str | None
) -> dict[str, Any]:
    engine = create_async_engine(url, connect_args={"options": CONNECT_OPTIONS})
    try:
        return await run(labels, engine, corpus=corpus, sidecar=sidecar)
    finally:
        await engine.dispose()


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1%}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.modules.knowledge.eval",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("labels", type=Path)
    parser.add_argument(
        "--corpus",
        default=os.environ.get("EVAL_CORPUS", "fixtures"),
        help="label for the results file: fixtures | real",
    )
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument(
        "--sidecar",
        metavar="SOCKET",
        help="embed queries through a running sidecar (latency check)",
    )
    args = parser.parse_args(argv)
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("set DATABASE_URL (any role that can read the knowledge schema)")
    report = asyncio.run(_run_with_engine(url, args.labels, args.corpus, args.sidecar))
    _out(
        f"retrieval ({report['corpus']}): recall@10 {_pct(report['recall@10'])}, recall@5 {_pct(report['recall@5'])}, "
        f"MRR {report['mrr']:.2f}; evaluated {report['evaluated']}/{report['answerable']} answerable; "
        f"latency p50 {report['latency_ms']['p50']} ms, p95 {report['latency_ms']['p95']} ms"
    )
    _out(
        f"skipped ({len(report['skipped'])}, labelled source not loaded): {', '.join(report['skipped']) or 'none'}"
    )
    _out(f"misses: {', '.join(report['misses']) or 'none'}")
    for line in report["unresolved_labels"]:
        _out(f"UNRESOLVED LABEL {line}")
    if not args.no_write:
        RESULTS.mkdir(parents=True, exist_ok=True)
        path = RESULTS / f"{report['date']}-retrieval-{report['corpus']}.json"
        history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        history.append(report)
        path.write_text(json.dumps(history, indent=1) + "\n", encoding="utf-8")
    _out(
        "PASS"
        if report["passed"]
        else "FAIL (gate: recall@10 >= 90%, >= 40 evaluated, <= 10 skipped, no unresolved labels)"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
