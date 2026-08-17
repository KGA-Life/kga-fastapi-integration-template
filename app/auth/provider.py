"""The vendor-neutral auth seam: the :class:`AuthProvider` ABC and its selector.

This is the one module the rest of the app depends on for identity. It defines
the abstract contract (``verify(token) -> Principal``), the vendor-neutral
exceptions providers and dependencies raise, and :func:`get_provider`, the single
swap point that maps ``AUTH_PROVIDER`` config to a concrete implementation.

It imports **no** JWT or Auth0 library — the concrete :class:`Auth0Provider` is
imported lazily inside :func:`get_provider` so this module stays free of vendor
types. Swapping identity providers is a new implementation file plus a branch
here; routes and the scope registry never change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from app.auth.models import Principal

__all__ = [
    "AuthProvider",
    "InsufficientScopeError",
    "InvalidTokenError",
    "get_provider",
]


class InvalidTokenError(Exception):
    """Raised when a bearer token is missing, malformed, or fails validation.

    Vendor-neutral by design (defined here, not in the Auth0 module) so the
    FastAPI layer maps it to ``401`` without depending on any JWT library's
    exception types.
    """


class InsufficientScopeError(Exception):
    """Raised when a valid principal lacks a required scope (maps to ``403``).

    Carries the :attr:`required` scope that was missing, so callers can report
    exactly what grant is needed.
    """

    def __init__(self, required: str, message: str | None = None) -> None:
        self.required = required
        super().__init__(message or f"Insufficient scope: {required!r} is required.")


class AuthProvider(ABC):
    """The identity contract the rest of the app depends on.

    A concrete provider validates a raw bearer token and returns a
    :class:`~app.auth.models.Principal`. Implementations must not perform network
    I/O at construction (keep the app offline-bootable); any remote key fetch is
    lazy and, ideally, injectable for offline tests.
    """

    @abstractmethod
    def verify(self, token: str) -> Principal:
        """Validate ``token`` and return the authenticated principal.

        Must raise :class:`InvalidTokenError` (never a vendor exception) on any
        validation failure.
        """
        raise NotImplementedError


@lru_cache
def get_provider() -> AuthProvider:
    """Return the configured :class:`AuthProvider`, cached for the process.

    Reads ``AUTH_PROVIDER`` from settings and returns the matching implementation.
    The concrete provider is imported lazily here so this module imports no
    vendor library — this branch is the ONE swap point when the IdP changes.
    """
    provider = get_settings().auth_provider
    if provider == "auth0":
        from app.auth.auth0 import Auth0Provider

        return Auth0Provider()
    raise RuntimeError(
        f"Unknown auth provider {provider!r}. Set AUTH_PROVIDER to a supported "
        "value (currently only 'auth0')."
    )
