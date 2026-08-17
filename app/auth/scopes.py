"""The single source of truth for the gateway's authorization scopes.

Scopes are shaped ``<domain>:<provider>:<action>`` (e.g. ``finance:xero:read``),
with two-part **domain-wide** supersets ``<domain>:<action>`` (e.g.
``finance:read``) that imply every provider under that domain. This registry is
the one place the taxonomy is defined; routes declare the scopes they require
against these constants, and the strings here are what the operator mirrors in
the Auth0 dashboard (see the UI handoff). Keeping the registry enumerable makes
it testable and diffable against the tenant config.

Superset semantics (implemented by :func:`satisfies`):

* A **domain-wide** grant satisfies any provider route in that domain —
  ``finance:read`` satisfies ``finance:xero:read``.
* **write implies read** within the same scope — ``finance:xero:write`` (or
  ``finance:write``) satisfies ``finance:xero:read``.
* A **narrow** grant never widens — ``finance:xero:read`` does NOT satisfy the
  domain-wide ``finance:read``, and never crosses providers.

Only the ``finance`` domain is built out as routes this round; the reserved
domains (``csc``/``legal``/``audit``/``hr``) appear here as documented
domain-wide constants so the taxonomy is stable before those domains exist.
"""

from __future__ import annotations

from collections.abc import Iterable

# --- Domains ----------------------------------------------------------------

# The one domain built out with routes this round.
FINANCE = "finance"

# Reserved domains: present in the registry so the taxonomy is complete and
# diffable, but NO routes are built for them this round.
CSC = "csc"
LEGAL = "legal"
AUDIT = "audit"
HR = "hr"

RESERVED_DOMAINS: tuple[str, ...] = (CSC, LEGAL, AUDIT, HR)

# --- Finance providers ------------------------------------------------------

XERO = "xero"
NETCASH = "netcash"
INVESTEC = "investec"

FINANCE_PROVIDERS: tuple[str, ...] = (XERO, NETCASH, INVESTEC)

# --- Actions ----------------------------------------------------------------

READ = "read"
WRITE = "write"

ACTIONS: tuple[str, ...] = (READ, WRITE)


def _finance_scopes() -> set[str]:
    """Every buildable ``finance`` scope: provider leaves + domain-wide supersets."""
    scopes = {f"{FINANCE}:{action}" for action in ACTIONS}
    scopes |= {
        f"{FINANCE}:{provider}:{action}" for provider in FINANCE_PROVIDERS for action in ACTIONS
    }
    return scopes


def _reserved_scopes() -> set[str]:
    """Domain-wide read/write for each reserved domain (no provider leaves yet)."""
    return {f"{domain}:{action}" for domain in RESERVED_DOMAINS for action in ACTIONS}


# The complete registry: every scope string this gateway recognises. Includes
# the buildable finance scopes and the reserved domain-wide scopes, so the set
# is complete and diffable against the Auth0 dashboard.
KNOWN_SCOPES: frozenset[str] = frozenset(_finance_scopes() | _reserved_scopes())


def finance_scope_strings() -> list[str]:
    """Return the buildable ``finance`` scope strings, sorted (for tests/handoff)."""
    return sorted(_finance_scopes())


def _parse(scope: str) -> tuple[str, str | None, str]:
    """Parse a scope into ``(domain, provider_or_None, action)``.

    A two-part scope (``finance:read``) is domain-wide, so ``provider`` is
    ``None``; a three-part scope (``finance:xero:read``) is provider-scoped.
    Raises :class:`ValueError` for any other shape.
    """
    parts = scope.split(":")
    if len(parts) == 2:
        domain, action = parts
        return domain, None, action
    if len(parts) == 3:
        domain, provider, action = parts
        return domain, provider, action
    raise ValueError(
        f"Malformed scope {scope!r}: expected '<domain>:<action>' or "
        "'<domain>:<provider>:<action>'."
    )


def _grant_satisfies(
    granted: tuple[str, str | None, str], required: tuple[str, str | None, str]
) -> bool:
    """Return True if a single parsed grant covers the parsed requirement."""
    g_domain, g_provider, g_action = granted
    r_domain, r_provider, r_action = required
    if g_domain != r_domain:
        return False
    # A domain-wide grant (provider is None) covers any provider; otherwise the
    # provider must match exactly.
    if g_provider is not None and g_provider != r_provider:
        return False
    # write implies read; otherwise the action must match exactly.
    return g_action == r_action or g_action == WRITE


def satisfies(granted: Iterable[str], required: str) -> bool:
    """Return True if any granted scope satisfies ``required`` (hierarchical superset).

    ``required`` must be a well-formed scope string (raises :class:`ValueError`
    otherwise); malformed entries in ``granted`` (e.g. unrelated OAuth scopes
    like ``openid``) are ignored rather than raising, since real tokens carry
    scopes outside this registry.
    """
    required_parsed = _parse(required)
    for scope in granted:
        try:
            granted_parsed = _parse(scope)
        except ValueError:
            # Tokens routinely carry scopes outside our taxonomy; skip them.
            continue
        if _grant_satisfies(granted_parsed, required_parsed):
            return True
    return False
