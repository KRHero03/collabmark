"""Shared type definitions for the CollabMark CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class SyncDirection(Enum):
    PUSH = "push"
    PULL = "pull"
    BOTH = "both"


class SyncMode(Enum):
    FOLDER = "folder"
    DOCUMENT = "document"


@dataclass(frozen=True)
class CloudDocument:
    """Lightweight reference to a document in CollabMark cloud."""

    id: str
    title: str
    content_hash: str


@dataclass(frozen=True)
class SyncEntry:
    """Mapping between a local file and its cloud counterpart."""

    local_path: Path
    cloud_doc_id: str
    content_hash: str


# ---------------------------------------------------------------------------
# API response types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FolderInfo:
    """Folder metadata returned by the CollabMark API."""

    id: str
    name: str
    owner_id: str
    parent_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass(frozen=True)
class SharedFolder:
    """A folder shared with the current user, including permission info."""

    id: str
    name: str
    owner_id: str
    owner_name: str = ""
    owner_email: str = ""
    permission: str = "view"
    parent_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass(frozen=True)
class DocumentInfo:
    """Document metadata (and optionally content) from the API."""

    id: str
    title: str
    content: str = ""
    owner_id: str = ""
    folder_id: Optional[str] = None
    content_length: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass(frozen=True)
class FolderContents:
    """Result of listing a folder's immediate children."""

    folders: list[FolderInfo] = field(default_factory=list)
    documents: list[DocumentInfo] = field(default_factory=list)
    permission: str = "edit"


# ---------------------------------------------------------------------------
# Per-project sync state types
# ---------------------------------------------------------------------------


@dataclass
class SyncConfig:
    """Persisted in ``~/.collabmark/projects/{folder_id}/config.json``."""

    server_url: str
    folder_id: str
    folder_name: str
    user_id: str
    user_email: str
    local_path: str = ""
    sync_mode: str = "folder"
    doc_id: Optional[str] = None


@dataclass
class SyncFileEntry:
    """Tracks the sync state of a single ``.md`` file."""

    doc_id: str
    content_hash: str
    last_synced_at: str


@dataclass
class SyncFolderEntry:
    """Tracks the cloud ID of a synced subdirectory."""

    folder_id: str


@dataclass
class SyncState:
    """Full sync state persisted in ``~/.collabmark/projects/{id}/sync.json``."""

    files: dict[str, SyncFileEntry] = field(default_factory=dict)
    folders: dict[str, SyncFolderEntry] = field(default_factory=dict)
