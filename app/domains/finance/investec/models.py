"""Investec domain models: the account read response, a posted transaction, and a payment body.

Investec's Business Banking API speaks camelCase JSON (``accountId``,
``currentBalance``), so the typed fields carry camelCase aliases; ``extra="allow"``
(inherited from :class:`FinanceBase`) keeps every other field. Only the primary
fields the gateway cares about are typed — replace/extend against the real
Investec schema.
"""

from pydantic import Field

from app.domains.finance.common import FinanceBase


class Account(FinanceBase):
    """An Investec bank account as returned by the read endpoint."""

    account_id: str | None = Field(default=None, alias="accountId", examples=["10000000001"])
    account_number: str | None = Field(
        default=None, alias="accountNumber", examples=["10000000001"]
    )
    account_name: str | None = Field(
        default=None, alias="accountName", examples=["KGA Life Operating"]
    )
    currency: str | None = Field(default=None, alias="currency", examples=["ZAR"])
    current_balance: float | None = Field(
        default=None, alias="currentBalance", examples=[125000.50]
    )


class AccountTransaction(FinanceBase):
    """An Investec account transaction (also the write path's created-record response)."""

    transaction_type: str | None = Field(default=None, alias="type", examples=["DEBIT"])
    amount: float | None = Field(default=None, alias="amount", examples=[1250.00])
    description: str | None = Field(default=None, alias="description", examples=["EFT payment"])
    posting_date: str | None = Field(default=None, alias="postingDate", examples=["2026-08-17"])


class PaymentCreate(FinanceBase):
    """Request body for creating an Investec beneficiary payment (the write path)."""

    account_id: str = Field(alias="accountId", examples=["10000000001"])
    beneficiary_id: str = Field(alias="beneficiaryId", examples=["BEN-001"])
    amount: float = Field(alias="amount", examples=[1250.00])
    reference: str | None = Field(default=None, alias="reference", examples=["Supplier payout"])
