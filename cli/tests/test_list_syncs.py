"""Tests for collabmark.commands.list_syncs — list all syncs command."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from collabmark.commands.list_syncs import list_syncs
from collabmark.lib.registry import register_sync


class TestListSyncsCommand:
    def test_shows_empty_state(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
            result = runner.invoke(list_syncs)
        assert result.exit_code == 0
        assert "No syncs registered" in result.output

    def test_shows_registered_syncs(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
            register_sync("/tmp/docs", "f1", "Docs", "http://x", "user@test.com", pid=999999999)
            register_sync("/tmp/notes", "f2", "Notes", "http://x", "user@test.com", pid=os.getpid())
            result = runner.invoke(list_syncs)
        assert result.exit_code == 0
        assert "Docs" in result.output
        assert "Notes" in result.output
