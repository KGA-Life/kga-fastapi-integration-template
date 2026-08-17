"""Auth0 settings governance: use-time config validation and the derived issuer.

Pure ``Settings``-object tests (no app/client). Init kwargs beat env/.env, so
these are hermetic: the missing-config cases force blank tenant values explicitly
regardless of any local ``.env``.
"""

from __future__ import annotations

import pytest

from app.config import Settings


def _settings(**kw) -> Settings:
    # Force a clean auth baseline; individual tests override as needed.
    base = {"auth0_domain": "", "auth0_api_audience": ""}
    base.update(kw)
    return Settings(**base)


def test_auth_provider_defaults_to_auth0() -> None:
    assert Settings().auth_provider == "auth0"


def test_auth_settings_load_from_kwargs() -> None:
    s = _settings(
        auth0_domain="tenant.eu.auth0.com",
        auth0_api_audience="https://api.kga/gw",
        auth0_algorithms="RS256,RS384",
    )
    assert s.auth0_domain == "tenant.eu.auth0.com"
    assert s.auth0_api_audience == "https://api.kga/gw"
    assert s.auth0_algorithms == "RS256,RS384"


def test_require_auth0_config_names_both_when_unset() -> None:
    with pytest.raises(RuntimeError) as exc:
        _settings().require_auth0_config()
    msg = str(exc.value)
    assert "AUTH0_DOMAIN" in msg
    assert "AUTH0_API_AUDIENCE" in msg


def test_require_auth0_config_names_only_the_missing_one() -> None:
    with pytest.raises(RuntimeError) as exc:
        _settings(auth0_domain="tenant.auth0.com").require_auth0_config()
    msg = str(exc.value)
    assert "AUTH0_API_AUDIENCE" in msg
    assert "AUTH0_DOMAIN" not in msg


def test_require_auth0_config_passes_when_both_present() -> None:
    # Must not raise.
    _settings(
        auth0_domain="tenant.auth0.com",
        auth0_api_audience="https://api.kga/gw",
    ).require_auth0_config()


def test_auth0_issuer_derives_from_domain_with_trailing_slash() -> None:
    s = _settings(auth0_domain="tenant.eu.auth0.com")
    assert s.auth0_issuer == "https://tenant.eu.auth0.com/"


def test_auth0_algorithms_default_is_rs256() -> None:
    assert Settings().auth0_algorithms == "RS256"
