"""Unit tests for the auth dependencies: ``current_principal`` and ``require_scopes``.

These drive the dependency callables directly (no HTTP), covering the bearer-token
extraction branches (missing header / wrong scheme / empty token / valid token),
the provider-validation-failure -> 401 mapping, and the ``require_scopes`` factory:
wiring-time validation against ``KNOWN_SCOPES``, the multi-scope AND semantics, and
the 403 challenge naming the missing scope.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.auth import dependencies
from app.auth.dependencies import current_principal, require_scopes
from app.auth.models import Principal
from app.auth.provider import AuthProvider, InsufficientScopeError, InvalidTokenError
from tests.conftest import make_principal


class _FakeProvider(AuthProvider):
    """A provider that returns a canned principal or raises, for seam tests."""

    def __init__(self, principal: Principal | None = None, raise_error: bool = False) -> None:
        self._principal = principal
        self._raise = raise_error

    def verify(self, token: str) -> Principal:
        if self._raise:
            raise InvalidTokenError("nope")
        assert self._principal is not None
        return self._principal


# --- current_principal -------------------------------------------------------


def test_missing_authorization_header_401() -> None:
    with pytest.raises(HTTPException) as exc:
        current_principal(authorization=None)
    assert exc.value.status_code == 401
    assert exc.value.headers["WWW-Authenticate"].startswith("Bearer")


def test_non_bearer_scheme_401() -> None:
    with pytest.raises(HTTPException) as exc:
        current_principal(authorization="Basic dXNlcjpwYXNz")
    assert exc.value.status_code == 401


def test_empty_bearer_token_401() -> None:
    with pytest.raises(HTTPException) as exc:
        current_principal(authorization="Bearer    ")
    assert exc.value.status_code == 401


def test_valid_bearer_returns_principal(monkeypatch: pytest.MonkeyPatch) -> None:
    principal = make_principal("finance:xero:read")
    monkeypatch.setattr(dependencies, "get_provider", lambda: _FakeProvider(principal=principal))
    result = current_principal(authorization="Bearer good-token")
    assert result is principal


def test_provider_rejection_maps_to_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dependencies, "get_provider", lambda: _FakeProvider(raise_error=True))
    with pytest.raises(HTTPException) as exc:
        current_principal(authorization="Bearer bad-token")
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid or expired token"


# --- require_scopes factory --------------------------------------------------


def test_require_scopes_rejects_unknown_scope_at_wiring_time() -> None:
    with pytest.raises(ValueError, match="Unknown scope"):
        require_scopes("finance:paypal:read")


def test_require_scopes_reports_every_unknown_scope() -> None:
    with pytest.raises(ValueError) as exc:
        require_scopes("finance:xero:read", "totally:made:up")
    assert "totally:made:up" in str(exc.value)


def test_dependency_allows_principal_with_the_scope() -> None:
    dep = require_scopes("finance:xero:read")
    principal = make_principal("finance:xero:read")
    assert dep(principal=principal) is principal


def test_dependency_allows_via_superset_grant() -> None:
    dep = require_scopes("finance:xero:read")
    # domain-wide write satisfies the provider read requirement.
    assert dep(principal=make_principal("finance:write")) is not None


def test_dependency_forbids_missing_scope_naming_the_gap() -> None:
    dep = require_scopes("finance:xero:write")
    # The dependency raises the vendor-neutral InsufficientScopeError carrying the
    # missing scope; the app-wide handler renders it as 403 + the insufficient_scope
    # challenge (asserted end-to-end in test_gateway_routing).
    with pytest.raises(InsufficientScopeError) as exc:
        dep(principal=make_principal("finance:xero:read"))
    assert exc.value.required == "finance:xero:write"


def test_dependency_requires_all_scopes_when_multiple() -> None:
    dep = require_scopes("finance:xero:read", "finance:netcash:read")
    # Holding only one of the two required scopes is rejected, and the first
    # missing scope (netcash) is named on the raised exception.
    with pytest.raises(InsufficientScopeError) as exc:
        dep(principal=make_principal("finance:xero:read"))
    assert exc.value.required == "finance:netcash:read"
    # A domain-wide grant covers both requirements.
    both = make_principal("finance:read")
    assert dep(principal=both) is both
