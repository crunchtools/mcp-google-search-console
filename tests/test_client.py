"""The outbound HTTP contract (constitution v1.36.0, MCP Server profile Layer 3).

Every test drives a real `httpx.AsyncClient` over a `MockTransport`. That is the
point: the agent string is set by the client and the ceiling is enforced while
the client reads, so an `AsyncMock` standing in for the client would mock away
the behaviour under test.
"""

import time
from collections.abc import AsyncIterator, Callable, Generator
from contextlib import contextmanager
from importlib.metadata import version
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from mcp_google_search_console_crunchtools import transport
from mcp_google_search_console_crunchtools.client import SearchConsoleClient
from mcp_google_search_console_crunchtools.errors import SearchConsoleApiError

Handler = Callable[[httpx.Request], httpx.Response]

SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"


async def _chunks(chunk: bytes, times: int) -> AsyncIterator[bytes]:
    """A chunked body, which carries no content-length -- what a header check misses."""
    for _ in range(times):
        yield chunk


@contextmanager
def _serving(handler: Handler) -> Generator[None, None, None]:
    """Run every client in the process on a MockTransport, token exchange bypassed."""
    real = httpx.AsyncClient

    def factory(**kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)
        return real(transport=httpx.MockTransport(handler), **kwargs)

    async def _fake_ensure_token(self: Any) -> None:
        self._access_token = "test_access_token"
        self._token_expires_at = time.time() + 3600

    with (
        patch.object(SearchConsoleClient, "_ensure_token", _fake_ensure_token),
        patch("httpx.AsyncClient", factory),
    ):
        yield


class TestUserAgent:
    """A request says what it is, and the version cannot drift from the release."""

    @pytest.mark.asyncio
    async def test_outgoing_request_names_the_product_and_version(self) -> None:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.headers["User-Agent"])
            return httpx.Response(200, json={"siteEntry": []})

        with _serving(handler):
            await SearchConsoleClient()._request("GET", SITES_URL)

        expected = (
            f"mcp-google-search-console-crunchtools/"
            f"{version('mcp-google-search-console-crunchtools')} "
            "(+https://github.com/crunchtools/mcp-google-search-console)"
        )
        assert seen == [expected]
        assert "python-httpx" not in seen[0]


class TestResponseCeiling:
    """The cap is enforced while reading, not taken from a header."""

    @pytest.mark.asyncio
    async def test_chunked_body_over_the_cap_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No content-length at all: this is what a header check lets through."""
        monkeypatch.setattr(transport, "MAX_RESPONSE_SIZE", 4096)

        def handler(_request: httpx.Request) -> httpx.Response:
            response = httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=_chunks(b"x" * 1024, 16),
            )
            assert "content-length" not in response.headers
            return response

        with _serving(handler), pytest.raises(SearchConsoleApiError) as caught:
            await SearchConsoleClient()._request("GET", SITES_URL)

        # The whole message: a substring check against a URL literal is both a
        # weaker claim and what CodeQL flags as incomplete sanitization, and the
        # shape of this message IS the third MUST.
        assert str(caught.value) == (
            "Search Console API error 200: GET https://www.googleapis.com/webmasters/v3/sites "
            "(HTTP 200, application/json) sent over the 4096 byte limit"
        )

    @pytest.mark.asyncio
    async def test_a_single_oversized_chunk_is_refused_before_it_is_copied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`aiter_bytes()` does not promise small chunks: one can be the whole body.

        Measuring after the append would mean copying in exactly the response
        being refused, on the way to refusing it.
        """
        monkeypatch.setattr(transport, "MAX_RESPONSE_SIZE", 1024)

        def handler(_request: httpx.Request) -> httpx.Response:
            response = httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=_chunks(b"x" * 8192, 1),
            )
            assert "content-length" not in response.headers
            return response

        with _serving(handler), pytest.raises(SearchConsoleApiError) as caught:
            await SearchConsoleClient()._request("GET", SITES_URL)

        assert "sent over the 1024 byte limit" in str(caught.value)

    @pytest.mark.asyncio
    async def test_declared_length_over_the_cap_is_rejected_early(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(transport, "MAX_RESPONSE_SIZE", 64)

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, headers={"content-type": "application/json"}, content=b"x" * 128
            )

        with _serving(handler), pytest.raises(SearchConsoleApiError) as caught:
            await SearchConsoleClient()._request("GET", SITES_URL)

        assert str(caught.value) == (
            "Search Console API error 200: GET https://www.googleapis.com/webmasters/v3/sites "
            "(HTTP 200, application/json) declared 128 bytes, over the 64 byte limit"
        )

    @pytest.mark.asyncio
    async def test_a_malformed_content_length_does_not_crash(self) -> None:
        """`int()` on an unchecked header is a ValueError escaping as itself."""

        def handler(_request: httpx.Request) -> httpx.Response:
            response = httpx.Response(200, json={"siteEntry": []})
            response.headers["content-length"] = "not-a-number"
            return response

        with _serving(handler):
            result = await SearchConsoleClient()._request("GET", SITES_URL)

        assert result == {"siteEntry": []}


class TestErrorNamesTheSite:
    """RT #1596: the message has to say which site answered, and with what."""

    @pytest.mark.asyncio
    async def test_non_json_body_names_url_status_type_and_a_snippet(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "text/html; charset=UTF-8"},
                text="<!DOCTYPE html><title>Just a moment...</title>",
            )

        with _serving(handler), pytest.raises(SearchConsoleApiError) as caught:
            await SearchConsoleClient()._request("GET", SITES_URL)

        assert str(caught.value) == (
            "Search Console API error 200: GET https://www.googleapis.com/webmasters/v3/sites "
            "(HTTP 200, text/html; charset=UTF-8) is not JSON "
            "(Expecting value: line 1 column 1 (char 0)): "
            "<!DOCTYPE html><title>Just a moment...</title>"
        )

    @pytest.mark.asyncio
    async def test_a_challenge_page_on_an_error_status_is_quoted(self) -> None:
        """A 500 whose body is HTML used to arrive as "Unknown error"."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                500, headers={"content-type": "text/html"}, text="Attention Required!"
            )

        with _serving(handler), pytest.raises(SearchConsoleApiError) as caught:
            await SearchConsoleClient()._request("GET", SITES_URL)

        assert str(caught.value) == (
            "Search Console API error 500: GET https://www.googleapis.com/webmasters/v3/sites "
            "(HTTP 500, text/html) is not JSON: Attention Required!"
        )


class TestErrorRedaction:
    """Layer 1 applies to an error message: the URL in it carries no secret."""

    @pytest.mark.asyncio
    async def test_userinfo_and_credential_params_are_redacted(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, headers={"content-type": "text/html"}, text="nope")

        with _serving(handler), pytest.raises(SearchConsoleApiError) as caught:
            await SearchConsoleClient()._request(
                "GET",
                "https://bot:sekrit@www.googleapis.com/webmasters/v3/sites",
                params={"access_token": "ya29-secret", "siteUrl": "https://example.com/"},
            )

        # The whole message, because what it leaves OUT is the point and a
        # substring check cannot show an absence. `%2A%2A%2A` is the redaction
        # percent-encoded by httpx; the host, path and real parameter survive.
        assert str(caught.value) == (
            "Search Console API error 500: GET https://www.googleapis.com/webmasters/v3/sites"
            "?access_token=%2A%2A%2A&siteUrl=https%3A%2F%2Fexample.com%2F "
            "(HTTP 500, text/html) is not JSON: nope"
        )
        assert "sekrit" not in str(caught.value)
        assert "ya29-secret" not in str(caught.value)


class TestTransportFailures:
    """Every call shares one send path, so its failure branches matter."""

    @pytest.mark.asyncio
    async def test_timeout_becomes_an_api_error(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("timed out")

        with _serving(handler), pytest.raises(SearchConsoleApiError) as caught:
            await SearchConsoleClient()._request("GET", SITES_URL)

        assert str(caught.value) == "Search Console API error 0: Request timeout: timed out"

    @pytest.mark.asyncio
    async def test_connect_failure_becomes_an_api_error(self) -> None:
        """A non-timeout transport failure takes the other branch, not the bare httpx error."""

        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("name or service not known")

        with _serving(handler), pytest.raises(SearchConsoleApiError) as caught:
            await SearchConsoleClient()._request("GET", SITES_URL)

        assert str(caught.value) == (
            "Search Console API error 0: Request failed: name or service not known"
        )
