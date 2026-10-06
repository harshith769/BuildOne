"""API entry point. `uvicorn app.main:app` uses the module-level app; tests call `create_app(settings)`."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter, FastAPI

from app.platform import health
from app.platform.config import Settings, get_settings
from app.platform.db import create_engine
from app.platform.errors import install_error_handlers
from app.platform.logging import configure_logging
from app.platform.middleware import RequestContextMiddleware


def _version() -> str:
    try:
        return version("buildone-backend")
    except PackageNotFoundError:
        return "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await app.state.engine.dispose()

    app = FastAPI(
        title="BuildOne API",
        version=_version(),
        openapi_url="/v1/openapi.json",
        docs_url="/v1/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = create_engine(settings)  # lazy: connects on first use

    install_error_handlers(app, root_domain=settings.root_domain)
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health.router)
    v1 = APIRouter(prefix="/v1")
    # Module routers are mounted here from M2 onward (identity, tenancy, ...).
    app.include_router(v1)
    return app


def __getattr__(name: str) -> FastAPI:
    # `uvicorn app.main:app` resolves `app` lazily, so importing this module (e.g. for OpenAPI export)
    # doesn't require DATABASE_URL to be set.
    if name == "app":
        return create_app()
    raise AttributeError(name)
