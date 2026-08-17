"""Pydantic v2 models for the authorization layer: :class:`TokenClaims` and :class:`Principal`.

These are vendor-neutral by design — they carry no Auth0 or JWT-library types, so
routes and the scope registry depend only on them (and the :class:`AuthProvider`
ABC), never on the concrete identity provider. A provider's ``verify`` turns a
raw bearer token into a :class:`Principal`; the rest of the app authorizes
against that alone.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.auth.scopes import satisfies


class TokenClaims(BaseModel):
    """The standard JWT claims the gateway reads, typed for clarity.

    ``extra="allow"`` keeps any additional provider/tenant claims (e.g. custom
    namespaced claims) rather than dropping them, so nothing is lost when a token
    is modelled. Only the claims the gateway actually relies on are typed here.
    """

    model_config = ConfigDict(extra="allow")

    iss: str
    aud: str | list[str]
    exp: int
    sub: str
    nbf: int | None = None
    scope: str | None = None
    permissions: list[str] | None = None


class Principal(BaseModel):
    """The authenticated caller: their subject, granted scopes, and raw claims.

    ``scopes`` is the resolved grant set (from the RBAC ``permissions`` claim, or
    the space-delimited ``scope`` claim); ``claims`` retains the full validated
    claim set for auditing or downstream needs. Authorization decisions go
    through :meth:`has_scope`, which applies the hierarchical superset rules.
    """

    subject: str
    scopes: frozenset[str]
    claims: dict

    def has_scope(self, required: str) -> bool:
        """Return True if this principal's grants satisfy ``required``.

        Delegates to :func:`app.auth.scopes.satisfies`, so domain-wide supersets
        and the write-implies-read rule apply uniformly.
        """
        return satisfies(self.scopes, required)
