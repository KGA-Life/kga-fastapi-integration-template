"""Tier-1 tests: real RS256 JWT validation through :class:`Auth0Provider`, offline.

A test RSA keypair (``rsa_keypair`` fixture) signs tokens with ``jwt.encode`` and
the provider's ``signing_key_resolver`` is injected with the matching public key,
so verification is fully offline — no JWKS network fetch. These cover the happy
paths (RBAC ``permissions`` claim AND the space-delimited ``scope`` fallback) and
every rejection path, each of which must surface the vendor-neutral
:class:`InvalidTokenError` (never a raw crypto/JWT exception, never a 500).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.auth.auth0 import Auth0Provider
from app.auth.models import Principal
from app.auth.provider import InvalidTokenError


def test_valid_token_permissions_claim(auth0_provider: Auth0Provider, mint_token: Any) -> None:
    token = mint_token(
        subject="auth0|alice",
        permissions=["finance:xero:read", "finance:netcash:write"],
    )
    principal = auth0_provider.verify(token)
    assert isinstance(principal, Principal)
    assert principal.subject == "auth0|alice"
    assert principal.scopes == frozenset({"finance:xero:read", "finance:netcash:write"})
    # Full validated claim set is retained for auditing.
    assert principal.claims["sub"] == "auth0|alice"


def test_valid_token_scope_claim_fallback(auth0_provider: Auth0Provider, mint_token: Any) -> None:
    # No RBAC permissions claim => fall back to the space-delimited scope claim.
    token = mint_token(scope="finance:investec:read openid profile")
    principal = auth0_provider.verify(token)
    assert principal.scopes == frozenset({"finance:investec:read", "openid", "profile"})


def test_permissions_claim_wins_over_scope_claim(
    auth0_provider: Auth0Provider, mint_token: Any
) -> None:
    # When both are present the RBAC permissions claim is authoritative.
    token = mint_token(
        permissions=["finance:read"],
        scope="finance:xero:read should-be-ignored",
    )
    principal = auth0_provider.verify(token)
    assert principal.scopes == frozenset({"finance:read"})


def test_token_with_no_grants_yields_empty_scopes(
    auth0_provider: Auth0Provider, mint_token: Any
) -> None:
    principal = auth0_provider.verify(mint_token())
    assert principal.scopes == frozenset()


def test_tampered_signature_is_rejected(auth0_provider: Auth0Provider, mint_token: Any) -> None:
    token = mint_token(permissions=["finance:xero:read"])
    tampered = token[:-4] + ("WXYZ" if token[-4:] != "WXYZ" else "ABCD")
    with pytest.raises(InvalidTokenError):
        auth0_provider.verify(tampered)


def test_wrong_audience_is_rejected(auth0_provider: Auth0Provider, mint_token: Any) -> None:
    with pytest.raises(InvalidTokenError):
        auth0_provider.verify(mint_token(audience="https://api.someone-else/"))


def test_wrong_issuer_is_rejected(auth0_provider: Auth0Provider, mint_token: Any) -> None:
    with pytest.raises(InvalidTokenError):
        auth0_provider.verify(mint_token(issuer="https://evil-tenant.auth0.com/"))


def test_expired_token_is_rejected(auth0_provider: Auth0Provider, mint_token: Any) -> None:
    with pytest.raises(InvalidTokenError):
        auth0_provider.verify(mint_token(expires_in=-30))


def test_future_nbf_is_rejected(auth0_provider: Auth0Provider, mint_token: Any) -> None:
    # A token whose not-before (nbf) is in the future is not yet valid: PyJWT
    # raises ImmatureSignatureError, which the provider maps to InvalidTokenError.
    token = mint_token(permissions=["finance:xero:read"], not_before=3600)
    with pytest.raises(InvalidTokenError):
        auth0_provider.verify(token)


def test_alg_none_forgery_is_rejected(auth0_provider: Auth0Provider, mint_token: Any) -> None:
    # Unsigned "alg=none" token: the provider pins RS256, so it is refused.
    forged = mint_token(algorithm="none", key=None)
    with pytest.raises(InvalidTokenError):
        auth0_provider.verify(forged)


def test_hs256_forgery_is_rejected(auth0_provider: Auth0Provider, mint_token: Any) -> None:
    # Classic RS256->HS256 confusion: a symmetric-signed token is refused because
    # only RS256 is accepted.
    forged = mint_token(
        algorithm="HS256",
        key="a-shared-symmetric-secret-of-sufficient-length",
        permissions=["finance:read"],
    )
    with pytest.raises(InvalidTokenError):
        auth0_provider.verify(forged)


def test_missing_sub_is_rejected_not_500(auth0_provider: Auth0Provider, mint_token: Any) -> None:
    # A signed, otherwise-valid token with no subject must be a clean
    # InvalidTokenError, not an unhandled crash.
    token = mint_token(subject=None, permissions=["finance:xero:read"])
    with pytest.raises(InvalidTokenError):
        auth0_provider.verify(token)


def test_missing_exp_is_rejected(auth0_provider: Auth0Provider, mint_token: Any) -> None:
    # The provider requires exp/iss/aud; a token lacking exp is refused.
    token = mint_token(include_exp=False, permissions=["finance:xero:read"])
    with pytest.raises(InvalidTokenError):
        auth0_provider.verify(token)


def test_verify_fails_fast_when_tenant_unconfigured(mint_token: Any) -> None:
    # An Auth0Provider over blank settings must fail fast at verify-time naming the
    # missing env vars (this is a config error, surfaced as RuntimeError).
    from app.config import Settings

    provider = Auth0Provider(
        settings=Settings(auth0_domain="", auth0_api_audience=""),
        signing_key_resolver=lambda _token: "unused",
    )
    with pytest.raises(RuntimeError) as exc:
        provider.verify(mint_token())
    assert "AUTH0_DOMAIN" in str(exc.value)
    assert "AUTH0_API_AUDIENCE" in str(exc.value)


def test_algorithms_setting_is_parsed(auth0_settings: Any) -> None:
    # Comma-separated algorithms parse into a clean list (whitespace/blanks dropped).
    provider = Auth0Provider(settings=auth0_settings)
    assert provider._algorithms == ["RS256"]

    from app.config import Settings

    multi = Auth0Provider(
        settings=Settings(auth0_algorithms="RS256, RS384 ,, "),
    )
    assert multi._algorithms == ["RS256", "RS384"]
