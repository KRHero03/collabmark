"""Tests for collabmark.lib.config — per-project sync state management."""

from __future__ import annotations

import json
from pathlib import Path

from collabmark.lib.config import (
    PROJECT_DIR_NAME,
    find_project_root,
    init_project,
    load_sync_config,
    load_sync_state,
    save_sync_config,
    save_sync_state,
)
from collabmark.types import SyncConfig, SyncFileEntry, SyncFolderEntry, SyncState

SAMPLE_CONFIG = SyncConfig(
    server_url="http://localhost:8000",
    folder_id="f1",
    folder_name="Engineering Context",
    user_id="u1",
    user_email="pm@acme.com",
)


# ===================================================================
# SyncConfig (config.json)
# ===================================================================


class TestSyncConfig:
    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        save_sync_config(SAMPLE_CONFIG, project_dir)
        loaded = load_sync_config(project_dir)

        assert loaded is not None
        assert loaded.server_url == SAMPLE_CONFIG.server_url
        assert loaded.folder_id == SAMPLE_CONFIG.folder_id
        assert loaded.folder_name == SAMPLE_CONFIG.folder_name
        assert loaded.user_id == SAMPLE_CONFIG.user_id
        assert loaded.user_email == SAMPLE_CONFIG.user_email

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        deep_dir = tmp_path / "a" / "b" / PROJECT_DIR_NAME
        save_sync_config(SAMPLE_CONFIG, deep_dir)
        assert (deep_dir / "config.json").is_file()

    def test_load_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert load_sync_config(tmp_path / "nonexistent") is None

    def test_load_returns_none_on_corrupt_json(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()
        (project_dir / "config.json").write_text("not json{{{", encoding="utf-8")
        assert load_sync_config(project_dir) is None

    def test_load_returns_none_when_key_missing(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()
        (project_dir / "config.json").write_text(json.dumps({"server_url": "x"}), encoding="utf-8")
        assert load_sync_config(project_dir) is None

    def test_atomic_write_does_not_corrupt_on_valid_data(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        save_sync_config(SAMPLE_CONFIG, project_dir)
        raw = json.loads((project_dir / "config.json").read_text(encoding="utf-8"))
        assert raw["folder_id"] == "f1"
        assert raw["user_email"] == "pm@acme.com"

    def test_overwrite_existing_config(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        save_sync_config(SAMPLE_CONFIG, project_dir)
        updated = SyncConfig(
            server_url="http://new:9000",
            folder_id="f2",
            folder_name="New Folder",
            user_id="u2",
            user_email="new@acme.com",
        )
        save_sync_config(updated, project_dir)

        loaded = load_sync_config(project_dir)
        assert loaded is not None
        assert loaded.folder_id == "f2"
        assert loaded.user_email == "new@acme.com"


# ===================================================================
# SyncState (sync.json)
# ===================================================================


class TestSyncState:
    def test_save_and_load_empty_state(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        save_sync_state(SyncState(), project_dir)
        loaded = load_sync_state(project_dir)

        assert loaded.files == {}
        assert loaded.folders == {}

    def test_save_and_load_with_files(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState(
            files={
                "overview.md": SyncFileEntry(
                    doc_id="d1",
                    content_hash="sha256:abc123",
                    last_synced_at="2025-06-21T11:00:00Z",
                ),
                "runbooks/deploy.md": SyncFileEntry(
                    doc_id="d2",
                    content_hash="sha256:def456",
                    last_synced_at="2025-06-21T12:00:00Z",
                ),
            }
        )
        save_sync_state(state, project_dir)
        loaded = load_sync_state(project_dir)

        assert len(loaded.files) == 2
        assert loaded.files["overview.md"].doc_id == "d1"
        assert loaded.files["runbooks/deploy.md"].content_hash == "sha256:def456"

    def test_save_and_load_with_folders(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState(
            folders={
                "runbooks": SyncFolderEntry(folder_id="f2"),
                "architecture": SyncFolderEntry(folder_id="f3"),
            }
        )
        save_sync_state(state, project_dir)
        loaded = load_sync_state(project_dir)

        assert len(loaded.folders) == 2
        assert loaded.folders["runbooks"].folder_id == "f2"

    def test_save_and_load_mixed(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState(
            files={
                "readme.md": SyncFileEntry(doc_id="d1", content_hash="h1", last_synced_at="t1"),
            },
            folders={"sub": SyncFolderEntry(folder_id="f1")},
        )
        save_sync_state(state, project_dir)
        loaded = load_sync_state(project_dir)

        assert "readme.md" in loaded.files
        assert "sub" in loaded.folders

    def test_load_returns_empty_when_missing(self, tmp_path: Path) -> None:
        loaded = load_sync_state(tmp_path / "nonexistent")
        assert loaded.files == {}
        assert loaded.folders == {}

    def test_load_returns_empty_on_corrupt_json(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()
        (project_dir / "sync.json").write_text("broken!", encoding="utf-8")
        loaded = load_sync_state(project_dir)
        assert loaded.files == {}

    def test_skips_corrupt_file_entries(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()
        data = {
            "files": {
                "good.md": {
                    "doc_id": "d1",
                    "content_hash": "h1",
                    "last_synced_at": "t1",
                },
                "bad.md": {"doc_id": "d2"},
            },
            "folders": {},
        }
        (project_dir / "sync.json").write_text(json.dumps(data), encoding="utf-8")
        loaded = load_sync_state(project_dir)
        assert "good.md" in loaded.files
        assert "bad.md" not in loaded.files

    def test_skips_corrupt_folder_entries(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()
        data = {
            "files": {},
            "folders": {
                "good": {"folder_id": "f1"},
                "bad": {},
            },
        }
        (project_dir / "sync.json").write_text(json.dumps(data), encoding="utf-8")
        loaded = load_sync_state(project_dir)
        assert "good" in loaded.folders
        assert "bad" not in loaded.folders

    def test_update_preserves_other_entries(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState(
            files={
                "a.md": SyncFileEntry(doc_id="d1", content_hash="h1", last_synced_at="t1"),
                "b.md": SyncFileEntry(doc_id="d2", content_hash="h2", last_synced_at="t2"),
            }
        )
        save_sync_state(state, project_dir)

        state.files["a.md"] = SyncFileEntry(doc_id="d1", content_hash="h1_updated", last_synced_at="t3")
        save_sync_state(state, project_dir)

        loaded = load_sync_state(project_dir)
        assert loaded.files["a.md"].content_hash == "h1_updated"
        assert loaded.files["b.md"].content_hash == "h2"


# ===================================================================
# find_project_root
# ===================================================================


class TestFindProjectRoot:
    def test_finds_in_current_directory(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()
        save_sync_config(SAMPLE_CONFIG, project_dir)

        assert find_project_root(tmp_path) == tmp_path

    def test_finds_in_parent_directory(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()
        save_sync_config(SAMPLE_CONFIG, project_dir)

        child = tmp_path / "subdir" / "deep"
        child.mkdir(parents=True)

        assert find_project_root(child) == tmp_path

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        assert find_project_root(tmp_path) is None

    def test_requires_config_json(self, tmp_path: Path) -> None:
        (tmp_path / PROJECT_DIR_NAME).mkdir()
        assert find_project_root(tmp_path) is None

    def test_respects_max_depth(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()
        save_sync_config(SAMPLE_CONFIG, project_dir)

        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        assert find_project_root(deep, max_depth=2) is None
        assert find_project_root(deep, max_depth=5) == tmp_path


# ===================================================================
# init_project
# ===================================================================


class TestInitProject:
    def test_creates_project_directory(self, tmp_path: Path) -> None:
        result = init_project(tmp_path, SAMPLE_CONFIG)
        assert result == tmp_path / PROJECT_DIR_NAME
        assert result.is_dir()

    def test_creates_config_and_sync_files(self, tmp_path: Path) -> None:
        init_project(tmp_path, SAMPLE_CONFIG)
        project_dir = tmp_path / PROJECT_DIR_NAME

        assert (project_dir / "config.json").is_file()
        assert (project_dir / "sync.json").is_file()

    def test_config_is_loadable(self, tmp_path: Path) -> None:
        init_project(tmp_path, SAMPLE_CONFIG)
        loaded = load_sync_config(tmp_path / PROJECT_DIR_NAME)

        assert loaded is not None
        assert loaded.folder_id == "f1"

    def test_sync_state_is_empty(self, tmp_path: Path) -> None:
        init_project(tmp_path, SAMPLE_CONFIG)
        state = load_sync_state(tmp_path / PROJECT_DIR_NAME)

        assert state.files == {}
        assert state.folders == {}

    def test_idempotent(self, tmp_path: Path) -> None:
        init_project(tmp_path, SAMPLE_CONFIG)
        init_project(tmp_path, SAMPLE_CONFIG)

        loaded = load_sync_config(tmp_path / PROJECT_DIR_NAME)
        assert loaded is not None

    def test_find_project_root_after_init(self, tmp_path: Path) -> None:
        init_project(tmp_path, SAMPLE_CONFIG)
        assert find_project_root(tmp_path) == tmp_path
