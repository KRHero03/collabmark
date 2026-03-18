"""Tests for collabmark.commands.stop — sync stop command."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from collabmark.commands.stop import stop
from collabmark.lib.registry import load_registry, register_sync


class TestStopNoSyncs:
    def test_shows_no_syncs_message(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
            result = runner.invoke(stop)
        assert result.exit_code == 0
        assert "No syncs are currently running" in result.output


class TestStopAll:
    def test_stops_all_running(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "proj_a"
        dir_b = tmp_path / "proj_b"
        dir_a.mkdir()
        dir_b.mkdir()

        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}):
            register_sync(str(dir_a), "f1", "Alpha", "http://x", "a@a.com", pid=999999999)
            register_sync(str(dir_b), "f2", "Beta", "http://x", "b@b.com", pid=999999998)
            result = runner.invoke(stop, ["--all"])
            assert result.exit_code == 0
            reg = load_registry()
            resolved_a = str(dir_a.resolve())
            resolved_b = str(dir_b.resolve())
            assert reg.syncs[resolved_a].status == "stopped"
            assert reg.syncs[resolved_b].status == "stopped"


class TestStopByPath:
    def test_reports_not_running(self, tmp_path: Path) -> None:
        project = tmp_path / "myproject"
        project.mkdir()
        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}):
            result = runner.invoke(stop, ["--path", str(project)])
        assert result.exit_code == 0
        assert "No sync found" in result.output


class TestInteractiveStop:
    def test_prompts_when_multiple_running(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "proj_a"
        dir_b = tmp_path / "proj_b"
        dir_a.mkdir()
        dir_b.mkdir()

        runner = CliRunner()
        with (
            patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}),
            patch("collabmark.lib.registry._is_pid_alive", return_value=True),
            patch("os.kill"),
            patch("collabmark.lib.daemon.remove_pid_file"),
        ):
            register_sync(str(dir_a), "f1", "Alpha", "http://x", "a@a.com", pid=88888)
            register_sync(str(dir_b), "f2", "Beta", "http://x", "b@b.com", pid=88889)
            result = runner.invoke(stop, input="1\n")
        assert result.exit_code == 0
        assert "Choose which to stop" in result.output
