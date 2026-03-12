"""Shared type definitions for the CollabMark CLI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SyncDirection(Enum):
    PUSH = "push"
    PULL = "pull"
    BOTH = "both"


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
