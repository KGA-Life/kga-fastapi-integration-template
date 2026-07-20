"""Application factory for the KGA integration API template.

This module assembles the FastAPI application: it configures logging from
:attr:`Settings.log_level`, mounts the example domain router (already carrying
its ``API_PREFIX``), registers the app-wide :class:`ProviderAuthError` handler,
installs the audit middleware, and exposes an unauthenticated ``/health``
liveness route outside the provider prefix.

The factory performs **no** provider network I/O at import or startup: the app
boots with no credentials and no stored token. Any provider call happens later,
per request, behind the auth seam. ``uvicorn app.main:app`` therefore starts
cleanly offline, and ``/docs`` renders without real credentials.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app.config import Settings, get_settings
from app.routers.deps import register_exception_handlers
from app.routers.example import router as example_router

__all__ = ["app", "create_app"]

logger = logging.getLogger(__name__)

APP_TITLE = "KGA Integration API (template)"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = (
    "Template FastAPI service for a KGA Life third-party integration API "
    "(provider-agnostic starting point). A caller asks *our* service; our "
    "service talks to the provider on their behalf behind a single, "
    "centrally-managed connection.\n\n"
    "This template ships the KGA house style: `X-API-Key` caller auth on the "
    "data surface, an audit middleware that logs request metadata (never "
    "secrets), a `/health` liveness route, and a clean provider-auth seam. "
    "Rename the `example` provider throughout to build a concrete service."
)

# OpenAPI tag metadata. Order here sets the section order in the docs UI, and
# each name must match the ``tags=[...]`` a router declares.
OPENAPI_TAGS: list[dict[str, str]] = [
    {
        "name": "Example",
        "description": (
            "Read and write endpoints over the example provider. Replace with "
            "the concrete provider's domains."
        ),
    },
    {
        "name": "Meta",
        "description": "Service metadata and liveness checks (not under the provider prefix).",
    },
]


def _configure_logging(settings: Settings) -> None:
    """Configure the stdlib root logger from ``settings.log_level``.

    An unrecognised level name falls back to ``INFO`` with a warning. No secret
    values are ever logged here or elsewhere in the factory.
    """
    level = logging.getLevelName(settings.log_level.upper())
    if not isinstance(level, int):
        logging.basicConfig(level=logging.INFO)
        logger.warning("Unknown log level %r; defaulting to INFO.", settings.log_level)
    else:
        logging.basicConfig(level=level)
    logger.info("Logging configured at level %s.", settings.log_level.upper())


def create_app() -> FastAPI:
    """Build and return the fully wired FastAPI application.

    Loads settings, configures logging, constructs the app with OpenAPI
    metadata, mounts the example router plus the ``/health`` liveness route,
    installs the audit middleware, and registers the app-wide provider-auth
    exception handler. Performs no provider network I/O.
    """
    settings = get_settings()
    _configure_logging(settings)

    app = FastAPI(
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        version=APP_VERSION,
        openapi_tags=OPENAPI_TAGS,
    )

    app.include_router(example_router)

    # Content-negotiated ProviderAuthError -> redirect (browser) / 503 (API).
    register_exception_handlers(app)

    @app.middleware("http")
    async def audit_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Log request metadata for governance — never secrets or key values.

        Records method, path, whether an ``X-API-Key`` was presented (a boolean
        marker, NOT the key itself), the response status, and the duration in
        milliseconds. This is the audit signal a future central KGA API consumes.
        """
        # Presence marker only: we log whether a key was sent, never its value.
        api_key_present = request.headers.get("X-API-Key") is not None
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "audit method=%s path=%s api_key_present=%s status=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            api_key_present,
            response.status_code,
            duration_ms,
        )
        return response

    @app.get("/health", tags=["Meta"], summary="Liveness check")
    def health() -> dict[str, str]:
        """Return a minimal liveness payload. Unauthenticated; never includes secrets."""
        return {"status": "ok", "app_env": settings.app_env}

    logger.info("%s v%s initialised (%d routes).", APP_TITLE, APP_VERSION, len(app.routes))
    return app


app = create_app()
