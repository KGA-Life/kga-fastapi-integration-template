"""Caller-auth contract for data endpoints.

With ``API_KEYS`` configured, a data route requires a valid ``X-API-Key``:
missing or wrong -> ``401``; correct -> ``200`` (with the provider-auth
dependency overridden by the fake service). ``/health`` needs no key.

The fake service is always installed so the ONLY failure source under test is
the API-key check — the result never depends on provider-auth ordering.
"""

from fastapi.testclient import TestClient

from tests.conftest import API_KEY, FakeExampleService, override_provider_auth

ITEMS_PATH = "/integrations/example/items"


def test_missing_api_key_is_rejected(
    client: TestClient, api_key: str, fake_service: FakeExampleService
) -> None:
    override_provider_auth(fake_service)
    resp = client.get(ITEMS_PATH)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing or invalid API key"


def test_wrong_api_key_is_rejected(
    client: TestClient, api_key: str, fake_service: FakeExampleService
) -> None:
    override_provider_auth(fake_service)
    resp = client.get(ITEMS_PATH, headers={"X-API-Key": "not-the-key"})
    assert resp.status_code == 401


def test_correct_api_key_is_accepted(
    client: TestClient, api_key: str, fake_service: FakeExampleService
) -> None:
    override_provider_auth(fake_service)
    resp = client.get(ITEMS_PATH, headers={"X-API-Key": API_KEY})
    assert resp.status_code == 200


def test_health_needs_no_api_key(client: TestClient, api_key: str) -> None:
    # /health is unauthenticated even when API_KEYS is configured.
    resp = client.get("/health")
    assert resp.status_code == 200
