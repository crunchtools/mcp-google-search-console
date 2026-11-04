"""Pydantic models for input validation.

All tool inputs are validated through these models to prevent injection attacks
and ensure data integrity before making API calls.
"""

import re
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, field_validator

SITE_URL_PATTERN = re.compile(
    r"^(https?://[a-zA-Z0-9\-_.]+\.[a-zA-Z]{2,}(/.*)?|sc-domain:[a-zA-Z0-9\-_.]+\.[a-zA-Z]{2,})$"
)

DIMENSION_VALUES = frozenset({"date", "query", "page", "country", "device", "searchAppearance"})

SEARCH_TYPE_VALUES = frozenset({"web", "image", "video", "news", "googleNews", "discover"})

AGGREGATION_TYPE_VALUES = frozenset({"auto", "byPage", "byProperty"})

DATA_STATE_VALUES = frozenset({"final", "all"})

FILTER_DIMENSION_VALUES = frozenset({"query", "page", "country", "device", "searchAppearance"})

FILTER_OPERATOR_VALUES = frozenset(
    {
        "equals",
        "notEquals",
        "contains",
        "notContains",
        "includingRegex",
        "excludingRegex",
    }
)

MAX_ROW_LIMIT = 25000
MAX_URL_LENGTH = 2048
MAX_DIMENSIONS = 6


def encode_site_url(site_url: str) -> str:
    """Validate and encode a site URL for use in API paths.

    Google Search Console uses URL-encoded site URLs in API paths.
    Accepts both regular URLs (https://example.com) and domain
    properties (sc-domain:example.com).

    Args:
        site_url: Site URL or domain property identifier

    Returns:
        URL-encoded site URL safe for API paths

    Raises:
        ValueError: If the site_url format is invalid
    """
    if not site_url or not site_url.strip():
        raise ValueError("site_url must not be empty")

    site_url = site_url.strip()

    if not SITE_URL_PATTERN.match(site_url):
        raise ValueError(
            "site_url must be a URL (https://example.com) or "
            "domain property (sc-domain:example.com)"
        )

    return quote(site_url, safe="")


class SearchAnalyticsFilter(BaseModel):
    """A single filter for search analytics queries."""

    model_config = ConfigDict(extra="forbid")

    dimension: str = Field(..., description="Dimension to filter on")
    operator: str = Field(default="equals", description="Filter operator")
    expression: str = Field(..., max_length=MAX_URL_LENGTH, description="Filter value")

    @field_validator("dimension")
    @classmethod
    def validate_dimension(cls, v: str) -> str:
        if v not in FILTER_DIMENSION_VALUES:
            raise ValueError(
                f"dimension must be one of: {', '.join(sorted(FILTER_DIMENSION_VALUES))}"
            )
        return v

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        if v not in FILTER_OPERATOR_VALUES:
            raise ValueError(
                f"operator must be one of: {', '.join(sorted(FILTER_OPERATOR_VALUES))}"
            )
        return v


class SearchAnalyticsQuery(BaseModel):
    """Validated input for search analytics queries."""

    model_config = ConfigDict(extra="forbid")

    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    dimensions: list[str] | None = Field(
        default=None,
        max_length=MAX_DIMENSIONS,
        description="Dimensions to group by",
    )
    search_type: str = Field(
        default="web",
        description="Search type filter",
    )
    aggregation_type: str = Field(
        default="auto",
        description="How to aggregate results",
    )
    row_limit: int = Field(
        default=1000,
        ge=1,
        le=MAX_ROW_LIMIT,
        description="Maximum rows to return",
    )
    start_row: int = Field(
        default=0,
        ge=0,
        description="Zero-based row offset for pagination",
    )
    dimension_filter_groups: list[dict[str, list[dict[str, str]]]] | None = Field(
        default=None,
        description="Filter groups for the query",
    )
    data_state: str = Field(
        default="final",
        description="Data freshness: final or all (includes fresh data)",
    )

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for dim in v:
                if dim not in DIMENSION_VALUES:
                    raise ValueError(
                        f"Invalid dimension '{dim}'. Must be one of: "
                        f"{', '.join(sorted(DIMENSION_VALUES))}"
                    )
        return v

    @field_validator("search_type")
    @classmethod
    def validate_search_type(cls, v: str) -> str:
        if v not in SEARCH_TYPE_VALUES:
            raise ValueError(f"search_type must be one of: {', '.join(sorted(SEARCH_TYPE_VALUES))}")
        return v

    @field_validator("aggregation_type")
    @classmethod
    def validate_aggregation_type(cls, v: str) -> str:
        if v not in AGGREGATION_TYPE_VALUES:
            raise ValueError(
                f"aggregation_type must be one of: {', '.join(sorted(AGGREGATION_TYPE_VALUES))}"
            )
        return v

    @field_validator("data_state")
    @classmethod
    def validate_data_state(cls, v: str) -> str:
        if v not in DATA_STATE_VALUES:
            raise ValueError(f"data_state must be one of: {', '.join(sorted(DATA_STATE_VALUES))}")
        return v


class InspectUrlInput(BaseModel):
    """Validated input for URL inspection."""

    model_config = ConfigDict(extra="forbid")

    inspection_url: str = Field(
        ..., min_length=1, max_length=MAX_URL_LENGTH, description="URL to inspect"
    )
    site_url: str = Field(
        ..., min_length=1, max_length=MAX_URL_LENGTH, description="Site URL (property)"
    )
    language_code: str = Field(
        default="en-US", max_length=10, description="Language code for results"
    )
