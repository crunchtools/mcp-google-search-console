# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

Entries prior to 2026-09-19 are back-filled from GitHub Release notes (RT #1484).

## [Unreleased]

## [0.5.2] - 2026-11-11

### Fixed

- Resource-server mode now requires and advertises the `openid` scope alongside `webmasters`. Without it, Google's tokeninfo returns no `sub` for a gateway-brokered token and FastMCP's verifier refused every request as `invalid_token` (RT#1613). Existing brokered grants need one re-consent to pick up the new scope.

## [0.5.1] - 2026-11-11

### Changed

- No functional change. First release on the build-once container pipeline (RT#1550): `:latest` now names a digest that passed the release gates.

## [0.5.0] - 2026-11-10

### Added

- **Resource-server mode for gateway-brokered OAuth (RT #1606).** With
  `GSC_RESOURCE_SERVER=true` and `GSC_BASE_URL` set to the origin the gateway
  dials (e.g. `http://mcp-gsc:8017`, no path), the server validates a Google
  bearer injected per request by the Trentina gateway instead of self-authing
  from a stored refresh token. It advertises its protected-resource metadata
  (`authorization_servers: accounts.google.com`, scope `webmasters`) and
  challenges an unauthenticated call with 401, so the gateway's OAuth broker can
  complete consent and auto-refresh the grant. Tokens are validated via FastMCP's
  `GoogleTokenVerifier` (tokeninfo, audience pinned to the client id) so a bad or
  foreign token is a 401 the gateway refreshes on. Each request carries its own
  bearer, so two profiles' grants never cross. Default off; the standalone
  self-auth flow is unchanged and remains the rollback path.

### Changed

- The API client's shared connection pool no longer holds a default
  `Authorization` header; every request builds its own from a per-request token
  source. No behaviour change in self-auth mode.

## [0.4.1] - 2026-11-10

### Fixed

- **The container now installs the versions CI actually tested.** The builder
  stage ran `pip install .`, which reads only `pyproject.toml`'s floor-pins and
  lets pip re-resolve every dependency fresh at build time -- silently drifting
  from the committed, Dependabot-maintained `uv.lock`. A new `lock` stage runs
  `uv export --frozen` to turn `uv.lock` into a pinned `requirements.txt`, and
  both the dependency and project installs now pass `--no-deps` so pip cannot
  re-resolve anything. Same fix as mcp-gemini (RT #1564), after a prod outage
  there from an unpinned `google-genai` jumping two major versions between the
  CI-tested image and what shipped.

## [0.4.0] - 2026-11-08

### Added

- **The client says what it is.** Every request — the API calls and both OAuth
  token exchanges — now carries
  `User-Agent: mcp-google-search-console-crunchtools/<version> (+<repo url>)`,
  with the version read from installed package metadata so it cannot drift from
  `pyproject.toml`. httpx's default is `python-httpx/<version>`, which bot
  protection answers with an HTML challenge page instead of the API: the
  failure that cost an afternoon on mcp-wordpress (RT #1596).

- `transport.py` holds what every outbound request has in common, because
  `auth.py` talks to Google's token endpoint on its own and two copies of this
  would mean one of them drifting.

### Fixed

- **The response ceiling is now a ceiling.** It read the `content-length`
  header and nothing else, and that header is optional: a chunked reply carried
  none and was read without limit. Bodies are now read in bounded pieces and
  the read aborts the moment the running total passes `MAX_RESPONSE_SIZE`. The
  header is still an early reject, now guarded so a malformed value is not an
  unhandled `ValueError`.

- **An error says which site answered, and with what.** A non-JSON body came
  back as `Unknown error` or a bare 200 characters of text with no indication
  of where it came from, so a WAF challenge, a consent screen and a genuine API
  error were one message. They now name the method, the full requested URL, the
  status, the content-type and a short body snippet.

- **The URL in an error carries no secret.** Userinfo is dropped and
  `access_token`, `client_secret`, `code`, `id_token`, `refresh_token` and
  `token` are redacted by name — by name rather than by dropping the query
  string, because the path and the ordinary parameters are the diagnosis.

- **A token refresh that answered with HTML surfaced as a `KeyError`.** It
  called `.json()` on an unchecked body and then indexed `access_token`. It now
  reports what came back instead.

### Changed

- Client tests drive a real `httpx.AsyncClient` over `httpx.MockTransport`
  instead of an `AsyncMock` standing in for the client. The client is what sets
  the agent string and what reads the body in pieces, so mocking its methods
  mocked away the behaviour the tests are now there to hold.

- Error-message tests assert the whole message rather than a substring. An
  absence cannot be shown by a substring check, and a substring check against a
  URL literal is what CodeQL flags as incomplete sanitization.

- Inherits constitution v1.36.0, whose MCP Server profile 1.8.0 states this
  contract and checks it.

## [0.3.1] - 2026-10-31

### Security

- Upgraded locked dependencies within their declared ranges to clear the
  advisories the fleet dependency audit found (anyio, authlib, certifi, cryptography, dnspython, fastmcp, joserfc, opentelemetry-api, pydantic-settings, pygments, pyjwt).

## [0.3.0] - 2026-10-20

### Changed

- Container base images pinned to `quay.io/hummingbird/python:3.14*` instead of
  `latest`, which moved to Python 3.15.0 on 2026-10-20 (crunchtools/constitution#66).

## [0.2.1] - 2026-10-11

### Fixed

- A 204 response reports `{"status": "deleted"}` only for DELETE requests;
  `add_site` and `submit_sitemap` now report `{"status": "success"}`.
- The OAuth consent URL URL-encodes its query parameters.
- The OAuth callback page HTML-escapes the `error` query parameter.

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
