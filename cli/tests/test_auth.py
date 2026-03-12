"""Tests for collabmark.lib.auth — keyring credential storage and validation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx
from keyring.errors import NoKeyringError, PasswordDeleteError

from collabmark.lib.auth import (
    AuthError,
    KeyringUnavailableError,
    LoginMetadata,
    UserInfo,
    clear_credentials,
    ensure_authenticated,
    load_api_key,
    load_metadata,
    mask_api_key,
    save_api_key,
    save_metadata,
    validate_api_key,
)

FAKE_KEY = "cm_" + "a1b2c3d4" * 8
FAKE_USER_RESPONSE = {
    "id": "user123",
    "email": "pm@acme.com",
    "name": "Alice PM",
    "avatar_url": "https://example.com/avatar.png",
    "org_name": "Acme Corp",
}
API_BASE = "http://test-server:8000"


# ---------------------------------------------------------------------------
# API key storage via keyring
# ---------------------------------------------------------------------------


class TestSaveApiKey:
    @patch("collabmark.lib.auth.keyring")
    def test_stores_in_keyring(self, mock_keyring: MagicMock) -> None:
        save_api_key(FAKE_KEY)
        mock_keyring.set_password.assert_called_once_with("collabmark-cli", "api_key", FAKE_KEY)

    @patch("collabmark.lib.auth.keyring")
    def test_raises_on_no_keyring_backend(self, mock_keyring: MagicMock) -> None:
        mock_keyring.set_password.side_effect = NoKeyringError
        with pytest.raises(KeyringUnavailableError, match="No secure credential storage"):
            save_api_key(FAKE_KEY)


class TestLoadApiKey:
    @patch("collabmark.lib.auth.keyring")
    def test_loads_from_keyring(self, mock_keyring: MagicMock) -> None:
        mock_keyring.get_password.return_value = FAKE_KEY
        assert load_api_key() == FAKE_KEY
        mock_keyring.get_password.assert_called_once_with("collabmark-cli", "api_key")

    @patch("collabmark.lib.auth.keyring")
    def test_returns_none_when_not_stored(self, mock_keyring: MagicMock) -> None:
        mock_keyring.get_password.return_value = None
        assert load_api_key() is None

    @patch("collabmark.lib.auth.keyring")
    def test_returns_none_when_no_backend(self, mock_keyring: MagicMock) -> None:
        mock_keyring.get_password.side_effect = NoKeyringError
        assert load_api_key() is None


class TestKeyringRoundTrip:
    """Simulates a full save/load cycle using an in-memory dict as keyring."""

    def test_save_then_load(self) -> None:
        store: dict[tuple[str, str], str] = {}

        def fake_set(service: str, username: str, password: str) -> None:
            store[(service, username)] = password

        def fake_get(service: str, username: str) -> str | None:
            return store.get((service, username))

        with (
            patch("collabmark.lib.auth.keyring.set_password", side_effect=fake_set),
            patch("collabmark.lib.auth.keyring.get_password", side_effect=fake_get),
        ):
            save_api_key(FAKE_KEY)
            assert load_api_key() == FAKE_KEY

    def test_overwrite(self) -> None:
        store: dict[tuple[str, str], str] = {}

        def fake_set(service: str, username: str, password: str) -> None:
            store[(service, username)] = password

        def fake_get(service: str, username: str) -> str | None:
            return store.get((service, username))

        with (
            patch("collabmark.lib.auth.keyring.set_password", side_effect=fake_set),
            patch("collabmark.lib.auth.keyring.get_password", side_effect=fake_get),
        ):
            save_api_key("cm_old_key")
            save_api_key(FAKE_KEY)
            assert load_api_key() == FAKE_KEY


# ---------------------------------------------------------------------------
# Metadata storage (non-sensitive JSON)
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        creds = tmp_path / "credentials.json"
        meta = LoginMetadata(email="pm@acme.com", name="Alice PM", server_url="http://srv:8000")
        save_metadata(meta, credentials_path=creds)

        loaded = load_metadata(credentials_path=creds)
        assert loaded is not None
        assert loaded.email == "pm@acme.com"
        assert loaded.name == "Alice PM"
        assert loaded.server_url == "http://srv:8000"

    def test_metadata_file_contains_no_api_key(self, tmp_path: Path) -> None:
        creds = tmp_path / "credentials.json"
        meta = LoginMetadata(email="pm@acme.com", name="Alice PM")
        save_metadata(meta, credentials_path=creds)

        raw = json.loads(creds.read_text(encoding="utf-8"))
        assert "api_key" not in raw
        assert "key" not in raw
        assert "password" not in raw
        assert "secret" not in raw
        assert "token" not in raw

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / "credentials.json"
        meta = LoginMetadata(email="pm@acme.com", name="Alice PM")
        save_metadata(meta, credentials_path=nested)
        assert nested.exists()
        assert load_metadata(credentials_path=nested) is not None

    def test_load_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert load_metadata(credentials_path=tmp_path / "nope.json") is None

    def test_load_returns_none_on_corrupt_json(self, tmp_path: Path) -> None:
        creds = tmp_path / "credentials.json"
        creds.write_text("NOT JSON!!!", encoding="utf-8")
        assert load_metadata(credentials_path=creds) is None

    def test_load_returns_none_when_required_fields_missing(self, tmp_path: Path) -> None:
        creds = tmp_path / "credentials.json"
        creds.write_text('{"email": "pm@acme.com"}\n', encoding="utf-8")
        assert load_metadata(credentials_path=creds) is None

    def test_server_url_is_optional(self, tmp_path: Path) -> None:
        creds = tmp_path / "credentials.json"
        meta = LoginMetadata(email="pm@acme.com", name="Alice PM")
        save_metadata(meta, credentials_path=creds)

        loaded = load_metadata(credentials_path=creds)
        assert loaded is not None
        assert loaded.server_url is None


# ---------------------------------------------------------------------------
# clear_credentials (keyring + metadata)
# ---------------------------------------------------------------------------


class TestClearCredentials:
    @patch("collabmark.lib.auth.keyring")
    def test_clears_both_keyring_and_metadata(self, mock_keyring: MagicMock, tmp_path: Path) -> None:
        creds = tmp_path / "credentials.json"
        save_metadata(LoginMetadata(email="a@b.com", name="A"), credentials_path=creds)
        assert creds.exists()

        result = clear_credentials(credentials_path=creds)
        assert result is True
        mock_keyring.delete_password.assert_called_once_with("collabmark-cli", "api_key")
        assert not creds.exists()

    @patch("collabmark.lib.auth.keyring")
    def test_returns_true_when_only_keyring_has_entry(self, mock_keyring: MagicMock, tmp_path: Path) -> None:
        result = clear_credentials(credentials_path=tmp_path / "nope.json")
        assert result is True

    @patch("collabmark.lib.auth.keyring")
    def test_returns_false_when_nothing_to_clear(self, mock_keyring: MagicMock, tmp_path: Path) -> None:
        mock_keyring.delete_password.side_effect = PasswordDeleteError
        result = clear_credentials(credentials_path=tmp_path / "nope.json")
        assert result is False

    @patch("collabmark.lib.auth.keyring")
    def test_handles_no_keyring_backend_gracefully(self, mock_keyring: MagicMock, tmp_path: Path) -> None:
        mock_keyring.delete_password.side_effect = NoKeyringError
        creds = tmp_path / "credentials.json"
        save_metadata(LoginMetadata(email="a@b.com", name="A"), credentials_path=creds)

        result = clear_credentials(credentials_path=creds)
        assert result is True
        assert not creds.exists()


# ---------------------------------------------------------------------------
# API key validation (mocked HTTP)
# ---------------------------------------------------------------------------


class TestValidateApiKey:
    @pytest.mark.asyncio
    @respx.mock
    async def test_valid_key_returns_user_info(self) -> None:
        respx.get(f"{API_BASE}/api/users/me").mock(return_value=httpx.Response(200, json=FAKE_USER_RESPONSE))
        info = await validate_api_key(FAKE_KEY, api_url=API_BASE)
        assert isinstance(info, UserInfo)
        assert info.email == "pm@acme.com"
        assert info.name == "Alice PM"
        assert info.org_name == "Acme Corp"

    @pytest.mark.asyncio
    @respx.mock
    async def test_invalid_key_raises_auth_error(self) -> None:
        respx.get(f"{API_BASE}/api/users/me").mock(return_value=httpx.Response(401, json={"detail": "Invalid API key"}))
        with pytest.raises(AuthError, match="Invalid API key"):
            await validate_api_key("cm_bad_key", api_url=API_BASE)

    @pytest.mark.asyncio
    @respx.mock
    async def test_server_error_raises_auth_error(self) -> None:
        respx.get(f"{API_BASE}/api/users/me").mock(return_value=httpx.Response(500, text="Internal Server Error"))
        with pytest.raises(AuthError, match="unexpected status 500"):
            await validate_api_key(FAKE_KEY, api_url=API_BASE)

    @pytest.mark.asyncio
    @respx.mock
    async def test_network_error_raises_auth_error(self) -> None:
        respx.get(f"{API_BASE}/api/users/me").mock(side_effect=httpx.ConnectError("Connection refused"))
        with pytest.raises(AuthError, match="Cannot reach"):
            await validate_api_key(FAKE_KEY, api_url=API_BASE)

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_api_key_header(self) -> None:
        route = respx.get(f"{API_BASE}/api/users/me").mock(return_value=httpx.Response(200, json=FAKE_USER_RESPONSE))
        await validate_api_key(FAKE_KEY, api_url=API_BASE)
        assert route.called
        request = route.calls[0].request
        assert request.headers["X-API-Key"] == FAKE_KEY


# ---------------------------------------------------------------------------
# ensure_authenticated
# ---------------------------------------------------------------------------


class TestEnsureAuthenticated:
    @pytest.mark.asyncio
    @patch("collabmark.lib.auth.load_api_key", return_value=None)
    async def test_raises_when_no_credentials(self, _mock_load: MagicMock) -> None:
        with pytest.raises(AuthError, match="Not logged in"):
            await ensure_authenticated(api_url=API_BASE)

    @pytest.mark.asyncio
    @respx.mock
    @patch("collabmark.lib.auth.load_api_key", return_value=FAKE_KEY)
    async def test_returns_key_and_user_info(self, _mock_load: MagicMock) -> None:
        respx.get(f"{API_BASE}/api/users/me").mock(return_value=httpx.Response(200, json=FAKE_USER_RESPONSE))
        api_key, user_info = await ensure_authenticated(api_url=API_BASE)
        assert api_key == FAKE_KEY
        assert user_info.name == "Alice PM"

    @pytest.mark.asyncio
    @respx.mock
    @patch("collabmark.lib.auth.load_api_key", return_value=FAKE_KEY)
    async def test_raises_on_expired_key(self, _mock_load: MagicMock) -> None:
        respx.get(f"{API_BASE}/api/users/me").mock(return_value=httpx.Response(401, json={"detail": "Expired"}))
        with pytest.raises(AuthError, match="Invalid API key"):
            await ensure_authenticated(api_url=API_BASE)


# ---------------------------------------------------------------------------
# mask_api_key
# ---------------------------------------------------------------------------


class TestMaskApiKey:
    def test_masks_long_key(self) -> None:
        masked = mask_api_key(FAKE_KEY)
        assert masked.startswith("cm_a1b")
        assert masked.endswith("c3d4")
        assert "..." in masked
        assert len(masked) < len(FAKE_KEY)

    def test_masks_short_key(self) -> None:
        assert mask_api_key("short") == "****"

    def test_masks_exactly_8_chars(self) -> None:
        assert mask_api_key("12345678") == "****"

    def test_masks_9_chars(self) -> None:
        masked = mask_api_key("123456789")
        assert masked == "123456...6789"
