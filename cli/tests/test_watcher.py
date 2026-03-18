"""Tests for collabmark.lib.watcher — file watching and debounce."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

from watchdog.events import DirCreatedEvent, FileCreatedEvent, FileDeletedEvent, FileModifiedEvent, FileMovedEvent

from collabmark.lib.watcher import DebouncedWatcher, SingleFileWatcher, _MarkdownHandler

# ===================================================================
# _MarkdownHandler filtering
# ===================================================================


class TestMarkdownHandler:
    def test_accepts_md_file(self, tmp_path: Path) -> None:
        cb = MagicMock()
        handler = _MarkdownHandler(callback=cb, sync_root=tmp_path)

        event = FileCreatedEvent(str(tmp_path / "doc.md"))
        handler.on_created(event)
        cb.assert_called_once_with(str(tmp_path / "doc.md"))

    def test_ignores_non_md_file(self, tmp_path: Path) -> None:
        cb = MagicMock()
        handler = _MarkdownHandler(callback=cb, sync_root=tmp_path)

        event = FileCreatedEvent(str(tmp_path / "image.png"))
        handler.on_created(event)
        cb.assert_not_called()

    def test_no_longer_ignores_collabmark_directory(self, tmp_path: Path) -> None:
        """Config is now centralized, so .collabmark dirs are not special."""
        cb = MagicMock()
        handler = _MarkdownHandler(callback=cb, sync_root=tmp_path)

        collabmark_dir = tmp_path / ".collabmark"
        collabmark_dir.mkdir()
        event = FileModifiedEvent(str(collabmark_dir / "sync.md"))
        handler.on_modified(event)
        cb.assert_called_once()

    def test_accepts_nested_md_file(self, tmp_path: Path) -> None:
        cb = MagicMock()
        handler = _MarkdownHandler(callback=cb, sync_root=tmp_path)

        event = FileCreatedEvent(str(tmp_path / "sub" / "deep" / "note.md"))
        handler.on_created(event)
        cb.assert_called_once()

    def test_ignores_directory_events(self, tmp_path: Path) -> None:
        cb = MagicMock()
        handler = _MarkdownHandler(callback=cb, sync_root=tmp_path)

        event = DirCreatedEvent(str(tmp_path / "newdir"))
        handler.on_created(event)
        cb.assert_not_called()

    def test_handles_modify_event(self, tmp_path: Path) -> None:
        cb = MagicMock()
        handler = _MarkdownHandler(callback=cb, sync_root=tmp_path)

        event = FileModifiedEvent(str(tmp_path / "doc.md"))
        handler.on_modified(event)
        cb.assert_called_once()

    def test_handles_delete_event(self, tmp_path: Path) -> None:
        cb = MagicMock()
        handler = _MarkdownHandler(callback=cb, sync_root=tmp_path)

        event = FileDeletedEvent(str(tmp_path / "doc.md"))
        handler.on_deleted(event)
        cb.assert_called_once()

    def test_handles_move_event_dest(self, tmp_path: Path) -> None:
        cb = MagicMock()
        handler = _MarkdownHandler(callback=cb, sync_root=tmp_path)

        event = FileMovedEvent(str(tmp_path / "old.txt"), str(tmp_path / "new.md"))
        handler.on_moved(event)
        cb.assert_called_once_with(str(tmp_path / "new.md"))

    def test_handles_move_event_both_md(self, tmp_path: Path) -> None:
        cb = MagicMock()
        handler = _MarkdownHandler(callback=cb, sync_root=tmp_path)

        event = FileMovedEvent(str(tmp_path / "old.md"), str(tmp_path / "new.md"))
        handler.on_moved(event)
        assert cb.call_count == 2


# ===================================================================
# DebouncedWatcher lifecycle
# ===================================================================


class TestDebouncedWatcher:
    def test_start_and_stop(self, tmp_path: Path) -> None:
        cb = MagicMock()
        watcher = DebouncedWatcher(tmp_path, on_change=cb, debounce_sec=0.05)
        watcher.start()
        assert watcher.is_running
        watcher.stop()
        assert not watcher.is_running

    def test_stop_without_start(self, tmp_path: Path) -> None:
        cb = MagicMock()
        watcher = DebouncedWatcher(tmp_path, on_change=cb)
        watcher.stop()

    def test_detects_new_md_file(self, tmp_path: Path) -> None:
        cb = MagicMock()
        watcher = DebouncedWatcher(tmp_path, on_change=cb, debounce_sec=0.1)
        watcher.start()
        try:
            (tmp_path / "new.md").write_text("hello", encoding="utf-8")
            time.sleep(0.5)
            assert cb.call_count >= 1
        finally:
            watcher.stop()

    def test_debounces_rapid_changes(self, tmp_path: Path) -> None:
        cb = MagicMock()
        watcher = DebouncedWatcher(tmp_path, on_change=cb, debounce_sec=0.2)
        watcher.start()
        try:
            md_file = tmp_path / "rapid.md"
            for i in range(5):
                md_file.write_text(f"change {i}", encoding="utf-8")
                time.sleep(0.03)
            time.sleep(0.5)
            assert cb.call_count <= 2
        finally:
            watcher.stop()

    def test_ignores_non_md_files(self, tmp_path: Path) -> None:
        cb = MagicMock()
        watcher = DebouncedWatcher(tmp_path, on_change=cb, debounce_sec=0.1)
        watcher.start()
        try:
            (tmp_path / "ignore.txt").write_text("nope", encoding="utf-8")
            (tmp_path / "also.png").write_bytes(b"\x89PNG")
            time.sleep(0.4)
            cb.assert_not_called()
        finally:
            watcher.stop()

    def test_callback_error_does_not_crash(self, tmp_path: Path) -> None:
        cb = MagicMock(side_effect=RuntimeError("boom"))
        watcher = DebouncedWatcher(tmp_path, on_change=cb, debounce_sec=0.05)
        watcher.start()
        try:
            (tmp_path / "crash.md").write_text("x", encoding="utf-8")
            time.sleep(0.3)
            assert watcher.is_running
        finally:
            watcher.stop()


# ===================================================================
# SingleFileWatcher
# ===================================================================


class TestSingleFileWatcher:
    def test_start_and_stop(self, tmp_path: Path) -> None:
        target = tmp_path / "doc.md"
        target.write_text("hello", encoding="utf-8")
        cb = MagicMock()
        watcher = SingleFileWatcher(target, on_change=cb, debounce_sec=0.05)
        watcher.start()
        assert watcher.is_running
        watcher.stop()
        assert not watcher.is_running

    def test_detects_target_file_change(self, tmp_path: Path) -> None:
        target = tmp_path / "doc.md"
        target.write_text("initial", encoding="utf-8")
        cb = MagicMock()
        watcher = SingleFileWatcher(target, on_change=cb, debounce_sec=0.1)
        watcher.start()
        try:
            time.sleep(0.2)
            target.write_text("modified", encoding="utf-8")
            time.sleep(0.5)
            assert cb.call_count >= 1
        finally:
            watcher.stop()

    def test_ignores_other_files_in_same_dir(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        target = sub / "target.md"
        target.write_text("keep", encoding="utf-8")
        cb = MagicMock()
        watcher = SingleFileWatcher(target, on_change=cb, debounce_sec=0.1)
        watcher.start()
        try:
            time.sleep(0.3)
            cb.reset_mock()
            (tmp_path / "other.md").write_text("noise", encoding="utf-8")
            (tmp_path / "another.txt").write_text("noise", encoding="utf-8")
            time.sleep(0.4)
            cb.assert_not_called()
        finally:
            watcher.stop()
