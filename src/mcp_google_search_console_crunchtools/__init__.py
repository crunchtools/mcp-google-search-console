"""MCP Google Search Console CrunchTools - Secure MCP server for Google Search Console.

Query search analytics (clicks, impressions, CTR, position), manage sitemaps,
inspect URL indexing status, and manage site properties via OAuth2.

Usage:
    mcp-google-search-console-crunchtools

    python -m mcp_google_search_console_crunchtools

    uvx mcp-google-search-console-crunchtools

Environment Variables:
    GSC_CLIENT_ID: Required. Google Cloud OAuth client ID.
    GSC_CLIENT_SECRET: Required. Google Cloud OAuth client secret.
    GSC_REFRESH_TOKEN: Required. OAuth refresh token with webmasters scope.

Example with Claude Code:
    claude mcp add mcp-google-search-console-crunchtools \\
        --env GSC_CLIENT_ID=your_client_id \\
        --env GSC_CLIENT_SECRET=your_client_secret \\
        --env GSC_REFRESH_TOKEN=your_refresh_token \\
        -- uvx mcp-google-search-console-crunchtools
"""

import argparse

from .server import mcp

__version__ = "0.2.0"
__all__ = ["main", "mcp"]


def main() -> None:
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="MCP server for Google Search Console")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to for HTTP transports (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8017,
        help="Port to bind to for HTTP transports (default: 8017)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)
