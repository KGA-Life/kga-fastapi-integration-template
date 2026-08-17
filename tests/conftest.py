"""Shared pytest fixtures for the fully-offline template test suite.

No fixture here performs a live provider call. Three invariants are enforced for
every test:

* the lru_cached singletons (``get_settings`` / ``get_token_store`` /
  ``get_provider``) are cleared before and after each test, so a test that
  repoints an env var cannot leak that state into another test;
* ``app.dependency_overrides`` is emptied around each test, so a router test that
  overrides ``require_provider_auth`` / ``current_principal`` starts and ends from
  a clean app; and
* **outbound network is blocked for the whole session** (see
  :func:`_block_outbound_network`) so any accidental real socket call fails loudly.
  The in-process ASGI ``TestClient`` keeps working because it never opens a real
  socket, and loopback (``127.0.0.1`` / ``::1``) is allowed so the Windows asyncio
  self-pipe still builds.

The auth-tier fixtures (``rsa_keypair`` / ``auth0_settings`` / ``auth0_provider`` /
``mint_token``) let JWT-validation tests generate a keypair, sign tokens, and
verify them through :class:`~app.auth.auth0.Auth0Provider` entirely offline (the
provider's signing-key resolver is injected with the test public key, so no JWKS
fetch happens).
"""

from __future__ import annotations

import socket
import time
from collections.abc import Callable, Iterator
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.auth.auth0 import Auth0Provider
from app.auth.dependencies import current_principal
from app.auth.models import Principal
from app.auth.provider import get_provider
from app.config import Settings, get_settings
from app.example.auth import get_token_store
from app.main import app
from app.routers.deps import require_provider_auth

# A known caller API key the auth tests configure via the ``api_key`` fixture.
API_KEY = "test-key-123"

# Canned provider item. ``UnknownFutureField`` is unmodelled by ``Item`` and must
# survive to the response via the model's ``extra="allow"``.
ITEM = {
    "id": "item-001",
    "name": "Example Widget",
    "status": "active",
    "UnknownFutureField": "passthrough-value",
}

# --- Auth0 test tenant (never a real tenant; used only offline) --------------
AUTH0_DOMAIN = "kga-test-tenant.eu.auth0.com"
AUTH0_AUDIENCE = "https://api.kga.test/gateway"
AUTH0_ISSUER = f"https://{AUTH0_DOMAIN}/"

# Sentinel so ``mint_token`` can distinguish "sign with the default private key"
# from an explicit ``key=None`` (needed to mint an ``alg=none`` token).
_UNSET: Any = object()


def _clear_caches() -> None:
    """Clear every lru_cached singleton so callers rebuild from env."""
    get_settings.cache_clear()
    get_token_store.cache_clear()
    get_provider.cache_clear()


# --- Offline network guard (session-wide, machine-checked) -------------------

_REAL_CONNECT = socket.socket.connect
_REAL_CREATE_CONNECTION = socket.create_connection


def _is_loopback(address: object) -> bool:
    """True if ``address`` targets loopback (allowed) rather than a remote host."""
    host = address[0] if isinstance(address, (tuple, list)) and address else None
    if not isinstance(host, str):
        return False
    return host in {"localhost", "::1", "127.0.0.1"} or host.startswith("127.")


@pytest.fixture(scope="session", autouse=True)
def _block_outbound_network() -> Iterator[None]:
    """Block every real outbound socket for the session; allow loopback only.

    This is the machine-checked offline invariant: any accidental JWKS fetch or
    provider HTTP call in the suite raises ``RuntimeError`` instead of silently
    reaching the network. Loopback is permitted so the ASGI ``TestClient`` and the
    Windows asyncio self-pipe keep working.
    """

    def guarded_connect(self: socket.socket, address: object, *args: Any, **kwargs: Any) -> Any:
        if _is_loopback(address):
            return _REAL_CONNECT(self, address, *args, **kwargs)
        raise RuntimeError(f"Offline test suite: outbound network blocked (connect {address!r}).")

    def guarded_create_connection(address: object, *args: Any, **kwargs: Any) -> Any:
        if _is_loopback(address):
            return _REAL_CREATE_CONNECTION(address, *args, **kwargs)
        raise RuntimeError(
            f"Offline test suite: outbound network blocked (create_connection {address!r})."
        )

    socket.socket.connect = guarded_connect  # type: ignore[method-assign,assignment]
    socket.create_connection = guarded_create_connection  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = _REAL_CONNECT  # type: ignore[method-assign]
        socket.create_connection = _REAL_CREATE_CONNECTION  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def reset_state() -> Iterator[None]:
    """Reset cached singletons and dependency overrides around every test."""
    _clear_caches()
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    _clear_caches()


@pytest.fixture
def client() -> TestClient:
    """A ``TestClient`` bound to the real app (redirects followed by default)."""
    return TestClient(app)


class FakeExampleService:
    """Minimal stand-in for ``ExampleService`` returning canned data.

    Covers the read (``list_items`` / ``get_item``) and write (``create_item``)
    surface without any network I/O.
    """

    def __init__(
        self,
        items: list[dict] | None = None,
        single: dict | None = None,
    ) -> None:
        self._items = items if items is not None else []
        self._single = single if single is not None else {}

    def list_items(self, page: int = 1) -> list[dict]:
        return self._items

    def get_item(self, item_id: str) -> dict:
        return self._single

    def create_item(self, payload: dict) -> dict:
        # Echo the caller's payload over a canned created record so the write
        # test can assert both the server-assigned id and the submitted fields.
        created = {"id": "item-new-999", "status": "active"}
        created.update(payload)
        return created


@pytest.fixture
def fake_service() -> FakeExampleService:
    """A fake authenticated service carrying canned item data."""
    return FakeExampleService(items=[ITEM], single=ITEM)


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Configure ``API_KEYS`` with a known key and return it.

    Sets the env var and clears the settings cache so ``require_api_key`` sees
    the configured key on the next request.
    """
    monkeypatch.setenv("API_KEYS", API_KEY)
    get_settings.cache_clear()
    return API_KEY


def override_provider_auth(service: FakeExampleService) -> None:
    """Override the provider-auth dependency with a fake service."""
    app.dependency_overrides[require_provider_auth] = lambda: service


# --- Principal / scope helpers ----------------------------------------------


def make_principal(*scopes: str, subject: str = "auth0|test-user") -> Principal:
    """Build a :class:`Principal` carrying an explicit grant set (for route tests)."""
    return Principal(subject=subject, scopes=frozenset(scopes), claims={"sub": subject})


def override_current_principal(principal: Principal) -> None:
    """Override the ``current_principal`` seam so a route resolves ``principal``.

    This exercises ``require_scopes`` enforcement without a real JWT: the scope
    dependency still runs its check against the injected principal's grants.
    """
    app.dependency_overrides[current_principal] = lambda: principal


# --- Auth0 JWT fixtures (fully offline) --------------------------------------


@pytest.fixture(scope="session")
def rsa_keypair() -> tuple[Any, Any]:
    """A session-wide RSA keypair: ``(private_key, public_key)`` for signing tokens."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture
def auth0_settings() -> Settings:
    """Settings pointing at the offline test tenant (domain + audience set)."""
    return Settings(
        auth_provider="auth0",
        auth0_domain=AUTH0_DOMAIN,
        auth0_api_audience=AUTH0_AUDIENCE,
        auth0_algorithms="RS256",
    )


@pytest.fixture
def auth0_provider(rsa_keypair: tuple[Any, Any], auth0_settings: Settings) -> Auth0Provider:
    """An :class:`Auth0Provider` whose signing key is injected (no JWKS fetch)."""
    _private_key, public_key = rsa_keypair
    return Auth0Provider(
        settings=auth0_settings,
        signing_key_resolver=lambda _token: public_key,
    )


@pytest.fixture
def mint_token(rsa_keypair: tuple[Any, Any]) -> Callable[..., str]:
    """Return a factory that mints signed JWTs for the offline test tenant.

    Defaults produce a valid RS256 token for the test audience/issuer with a
    future ``exp``. Override any field to craft the negative cases (wrong ``aud``
    /``iss``, past ``exp``, ``alg=none``/``HS256`` forgery, missing ``sub``, ...).
    """
    private_key, _public_key = rsa_keypair

    def _mint(
        *,
        subject: str | None = "auth0|user-1",
        audience: str | list[str] = AUTH0_AUDIENCE,
        issuer: str = AUTH0_ISSUER,
        expires_in: int = 3600,
        permissions: list[str] | None = None,
        scope: str | None = None,
        extra: dict[str, Any] | None = None,
        algorithm: str = "RS256",
        key: Any = _UNSET,
        kid: str = "test-key-1",
        include_exp: bool = True,
        not_before: int | None = None,
    ) -> str:
        now = int(time.time())
        payload: dict[str, Any] = {"iss": issuer, "aud": audience}
        if subject is not None:
            payload["sub"] = subject
        if include_exp:
            payload["exp"] = now + expires_in
        if not_before is not None:
            payload["nbf"] = now + not_before
        if permissions is not None:
            payload["permissions"] = permissions
        if scope is not None:
            payload["scope"] = scope
        if extra:
            payload.update(extra)
        signing_key = private_key if key is _UNSET else key
        return jwt.encode(payload, signing_key, algorithm=algorithm, headers={"kid": kid})

    return _mint
