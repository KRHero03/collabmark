"""Tests for collabmark.lib.registry — centralized sync registry."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from collabmark.lib.registry import (
    SyncRegistry,
    clear_stopped_entries,
    find_entry_by_folder_id,
    find_entry_by_path,
    list_syncs,
    load_registry,
    mark_stopped,
    prune_dead,
    register_sync,
    stop_all_syncs,
    stop_sync_process,
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


class TestFindEntryByPath:
    def test_finds_exact_match(self, registry_home: Path) -> None:
        dir_a = registry_home / "proj"
        dir_a.mkdir()
        register_sync(str(dir_a), "f1", "Proj", "http://x", "a@a.com")
        entry = find_entry_by_path(dir_a)
        assert entry is not None
        assert entry.folder_id == "f1"

    def test_finds_parent_match(self, registry_home: Path) -> None:
        dir_a = registry_home / "proj"
        dir_a.mkdir()
        register_sync(str(dir_a), "f1", "Proj", "http://x", "a@a.com")
        sub = dir_a / "sub" / "deep"
        sub.mkdir(parents=True)
        entry = find_entry_by_path(sub)
        assert entry is not None
        assert entry.folder_id == "f1"

    def test_returns_none_when_no_match(self, registry_home: Path) -> None:
        entry = find_entry_by_path(Path("/tmp/unknown"))
        assert entry is None


class TestFindEntryByFolderId:
    def test_finds_by_folder_id(self, registry_home: Path) -> None:
        register_sync("/tmp/notes", "f_target", "Notes", "http://x", "a@a.com")
        entry = find_entry_by_folder_id("f_target")
        assert entry is not None
        assert entry.folder_name == "Notes"

    def test_returns_none_when_no_match(self, registry_home: Path) -> None:
        entry = find_entry_by_folder_id("nonexistent")
        assert entry is None


class TestDocSyncFields:
    def test_register_with_doc_id_and_sync_mode(self, registry_home: Path) -> None:
        register_sync(
            "/tmp/doc.md",
            "f1",
            "Doc",
            "http://x",
            "a@a.com",
            doc_id="d123",
            sync_mode="document",
        )
        reg = load_registry()
        resolved = str(Path("/tmp/doc.md").resolve())
        entry = reg.syncs[resolved]
        assert entry.doc_id == "d123"
        assert entry.sync_mode == "document"

    def test_default_sync_mode_is_folder(self, registry_home: Path) -> None:
        register_sync("/tmp/notes", "f1", "Notes", "http://x", "a@a.com")
        reg = load_registry()
        resolved = str(Path("/tmp/notes").resolve())
        assert reg.syncs[resolved].sync_mode == "folder"
        assert reg.syncs[resolved].doc_id is None


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


class TestStopSyncProcess:
    def test_stops_running_process(self, registry_home: Path) -> None:
        register_sync("/tmp/notes", "abc", "Notes", "http://x", "t@t.com", pid=88888)
        reg = load_registry()
        resolved = str(Path("/tmp/notes").resolve())
        entry = reg.syncs[resolved]

        with (
            patch("collabmark.lib.registry._is_pid_alive", return_value=True),
            patch("os.kill") as mock_kill,
            patch("collabmark.lib.daemon.remove_pid_file"),
        ):
            result = stop_sync_process(entry)
        assert result is True
        mock_kill.assert_called_once()
        reg = load_registry()
        assert reg.syncs[resolved].status == "stopped"
        assert reg.syncs[resolved].pid is None

    def test_handles_already_dead_process(self, registry_home: Path) -> None:
        register_sync("/tmp/notes", "abc", "Notes", "http://x", "t@t.com", pid=999999999)
        reg = load_registry()
        resolved = str(Path("/tmp/notes").resolve())
        entry = reg.syncs[resolved]

        with patch("collabmark.lib.daemon.remove_pid_file"):
            result = stop_sync_process(entry)
        assert result is False
        reg = load_registry()
        assert reg.syncs[resolved].status == "stopped"

    def test_handles_no_pid(self, registry_home: Path) -> None:
        register_sync("/tmp/notes", "abc", "Notes", "http://x", "t@t.com", pid=1)
        mark_stopped("/tmp/notes")
        reg = load_registry()
        resolved = str(Path("/tmp/notes").resolve())
        entry = reg.syncs[resolved]

        with patch("collabmark.lib.daemon.remove_pid_file"):
            result = stop_sync_process(entry)
        assert result is False


class TestStopAllSyncs:
    def test_stops_all_running(self, registry_home: Path) -> None:
        register_sync("/tmp/a", "f1", "A", "http://x", "a@a.com", pid=88888)
        register_sync("/tmp/b", "f2", "B", "http://x", "b@b.com", pid=88889)

        with (
            patch("collabmark.lib.registry._is_pid_alive", return_value=True),
            patch("os.kill"),
            patch("collabmark.lib.daemon.remove_pid_file"),
        ):
            stopped, total = stop_all_syncs()
        assert stopped == 2
        assert total == 2

    def test_returns_zero_when_none_running(self, registry_home: Path) -> None:
        stopped, total = stop_all_syncs()
        assert stopped == 0
        assert total == 0

    def test_counts_dead_processes_correctly(self, registry_home: Path) -> None:
        register_sync("/tmp/a", "f1", "A", "http://x", "a@a.com", pid=999999999)
        register_sync("/tmp/b", "f2", "B", "http://x", "b@b.com", pid=999999998)

        with patch("collabmark.lib.daemon.remove_pid_file"):
            stopped, total = stop_all_syncs()
        assert stopped == 0
        assert total == 0


class TestClearStoppedEntries:
    def test_removes_stopped_entries(self, registry_home: Path) -> None:
        register_sync("/tmp/a", "f1", "A", "http://x", "a@a.com", pid=1)
        register_sync("/tmp/b", "f2", "B", "http://x", "b@b.com", pid=2)
        mark_stopped("/tmp/a")
        mark_stopped("/tmp/b")

        removed = clear_stopped_entries()
        assert removed == 2
        reg = load_registry()
        assert len(reg.syncs) == 0

    def test_removes_error_entries(self, registry_home: Path) -> None:
        register_sync("/tmp/a", "f1", "A", "http://x", "a@a.com")
        update_heartbeat("/tmp/a", actions_count=0, error="fail")

        removed = clear_stopped_entries()
        assert removed == 1

    def test_keeps_running_entries(self, registry_home: Path) -> None:
        register_sync("/tmp/a", "f1", "A", "http://x", "a@a.com", pid=os.getpid())
        register_sync("/tmp/b", "f2", "B", "http://x", "b@b.com", pid=1)
        mark_stopped("/tmp/b")

        removed = clear_stopped_entries()
        assert removed == 1
        reg = load_registry()
        assert len(reg.syncs) == 1

    def test_returns_zero_when_nothing_to_clean(self, registry_home: Path) -> None:
        removed = clear_stopped_entries()
        assert removed == 0
