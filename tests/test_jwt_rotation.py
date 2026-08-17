"""Tier-1 tests: per-``kid`` signing-key resolution (JWKS rotation tolerance), offline.

The provider resolves the signing key *per token* from the token's ``kid`` header
rather than caching a single key — which is exactly what makes a JWKS key rotation
(old + new key valid concurrently) safe. These prove that behaviour with an
injected resolver mapping two ``kid``s to two distinct RSA public keys, so no
network JWKS fetch happens.

An unknown ``kid`` must surface the vendor-neutral :class:`InvalidTokenError`
(mirroring production, where :class:`jwt.PyJWKClient` raises ``PyJWKClientError``
for an unknown ``kid`` and the provider remaps it) — never an unhandled 500.
"""

from __future__ import annotations

from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.exceptions import PyJWKClientError

from app.auth.auth0 import Auth0Provider
from app.auth.models import Principal
from app.auth.provider import InvalidTokenError
from app.config import Settings


@pytest.fixture
def rotating_provider(
    rsa_keypair: tuple[Any, Any], auth0_settings: Settings
) -> tuple[Auth0Provider, Any]:
    """A provider whose resolver maps two ``kid``s to two distinct public keys.

    Key ``"A"`` is the session keypair (so ``mint_token``'s default signing key
    matches it); key ``"B"`` is a second, independently-generated keypair. Returns
    the provider and key B's *private* key so a token can be signed with it.
    """
    _private_a, public_a = rsa_keypair
    private_b = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    keys_by_kid = {"A": public_a, "B": private_b.public_key()}

    def resolver(token: str) -> Any:
        kid = jwt.get_unverified_header(token).get("kid")
        try:
            return keys_by_kid[kid]
        except KeyError as exc:
            # Mirror PyJWKClient's behaviour for an unknown kid; the provider
            # catches PyJWKClientError and remaps it to InvalidTokenError.
            raise PyJWKClientError(f"Unable to find a signing key for kid {kid!r}") from exc

    provider = Auth0Provider(settings=auth0_settings, signing_key_resolver=resolver)
    return provider, private_b


def test_both_rotated_kids_verify(
    rotating_provider: tuple[Auth0Provider, Any], mint_token: Any
) -> None:
    # Token signed with key A (default mint key) resolves via kid "A".
    provider, private_b = rotating_provider
    token_a = mint_token(subject="auth0|alice", kid="A", permissions=["finance:xero:read"])
    principal_a = provider.verify(token_a)
    assert isinstance(principal_a, Principal)
    assert principal_a.subject == "auth0|alice"
    assert principal_a.scopes == frozenset({"finance:xero:read"})

    # Token signed with the *different* key B resolves via kid "B" — proving the
    # provider does not cache key A but resolves per-kid.
    token_b = mint_token(
        subject="auth0|bob", kid="B", key=private_b, permissions=["finance:netcash:write"]
    )
    principal_b = provider.verify(token_b)
    assert principal_b.subject == "auth0|bob"
    assert principal_b.scopes == frozenset({"finance:netcash:write"})


def test_unknown_kid_is_rejected_not_500(
    rotating_provider: tuple[Auth0Provider, Any], mint_token: Any
) -> None:
    # A token whose kid the resolver cannot map must become a clean
    # InvalidTokenError, not an unhandled crash.
    provider, _private_b = rotating_provider
    token = mint_token(kid="unknown-kid", permissions=["finance:xero:read"])
    with pytest.raises(InvalidTokenError):
        provider.verify(token)
