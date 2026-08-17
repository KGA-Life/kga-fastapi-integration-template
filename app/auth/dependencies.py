"""FastAPI authorization dependencies: authenticate the caller, then gate on scope.

Two pieces, both vendor-neutral (they touch only the :class:`AuthProvider` seam
and the scope registry):

* :func:`current_principal` -- extracts the ``Bearer`` token, runs the active
  provider's ``verify``, and returns the :class:`~app.auth.models.Principal`.
  Missing/malformed token or a failed validation → ``401`` with the
  ``WWW-Authenticate: Bearer error="invalid_token"`` challenge.
* :func:`require_scopes` -- a **factory** returning a dependency that requires the
  caller hold every listed scope (hierarchical superset rules apply). Missing a
  scope → ``403`` with an ``insufficient_scope`` challenge naming the gap. Each
  scope is validated against :data:`~app.auth.scopes.KNOWN_SCOPES` when the
  factory is called, so a typo fails loudly at wiring time, not at request time.

Routes depend on these, never on the identity provider directly — swapping the
IdP behind :func:`~app.auth.provider.get_provider` leaves this wiring untouched.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException

from app.auth import scopes
from app.auth.models import Principal
from app.auth.provider import InvalidTokenError, get_provider

__all__ = ["current_principal", "require_scopes"]

# The 401 challenge for a missing/invalid bearer token (RFC 6750).
_INVALID_TOKEN_HEADERS = {"WWW-Authenticate": 'Bearer error="invalid_token"'}


def current_principal(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> Principal:
    """Authenticate the caller from the ``Authorization: Bearer <token>`` header.

    A missing header, a non-``Bearer`` scheme, or an empty token raises ``401``;
    a token that fails provider validation (:class:`InvalidTokenError`) also
    raises ``401``. Returns the validated :class:`Principal` on success.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token",
            headers=_INVALID_TOKEN_HEADERS,
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token",
            headers=_INVALID_TOKEN_HEADERS,
        )
    try:
        return get_provider().verify(token.strip())
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers=_INVALID_TOKEN_HEADERS,
        ) from exc


# Module-level singleton so the inner dependency doesn't call ``Depends`` in an
# argument default (bugbear B008); FastAPI reads it identically to inline.
_PRINCIPAL = Depends(current_principal)


def require_scopes(*required: str) -> Callable[..., Principal]:
    """Build a dependency requiring the caller hold every scope in ``required``.

    Validates each scope against :data:`~app.auth.scopes.KNOWN_SCOPES` at
    factory-call time (a typo'd scope raises :class:`ValueError` at wiring time).
    The returned dependency depends on :func:`current_principal`, checks each
    required scope via :meth:`Principal.has_scope`, and raises ``403`` with an
    ``insufficient_scope`` challenge naming the first missing scope. Returns the
    principal on success.
    """
    unknown = [scope for scope in required if scope not in scopes.KNOWN_SCOPES]
    if unknown:
        raise ValueError(
            f"Unknown scope(s) {unknown}: not in scopes.KNOWN_SCOPES. "
            "Add them to the registry or fix the typo."
        )

    def dependency(principal: Principal = _PRINCIPAL) -> Principal:
        for scope in required:
            if not principal.has_scope(scope):
                raise HTTPException(
                    status_code=403,
                    detail="Insufficient scope",
                    headers={
                        "WWW-Authenticate": (f'Bearer error="insufficient_scope", scope="{scope}"')
                    },
                )
        return principal

    return dependency
