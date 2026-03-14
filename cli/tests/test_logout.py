"""Tests for collabmark.commands.logout — registry cleanup on logout."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from collabmark.commands.logout import logout
from collabmark.lib.registry import load_registry, mark_stopped, register_sync


class TestLogoutStopsSyncs:
    def test_stops_running_syncs_on_logout(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with (
            patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}),
            patch("collabmark.lib.registry._is_pid_alive", return_value=True),
            patch("os.kill"),
            patch("collabmark.lib.daemon.remove_pid_file"),
            patch("collabmark.commands.logout.clear_credentials", return_value=True),
        ):
            register_sync(str(tmp_path / "proj"), "f1", "Proj", "http://x", "t@t.com", pid=88888)
            result = runner.invoke(logout)

        assert result.exit_code == 0
        assert "Stopped 1/1" in result.output

    def test_cleans_stale_entries_on_logout(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with (
            patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}),
            patch("collabmark.commands.logout.clear_credentials", return_value=True),
        ):
            register_sync(str(tmp_path / "proj"), "f1", "Proj", "http://x", "t@t.com", pid=999999999)
            mark_stopped(str(tmp_path / "proj"))
            result = runner.invoke(logout)

        assert result.exit_code == 0
        assert "Cleaned 1 stale" in result.output
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}):
            reg = load_registry()
        assert len(reg.syncs) == 0

    def test_handles_no_syncs(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with (
            patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}),
            patch("collabmark.commands.logout.clear_credentials", return_value=True),
        ):
            result = runner.invoke(logout)

        assert result.exit_code == 0
        assert "You are logged out" in result.output

    def test_handles_no_credentials(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with (
            patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}),
            patch("collabmark.commands.logout.clear_credentials", return_value=False),
        ):
            result = runner.invoke(logout)

        assert result.exit_code == 0
        assert "No stored credentials found" in result.output
        assert "You are logged out" in result.output

    def test_stops_multiple_syncs(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with (
            patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}),
            patch("collabmark.lib.registry._is_pid_alive", return_value=True),
            patch("os.kill"),
            patch("collabmark.lib.daemon.remove_pid_file"),
            patch("collabmark.commands.logout.clear_credentials", return_value=True),
        ):
            register_sync(str(tmp_path / "a"), "f1", "A", "http://x", "t@t.com", pid=88888)
            register_sync(str(tmp_path / "b"), "f2", "B", "http://x", "t@t.com", pid=88889)
            result = runner.invoke(logout)

        assert result.exit_code == 0
        assert "Stopped 2/2" in result.output
