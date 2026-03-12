"""Authentication: credential storage, validation, and orchestration.

API keys are stored in the OS keychain via the ``keyring`` library
(macOS Keychain, Linux Secret Service, Windows Credential Locker).

Non-sensitive metadata (email, server URL) is kept in
``~/.collabmark/credentials.json`` for quick display without a network call.

The API key is sent via the ``X-API-Key`` header on every request.
"""

from __future__ import annotations

import json
import logging
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
import keyring
from keyring.errors import NoKeyringError, PasswordDeleteError

from collabmark.lib.config import API_KEY_HEADER, get_api_url, get_credentials_path

logger = logging.getLogger(__name__)

_KEYRING_SERVICE = "collabmark-cli"
_KEYRING_USERNAME = "api_key"
_METADATA_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR  # 0o600


@dataclass(frozen=True)
class UserInfo:
    """Authenticated user profile returned by the server."""

    id: str
    email: str
    name: str
    avatar_url: Optional[str] = None
    org_name: Optional[str] = None


class AuthError(Exception):
    """Raised when authentication fails."""


class KeyringUnavailableError(AuthError):
    """Raised when no secure keyring backend is available."""


# ---------------------------------------------------------------------------
# API key storage (OS keychain)
# ---------------------------------------------------------------------------


def save_api_key(api_key: str) -> None:
    """Store the API key in the OS keychain.

    Raises ``KeyringUnavailableError`` if no secure backend is found.
    """
    try:
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, api_key)
    except NoKeyringError as exc:
        raise KeyringUnavailableError(
            "No secure credential storage backend found.\n"
            "On macOS this should work out of the box (Keychain).\n"
            "On Linux, install gnome-keyring or kwallet.\n"
            "See: https://pypi.org/project/keyring/"
        ) from exc


def load_api_key() -> str | None:
    """Retrieve the API key from the OS keychain. Returns ``None`` if absent."""
    try:
        return keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
    except NoKeyringError:
        logger.debug("No keyring backend available; cannot load API key")
        return None


def _delete_keyring_entry() -> bool:
    """Remove the API key from the OS keychain. Returns True if removed."""
    try:
        keyring.delete_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
        return True
    except PasswordDeleteError:
        return False
    except NoKeyringError:
        return False


# ---------------------------------------------------------------------------
# Metadata storage (non-sensitive JSON file)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoginMetadata:
    """Non-sensitive info persisted locally for display purposes."""

    email: str
    name: str
    server_url: str | None = None


def save_metadata(
    metadata: LoginMetadata,
    credentials_path: Path | None = None,
) -> Path:
    """Write non-sensitive login metadata to ``~/.collabmark/credentials.json``."""
    path = credentials_path or get_credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {"email": metadata.email, "name": metadata.name}
    if metadata.server_url:
        payload["server_url"] = metadata.server_url

    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, _METADATA_FILE_MODE)
    return path


def load_metadata(credentials_path: Path | None = None) -> LoginMetadata | None:
    """Read stored login metadata. Returns ``None`` if absent or corrupt."""
    path = credentials_path or get_credentials_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return LoginMetadata(
            email=data["email"],
            name=data["name"],
            server_url=data.get("server_url"),
        )
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def _delete_metadata(credentials_path: Path | None = None) -> bool:
    """Remove the metadata file. Returns True if a file was deleted."""
    path = credentials_path or get_credentials_path()
    if path.exists():
        path.unlink()
        return True
    return False


# ---------------------------------------------------------------------------
# Combined operations
# ---------------------------------------------------------------------------


def clear_credentials(credentials_path: Path | None = None) -> bool:
    """Remove API key from keychain and metadata file from disk.

    Returns True if at least one of keyring entry or metadata file was removed.
    """
    keyring_removed = _delete_keyring_entry()
    metadata_removed = _delete_metadata(credentials_path)
    return keyring_removed or metadata_removed


# ---------------------------------------------------------------------------
# Validation (network)
# ---------------------------------------------------------------------------


async def validate_api_key(api_key: str, api_url: str | None = None) -> UserInfo:
    """Validate an API key against the server and return user info.

    Raises ``AuthError`` on invalid key or network failure.
    """
    base = api_url or get_api_url()
    async with httpx.AsyncClient(base_url=base, timeout=10.0) as client:
        try:
            resp = await client.get(
                "/api/users/me",
                headers={API_KEY_HEADER: api_key},
            )
        except httpx.HTTPError as exc:
            raise AuthError(f"Cannot reach CollabMark server at {base}: {exc}") from exc

    if resp.status_code == 401:
        raise AuthError("Invalid API key. Please check your key and try again.")
    if resp.status_code != 200:
        raise AuthError(f"Server returned unexpected status {resp.status_code}")

    data = resp.json()
    return UserInfo(
        id=data["id"],
        email=data["email"],
        name=data["name"],
        avatar_url=data.get("avatar_url"),
        org_name=data.get("org_name"),
    )


async def ensure_authenticated(
    credentials_path: Path | None = None,
    api_url: str | None = None,
) -> tuple[str, UserInfo]:
    """Return (api_key, user_info) from stored credentials.

    Raises ``AuthError`` if no credentials are stored or they are invalid.
    """
    api_key = load_api_key()
    if not api_key:
        raise AuthError("Not logged in. Run [bold]collabmark login[/bold] first.")
    user_info = await validate_api_key(api_key, api_url)
    return api_key, user_info


def mask_api_key(api_key: str) -> str:
    """Return a masked version of the API key for safe display."""
    if len(api_key) <= 8:
        return "****"
    return api_key[:6] + "..." + api_key[-4:]
