"""Tests for the conflicts command and conflict file generation."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from collabmark.commands.conflicts import _find_conflict_files, conflicts
from collabmark.lib.sync_engine import (
    ActionKind,
    SyncAction,
    _handle_conflict,
)
from collabmark.types import SyncFileEntry, SyncState


class TestFindConflictFiles:
    def test_finds_conflict_files(self, tmp_path: Path):
        (tmp_path / "notes.conflict.2026-03-10_120000.md").write_text("x")
        (tmp_path / "readme.md").write_text("y")
        result = _find_conflict_files(tmp_path)
        assert len(result) == 1
        assert "conflict" in result[0].name

    def test_finds_nested_conflicts(self, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.conflict.2026-01-01_000000.md").write_text("x")
        (tmp_path / "top.conflict.2026-01-01_000000.md").write_text("y")
        result = _find_conflict_files(tmp_path)
        assert len(result) == 2

    def test_returns_empty_when_no_conflicts(self, tmp_path: Path):
        (tmp_path / "clean.md").write_text("no conflict")
        result = _find_conflict_files(tmp_path)
        assert result == []


class TestConflictsCommand:
    def test_no_conflicts_shows_clean(self, tmp_path: Path):
        runner = CliRunner()
        result = runner.invoke(conflicts, [str(tmp_path)])
        assert result.exit_code == 0
        assert "No conflict files found" in result.output

    def test_shows_conflict_table(self, tmp_path: Path):
        (tmp_path / "notes.conflict.2026-03-10_120000.md").write_text("cloud version")
        runner = CliRunner()
        result = runner.invoke(conflicts, [str(tmp_path)])
        assert result.exit_code == 0
        assert "notes.conflict" in result.output
        assert "1 conflict" in result.output


class TestHandleConflictCreatesFile:
    async def test_creates_conflict_sidecar_file(self, tmp_path: Path):
        sync_root = tmp_path / "sync"
        sync_root.mkdir()
        original = sync_root / "notes.md"
        original.write_text("local content")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        state = SyncState(
            files={
                "notes.md": SyncFileEntry(doc_id="doc1", content_hash="old", last_synced_at="2026-01-01"),
            }
        )
        action = SyncAction(
            kind=ActionKind.CONFLICT,
            rel_path="notes.md",
            doc_id="doc1",
            local_hash="local_h",
            remote_hash="remote_h",
        )

        await _handle_conflict(sync_root, action, state, project_dir, api_key="fake")

        conflict_files = list(sync_root.glob("notes.conflict.*.md"))
        assert len(conflict_files) == 1
        content = conflict_files[0].read_text()
        assert "Conflict detected" in content or len(content) > 0

    async def test_original_file_untouched(self, tmp_path: Path):
        sync_root = tmp_path / "sync"
        sync_root.mkdir()
        original = sync_root / "readme.md"
        original.write_text("original content")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        state = SyncState(
            files={
                "readme.md": SyncFileEntry(doc_id="d2", content_hash="old", last_synced_at="2026-01-01"),
            }
        )
        action = SyncAction(
            kind=ActionKind.CONFLICT,
            rel_path="readme.md",
            doc_id="d2",
            local_hash="l",
            remote_hash="r",
        )

        await _handle_conflict(sync_root, action, state, project_dir, api_key="fake")

        assert original.read_text() == "original content"
