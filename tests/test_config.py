"""Settings governance: use-time credential validation and derived provider URLs.

Pure ``Settings``-object tests (no app/client). Init kwargs beat env/.env, so these
are hermetic regardless of the environment they run in.
"""

import pytest

from app.config import API_PREFIX, Settings


def _settings(**kw) -> Settings:
    base = {"example_client_id": "", "example_client_secret": ""}
    base.update(kw)
    return Settings(**base)


def test_require_credentials_raises_naming_both_when_missing() -> None:
    with pytest.raises(RuntimeError) as exc:
        _settings().require_credentials()
    msg = str(exc.value)
    assert "EXAMPLE_CLIENT_ID" in msg
    assert "EXAMPLE_CLIENT_SECRET" in msg


def test_require_credentials_names_only_the_missing_one() -> None:
    with pytest.raises(RuntimeError) as exc:
        _settings(example_client_id="have-id").require_credentials()
    msg = str(exc.value)
    assert "EXAMPLE_CLIENT_SECRET" in msg
    assert "EXAMPLE_CLIENT_ID" not in msg


def test_require_credentials_passes_when_both_present() -> None:
    # Must not raise.
    _settings(example_client_id="id", example_client_secret="sec").require_credentials()


def test_has_credentials_property() -> None:
    assert _settings().has_credentials is False
    assert _settings(example_client_id="id", example_client_secret="sec").has_credentials is True


def test_derived_provider_urls() -> None:
    s = _settings(app_base_url="https://svc.example.org/")
    assert s.callback_path == f"{API_PREFIX}/auth/callback"
    # the trailing slash on the base URL is stripped before joining.
    assert s.redirect_uri == f"https://svc.example.org{API_PREFIX}/auth/callback"
