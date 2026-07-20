"""Example domain routes: read + write over the provider, kept deliberately thin.

Every route carries BOTH governance dependencies:

* :func:`~app.routers.deps.require_api_key` (caller auth), attached via the
  route ``dependencies=[...]`` list, and
* :func:`~app.routers.deps.require_provider_auth`, which yields the authenticated
  :class:`~app.example.service.ExampleService`.

Each route binds path + params + ``response_model``, calls one service method,
and returns. No provider HTTP, pagination, or error mapping lives here — that all
belongs to the service layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.config import API_PREFIX
from app.example.service import ExampleService
from app.models import Item, ItemCreate
from app.routers.deps import require_api_key, require_provider_auth

router = APIRouter(prefix=API_PREFIX, tags=["Example"])

# Module-level singletons so the callables aren't function calls in argument
# defaults (bugbear B008); FastAPI reads them identically to inline ``Depends``.
_API_KEY = Depends(require_api_key)
_SERVICE = Depends(require_provider_auth)


@router.get(
    "/items",
    response_model=list[Item],
    summary="List items",
    dependencies=[_API_KEY],
)
def list_items(
    page: int = Query(1, ge=1, description="1-indexed page of items"),
    service: ExampleService = _SERVICE,
) -> list[Item]:
    """List items (paged)."""
    return service.list_items(page=page)


@router.get(
    "/items/{item_id}",
    response_model=Item,
    summary="Get an item by ID",
    dependencies=[_API_KEY],
)
def get_item(
    item_id: str,
    service: ExampleService = _SERVICE,
) -> Item:
    """Fetch a single item by its provider id."""
    return service.get_item(item_id)


@router.post(
    "/items",
    response_model=Item,
    status_code=201,
    summary="Create an item",
    dependencies=[_API_KEY],
)
def create_item(
    payload: ItemCreate,
    service: ExampleService = _SERVICE,
) -> Item:
    """Create an item at the provider (write path)."""
    return service.create_item(payload.model_dump(by_alias=True, exclude_none=True))
