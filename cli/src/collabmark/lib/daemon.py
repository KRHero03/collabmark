"""Daemon mode: PID file management and process lifecycle.

Provides helpers to write/read/check PID files so that ``collabmark status``
and ``collabmark stop`` can interact with a running daemon.
"""

from __future__ import annotations

import logging
import os
import signal
from pathlib import Path

from collabmark.lib.config import get_cli_home

logger = logging.getLogger(__name__)

_PID_FILE_NAME = "collabmark.pid"


def get_pid_file() -> Path:
    return get_cli_home() / _PID_FILE_NAME


def write_pid_file(pid: int | None = None) -> Path:
    """Write the current (or given) PID to the PID file."""
    pid_file = get_pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(pid or os.getpid()), encoding="utf-8")
    logger.debug("Wrote PID %d to %s", pid or os.getpid(), pid_file)
    return pid_file


def read_pid() -> int | None:
    """Read the PID from the PID file. Returns None if missing or invalid."""
    pid_file = get_pid_file()
    if not pid_file.is_file():
        return None
    try:
        return int(pid_file.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def remove_pid_file() -> bool:
    """Remove the PID file. Returns True if a file was removed."""
    pid_file = get_pid_file()
    if pid_file.is_file():
        pid_file.unlink()
        return True
    return False


def stop_daemon() -> bool:
    """Send SIGTERM to the running daemon. Returns True if signal was sent."""
    pid = read_pid()
    if pid is None:
        return False
    if not is_process_alive(pid):
        remove_pid_file()
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        logger.info("Sent SIGTERM to PID %d", pid)
        return True
    except OSError as exc:
        logger.warning("Failed to send SIGTERM to PID %d: %s", pid, exc)
        return False
