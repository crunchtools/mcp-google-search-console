"""Google Search Console API client with OAuth2 token management.

This module provides a secure async HTTP client for the Search Console API.
Handles automatic OAuth2 token refresh and dual base URL routing.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from .auth import load_credentials, save_credentials
from .config import get_config
from .errors import (
    AuthRequiredError,
    PermissionDeniedError,
    RateLimitError,
    SearchConsoleApiError,
    SiteNotFoundError,
)
from .transport import (
    HEADERS,
    REQUEST_TIMEOUT,
    body_snippet,
    send_capped,
    where,
)

logger = logging.getLogger(__name__)

TOKEN_REFRESH_BUFFER = 60


def _parse_error_body(response: httpx.Response, body: bytes) -> str:
    """Extract a human-readable error message from an API error response.

    Falls back to naming the request and quoting the body, which is what tells
    a WAF challenge or a consent screen apart from the API answering badly.
    """
    try:
        error_body = json.loads(body)
    except ValueError:
        return f"{where(response)} is not JSON: {body_snippet(body)}"

    if not isinstance(error_body, dict):
        return str(error_body)

    error_detail = error_body.get("error", {})
    if isinstance(error_detail, dict):
        return str(error_detail.get("message", str(error_detail)))
    if isinstance(error_detail, str):
        return error_detail
    return str(error_body)


class SearchConsoleClient:
    """Async HTTP client for Google Search Console API.

    Security features:
    - OAuth2 token refresh with expiry tracking
    - Bearer token auth (never in URL)
    - TLS certificate validation (httpx default)
    - Request timeout enforcement
    - Response size limits
    - Dual base URL routing (webmasters vs inspection)
    """

    def __init__(self) -> None:
        """Initialize the Search Console client."""
        self._config = get_config()
        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def _get_refresh_token(self) -> str:
        """Get refresh token from file-based credentials or env var fallback."""
        creds = load_credentials(self._config.credentials_dir)
        if creds and creds.get("refresh_token"):
            expiry_str = creds.get("expiry")
            if expiry_str and creds.get("access_token"):
                try:
                    expiry = datetime.fromisoformat(expiry_str).timestamp()
                    if time.time() < expiry - TOKEN_REFRESH_BUFFER:
                        self._access_token = creds["access_token"]
                        self._token_expires_at = expiry
                except (ValueError, OSError) as exc:
                    logger.debug("Ignoring unusable cached access token, refreshing: %s", exc)
            return str(creds["refresh_token"])

        if self._config.refresh_token:
            return self._config.refresh_token

        raise AuthRequiredError(self._config.auth_url)

    async def _ensure_token(self) -> None:
        """Exchange refresh_token for access_token, cache until expiry."""
        if self._access_token and time.time() < self._token_expires_at - TOKEN_REFRESH_BUFFER:
            return

        refresh_token = self._get_refresh_token()
        if self._access_token and time.time() < self._token_expires_at - TOKEN_REFRESH_BUFFER:
            return

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(REQUEST_TIMEOUT), headers=HEADERS
        ) as token_client:
            request = token_client.build_request(
                "POST",
                self._config.token_endpoint,
                data={
                    "client_id": self._config.client_id,
                    "client_secret": self._config.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response, body = await send_capped(token_client, request)

        if response.status_code in (400, 401):
            logger.error("Refresh token expired. Re-authenticate at: %s", self._config.auth_url)
            raise AuthRequiredError(self._config.auth_url)

        if not response.is_success:
            raise SearchConsoleApiError(
                response.status_code,
                f"Token refresh failed: {where(response)} returned {body_snippet(body)}",
            )

        try:
            token_data = json.loads(body)
        except ValueError as e:
            raise SearchConsoleApiError(
                response.status_code,
                f"Token refresh returned no JSON: {where(response)} sent {body_snippet(body)}",
            ) from e
        self._access_token = token_data["access_token"]
        self._token_expires_at = time.time() + token_data.get("expires_in", 3600)
        logger.debug("OAuth2 token refreshed, expires in %ds", token_data.get("expires_in", 3600))

        expiry_ts = datetime.fromtimestamp(self._token_expires_at, tz=timezone.utc).isoformat()
        new_refresh = token_data.get("refresh_token", refresh_token)
        save_credentials(
            self._config.credentials_dir,
            {
                "access_token": self._access_token,
                "refresh_token": new_refresh,
                "token_uri": self._config.token_endpoint,
                "scope": "https://www.googleapis.com/auth/webmasters",
                "expiry": expiry_ts,
            },
        )

    async def _bearer(self) -> str:
        """The access token for THIS request.

        In resource-server mode (RT #1606) the gateway injects a Google bearer per
        request; it is read from the request context, bound to this task, so two
        profiles' tokens can never cross. Otherwise the self-managed refresh-token
        grant is used. Only this method ever reaches a credential; the shared
        client below carries no default Authorization header.
        """
        if self._config.resource_server:
            from fastmcp.server.dependencies import get_access_token

            token = get_access_token()
            if token is None:
                raise PermissionDeniedError("No bearer token on the request")
            return token.token
        await self._ensure_token()
        if self._access_token is None:  # _ensure_token sets it or raises; defensive
            raise AuthRequiredError(self._config.auth_url)
        return self._access_token

    async def _get_client(self) -> httpx.AsyncClient:
        """The shared connection pool. It carries no credential; every request sets
        its own Authorization header from _bearer()."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"Content-Type": "application/json", **HEADERS},
                timeout=httpx.Timeout(REQUEST_TIMEOUT),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _send(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        params: dict[str, Any] | None,
        json_data: dict[str, Any] | None,
        token: str,
    ) -> tuple[httpx.Response, bytes]:
        """Send one request with a per-request bearer and return its bounded body."""
        request = client.build_request(
            method,
            url,
            params=params,
            json=json_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            return await send_capped(client, request)
        except httpx.TimeoutException as e:
            raise SearchConsoleApiError(0, f"Request timeout: {e}") from e
        except httpx.RequestError as e:
            raise SearchConsoleApiError(0, f"Request failed: {e}") from e

    async def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an API request with error handling and token retry.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Full API URL
            params: Query parameters
            json_data: JSON body data

        Returns:
            API response data

        Raises:
            SearchConsoleApiError: On API errors
            RateLimitError: On rate limiting
            PermissionDeniedError: On authorization failures
        """
        client = await self._get_client()
        token = await self._bearer()
        logger.debug("API request: %s %s", method, url)

        response, body = await self._send(client, method, url, params, json_data, token)

        # Self-auth only: a stale cached access token is cleared and refreshed once.
        # In resource-server mode the gateway owns the token and its own retry path
        # refreshes the grant; a 401 here is raised straight rather than retried.
        if response.status_code == 401 and not self._config.resource_server:
            self._access_token = None
            self._token_expires_at = 0.0
            token = await self._bearer()
            response, body = await self._send(client, method, url, params, json_data, token)

        if not response.is_success:
            self._handle_error_response(response, body)

        if response.status_code == 204:
            return {"status": "deleted" if method == "DELETE" else "success"}

        return self._parse_response(response, body)

    def _parse_response(self, response: httpx.Response, body: bytes) -> dict[str, Any]:
        """Parse a successful JSON response."""
        try:
            parsed = json.loads(body)
        except ValueError as e:
            raise SearchConsoleApiError(
                response.status_code,
                f"{where(response)} is not JSON ({e}): {body_snippet(body)}",
            ) from e

        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"items": parsed}
        return {"data": parsed}

    def _handle_error_response(self, response: httpx.Response, body: bytes) -> None:
        """Handle error responses from the API."""
        error_msg = _parse_error_body(response, body)

        match response.status_code:
            case 401:
                raise PermissionDeniedError("Invalid or expired OAuth2 credentials")
            case 403:
                raise PermissionDeniedError(error_msg)
            case 404:
                raise SiteNotFoundError(error_msg)
            case 429:
                retry_after = response.headers.get("retry-after")
                raise RateLimitError(int(retry_after) if retry_after else None)
            case _:
                raise SearchConsoleApiError(response.status_code, error_msg)

    def _webmasters_url(self, path: str) -> str:
        """Build a full URL for the webmasters API."""
        return f"{self._config.webmasters_base_url}{path}"

    def _inspection_url(self, path: str) -> str:
        """Build a full URL for the inspection API."""
        return f"{self._config.inspection_base_url}{path}"

    async def webmasters_get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make a GET request to the webmasters API."""
        return await self._request("GET", self._webmasters_url(path), params=params)

    async def webmasters_post(
        self,
        path: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a POST request to the webmasters API."""
        return await self._request("POST", self._webmasters_url(path), json_data=json_data)

    async def webmasters_put(
        self,
        path: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a PUT request to the webmasters API."""
        return await self._request("PUT", self._webmasters_url(path), json_data=json_data)

    async def webmasters_delete(self, path: str) -> dict[str, Any]:
        """Make a DELETE request to the webmasters API."""
        return await self._request("DELETE", self._webmasters_url(path))

    async def inspection_post(
        self,
        path: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a POST request to the inspection API."""
        return await self._request("POST", self._inspection_url(path), json_data=json_data)


_client: SearchConsoleClient | None = None


def get_client() -> SearchConsoleClient:
    """Get the global Search Console client instance."""
    global _client
    if _client is None:
        _client = SearchConsoleClient()
    return _client
