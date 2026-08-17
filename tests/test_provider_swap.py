"""The provider-agnostic seam: ``get_provider`` selection and IdP swappability.

Proves the design promise from context §5/§10: routes and the scope registry
depend ONLY on the :class:`AuthProvider` ABC, so a different identity provider is
a new implementation plus a config branch — no route or registry change. A
``FakeProvider`` is injected via the ``get_provider`` seam and drives a REAL
finance route to 200/401/403 with zero edits to the route or registry.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import dependencies
from app.auth.auth0 import Auth0Provider
from app.auth.models import Principal
from app.auth.provider import (
    AuthProvider,
    InsufficientScopeError,
    InvalidTokenError,
    get_provider,
)
from tests.conftest import API_KEY, make_principal


class FakeProvider(AuthProvider):
    """A non-Auth0 provider that returns a canned principal (or rejects the token).

    Depends on nothing vendor-specific — it exists purely to prove the seam.
    """

    def __init__(self, principal: Principal | None = None, *, reject: bool = False) -> None:
        self._principal = principal
        self._reject = reject

    def verify(self, token: str) -> Principal:
        if self._reject:
            raise InvalidTokenError("fake rejects everything")
        assert self._principal is not None
        return self._principal


def test_get_provider_returns_auth0_for_auth0_config() -> None:
    get_provider.cache_clear()
    provider = get_provider()
    assert isinstance(provider, Auth0Provider)


def test_get_provider_is_cached() -> None:
    get_provider.cache_clear()
    assert get_provider() is get_provider()


def test_get_provider_unknown_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.auth import provider as provider_mod

    class _Settings:
        auth_provider = "mystery-idp"

    monkeypatch.setattr(provider_mod, "get_settings", lambda: _Settings())
    get_provider.cache_clear()
    with pytest.raises(RuntimeError, match="Unknown auth provider"):
        get_provider()
    get_provider.cache_clear()


def test_swapped_provider_drives_a_real_route_to_200(
    client: TestClient, api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Inject a completely different AuthProvider via the seam only. The mounted
    # /finance/xero route resolves its principal through the fake and returns 200
    # — no route or scope-registry change was needed to swap the IdP.
    fake = FakeProvider(make_principal("finance:xero:read"))
    monkeypatch.setattr(dependencies, "get_provider", lambda: fake)
    resp = client.get(
        "/finance/xero/invoices",
        headers={"X-API-Key": API_KEY, "Authorization": "Bearer opaque-to-us"},
    )
    assert resp.status_code == 200


def test_swapped_provider_rejection_becomes_401(
    client: TestClient, api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dependencies, "get_provider", lambda: FakeProvider(reject=True))
    resp = client.get(
        "/finance/xero/invoices",
        headers={"X-API-Key": API_KEY, "Authorization": "Bearer whatever"},
    )
    assert resp.status_code == 401


def test_swapped_provider_still_subject_to_scope_gate(
    client: TestClient, api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The fake authenticates the caller but grants the wrong scope: require_scopes
    # still enforces, proving authz is independent of the identity provider.
    fake = FakeProvider(make_principal("finance:netcash:read"))
    monkeypatch.setattr(dependencies, "get_provider", lambda: fake)
    resp = client.get(
        "/finance/xero/invoices",
        headers={"X-API-Key": API_KEY, "Authorization": "Bearer whatever"},
    )
    assert resp.status_code == 403


def test_abstract_verify_raises_not_implemented() -> None:
    class Passthrough(AuthProvider):
        def verify(self, token: str) -> Principal:
            return super().verify(token)

    with pytest.raises(NotImplementedError):
        Passthrough().verify("x")


def test_insufficient_scope_error_carries_required_and_default_message() -> None:
    err = InsufficientScopeError("finance:xero:read")
    assert err.required == "finance:xero:read"
    assert "finance:xero:read" in str(err)


def test_insufficient_scope_error_accepts_custom_message() -> None:
    err = InsufficientScopeError("finance:read", "you shall not pass")
    assert err.required == "finance:read"
    assert str(err) == "you shall not pass"
