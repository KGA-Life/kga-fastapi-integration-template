"""Netcash domain models: the transaction read response and the payment write body.

Netcash's NIWS service speaks PascalCase field names; the typed fields carry
those as aliases, and ``extra="allow"`` (inherited from :class:`FinanceBase`)
keeps everything else. Only the primary fields the gateway cares about are typed
— replace/extend against the real Netcash schema.
"""

from pydantic import Field

from app.domains.finance.common import FinanceBase


class Transaction(FinanceBase):
    """A Netcash account transaction as returned by the read endpoint."""

    transaction_id: str | None = Field(default=None, alias="TransactionId", examples=["TXN-1001"])
    account_reference: str | None = Field(
        default=None, alias="AccountReference", examples=["ACC-001"]
    )
    amount: float | None = Field(default=None, alias="Amount", examples=[500.00])
    action_date: str | None = Field(default=None, alias="ActionDate", examples=["2026-08-17"])
    status: str | None = Field(default=None, alias="Status", examples=["Processed"])


class PaymentCreate(FinanceBase):
    """Request body for creating a Netcash payment (the write path)."""

    account_reference: str = Field(alias="AccountReference", examples=["ACC-001"])
    amount: float = Field(alias="Amount", examples=[500.00])
    reference: str | None = Field(default=None, alias="Reference", examples=["Payout Aug"])
