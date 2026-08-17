"""Canonical base model for the finance domain's provider wrappers.

Finance providers speak varied JSON casing (Xero PascalCase, Investec camelCase,
Netcash mixed). Every request/response model in the ``finance`` domain subclasses
:class:`FinanceBase`, which mirrors :class:`app.models.common.ExampleBase`:

* accepts either the field's alias or its Python name on input
  (``populate_by_name=True``), so models build from wire payloads or native
  Python, and
* lets unknown provider fields pass through untouched (``extra="allow"``), so the
  wrapper stays forward-compatible as each provider grows new fields.

Only the primary fields the gateway cares about are typed; everything else rides
along via passthrough.
"""

from pydantic import BaseModel, ConfigDict


class FinanceBase(BaseModel):
    """Base for all finance provider models: alias/name interchange + passthrough."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)
