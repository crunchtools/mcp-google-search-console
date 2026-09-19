# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

Entries prior to 2026-09-19 are back-filled from GitHub Release notes (RT #1484).

## [Unreleased]

## [0.1.0] - 2026-03-03

Initial release of mcp-google-search-console-crunchtools.

### Added
- 10 tools across 4 categories: Sites (`list_sites`, `get_site`, `add_site`,
  `delete_site`), Search Analytics (`query_search_analytics`), Sitemaps
  (`list_sitemaps`, `get_sitemap`, `submit_sitemap`, `delete_sitemap`), and URL
  Inspection (`inspect_url`).
- OAuth2 authentication with refresh token flow.
- Full Google Search Console API coverage.
- Pydantic input validation.
- Built on Hummingbird container images.
