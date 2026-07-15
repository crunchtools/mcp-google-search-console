"""Tests for MCP tools.

These tests verify tool behavior without making actual API calls.
All HTTP interactions are mocked via httpx.AsyncClient patching.
"""

import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from tests.conftest import _mock_response, _patch_client


class TestToolRegistration:
    """Tests to verify all tools are properly registered."""

    def test_server_has_tools(self) -> None:
        """Server should have all expected tools registered."""
        from mcp_google_search_console_crunchtools.server import mcp

        assert mcp is not None

    def test_imports(self) -> None:
        """All tool functions should be importable."""
        import mcp_google_search_console_crunchtools.tools as tools_mod
        from mcp_google_search_console_crunchtools.tools import __all__

        for name in __all__:
            func = getattr(tools_mod, name)
            assert callable(func), f"{name} is not callable"

    def test_tool_count(self) -> None:
        """Server should have exactly 10 tools registered."""
        from mcp_google_search_console_crunchtools.tools import __all__

        assert len(__all__) == 10


class TestErrorSafety:
    """Tests to verify error messages don't leak sensitive data."""

    def test_api_error_sanitizes_client_secret(self) -> None:
        """SearchConsoleApiError should sanitize secrets from messages."""
        from mcp_google_search_console_crunchtools.errors import SearchConsoleApiError

        os.environ["GSC_CLIENT_SECRET"] = "super_secret_value"

        try:
            error = SearchConsoleApiError(401, "Invalid secret: super_secret_value")
            assert "super_secret_value" not in str(error)
            assert "***" in str(error)
        finally:
            os.environ["GSC_CLIENT_SECRET"] = "test_client_secret"

    def test_api_error_sanitizes_refresh_token(self) -> None:
        """SearchConsoleApiError should sanitize refresh tokens from messages."""
        from mcp_google_search_console_crunchtools.errors import SearchConsoleApiError

        os.environ["GSC_REFRESH_TOKEN"] = "1//my_refresh_token"

        try:
            error = SearchConsoleApiError(401, "Token: 1//my_refresh_token")
            assert "1//my_refresh_token" not in str(error)
            assert "***" in str(error)
        finally:
            os.environ["GSC_REFRESH_TOKEN"] = "test_refresh_token"

    def test_site_not_found_truncates_long_urls(self) -> None:
        """SiteNotFoundError should truncate long identifiers."""
        from mcp_google_search_console_crunchtools.errors import SiteNotFoundError

        long_url = "https://example.com/" + "a" * 300
        error = SiteNotFoundError(long_url)
        error_str = str(error)

        assert long_url not in error_str
        assert "..." in error_str


class TestConfigSafety:
    """Tests for configuration security."""

    def test_config_repr_hides_credentials(self) -> None:
        """Config repr should never show credentials."""
        from mcp_google_search_console_crunchtools.config import Config

        config = Config()
        assert "test_client_id" not in repr(config)
        assert "test_client_secret" not in repr(config)
        assert "test_refresh_token" not in repr(config)
        assert "***" in repr(config)

    def test_config_requires_client_id(self) -> None:
        """Config should require GSC_CLIENT_ID."""
        from mcp_google_search_console_crunchtools.config import Config
        from mcp_google_search_console_crunchtools.errors import ConfigurationError

        saved = os.environ.pop("GSC_CLIENT_ID")

        try:
            with pytest.raises(ConfigurationError, match="GSC_CLIENT_ID"):
                Config()
        finally:
            os.environ["GSC_CLIENT_ID"] = saved

    def test_config_requires_client_secret(self) -> None:
        """Config should require GSC_CLIENT_SECRET."""
        from mcp_google_search_console_crunchtools.config import Config
        from mcp_google_search_console_crunchtools.errors import ConfigurationError

        saved = os.environ.pop("GSC_CLIENT_SECRET")

        try:
            with pytest.raises(ConfigurationError, match="GSC_CLIENT_SECRET"):
                Config()
        finally:
            os.environ["GSC_CLIENT_SECRET"] = saved

    def test_config_refresh_token_optional(self) -> None:
        """Config should accept missing GSC_REFRESH_TOKEN (file-based auth)."""
        from mcp_google_search_console_crunchtools.config import Config

        saved = os.environ.pop("GSC_REFRESH_TOKEN")

        try:
            config = Config()
            assert config.refresh_token is None
        finally:
            os.environ["GSC_REFRESH_TOKEN"] = saved


class TestSiteTools:
    """Tests for site management tools."""

    @pytest.mark.asyncio
    async def test_list_sites(self) -> None:
        """list_sites should return site entries."""
        from mcp_google_search_console_crunchtools.tools import list_sites

        mock_resp = _mock_response(
            json_data={
                "siteEntry": [
                    {"siteUrl": "https://crunchtools.com/", "permissionLevel": "siteOwner"},
                    {"siteUrl": "https://educatedconfusion.com/", "permissionLevel": "siteOwner"},
                ]
            }
        )

        with _patch_client(mock_resp):
            result = await list_sites()

        assert "siteEntry" in result
        assert len(result["siteEntry"]) == 2

    @pytest.mark.asyncio
    async def test_get_site(self) -> None:
        """get_site should return site details."""
        from mcp_google_search_console_crunchtools.tools import get_site

        mock_resp = _mock_response(
            json_data={
                "siteUrl": "https://crunchtools.com/",
                "permissionLevel": "siteOwner",
            }
        )

        with _patch_client(mock_resp):
            result = await get_site(site_url="https://crunchtools.com/")

        assert result["siteUrl"] == "https://crunchtools.com/"

    @pytest.mark.asyncio
    async def test_add_site(self) -> None:
        """add_site should succeed with empty response."""
        from mcp_google_search_console_crunchtools.tools import add_site

        mock_resp = _mock_response(status_code=204)

        with _patch_client(mock_resp):
            result = await add_site(site_url="https://example.com/")

        assert result["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_site(self) -> None:
        """delete_site should succeed with 204."""
        from mcp_google_search_console_crunchtools.tools import delete_site

        mock_resp = _mock_response(status_code=204)

        with _patch_client(mock_resp):
            result = await delete_site(site_url="https://example.com/")

        assert result["status"] == "deleted"


class TestAnalyticsTools:
    """Tests for search analytics tools."""

    @pytest.mark.asyncio
    async def test_query_search_analytics(self) -> None:
        """query_search_analytics should return analytics data."""
        from mcp_google_search_console_crunchtools.tools import query_search_analytics

        mock_resp = _mock_response(
            json_data={
                "rows": [
                    {
                        "keys": ["2026-03-01"],
                        "clicks": 150.0,
                        "impressions": 3000.0,
                        "ctr": 0.05,
                        "position": 12.5,
                    }
                ],
                "responseAggregationType": "byProperty",
            }
        )

        with _patch_client(mock_resp):
            result = await query_search_analytics(
                site_url="https://crunchtools.com/",
                start_date="2026-03-01",
                end_date="2026-03-01",
                dimensions=["date"],
            )

        assert "rows" in result
        assert result["rows"][0]["clicks"] == 150.0

    @pytest.mark.asyncio
    async def test_query_search_analytics_with_filters(self) -> None:
        """query_search_analytics should accept dimension filter groups."""
        from mcp_google_search_console_crunchtools.tools import query_search_analytics

        mock_resp = _mock_response(
            json_data={
                "rows": [],
                "responseAggregationType": "auto",
            }
        )

        with _patch_client(mock_resp):
            result = await query_search_analytics(
                site_url="https://crunchtools.com/",
                start_date="2026-03-01",
                end_date="2026-03-03",
                dimensions=["query"],
                search_type="web",
                row_limit=10,
            )

        assert "rows" in result


class TestSitemapTools:
    """Tests for sitemap management tools."""

    @pytest.mark.asyncio
    async def test_list_sitemaps(self) -> None:
        """list_sitemaps should return sitemap entries."""
        from mcp_google_search_console_crunchtools.tools import list_sitemaps

        mock_resp = _mock_response(
            json_data={
                "sitemap": [
                    {
                        "path": "https://crunchtools.com/sitemap.xml",
                        "lastSubmitted": "2026-03-01T00:00:00Z",
                        "isPending": False,
                        "isSitemapsIndex": True,
                    }
                ]
            }
        )

        with _patch_client(mock_resp):
            result = await list_sitemaps(site_url="https://crunchtools.com/")

        assert "sitemap" in result

    @pytest.mark.asyncio
    async def test_get_sitemap(self) -> None:
        """get_sitemap should return sitemap details."""
        from mcp_google_search_console_crunchtools.tools import get_sitemap

        mock_resp = _mock_response(
            json_data={
                "path": "https://crunchtools.com/sitemap.xml",
                "lastSubmitted": "2026-03-01T00:00:00Z",
                "isPending": False,
            }
        )

        with _patch_client(mock_resp):
            result = await get_sitemap(
                site_url="https://crunchtools.com/",
                feedpath="https://crunchtools.com/sitemap.xml",
            )

        assert result["path"] == "https://crunchtools.com/sitemap.xml"

    @pytest.mark.asyncio
    async def test_submit_sitemap(self) -> None:
        """submit_sitemap should succeed with 204."""
        from mcp_google_search_console_crunchtools.tools import submit_sitemap

        mock_resp = _mock_response(status_code=204)

        with _patch_client(mock_resp):
            result = await submit_sitemap(
                site_url="https://crunchtools.com/",
                feedpath="https://crunchtools.com/sitemap.xml",
            )

        assert result["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_sitemap(self) -> None:
        """delete_sitemap should succeed with 204."""
        from mcp_google_search_console_crunchtools.tools import delete_sitemap

        mock_resp = _mock_response(status_code=204)

        with _patch_client(mock_resp):
            result = await delete_sitemap(
                site_url="https://crunchtools.com/",
                feedpath="https://crunchtools.com/sitemap.xml",
            )

        assert result["status"] == "deleted"


class TestInspectionTools:
    """Tests for URL inspection tools."""

    @pytest.mark.asyncio
    async def test_inspect_url(self) -> None:
        """inspect_url should return inspection result."""
        from mcp_google_search_console_crunchtools.tools import inspect_url

        mock_resp = _mock_response(
            json_data={
                "inspectionResult": {
                    "indexStatusResult": {
                        "verdict": "PASS",
                        "coverageState": "Submitted and indexed",
                        "lastCrawlTime": "2026-03-01T12:00:00Z",
                    },
                    "mobileUsabilityResult": {
                        "verdict": "PASS",
                    },
                }
            }
        )

        with _patch_client(mock_resp):
            result = await inspect_url(
                inspection_url="https://crunchtools.com/blog/test",
                site_url="https://crunchtools.com/",
            )

        assert "inspectionResult" in result
        assert result["inspectionResult"]["indexStatusResult"]["verdict"] == "PASS"


class TestClientErrorHandling:
    """Tests for client error handling."""

    @pytest.mark.asyncio
    async def test_401_raises_permission_denied(self) -> None:
        """401 response should raise PermissionDeniedError after retry."""
        from mcp_google_search_console_crunchtools.errors import PermissionDeniedError
        from mcp_google_search_console_crunchtools.tools import list_sites

        error_resp = _mock_response(
            status_code=401,
            json_data={"error": {"message": "Invalid credentials"}},
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request = AsyncMock(return_value=error_resp)
        mock_client.aclose = AsyncMock()
        mock_client.headers = {}

        with (
            patch(
                "mcp_google_search_console_crunchtools.client.SearchConsoleClient._ensure_token",
                new_callable=AsyncMock,
            ),
            patch("httpx.AsyncClient", return_value=mock_client),
            pytest.raises(PermissionDeniedError),
        ):
            await list_sites()

    @pytest.mark.asyncio
    async def test_404_raises_site_not_found(self) -> None:
        """404 response should raise SiteNotFoundError."""
        from mcp_google_search_console_crunchtools.errors import SiteNotFoundError
        from mcp_google_search_console_crunchtools.tools import get_site

        mock_resp = _mock_response(
            status_code=404,
            json_data={"error": {"message": "Not found"}},
        )

        with _patch_client(mock_resp), pytest.raises(SiteNotFoundError):
            await get_site(site_url="https://nonexistent.com/")

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self) -> None:
        """429 response should raise RateLimitError."""
        from mcp_google_search_console_crunchtools.errors import RateLimitError
        from mcp_google_search_console_crunchtools.tools import list_sites

        mock_resp = _mock_response(
            status_code=429,
            json_data={"error": {"message": "Rate limit exceeded"}},
            headers={"retry-after": "60"},
        )

        with _patch_client(mock_resp), pytest.raises(RateLimitError, match="60"):
            await list_sites()
