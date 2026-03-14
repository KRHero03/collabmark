"""Tests for collabmark.lib.daemon — PID file management and daemonization."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from collabmark.lib.daemon import (
    daemonize,
    get_pid_file,
    is_process_alive,
    list_all_pids,
    read_pid,
    remove_pid_file,
    write_pid_file,
)


@pytest.fixture()
def daemon_home(tmp_path: Path):
    """Point COLLABMARK_HOME to a temp dir for isolated daemon tests."""
    with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
        yield tmp_path


class TestPidFile:
    def test_write_and_read_pid(self, daemon_home: Path) -> None:
        write_pid_file(12345, folder_id="folder_a")
        assert read_pid(folder_id="folder_a") == 12345

    def test_write_uses_current_pid_by_default(self, daemon_home: Path) -> None:
        write_pid_file(folder_id="folder_a")
        assert read_pid(folder_id="folder_a") == os.getpid()

    def test_read_returns_none_when_missing(self, daemon_home: Path) -> None:
        assert read_pid(folder_id="nonexistent") is None

    def test_read_returns_none_on_corrupt_file(self, daemon_home: Path) -> None:
        pid_file = daemon_home / "pids" / "bad.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("not a number", encoding="utf-8")
        assert read_pid(folder_id="bad") is None

    def test_remove_pid_file(self, daemon_home: Path) -> None:
        write_pid_file(123, folder_id="folder_a")
        assert remove_pid_file(folder_id="folder_a") is True
        assert read_pid(folder_id="folder_a") is None

    def test_remove_returns_false_when_missing(self, daemon_home: Path) -> None:
        assert remove_pid_file(folder_id="missing") is False

    def test_creates_parent_directories(self, daemon_home: Path) -> None:
        write_pid_file(99, folder_id="deep_folder")
        pid_file = daemon_home / "pids" / "deep_folder.pid"
        assert pid_file.is_file()


class TestGetPidFile:
    def test_with_folder_id(self, daemon_home: Path) -> None:
        path = get_pid_file("my_folder")
        assert path == daemon_home / "pids" / "my_folder.pid"

    def test_without_folder_id_legacy(self, daemon_home: Path) -> None:
        path = get_pid_file()
        assert path == daemon_home / "collabmark.pid"


class TestListAllPids:
    def test_lists_multiple_pid_files(self, daemon_home: Path) -> None:
        write_pid_file(100, folder_id="folder_a")
        write_pid_file(200, folder_id="folder_b")
        pids = list_all_pids()
        pids_dict = dict(pids)
        assert pids_dict["folder_a"] == 100
        assert pids_dict["folder_b"] == 200

    def test_returns_empty_when_no_pids_dir(self, daemon_home: Path) -> None:
        assert list_all_pids() == []

    def test_skips_corrupt_pid_files(self, daemon_home: Path) -> None:
        pids_dir = daemon_home / "pids"
        pids_dir.mkdir(parents=True, exist_ok=True)
        (pids_dir / "good.pid").write_text("42", encoding="utf-8")
        (pids_dir / "bad.pid").write_text("xyz", encoding="utf-8")
        pids = list_all_pids()
        pids_dict = dict(pids)
        assert "good" in pids_dict
        assert "bad" not in pids_dict


class TestIsProcessAlive:
    def test_current_process_is_alive(self) -> None:
        assert is_process_alive(os.getpid()) is True

    def test_nonexistent_pid_is_not_alive(self) -> None:
        assert is_process_alive(999999999) is False


class TestDaemonize:
    def test_skips_on_windows(self) -> None:
        with patch.object(sys, "platform", "win32"):
            daemonize()

    def test_calls_double_fork(self) -> None:
        fork_calls = []

        def mock_fork():
            fork_calls.append(1)
            return 0

        with (
            patch("collabmark.lib.daemon.os.fork", side_effect=mock_fork),
            patch("collabmark.lib.daemon.os.setsid"),
            patch("collabmark.lib.daemon.os.open", return_value=3),
            patch("collabmark.lib.daemon.os.dup2"),
            patch("collabmark.lib.daemon.os.close"),
            patch("collabmark.lib.daemon.sys.stdin") as mock_stdin,
            patch("collabmark.lib.daemon.sys.stdout") as mock_stdout,
            patch("collabmark.lib.daemon.sys.stderr") as mock_stderr,
        ):
            mock_stdin.fileno.return_value = 0
            mock_stdout.fileno.return_value = 1
            mock_stderr.fileno.return_value = 2
            daemonize()
            assert len(fork_calls) == 2

    def test_parent_exits_on_first_fork(self) -> None:
        class _ParentExit(SystemExit):
            pass

        with (
            patch("collabmark.lib.daemon.os.fork", return_value=42),
            patch("collabmark.lib.daemon.os._exit", side_effect=_ParentExit(0)),
            pytest.raises(_ParentExit),
        ):
            daemonize()
