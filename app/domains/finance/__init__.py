"""The ``finance`` domain: Xero, Netcash, and Investec wrapped under ``/finance``.

The single public object is :data:`app.domains.finance.router.router`, the
aggregate ``APIRouter`` that mounts the three provider subrouters. Provider
services are STUBBED for the gateway template (routing + auth are real; upstream
calls are not).
"""
