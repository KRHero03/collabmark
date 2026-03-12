"""Sync engine: reconcile local ``.md`` files with CollabMark cloud.

Handles the three-way comparison between the local filesystem,
the persisted sync state (``.collabmark/sync.json``), and the remote
cloud state fetched via the API client.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum, auto
from pathlib import Path

from collabmark.lib.api import CollabMarkClient, NotFoundError
from collabmark.lib.config import save_sync_state
from collabmark.types import (
    DocumentInfo,
    FolderContents,
    SyncFileEntry,
    SyncFolderEntry,
    SyncState,
)

logger = logging.getLogger(__name__)

_MD_SUFFIX = ".md"


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def content_hash(text: str) -> str:
    """Return a deterministic SHA-256 hash of *text* (normalised to LF)."""
    normalised = text.replace("\r\n", "\n")
    digest = hashlib.sha256(normalised.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# ---------------------------------------------------------------------------
# Action types produced by reconciliation
# ---------------------------------------------------------------------------


class ActionKind(Enum):
    PUSH_NEW = auto()
    PUSH_UPDATE = auto()
    PULL_NEW = auto()
    PULL_UPDATE = auto()
    DELETE_LOCAL = auto()
    DELETE_REMOTE = auto()
    CONFLICT = auto()


@dataclass
class SyncAction:
    """A single operation the engine should execute."""

    kind: ActionKind
    rel_path: str
    doc_id: str | None = None
    local_hash: str | None = None
    remote_hash: str | None = None


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


def _list_local_md_files(sync_root: Path) -> dict[str, str]:
    """Return ``{relative_path: content_hash}`` for all ``.md`` files."""
    result: dict[str, str] = {}
    project_dir_name = ".collabmark"
    for md_file in sync_root.rglob(f"*{_MD_SUFFIX}"):
        if project_dir_name in md_file.parts:
            continue
        rel = str(md_file.relative_to(sync_root))
        text = md_file.read_text(encoding="utf-8")
        result[rel] = content_hash(text)
    return result


def _build_remote_file_index(
    contents: FolderContents,
) -> dict[str, DocumentInfo]:
    """Map document title (used as filename) to ``DocumentInfo``."""
    index: dict[str, DocumentInfo] = {}
    for doc in contents.documents:
        filename = _doc_title_to_filename(doc.title)
        index[filename] = doc
    return index


def _doc_title_to_filename(title: str) -> str:
    """Convert a cloud document title to a local filename."""
    name = title.strip()
    if not name:
        name = "Untitled"
    if not name.endswith(_MD_SUFFIX):
        name += _MD_SUFFIX
    return name


def _filename_to_doc_title(filename: str) -> str:
    """Convert a local filename to a cloud document title."""
    if filename.endswith(_MD_SUFFIX):
        return filename[: -len(_MD_SUFFIX)]
    return filename


def reconcile(
    local_files: dict[str, str],
    state: SyncState,
    remote_files: dict[str, DocumentInfo],
) -> list[SyncAction]:
    """Compare local filesystem, sync state, and cloud to produce actions.

    Args:
        local_files: ``{relative_path: content_hash}`` from the filesystem.
        state: The last-known sync state from ``sync.json``.
        remote_files: ``{relative_path: DocumentInfo}`` from the cloud.

    Returns:
        A list of ``SyncAction`` items to execute.
    """
    actions: list[SyncAction] = []
    all_paths = set(local_files) | set(state.files) | set(remote_files)

    for rel in sorted(all_paths):
        local_hash = local_files.get(rel)
        entry = state.files.get(rel)
        remote_doc = remote_files.get(rel)

        action = _decide_action(rel, local_hash, entry, remote_doc)
        if action:
            actions.append(action)

    return actions


def _decide_action(
    rel: str,
    local_hash: str | None,
    entry: SyncFileEntry | None,
    remote_doc: DocumentInfo | None,
) -> SyncAction | None:
    remote_hash = content_hash(remote_doc.content) if remote_doc else None
    doc_id = entry.doc_id if entry else (remote_doc.id if remote_doc else None)

    is_local = local_hash is not None
    is_tracked = entry is not None
    is_remote = remote_doc is not None

    if is_local and not is_tracked and not is_remote:
        return SyncAction(ActionKind.PUSH_NEW, rel, local_hash=local_hash)

    if not is_local and not is_tracked and is_remote:
        return SyncAction(ActionKind.PULL_NEW, rel, doc_id=doc_id, remote_hash=remote_hash)

    if is_local and is_tracked and is_remote:
        local_changed = local_hash != entry.content_hash
        remote_changed = remote_hash != entry.content_hash
        if local_changed and remote_changed:
            return SyncAction(
                ActionKind.CONFLICT,
                rel,
                doc_id=doc_id,
                local_hash=local_hash,
                remote_hash=remote_hash,
            )
        if local_changed:
            return SyncAction(ActionKind.PUSH_UPDATE, rel, doc_id=doc_id, local_hash=local_hash)
        if remote_changed:
            return SyncAction(ActionKind.PULL_UPDATE, rel, doc_id=doc_id, remote_hash=remote_hash)
        return None

    if not is_local and is_tracked and is_remote:
        return SyncAction(ActionKind.DELETE_REMOTE, rel, doc_id=doc_id)

    if is_local and is_tracked and not is_remote:
        return SyncAction(ActionKind.DELETE_LOCAL, rel)

    if not is_local and is_tracked and not is_remote:
        return None

    if is_local and not is_tracked and is_remote:
        if local_hash == remote_hash:
            return None
        return SyncAction(
            ActionKind.CONFLICT,
            rel,
            doc_id=doc_id,
            local_hash=local_hash,
            remote_hash=remote_hash,
        )

    return None


# ---------------------------------------------------------------------------
# Execution helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def push_new_file(
    client: CollabMarkClient,
    sync_root: Path,
    state: SyncState,
    rel_path: str,
    folder_id: str,
    project_dir: Path,
    api_key: str | None = None,
) -> None:
    """Create a new cloud document from a local ``.md`` file."""
    file_path = sync_root / rel_path
    text = file_path.read_text(encoding="utf-8")
    title = _filename_to_doc_title(Path(rel_path).name)

    doc = await client.create_document(title, text, folder_id=folder_id)

    if api_key and text:
        await _sync_crdt(doc.id, text, api_key)

    state.files[rel_path] = SyncFileEntry(
        doc_id=doc.id,
        content_hash=content_hash(text),
        last_synced_at=_now_iso(),
    )
    save_sync_state(state, project_dir)
    logger.info("↑ pushed (new)  %s", rel_path)


async def push_update(
    client: CollabMarkClient,
    sync_root: Path,
    state: SyncState,
    rel_path: str,
    doc_id: str,
    project_dir: Path,
    api_key: str | None = None,
) -> None:
    """Update an existing cloud document with local changes."""
    file_path = sync_root / rel_path
    text = file_path.read_text(encoding="utf-8")

    await client.update_document(doc_id, content=text)

    if api_key:
        await _sync_crdt(doc_id, text, api_key)

    state.files[rel_path] = SyncFileEntry(
        doc_id=doc_id,
        content_hash=content_hash(text),
        last_synced_at=_now_iso(),
    )
    save_sync_state(state, project_dir)
    logger.info("↑ pushed (update) %s", rel_path)


async def _sync_crdt(doc_id: str, content: str, api_key: str) -> None:
    """Push content to the CRDT store via WebSocket (best-effort)."""
    try:
        from collabmark.lib.crdt_sync import sync_content_via_ws

        await sync_content_via_ws(doc_id, content, api_key)
    except Exception as exc:
        logger.warning("CRDT sync failed for %s: %s", doc_id, exc)


async def pull_file(
    client: CollabMarkClient,
    sync_root: Path,
    state: SyncState,
    rel_path: str,
    doc_id: str,
    project_dir: Path,
) -> None:
    """Download a cloud document and write it locally."""
    doc = await client.get_document(doc_id)
    file_path = sync_root / rel_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(doc.content, encoding="utf-8")

    state.files[rel_path] = SyncFileEntry(
        doc_id=doc_id,
        content_hash=content_hash(doc.content),
        last_synced_at=_now_iso(),
    )
    save_sync_state(state, project_dir)
    logger.info("↓ pulled  %s", rel_path)


async def delete_remote(
    client: CollabMarkClient,
    state: SyncState,
    rel_path: str,
    doc_id: str,
    project_dir: Path,
) -> None:
    """Soft-delete a cloud document (local file was removed)."""
    try:
        await client.delete_document(doc_id)
    except NotFoundError:
        logger.debug("Document %s already deleted on cloud", doc_id)

    state.files.pop(rel_path, None)
    save_sync_state(state, project_dir)
    logger.info("x deleted remote  %s", rel_path)


def delete_local(
    sync_root: Path,
    state: SyncState,
    rel_path: str,
    project_dir: Path,
) -> None:
    """Remove a local file (cloud document was deleted)."""
    file_path = sync_root / rel_path
    if file_path.is_file():
        trash_dir = project_dir / "trash"
        trash_dir.mkdir(exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        dest = trash_dir / f"{ts}_{file_path.name}"
        file_path.rename(dest)
        logger.info("↓ moved to trash  %s → %s", rel_path, dest.name)

    state.files.pop(rel_path, None)
    save_sync_state(state, project_dir)


# ---------------------------------------------------------------------------
# Full sync cycle
# ---------------------------------------------------------------------------


async def fetch_remote_files(
    client: CollabMarkClient,
    folder_id: str,
    prefix: str = "",
) -> dict[str, DocumentInfo]:
    """Fetch all documents under *folder_id* from the cloud.

    Uses the ``/tree`` endpoint for a single request when available,
    falling back to recursive ``list_folder_contents`` calls.

    Returns ``{relative_path: DocumentInfo}``.
    """
    try:
        tree = await client.get_folder_tree(folder_id)
        return _flatten_tree(tree, prefix)
    except Exception:
        logger.debug("Tree endpoint unavailable, falling back to recursive listing")
        return await _fetch_remote_files_recursive(client, folder_id, prefix)


def _flatten_tree(tree: dict, prefix: str = "") -> dict[str, DocumentInfo]:
    """Walk a tree response and build a flat ``{rel_path: DocumentInfo}`` map."""
    result: dict[str, DocumentInfo] = {}
    for doc_data in tree.get("documents", []):
        filename = _doc_title_to_filename(doc_data["title"])
        rel = f"{prefix}{filename}" if not prefix else f"{prefix}/{filename}"
        result[rel] = DocumentInfo(
            id=doc_data["id"],
            title=doc_data["title"],
            content=doc_data.get("content", ""),
            owner_id=doc_data.get("owner_id", ""),
            folder_id=tree.get("id"),
            content_length=doc_data.get("content_length", 0),
            created_at=None,
            updated_at=None,
        )

    for sub in tree.get("folders", []):
        sub_name = sub["name"]
        sub_prefix = f"{prefix}{sub_name}" if not prefix else f"{prefix}/{sub_name}"
        result.update(_flatten_tree(sub, sub_prefix))

    return result


async def _fetch_remote_files_recursive(
    client: CollabMarkClient,
    folder_id: str,
    prefix: str = "",
) -> dict[str, DocumentInfo]:
    """Fallback: recursively call ``list_folder_contents``."""
    result: dict[str, DocumentInfo] = {}
    contents = await client.list_folder_contents(folder_id)

    for doc in contents.documents:
        filename = _doc_title_to_filename(doc.title)
        rel = f"{prefix}{filename}" if not prefix else f"{prefix}/{filename}"
        result[rel] = doc

    for folder in contents.folders:
        sub_prefix = f"{prefix}{folder.name}" if not prefix else f"{prefix}/{folder.name}"
        sub_docs = await _fetch_remote_files_recursive(client, folder.id, sub_prefix)
        result.update(sub_docs)

    return result


async def _ensure_cloud_folders(
    client: CollabMarkClient,
    actions: list[SyncAction],
    state: SyncState,
    root_folder_id: str,
    project_dir: Path,
) -> None:
    """Create cloud subfolders for any PUSH_NEW files in nested directories.

    Scans the actions for files that need to be pushed into subdirectories,
    creates those directories on the cloud (depth-first), and records the
    mappings in ``state.folders`` so ``_resolve_folder_id`` can find them.
    """
    needed_dirs: set[str] = set()
    for action in actions:
        if action.kind == ActionKind.PUSH_NEW:
            parent = str(Path(action.rel_path).parent)
            if parent != ".":
                needed_dirs.add(parent)

    if not needed_dirs:
        return

    all_dirs: set[str] = set()
    for d in needed_dirs:
        parts = Path(d).parts
        for i in range(1, len(parts) + 1):
            all_dirs.add(str(Path(*parts[:i])))

    for dir_path in sorted(all_dirs):
        if dir_path in state.folders:
            continue

        parent_path = str(Path(dir_path).parent)
        if parent_path == ".":
            parent_id = root_folder_id
        else:
            parent_entry = state.folders.get(parent_path)
            parent_id = parent_entry.folder_id if parent_entry else root_folder_id

        folder_name = Path(dir_path).name
        folder = await client.create_folder(folder_name, parent_id=parent_id)
        state.folders[dir_path] = SyncFolderEntry(folder_id=folder.id)
        logger.info("📁 created cloud folder  %s", dir_path)

    save_sync_state(state, project_dir)


async def run_sync_cycle(
    client: CollabMarkClient,
    sync_root: Path,
    folder_id: str,
    state: SyncState,
    project_dir: Path,
    api_key: str | None = None,
) -> list[SyncAction]:
    """Execute one full sync: scan, reconcile, execute actions.

    Returns the list of actions that were taken.
    """
    local_files = _list_local_md_files(sync_root)
    remote_files = await fetch_remote_files(client, folder_id)
    actions = reconcile(local_files, state, remote_files)

    await _ensure_cloud_folders(client, actions, state, folder_id, project_dir)

    for action in actions:
        await _execute_action(client, sync_root, state, action, folder_id, project_dir, api_key)

    return actions


async def _execute_action(
    client: CollabMarkClient,
    sync_root: Path,
    state: SyncState,
    action: SyncAction,
    root_folder_id: str,
    project_dir: Path,
    api_key: str | None = None,
) -> None:
    if action.kind == ActionKind.PUSH_NEW:
        folder_id = _resolve_folder_id(action.rel_path, state, root_folder_id)
        await push_new_file(client, sync_root, state, action.rel_path, folder_id, project_dir, api_key)

    elif action.kind == ActionKind.PUSH_UPDATE:
        assert action.doc_id is not None
        await push_update(client, sync_root, state, action.rel_path, action.doc_id, project_dir, api_key)

    elif action.kind in (ActionKind.PULL_NEW, ActionKind.PULL_UPDATE):
        assert action.doc_id is not None
        await pull_file(client, sync_root, state, action.rel_path, action.doc_id, project_dir)

    elif action.kind == ActionKind.DELETE_REMOTE:
        assert action.doc_id is not None
        await delete_remote(client, state, action.rel_path, action.doc_id, project_dir)

    elif action.kind == ActionKind.DELETE_LOCAL:
        delete_local(sync_root, state, action.rel_path, project_dir)

    elif action.kind == ActionKind.CONFLICT:
        _handle_conflict(sync_root, action)


def _resolve_folder_id(rel_path: str, state: SyncState, root_folder_id: str) -> str:
    """Find the cloud folder ID for a file's parent directory."""
    parent = str(Path(rel_path).parent)
    if parent == ".":
        return root_folder_id
    entry = state.folders.get(parent)
    return entry.folder_id if entry else root_folder_id


def _handle_conflict(sync_root: Path, action: SyncAction) -> None:
    """Log a conflict without overwriting either side."""
    logger.warning(
        "⚠ CONFLICT  %s — modified both locally and on cloud. Resolve manually. Local hash: %s, remote hash: %s",
        action.rel_path,
        action.local_hash,
        action.remote_hash,
    )
