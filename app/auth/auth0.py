"""The concrete Auth0 validator: a validate-only OAuth2 resource server.

:class:`Auth0Provider` implements :class:`~app.auth.provider.AuthProvider` for
Auth0. It **validates** bearer JWTs and nothing else — it never mints, refreshes,
or stores tokens (that is Auth0's job; the gateway is a resource server).

Validation per request: resolve the signing key for the token's ``kid`` from the
tenant JWKS, verify the RS256 signature, then verify ``iss``/``aud``/``exp`` via
``jwt.decode``. Any failure is mapped to the vendor-neutral
:class:`~app.auth.provider.InvalidTokenError` with a safe, secret-free message.

Offline-safe: construction performs no network I/O. The JWKS client is built
lazily on first use, and the signing-key resolver is injectable so tests supply a
known public key without touching the network.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError

from app.auth.models import Principal
from app.auth.provider import AuthProvider, InvalidTokenError
from app.config import Settings, get_settings

# PyJWT validation failures we translate into a single vendor-neutral error.
# ``jwt.InvalidTokenError`` is the base of the signature/audience/issuer/expiry
# families; ``PyJWKClientError`` (JWKS fetch / unknown ``kid``) sits outside that
# hierarchy, so both are caught.
_JWT_ERRORS: tuple[type[Exception], ...] = (
    jwt.ExpiredSignatureError,
    jwt.InvalidAudienceError,
    jwt.InvalidIssuerError,
    jwt.InvalidSignatureError,
    jwt.DecodeError,
    PyJWKClientError,
    jwt.InvalidTokenError,
)


class Auth0Provider(AuthProvider):
    """Validate Auth0-issued RS256 access tokens for this API (resource server).

    Args:
        settings: Settings source (defaults to the cached app settings). Injecting
            a settings object lets tests override tenant domain/audience without a
            populated environment.
        signing_key_resolver: Optional ``token -> key`` callable. When ``None``
            (production), the key is resolved from the tenant JWKS via
            :class:`jwt.PyJWKClient`; tests pass a fake returning a known public
            key so no network call happens.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        signing_key_resolver: Callable[[str], Any] | None = None,
    ) -> None:
        # No I/O here: only capture config and the optional resolver. The JWKS
        # client is built lazily (see ``_jwks_client``) so construction is offline.
        self._settings = settings or get_settings()
        self._signing_key_resolver = signing_key_resolver

    @property
    def _algorithms(self) -> list[str]:
        """Allowed signing algorithms, parsed from the comma-separated setting."""
        raw = self._settings.auth0_algorithms
        return [alg.strip() for alg in raw.split(",") if alg.strip()]

    @cached_property
    def _jwks_client(self) -> PyJWKClient:
        """The tenant JWKS client, built once on first use (never at import)."""
        domain = self._settings.auth0_domain
        return PyJWKClient(f"https://{domain}/.well-known/jwks.json")

    def _resolve_signing_key(self, token: str) -> Any:
        """Return the public signing key for ``token`` (injected fake or JWKS)."""
        if self._signing_key_resolver is not None:
            return self._signing_key_resolver(token)
        return self._jwks_client.get_signing_key_from_jwt(token).key

    def verify(self, token: str) -> Principal:
        """Validate ``token`` and return the authenticated :class:`Principal`.

        Fails fast (``RuntimeError``) if the tenant domain/audience are unset,
        then verifies signature, issuer, audience, and expiry. Every PyJWT failure
        is remapped to :class:`~app.auth.provider.InvalidTokenError` with a
        secret-free message.
        """
        self._settings.require_auth0_config()
        try:
            signing_key = self._resolve_signing_key(token)
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=self._algorithms,
                audience=self._settings.auth0_api_audience,
                issuer=self._settings.auth0_issuer,
                options={"require": ["exp", "iss", "aud"]},
            )
        except _JWT_ERRORS as exc:
            # Deliberately generic: never leak token contents or crypto detail.
            raise InvalidTokenError("Bearer token validation failed.") from exc

        return self._principal_from_claims(claims)

    @staticmethod
    def _principal_from_claims(claims: dict[str, Any]) -> Principal:
        """Build a :class:`Principal` from validated claims (RBAC first, scope fallback)."""
        subject = claims.get("sub")
        if not subject:
            raise InvalidTokenError("Bearer token has no subject ('sub') claim.")

        permissions = claims.get("permissions")
        scope_claim = claims.get("scope")
        if isinstance(permissions, list):
            granted = frozenset(str(p) for p in permissions)
        elif isinstance(scope_claim, str) and scope_claim.strip():
            granted = frozenset(scope_claim.split())
        else:
            granted = frozenset()

        return Principal(subject=subject, scopes=granted, claims=claims)
