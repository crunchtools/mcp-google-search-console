"""Secure configuration handling.

This module handles all configuration including the sensitive OAuth credentials.
Tokens are stored as SecretStr to prevent accidental logging.
"""

import logging
import os
from urllib.parse import urlsplit

from pydantic import SecretStr

from .errors import ConfigurationError

logger = logging.getLogger(__name__)

TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
WEBMASTERS_BASE_URL = "https://www.googleapis.com/webmasters/v3"
INSPECTION_BASE_URL = "https://searchconsole.googleapis.com/v1"


def resource_server_enabled() -> bool:
    """Whether gateway-brokered resource-server mode is on (RT #1606).

    Read on its own so the server can decide whether to mount the auth
    provider without constructing a full Config (which needs credentials).
    """
    return os.environ.get("GSC_RESOURCE_SERVER", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


class Config:
    """Secure configuration handling.

    OAuth credentials are stored as SecretStr and should only be accessed
    via properties when actually needed for token exchange.
    """

    def __init__(self) -> None:
        """Initialize configuration from environment variables.

        Raises:
            ConfigurationError: If required environment variables are missing.
        """
        client_id = os.environ.get("GSC_CLIENT_ID")
        if not client_id:
            raise ConfigurationError(
                "GSC_CLIENT_ID environment variable required. "
                "Set this to your Google Cloud OAuth client ID."
            )

        client_secret = os.environ.get("GSC_CLIENT_SECRET")
        if not client_secret:
            raise ConfigurationError(
                "GSC_CLIENT_SECRET environment variable required. "
                "Set this to your Google Cloud OAuth client secret."
            )

        refresh_token = os.environ.get("GSC_REFRESH_TOKEN")

        self._client_id = SecretStr(client_id)
        self._client_secret = SecretStr(client_secret)
        self._refresh_token = SecretStr(refresh_token) if refresh_token else None
        self._credentials_dir = os.environ.get("GSC_CREDENTIALS_DIR", "/data")
        self._redirect_uri = os.environ.get("GSC_OAUTH_REDIRECT_URI", "")
        # Resource-server mode (RT #1606): when on, this server validates a
        # gateway-injected Google bearer per request instead of self-authing.
        # Default off keeps the standalone self-auth flow unchanged.
        self._resource_server = resource_server_enabled()
        base_url = os.environ.get("GSC_BASE_URL", "").strip()
        if self._resource_server:
            if not base_url:
                raise ConfigurationError(
                    "GSC_BASE_URL is required when GSC_RESOURCE_SERVER is set. "
                    "Use the ORIGIN the gateway dials, with no path, e.g. http://mcp-gsc:8017"
                )
            parts = urlsplit(base_url)
            if not parts.scheme or not parts.netloc or parts.path not in ("", "/"):
                raise ConfigurationError(
                    "GSC_BASE_URL must be an origin with no path, e.g. http://mcp-gsc:8017 "
                    f"(got {base_url!r}). FastMCP appends the MCP path itself."
                )
            base_url = f"{parts.scheme}://{parts.netloc}"
        self._base_url = base_url

        if not refresh_token:
            logger.info("No GSC_REFRESH_TOKEN set; will use file-based credentials or OAuth flow")
        logger.info("Configuration loaded successfully")

    @property
    def client_id(self) -> str:
        """Get OAuth client ID."""
        return self._client_id.get_secret_value()

    @property
    def client_secret(self) -> str:
        """Get OAuth client secret."""
        return self._client_secret.get_secret_value()

    @property
    def refresh_token(self) -> str | None:
        """Get OAuth refresh token from env var, or None."""
        if self._refresh_token is None:
            return None
        return self._refresh_token.get_secret_value()

    @property
    def credentials_dir(self) -> str:
        """Directory for file-based credential storage."""
        return self._credentials_dir

    @property
    def resource_server(self) -> bool:
        """True when the gateway injects the bearer (RT #1606); self-auth is bypassed."""
        return self._resource_server

    @property
    def base_url(self) -> str:
        """Origin the gateway dials (resource-server mode only), e.g. http://mcp-gsc:8017."""
        return self._base_url

    @property
    def redirect_uri(self) -> str:
        """OAuth2 redirect URI for browser-based auth flow."""
        return self._redirect_uri

    @property
    def auth_url(self) -> str:
        """URL the user should visit to start the OAuth flow."""
        if self._redirect_uri:
            return self._redirect_uri.rsplit("/oauth2callback", 1)[0] + "/auth"
        return "/auth"

    @property
    def token_endpoint(self) -> str:
        """Google OAuth2 token endpoint."""
        return TOKEN_ENDPOINT

    @property
    def webmasters_base_url(self) -> str:
        """Base URL for Sites, Analytics, and Sitemaps APIs."""
        return WEBMASTERS_BASE_URL

    @property
    def inspection_base_url(self) -> str:
        """Base URL for URL Inspection API."""
        return INSPECTION_BASE_URL

    def __repr__(self) -> str:
        """Safe repr that never exposes credentials."""
        return "Config(client_id=***, client_secret=***, refresh_token=***)"

    def __str__(self) -> str:
        """Safe str that never exposes credentials."""
        return "Config(client_id=***, client_secret=***, refresh_token=***)"


_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance.

    This function lazily initializes the configuration on first call.
    Subsequent calls return the same instance.

    Returns:
        The global Config instance.

    Raises:
        ConfigurationError: If configuration is invalid.
    """
    global _config
    if _config is None:
        _config = Config()
    return _config
