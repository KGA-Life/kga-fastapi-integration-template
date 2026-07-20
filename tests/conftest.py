"""Shared pytest fixtures for the fully-offline template test suite.

No fixture here performs a live provider call. Two invariants are enforced for
every test:

* the lru_cached singletons (``get_settings`` / ``get_token_store``) are cleared
  before and after each test, so a test that repoints an env var cannot leak
  that state into another test; and
* ``app.dependency_overrides`` is emptied around each test, so a router test that
  overrides ``require_provider_auth`` starts and ends from a clean app.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
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


def _clear_caches() -> None:
    """Clear every lru_cached singleton so callers rebuild from env."""
    get_settings.cache_clear()
    get_token_store.cache_clear()


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
