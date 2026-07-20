"""Example domain models: the read response and the write request body.

These illustrate the house style — typed primary fields with a wire alias, plus
``extra="allow"`` passthrough inherited from :class:`ExampleBase`. Replace with
the concrete provider's fields.
"""

from pydantic import Field

from app.models.common import ExampleBase


class Item(ExampleBase):
    """A provider item as returned by the read endpoints."""

    item_id: str | None = Field(default=None, alias="id", examples=["item-001"])
    name: str | None = Field(default=None, alias="name", examples=["Example Widget"])
    status: str | None = Field(default=None, alias="status", examples=["active"])


class ItemCreate(ExampleBase):
    """Request body for creating an item (the write path)."""

    name: str = Field(alias="name", examples=["New Widget"])
    status: str | None = Field(default=None, alias="status", examples=["active"])
