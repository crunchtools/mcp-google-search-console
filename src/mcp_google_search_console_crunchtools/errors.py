"""Safe error types that can be shown to users.

This module defines exception classes that are safe to expose to MCP clients.
Internal errors should be caught and converted to UserError before propagating.
"""

import os

SAFE_ID_MAX_LENGTH = 200


class UserError(Exception):
    """Base class for safe errors that can be shown to users.

    All error messages in UserError subclasses must be carefully crafted
    to avoid leaking sensitive information like OAuth tokens or internal paths.
    """

    pass


class ConfigurationError(UserError):
    """Error in server configuration."""

    pass


class SearchConsoleApiError(UserError):
    """Error from Google Search Console API.

    The message is sanitized to remove any potential token references.
    """

    def __init__(self, code: int, message: str) -> None:
        for env_var in ("GSC_CLIENT_SECRET", "GSC_REFRESH_TOKEN", "GSC_CLIENT_ID"):
            secret = os.environ.get(env_var, "")
            if secret:
                message = message.replace(secret, "***")
        super().__init__(f"Search Console API error {code}: {message}")


class SiteNotFoundError(UserError):
    """Site not found or not accessible."""

    def __init__(self, identifier: str) -> None:
        if len(identifier) > SAFE_ID_MAX_LENGTH:
            safe_id = identifier[:SAFE_ID_MAX_LENGTH] + "..."
        else:
            safe_id = identifier
        super().__init__(f"Site not found or not accessible: {safe_id}")


class PermissionDeniedError(UserError):
    """Permission denied for the requested operation."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Permission denied: {detail}")


class RateLimitError(UserError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int | None = None) -> None:
        msg = "Rate limit exceeded."
        if retry_after:
            msg += f" Retry after {retry_after} seconds."
        super().__init__(msg)


class ValidationError(UserError):
    """Input validation error."""

    pass


class AuthRequiredError(UserError):
    """OAuth credentials are missing or expired.

    The message includes the URL the user should visit to re-authenticate.
    """

    def __init__(self, auth_url: str) -> None:
        super().__init__(
            f"OAuth credentials expired or missing. Re-authenticate by visiting: {auth_url}"
        )
