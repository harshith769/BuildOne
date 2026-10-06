from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import APIRouter
from pydantic import BaseModel

from app.main import create_app
from app.platform.config import Settings
from app.platform.errors import NotFound
from app.platform.health import migration_heads


class _Body(BaseModel):
    name: str
    count: int


@pytest.fixture
async def client(api_settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(api_settings)
    probe = APIRouter(prefix="/v1/_test")

    @probe.get("/missing")
    async def missing() -> None:
        raise NotFound("No such thing")

    @probe.post("/echo")
    async def echo(body: _Body) -> _Body:
        return body

    @probe.get("/boom")
    async def boom() -> None:
        raise RuntimeError("unexpected")

    app.include_router(probe)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await app.state.engine.dispose()


async def test_healthz(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


async def test_readyz_is_ready_after_migrations(client: httpx.AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "migrations": "ok", "queue": "ok"},
    }


async def test_readyz_reports_database_down() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://nobody:wrong@127.0.0.1:1/none", log_level="WARNING"
    )
    app = create_app(settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        response = await c.get("/readyz")
    await app.state.engine.dispose()
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "fail"


def test_single_migration_head() -> None:
    assert len(migration_heads()) == 1, "migrations must have exactly one head"


async def test_request_id_is_echoed_and_used_in_problems(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/_test/missing", headers={"X-Request-ID": "req-abcdef12"})
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["x-request-id"] == "req-abcdef12"
    body = response.json()
    assert body["code"] == "not_found"
    assert body["detail"] == "No such thing"
    assert body["request_id"] == "req-abcdef12"
    assert body["type"] == "https://localhost/problems/not-found"


async def test_validation_errors_are_400_with_field_list(client: httpx.AsyncClient) -> None:
    response = await client.post("/v1/_test/echo", json={"name": "x", "count": "many"})
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["errors"][0]["field"] == "count"


async def test_unknown_route_is_a_problem_document(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_unexpected_errors_hide_details(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/_test/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "internal_error"
    assert "unexpected" not in body["detail"]
    assert body["request_id"]


async def test_openapi_served_under_v1(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/openapi.json")
    assert response.status_code == 200
    assert "/readyz" in response.json()["paths"]
