"""Tests for collabmark.commands.start — the main start command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from collabmark.commands.start import (
    _extract_folder_id_from_link,
    _print_sync_summary,
    _resolve_folder,
    start,
)
from collabmark.lib.auth import UserInfo
from collabmark.lib.config import init_project, load_sync_config
from collabmark.lib.sync_engine import ActionKind, SyncAction
from collabmark.types import FolderInfo, SyncConfig

# ===================================================================
# Link parsing
# ===================================================================


class TestExtractFolderIdFromLink:
    def test_bare_id(self) -> None:
        assert _extract_folder_id_from_link("abc123") == "abc123"

    def test_full_url_with_folder_path(self) -> None:
        url = "https://app.collabmark.io/folder/abc123"
        assert _extract_folder_id_from_link(url) == "abc123"

    def test_url_with_trailing_slash(self) -> None:
        url = "https://app.collabmark.io/folder/abc123/"
        assert _extract_folder_id_from_link(url) == "abc123"

    def test_url_without_folder_segment(self) -> None:
        url = "https://app.collabmark.io/share/xyz789"
        assert _extract_folder_id_from_link(url) == "xyz789"


# ===================================================================
# Sync summary
# ===================================================================


class TestPrintSyncSummary:
    def test_no_actions(self, capsys) -> None:
        _print_sync_summary([])

    def test_mixed_actions(self, capsys) -> None:
        actions = [
            SyncAction(ActionKind.PUSH_NEW, "a.md"),
            SyncAction(ActionKind.PUSH_NEW, "b.md"),
            SyncAction(ActionKind.PULL_NEW, "c.md"),
            SyncAction(ActionKind.CONFLICT, "d.md"),
        ]
        _print_sync_summary(actions)


# ===================================================================
# Start command CLI integration
# ===================================================================


class TestStartCommand:
    def test_help_text(self) -> None:
        runner = CliRunner()
        result = runner.invoke(start, ["--help"])
        assert result.exit_code == 0
        assert "Start syncing markdown files" in result.output

    def test_shows_daemon_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(start, ["--help"])
        assert "--daemon" in result.output
        assert "-d" in result.output

    def test_shows_path_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(start, ["--help"])
        assert "--path" in result.output

    def test_shows_interval_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(start, ["--help"])
        assert "--interval" in result.output

    @patch("collabmark.commands.start._start_async")
    def test_invokes_async_start(self, mock_start: MagicMock) -> None:
        mock_start.return_value = None
        runner = CliRunner()

        async def noop(*args):
            pass

        mock_start.side_effect = noop

        with patch("collabmark.commands.start.asyncio") as mock_asyncio:
            mock_asyncio.run = MagicMock()
            runner.invoke(start, [])
            mock_asyncio.run.assert_called_once()

    @patch("collabmark.commands.start._launch_daemon")
    def test_daemon_flag_calls_launch_daemon(self, mock_launch: MagicMock) -> None:
        runner = CliRunner()
        runner.invoke(start, ["-d"])
        mock_launch.assert_called_once()


# ===================================================================
# Resume detection
# ===================================================================

_FAKE_USER = UserInfo(id="u1", email="test@test.com", name="Test User")


class TestResumeDetection:
    @pytest.mark.asyncio
    async def test_resumes_from_existing_config(self, tmp_path) -> None:
        config = SyncConfig(
            server_url="http://localhost:8000",
            folder_id="f_existing",
            folder_name="My Folder",
            user_id="u1",
            user_email="test@test.com",
        )
        init_project(tmp_path, config)

        mock_client = AsyncMock()
        folder_id, folder_name = await _resolve_folder(mock_client, tmp_path, None, _FAKE_USER)

        assert folder_id == "f_existing"
        assert folder_name == "My Folder"
        mock_client.list_folder_contents.assert_not_called()

    @pytest.mark.asyncio
    async def test_link_overrides_when_no_existing_config(self, tmp_path) -> None:
        mock_client = AsyncMock()
        mock_client.get_folder.return_value = FolderInfo(id="f_link", name="Linked Folder", owner_id="u1")

        folder_id, folder_name = await _resolve_folder(mock_client, tmp_path, "f_link", _FAKE_USER)

        assert folder_id == "f_link"
        assert folder_name == "Linked Folder"

    @pytest.mark.asyncio
    async def test_link_config_stores_user_info(self, tmp_path) -> None:
        mock_client = AsyncMock()
        mock_client.get_folder.return_value = FolderInfo(id="f1", name="F1", owner_id="u1")

        await _resolve_folder(mock_client, tmp_path, "f1", _FAKE_USER)

        config = load_sync_config(tmp_path / ".collabmark")
        assert config is not None
        assert config.user_id == "u1"
        assert config.user_email == "test@test.com"
