"""Provider-agnostic authorization package for the KGA gateway.

Public surface (import these; the concrete Auth0 impl lives in
:mod:`app.auth.auth0` and is reached only through :func:`get_provider`):

* :class:`~app.auth.provider.AuthProvider` -- the swappable identity seam, with
  :func:`~app.auth.provider.get_provider` as the single config-driven swap point.
* :class:`~app.auth.models.Principal` / :class:`~app.auth.models.TokenClaims` --
  the vendor-neutral identity models.
* :func:`~app.auth.dependencies.current_principal` /
  :func:`~app.auth.dependencies.require_scopes` -- the FastAPI auth dependencies.
* :class:`~app.auth.provider.InvalidTokenError` (401) /
  :class:`~app.auth.provider.InsufficientScopeError` (403) -- the auth exceptions.

The scope registry is :mod:`app.auth.scopes`. This package imports no JWT/Auth0
library at import time, keeping ``import app.auth`` vendor-neutral.
"""

from app.auth.dependencies import current_principal, require_scopes
from app.auth.models import Principal, TokenClaims
from app.auth.provider import (
    AuthProvider,
    InsufficientScopeError,
    InvalidTokenError,
    get_provider,
)

__all__ = [
    "AuthProvider",
    "InsufficientScopeError",
    "InvalidTokenError",
    "Principal",
    "TokenClaims",
    "current_principal",
    "get_provider",
    "require_scopes",
]
