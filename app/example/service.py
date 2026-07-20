"""Thin provider service facade over ``httpx`` for the KGA integration API template.

All interaction with the third-party provider is funnelled through
:class:`ExampleService`. Routers stay thin: they bind path + params +
``response_model`` and call one service method; this layer owns the HTTP client,
request dispatch, and error mapping.

Construction performs **no** I/O — it only stores the configured base URL and
builds the ``httpx.Client`` lazily on first use — so the service can be
instantiated at import/boot without a network round-trip.

Error mapping
-------------
* HTTP ``401`` / ``403`` -> :class:`~app.example.auth.ProviderAuthError` (the
  provider no longer accepts our token; re-authorization is required). It
  propagates to the app-wide handler in :mod:`app.routers.deps`.
* HTTP ``429`` -> :class:`fastapi.HTTPException` ``429`` with a ``Retry-After``
  header (relayed from the provider when present, else ``"60"``).
* Other ``4xx`` / ``5xx`` -> :class:`fastapi.HTTPException` carrying that status
  and a safe, secret-free detail message.
* Transport error (DNS/TLS/timeout) -> :class:`fastapi.HTTPException` ``502``.
"""

from __future__ import annotations

from typing import Any, NoReturn

import httpx
from fastapi import HTTPException

from app.config import get_settings
from app.example.auth import ProviderAuthError


class ExampleService:
    """Router-facing facade over the provider's HTTP API.

    Demonstrates both read (``list_items`` / ``get_item``) and write
    (``create_item``) house style. Swap the paths and payloads for the concrete
    provider; keep the error mapping.
    """

    def __init__(self) -> None:
        # No I/O here: just capture config. The client is built lazily so the
        # service can be constructed offline.
        self._base_url = get_settings().example_api_base.rstrip("/")
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Return the lazily-built ``httpx.Client`` bound to the provider base URL."""
        if self._client is None:
            self._client = httpx.Client(base_url=self._base_url, timeout=30.0)
        return self._client

    def list_items(self, page: int = 1) -> list[dict]:
        """Return a page of items from the provider (read)."""
        data = self._request("GET", "/items", params={"page": page})
        items = data.get("items") if isinstance(data, dict) else data
        return items or []

    def get_item(self, item_id: str) -> dict:
        """Return a single item by id from the provider (read)."""
        return self._request("GET", f"/items/{item_id}")

    def create_item(self, payload: dict) -> dict:
        """Create an item at the provider and return the created record (write)."""
        return self._request("POST", "/items", json=payload)

    # -- internals -----------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Dispatch one provider request and map failures onto the right exception."""
        try:
            response = self.client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            # Transport-level failure (DNS/TLS/timeout) -> upstream gateway error.
            raise HTTPException(status_code=502, detail="Provider request failed") from exc
        if response.status_code >= 400:
            self._raise_mapped(response)
        return response.json()

    @staticmethod
    def _raise_mapped(response: httpx.Response) -> NoReturn:
        """Translate a non-2xx provider response into the appropriate exception."""
        status = response.status_code
        if status in (401, 403):
            raise ProviderAuthError(
                f"Provider rejected the access token (HTTP {status}); re-authorization required."
            )
        if status == 429:
            retry_after = response.headers.get("Retry-After", "60")
            raise HTTPException(
                status_code=429,
                detail="Provider rate limit exceeded",
                headers={"Retry-After": retry_after},
            )
        raise HTTPException(status_code=status, detail=f"Provider API error {status}")


def get_example_service() -> ExampleService:
    """Return a fresh :class:`ExampleService` (used by the auth dependency)."""
    return ExampleService()
