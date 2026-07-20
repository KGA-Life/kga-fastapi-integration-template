"""Generic provider auth seam for the KGA integration API template.

This module demonstrates the provider-authentication seam without hitting any
live network: it loads a persisted token via the injected
:class:`~app.example.token_store.TokenStore` and signals
:class:`ProviderAuthError` when no usable token is present.

Concrete services replace the stub :func:`refresh` with the provider's real
token-refresh call (OAuth2 code exchange, API-key handshake, HMAC signing, ...)
and, if the provider issues rotating refresh tokens, persist the rotated token
through the store before returning — the single most important correctness
property of a real auth module.

Credentials are read from :func:`app.config.get_settings` at call time, never at
import time, so the application boots and ``/docs`` renders even when no ``.env``
credentials are present.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import API_PREFIX, get_settings
from app.example.token_store import FileTokenStore, TokenStore


class ProviderAuthError(Exception):
    """Raised when there is no usable provider token.

    Signals that the provider authorization flow must be run (nothing is stored,
    or a refresh could not proceed). The app-wide handler in
    :mod:`app.routers.deps` translates this into a ``503`` (JSON) or a redirect
    to :func:`login_url` (browser).
    """


@lru_cache
def get_token_store() -> TokenStore:
    """Return the process-wide token store (a :class:`FileTokenStore`)."""
    return FileTokenStore(get_settings().token_store_path)


def refresh() -> dict:
    """Refresh the provider token (stub — no live network in the template).

    A concrete service posts to the provider's token endpoint here, persists the
    (possibly rotated) token via :func:`get_token_store`, and returns it. The
    template raises so an accidental call in a generated service fails loudly
    until wired up.
    """
    get_settings().require_credentials()
    raise ProviderAuthError(
        "Provider token refresh is not implemented in this template; "
        "wire app.example.auth.refresh() to the provider's token endpoint."
    )


def ensure_valid_token() -> None:
    """Ensure a usable provider token is present, refreshing if stale.

    Called before any provider call (by the auth dependency in
    :mod:`app.routers.deps`). Loads the stored token and raises
    :class:`ProviderAuthError` if nothing is stored. A concrete service extends
    this to check expiry and call :func:`refresh` when the token is stale.
    """
    token = get_token_store().load()
    if not token:
        raise ProviderAuthError("No provider token stored; authorization required.")


def authorization_url(state: str) -> str:
    """Build the provider consent/authorize URL (placeholder in the template).

    The ``state`` value is round-tripped by the provider to the callback and must
    be validated there for CSRF protection. A concrete service returns the real
    provider authorize endpoint; here it points back at the local login path.
    """
    return f"{login_url()}?state={state}"


def login_url() -> str:
    """Return the app-relative provider login path (used in error responses)."""
    return f"{API_PREFIX}/auth/login"
