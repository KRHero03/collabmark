"""Centralized sync registry at ``~/.collabmark/registry.json``.

Tracks all CollabMark sync projects across the filesystem so
``collabmark status`` can show a global overview, ``collabmark stop``
can target any running sync, and each sync process can emit heartbeats.

File-level locking prevents corruption when multiple CLI processes
update the registry concurrently.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from collabmark.lib.config import get_cli_home

logger = logging.getLogger(__name__)

_REGISTRY_FILE = "registry.json"


@dataclass
class SyncRegistryEntry:
    """One tracked sync project."""

    local_path: str
    folder_id: str
    folder_name: str
    server_url: str
    user_email: str
    registered_at: str
    last_synced_at: str | None = None
    last_sync_actions: int = 0
    last_error: str | None = None
    pid: int | None = None
    status: str = "stopped"


@dataclass
class SyncRegistry:
    """All tracked sync projects, keyed by absolute local path."""

    syncs: dict[str, SyncRegistryEntry] = field(default_factory=dict)


def _registry_path() -> Path:
    return get_cli_home() / _REGISTRY_FILE


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_locked(f) -> SyncRegistry:
    """Read the registry from a file object that is already locked."""
    f.seek(0)
    raw = f.read()
    if not raw.strip():
        return SyncRegistry()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Corrupt registry.json, resetting")
        return SyncRegistry()

    syncs: dict[str, SyncRegistryEntry] = {}
    for key, entry in data.get("syncs", {}).items():
        try:
            syncs[key] = SyncRegistryEntry(**entry)
        except TypeError:
            logger.warning("Skipping corrupt registry entry: %s", key)
    return SyncRegistry(syncs=syncs)


def _save_locked(f, registry: SyncRegistry) -> None:
    """Write the registry to a file object that is already locked."""
    payload = {"syncs": {k: asdict(v) for k, v in registry.syncs.items()}}
    f.seek(0)
    f.truncate()
    json.dump(payload, f, indent=2, default=str)
    f.write("\n")
    f.flush()


def _with_lock(fn):
    """Open the registry file with an exclusive lock, call fn(fh, registry),
    and write back if fn returns the registry (or a truthy value)."""
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        path.write_text("{}", encoding="utf-8")

    with open(path, "r+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            registry = _load_locked(f)
            result = fn(registry)
            if result is not None:
                _save_locked(f, registry)
            return result
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def load_registry() -> SyncRegistry:
    """Read the full registry (shared lock)."""
    path = _registry_path()
    if not path.is_file():
        return SyncRegistry()

    with open(path, "r", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            return _load_locked(f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def register_sync(
    local_path: str,
    folder_id: str,
    folder_name: str,
    server_url: str,
    user_email: str,
    pid: int | None = None,
) -> None:
    """Register or update a sync project in the registry."""
    abs_path = str(Path(local_path).resolve())

    def _update(reg: SyncRegistry) -> SyncRegistry:
        existing = reg.syncs.get(abs_path)
        reg.syncs[abs_path] = SyncRegistryEntry(
            local_path=abs_path,
            folder_id=folder_id,
            folder_name=folder_name,
            server_url=server_url,
            user_email=user_email,
            registered_at=existing.registered_at if existing else _now_iso(),
            last_synced_at=existing.last_synced_at if existing else None,
            last_sync_actions=existing.last_sync_actions if existing else 0,
            last_error=None,
            pid=pid or os.getpid(),
            status="running",
        )
        return reg

    _with_lock(_update)


def update_heartbeat(
    local_path: str,
    actions_count: int,
    error: str | None = None,
) -> None:
    """Update the last-sync timestamp and action count for a project."""
    abs_path = str(Path(local_path).resolve())

    def _update(reg: SyncRegistry) -> SyncRegistry | None:
        entry = reg.syncs.get(abs_path)
        if not entry:
            return None
        entry.last_synced_at = _now_iso()
        entry.last_sync_actions = actions_count
        entry.last_error = error
        if error:
            entry.status = "error"
        elif entry.status != "running":
            entry.status = "running"
        return reg

    _with_lock(_update)


def mark_stopped(local_path: str) -> None:
    """Mark a sync project as stopped."""
    abs_path = str(Path(local_path).resolve())

    def _update(reg: SyncRegistry) -> SyncRegistry | None:
        entry = reg.syncs.get(abs_path)
        if not entry:
            return None
        entry.status = "stopped"
        entry.pid = None
        entry.last_error = None
        return reg

    _with_lock(_update)


def unregister_sync(local_path: str) -> bool:
    """Remove a sync project from the registry. Returns True if it existed."""
    abs_path = str(Path(local_path).resolve())
    removed = False

    def _update(reg: SyncRegistry) -> SyncRegistry | None:
        nonlocal removed
        if abs_path in reg.syncs:
            del reg.syncs[abs_path]
            removed = True
            return reg
        return None

    _with_lock(_update)
    return removed


def prune_dead() -> int:
    """Check all 'running' entries and mark dead PIDs as 'stopped'.

    Returns the number of entries pruned.
    """
    pruned = 0

    def _update(reg: SyncRegistry) -> SyncRegistry | None:
        nonlocal pruned
        for entry in reg.syncs.values():
            if entry.status == "running" and entry.pid is not None:
                if not _is_pid_alive(entry.pid):
                    entry.status = "stopped"
                    entry.pid = None
                    pruned += 1
        return reg if pruned else None

    _with_lock(_update)
    return pruned


def list_syncs() -> list[SyncRegistryEntry]:
    """Return all registered syncs (after pruning dead ones)."""
    prune_dead()
    reg = load_registry()
    return list(reg.syncs.values())


def get_running_syncs() -> list[SyncRegistryEntry]:
    """Return only syncs with status 'running' (after pruning)."""
    return [s for s in list_syncs() if s.status == "running"]


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False
