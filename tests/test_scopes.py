"""Unit matrix for the scope registry and the hierarchical ``satisfies`` rules.

Encodes the taxonomy from context §6: the six ``finance:<provider>:<action>``
leaves, the ``finance:read`` / ``finance:write`` domain-wide supersets, and the
two superset rules — domain-wide implies provider, and write implies read within
the same scope. The negatives pin the boundaries: a narrow grant never widens,
and grants never cross providers or domains.
"""

from __future__ import annotations

import pytest

from app.auth import scopes
from app.auth.models import Principal
from app.auth.scopes import (
    FINANCE_PROVIDERS,
    KNOWN_SCOPES,
    _grant_satisfies,
    finance_scope_strings,
    satisfies,
)

# The six provider-leaf truths of context §6.
SIX_LEAVES = [
    "finance:xero:read",
    "finance:xero:write",
    "finance:netcash:read",
    "finance:netcash:write",
    "finance:investec:read",
    "finance:investec:write",
]


@pytest.mark.parametrize("leaf", SIX_LEAVES)
def test_exact_scope_satisfies_itself(leaf: str) -> None:
    assert satisfies({leaf}, leaf) is True


@pytest.mark.parametrize("provider", FINANCE_PROVIDERS)
def test_write_implies_read_within_provider(provider: str) -> None:
    assert satisfies({f"finance:{provider}:write"}, f"finance:{provider}:read") is True


@pytest.mark.parametrize("provider", FINANCE_PROVIDERS)
def test_domain_wide_read_satisfies_provider_read(provider: str) -> None:
    assert satisfies({"finance:read"}, f"finance:{provider}:read") is True


@pytest.mark.parametrize("provider", FINANCE_PROVIDERS)
def test_domain_wide_write_satisfies_provider_read_and_write(provider: str) -> None:
    # Domain-wide write implies provider write, and (write => read) provider read.
    assert satisfies({"finance:write"}, f"finance:{provider}:write") is True
    assert satisfies({"finance:write"}, f"finance:{provider}:read") is True


def test_any_one_of_several_grants_satisfies() -> None:
    granted = {"openid", "finance:netcash:read", "profile"}
    assert satisfies(granted, "finance:netcash:read") is True


# --- Negatives ---------------------------------------------------------------


def test_narrow_grant_does_not_satisfy_domain_wide() -> None:
    assert satisfies({"finance:xero:read"}, "finance:read") is False
    assert satisfies({"finance:xero:write"}, "finance:write") is False


def test_cross_provider_is_denied() -> None:
    assert satisfies({"finance:xero:read"}, "finance:netcash:read") is False
    assert satisfies({"finance:xero:write"}, "finance:investec:read") is False


def test_read_does_not_imply_write() -> None:
    assert satisfies({"finance:xero:read"}, "finance:xero:write") is False


def test_write_only_implies_read_not_any_future_action() -> None:
    # Pins the intent of the `g_action == WRITE and r_action == READ` guard in
    # `_grant_satisfies`: a WRITE grant implies READ, but must NOT satisfy an
    # arbitrary (future) non-read action. Constructed at the parsed-grant level
    # with a SYNTHETIC action ("admin") that does not exist in ACTIONS today, so
    # the invariant survives the day a third action is added to the taxonomy.
    write_grant = ("finance", "xero", "write")
    # Real cases still hold: write => read True; read never widens to write.
    assert _grant_satisfies(write_grant, ("finance", "xero", "read")) is True
    assert _grant_satisfies(("finance", "xero", "read"), write_grant) is False
    # Future-proofing case: WRITE does not satisfy a hypothetical non-read action.
    assert _grant_satisfies(write_grant, ("finance", "xero", "admin")) is False


def test_domain_read_does_not_imply_domain_write() -> None:
    assert satisfies({"finance:read"}, "finance:write") is False


def test_cross_domain_is_denied() -> None:
    assert satisfies({"csc:read"}, "finance:read") is False
    assert satisfies({"finance:read"}, "csc:read") is False


def test_empty_grants_never_satisfy() -> None:
    assert satisfies(set(), "finance:xero:read") is False


def test_unrelated_oauth_scopes_are_ignored_not_errored() -> None:
    # Real tokens carry scopes outside our taxonomy (openid, email, ...): these
    # must be skipped, not raise.
    assert satisfies({"openid", "email", "offline_access"}, "finance:xero:read") is False


def test_malformed_required_scope_raises() -> None:
    with pytest.raises(ValueError, match="Malformed scope"):
        satisfies({"finance:xero:read"}, "finance")
    with pytest.raises(ValueError, match="Malformed scope"):
        satisfies({"finance:xero:read"}, "a:b:c:d")


# --- Registry ----------------------------------------------------------------


def test_known_scopes_contains_all_finance_leaves_and_supersets() -> None:
    for leaf in SIX_LEAVES:
        assert leaf in KNOWN_SCOPES
    assert "finance:read" in KNOWN_SCOPES
    assert "finance:write" in KNOWN_SCOPES


def test_reserved_domains_are_registered_but_have_no_leaves() -> None:
    for domain in ("csc", "legal", "audit", "hr"):
        assert f"{domain}:read" in KNOWN_SCOPES
        assert f"{domain}:write" in KNOWN_SCOPES
        # No provider leaves for reserved domains this round.
        assert not any(s.startswith(f"{domain}:") and s.count(":") == 2 for s in KNOWN_SCOPES)


def test_finance_scope_strings_are_the_eight_buildable_scopes_sorted() -> None:
    strings = finance_scope_strings()
    assert strings == sorted(strings)
    assert set(strings) == {
        "finance:read",
        "finance:write",
        *SIX_LEAVES,
    }


def test_principal_has_scope_delegates_to_satisfies() -> None:
    principal = Principal(
        subject="auth0|x",
        scopes=frozenset({"finance:xero:write"}),
        claims={},
    )
    assert principal.has_scope("finance:xero:read") is True  # write => read
    assert principal.has_scope("finance:netcash:read") is False  # cross-provider


def test_actions_and_domain_constants_are_wired() -> None:
    # Guard against a typo drift between the string constants and the taxonomy.
    assert scopes.FINANCE == "finance"
    assert scopes.READ == "read"
    assert scopes.WRITE == "write"
    assert set(scopes.FINANCE_PROVIDERS) == {"xero", "netcash", "investec"}
