"""Stubbed Xero service facade for the gateway template.

This mirrors the house service-layer shape (a thin router-facing class plus a
``get_xero_service()`` factory) but performs **no** network I/O: every method is
an explicit STUB returning representative in-memory data shaped like the models
in :mod:`app.domains.finance.xero.models`. The gateway's job here is to prove the
routing + scope topology end-to-end; the real Xero calls live in the dedicated
``kga-xero-api`` service and get wired in later.
"""

from __future__ import annotations

from typing import Any


class XeroService:
    """Router-facing facade over the Xero Accounting API (STUBBED).

    Demonstrates read (``list_invoices``) and write (``create_invoice``) house
    style. Swap each stub for the real client; keep the router/scope topology.
    """

    def list_invoices(self, page: int = 1) -> list[dict]:
        """Return a page of invoices (read).

        Returns wire-shaped (PascalCase-aliased) records so the router's
        ``response_model`` coerces them exactly as a live payload would.
        """
        # TODO: wire to the real Xero API (kga-xero-api) — stubbed for the gateway template
        return [
            {
                "InvoiceID": "INV-0001",
                "InvoiceNumber": "INV-0001",
                "Type": "ACCREC",
                "Status": "AUTHORISED",
                "Total": 1250.00,
            },
            {
                "InvoiceID": "INV-0002",
                "InvoiceNumber": "INV-0002",
                "Type": "ACCPAY",
                "Status": "PAID",
                "Total": 480.50,
            },
        ]

    def create_invoice(self, payload: dict[str, Any]) -> dict:
        """Create an invoice at Xero and return the created record (write)."""
        # TODO: wire to the real Xero API (kga-xero-api) — stubbed for the gateway template
        return {
            "InvoiceID": "INV-0003",
            "InvoiceNumber": "INV-0003",
            "Status": "DRAFT",
            **payload,
        }


def get_xero_service() -> XeroService:
    """Return a fresh :class:`XeroService` (used by the route dependency)."""
    return XeroService()
