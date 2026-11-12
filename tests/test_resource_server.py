"""Resource-server mode (RT #1606): the gateway injects a Google bearer per
request and this server validates it, instead of self-authing from a stored
refresh token. These tests cover the mode switch and its config guard, the exact
protected-resource metadata the gateway reads, and the property that two
profiles' tokens never cross because every request carries its own.
"""

from __future__ import annotations

import asyncio
import contextvars
from typing import Any
from unittest.mock import patch

import httpx
import pytest

import mcp_google_search_console_crunchtools.config as config_module
from mcp_google_search_console_crunchtools.config import Config
from mcp_google_search_console_crunchtools.errors import ConfigurationError

WEBMASTERS = "https://www.googleapis.com/auth/webmasters"
SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"


class TestModeConfig:
    def test_self_auth_is_the_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GSC_RESOURCE_SERVER", raising=False)
        cfg = Config()
        assert cfg.resource_server is False
        assert cfg.base_url == ""

    def test_resource_server_requires_a_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GSC_RESOURCE_SERVER", "true")
        monkeypatch.delenv("GSC_BASE_URL", raising=False)
        with pytest.raises(ConfigurationError, match="GSC_BASE_URL"):
            Config()

    def test_base_url_with_a_path_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GSC_RESOURCE_SERVER", "true")
        monkeypatch.setenv("GSC_BASE_URL", "http://mcp-gsc:8017/mcp")
        with pytest.raises(ConfigurationError, match="origin"):
            Config()

    def test_origin_base_url_is_accepted_and_normalised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GSC_RESOURCE_SERVER", "true")
        monkeypatch.setenv("GSC_BASE_URL", "http://mcp-gsc:8017/")
        cfg = Config()
        assert cfg.resource_server is True
        assert cfg.base_url == "http://mcp-gsc:8017"

    @pytest.mark.parametrize(
        "bad",
        [
            "http://user:pass@mcp-gsc:8017",
            "http://mcp-gsc:8017?x=1",
            "http://mcp-gsc:8017#f",
            "http://mcp-gsc:8017/mcp",
        ],
    )
    def test_base_url_rejects_non_origin_components(
        self, monkeypatch: pytest.MonkeyPatch, bad: str
    ) -> None:
        monkeypatch.setenv("GSC_RESOURCE_SERVER", "true")
        monkeypatch.setenv("GSC_BASE_URL", bad)
        with pytest.raises(ConfigurationError):
            Config()


class TestProtectedResourceMetadata:
    async def test_metadata_matches_what_the_gateway_expects(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GSC_RESOURCE_SERVER", "true")
        monkeypatch.setenv("GSC_BASE_URL", "http://mcp-gsc:8017")
        config_module._config = None

        from fastmcp import FastMCP

        from mcp_google_search_console_crunchtools.server import _build_auth

        provider = _build_auth()
        assert provider is not None
        app = FastMCP(name="gsc-test", auth=provider).http_app()

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://mcp-gsc:8017") as client:
            resp = await client.get("/.well-known/oauth-protected-resource/mcp")

        assert resp.status_code == 200
        doc = resp.json()
        assert doc["resource"] == "http://mcp-gsc:8017/mcp"
        # Byte-for-byte: a trailing slash here fails the gateway's issuer_mismatch
        # check against Google's issuer "https://accounts.google.com".
        assert doc["authorization_servers"] == ["https://accounts.google.com"]
        assert WEBMASTERS in doc["scopes_supported"]
        # The gateway asks Google for exactly these; without openid the token
        # has no `sub` and the verifier refuses it (RT #1613).
        assert "openid" in doc["scopes_supported"]


def _tokeninfo(scope: str, *, sub: bool) -> dict[str, Any]:
    """tokeninfo as Google returned it for a gateway-brokered token (RT #1613)."""
    client_id = "test_client_id"
    info: dict[str, Any] = {
        "aud": client_id,
        "azp": client_id,
        "scope": scope,
        "expires_in": "3557",
    }
    if sub:
        info["sub"] = "1234567890"
    return info


class TestVerifierAcceptsBrokeredToken:
    async def _verify(self, monkeypatch: pytest.MonkeyPatch, info: dict[str, Any]) -> Any:
        monkeypatch.setenv("GSC_RESOURCE_SERVER", "true")
        monkeypatch.setenv("GSC_BASE_URL", "http://mcp-gsc:8017")
        config_module._config = None

        import httpx2

        from mcp_google_search_console_crunchtools.server import _build_auth

        # Every Google call answers with the tokeninfo body; the verifier's
        # follow-up userinfo call only enriches claims and accepts any 200.
        transport = httpx2.MockTransport(lambda _request: httpx2.Response(200, json=info))

        provider = _build_auth()
        assert provider is not None
        verifier: Any = provider.token_verifier
        verifier._http_client = httpx2.AsyncClient(transport=transport)
        return await verifier.verify_token("ya29.test")

    async def test_token_with_openid_and_webmasters_is_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        info = _tokeninfo(f"openid {WEBMASTERS}", sub=True)
        assert await self._verify(monkeypatch, info) is not None

    async def test_webmasters_only_token_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The shape the gateway held before the fix: right aud and scope, no sub.
        info = _tokeninfo(WEBMASTERS, sub=False)
        assert await self._verify(monkeypatch, info) is None


class TestPerRequestBearer:
    async def test_two_tokens_never_cross_and_no_self_auth_happens(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        monkeypatch.setenv("GSC_RESOURCE_SERVER", "true")
        monkeypatch.setenv("GSC_BASE_URL", "http://mcp-gsc:8017")
        monkeypatch.setenv("GSC_CREDENTIALS_DIR", str(tmp_path))
        config_module._config = None

        from fastmcp.server.auth import AccessToken

        from mcp_google_search_console_crunchtools.client import SearchConsoleClient

        sent: list[tuple[str, str | None]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append((str(request.url), request.headers.get("Authorization")))
            return httpx.Response(200, json={"siteEntry": []})

        real = httpx.AsyncClient

        def factory(**kwargs: Any) -> httpx.AsyncClient:
            kwargs.pop("transport", None)
            return real(transport=httpx.MockTransport(handler), **kwargs)

        current = contextvars.ContextVar[str]("current_bearer")

        def fake_get_access_token() -> AccessToken:
            # Stands in for what RequireAuthMiddleware binds to the request task
            # after the verifier accepts the gateway-injected token.
            return AccessToken(
                token=current.get(),
                client_id="test_client_id",
                scopes=[WEBMASTERS],
            )

        async def drive(bearer: str) -> None:
            current.set(bearer)
            await SearchConsoleClient()._request("GET", SITES_URL)

        with (
            patch("httpx.AsyncClient", factory),
            patch(
                "fastmcp.server.dependencies.get_access_token",
                fake_get_access_token,
            ),
        ):
            # gather schedules each coroutine as its own task with its own copied
            # context, so current.set() in one cannot leak into the other.
            await asyncio.gather(drive("AAA"), drive("BBB"))

        auths = {auth for _, auth in sent}
        assert auths == {"Bearer AAA", "Bearer BBB"}
        # Self-auth never runs in resource-server mode: the token endpoint is not
        # hit and nothing is written to the credentials dir.
        assert all("oauth2.googleapis.com/token" not in url for url, _ in sent)
        assert list(tmp_path.iterdir()) == []

    async def test_missing_bearer_is_permission_denied(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        monkeypatch.setenv("GSC_RESOURCE_SERVER", "true")
        monkeypatch.setenv("GSC_BASE_URL", "http://mcp-gsc:8017")
        monkeypatch.setenv("GSC_CREDENTIALS_DIR", str(tmp_path))
        config_module._config = None

        from mcp_google_search_console_crunchtools.client import SearchConsoleClient
        from mcp_google_search_console_crunchtools.errors import PermissionDeniedError

        with (
            patch(
                "fastmcp.server.dependencies.get_access_token",
                lambda: None,
            ),
            pytest.raises(PermissionDeniedError),
        ):
            await SearchConsoleClient()._request("GET", SITES_URL)
