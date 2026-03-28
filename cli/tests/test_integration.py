"""Integration tests — end-to-end sync flows and CLI UX validation."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from collabmark import __version__
from collabmark.lib.api import CollabMarkClient
from collabmark.lib.auth import AuthError
from collabmark.lib.config import (
    init_project,
    save_sync_state,
)
from collabmark.lib.registry import register_sync
from collabmark.lib.sync_engine import (
    ActionKind,
    _flatten_tree,
    content_hash,
    fetch_remote_files,
    run_sync_cycle,
)
from collabmark.main import cli
from collabmark.types import (
    DocumentInfo,
    FolderContents,
    SyncConfig,
    SyncFileEntry,
    SyncState,
)

_FAKE_API_KEY = "cm_test_key_123"

# ===================================================================
# Tree flattening
# ===================================================================


class TestFlattenTree:
    def test_empty_tree(self) -> None:
        tree = {"id": "r1", "name": "Root", "folders": [], "documents": [], "permission": "edit"}
        result = _flatten_tree(tree)
        assert result == {}

    def test_flat_documents(self) -> None:
        tree = {
            "id": "r1",
            "name": "Root",
            "folders": [],
            "documents": [
                {"id": "d1", "title": "README", "content_length": 42},
                {"id": "d2", "title": "NOTES", "content_length": 10},
            ],
            "permission": "edit",
        }
        result = _flatten_tree(tree)
        assert "README.md" in result
        assert "NOTES.md" in result
        assert result["README.md"].id == "d1"
        assert result["NOTES.md"].id == "d2"

    def test_nested_folders(self) -> None:
        tree = {
            "id": "r1",
            "name": "Root",
            "folders": [
                {
                    "id": "f1",
                    "name": "sub",
                    "folders": [],
                    "documents": [{"id": "d1", "title": "deep", "content_length": 5}],
                    "permission": "edit",
                }
            ],
            "documents": [{"id": "d2", "title": "top", "content_length": 3}],
            "permission": "edit",
        }
        result = _flatten_tree(tree)
        assert "top.md" in result
        assert "sub/deep.md" in result

    def test_deeply_nested(self) -> None:
        tree = {
            "id": "r1",
            "name": "Root",
            "folders": [
                {
                    "id": "f1",
                    "name": "a",
                    "folders": [
                        {
                            "id": "f2",
                            "name": "b",
                            "folders": [],
                            "documents": [{"id": "d1", "title": "leaf", "content_length": 1}],
                            "permission": "edit",
                        }
                    ],
                    "documents": [],
                    "permission": "edit",
                }
            ],
            "documents": [],
            "permission": "edit",
        }
        result = _flatten_tree(tree)
        assert "a/b/leaf.md" in result

    def test_with_prefix(self) -> None:
        tree = {
            "id": "r1",
            "name": "Root",
            "folders": [],
            "documents": [{"id": "d1", "title": "file", "content_length": 10}],
            "permission": "edit",
        }
        result = _flatten_tree(tree, prefix="pre")
        assert "pre/file.md" in result


# ===================================================================
# Fetch remote files — tree vs. fallback
# ===================================================================


class TestFetchRemoteFiles:
    @pytest.mark.asyncio
    async def test_uses_tree_endpoint(self) -> None:
        mock_client = AsyncMock(spec=CollabMarkClient)
        mock_client.get_folder_tree.return_value = {
            "id": "r1",
            "name": "Root",
            "folders": [],
            "documents": [{"id": "d1", "title": "hello", "content_length": 5}],
            "permission": "edit",
        }

        result = await fetch_remote_files(mock_client, "r1")
        mock_client.get_folder_tree.assert_called_once_with("r1")
        assert "hello.md" in result

    @pytest.mark.asyncio
    async def test_falls_back_to_recursive(self) -> None:
        mock_client = AsyncMock(spec=CollabMarkClient)
        mock_client.get_folder_tree.side_effect = Exception("not available")
        mock_client.list_folder_contents.return_value = FolderContents(
            folders=[],
            documents=[DocumentInfo(id="d1", title="fallback", content="text")],
            permission="edit",
        )

        result = await fetch_remote_files(mock_client, "r1")
        mock_client.list_folder_contents.assert_called_once_with("r1")
        assert "fallback.md" in result


# ===================================================================
# Full sync cycle
# ===================================================================


class TestRunSyncCycle:
    @pytest.mark.asyncio
    @patch("collabmark.lib.sync_engine.write_content_via_ws", new_callable=AsyncMock)
    async def test_initial_push_new_files(self, mock_crdt_write, tmp_path: Path) -> None:
        """Local files with no prior state and empty cloud -> PUSH_NEW."""
        sync_root = tmp_path / "root"
        sync_root.mkdir()
        (sync_root / "notes.md").write_text("# Notes\n", encoding="utf-8")

        project_dir = tmp_path / "project_state"
        project_dir.mkdir()
        state = SyncState()
        save_sync_state(state, project_dir)

        mock_client = AsyncMock(spec=CollabMarkClient)
        mock_client.get_folder_tree.return_value = {
            "id": "f1",
            "name": "Root",
            "folders": [],
            "documents": [],
            "permission": "edit",
        }
        mock_client.create_document.return_value = DocumentInfo(id="d1", title="notes", content="")

        actions = await run_sync_cycle(mock_client, sync_root, "f1", state, project_dir, _FAKE_API_KEY)
        assert len(actions) == 1
        assert actions[0].kind == ActionKind.PUSH_NEW
        assert "notes.md" in state.files
        mock_crdt_write.assert_called_once()

    @pytest.mark.asyncio
    @patch("collabmark.lib.sync_engine.read_content_via_ws", new_callable=AsyncMock)
    @patch("collabmark.lib.sync_engine.read_contents_batch", new_callable=AsyncMock)
    async def test_initial_pull_new_files(self, mock_batch_read, mock_crdt_read, tmp_path: Path) -> None:
        """Empty local with cloud docs -> PULL_NEW."""
        sync_root = tmp_path / "root"
        sync_root.mkdir()

        project_dir = tmp_path / "project_state"
        project_dir.mkdir()
        state = SyncState()
        save_sync_state(state, project_dir)

        mock_client = AsyncMock(spec=CollabMarkClient)
        mock_client.get_folder_tree.return_value = {
            "id": "f1",
            "name": "Root",
            "folders": [],
            "documents": [{"id": "d1", "title": "cloud-doc", "content_length": 14}],
            "permission": "edit",
        }
        mock_batch_read.return_value = {}
        mock_crdt_read.return_value = "hello from cloud"

        actions = await run_sync_cycle(mock_client, sync_root, "f1", state, project_dir, _FAKE_API_KEY)
        assert len(actions) == 1
        assert actions[0].kind == ActionKind.PULL_NEW
        assert (sync_root / "cloud-doc.md").read_text(encoding="utf-8") == "hello from cloud"

    @pytest.mark.asyncio
    @patch("collabmark.lib.sync_engine.read_contents_batch", new_callable=AsyncMock)
    async def test_no_actions_when_in_sync(self, mock_batch_read, tmp_path: Path) -> None:
        """Both sides identical -> no actions."""
        sync_root = tmp_path / "root"
        sync_root.mkdir()
        (sync_root / "doc.md").write_text("same content", encoding="utf-8")

        project_dir = tmp_path / "project_state"
        project_dir.mkdir()

        h = content_hash("same content")
        state = SyncState(files={"doc.md": SyncFileEntry(doc_id="d1", content_hash=h, last_synced_at="t1")})
        save_sync_state(state, project_dir)

        mock_client = AsyncMock(spec=CollabMarkClient)
        mock_client.get_folder_tree.return_value = {
            "id": "f1",
            "name": "Root",
            "folders": [],
            "documents": [{"id": "d1", "title": "doc", "content_length": 12}],
            "permission": "edit",
        }
        mock_batch_read.return_value = {"d1": "same content"}

        actions = await run_sync_cycle(mock_client, sync_root, "f1", state, project_dir, _FAKE_API_KEY)
        assert actions == []

    @pytest.mark.asyncio
    @patch("collabmark.lib.sync_engine.read_contents_batch", new_callable=AsyncMock)
    async def test_conflict_detection(self, mock_batch_read, tmp_path: Path) -> None:
        """Both local and cloud changed -> CONFLICT."""
        sync_root = tmp_path / "root"
        sync_root.mkdir()
        (sync_root / "doc.md").write_text("local version", encoding="utf-8")

        project_dir = tmp_path / "project_state"
        project_dir.mkdir()

        h = content_hash("original")
        state = SyncState(files={"doc.md": SyncFileEntry(doc_id="d1", content_hash=h, last_synced_at="t1")})
        save_sync_state(state, project_dir)

        mock_client = AsyncMock(spec=CollabMarkClient)
        mock_client.get_folder_tree.return_value = {
            "id": "f1",
            "name": "Root",
            "folders": [],
            "documents": [{"id": "d1", "title": "doc", "content_length": 13}],
            "permission": "edit",
        }
        mock_batch_read.return_value = {"d1": "cloud version"}

        actions = await run_sync_cycle(mock_client, sync_root, "f1", state, project_dir, _FAKE_API_KEY)
        assert len(actions) == 1
        assert actions[0].kind == ActionKind.CONFLICT


# ===================================================================
# CLI bare invocation
# ===================================================================


class TestCLIBareInvocation:
    def test_bare_invocation_shows_welcome(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "CollabMark" in result.output
        assert "collabmark login" in result.output
        assert "collabmark start" in result.output

    def test_help_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "collabmark" in result.output.lower()

    def test_version_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output


# ===================================================================
# Command help text
# ===================================================================


class TestCommandHelp:
    @pytest.fixture()
    def runner(self) -> CliRunner:
        return CliRunner()

    @pytest.mark.parametrize(
        "cmd",
        ["init", "login", "logout", "start", "status", "stop", "logs"],
    )
    def test_command_has_help(self, runner: CliRunner, cmd: str) -> None:
        result = runner.invoke(cli, [cmd, "--help"])
        assert result.exit_code == 0
        assert len(result.output) > 50

    def test_start_help_shows_examples(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["start", "--help"])
        assert "Examples:" in result.output

    def test_logs_help_shows_examples(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["logs", "--help"])
        assert "Examples:" in result.output

    def test_init_help_shows_examples(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["init", "--help"])
        assert "Examples:" in result.output


# ===================================================================
# Init command
# ===================================================================


class TestInitCommand:
    def test_already_initialized(self, tmp_path: Path) -> None:
        cli_home = tmp_path / "home"
        target = tmp_path / "project"
        target.mkdir()

        config = SyncConfig(
            server_url="http://localhost:8000",
            folder_id="f1",
            folder_name="Test",
            user_id="u1",
            user_email="test@test.com",
            local_path=str(target.resolve()),
        )
        with patch.dict(os.environ, {"COLLABMARK_HOME": str(cli_home)}):
            init_project("f1", config)
            register_sync(str(target), "f1", "Test", "http://localhost:8000", "test@test.com")

            runner = CliRunner()
            result = runner.invoke(cli, ["init", "--path", str(target)])
        assert "already set up" in result.output

    @pytest.mark.asyncio
    async def test_requires_auth(self) -> None:
        runner = CliRunner()
        with patch("collabmark.commands.init.ensure_authenticated") as mock_auth:
            mock_auth.side_effect = AuthError("Not logged in")
            result = runner.invoke(cli, ["init", "--path", "/tmp"])
            assert result.exit_code == 1
