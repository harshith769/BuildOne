"""API entry point. `uvicorn app.main:app` uses the module-level app; tests call `create_app(settings)`."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.identity.api import FAKE_AUTHORIZE_PATH, auth_router, fake_idp_router, me_router
from app.modules.identity.providers.base import IdentityProvider
from app.modules.identity.providers.fake import FakeIdentityProvider
from app.modules.identity.service import IdentityService
from app.platform import health
from app.platform.clock import Clock, SystemClock
from app.platform.config import Settings, get_settings
from app.platform.db import create_engine
from app.platform.errors import install_error_handlers
from app.platform.logging import configure_logging
from app.platform.middleware import OriginCheckMiddleware, RequestContextMiddleware


def _version() -> str:
    try:
        return version("buildone-backend")
    except PackageNotFoundError:
        return "0.1.0"


def build_identity_provider(settings: Settings, clock: Clock) -> IdentityProvider:
    if settings.identity_provider == "workos":
        # Imported here so the SDK loads only when configured (and only inside the adapter package).
        from app.modules.identity.providers.workos import WorkOSIdentityProvider

        return WorkOSIdentityProvider(
            api_key=settings.workos_api_key.get_secret_value(),
            client_id=settings.workos_client_id,
        )
    return FakeIdentityProvider(
        api_base_url=settings.api_base_url,
        key=settings.secret_key.get_secret_value().encode(),
        clock=clock,
    )


def create_app(
    settings: Settings | None = None,
    *,
    clock: Clock | None = None,
    identity_provider: IdentityProvider | None = None,
) -> FastAPI:
    """Build the API. Tests pass a FrozenClock and, when needed, their own identity provider."""
    settings = settings or get_settings()
    clock = clock or SystemClock()
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
    app.state.clock = clock
    provider = identity_provider or build_identity_provider(settings, clock)
    app.state.identity = IdentityService(
        engine=app.state.engine, settings=settings, clock=clock, provider=provider
    )
    fake_idp = isinstance(provider, FakeIdentityProvider) and settings.environment != "production"

    install_error_handlers(app, root_domain=settings.root_domain)
    # The SPA (app.<domain>) calls the API (api.<domain>) with the session cookie, so only that one origin
    # may make credentialed cross-origin requests. Added before RequestContextMiddleware, so the request
    # ID middleware is outermost and every response, including preflights, carries X-Request-ID.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.app_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )
    # Starlette runs the last-added middleware first: request ID -> Origin check -> CORS -> routes. Preflights
    # (OPTIONS) are not checked, so CORS still answers them.
    app.add_middleware(
        OriginCheckMiddleware,
        allowed_origin=settings.app_origin,
        root_domain=settings.root_domain,
        exempt_paths=frozenset({FAKE_AUTHORIZE_PATH}) if fake_idp else frozenset(),
    )
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health.router)
    app.include_router(auth_router)
    app.include_router(me_router)
    if fake_idp:
        app.include_router(fake_idp_router)
    return app


def __getattr__(name: str) -> FastAPI:
    # `uvicorn app.main:app` resolves `app` lazily, so importing this module (e.g. for OpenAPI export)
    # doesn't require DATABASE_URL to be set.
    if name == "app":
        return create_app()
    raise AttributeError(name)
