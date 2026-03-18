"""File watcher: monitor a directory for ``.md`` changes using watchdog.

Debounces rapid filesystem events and feeds them into a callback
that triggers a sync cycle.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import Callable

from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

_MD_SUFFIX = ".md"
_DEFAULT_DEBOUNCE_SEC = 0.5


class _MarkdownHandler(FileSystemEventHandler):
    """Filter filesystem events to only ``.md`` files."""

    def __init__(
        self,
        callback: Callable[[str], None],
        sync_root: Path,
    ) -> None:
        super().__init__()
        self._callback = callback
        self._sync_root = sync_root

    def _is_relevant(self, path: str) -> bool:
        if not path.endswith(_MD_SUFFIX):
            return False
        try:
            Path(path).relative_to(self._sync_root)
        except ValueError:
            return False
        return True

    def on_created(self, event: FileCreatedEvent) -> None:
        if not event.is_directory and self._is_relevant(event.src_path):
            logger.debug("Detected create: %s", event.src_path)
            self._callback(event.src_path)

    def on_modified(self, event: FileModifiedEvent) -> None:
        if not event.is_directory and self._is_relevant(event.src_path):
            logger.debug("Detected modify: %s", event.src_path)
            self._callback(event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        if not event.is_directory:
            if self._is_relevant(event.src_path):
                logger.debug("Detected move (src): %s", event.src_path)
                self._callback(event.src_path)
            if self._is_relevant(event.dest_path):
                logger.debug("Detected move (dest): %s", event.dest_path)
                self._callback(event.dest_path)

    def on_deleted(self, event) -> None:
        if not event.is_directory and self._is_relevant(event.src_path):
            logger.debug("Detected delete: %s", event.src_path)
            self._callback(event.src_path)


class DebouncedWatcher:
    """Watch *sync_root* for ``.md`` changes, debounce, then call *on_change*.

    Usage::

        async def handle():
            await run_sync_cycle(...)

        watcher = DebouncedWatcher(sync_root, on_change=handle)
        watcher.start()
        ...
        watcher.stop()
    """

    def __init__(
        self,
        sync_root: Path,
        on_change: Callable[[], object],
        debounce_sec: float = _DEFAULT_DEBOUNCE_SEC,
    ) -> None:
        self._sync_root = sync_root
        self._on_change = on_change
        self._debounce_sec = debounce_sec
        self._observer: Observer | None = None
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._pending = False

    def start(self) -> None:
        handler = _MarkdownHandler(
            callback=self._on_event,
            sync_root=self._sync_root,
        )
        self._observer = Observer()
        self._observer.schedule(handler, str(self._sync_root), recursive=True)
        self._observer.start()
        logger.info("Watching %s for .md changes", self._sync_root)

    def stop(self) -> None:
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        logger.info("Stopped watching %s", self._sync_root)

    def _on_event(self, path: str) -> None:
        """Called from watchdog thread; resets the debounce timer."""
        with self._lock:
            self._pending = True
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_sec, self._fire_callback)
            self._timer.daemon = True
            self._timer.start()

    def _fire_callback(self) -> None:
        with self._lock:
            self._pending = False
            self._timer = None
        try:
            result = self._on_change()
            if asyncio.iscoroutine(result):
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(result, loop)
                else:
                    loop.run_until_complete(result)
        except Exception:
            logger.exception("Error in sync callback")

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()


class _SingleFileHandler(FileSystemEventHandler):
    """Watch for changes to a single specific file."""

    def __init__(self, target: Path, callback: Callable[[str], None]) -> None:
        super().__init__()
        self._target = str(target.resolve())
        self._callback = callback

    def _matches(self, path: str) -> bool:
        return str(Path(path).resolve()) == self._target

    def on_created(self, event) -> None:
        if not event.is_directory and self._matches(event.src_path):
            self._callback(event.src_path)

    def on_modified(self, event) -> None:
        if not event.is_directory and self._matches(event.src_path):
            self._callback(event.src_path)

    def on_moved(self, event) -> None:
        if not event.is_directory and self._matches(getattr(event, "dest_path", "")):
            self._callback(event.dest_path)


class SingleFileWatcher:
    """Watch a single file for changes with debouncing.

    Watches the parent directory and filters events to the target file only.
    """

    def __init__(
        self,
        target_file: Path,
        on_change: Callable[[], object],
        debounce_sec: float = _DEFAULT_DEBOUNCE_SEC,
    ) -> None:
        self._target = target_file.resolve()
        self._on_change = on_change
        self._debounce_sec = debounce_sec
        self._observer: Observer | None = None
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        handler = _SingleFileHandler(self._target, self._on_event)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._target.parent), recursive=False)
        self._observer.start()
        logger.info("Watching single file %s", self._target)

    def stop(self) -> None:
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        logger.info("Stopped watching %s", self._target)

    def _on_event(self, path: str) -> None:
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_sec, self._fire_callback)
            self._timer.daemon = True
            self._timer.start()

    def _fire_callback(self) -> None:
        with self._lock:
            self._timer = None
        try:
            result = self._on_change()
            if asyncio.iscoroutine(result):
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(result, loop)
                else:
                    loop.run_until_complete(result)
        except Exception:
            logger.exception("Error in single-file sync callback")

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
