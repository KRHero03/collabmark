"""Tests for collabmark.commands.login — registry cleanup on login."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from collabmark.commands.login import login
from collabmark.lib.registry import load_registry, mark_stopped, register_sync


def _make_user_info(name: str = "Test User", email: str = "test@example.com"):
    info = MagicMock()
    info.name = name
    info.email = email
    return info


class TestLoginPrunesRegistry:
    def test_prunes_dead_entries_after_browser_login(self, tmp_path: Path) -> None:
        runner = CliRunner()
        user_info = _make_user_info()
        mock_browser = AsyncMock(return_value=("cm_test_key_123", user_info))

        with (
            patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}),
            patch("collabmark.commands.login.browser_login", mock_browser),
            patch("collabmark.commands.login.save_metadata"),
        ):
            register_sync(str(tmp_path / "proj"), "f1", "Proj", "http://x", "old@x.com", pid=999999999)
            mark_stopped(str(tmp_path / "proj"))
            result = runner.invoke(login)

        assert result.exit_code == 0
        assert "Cleaned up" in result.output
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}):
            reg = load_registry()
        assert len(reg.syncs) == 0

    def test_prunes_dead_entries_after_api_key_login(self, tmp_path: Path) -> None:
        runner = CliRunner()
        user_info = _make_user_info()
        mock_validate = AsyncMock(return_value=user_info)

        with (
            patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}),
            patch("collabmark.commands.login.validate_api_key", mock_validate),
            patch("collabmark.commands.login.save_api_key"),
            patch("collabmark.commands.login.save_metadata"),
        ):
            register_sync(str(tmp_path / "proj"), "f1", "Proj", "http://x", "old@x.com", pid=999999999)
            mark_stopped(str(tmp_path / "proj"))
            result = runner.invoke(login, ["--api-key", "cm_test123"])

        assert result.exit_code == 0
        assert "Cleaned up" in result.output
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}):
            reg = load_registry()
        assert len(reg.syncs) == 0

    def test_no_cleanup_message_when_registry_empty(self, tmp_path: Path) -> None:
        runner = CliRunner()
        user_info = _make_user_info()
        mock_browser = AsyncMock(return_value=("cm_key", user_info))

        with (
            patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}),
            patch("collabmark.commands.login.browser_login", mock_browser),
            patch("collabmark.commands.login.save_metadata"),
        ):
            result = runner.invoke(login)

        assert result.exit_code == 0
        assert "Cleaned up" not in result.output

    def test_keeps_running_entries(self, tmp_path: Path) -> None:
        runner = CliRunner()
        user_info = _make_user_info()
        mock_browser = AsyncMock(return_value=("cm_key", user_info))

        with (
            patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}),
            patch("collabmark.commands.login.browser_login", mock_browser),
            patch("collabmark.commands.login.save_metadata"),
            patch("collabmark.lib.registry._is_pid_alive", return_value=True),
        ):
            register_sync(str(tmp_path / "proj"), "f1", "Proj", "http://x", "t@t.com", pid=88888)
            result = runner.invoke(login)

        assert result.exit_code == 0
        with (
            patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}),
            patch("collabmark.lib.registry._is_pid_alive", return_value=True),
        ):
            reg = load_registry()
        assert len(reg.syncs) == 1
