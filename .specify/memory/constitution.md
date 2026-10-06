# mcp-google-search-console-crunchtools Constitution

> **Version:** 1.1.0
> **Ratified:** 2026-03-03
> **Amended:** 2026-10-02
> **Status:** Active
> **Inherits:** [crunchtools/constitution](https://github.com/crunchtools/constitution) v1.20.0
> **Profile:** MCP Server

This file holds what is specific to mcp-google-search-console. The fleet
rules and the MCP Server profile (five-layer security model, two-layer tools,
distribution channels, transports, quality gates, Gourmand) apply at the
inherited version and are checked against this repo's files by
`constitution.yml`. They are not restated here.

## Security Model Specifics

- **Credentials:** `GSC_CLIENT_ID` and `GSC_CLIENT_SECRET` (required) and
  `GSC_REFRESH_TOKEN` (optional), all held as `SecretStr` and read from the
  environment only. `SearchConsoleApiError` scrubs them from messages,
  `SiteNotFoundError` truncates long identifiers, and
  `Config.__repr__()`/`__str__()` never expose credentials.
- **Input limits:** Pydantic models with `extra="forbid"`; dimensions,
  search types, aggregation types, data states, filter dimensions and
  filter operators are allowlisted; site URLs must match
  `SITE_URL_PATTERN`.
- **API:** Bearer token in the `Authorization` header, never the URL; path
  parameters are URL-encoded; requests time out after 30s; responses are
  capped at 10MB.
- **Surface:** API wrappers whose only filesystem write is the credentials
  file below. No shell execution or code evaluation.

## OAuth2 Token Management

- The refresh token comes from `GSC_CREDENTIALS_DIR/credentials.json` first
  (default `/data`, written by the browser flow), then `GSC_REFRESH_TOKEN`.
  With neither, tools raise `AuthRequiredError` carrying the auth URL.
- The browser flow is served by the `/auth` and `/oauth2callback` routes;
  `GSC_OAUTH_REDIRECT_URI` sets the callback URL.
- The refresh token is exchanged at `https://oauth2.googleapis.com/token`;
  the access token is cached until 60s before expiry and refreshed once on a
  401. Refreshed credentials are saved atomically with mode `0600`.
- Scope `https://www.googleapis.com/auth/webmasters`; two API bases, the
  webmasters API (`https://www.googleapis.com/webmasters/v3`) and the URL
  inspection API (`https://searchconsole.googleapis.com/v1`).
- In the container, `/data` is a persistent volume so credentials survive
  restarts.

## Instance

| Context | Name |
|---------|------|
| GitHub repo | `crunchtools/mcp-google-search-console` |
| PyPI package | `mcp-google-search-console-crunchtools` |
| Container image | `quay.io/crunchtools/mcp-google-search-console` |
| systemd service | `mcp-google-search-console.service` |
| HTTP port | 8017 |

## History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-03 | Initial constitution |
| 1.0.1 | 2026-03-16 | Add Section VI (Container Conventions); renumber VI-VIII to VII-IX |
| 1.0.2 | 2026-09-25 | Inherit constitution v1.17.0 (Gatehouse gates) |
| 1.1.0 | 2026-10-02 | Manifest under constitution v1.18.0: profile restatement removed, OAuth and credential-file specifics kept and corrected to match the code |
