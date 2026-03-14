"""Tests for collabmark.lib.sync_engine — reconciliation and sync operations."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from collabmark.lib.api import CollabMarkClient, NotFoundError
from collabmark.lib.config import PROJECT_DIR_NAME, load_sync_state, save_sync_state
from collabmark.lib.sync_engine import (
    ActionKind,
    SyncAction,
    _doc_title_to_filename,
    _ensure_cloud_folders,
    _filename_to_doc_title,
    _list_local_md_files,
    content_hash,
    delete_local,
    delete_remote,
    pull_file,
    push_new_file,
    push_update,
    reconcile,
)
from collabmark.types import DocumentInfo, FolderInfo, SyncFileEntry, SyncFolderEntry, SyncState

_FAKE_API_KEY = "cm_test_key_123"

# ===================================================================
# Content hashing
# ===================================================================


class TestContentHash:
    def test_deterministic(self) -> None:
        assert content_hash("hello") == content_hash("hello")

    def test_different_content_different_hash(self) -> None:
        assert content_hash("hello") != content_hash("world")

    def test_normalises_crlf(self) -> None:
        assert content_hash("line1\r\nline2") == content_hash("line1\nline2")

    def test_starts_with_sha256_prefix(self) -> None:
        h = content_hash("test")
        assert h.startswith("sha256:")
        assert len(h) == 7 + 64  # "sha256:" + 64 hex chars

    def test_empty_string(self) -> None:
        h = content_hash("")
        assert h.startswith("sha256:")


# ===================================================================
# Filename / title conversion
# ===================================================================


class TestFilenameConversion:
    def test_title_to_filename_adds_md(self) -> None:
        assert _doc_title_to_filename("Overview") == "Overview.md"

    def test_title_to_filename_keeps_existing_md(self) -> None:
        assert _doc_title_to_filename("Overview.md") == "Overview.md"

    def test_title_to_filename_strips_whitespace(self) -> None:
        assert _doc_title_to_filename("  Overview  ") == "Overview.md"

    def test_title_to_filename_empty(self) -> None:
        assert _doc_title_to_filename("") == "Untitled.md"

    def test_filename_to_title_removes_md(self) -> None:
        assert _filename_to_doc_title("Overview.md") == "Overview"

    def test_filename_to_title_no_suffix(self) -> None:
        assert _filename_to_doc_title("README") == "README"


# ===================================================================
# List local .md files
# ===================================================================


class TestListLocalMdFiles:
    def test_finds_md_files(self, tmp_path: Path) -> None:
        (tmp_path / "doc.md").write_text("hello", encoding="utf-8")
        result = _list_local_md_files(tmp_path)
        assert "doc.md" in result

    def test_ignores_non_md_files(self, tmp_path: Path) -> None:
        (tmp_path / "doc.md").write_text("hello", encoding="utf-8")
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        (tmp_path / "notes.txt").write_text("text", encoding="utf-8")
        result = _list_local_md_files(tmp_path)
        assert len(result) == 1
        assert "doc.md" in result

    def test_finds_nested_files(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub" / "deep"
        sub.mkdir(parents=True)
        (sub / "nested.md").write_text("nested", encoding="utf-8")
        result = _list_local_md_files(tmp_path)
        rel = str(Path("sub/deep/nested.md"))
        assert rel in result

    def test_ignores_collabmark_directory(self, tmp_path: Path) -> None:
        (tmp_path / "doc.md").write_text("hello", encoding="utf-8")
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()
        (project_dir / "internal.md").write_text("skip", encoding="utf-8")
        result = _list_local_md_files(tmp_path)
        assert len(result) == 1

    def test_empty_directory(self, tmp_path: Path) -> None:
        result = _list_local_md_files(tmp_path)
        assert result == {}

    def test_hash_matches_content_hash(self, tmp_path: Path) -> None:
        (tmp_path / "doc.md").write_text("content", encoding="utf-8")
        result = _list_local_md_files(tmp_path)
        assert result["doc.md"] == content_hash("content")


# ===================================================================
# Reconciliation logic
# ===================================================================


def _doc(doc_id: str, title: str, content: str = "") -> DocumentInfo:
    return DocumentInfo(id=doc_id, title=title, content=content)


def _hashes_from_content(remote: dict[str, DocumentInfo], content_map: dict[str, str]) -> dict[str, str]:
    """Build remote_hashes from a mapping of rel_path -> content text."""
    return {rel: content_hash(text) for rel, text in content_map.items()}


class TestReconcile:
    def test_new_local_file_produces_push_new(self) -> None:
        local = {"new.md": content_hash("hello")}
        state = SyncState()
        remote: dict[str, DocumentInfo] = {}
        remote_hashes: dict[str, str] = {}

        actions = reconcile(local, state, remote, remote_hashes)

        assert len(actions) == 1
        assert actions[0].kind == ActionKind.PUSH_NEW
        assert actions[0].rel_path == "new.md"

    def test_new_remote_file_produces_pull_new(self) -> None:
        local: dict[str, str] = {}
        state = SyncState()
        remote = {"doc.md": _doc("d1", "doc")}
        remote_hashes: dict[str, str] = {}

        actions = reconcile(local, state, remote, remote_hashes)

        assert len(actions) == 1
        assert actions[0].kind == ActionKind.PULL_NEW
        assert actions[0].doc_id == "d1"

    def test_local_modified_produces_push_update(self) -> None:
        old_hash = content_hash("old")
        new_hash = content_hash("new content")
        local = {"doc.md": new_hash}
        state = SyncState(files={"doc.md": SyncFileEntry("d1", old_hash, "t1")})
        remote = {"doc.md": _doc("d1", "doc")}
        remote_hashes = {"doc.md": old_hash}

        actions = reconcile(local, state, remote, remote_hashes)

        assert len(actions) == 1
        assert actions[0].kind == ActionKind.PUSH_UPDATE
        assert actions[0].doc_id == "d1"

    def test_remote_modified_produces_pull_update(self) -> None:
        old_hash = content_hash("old")
        local = {"doc.md": old_hash}
        state = SyncState(files={"doc.md": SyncFileEntry("d1", old_hash, "t1")})
        remote = {"doc.md": _doc("d1", "doc")}
        remote_hashes = {"doc.md": content_hash("new from cloud")}

        actions = reconcile(local, state, remote, remote_hashes)

        assert len(actions) == 1
        assert actions[0].kind == ActionKind.PULL_UPDATE

    def test_both_modified_produces_conflict(self) -> None:
        old_hash = content_hash("original")
        local = {"doc.md": content_hash("local edit")}
        state = SyncState(files={"doc.md": SyncFileEntry("d1", old_hash, "t1")})
        remote = {"doc.md": _doc("d1", "doc")}
        remote_hashes = {"doc.md": content_hash("cloud edit")}

        actions = reconcile(local, state, remote, remote_hashes)

        assert len(actions) == 1
        assert actions[0].kind == ActionKind.CONFLICT

    def test_no_changes_produces_no_actions(self) -> None:
        h = content_hash("same")
        local = {"doc.md": h}
        state = SyncState(files={"doc.md": SyncFileEntry("d1", h, "t1")})
        remote = {"doc.md": _doc("d1", "doc")}
        remote_hashes = {"doc.md": h}

        actions = reconcile(local, state, remote, remote_hashes)
        assert actions == []

    def test_local_deleted_produces_delete_remote(self) -> None:
        h = content_hash("content")
        local: dict[str, str] = {}
        state = SyncState(files={"doc.md": SyncFileEntry("d1", h, "t1")})
        remote = {"doc.md": _doc("d1", "doc")}
        remote_hashes = {"doc.md": h}

        actions = reconcile(local, state, remote, remote_hashes)

        assert len(actions) == 1
        assert actions[0].kind == ActionKind.DELETE_REMOTE
        assert actions[0].doc_id == "d1"

    def test_remote_deleted_produces_delete_local(self) -> None:
        h = content_hash("content")
        local = {"doc.md": h}
        state = SyncState(files={"doc.md": SyncFileEntry("d1", h, "t1")})
        remote: dict[str, DocumentInfo] = {}
        remote_hashes: dict[str, str] = {}

        actions = reconcile(local, state, remote, remote_hashes)

        assert len(actions) == 1
        assert actions[0].kind == ActionKind.DELETE_LOCAL

    def test_both_deleted_no_action(self) -> None:
        h = content_hash("content")
        local: dict[str, str] = {}
        state = SyncState(files={"doc.md": SyncFileEntry("d1", h, "t1")})
        remote: dict[str, DocumentInfo] = {}
        remote_hashes: dict[str, str] = {}

        actions = reconcile(local, state, remote, remote_hashes)
        assert actions == []

    def test_multiple_files_sorted_by_path(self) -> None:
        local = {
            "b.md": content_hash("b"),
            "a.md": content_hash("a"),
        }
        state = SyncState()
        remote: dict[str, DocumentInfo] = {}
        remote_hashes: dict[str, str] = {}

        actions = reconcile(local, state, remote, remote_hashes)

        assert len(actions) == 2
        assert actions[0].rel_path == "a.md"
        assert actions[1].rel_path == "b.md"

    def test_untracked_local_and_remote_same_content_no_action(self) -> None:
        """File exists both locally and remotely (not tracked) with same content."""
        text = "identical"
        local = {"doc.md": content_hash(text)}
        state = SyncState()
        remote = {"doc.md": _doc("d1", "doc")}
        remote_hashes = {"doc.md": content_hash(text)}

        actions = reconcile(local, state, remote, remote_hashes)
        assert actions == []

    def test_untracked_local_and_remote_different_content_conflict(self) -> None:
        local = {"doc.md": content_hash("local")}
        state = SyncState()
        remote = {"doc.md": _doc("d1", "doc")}
        remote_hashes = {"doc.md": content_hash("cloud")}

        actions = reconcile(local, state, remote, remote_hashes)

        assert len(actions) == 1
        assert actions[0].kind == ActionKind.CONFLICT


# ===================================================================
# Push / pull operations
# ===================================================================


class TestPushNewFile:
    @pytest.mark.asyncio
    @patch("collabmark.lib.sync_engine.write_content_via_ws", new_callable=AsyncMock)
    async def test_creates_document_and_updates_state(self, mock_crdt_write, tmp_path: Path) -> None:
        sync_root = tmp_path / "root"
        sync_root.mkdir()
        (sync_root / "new.md").write_text("# Hello", encoding="utf-8")

        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState()
        mock_client = AsyncMock(spec=CollabMarkClient)
        mock_client.create_document.return_value = DocumentInfo(id="d_new", title="new", content="")

        await push_new_file(mock_client, sync_root, state, "new.md", "f1", project_dir, _FAKE_API_KEY)

        mock_client.create_document.assert_called_once_with("new", "", folder_id="f1")
        mock_crdt_write.assert_called_once_with("d_new", "# Hello", _FAKE_API_KEY)
        assert "new.md" in state.files
        assert state.files["new.md"].doc_id == "d_new"
        assert state.files["new.md"].content_hash == content_hash("# Hello")


class TestPushUpdate:
    @pytest.mark.asyncio
    @patch("collabmark.lib.sync_engine.update_content_via_ws", new_callable=AsyncMock)
    async def test_updates_document_via_crdt(self, mock_crdt_update, tmp_path: Path) -> None:
        sync_root = tmp_path / "root"
        sync_root.mkdir()
        (sync_root / "doc.md").write_text("updated", encoding="utf-8")

        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState(files={"doc.md": SyncFileEntry("d1", content_hash("old"), "t1")})

        await push_update(sync_root, state, "doc.md", "d1", project_dir, _FAKE_API_KEY)

        mock_crdt_update.assert_called_once_with("d1", "updated", _FAKE_API_KEY)
        assert state.files["doc.md"].content_hash == content_hash("updated")


class TestPullFile:
    @pytest.mark.asyncio
    @patch("collabmark.lib.sync_engine.read_content_via_ws", new_callable=AsyncMock)
    async def test_downloads_and_writes_file(self, mock_crdt_read, tmp_path: Path) -> None:
        mock_crdt_read.return_value = "cloud content"

        sync_root = tmp_path / "root"
        sync_root.mkdir()

        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState()

        await pull_file(sync_root, state, "doc.md", "d1", project_dir, _FAKE_API_KEY)

        mock_crdt_read.assert_called_once_with("d1", _FAKE_API_KEY)
        written = (sync_root / "doc.md").read_text(encoding="utf-8")
        assert written == "cloud content"
        assert state.files["doc.md"].doc_id == "d1"
        assert state.files["doc.md"].content_hash == content_hash("cloud content")

    @pytest.mark.asyncio
    @patch("collabmark.lib.sync_engine.read_content_via_ws", new_callable=AsyncMock)
    async def test_creates_parent_directories(self, mock_crdt_read, tmp_path: Path) -> None:
        mock_crdt_read.return_value = "content"

        sync_root = tmp_path / "root"
        sync_root.mkdir()

        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState()

        await pull_file(sync_root, state, "sub/deep/nested.md", "d1", project_dir, _FAKE_API_KEY)

        assert (sync_root / "sub" / "deep" / "nested.md").is_file()


# ===================================================================
# Delete operations
# ===================================================================


class TestDeleteLocal:
    def test_moves_file_to_trash(self, tmp_path: Path) -> None:
        sync_root = tmp_path / "root"
        sync_root.mkdir()
        (sync_root / "obsolete.md").write_text("old", encoding="utf-8")

        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState(files={"obsolete.md": SyncFileEntry("d1", "h1", "t1")})

        delete_local(sync_root, state, "obsolete.md", project_dir)

        assert not (sync_root / "obsolete.md").exists()
        assert "obsolete.md" not in state.files
        trash = project_dir / "trash"
        assert trash.is_dir()
        trashed_files = list(trash.iterdir())
        assert len(trashed_files) == 1
        assert trashed_files[0].name.endswith("_obsolete.md")

    def test_handles_already_deleted_file(self, tmp_path: Path) -> None:
        sync_root = tmp_path / "root"
        sync_root.mkdir()

        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState(files={"gone.md": SyncFileEntry("d1", "h1", "t1")})

        delete_local(sync_root, state, "gone.md", project_dir)
        assert "gone.md" not in state.files


class TestDeleteRemote:
    @pytest.mark.asyncio
    async def test_soft_deletes_document(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState(files={"doc.md": SyncFileEntry("d1", "h1", "t1")})
        mock_client = AsyncMock(spec=CollabMarkClient)
        mock_client.delete_document.return_value = DocumentInfo(id="d1", title="doc")

        await delete_remote(mock_client, state, "doc.md", "d1", project_dir)

        mock_client.delete_document.assert_called_once_with("d1")
        assert "doc.md" not in state.files

    @pytest.mark.asyncio
    async def test_handles_already_deleted_remote(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState(files={"doc.md": SyncFileEntry("d1", "h1", "t1")})
        mock_client = AsyncMock(spec=CollabMarkClient)
        mock_client.delete_document.side_effect = NotFoundError("Not found", status_code=404)

        await delete_remote(mock_client, state, "doc.md", "d1", project_dir)
        assert "doc.md" not in state.files


# ===================================================================
# State persistence after operations
# ===================================================================


class TestStatePersistence:
    @pytest.mark.asyncio
    @patch("collabmark.lib.sync_engine.write_content_via_ws", new_callable=AsyncMock)
    async def test_push_new_persists_to_disk(self, mock_crdt_write, tmp_path: Path) -> None:
        sync_root = tmp_path / "root"
        sync_root.mkdir()
        (sync_root / "file.md").write_text("data", encoding="utf-8")

        project_dir = sync_root / PROJECT_DIR_NAME
        project_dir.mkdir()
        save_sync_state(SyncState(), project_dir)

        state = SyncState()
        mock_client = AsyncMock(spec=CollabMarkClient)
        mock_client.create_document.return_value = DocumentInfo(id="d1", title="file", content="")

        await push_new_file(mock_client, sync_root, state, "file.md", "f1", project_dir, _FAKE_API_KEY)

        reloaded = load_sync_state(project_dir)
        assert "file.md" in reloaded.files
        assert reloaded.files["file.md"].doc_id == "d1"


# ===================================================================
# Cloud folder creation
# ===================================================================


class TestEnsureCloudFolders:
    @pytest.mark.asyncio
    async def test_creates_single_level_folder(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState()
        mock_client = AsyncMock(spec=CollabMarkClient)
        mock_client.create_folder.return_value = FolderInfo(id="cf1", name="src", owner_id="u1")

        actions = [SyncAction(ActionKind.PUSH_NEW, "src/file.md")]
        await _ensure_cloud_folders(mock_client, actions, state, "root_f", project_dir)

        mock_client.create_folder.assert_called_once_with("src", parent_id="root_f")
        assert "src" in state.folders
        assert state.folders["src"].folder_id == "cf1"

    @pytest.mark.asyncio
    async def test_creates_nested_folders_depth_first(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState()
        mock_client = AsyncMock(spec=CollabMarkClient)
        mock_client.create_folder.side_effect = [
            FolderInfo(id="cf1", name="a", owner_id="u1"),
            FolderInfo(id="cf2", name="b", owner_id="u1"),
        ]

        actions = [SyncAction(ActionKind.PUSH_NEW, "a/b/file.md")]
        await _ensure_cloud_folders(mock_client, actions, state, "root_f", project_dir)

        assert mock_client.create_folder.call_count == 2
        calls = mock_client.create_folder.call_args_list
        assert calls[0].args == ("a",)
        assert calls[0].kwargs == {"parent_id": "root_f"}
        assert calls[1].args == ("b",)
        assert calls[1].kwargs == {"parent_id": "cf1"}
        assert state.folders["a"].folder_id == "cf1"
        assert state.folders["a/b"].folder_id == "cf2"

    @pytest.mark.asyncio
    async def test_skips_existing_folders(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState(folders={"src": SyncFolderEntry(folder_id="existing_f")})
        mock_client = AsyncMock(spec=CollabMarkClient)

        actions = [SyncAction(ActionKind.PUSH_NEW, "src/file.md")]
        await _ensure_cloud_folders(mock_client, actions, state, "root_f", project_dir)

        mock_client.create_folder.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_root_level_files(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState()
        mock_client = AsyncMock(spec=CollabMarkClient)

        actions = [SyncAction(ActionKind.PUSH_NEW, "readme.md")]
        await _ensure_cloud_folders(mock_client, actions, state, "root_f", project_dir)

        mock_client.create_folder.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_non_push_actions(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState()
        mock_client = AsyncMock(spec=CollabMarkClient)

        actions = [
            SyncAction(ActionKind.PULL_NEW, "sub/file.md", doc_id="d1"),
            SyncAction(ActionKind.DELETE_REMOTE, "sub2/file.md", doc_id="d2"),
        ]
        await _ensure_cloud_folders(mock_client, actions, state, "root_f", project_dir)

        mock_client.create_folder.assert_not_called()

    @pytest.mark.asyncio
    async def test_deduplicates_shared_parent(self, tmp_path: Path) -> None:
        project_dir = tmp_path / PROJECT_DIR_NAME
        project_dir.mkdir()

        state = SyncState()
        mock_client = AsyncMock(spec=CollabMarkClient)
        mock_client.create_folder.return_value = FolderInfo(id="cf1", name="docs", owner_id="u1")

        actions = [
            SyncAction(ActionKind.PUSH_NEW, "docs/a.md"),
            SyncAction(ActionKind.PUSH_NEW, "docs/b.md"),
            SyncAction(ActionKind.PUSH_NEW, "docs/c.md"),
        ]
        await _ensure_cloud_folders(mock_client, actions, state, "root_f", project_dir)

        mock_client.create_folder.assert_called_once_with("docs", parent_id="root_f")
