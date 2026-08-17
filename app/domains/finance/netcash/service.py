"""Stubbed Netcash service facade for the gateway template.

This mirrors the house service-layer shape (a thin router-facing class plus a
``get_netcash_service()`` factory) but performs **no** network I/O: every method
is an explicit STUB returning representative in-memory data shaped like the
models in :mod:`app.domains.finance.netcash.models`. The real Netcash NIWS SOAP
calls live in the dedicated Netcash integration and get wired in later.
"""

from __future__ import annotations

from typing import Any


class NetcashService:
    """Router-facing facade over the Netcash NIWS API (STUBBED).

    Demonstrates read (``list_transactions``) and write (``create_payment``)
    house style. Swap each stub for the real client; keep the topology.
    """

    def list_transactions(self, page: int = 1) -> list[dict]:
        """Return a page of account transactions (read).

        Returns wire-shaped (aliased) records so the router's ``response_model``
        coerces them exactly as a live payload would.
        """
        # TODO: wire to the real Netcash NIWS API — stubbed for the gateway template
        return [
            {
                "TransactionId": "TXN-1001",
                "AccountReference": "ACC-001",
                "Amount": 500.00,
                "ActionDate": "2026-08-17",
                "Status": "Processed",
            },
            {
                "TransactionId": "TXN-1002",
                "AccountReference": "ACC-002",
                "Amount": 1200.00,
                "ActionDate": "2026-08-16",
                "Status": "Pending",
            },
        ]

    def create_payment(self, payload: dict[str, Any]) -> dict:
        """Create a payment at Netcash and return the resulting transaction (write)."""
        # TODO: wire to the real Netcash NIWS API — stubbed for the gateway template
        return {
            "TransactionId": "TXN-1003",
            "Status": "Submitted",
            "ActionDate": "2026-08-17",
            **payload,
        }


def get_netcash_service() -> NetcashService:
    """Return a fresh :class:`NetcashService` (used by the route dependency)."""
    return NetcashService()
