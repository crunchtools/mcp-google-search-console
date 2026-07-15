# mcp-google-search-console-crunchtools

<!-- mcp-name: io.github.crunchtools/google-search-console -->

Secure MCP server for Google Search Console. Query search analytics (clicks, impressions, CTR, position), manage sitemaps, inspect URL indexing status, and manage site properties.

[![CI](https://github.com/crunchtools/mcp-google-search-console/actions/workflows/ci.yml/badge.svg)](https://github.com/crunchtools/mcp-google-search-console/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mcp-google-search-console-crunchtools)](https://pypi.org/project/mcp-google-search-console-crunchtools/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## Installation

### uvx (recommended, zero-install)

```bash
claude mcp add mcp-google-search-console-crunchtools \
    --env GSC_CLIENT_ID=your_client_id \
    --env GSC_CLIENT_SECRET=your_client_secret \
    --env GSC_REFRESH_TOKEN=your_refresh_token \
    -- uvx mcp-google-search-console-crunchtools
```

### pip

```bash
pip install mcp-google-search-console-crunchtools
```

### Container (Podman/Docker)

```bash
podman run -d -p 8017:8017 \
    --env-file ~/.config/mcp-env/mcp-google-search-console.env \
    quay.io/crunchtools/mcp-google-search-console \
    --transport streamable-http --host 0.0.0.0
```

## OAuth Setup

This server supports two authentication methods: **browser-based OAuth** (recommended) and **environment variable** (fallback).

### Option A: Browser-Based OAuth (Recommended)

Browser-based OAuth handles token exchange automatically. When credentials expire, visit the `/auth` URL and click through Google's consent screen — no manual code exchange needed.

#### Step 1: Create a Google Cloud OAuth App

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services > Library**
4. Search for **Google Search Console API** and click **Enable**
5. Navigate to **APIs & Services > Credentials**
6. Click **+ CREATE CREDENTIALS > OAuth client ID**
7. If prompted, configure the OAuth consent screen first:
   - User type: **External** (or Internal if using Google Workspace)
   - App name: anything (e.g., "MCP Search Console")
   - Scopes: add `https://www.googleapis.com/auth/webmasters`
   - Test users: add your Google account email
8. Back on Create OAuth client ID:
   - Application type: **Web application**
   - Name: anything (e.g., "MCP Search Console")
   - Authorized redirect URIs: add your server's callback URL (e.g., `https://mcp-gsc.example.com/oauth2callback`)
9. Click **Create** — copy the **Client ID** and **Client Secret**

#### Step 2: Configure and Start

Create an env file:

```bash
cat > ~/.config/mcp-env/mcp-google-search-console.env << 'EOF'
GSC_CLIENT_ID=your_client_id
GSC_CLIENT_SECRET=your_client_secret
GSC_CREDENTIALS_DIR=/data
GSC_OAUTH_REDIRECT_URI=https://mcp-gsc.example.com/oauth2callback
EOF
chmod 600 ~/.config/mcp-env/mcp-google-search-console.env
```

Start the server with a persistent volume for credentials:

```bash
podman run -d -p 8017:8017 \
    --env-file ~/.config/mcp-env/mcp-google-search-console.env \
    -v mcp-gsc-data:/data:Z \
    quay.io/crunchtools/mcp-google-search-console \
    --transport streamable-http --host 0.0.0.0
```

#### Step 3: Authenticate

Visit `https://mcp-gsc.example.com/auth` in your browser. You'll be redirected to Google's consent screen. Grant access and the server will save credentials automatically.

When tokens expire, any tool call will return the `/auth` URL. Click it to re-authenticate — no container restart needed.

### Option B: Environment Variable (Fallback)

If you prefer static credentials or can't expose a callback URL, set `GSC_REFRESH_TOKEN` in your env file. See the [manual OAuth flow](#manual-oauth-flow) below.

<details>
<summary><strong>Manual OAuth flow</strong></summary>

```bash
export GSC_CLIENT_ID="your_client_id_here"
export GSC_CLIENT_SECRET="your_client_secret_here"

echo "https://accounts.google.com/o/oauth2/v2/auth?client_id=${GSC_CLIENT_ID}&redirect_uri=http://127.0.0.1&response_type=code&scope=https://www.googleapis.com/auth/webmasters&access_type=offline&prompt=consent"
```

1. Open the URL in your browser, sign in, and click **Allow**
2. Copy the `code=` value from the redirect URL
3. Exchange the code:

```bash
curl -s -X POST https://oauth2.googleapis.com/token \
    -d "client_id=${GSC_CLIENT_ID}" \
    -d "client_secret=${GSC_CLIENT_SECRET}" \
    -d "code=PASTE_CODE_HERE" \
    -d "grant_type=authorization_code" \
    -d "redirect_uri=http://127.0.0.1" | python3 -m json.tool
```

4. Copy the `refresh_token` from the response and add `GSC_REFRESH_TOKEN=...` to your env file.

</details>

### How it works at runtime

The server checks for credentials in this order:
1. **File-based credentials** from `GSC_CREDENTIALS_DIR/credentials.json` (written by the browser-based flow)
2. **Environment variable** `GSC_REFRESH_TOKEN` (fallback)

On each API call, the server exchanges the refresh token for a short-lived access token (~1 hour), cached in memory and refreshed automatically. Updated tokens are persisted to the credentials file for reuse across container restarts.

## Available Tools (10)

| Category | Count | Tools |
|----------|------:|-------|
| Sites | 4 | list_sites, get_site, add_site, delete_site |
| Search Analytics | 1 | query_search_analytics |
| Sitemaps | 4 | list_sitemaps, get_sitemap, submit_sitemap, delete_sitemap |
| URL Inspection | 1 | inspect_url |

## Security

- OAuth2 credentials stored as `SecretStr` (never logged)
- File-based credentials written with `0o600` permissions (atomic writes)
- Automatic token scrubbing from error messages
- Pydantic input validation with `extra="forbid"`
- No filesystem access, shell execution, or code evaluation
- TLS certificate validation (httpx default)
- Request timeouts and response size limits
- Built on [Hummingbird](https://github.com/hummingbird-project) container images

See [SECURITY.md](SECURITY.md) for the full security design document.

## Development

```bash
uv sync --all-extras
uv run ruff check src tests
uv run mypy src
uv run pytest -v
gourmand --full .
podman build -f Containerfile .
```

## License

[AGPL-3.0-or-later](LICENSE)
