"""Router behaviour with a correct API key and the provider auth overridden.

These prove the thin routers wire the fake ``ExampleService`` through the
response models correctly — alias serialization on output, ``extra="allow"``
passthrough of unknown provider fields, and the create (write) path.
"""

from fastapi.testclient import TestClient

from tests.conftest import API_KEY, FakeExampleService, override_provider_auth

ITEMS_PATH = "/integrations/example/items"
AUTH_HEADER = {"X-API-Key": API_KEY}


def test_list_items_shaped_by_model_with_passthrough(
    client: TestClient, api_key: str, fake_service: FakeExampleService
) -> None:
    override_provider_auth(fake_service)
    resp = client.get(ITEMS_PATH, headers=AUTH_HEADER)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    item = body[0]
    assert item["id"] == "item-001"
    assert item["name"] == "Example Widget"
    # Unknown field survives via extra="allow".
    assert item["UnknownFutureField"] == "passthrough-value"


def test_get_single_item(
    client: TestClient, api_key: str, fake_service: FakeExampleService
) -> None:
    override_provider_auth(fake_service)
    resp = client.get(f"{ITEMS_PATH}/item-001", headers=AUTH_HEADER)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "item-001"
    assert body["name"] == "Example Widget"


def test_create_item_write_path(
    client: TestClient, api_key: str, fake_service: FakeExampleService
) -> None:
    override_provider_auth(fake_service)
    resp = client.post(ITEMS_PATH, headers=AUTH_HEADER, json={"name": "New Widget"})
    assert resp.status_code == 201
    body = resp.json()
    # Server-assigned id from the fake, plus the submitted name echoed back.
    assert body["id"] == "item-new-999"
    assert body["name"] == "New Widget"


def test_create_item_rejects_invalid_body(
    client: TestClient, api_key: str, fake_service: FakeExampleService
) -> None:
    override_provider_auth(fake_service)
    # ``name`` is required on ItemCreate -> FastAPI validation 422.
    resp = client.post(ITEMS_PATH, headers=AUTH_HEADER, json={"status": "active"})
    assert resp.status_code == 422
