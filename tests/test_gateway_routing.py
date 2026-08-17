"""Tier-2 tests: the finance gateway routes + ``require_scopes`` enforcement.

These override the ``current_principal`` seam (via
``override_current_principal``) so ``require_scopes`` runs its check against a
controlled grant set WITHOUT a real JWT, and configure ``API_KEYS`` (the
``api_key`` fixture) so ``require_api_key`` is active. Every finance provider
(xero / netcash / investec) is covered on BOTH its read and write route, across
the five cases: exact scope, non-satisfying scope, domain-wide write superset,
missing API key, and missing bearer.

A final consistency test extracts the ACTUAL required scope string from every
mounted ``/finance/...`` route's dependency tree and asserts it is registered in
``KNOWN_SCOPES``.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.scopes import KNOWN_SCOPES
from app.main import app
from tests.conftest import make_principal, override_current_principal

# The six provider-leaf scopes the finance routes must map onto.
SIX_LEAVES = {
    "finance:xero:read",
    "finance:xero:write",
    "finance:netcash:read",
    "finance:netcash:write",
    "finance:investec:read",
    "finance:investec:write",
}

# One row per mounted finance route. ``wrong`` is a grant that must NOT satisfy
# ``required`` (cross-provider for reads, read-for-write for writes); ``superset``
# is the domain-wide write grant that SHOULD satisfy every finance route.
ROUTES: list[dict[str, Any]] = [
    {
        "id": "xero-read",
        "method": "GET",
        "path": "/finance/xero/invoices",
        "required": "finance:xero:read",
        "wrong": "finance:netcash:read",
        "body": None,
        "ok": 200,
        "shape_key": "InvoiceID",
        "is_list": True,
    },
    {
        "id": "xero-write",
        "method": "POST",
        "path": "/finance/xero/invoices",
        "required": "finance:xero:write",
        "wrong": "finance:xero:read",
        "body": {"Type": "ACCREC", "ContactID": "00000000-0000-0000-0000-000000000000"},
        "ok": 201,
        "shape_key": "InvoiceID",
        "is_list": False,
    },
    {
        "id": "netcash-read",
        "method": "GET",
        "path": "/finance/netcash/transactions",
        "required": "finance:netcash:read",
        "wrong": "finance:xero:read",
        "body": None,
        "ok": 200,
        "shape_key": "TransactionId",
        "is_list": True,
    },
    {
        "id": "netcash-write",
        "method": "POST",
        "path": "/finance/netcash/payments",
        "required": "finance:netcash:write",
        "wrong": "finance:netcash:read",
        "body": {"AccountReference": "ACC-001", "Amount": 500.0},
        "ok": 201,
        "shape_key": "TransactionId",
        "is_list": False,
    },
    {
        "id": "investec-read",
        "method": "GET",
        "path": "/finance/investec/accounts",
        "required": "finance:investec:read",
        "wrong": "finance:netcash:read",
        "body": None,
        "ok": 200,
        "shape_key": "accountId",
        "is_list": True,
    },
    {
        "id": "investec-write",
        "method": "POST",
        "path": "/finance/investec/payments",
        "required": "finance:investec:write",
        "wrong": "finance:investec:read",
        "body": {"accountId": "10000000001", "beneficiaryId": "BEN-001", "amount": 1250.0},
        "ok": 201,
        "shape_key": "amount",
        "is_list": False,
    },
]

_IDS = [r["id"] for r in ROUTES]
API_HEADER = {"X-API-Key": "test-key-123"}


def _send(client: TestClient, route: dict[str, Any], headers: dict[str, str]):
    if route["method"] == "GET":
        return client.get(route["path"], headers=headers)
    return client.post(route["path"], headers=headers, json=route["body"])


def _first(body: Any, route: dict[str, Any]) -> dict:
    return body[0] if route["is_list"] else body


@pytest.mark.parametrize("route", ROUTES, ids=_IDS)
def test_exact_scope_allows_and_returns_stub_shape(
    client: TestClient, api_key: str, route: dict[str, Any]
) -> None:
    override_current_principal(make_principal(route["required"]))
    resp = _send(client, route, API_HEADER)
    assert resp.status_code == route["ok"]
    assert route["shape_key"] in _first(resp.json(), route)


@pytest.mark.parametrize("route", ROUTES, ids=_IDS)
def test_nonsatisfying_scope_is_forbidden(
    client: TestClient, api_key: str, route: dict[str, Any]
) -> None:
    override_current_principal(make_principal(route["wrong"]))
    resp = _send(client, route, API_HEADER)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Insufficient scope"
    assert "insufficient_scope" in resp.headers.get("www-authenticate", "")


@pytest.mark.parametrize("route", ROUTES, ids=_IDS)
def test_domain_wide_write_superset_allows(
    client: TestClient, api_key: str, route: dict[str, Any]
) -> None:
    # finance:write implies every provider write, and (write => read) every read.
    override_current_principal(make_principal("finance:write"))
    resp = _send(client, route, API_HEADER)
    assert resp.status_code == route["ok"]


@pytest.mark.parametrize("route", ROUTES, ids=_IDS)
def test_missing_api_key_is_rejected(
    client: TestClient, api_key: str, route: dict[str, Any]
) -> None:
    # Principal is fine; the missing X-API-Key must 401 at the caller-auth layer.
    override_current_principal(make_principal(route["required"]))
    resp = _send(client, route, headers={})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing or invalid API key"


@pytest.mark.parametrize("route", ROUTES, ids=_IDS)
def test_wrong_api_key_is_rejected(client: TestClient, api_key: str, route: dict[str, Any]) -> None:
    override_current_principal(make_principal(route["required"]))
    resp = _send(client, route, headers={"X-API-Key": "not-the-key"})
    assert resp.status_code == 401


@pytest.mark.parametrize("route", ROUTES, ids=_IDS)
def test_missing_bearer_is_rejected(
    client: TestClient, api_key: str, route: dict[str, Any]
) -> None:
    # No principal override => the REAL current_principal runs. With a valid API
    # key but no Authorization header, the JWT layer 401s (never reaching a stub).
    resp = _send(client, route, API_HEADER)
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate", "").startswith("Bearer")


def test_invalid_bearer_token_returns_401_end_to_end(
    client: TestClient,
    api_key: str,
    auth0_provider: Any,
    mint_token: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Drive the REAL current_principal -> Auth0Provider chain end-to-end, but with
    # the offline injected-resolver provider (no JWKS network). current_principal
    # calls get_provider() by name in its own module, so monkeypatch that name
    # rather than using dependency_overrides. This proves the invalid-token path
    # returns 401 through a mounted finance route (the provider-level tests only
    # prove verify() raises; the existing route tests only cover missing-bearer).
    monkeypatch.setattr("app.auth.dependencies.get_provider", lambda: auth0_provider)

    # Valid API key, but an EXPIRED bearer -> 401 with the invalid_token challenge.
    expired = mint_token(expires_in=-30, permissions=["finance:xero:read"])
    resp = client.get(
        "/finance/xero/invoices",
        headers={**API_HEADER, "Authorization": f"Bearer {expired}"},
    )
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate", "") == 'Bearer error="invalid_token"'

    # Valid API key, but NO Authorization header -> 401 (short-circuits at the
    # bearer check, before the provider is consulted).
    resp_missing = client.get("/finance/xero/invoices", headers=API_HEADER)
    assert resp_missing.status_code == 401
    assert resp_missing.headers.get("www-authenticate", "").startswith("Bearer")


# --- Registry <-> routes consistency ----------------------------------------


def _iter_effective_contexts(a: Any):
    """Yield every effective route context from the app's included routers."""
    for route in a.routes:
        gen = getattr(route, "effective_route_contexts", None)
        if callable(gen):
            yield from gen()


def _scopes_in_dependant(dep: Any) -> set[str]:
    """Recursively pull scope-shaped strings out of a dependency closure tree."""
    found: set[str] = set()
    call = getattr(dep, "call", None)
    closure = getattr(call, "__closure__", None) if call is not None else None
    if closure:
        for cell in closure:
            try:
                value = cell.cell_contents
            except ValueError:
                continue
            items = value if isinstance(value, (tuple, list)) else [value]
            for item in items:
                if isinstance(item, str) and ":" in item:
                    found.add(item)
    for sub in getattr(dep, "dependencies", []):
        found |= _scopes_in_dependant(sub)
    return found


def _finance_route_scopes() -> dict[str, set[str]]:
    scopes_by_route: dict[str, set[str]] = {}
    for ctx in _iter_effective_contexts(app):
        if ctx.path.startswith("/finance"):
            key = f"{sorted(ctx.methods)} {ctx.path}"
            scopes_by_route[key] = _scopes_in_dependant(ctx.dependant)
    return scopes_by_route


def test_every_finance_route_declares_a_registered_scope() -> None:
    scopes_by_route = _finance_route_scopes()
    # All six provider routes are discovered, each declaring exactly one scope.
    assert len(scopes_by_route) == 6
    for key, declared in scopes_by_route.items():
        assert declared, f"route {key} declares no scope"
        assert declared <= KNOWN_SCOPES, f"route {key} scope not in KNOWN_SCOPES: {declared}"
    union = set().union(*scopes_by_route.values())
    assert union == SIX_LEAVES


def test_finance_paths_are_documented_in_openapi(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for route in ROUTES:
        assert route["path"] in paths
