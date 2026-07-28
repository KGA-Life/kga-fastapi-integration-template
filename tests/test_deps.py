"""Core governance-seam behaviour in ``app.routers.deps``.

These exercise the two seams the higher-level auth/router contract tests skip:

* ``require_api_key`` when ``API_KEYS`` is empty — the unguarded dev path (a request
  with no key is allowed through, with a warning logged); and
* the app-wide ``ProviderAuthError`` handler's content-negotiated branches — a
  ``503`` + ``login_url`` JSON body for an API client, and a ``307`` redirect for a
  browser. Both are triggered by overriding ``require_provider_auth`` to raise.
"""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.example.auth import ProviderAuthError, login_url
from app.main import app
from app.routers.deps import require_provider_auth
from tests.conftest import API_KEY, FakeExampleService, override_provider_auth

ITEMS_PATH = "/integrations/example/items"


def _raise_provider_auth() -> None:
    raise ProviderAuthError("no token stored")


def test_unguarded_when_no_api_keys_configured(
    client: TestClient, monkeypatch, fake_service: FakeExampleService
) -> None:
    # API_KEYS empty => caller-auth is disabled (dev convenience): a request with NO
    # X-API-Key is allowed through to the handler rather than 401'd.
    monkeypatch.delenv("API_KEYS", raising=False)
    get_settings.cache_clear()
    override_provider_auth(fake_service)
    resp = client.get(ITEMS_PATH)  # deliberately no X-API-Key
    assert resp.status_code == 200


def test_provider_auth_error_returns_503_json_for_api_client(
    client: TestClient, api_key: str
) -> None:
    app.dependency_overrides[require_provider_auth] = _raise_provider_auth
    resp = client.get(ITEMS_PATH, headers={"X-API-Key": API_KEY, "Accept": "application/json"})
    assert resp.status_code == 503
    body = resp.json()
    assert body["detail"] == "Provider authorization required"
    # login_url is absolute (built from the request base) and ends with the login path.
    assert body["login_url"].startswith("http")
    assert body["login_url"].endswith(login_url())


def test_provider_auth_error_redirects_browser(client: TestClient, api_key: str) -> None:
    app.dependency_overrides[require_provider_auth] = _raise_provider_auth
    resp = client.get(
        ITEMS_PATH,
        headers={"X-API-Key": API_KEY, "Accept": "text/html"},
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert resp.headers["location"].endswith(login_url())
