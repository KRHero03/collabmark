"""Tests for collabmark.lib.daemon — PID file management."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from collabmark.lib.daemon import (
    is_process_alive,
    read_pid,
    remove_pid_file,
    write_pid_file,
)


class TestPidFile:
    def test_write_and_read_pid(self, tmp_path: Path) -> None:
        with patch("collabmark.lib.daemon.get_pid_file", return_value=tmp_path / "test.pid"):
            write_pid_file(12345)
            assert read_pid() == 12345

    def test_write_uses_current_pid_by_default(self, tmp_path: Path) -> None:
        with patch("collabmark.lib.daemon.get_pid_file", return_value=tmp_path / "test.pid"):
            write_pid_file()
            assert read_pid() == os.getpid()

    def test_read_returns_none_when_missing(self, tmp_path: Path) -> None:
        with patch("collabmark.lib.daemon.get_pid_file", return_value=tmp_path / "missing.pid"):
            assert read_pid() is None

    def test_read_returns_none_on_corrupt_file(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "bad.pid"
        pid_file.write_text("not a number", encoding="utf-8")
        with patch("collabmark.lib.daemon.get_pid_file", return_value=pid_file):
            assert read_pid() is None

    def test_remove_pid_file(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("123", encoding="utf-8")
        with patch("collabmark.lib.daemon.get_pid_file", return_value=pid_file):
            assert remove_pid_file() is True
            assert not pid_file.exists()

    def test_remove_returns_false_when_missing(self, tmp_path: Path) -> None:
        with patch("collabmark.lib.daemon.get_pid_file", return_value=tmp_path / "nope.pid"):
            assert remove_pid_file() is False

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "deep" / "nested" / "test.pid"
        with patch("collabmark.lib.daemon.get_pid_file", return_value=pid_file):
            write_pid_file(99)
        assert pid_file.is_file()


class TestIsProcessAlive:
    def test_current_process_is_alive(self) -> None:
        assert is_process_alive(os.getpid()) is True

    def test_nonexistent_pid_is_not_alive(self) -> None:
        assert is_process_alive(999999999) is False
