"""Boot / liveness / OpenAPI contract tests.

These prove the app assembles and serves offline (no provider credentials, no
stored token) and that the OpenAPI surface exposes the representative endpoints.
"""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # app_env is echoed from settings; it must be one of the declared literals.
    assert body["app_env"] in ("dev", "prod")
    # The liveness payload is exactly these two keys — no secrets leak here.
    assert set(body) == {"status", "app_env"}


def test_openapi_json_available(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")


def test_docs_available(client: TestClient) -> None:
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_openapi_includes_representative_paths(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for expected in (
        "/integrations/example/items",
        "/integrations/example/items/{item_id}",
    ):
        assert expected in paths, f"missing OpenAPI path: {expected}"
    # /health lives outside the provider prefix but must still be documented.
    assert "/health" in paths
