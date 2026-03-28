"""Tests for collabmark.lib.browser_auth — browser OAuth login flow."""

from __future__ import annotations

import threading
import time
import urllib.request
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from click.testing import CliRunner

from collabmark.lib.auth import AuthError, UserInfo
from collabmark.lib.browser_auth import (
    _CallbackHandler,
    _exchange_code_for_jwt,
    _find_free_port,
    _reuse_or_create_api_key,
    browser_login,
)
from collabmark.main import cli

FAKE_JWT = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.sig"
FAKE_RAW_KEY = "cm_" + "ab12cd34" * 8
FAKE_USER_RESPONSE = {
    "id": "user123",
    "email": "pm@acme.com",
    "name": "Alice PM",
    "avatar_url": None,
    "org_name": "Acme Corp",
}
FAKE_KEY_RESPONSE = {
    "id": "key456",
    "name": "CollabMark CLI (auto-created)",
    "raw_key": FAKE_RAW_KEY,
    "created_at": "2026-01-01T00:00:00Z",
}
API_BASE = "http://test-server:8000"
FRONTEND_BASE = "http://test-frontend:5173"


class TestFindFreePort:
    def test_returns_positive_int(self) -> None:
        port = _find_free_port()
        assert isinstance(port, int)
        assert port > 0

    def test_returns_different_ports(self) -> None:
        ports = {_find_free_port() for _ in range(5)}
        assert len(ports) >= 2


class TestCallbackHandler:
    def test_code_captured_from_query_param(self) -> None:
        _CallbackHandler.code = None
        _CallbackHandler.frontend_url = "http://localhost:5173"

        handler = MagicMock(spec=_CallbackHandler)
        handler.path = "/callback?code=abc123"
        handler.server = MagicMock()

        _CallbackHandler.do_GET(handler)
        assert _CallbackHandler.code == "abc123"
        handler.send_response.assert_called_once_with(302)
        location_header = [c for c in handler.send_header.call_args_list if c[0][0] == "Location"]
        assert len(location_header) == 1
        assert "status=success" in location_header[0][0][1]

    def test_code_none_when_no_query_param(self) -> None:
        _CallbackHandler.code = None
        _CallbackHandler.frontend_url = "http://localhost:5173"

        handler = MagicMock(spec=_CallbackHandler)
        handler.path = "/callback"
        handler.server = MagicMock()

        _CallbackHandler.do_GET(handler)
        assert _CallbackHandler.code is None
        handler.send_response.assert_called_once_with(302)
        location_header = [c for c in handler.send_header.call_args_list if c[0][0] == "Location"]
        assert len(location_header) == 1
        assert "status=error" in location_header[0][0][1]

    def test_redirects_to_frontend_url(self) -> None:
        _CallbackHandler.code = None
        _CallbackHandler.frontend_url = "https://app.collabmark.io"

        handler = MagicMock(spec=_CallbackHandler)
        handler.path = "/callback?code=tok123"
        handler.server = MagicMock()

        _CallbackHandler.do_GET(handler)
        location_header = [c for c in handler.send_header.call_args_list if c[0][0] == "Location"]
        assert "https://app.collabmark.io/cli-login" in location_header[0][0][1]


class TestExchangeCodeForJwt:
    @pytest.mark.asyncio
    @respx.mock
    async def test_exchanges_code_successfully(self) -> None:
        respx.post(f"{API_BASE}/api/auth/cli/exchange").mock(return_value=httpx.Response(200, json={"token": FAKE_JWT}))
        token = await _exchange_code_for_jwt("test_code_123", API_BASE)
        assert token == FAKE_JWT

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_invalid_code(self) -> None:
        respx.post(f"{API_BASE}/api/auth/cli/exchange").mock(return_value=httpx.Response(401))
        with pytest.raises(AuthError, match="Code exchange failed"):
            await _exchange_code_for_jwt("expired_code", API_BASE)

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_code_in_json_body(self) -> None:
        route = respx.post(f"{API_BASE}/api/auth/cli/exchange").mock(
            return_value=httpx.Response(200, json={"token": FAKE_JWT})
        )
        await _exchange_code_for_jwt("my_code", API_BASE)
        request = route.calls[0].request
        import json

        body = json.loads(request.content)
        assert body == {"code": "my_code"}


class TestReuseOrCreateApiKey:
    @pytest.mark.asyncio
    @respx.mock
    @patch("collabmark.lib.browser_auth.load_api_key", return_value=None)
    async def test_creates_key_when_no_local_key(self, _mock_load) -> None:
        respx.get(f"{API_BASE}/api/users/me").mock(return_value=httpx.Response(200, json=FAKE_USER_RESPONSE))
        respx.post(f"{API_BASE}/api/keys").mock(return_value=httpx.Response(201, json=FAKE_KEY_RESPONSE))

        raw_key, user_info = await _reuse_or_create_api_key(FAKE_JWT, API_BASE)
        assert raw_key == FAKE_RAW_KEY
        assert user_info.email == "pm@acme.com"
        assert user_info.name == "Alice PM"

    @pytest.mark.asyncio
    @patch("collabmark.lib.browser_auth.validate_api_key")
    @patch("collabmark.lib.browser_auth.load_api_key", return_value="cm_existing_key_1234")
    async def test_reuses_valid_local_key(self, _mock_load, mock_validate) -> None:
        expected_info = UserInfo(
            id="user123",
            email="pm@acme.com",
            name="Alice PM",
            avatar_url=None,
            org_name="Acme Corp",
        )
        mock_validate.return_value = expected_info

        raw_key, user_info = await _reuse_or_create_api_key(FAKE_JWT, API_BASE)
        assert raw_key == "cm_existing_key_1234"
        assert user_info.email == "pm@acme.com"
        mock_validate.assert_called_once_with("cm_existing_key_1234", API_BASE)

    @pytest.mark.asyncio
    @respx.mock
    @patch("collabmark.lib.browser_auth.validate_api_key", side_effect=AuthError("expired"))
    @patch("collabmark.lib.browser_auth.load_api_key", return_value="cm_stale_key")
    async def test_creates_new_key_when_local_key_invalid(self, _mock_load, _mock_validate) -> None:
        respx.get(f"{API_BASE}/api/users/me").mock(return_value=httpx.Response(200, json=FAKE_USER_RESPONSE))
        respx.post(f"{API_BASE}/api/keys").mock(return_value=httpx.Response(201, json=FAKE_KEY_RESPONSE))

        raw_key, user_info = await _reuse_or_create_api_key(FAKE_JWT, API_BASE)
        assert raw_key == FAKE_RAW_KEY
        assert user_info.name == "Alice PM"

    @pytest.mark.asyncio
    @respx.mock
    @patch("collabmark.lib.browser_auth.load_api_key", return_value=None)
    async def test_sends_jwt_as_cookie(self, _mock_load) -> None:
        user_route = respx.get(f"{API_BASE}/api/users/me").mock(
            return_value=httpx.Response(200, json=FAKE_USER_RESPONSE)
        )
        respx.post(f"{API_BASE}/api/keys").mock(return_value=httpx.Response(201, json=FAKE_KEY_RESPONSE))

        await _reuse_or_create_api_key(FAKE_JWT, API_BASE)
        request = user_route.calls[0].request
        assert "access_token" in str(request.headers.get("cookie", ""))

    @pytest.mark.asyncio
    @respx.mock
    @patch("collabmark.lib.browser_auth.load_api_key", return_value=None)
    async def test_raises_on_user_fetch_failure(self, _mock_load) -> None:
        respx.get(f"{API_BASE}/api/users/me").mock(return_value=httpx.Response(401, json={"detail": "Unauthorized"}))

        with pytest.raises(AuthError, match="Failed to fetch user info"):
            await _reuse_or_create_api_key(FAKE_JWT, API_BASE)

    @pytest.mark.asyncio
    @respx.mock
    @patch("collabmark.lib.browser_auth.load_api_key", return_value=None)
    async def test_raises_on_key_creation_failure(self, _mock_load) -> None:
        respx.get(f"{API_BASE}/api/users/me").mock(return_value=httpx.Response(200, json=FAKE_USER_RESPONSE))
        respx.post(f"{API_BASE}/api/keys").mock(return_value=httpx.Response(500, text="Internal Server Error"))

        with pytest.raises(AuthError, match="Failed to create API key"):
            await _reuse_or_create_api_key(FAKE_JWT, API_BASE)


class TestBrowserLogin:
    @pytest.mark.asyncio
    @respx.mock
    @patch("collabmark.lib.browser_auth.load_api_key", return_value=None)
    @patch("collabmark.lib.browser_auth.save_api_key")
    @patch("collabmark.lib.browser_auth.webbrowser.open")
    async def test_full_flow(self, mock_open: MagicMock, mock_save: MagicMock, _mock_load: MagicMock) -> None:
        """Simulates the full browser login by injecting an auth code via HTTP."""
        fake_code = "cli_auth_code_abc123"
        respx.post(f"{API_BASE}/api/auth/cli/exchange").mock(return_value=httpx.Response(200, json={"token": FAKE_JWT}))
        respx.get(f"{API_BASE}/api/users/me").mock(return_value=httpx.Response(200, json=FAKE_USER_RESPONSE))
        respx.post(f"{API_BASE}/api/keys").mock(return_value=httpx.Response(201, json=FAKE_KEY_RESPONSE))

        def simulate_callback(url: str) -> None:
            """Parse the port from the frontend URL and hit the callback with a code."""
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            port = int(qs["port"][0])

            time.sleep(0.3)
            try:
                urllib.request.urlopen(f"http://localhost:{port}/callback?code={fake_code}")
            except Exception:
                pass

        mock_open.side_effect = lambda url: threading.Thread(target=simulate_callback, args=(url,), daemon=True).start()

        raw_key, user_info = await browser_login(api_url=API_BASE, frontend_url=FRONTEND_BASE, timeout_seconds=10)

        assert raw_key == FAKE_RAW_KEY
        assert user_info.email == "pm@acme.com"
        mock_save.assert_called_once_with(FAKE_RAW_KEY)
        mock_open.assert_called_once()
        opened_url = mock_open.call_args[0][0]
        assert opened_url.startswith(f"{FRONTEND_BASE}/cli-login?port=")

    @pytest.mark.asyncio
    @patch("collabmark.lib.browser_auth.save_api_key")
    @patch("collabmark.lib.browser_auth.webbrowser.open")
    async def test_timeout_raises_auth_error(self, mock_open: MagicMock, mock_save: MagicMock) -> None:
        mock_open.return_value = None

        with pytest.raises(AuthError, match="Login timed out"):
            await browser_login(api_url=API_BASE, frontend_url=FRONTEND_BASE, timeout_seconds=1)

        mock_save.assert_not_called()

    @pytest.mark.asyncio
    @patch("collabmark.lib.browser_auth.save_api_key")
    @patch("collabmark.lib.browser_auth.webbrowser.open")
    async def test_opens_frontend_cli_login_url(self, mock_open: MagicMock, mock_save: MagicMock) -> None:
        mock_open.return_value = None

        with pytest.raises(AuthError, match="Login timed out"):
            await browser_login(api_url=API_BASE, frontend_url=FRONTEND_BASE, timeout_seconds=1)

        mock_open.assert_called_once()
        url = mock_open.call_args[0][0]
        assert "/cli-login?port=" in url
        assert url.startswith(FRONTEND_BASE)


class TestLoginCommand:
    """Test the login CLI command in both browser and API key modes."""

    @patch("collabmark.lib.browser_auth.save_api_key")
    @patch("collabmark.lib.browser_auth.webbrowser.open")
    def test_login_help_shows_browser_default(self, _a: MagicMock, _b: MagicMock) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["login", "--help"])
        assert result.exit_code == 0
        assert "browser" in result.output.lower() or "api-key" in result.output.lower()
