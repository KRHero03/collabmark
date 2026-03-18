"""Tests for collabmark.commands.status — sync status display."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from collabmark.commands.status import status
from collabmark.lib.config import init_project
from collabmark.lib.registry import register_sync
from collabmark.types import SyncConfig


class TestGlobalStatus:
    def test_shows_no_syncs_message(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
            result = runner.invoke(status)
        assert result.exit_code == 0
        assert "No syncs registered" in result.output

    def test_shows_table_with_registered_syncs(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
            register_sync("/tmp/notes", "f1", "Notes", "http://localhost:8000", "user@test.com", pid=os.getpid())
            result = runner.invoke(status)
        assert result.exit_code == 0
        assert "Notes" in result.output
        assert "Running" in result.output

    def test_shows_multiple_syncs(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
            register_sync("/tmp/a", "f1", "Alpha", "http://x", "a@a.com", pid=999999999)
            register_sync("/tmp/b", "f2", "Beta", "http://x", "b@b.com", pid=os.getpid())
            result = runner.invoke(status)
        assert result.exit_code == 0
        assert "Alpha" in result.output
        assert "Beta" in result.output


class TestProjectStatus:
    def test_shows_project_detail(self, tmp_path: Path) -> None:
        cli_home = tmp_path / "home"
        project_dir = tmp_path / "notes"
        project_dir.mkdir()

        config = SyncConfig(
            server_url="http://x",
            folder_id="f1",
            folder_name="Notes",
            user_id="u1",
            user_email="e@e.com",
            local_path=str(project_dir.resolve()),
        )

        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(cli_home)}):
            init_project("f1", config)
            register_sync(str(project_dir), "f1", "Notes", "http://x", "e@e.com")
            result = runner.invoke(status, ["--path", str(project_dir)])
        assert result.exit_code == 0
        assert "Notes" in result.output
        assert "0 synced" in result.output

    def test_shows_no_sync_for_empty_dir(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path / "home")}):
            result = runner.invoke(status, ["--path", str(tmp_path)])
        assert result.exit_code == 0
        assert "No active sync found" in result.output
