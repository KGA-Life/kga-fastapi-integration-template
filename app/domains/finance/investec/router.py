"""Investec routes under ``/finance/investec``: list accounts + create payments.

Every route carries BOTH governance layers:

* caller auth via :func:`~app.routers.deps.require_api_key`, attached through the
  route ``dependencies=[...]`` list, and
* scope auth via :func:`~app.auth.dependencies.require_scopes`, injected as the
  ``principal`` parameter — ``finance:investec:read`` for reads,
  ``finance:investec:write`` for writes.

Each route binds path + params + ``response_model``, calls one service method,
and returns. The upstream Investec calls live in the (stubbed) service layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.models import Principal
from app.domains.finance.investec.models import Account, AccountTransaction, PaymentCreate
from app.domains.finance.investec.service import InvestecService, get_investec_service
from app.routers.deps import require_api_key, require_scopes

router = APIRouter(prefix="/investec", tags=["Finance: Investec"])

# Module-level Depends singletons (B008-safe; scope validated at import time).
_API_KEY = Depends(require_api_key)
_SERVICE = Depends(get_investec_service)
_READ = Depends(require_scopes("finance:investec:read"))
_WRITE = Depends(require_scopes("finance:investec:write"))


@router.get(
    "/accounts",
    response_model=list[Account],
    summary="List Investec accounts",
    dependencies=[_API_KEY],
)
def list_accounts(
    principal: Principal = _READ,
    service: InvestecService = _SERVICE,
) -> list[Account]:
    """List the caller's accounts (read; requires ``finance:investec:read``)."""
    return service.list_accounts()


@router.post(
    "/payments",
    response_model=AccountTransaction,
    status_code=201,
    summary="Create an Investec payment",
    dependencies=[_API_KEY],
)
def create_payment(
    payload: PaymentCreate,
    principal: Principal = _WRITE,
    service: InvestecService = _SERVICE,
) -> AccountTransaction:
    """Submit a beneficiary payment (write; requires ``finance:investec:write``)."""
    return service.create_payment(payload.model_dump(by_alias=True, exclude_none=True))
