"""Shared router dependencies and app-wide exception handling — the governance seam.

This module holds the single place every data endpoint attaches to for auth, and
the content-negotiated handler that turns a :class:`ProviderAuthError` into either
a browser redirect or a JSON ``503``.

Three pieces live here:

* :func:`require_api_key` -- the **caller-auth** dependency. When
  ``API_KEYS`` is configured it rejects requests lacking a valid ``X-API-Key``;
  when it is empty it logs a warning that the surface is unguarded and allows
  the request (a dev convenience). This is the documented attachment point for
  future centralized caller-auth.
* :func:`require_provider_auth` -- ensures a usable provider token via
  :func:`~app.example.auth.ensure_valid_token`, then hands back an
  :class:`~app.example.service.ExampleService`. The service is imported lazily
  so this module has no import-time coupling to the service layer.
* :func:`register_exception_handlers` -- registers the app-wide
  :class:`ProviderAuthError` handler. Browsers (``Accept: text/html``) are
  redirected to the login path; API clients receive ``503`` with a JSON body
  carrying the absolute ``login_url``. It is ``503`` (not ``401``) because a
  missing provider token is a server-side gap, not a caller mistake — caller
  auth is handled separately by :func:`require_api_key`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import get_settings
from app.example.auth import ProviderAuthError, ensure_valid_token, login_url

if TYPE_CHECKING:
    from app.example.service import ExampleService

logger = logging.getLogger(__name__)

__all__ = [
    "ProviderAuthError",
    "provider_auth_exception_handler",
    "register_exception_handlers",
    "require_api_key",
    "require_provider_auth",
]


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Gate our own surface on a configured ``X-API-Key`` (caller auth).

    When ``API_KEYS`` is set, a missing or unrecognised key raises ``401``. When
    it is empty the surface is unguarded — allowed as a dev convenience, with a
    warning logged. This is the seam a future central KGA API replaces with
    shared caller-auth; keep it here, never inline in routers.
    """
    allowed = get_settings().api_key_set
    if not allowed:
        logger.warning(
            "No API_KEYS configured: caller-auth is DISABLED and the surface is "
            "unguarded. Set API_KEYS in .env before exposing this service."
        )
        return
    if x_api_key is None or x_api_key not in allowed:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")


def require_provider_auth() -> ExampleService:
    """Ensure a usable provider token, then return an authenticated service.

    Raises :class:`ProviderAuthError` (handled app-wide) when the service must
    (re)authorize with the provider. The service is imported lazily to avoid an
    import-time coupling between this seam and the service layer.
    """
    ensure_valid_token()

    from app.example.service import get_example_service

    return get_example_service()


def _absolute_login_url(request: Request) -> str:
    """Build the absolute provider login URL from the request base and ``login_url``."""
    return str(request.base_url).rstrip("/") + login_url()


async def provider_auth_exception_handler(request: Request, exc: ProviderAuthError) -> Response:
    """Redirect browsers to login; return 503 + login_url JSON to API clients."""
    target = _absolute_login_url(request)
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return RedirectResponse(url=target, status_code=307)
    return JSONResponse(
        status_code=503,
        content={"detail": "Provider authorization required", "login_url": target},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the app-wide handler for :class:`ProviderAuthError`."""
    app.add_exception_handler(ProviderAuthError, provider_auth_exception_handler)
