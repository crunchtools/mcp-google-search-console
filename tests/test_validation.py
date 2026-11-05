"""Tests for input validation."""

import pytest
from pydantic import ValidationError

from mcp_google_search_console_crunchtools.models import (
    InspectUrlInput,
    SearchAnalyticsQuery,
    encode_site_url,
)


class TestSiteUrlEncoding:
    """Tests for site URL validation and encoding."""

    def test_https_url(self) -> None:
        """HTTPS URL should be URL-encoded."""
        result = encode_site_url("https://crunchtools.com/")
        assert result == "https%3A%2F%2Fcrunchtools.com%2F"

    def test_http_url(self) -> None:
        """HTTP URL should be URL-encoded."""
        result = encode_site_url("http://example.com/")
        assert result == "http%3A%2F%2Fexample.com%2F"

    def test_domain_property(self) -> None:
        """Domain property should be URL-encoded."""
        result = encode_site_url("sc-domain:crunchtools.com")
        assert result == "sc-domain%3Acrunchtools.com"

    def test_url_with_path(self) -> None:
        """URL with path should be valid."""
        result = encode_site_url("https://example.com/blog/")
        assert result == "https%3A%2F%2Fexample.com%2Fblog%2F"

    def test_empty_string(self) -> None:
        """Empty string should fail."""
        with pytest.raises(ValueError, match="must not be empty"):
            encode_site_url("")

    def test_whitespace_only(self) -> None:
        """Whitespace-only string should fail."""
        with pytest.raises(ValueError, match="must not be empty"):
            encode_site_url("   ")

    def test_invalid_url(self) -> None:
        """Invalid URL format should fail."""
        with pytest.raises(ValueError, match="must be a URL"):
            encode_site_url("not-a-url")

    def test_injection_attempt(self) -> None:
        """Injection attempts should fail."""
        with pytest.raises(ValueError, match="must be a URL"):
            encode_site_url("https://example.com; rm -rf /")


class TestSearchAnalyticsQuery:
    """Tests for search analytics query validation."""

    def test_valid_minimal(self) -> None:
        """Minimal valid query should pass."""
        query = SearchAnalyticsQuery(
            start_date="2026-03-01",
            end_date="2026-03-03",
        )
        assert query.start_date == "2026-03-01"
        assert query.search_type == "web"

    def test_valid_full(self) -> None:
        """Full valid query should pass."""
        query = SearchAnalyticsQuery(
            start_date="2026-03-01",
            end_date="2026-03-03",
            dimensions=["date", "query", "page"],
            search_type="web",
            aggregation_type="byPage",
            row_limit=5000,
            start_row=100,
            data_state="all",
        )
        assert query.row_limit == 5000
        assert query.dimensions == ["date", "query", "page"]

    def test_invalid_dimension(self) -> None:
        """Invalid dimension should fail."""
        with pytest.raises(ValidationError, match="Invalid dimension"):
            SearchAnalyticsQuery(
                start_date="2026-03-01",
                end_date="2026-03-03",
                dimensions=["invalid_dimension"],
            )

    def test_invalid_search_type(self) -> None:
        """Invalid search type should fail."""
        with pytest.raises(ValidationError, match="search_type"):
            SearchAnalyticsQuery(
                start_date="2026-03-01",
                end_date="2026-03-03",
                search_type="invalid",
            )

    def test_invalid_aggregation_type(self) -> None:
        """Invalid aggregation type should fail."""
        with pytest.raises(ValidationError, match="aggregation_type"):
            SearchAnalyticsQuery(
                start_date="2026-03-01",
                end_date="2026-03-03",
                aggregation_type="invalid",
            )

    def test_invalid_data_state(self) -> None:
        """Invalid data state should fail."""
        with pytest.raises(ValidationError, match="data_state"):
            SearchAnalyticsQuery(
                start_date="2026-03-01",
                end_date="2026-03-03",
                data_state="invalid",
            )

    def test_row_limit_too_high(self) -> None:
        """Row limit above 25000 should fail."""
        with pytest.raises(ValidationError):
            SearchAnalyticsQuery(
                start_date="2026-03-01",
                end_date="2026-03-03",
                row_limit=30000,
            )

    def test_row_limit_zero(self) -> None:
        """Row limit of 0 should fail."""
        with pytest.raises(ValidationError):
            SearchAnalyticsQuery(
                start_date="2026-03-01",
                end_date="2026-03-03",
                row_limit=0,
            )

    def test_extra_fields_rejected(self) -> None:
        """Extra fields should be rejected."""
        with pytest.raises(ValidationError):
            SearchAnalyticsQuery(
                start_date="2026-03-01",
                end_date="2026-03-03",
                extra_field="not_allowed",  # type: ignore[call-arg]
            )


class TestInspectUrlInput:
    """Tests for URL inspection input validation."""

    def test_valid_minimal(self) -> None:
        """Minimal valid input should pass."""
        inp = InspectUrlInput(
            inspection_url="https://crunchtools.com/blog/test",
            site_url="https://crunchtools.com/",
        )
        assert inp.language_code == "en-US"

    def test_valid_full(self) -> None:
        """Full valid input should pass."""
        inp = InspectUrlInput(
            inspection_url="https://crunchtools.com/blog/test",
            site_url="https://crunchtools.com/",
            language_code="de-DE",
        )
        assert inp.language_code == "de-DE"

    def test_empty_url_rejected(self) -> None:
        """Empty inspection URL should fail."""
        with pytest.raises(ValidationError):
            InspectUrlInput(
                inspection_url="",
                site_url="https://crunchtools.com/",
            )

    def test_extra_fields_rejected(self) -> None:
        """Extra fields should be rejected."""
        with pytest.raises(ValidationError):
            InspectUrlInput(
                inspection_url="https://crunchtools.com/test",
                site_url="https://crunchtools.com/",
                extra_field="not_allowed",  # type: ignore[call-arg]
            )
