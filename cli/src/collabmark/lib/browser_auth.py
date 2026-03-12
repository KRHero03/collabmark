"""Browser-based OAuth login flow for the CollabMark CLI.

Opens the user's default browser to the CollabMark login page, starts a
temporary local HTTP server to receive the callback, then exchanges the
JWT for a persistent API key.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from collabmark.lib.auth import AuthError, UserInfo, load_api_key, save_api_key, validate_api_key
from collabmark.lib.config import get_api_url, get_frontend_url

logger = logging.getLogger(__name__)

_CLI_API_KEY_NAME = "CollabMark CLI (auto-created)"


class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth callback token.

    After capturing (or failing to capture) the token, the browser is
    redirected back to the main CollabMark frontend ``/cli-login`` page
    with a ``status`` query parameter so the real site renders the
    success/error UI with full theme and styling support.
    """

    token: str | None = None
    frontend_url: str = "/"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        token_list = params.get("token", [])

        base = _CallbackHandler.frontend_url.rstrip("/")
        if token_list:
            _CallbackHandler.token = token_list[0]
            redirect = f"{base}/cli-login?{urlencode({'status': 'success'})}"
        else:
            redirect = f"{base}/cli-login?{urlencode({'status': 'error'})}"

        self.send_response(302)
        self.send_header("Location", redirect)
        self.end_headers()

        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, format: str, *args: object) -> None:
        logger.debug("Callback server: %s", format % args)


def _find_free_port() -> int:
    """Find and return a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _reuse_or_create_api_key(jwt_token: str, api_url: str) -> tuple[str, UserInfo]:
    """Return a valid API key, reusing the local keychain entry when possible.

    1. If the keychain already holds a key that the server accepts, return it.
    2. Otherwise, create a fresh key (the server stores only the hash, so the
       raw key is available only at creation time).

    Returns (raw_api_key, user_info).
    """
    existing_key = load_api_key()
    if existing_key:
        try:
            user_info = await validate_api_key(existing_key, api_url)
            logger.debug("Reusing existing CLI API key from keychain")
            return existing_key, user_info
        except AuthError:
            logger.debug("Existing keychain key is invalid; will create a new one")

    cookies = {"access_token": jwt_token}
    async with httpx.AsyncClient(base_url=api_url, timeout=10.0, cookies=cookies) as client:
        user_resp = await client.get("/api/users/me")
        if user_resp.status_code != 200:
            raise AuthError(f"Failed to fetch user info (status {user_resp.status_code})")
        user_data = user_resp.json()

        key_resp = await client.post("/api/keys", json={"name": _CLI_API_KEY_NAME})
        if key_resp.status_code != 201:
            raise AuthError(f"Failed to create API key (status {key_resp.status_code})")
        key_data = key_resp.json()

    user_info = UserInfo(
        id=user_data["id"],
        email=user_data["email"],
        name=user_data["name"],
        avatar_url=user_data.get("avatar_url"),
        org_name=user_data.get("org_name"),
    )
    return key_data["raw_key"], user_info


async def browser_login(
    api_url: str | None = None,
    frontend_url: str | None = None,
    timeout_seconds: int = 120,
) -> tuple[str, UserInfo]:
    """Run the full browser OAuth flow.

    1. Start a local HTTP server on a random port.
    2. Open the browser to the CollabMark CLI login page.
    3. User authenticates via Google or SSO in the browser.
    4. Frontend detects login, redirects to backend /api/auth/cli/complete.
    5. Backend relays JWT to the CLI's local server.
    6. CLI captures the token, redirects browser to /cli-login?status=success.
    7. CLI exchanges JWT for a persistent API key.
    8. API key is stored in the OS keychain.

    Returns (api_key, user_info).
    Raises AuthError on failure or timeout.
    """
    base = api_url or get_api_url()
    frontend = frontend_url or get_frontend_url()
    port = _find_free_port()
    login_url = f"{frontend}/cli-login?port={port}"

    _CallbackHandler.token = None
    _CallbackHandler.frontend_url = frontend
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        webbrowser.open(login_url)

        elapsed = 0
        poll_interval = 0.5
        while _CallbackHandler.token is None and elapsed < timeout_seconds:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        if _CallbackHandler.token is None:
            raise AuthError(
                f"Login timed out after {timeout_seconds}s. Please try again or use --api-key for manual login."
            )

        jwt_token = _CallbackHandler.token

        raw_api_key, user_info = await _reuse_or_create_api_key(jwt_token, base)
        save_api_key(raw_api_key)
        return raw_api_key, user_info

    finally:
        server.shutdown()
        server_thread.join(timeout=2)
