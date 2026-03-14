"""Tests for collabmark.commands.clean — registry cleanup command."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from collabmark.commands.clean import clean
from collabmark.lib.registry import load_registry, register_sync


class TestCleanEmpty:
    def test_shows_no_syncs_message(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
            result = runner.invoke(clean)
        assert result.exit_code == 0
        assert "No syncs registered" in result.output


class TestCleanAll:
    def test_removes_all_stopped_entries(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "proj_a"
        dir_b = tmp_path / "proj_b"
        dir_a.mkdir()
        dir_b.mkdir()

        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}):
            register_sync(str(dir_a), "f1", "Alpha", "http://x", "a@a.com", pid=999999999)
            register_sync(str(dir_b), "f2", "Beta", "http://x", "b@b.com", pid=999999998)
            result = runner.invoke(clean, ["--all"])
            assert result.exit_code == 0
            reg = load_registry()
            assert len(reg.syncs) == 0
            assert "Removed" in result.output

    def test_skips_running_syncs_without_force(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "proj_a"
        dir_b = tmp_path / "proj_b"
        dir_a.mkdir()
        dir_b.mkdir()

        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}):
            register_sync(str(dir_a), "f1", "Alpha", "http://x", "a@a.com", pid=os.getpid())
            register_sync(str(dir_b), "f2", "Beta", "http://x", "b@b.com", pid=999999998)
            result = runner.invoke(clean, ["--all"])
            assert result.exit_code == 0
            reg = load_registry()
            assert len(reg.syncs) == 1


class TestCleanForce:
    def test_removes_running_syncs_too(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "proj_a"
        dir_a.mkdir()

        runner = CliRunner()
        with (
            patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}),
            patch("collabmark.lib.registry._is_pid_alive", return_value=True),
        ):
            register_sync(str(dir_a), "f1", "Alpha", "http://x", "a@a.com", pid=88888)
            result = runner.invoke(clean, ["--force"])
            assert result.exit_code == 0
            reg = load_registry()
            assert len(reg.syncs) == 0


class TestCleanInteractive:
    def test_single_stale_entry_removed_directly(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "proj_a"
        dir_a.mkdir()

        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}):
            register_sync(str(dir_a), "f1", "Alpha", "http://x", "a@a.com", pid=999999999)
            result = runner.invoke(clean)
            assert result.exit_code == 0
            assert "Removed" in result.output
            reg = load_registry()
            assert len(reg.syncs) == 0

    def test_multiple_entries_shows_picker(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "proj_a"
        dir_b = tmp_path / "proj_b"
        dir_a.mkdir()
        dir_b.mkdir()

        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}):
            register_sync(str(dir_a), "f1", "Alpha", "http://x", "a@a.com", pid=999999999)
            register_sync(str(dir_b), "f2", "Beta", "http://x", "b@b.com", pid=999999998)
            result = runner.invoke(clean, input="1\n")
            assert result.exit_code == 0
            assert "Stale entries" in result.output
            reg = load_registry()
            assert len(reg.syncs) == 1

    def test_no_stale_when_all_running(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "proj_a"
        dir_a.mkdir()

        runner = CliRunner()
        with (
            patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}),
            patch("collabmark.lib.registry._is_pid_alive", return_value=True),
        ):
            register_sync(str(dir_a), "f1", "Alpha", "http://x", "a@a.com", pid=88888)
            result = runner.invoke(clean)
            assert result.exit_code == 0
            assert "No stale entries" in result.output
