"""The machine-checked offline invariant (context §10.2).

Two things are proven here:

* the session-wide socket guard actually blocks a real outbound connection while
  leaving the in-process ``TestClient`` working; and
* ``app.main`` imports and ``app.openapi()`` render with ZERO network, and
  ``/health`` serves 200 — the offline-boot guarantee.

A third test drives the guard through the ONLY real network path in the auth
stack (an ``Auth0Provider`` with no injected key resolver, which would otherwise
fetch JWKS): under the guard, ``verify`` raises the guard's ``RuntimeError``
rather than reaching Auth0.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.auth0 import Auth0Provider
from app.config import Settings
from tests.conftest import AUTH0_AUDIENCE, AUTH0_DOMAIN


def test_outbound_connection_is_blocked() -> None:
    # A non-loopback connect must be refused loudly, without touching the network
    # (the guard raises before any DNS/socket work happens).
    with pytest.raises(RuntimeError, match="outbound network blocked"):
        socket.create_connection(("example.com", 443), timeout=1)


def test_outbound_socket_connect_is_blocked() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError, match="outbound network blocked"):
            sock.connect(("93.184.216.34", 443))  # example.com literal IP
    finally:
        sock.close()


def test_loopback_is_still_allowed() -> None:
    # The guard must NOT block loopback, or the ASGI TestClient / asyncio
    # self-pipe would break. Connecting to a closed loopback port raises a
    # connection error (OSError) — crucially NOT our RuntimeError.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)
    try:
        with pytest.raises(OSError) as exc:
            sock.connect(("127.0.0.1", 1))
        assert not isinstance(exc.value, RuntimeError) or "outbound network" not in str(exc.value)
    finally:
        sock.close()


def test_offline_boot_imports_and_serves() -> None:
    # Importing the app factory and rendering the OpenAPI schema must perform no
    # network at all (this whole test runs under the active guard).
    import app.main as main_module

    schema = main_module.app.openapi()
    assert schema["info"]["title"]
    assert "/health" in schema["paths"]

    client = TestClient(main_module.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_jwks_fetch_path_is_intercepted_by_the_guard(mint_token: Any) -> None:
    # No resolver injected => the provider would resolve the signing key from the
    # tenant JWKS over the network. The guard intercepts that single network path.
    settings = Settings(
        auth0_domain=AUTH0_DOMAIN,
        auth0_api_audience=AUTH0_AUDIENCE,
        auth0_algorithms="RS256",
    )
    provider = Auth0Provider(settings=settings)  # no signing_key_resolver
    token = mint_token(permissions=["finance:xero:read"])
    with pytest.raises(RuntimeError, match="outbound network blocked"):
        provider.verify(token)
