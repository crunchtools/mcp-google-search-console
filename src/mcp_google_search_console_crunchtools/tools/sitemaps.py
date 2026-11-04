"""Sitemap management tools.

Tools for listing, getting, submitting, and deleting sitemaps.
"""

from typing import Any
from urllib.parse import quote

from ..client import get_client
from ..models import encode_site_url


async def list_sitemaps(
    site_url: str,
) -> dict[str, Any]:
    """List all sitemaps for a site.

    Args:
        site_url: Site URL or domain property

    Returns:
        Dictionary containing sitemap entries with status and metadata
    """
    client = get_client()
    encoded_url = encode_site_url(site_url)
    return await client.webmasters_get(f"/sites/{encoded_url}/sitemaps")


async def get_sitemap(
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
    client = get_client()
    encoded_url = encode_site_url(site_url)
    encoded_feedpath = quote(feedpath, safe="")
    return await client.webmasters_get(f"/sites/{encoded_url}/sitemaps/{encoded_feedpath}")


async def submit_sitemap(
    site_url: str,
    feedpath: str,
) -> dict[str, Any]:
    """Submit a sitemap for crawling.

    Args:
        site_url: Site URL or domain property
        feedpath: Full URL of the sitemap to submit

    Returns:
        Confirmation of submission
    """
    client = get_client()
    encoded_url = encode_site_url(site_url)
    encoded_feedpath = quote(feedpath, safe="")
    return await client.webmasters_put(f"/sites/{encoded_url}/sitemaps/{encoded_feedpath}")


async def delete_sitemap(
    site_url: str,
    feedpath: str,
) -> dict[str, Any]:
    """Remove a sitemap.

    Args:
        site_url: Site URL or domain property
        feedpath: Full URL of the sitemap to delete

    Returns:
        Confirmation of deletion
    """
    client = get_client()
    encoded_url = encode_site_url(site_url)
    encoded_feedpath = quote(feedpath, safe="")
    return await client.webmasters_delete(f"/sites/{encoded_url}/sitemaps/{encoded_feedpath}")
