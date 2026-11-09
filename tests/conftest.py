"""Shared test fixtures for mcp-google-search-console tests."""

import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest


@pytest.fixture(autouse=True)
def _reset_singletons() -> Generator[None, None, None]:
    """Reset client and config singletons between tests."""
    os.environ["GSC_CLIENT_ID"] = "test_client_id"
    os.environ["GSC_CLIENT_SECRET"] = "test_client_secret"
    os.environ["GSC_REFRESH_TOKEN"] = "test_refresh_token"

    yield

    import mcp_google_search_console_crunchtools.client as client_module
    import mcp_google_search_console_crunchtools.config as config_module

    client_module._client = None
    config_module._config = None

    os.environ.pop("GSC_CLIENT_ID", None)
    os.environ.pop("GSC_CLIENT_SECRET", None)
    os.environ.pop("GSC_REFRESH_TOKEN", None)


def _mock_response(
    status_code: int = 200,
    json_data: Any = None,
    text: str = "",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Build a mock httpx.Response."""
    if json_data is not None:
        content = json.dumps(json_data).encode()
        content_type = "application/json"
    else:
        content = text.encode()
        content_type = "text/plain"

    resp_headers = {"content-type": content_type}
    if headers:
        resp_headers.update(headers)

    return httpx.Response(
        status_code=status_code,
        content=content,
        headers=resp_headers,
        request=httpx.Request("GET", "https://example.com"),
    )


@contextmanager
def _patch_client(
    response: httpx.Response,
) -> Generator[list[httpx.Request], None, None]:
    """Answer every API call with one response, and collect the requests sent.

    A real `httpx.AsyncClient` over a `MockTransport`, not an AsyncMock standing
    in for the client: the client is what sets the User-Agent and what reads the
    body in bounded pieces, so mocking its methods would mock away the behaviour
    the contract exists to hold (constitution v1.36.0, Layer 3). OAuth token
    exchange is still bypassed by patching `_ensure_token`.

    Yields the `httpx.Request` objects as they go out, which is what a caller
    asserting on method and URL wants.
    """
    sent: list[httpx.Request] = []
    # Content-length is dropped so httpx recomputes it for the body it is given.
    headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        # A fresh response each time: a streamed body can be read once, and the
        # error messages under test name `response.request.url`, which has to be
        # the URL the client actually built rather than the template's placeholder.
        return httpx.Response(
            response.status_code, headers=headers, content=response.content, request=request
        )

    real = httpx.AsyncClient

    def factory(**kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)
        return real(transport=httpx.MockTransport(handler), **kwargs)

    with (
        patch(
            "mcp_google_search_console_crunchtools.client.SearchConsoleClient._ensure_token",
            new_callable=AsyncMock,
        ),
        patch("httpx.AsyncClient", factory),
    ):
        yield sent
