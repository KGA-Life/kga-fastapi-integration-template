"""Canonical base model for the provider wrapper.

Providers speak varied JSON casing (PascalCase, camelCase, snake_case). Every
response/request model here subclasses :class:`ExampleBase`, which:

* accepts either the field's alias or its Python name on input
  (``populate_by_name=True``), so models can be built from wire payloads or
  native Python, and
* lets unknown provider fields pass through untouched (``extra="allow"``), so the
  wrapper stays forward-compatible as the provider grows new fields.

We deliberately type only the primary fields the service cares about rather than
exhaustively modelling every provider schema.
"""

from pydantic import BaseModel, ConfigDict


class ExampleBase(BaseModel):
    """Base for all provider models: alias/name interchange + passthrough."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)
