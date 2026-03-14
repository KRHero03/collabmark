"""Daemon mode: PID file management, process lifecycle, and daemonization.

PID files are stored per-project at ``~/.collabmark/pids/{folder_id}.pid``
so multiple syncs can run simultaneously.  The ``daemonize()`` function
uses the standard Unix double-fork pattern to fully detach the process
from the controlling terminal.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

from collabmark.lib.config import get_cli_home

logger = logging.getLogger(__name__)

_PIDS_DIR = "pids"
_LEGACY_PID_FILE = "collabmark.pid"


def _pids_dir() -> Path:
    return get_cli_home() / _PIDS_DIR


def get_pid_file(folder_id: str | None = None) -> Path:
    """Return the PID file path for a given folder_id.

    Falls back to the legacy single-file location when no folder_id
    is provided (backward compat for old ``stop``/``status`` callers).
    """
    if folder_id:
        return _pids_dir() / f"{folder_id}.pid"
    return get_cli_home() / _LEGACY_PID_FILE


def write_pid_file(pid: int | None = None, folder_id: str | None = None) -> Path:
    """Write the current (or given) PID to the project's PID file."""
    pid_file = get_pid_file(folder_id)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(pid or os.getpid()), encoding="utf-8")
    logger.debug("Wrote PID %d to %s", pid or os.getpid(), pid_file)
    return pid_file


def read_pid(folder_id: str | None = None) -> int | None:
    """Read the PID for a project. Returns None if missing or invalid."""
    pid_file = get_pid_file(folder_id)
    if not pid_file.is_file():
        if not folder_id:
            return _try_legacy_pid()
        return None
    try:
        return int(pid_file.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _try_legacy_pid() -> int | None:
    """Check the legacy single-PID file as a fallback."""
    legacy = get_cli_home() / _LEGACY_PID_FILE
    if not legacy.is_file():
        return None
    try:
        return int(legacy.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def remove_pid_file(folder_id: str | None = None) -> bool:
    """Remove the PID file. Returns True if a file was removed."""
    pid_file = get_pid_file(folder_id)
    if pid_file.is_file():
        pid_file.unlink()
        return True
    return False


def stop_daemon(folder_id: str | None = None) -> bool:
    """Send SIGTERM to a running daemon. Returns True if signal was sent."""
    pid = read_pid(folder_id)
    if pid is None:
        return False
    if not is_process_alive(pid):
        remove_pid_file(folder_id)
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        logger.info("Sent SIGTERM to PID %d", pid)
        return True
    except OSError as exc:
        logger.warning("Failed to send SIGTERM to PID %d: %s", pid, exc)
        return False


def list_all_pids() -> list[tuple[str, int]]:
    """Return ``[(folder_id, pid)]`` for every PID file in the pids dir."""
    pids_dir = _pids_dir()
    if not pids_dir.is_dir():
        return []
    result = []
    for f in pids_dir.iterdir():
        if f.suffix == ".pid":
            try:
                pid = int(f.read_text(encoding="utf-8").strip())
                result.append((f.stem, pid))
            except (ValueError, OSError):
                pass
    return result


def daemonize() -> None:
    """Detach the current process from the terminal using a double-fork.

    After this call the process runs as a proper Unix daemon:
    - Session leader with no controlling terminal
    - stdin/stdout/stderr redirected to /dev/null
    - Working directory unchanged (caller manages cwd)
    """
    if sys.platform == "win32":
        return

    pid = os.fork()
    if pid > 0:
        os._exit(0)

    os.setsid()

    pid = os.fork()
    if pid > 0:
        os._exit(0)

    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, sys.stdin.fileno())
    os.dup2(devnull, sys.stdout.fileno())
    os.dup2(devnull, sys.stderr.fileno())
    os.close(devnull)
