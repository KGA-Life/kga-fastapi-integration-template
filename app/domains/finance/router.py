"""The ``finance`` domain's aggregate router — the single object ``main.py`` mounts.

Owns the ``/finance`` prefix and mounts the three provider subrouters so their
full paths become ``/finance/xero/*``, ``/finance/netcash/*``, and
``/finance/investec/*``. Each provider subrouter carries its own two-layer auth
(``require_api_key`` + granular ``require_scopes``); this module only composes
them under one prefix.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.domains.finance.investec.router import router as investec_router
from app.domains.finance.netcash.router import router as netcash_router
from app.domains.finance.xero.router import router as xero_router

router = APIRouter(prefix="/finance", tags=["Finance"])

router.include_router(xero_router)
router.include_router(netcash_router)
router.include_router(investec_router)
