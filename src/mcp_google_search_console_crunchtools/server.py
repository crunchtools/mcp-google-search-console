"""FastMCP server setup for Google Search Console MCP.

This module creates and configures the MCP server with all tools,
plus OAuth2 browser-based authentication routes.
"""

import logging
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from .auth import build_consent_url, exchange_code, save_credentials, validate_state
from .config import get_config
from .tools import (
    add_site,
    delete_site,
    delete_sitemap,
    get_site,
    get_sitemap,
    inspect_url,
    list_sitemaps,
    list_sites,
    query_search_analytics,
    submit_sitemap,
)

logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="mcp-google-search-console-crunchtools",
    version="0.1.0",
    instructions=(
        "Secure MCP server for Google Search Console. "
        "Query search analytics (clicks, impressions, CTR, position), "
        "manage sitemaps, inspect URL indexing status, and manage site properties."
    ),
)


@mcp.tool()
async def list_sites_tool() -> dict[str, Any]:
    """List all Search Console properties accessible by the authenticated user.

    Returns:
        List of site entries with permission levels and site URLs
    """
    return await list_sites()


@mcp.tool()
async def get_site_tool(
    site_url: str,
) -> dict[str, Any]:
    """Get details for a specific Search Console property.

    Args:
        site_url: Site URL (e.g., "https://example.com/") or domain property
                  (e.g., "sc-domain:example.com")

    Returns:
        Site details including permission level
    """
    return await get_site(site_url=site_url)


@mcp.tool()
async def add_site_tool(
    site_url: str,
) -> dict[str, Any]:
    """Add a site to Search Console.

    Args:
        site_url: Site URL (e.g., "https://example.com/") or domain property

    Returns:
        Confirmation of addition
    """
    return await add_site(site_url=site_url)


@mcp.tool()
async def delete_site_tool(
    site_url: str,
) -> dict[str, Any]:
    """Remove a site from Search Console.

    Args:
        site_url: Site URL to remove

    Returns:
        Confirmation of deletion
    """
    return await delete_site(site_url=site_url)


@mcp.tool()
async def query_search_analytics_tool(
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: list[str] | None = None,
    search_type: str = "web",
    aggregation_type: str = "auto",
    row_limit: int = 1000,
    start_row: int = 0,
    dimension_filter_groups: list[dict[str, list[dict[str, str]]]] | None = None,
    data_state: str = "final",
) -> dict[str, Any]:
    """Query search traffic data with filters and dimensions.

    Returns clicks, impressions, CTR, and average position grouped by
    the requested dimensions. Use this to analyze search performance
    for specific pages, queries, countries, devices, or date ranges.

    Args:
        site_url: Site URL or domain property
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        dimensions: Dimensions to group by (date, query, page, country,
                    device, searchAppearance). Multiple allowed.
        search_type: Search type filter (web, image, video, news,
                     googleNews, discover). Default: web
        aggregation_type: How to aggregate results (auto, byPage,
                          byProperty). Default: auto
        row_limit: Maximum rows to return, 1-25000 (default: 1000)
        start_row: Zero-based row offset for pagination (default: 0)
        dimension_filter_groups: Filter groups to narrow results
        data_state: Data freshness (final, all). Default: final

    Returns:
        Search analytics data with rows containing clicks, impressions,
        ctr, and position values
    """
    return await query_search_analytics(
        site_url=site_url,
        start_date=start_date,
        end_date=end_date,
        dimensions=dimensions,
        search_type=search_type,
        aggregation_type=aggregation_type,
        row_limit=row_limit,
        start_row=start_row,
        dimension_filter_groups=dimension_filter_groups,
        data_state=data_state,
    )


@mcp.tool()
async def list_sitemaps_tool(
    site_url: str,
) -> dict[str, Any]:
    """List all sitemaps submitted for a site.

    Args:
        site_url: Site URL or domain property

    Returns:
        List of sitemaps with status, type, and submission metadata
    """
    return await list_sitemaps(site_url=site_url)


@mcp.tool()
async def get_sitemap_tool(
    site_url: str,
    feedpath: str,
) -> dict[str, Any]:
    """Get details for a specific sitemap.

    Args:
        site_url: Site URL or domain property
        feedpath: Full URL of the sitemap (e.g., "https://example.com/sitemap.xml")

    Returns:
        Sitemap details including type, submission time, and index status
    """
    return await get_sitemap(site_url=site_url, feedpath=feedpath)


@mcp.tool()
async def submit_sitemap_tool(
    site_url: str,
    feedpath: str,
) -> dict[str, Any]:
    """Submit a sitemap for crawling.

    Args:
        site_url: Site URL or domain property
        feedpath: Full URL of the sitemap to submit (e.g., "https://example.com/sitemap.xml")

    Returns:
        Confirmation of submission
    """
    return await submit_sitemap(site_url=site_url, feedpath=feedpath)


@mcp.tool()
async def delete_sitemap_tool(
    site_url: str,
    feedpath: str,
) -> dict[str, Any]:
    """Remove a sitemap from Search Console.

    Args:
        site_url: Site URL or domain property
        feedpath: Full URL of the sitemap to delete

    Returns:
        Confirmation of deletion
    """
    return await delete_sitemap(site_url=site_url, feedpath=feedpath)


@mcp.tool()
async def inspect_url_tool(
    inspection_url: str,
    site_url: str,
    language_code: str = "en-US",
) -> dict[str, Any]:
    """Inspect a URL's index status in Google Search.

    Returns detailed information about how Google sees a URL including
    index coverage, crawl status, mobile usability, and rich results.

    Args:
        inspection_url: The fully-qualified URL to inspect
                        (e.g., "https://example.com/page")
        site_url: The Search Console property this URL belongs to
        language_code: Language code for localized results (default: en-US)

    Returns:
        URL inspection result with indexing, crawling, and mobile usability data
    """
    return await inspect_url(
        inspection_url=inspection_url,
        site_url=site_url,
        language_code=language_code,
    )


@mcp.custom_route("/auth", methods=["GET"])
async def auth_redirect(_request: Request) -> Response:
    """Redirect the user to Google's OAuth consent screen."""
    config = get_config()
    if not config.redirect_uri:
        return HTMLResponse(
            "<h2>OAuth not configured</h2>"
            "<p>Set GSC_OAUTH_REDIRECT_URI to enable browser-based authentication.</p>",
            status_code=500,
        )
    url = build_consent_url(config.client_id, config.redirect_uri)
    return RedirectResponse(url=url)


@mcp.custom_route("/oauth2callback", methods=["GET"])
async def oauth_callback(request: Request) -> Response:
    """Handle the OAuth2 callback from Google."""
    error = request.query_params.get("error")
    if error:
        return HTMLResponse(
            f"<h2>Authentication failed</h2><p>Google returned: {error}</p>",
            status_code=400,
        )

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        return HTMLResponse(
            "<h2>Invalid callback</h2><p>Missing code or state parameter.</p>",
            status_code=400,
        )

    if not validate_state(state):
        return HTMLResponse(
            "<h2>Invalid state</h2><p>CSRF state mismatch or expired. Try again from /auth.</p>",
            status_code=400,
        )

    config = get_config()
    try:
        tokens = await exchange_code(
            config.client_id,
            config.client_secret,
            code,
            config.redirect_uri,
        )
    except RuntimeError as e:
        logger.exception("Token exchange failed")
        return HTMLResponse(
            f"<h2>Token exchange failed</h2><p>{e}</p>",
            status_code=500,
        )

    save_credentials(config.credentials_dir, tokens)

    from . import client as client_mod

    if client_mod._client is not None:
        client_mod._client._access_token = None
        client_mod._client._token_expires_at = 0.0

    return HTMLResponse(
        "<h2>Authentication complete</h2>"
        "<p>Google Search Console credentials saved. You can close this window.</p>"
    )
