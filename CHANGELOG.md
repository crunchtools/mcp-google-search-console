# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

Entries prior to 2026-09-19 are back-filled from GitHub Release notes (RT #1484).

## [Unreleased]

## [0.2.0] - 2026-10-10

### Added

- The six tools that only read (`list_sites`, `get_site`,
  `query_search_analytics`, `list_sitemaps`, `get_sitemap`, `inspect_url`)
  publish `readOnlyHint: true`. A gateway uses it to decide whether an invalid
  optional argument may be dropped or must refuse the call
  (crunchtools/constitution#35).
- Tests pin every registered tool into `READ_ONLY` or `WRITES`, and check that
  a read-only tool sends only GET, apart from the two named POST endpoints
  that query (`searchAnalytics/query`, `urlInspection/index:inspect`).

### Changed

- Inherits constitution v1.22.0; the workflow pins and the pre-commit hook rev
  move with it.
- Constitution is now a v1.18.0 manifest: it holds only what is specific to
  this repo; fleet and profile rules apply by reference.
- Constitution validation is pinned to the inherited release via
  `.github/workflows/constitution.yml`.
- Dependabot auto-merges GitHub Actions minor and patch updates.

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
