"""Central configuration for the KGA integration API template.

This module is the single source of truth for provider endpoint constants and
application settings. Every other module imports its constants and its
``Settings`` instance (via :func:`get_settings`) from here.

Design note: the provider client id/secret are intentionally *optional* at the
settings layer so the app can boot offline — ``uvicorn app.main:app`` starts
and ``/docs`` renders without real credentials, and the test suite runs without
a populated ``.env``. Credentials are validated at provider *use-time* via
:meth:`Settings.require_credentials`, which fails fast with a clear error,
rather than at import-time.

To turn this template into a concrete service, rename ``example`` throughout to
the provider (``freshdesk``, ``netcash``, ...), point the fields below at the
real API, and swap :data:`API_PREFIX` for this service's namespace.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Application constants --------------------------------------------------

# The per-integration URL namespace: ``/<domain>/<provider>``. Every data route
# is mounted under this prefix. RENAME this per service (e.g. ``/finance/xero``,
# ``/support/freshdesk``); ``/health`` deliberately lives outside it.
API_PREFIX = "/integrations/example"


class Settings(BaseSettings):
    """Application settings, populated from the environment and ``.env``.

    Environment variable names are the UPPER_SNAKE_CASE form of each field
    (e.g. ``example_client_id`` <- ``EXAMPLE_CLIENT_ID``), matching
    ``.env.example``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["dev", "prod"] = "dev"
    app_base_url: str = "http://localhost:8000"
    log_level: str = "INFO"
    token_store_path: str = ".tokens/example_token.json"

    # Caller-auth: comma-separated list of X-API-Key values our own surface
    # accepts. Empty => the surface is unguarded (dev convenience); see
    # ``app.routers.deps.require_api_key``.
    api_keys: str = ""

    # Provider-generic connection settings. ``example_api_base`` is a harmless
    # placeholder so the app boots offline; the client id/secret are optional
    # here and validated at use-time (``require_credentials``).
    example_api_base: str = "https://api.example.com/v1"
    example_client_id: str = ""
    example_client_secret: str = ""

    @property
    def api_key_set(self) -> set[str]:
        """Configured caller API keys as a set, ignoring blanks."""
        return {key.strip() for key in self.api_keys.split(",") if key.strip()}

    @property
    def callback_path(self) -> str:
        """Path of the provider OAuth callback route, relative to the service root."""
        return f"{API_PREFIX}/auth/callback"

    @property
    def redirect_uri(self) -> str:
        """Effective provider redirect URI, derived from ``APP_BASE_URL``."""
        return f"{self.app_base_url.rstrip('/')}{self.callback_path}"

    @property
    def has_credentials(self) -> bool:
        """True when both the provider client id and secret are configured."""
        return bool(self.example_client_id and self.example_client_secret)

    def require_credentials(self) -> None:
        """Fail fast if provider credentials are missing.

        Called at provider use-time only (never at import/boot). Raises
        ``RuntimeError`` naming the missing environment variable(s) so the
        operator knows exactly what to set.
        """
        missing: list[str] = []
        if not self.example_client_id:
            missing.append("EXAMPLE_CLIENT_ID")
        if not self.example_client_secret:
            missing.append("EXAMPLE_CLIENT_SECRET")
        if missing:
            raise RuntimeError(
                "Missing required provider credential(s): "
                f"{', '.join(missing)}. Set them in your .env file "
                "(see .env.example) before making a provider call."
            )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
