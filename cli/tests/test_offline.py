"""Tests for offline resilience: empty-content guard and pending queue."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from collabmark.lib.config import (
    clear_pending_actions,
    load_pending_actions,
    save_pending_actions,
)
from collabmark.lib.sync_engine import pull_file
from collabmark.types import SyncState


class TestEmptyContentGuard:
    @pytest.fixture
    def state(self):
        return SyncState(files={})

    async def test_refuses_to_overwrite_non_empty_with_empty(self, tmp_path: Path, state: SyncState):
        sync_root = tmp_path / "sync"
        sync_root.mkdir()
        existing = sync_root / "notes.md"
        existing.write_text("important content")

        project_dir = tmp_path / "proj"
        project_dir.mkdir()

        with patch("collabmark.lib.sync_engine._crdt_read", new_callable=AsyncMock, return_value=""):
            await pull_file(sync_root, state, "notes.md", "doc1", project_dir, "fake_key")

        assert existing.read_text() == "important content"

    async def test_allows_pull_when_local_file_does_not_exist(self, tmp_path: Path, state: SyncState):
        sync_root = tmp_path / "sync"
        sync_root.mkdir()

        project_dir = tmp_path / "proj"
        project_dir.mkdir()

        with patch("collabmark.lib.sync_engine._crdt_read", new_callable=AsyncMock, return_value="new content"):
            await pull_file(sync_root, state, "new.md", "doc2", project_dir, "fake_key")

        assert (sync_root / "new.md").read_text() == "new content"

    async def test_allows_overwrite_with_non_empty_content(self, tmp_path: Path, state: SyncState):
        sync_root = tmp_path / "sync"
        sync_root.mkdir()
        existing = sync_root / "notes.md"
        existing.write_text("old content")

        project_dir = tmp_path / "proj"
        project_dir.mkdir()

        with patch("collabmark.lib.sync_engine._crdt_read", new_callable=AsyncMock, return_value="updated content"):
            await pull_file(sync_root, state, "notes.md", "doc1", project_dir, "fake_key")

        assert existing.read_text() == "updated content"

    async def test_allows_pull_of_empty_content_to_empty_file(self, tmp_path: Path, state: SyncState):
        sync_root = tmp_path / "sync"
        sync_root.mkdir()
        existing = sync_root / "empty.md"
        existing.write_text("")

        project_dir = tmp_path / "proj"
        project_dir.mkdir()

        with patch("collabmark.lib.sync_engine._crdt_read", new_callable=AsyncMock, return_value=""):
            await pull_file(sync_root, state, "empty.md", "doc3", project_dir, "fake_key")

        assert existing.read_text() == ""


class TestPendingQueue:
    def test_save_and_load_round_trip(self, tmp_path: Path):
        actions = [
            {"kind": "PUSH_UPDATE", "rel_path": "notes.md", "doc_id": "d1"},
            {"kind": "PUSH_NEW", "rel_path": "new.md"},
        ]
        save_pending_actions(tmp_path, actions)
        loaded = load_pending_actions(tmp_path)
        assert loaded == actions

    def test_load_returns_empty_when_no_file(self, tmp_path: Path):
        assert load_pending_actions(tmp_path) == []

    def test_clear_removes_file(self, tmp_path: Path):
        save_pending_actions(tmp_path, [{"kind": "test"}])
        assert (tmp_path / "pending.json").is_file()
        clear_pending_actions(tmp_path)
        assert not (tmp_path / "pending.json").is_file()

    def test_clear_is_idempotent(self, tmp_path: Path):
        clear_pending_actions(tmp_path)
        clear_pending_actions(tmp_path)

    def test_save_creates_parent_directories(self, tmp_path: Path):
        deep = tmp_path / "a" / "b" / "c"
        save_pending_actions(deep, [{"kind": "test"}])
        assert load_pending_actions(deep) == [{"kind": "test"}]

    def test_overwrite_existing_pending(self, tmp_path: Path):
        save_pending_actions(tmp_path, [{"kind": "first"}])
        save_pending_actions(tmp_path, [{"kind": "second"}])
        assert load_pending_actions(tmp_path) == [{"kind": "second"}]
