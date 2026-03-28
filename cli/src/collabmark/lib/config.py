"""Configuration and path management for the CollabMark CLI.

Global paths:
    ~/.collabmark/              — CLI home (credentials, global config)
    ~/.collabmark/projects/     — per-project sync state (centralized)

Environment overrides:
    COLLABMARK_API_URL          — base URL for the CollabMark API
    COLLABMARK_FRONTEND_URL     — base URL for the CollabMark frontend
    COLLABMARK_HOME             — override ~/.collabmark location
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from collabmark.types import (
    SyncConfig,
    SyncFileEntry,
    SyncFolderEntry,
    SyncState,
)

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://web-production-5e1bc.up.railway.app"
_DEFAULT_FRONTEND_URL = "https://web-production-5e1bc.up.railway.app"

API_KEY_HEADER = "X-API-Key"
_home_override = os.environ.get("COLLABMARK_HOME")
COLLABMARK_HOME = Path(_home_override) if _home_override else Path.home() / ".collabmark"
_CONFIG_FILE = "config.json"
_SYNC_FILE = "sync.json"
_PENDING_FILE = "pending.json"


# ---------------------------------------------------------------------------
# Global paths / env
# ---------------------------------------------------------------------------


def get_api_url() -> str:
    return os.environ.get("COLLABMARK_API_URL", _DEFAULT_API_URL).rstrip("/")


def get_frontend_url() -> str:
    return os.environ.get("COLLABMARK_FRONTEND_URL", _DEFAULT_FRONTEND_URL).rstrip("/")


def get_cli_home() -> Path:
    override = os.environ.get("COLLABMARK_HOME")
    if override:
        return Path(override)
    return Path.home() / ".collabmark"


def get_credentials_path() -> Path:
    return get_cli_home() / "credentials.json"


def get_project_dir(folder_id: str) -> Path:
    """Return the centralized project directory for a given folder/doc sync."""
    return get_cli_home() / "projects" / folder_id


# ---------------------------------------------------------------------------
# Project initialisation
# ---------------------------------------------------------------------------


def init_project(folder_id: str, config: SyncConfig) -> Path:
    """Create centralized project dir with ``config.json`` and empty ``sync.json``.

    Returns the path to the project directory.
    """
    project_dir = get_project_dir(folder_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    save_sync_config(config, project_dir)
    save_sync_state(SyncState(), project_dir)

    logger.debug("Initialised project at %s", project_dir)
    return project_dir


# ---------------------------------------------------------------------------
# Atomic JSON helpers
# ---------------------------------------------------------------------------


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write *data* as JSON to *path* atomically (temp-file + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> dict | None:
    """Read a JSON file, returning ``None`` if missing or corrupt."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# SyncConfig (config.json)
# ---------------------------------------------------------------------------


def save_sync_config(config: SyncConfig, project_dir: Path) -> None:
    _atomic_write_json(
        project_dir / _CONFIG_FILE,
        {
            "server_url": config.server_url,
            "folder_id": config.folder_id,
            "folder_name": config.folder_name,
            "user_id": config.user_id,
            "user_email": config.user_email,
            "local_path": config.local_path,
            "sync_mode": config.sync_mode,
            "doc_id": config.doc_id,
        },
    )


def load_sync_config(project_dir: Path) -> SyncConfig | None:
    data = _read_json(project_dir / _CONFIG_FILE)
    if not data:
        return None
    try:
        return SyncConfig(
            server_url=data["server_url"],
            folder_id=data["folder_id"],
            folder_name=data["folder_name"],
            user_id=data["user_id"],
            user_email=data["user_email"],
            local_path=data.get("local_path", ""),
            sync_mode=data.get("sync_mode", "folder"),
            doc_id=data.get("doc_id"),
        )
    except KeyError as exc:
        logger.warning("Incomplete config.json, missing key: %s", exc)
        return None


# ---------------------------------------------------------------------------
# SyncState (sync.json)
# ---------------------------------------------------------------------------


def save_sync_state(state: SyncState, project_dir: Path) -> None:
    files = {
        rel: {
            "doc_id": entry.doc_id,
            "content_hash": entry.content_hash,
            "last_synced_at": entry.last_synced_at,
        }
        for rel, entry in state.files.items()
    }
    folders = {rel: {"folder_id": entry.folder_id} for rel, entry in state.folders.items()}
    _atomic_write_json(project_dir / _SYNC_FILE, {"files": files, "folders": folders})


def load_sync_state(project_dir: Path) -> SyncState:
    """Load sync state; returns an empty ``SyncState`` if missing or corrupt."""
    data = _read_json(project_dir / _SYNC_FILE)
    if not data:
        return SyncState()

    files: dict[str, SyncFileEntry] = {}
    for rel, entry in data.get("files", {}).items():
        try:
            files[rel] = SyncFileEntry(
                doc_id=entry["doc_id"],
                content_hash=entry["content_hash"],
                last_synced_at=entry["last_synced_at"],
            )
        except (KeyError, TypeError):
            logger.warning("Skipping corrupt sync entry: %s", rel)

    folders: dict[str, SyncFolderEntry] = {}
    for rel, entry in data.get("folders", {}).items():
        try:
            folders[rel] = SyncFolderEntry(folder_id=entry["folder_id"])
        except (KeyError, TypeError):
            logger.warning("Skipping corrupt folder entry: %s", rel)

    return SyncState(files=files, folders=folders)


# ---------------------------------------------------------------------------
# Pending changes queue (pending.json)
# ---------------------------------------------------------------------------


def save_pending_actions(project_dir: Path, actions: list[dict]) -> None:
    """Persist failed sync actions to retry on the next successful cycle."""
    _atomic_write_json(project_dir / _PENDING_FILE, {"actions": actions})


def load_pending_actions(project_dir: Path) -> list[dict]:
    data = _read_json(project_dir / _PENDING_FILE)
    if not data:
        return []
    return data.get("actions", [])


def clear_pending_actions(project_dir: Path) -> None:
    pending = project_dir / _PENDING_FILE
    if pending.is_file():
        pending.unlink(missing_ok=True)
