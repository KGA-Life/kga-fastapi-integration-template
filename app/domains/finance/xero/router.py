"""Xero routes under ``/finance/xero``: list + create invoices, kept deliberately thin.

Every route carries BOTH governance layers:

* caller auth via :func:`~app.routers.deps.require_api_key`, attached through the
  route ``dependencies=[...]`` list, and
* scope auth via :func:`~app.auth.dependencies.require_scopes`, injected as the
  ``principal`` parameter — ``finance:xero:read`` for reads, ``finance:xero:write``
  for writes (write implies read via the registry's superset rules).

Each route binds path + params + ``response_model``, calls one service method,
and returns. The upstream Xero calls live in the (stubbed) service layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth.models import Principal
from app.domains.finance.xero.models import Invoice, InvoiceCreate
from app.domains.finance.xero.service import XeroService, get_xero_service
from app.routers.deps import require_api_key, require_scopes

router = APIRouter(prefix="/xero", tags=["Finance: Xero"])

# Module-level Depends singletons so the callables aren't function calls in
# argument defaults (bugbear B008); FastAPI reads them identically to inline
# Depends. ``require_scopes`` validates its scope against KNOWN_SCOPES when
# called here, so a typo fails loudly at import (wiring) time.
_API_KEY = Depends(require_api_key)
_SERVICE = Depends(get_xero_service)
_READ = Depends(require_scopes("finance:xero:read"))
_WRITE = Depends(require_scopes("finance:xero:write"))


@router.get(
    "/invoices",
    response_model=list[Invoice],
    summary="List Xero invoices",
    dependencies=[_API_KEY],
)
def list_invoices(
    page: int = Query(1, ge=1, description="1-indexed page of invoices"),
    principal: Principal = _READ,
    service: XeroService = _SERVICE,
) -> list[Invoice]:
    """List invoices (read; requires ``finance:xero:read``)."""
    return service.list_invoices(page=page)


@router.post(
    "/invoices",
    response_model=Invoice,
    status_code=201,
    summary="Create a Xero invoice",
    dependencies=[_API_KEY],
)
def create_invoice(
    payload: InvoiceCreate,
    principal: Principal = _WRITE,
    service: XeroService = _SERVICE,
) -> Invoice:
    """Create an invoice (write; requires ``finance:xero:write``)."""
    return service.create_invoice(payload.model_dump(by_alias=True, exclude_none=True))
