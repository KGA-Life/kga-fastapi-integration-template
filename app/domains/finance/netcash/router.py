"""Netcash routes under ``/finance/netcash``: list transactions + create payments.

Every route carries BOTH governance layers:

* caller auth via :func:`~app.routers.deps.require_api_key`, attached through the
  route ``dependencies=[...]`` list, and
* scope auth via :func:`~app.auth.dependencies.require_scopes`, injected as the
  ``principal`` parameter — ``finance:netcash:read`` for reads,
  ``finance:netcash:write`` for writes.

Each route binds path + params + ``response_model``, calls one service method,
and returns. The upstream Netcash NIWS calls live in the (stubbed) service layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth.models import Principal
from app.domains.finance.netcash.models import PaymentCreate, Transaction
from app.domains.finance.netcash.service import NetcashService, get_netcash_service
from app.routers.deps import require_api_key, require_scopes

router = APIRouter(prefix="/netcash", tags=["Finance: Netcash"])

# Module-level Depends singletons (B008-safe; scope validated at import time).
_API_KEY = Depends(require_api_key)
_SERVICE = Depends(get_netcash_service)
_READ = Depends(require_scopes("finance:netcash:read"))
_WRITE = Depends(require_scopes("finance:netcash:write"))


@router.get(
    "/transactions",
    response_model=list[Transaction],
    summary="List Netcash transactions",
    dependencies=[_API_KEY],
)
def list_transactions(
    page: int = Query(1, ge=1, description="1-indexed page of transactions"),
    principal: Principal = _READ,
    service: NetcashService = _SERVICE,
) -> list[Transaction]:
    """List account transactions (read; requires ``finance:netcash:read``)."""
    return service.list_transactions(page=page)


@router.post(
    "/payments",
    response_model=Transaction,
    status_code=201,
    summary="Create a Netcash payment",
    dependencies=[_API_KEY],
)
def create_payment(
    payload: PaymentCreate,
    principal: Principal = _WRITE,
    service: NetcashService = _SERVICE,
) -> Transaction:
    """Create a payment (write; requires ``finance:netcash:write``)."""
    return service.create_payment(payload.model_dump(by_alias=True, exclude_none=True))
