"""Xero domain models: the invoice read response and the invoice write body.

Xero's Accounting API speaks PascalCase JSON (``InvoiceID``, ``InvoiceNumber``),
so the typed fields carry PascalCase aliases; ``extra="allow"`` (inherited from
:class:`FinanceBase`) keeps every other Xero field. Only the primary fields the
gateway cares about are typed — replace/extend against the real Xero schema.
"""

from pydantic import Field

from app.domains.finance.common import FinanceBase


class Invoice(FinanceBase):
    """A Xero invoice as returned by the read endpoint."""

    invoice_id: str | None = Field(default=None, alias="InvoiceID", examples=["INV-0001"])
    invoice_number: str | None = Field(default=None, alias="InvoiceNumber", examples=["INV-0001"])
    type: str | None = Field(default=None, alias="Type", examples=["ACCREC"])
    status: str | None = Field(default=None, alias="Status", examples=["AUTHORISED"])
    total: float | None = Field(default=None, alias="Total", examples=[1250.00])


class InvoiceCreate(FinanceBase):
    """Request body for creating a Xero invoice (the write path)."""

    type: str = Field(alias="Type", examples=["ACCREC"])
    contact_id: str = Field(alias="ContactID", examples=["00000000-0000-0000-0000-000000000000"])
    reference: str | None = Field(default=None, alias="Reference", examples=["Q3 services"])
