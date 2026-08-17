"""Stubbed Investec service facade for the gateway template.

This mirrors the house service-layer shape (a thin router-facing class plus a
``get_investec_service()`` factory) but performs **no** network I/O: every method
is an explicit STUB returning representative in-memory data shaped like the
models in :mod:`app.domains.finance.investec.models`. The real Investec Business
Banking API calls live in the dedicated integration and get wired in later.
"""

from __future__ import annotations

from typing import Any


class InvestecService:
    """Router-facing facade over the Investec Business Banking API (STUBBED).

    Demonstrates read (``list_accounts``) and write (``create_payment``) house
    style. Swap each stub for the real client; keep the topology.
    """

    def list_accounts(self) -> list[dict]:
        """Return the caller's Investec accounts (read).

        Returns wire-shaped (camelCase-aliased) records so the router's
        ``response_model`` coerces them exactly as a live payload would.
        """
        # TODO: wire to the real Investec API — stubbed for the gateway template
        return [
            {
                "accountId": "10000000001",
                "accountNumber": "10000000001",
                "accountName": "KGA Life Operating",
                "currency": "ZAR",
                "currentBalance": 125000.50,
            },
            {
                "accountId": "10000000002",
                "accountNumber": "10000000002",
                "accountName": "KGA Life Claims",
                "currency": "ZAR",
                "currentBalance": 48250.00,
            },
        ]

    def create_payment(self, payload: dict[str, Any]) -> dict:
        """Submit a beneficiary payment and return the resulting transaction (write)."""
        # TODO: wire to the real Investec API — stubbed for the gateway template
        return {
            "type": "DEBIT",
            "amount": payload.get("amount"),
            "description": payload.get("reference", "Beneficiary payment"),
            "postingDate": "2026-08-17",
        }


def get_investec_service() -> InvestecService:
    """Return a fresh :class:`InvestecService` (used by the route dependency)."""
    return InvestecService()
