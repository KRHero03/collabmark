"""Tests for collabmark.lib.registry — centralized sync registry."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from collabmark.lib.registry import (
    SyncRegistry,
    list_syncs,
    load_registry,
    mark_stopped,
    prune_dead,
    register_sync,
    unregister_sync,
    update_heartbeat,
)


@pytest.fixture()
def registry_home(tmp_path: Path):
    """Point COLLABMARK_HOME to a temp dir for isolated tests."""
    with patch.dict(os.environ, {"COLLABMARK_HOME": str(tmp_path)}):
        yield tmp_path


class TestRegisterSync:
    def test_register_creates_entry(self, registry_home: Path) -> None:
        register_sync(
            local_path="/tmp/notes",
            folder_id="abc123",
            folder_name="Notes",
            server_url="http://localhost:8000",
            user_email="test@example.com",
            pid=1234,
        )
        reg = load_registry()
        resolved = str(Path("/tmp/notes").resolve())
        assert resolved in reg.syncs
        entry = reg.syncs[resolved]
        assert entry.folder_id == "abc123"
        assert entry.folder_name == "Notes"
        assert entry.status == "running"
        assert entry.pid == 1234

    def test_register_updates_existing_entry(self, registry_home: Path) -> None:
        register_sync(
            local_path="/tmp/notes",
            folder_id="abc123",
            folder_name="Notes",
            server_url="http://localhost:8000",
            user_email="test@example.com",
        )
        register_sync(
            local_path="/tmp/notes",
            folder_id="abc123",
            folder_name="Notes v2",
            server_url="http://localhost:8000",
            user_email="new@example.com",
        )
        reg = load_registry()
        resolved = str(Path("/tmp/notes").resolve())
        assert reg.syncs[resolved].folder_name == "Notes v2"
        assert reg.syncs[resolved].user_email == "new@example.com"

    def test_register_preserves_timestamps(self, registry_home: Path) -> None:
        register_sync(
            local_path="/tmp/notes",
            folder_id="abc",
            folder_name="N",
            server_url="http://localhost:8000",
            user_email="t@t.com",
        )
        reg = load_registry()
        resolved = str(Path("/tmp/notes").resolve())
        original_ts = reg.syncs[resolved].registered_at

        register_sync(
            local_path="/tmp/notes",
            folder_id="abc",
            folder_name="N2",
            server_url="http://localhost:8000",
            user_email="t@t.com",
        )
        reg = load_registry()
        assert reg.syncs[resolved].registered_at == original_ts


class TestUpdateHeartbeat:
    def test_updates_last_synced(self, registry_home: Path) -> None:
        register_sync(
            local_path="/tmp/notes",
            folder_id="abc",
            folder_name="N",
            server_url="http://localhost:8000",
            user_email="t@t.com",
        )
        update_heartbeat("/tmp/notes", actions_count=5)
        reg = load_registry()
        resolved = str(Path("/tmp/notes").resolve())
        entry = reg.syncs[resolved]
        assert entry.last_synced_at is not None
        assert entry.last_sync_actions == 5
        assert entry.last_error is None

    def test_records_error(self, registry_home: Path) -> None:
        register_sync(
            local_path="/tmp/notes",
            folder_id="abc",
            folder_name="N",
            server_url="http://localhost:8000",
            user_email="t@t.com",
        )
        update_heartbeat("/tmp/notes", actions_count=0, error="Connection refused")
        reg = load_registry()
        resolved = str(Path("/tmp/notes").resolve())
        assert reg.syncs[resolved].last_error == "Connection refused"
        assert reg.syncs[resolved].status == "error"

    def test_noop_for_unregistered_path(self, registry_home: Path) -> None:
        update_heartbeat("/nonexistent", actions_count=1)
        reg = load_registry()
        assert len(reg.syncs) == 0


class TestMarkStopped:
    def test_marks_entry_as_stopped(self, registry_home: Path) -> None:
        register_sync(
            local_path="/tmp/notes",
            folder_id="abc",
            folder_name="N",
            server_url="http://localhost:8000",
            user_email="t@t.com",
            pid=999,
        )
        mark_stopped("/tmp/notes")
        reg = load_registry()
        resolved = str(Path("/tmp/notes").resolve())
        assert reg.syncs[resolved].status == "stopped"
        assert reg.syncs[resolved].pid is None


class TestUnregisterSync:
    def test_removes_entry(self, registry_home: Path) -> None:
        register_sync(
            local_path="/tmp/notes",
            folder_id="abc",
            folder_name="N",
            server_url="http://localhost:8000",
            user_email="t@t.com",
        )
        assert unregister_sync("/tmp/notes") is True
        reg = load_registry()
        assert len(reg.syncs) == 0

    def test_returns_false_for_missing(self, registry_home: Path) -> None:
        assert unregister_sync("/nonexistent") is False


class TestPruneDead:
    def test_prunes_dead_pids(self, registry_home: Path) -> None:
        register_sync(
            local_path="/tmp/notes",
            folder_id="abc",
            folder_name="N",
            server_url="http://localhost:8000",
            user_email="t@t.com",
            pid=999999999,
        )
        count = prune_dead()
        assert count == 1
        reg = load_registry()
        resolved = str(Path("/tmp/notes").resolve())
        assert reg.syncs[resolved].status == "stopped"
        assert reg.syncs[resolved].pid is None

    def test_keeps_alive_pids(self, registry_home: Path) -> None:
        register_sync(
            local_path="/tmp/notes",
            folder_id="abc",
            folder_name="N",
            server_url="http://localhost:8000",
            user_email="t@t.com",
            pid=os.getpid(),
        )
        count = prune_dead()
        assert count == 0
        reg = load_registry()
        resolved = str(Path("/tmp/notes").resolve())
        assert reg.syncs[resolved].status == "running"


class TestListSyncs:
    def test_returns_all_entries(self, registry_home: Path) -> None:
        register_sync("/tmp/a", "f1", "A", "http://x", "a@a.com")
        register_sync("/tmp/b", "f2", "B", "http://x", "b@b.com")
        syncs = list_syncs()
        assert len(syncs) == 2

    def test_returns_empty_when_no_registry(self, registry_home: Path) -> None:
        syncs = list_syncs()
        assert syncs == []


class TestLoadRegistry:
    def test_returns_empty_when_no_file(self, registry_home: Path) -> None:
        reg = load_registry()
        assert isinstance(reg, SyncRegistry)
        assert len(reg.syncs) == 0

    def test_handles_corrupt_file(self, registry_home: Path) -> None:
        reg_file = registry_home / "registry.json"
        reg_file.write_text("not json!", encoding="utf-8")
        reg = load_registry()
        assert len(reg.syncs) == 0

    def test_handles_malformed_entries(self, registry_home: Path) -> None:
        reg_file = registry_home / "registry.json"
        data = {"syncs": {"/tmp/bad": {"folder_id": "x"}}}
        reg_file.write_text(json.dumps(data), encoding="utf-8")
        reg = load_registry()
        assert len(reg.syncs) == 0
