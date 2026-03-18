"""Tests for collabmark.commands.logs — log viewing command."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from collabmark.commands.logs import logs


def _write_log_entries(log_file: Path, entries: list[dict]) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e) for e in entries]
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestNoLogs:
    def test_shows_no_log_file_message(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
            result = runner.invoke(logs)
        assert result.exit_code == 0
        assert "No log file found" in result.output


class TestPerProjectLogs:
    def test_shows_project_log(self, tmp_path: Path) -> None:
        log_file = tmp_path / "logs" / "folder_abc.log"
        _write_log_entries(
            log_file,
            [
                {"ts": "2025-01-01T10:00:00", "level": "INFO", "logger": "test", "message": "hello"},
                {"ts": "2025-01-01T10:01:00", "level": "INFO", "logger": "test", "message": "world"},
            ],
        )

        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
            result = runner.invoke(logs, ["--folder", "folder_abc"])
        assert result.exit_code == 0
        assert "hello" in result.output
        assert "world" in result.output

    def test_missing_folder_log(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
            result = runner.invoke(logs, ["--folder", "nonexistent"])
        assert result.exit_code == 0
        assert "No log file" in result.output


class TestLogLines:
    def test_limits_output_lines(self, tmp_path: Path) -> None:
        log_file = tmp_path / "logs" / "folder_abc.log"
        entries = [
            {"ts": f"2025-01-01T10:{i:02d}:00", "level": "INFO", "logger": "test", "message": f"line-{i}"}
            for i in range(20)
        ]
        _write_log_entries(log_file, entries)

        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
            result = runner.invoke(logs, ["--folder", "folder_abc", "-n", "5"])
        assert result.exit_code == 0
        assert "line-15" in result.output
        assert "line-19" in result.output
        assert "line-0" not in result.output


class TestAllSyncsLogs:
    def test_interleaves_multiple_logs(self, tmp_path: Path) -> None:
        log_a = tmp_path / "logs" / "folder_a.log"
        log_b = tmp_path / "logs" / "folder_b.log"
        _write_log_entries(
            log_a,
            [
                {"ts": "2025-01-01T10:00:00", "level": "INFO", "logger": "a", "message": "alpha"},
                {"ts": "2025-01-01T10:02:00", "level": "INFO", "logger": "a", "message": "alpha2"},
            ],
        )
        _write_log_entries(
            log_b,
            [
                {"ts": "2025-01-01T10:01:00", "level": "INFO", "logger": "b", "message": "beta"},
            ],
        )

        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
            result = runner.invoke(logs, ["--all-syncs"])
        assert result.exit_code == 0
        assert "alpha" in result.output
        assert "beta" in result.output
        assert "alpha2" in result.output

    def test_empty_all_syncs(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
            result = runner.invoke(logs, ["--all-syncs"])
        assert result.exit_code == 0
        assert "No log files found" in result.output
