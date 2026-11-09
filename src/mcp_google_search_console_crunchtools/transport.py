"""What every outbound request in this server has in common.

The contract is constitution v1.36.0, MCP Server profile Layer 3: a request says
what it is, a response is read with a ceiling enforced while reading, and an
error says which site answered and with what. It lives here rather than in
`client.py` because `auth.py` talks to Google's token endpoint on its own, and
two copies of this would mean one of them drifting.
"""

from importlib.metadata import version

import httpx

from .errors import SearchConsoleApiError

MAX_RESPONSE_SIZE = 10 * 1024 * 1024
REQUEST_TIMEOUT = 30.0

# Identify this client by name. httpx otherwise sends `python-httpx/<version>`,
# which bot protection answers with an HTML challenge page instead of the API --
# the failure that cost an afternoon on mcp-wordpress (RT #1596). The version
# comes from installed package metadata so it cannot drift from pyproject.toml.
USER_AGENT = (
    f"mcp-google-search-console-crunchtools/{version('mcp-google-search-console-crunchtools')} "
    "(+https://github.com/crunchtools/mcp-google-search-console)"
)

HEADERS = {"User-Agent": USER_AGENT}

# How much of a body to quote back in an error. Enough to recognise a WAF page,
# a consent screen or a proxy error; short enough to stay readable.
BODY_SNIPPET_CHARS = 200

# Query parameters whose value is a secret rather than part of the request.
# Google's OAuth endpoints take several of these in a query string.
REDACTED_PARAMS = frozenset(
    {"access_token", "client_secret", "code", "id_token", "refresh_token", "token"}
)


def safe_url(url: httpx.URL) -> httpx.URL:
    """A URL fit to appear in an error message (Layer 1).

    Userinfo goes first: it carries its secret before the path, where redacting
    query parameters never reaches it. The rest is redacted by name rather than
    dropped, because the path and the ordinary parameters are the diagnosis.
    """
    url = url.copy_with(userinfo=b"")
    for name in REDACTED_PARAMS & set(url.params):
        url = url.copy_set_param(name, "***")
    return url


def body_snippet(body: bytes) -> str:
    """A short, single-line excerpt of a response body, for an error message."""
    # Slice the bytes, then decode only that: a WAF page can be megabytes, and
    # decoding all of it to keep 200 characters copies it twice for nothing.
    # Four times the snippet is slack for the whitespace a collapse removes;
    # `replace` covers a multi-byte character the slice cut in half.
    prefix = body[: BODY_SNIPPET_CHARS * 4]
    collapsed = " ".join(prefix.decode("utf-8", errors="replace").split())
    if not collapsed:
        return "<empty body>"
    if len(collapsed) > BODY_SNIPPET_CHARS or len(body) > len(prefix):
        return collapsed[:BODY_SNIPPET_CHARS] + "..."
    return collapsed


def where(response: httpx.Response) -> str:
    """Which request a response answered, for an error message.

    The requested URL and not the configured one: a base that redirects returns
    a body from somewhere else entirely, and only the URL actually requested
    tells that apart from the API having answered badly.
    """
    return (
        f"{response.request.method} {safe_url(response.request.url)} "
        f"(HTTP {response.status_code}, {response.headers.get('content-type', 'no content-type')})"
    )


async def read_capped(response: httpx.Response) -> bytes:
    """Read the body, aborting as soon as it passes MAX_RESPONSE_SIZE.

    The cap is enforced while reading. A `content-length` check alone is not a
    ceiling: the header is optional, so a chunked reply carries none and walks
    straight past it. The header stays as an early reject, guarded so that a
    malformed value is an API error rather than an unhandled ValueError.
    """
    declared = response.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_RESPONSE_SIZE:
        raise SearchConsoleApiError(
            response.status_code,
            f"{where(response)} declared {declared} bytes, over the {MAX_RESPONSE_SIZE} byte limit",
        )
    # One growing buffer, not a list of chunks plus a full-size join: near the
    # ceiling the join holds both copies at once, which doubles the peak this
    # limit exists to bound. mcp-wordpress's `_read_body` is written this way.
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body += chunk
        if len(body) > MAX_RESPONSE_SIZE:
            raise SearchConsoleApiError(
                response.status_code,
                f"{where(response)} sent over the {MAX_RESPONSE_SIZE} byte limit",
            )
    return bytes(body)


async def send_capped(
    client: httpx.AsyncClient, request: httpx.Request
) -> tuple[httpx.Response, bytes]:
    """Send a request and return the response with its bounded body.

    One function so no call site can stream a response and forget to close it,
    or read it without the ceiling.
    """
    response = await client.send(request, stream=True)
    try:
        return response, await read_capped(response)
    finally:
        await response.aclose()
