"""``collabmark start`` — begin syncing a folder with CollabMark cloud."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Prompt

from collabmark.lib.api import CollabMarkClient
from collabmark.lib.auth import AuthError, UserInfo, ensure_authenticated
from collabmark.lib.config import (
    find_project_root,
    get_api_url,
    init_project,
    load_sync_config,
    load_sync_state,
)
from collabmark.lib.daemon import daemonize, remove_pid_file, write_pid_file
from collabmark.lib.logger import setup_logging
from collabmark.lib.registry import mark_stopped, register_sync, update_heartbeat
from collabmark.lib.sync_engine import ActionKind, run_sync_cycle
from collabmark.lib.watcher import DebouncedWatcher
from collabmark.types import SyncConfig

console = Console()
logger = logging.getLogger(__name__)


@click.command()
@click.argument("link", required=False, default=None)
@click.option("--daemon", "-d", is_flag=True, help="Run as a background service.")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    default=None,
    help="Local directory to sync (defaults to current directory).",
)
@click.option(
    "--interval",
    type=float,
    default=10.0,
    show_default=True,
    help="Seconds between cloud poll cycles.",
)
def start(link: str | None, daemon: bool, path: str | None, interval: float) -> None:
    """Start syncing markdown files with CollabMark.

    \b
    Examples:
      collabmark start                   Sync current dir (foreground)
      collabmark start <share-link>      Join a shared folder by link
      collabmark start -d                Run sync in the background
      collabmark start -p ~/notes        Sync a specific directory

    The CLI monitors your local .md files and the cloud folder, keeping
    them in sync bidirectionally. Press Ctrl+C to stop when running
    in the foreground, or use `collabmark stop` for background mode.
    """
    if daemon:
        _launch_daemon(link, path, interval)
    else:
        try:
            asyncio.run(_start_async(link, path, interval))
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped.[/dim]")


def _launch_daemon(link: str | None, path_str: str | None, interval: float) -> None:
    """Fork to background and start the sync loop as a daemon."""
    console.print("[dim]Starting background sync daemon...[/dim]")
    daemonize()
    setup_logging(log_to_file=True)
    try:
        asyncio.run(_start_async(link, path_str, interval, is_daemon=True))
    finally:
        pass


async def _start_async(
    link: str | None,
    path_str: str | None,
    interval: float,
    is_daemon: bool = False,
) -> None:
    sync_root = Path(path_str) if path_str else Path.cwd()

    api_key, user_info = await _authenticate()
    console.print(f"[green]✓[/green] {user_info.name} ({user_info.email})")

    async with CollabMarkClient(api_key) as client:
        folder_id, folder_name = await _resolve_folder(client, sync_root, link, user_info)
        console.print(f"[green]✓[/green] Syncing [bold]{sync_root.name}/[/bold] ↔ [bold]{folder_name}[/bold]")

        setup_logging(log_to_file=True, folder_id=folder_id)

        if is_daemon:
            write_pid_file(os.getpid(), folder_id)

        config = load_sync_config(sync_root / ".collabmark")
        register_sync(
            local_path=str(sync_root),
            folder_id=folder_id,
            folder_name=folder_name,
            server_url=config.server_url if config else get_api_url(),
            user_email=user_info.email,
            pid=os.getpid(),
        )

        project_dir = sync_root / ".collabmark"
        state = load_sync_state(project_dir)

        try:
            console.print("[dim]Running initial sync...[/dim]")
            actions = await run_sync_cycle(client, sync_root, folder_id, state, project_dir, api_key)
            _print_sync_summary(actions)
            update_heartbeat(str(sync_root), len(actions))

            console.print(f"[green]✓[/green] Watching for changes (poll every {interval}s)")
            console.print("[dim]Press Ctrl+C to stop.[/dim]")
            await _watch_loop(client, sync_root, folder_id, state, project_dir, interval, api_key)
        finally:
            mark_stopped(str(sync_root))
            if is_daemon:
                remove_pid_file(folder_id)


async def _authenticate() -> tuple:
    """Authenticate and return (api_key, user_info)."""
    try:
        return await ensure_authenticated()
    except AuthError as exc:
        console.print(f"[red]✗[/red] {exc}")
        sys.exit(1)


async def _resolve_folder(
    client: CollabMarkClient,
    sync_root: Path,
    link: str | None,
    user_info: UserInfo | None = None,
) -> tuple[str, str]:
    """Determine the cloud folder to sync with.

    Priority:
    1. Existing .collabmark/config.json in sync_root (resume)
    2. Link argument (join via URL -- extract folder ID)
    3. Interactive folder picker
    """
    existing_root = find_project_root(sync_root)
    if existing_root == sync_root:
        config = load_sync_config(sync_root / ".collabmark")
        if config:
            console.print(f"[dim]Resuming sync with '{config.folder_name}'[/dim]")
            return config.folder_id, config.folder_name

    if link:
        folder_id = _extract_folder_id_from_link(link)
        if folder_id:
            folder = await client.get_folder(folder_id)
            _init_project_config(sync_root, client, folder.id, folder.name, user_info)
            return folder.id, folder.name

    return await _interactive_folder_picker(client, sync_root, user_info)


def _extract_folder_id_from_link(link: str) -> str | None:
    """Try to extract a folder ID from a CollabMark URL.

    Supports formats like:
    - https://app.collabmark.io/folder/abc123
    - abc123 (bare ID)
    """
    if "/" in link:
        parts = link.rstrip("/").split("/")
        folder_idx = None
        for i, part in enumerate(parts):
            if part == "folder":
                folder_idx = i
                break
        if folder_idx is not None and folder_idx + 1 < len(parts):
            return parts[folder_idx + 1]
        return parts[-1]
    return link


def _init_project_config(
    sync_root: Path,
    client: CollabMarkClient,
    folder_id: str,
    folder_name: str,
    user_info: UserInfo | None = None,
) -> None:
    """Initialise .collabmark/ with config for the given folder."""
    config = SyncConfig(
        server_url=get_api_url(),
        folder_id=folder_id,
        folder_name=folder_name,
        user_id=user_info.id if user_info else "",
        user_email=user_info.email if user_info else "",
    )
    init_project(sync_root, config)


async def _interactive_folder_picker(
    client: CollabMarkClient,
    sync_root: Path,
    user_info: UserInfo | None = None,
) -> tuple[str, str]:
    """Let the user choose from their folders or create a new one."""
    console.print("\n[bold]Choose a cloud folder to sync:[/bold]\n")

    contents = await client.list_folder_contents()
    shared = await client.list_shared_folders()

    choices: list[tuple[str, str]] = []

    if contents.folders:
        console.print("[dim]Your folders:[/dim]")
        for f in contents.folders:
            idx = len(choices) + 1
            console.print(f"  {idx}. {f.name}")
            choices.append((f.id, f.name))

    if shared:
        console.print("[dim]Shared with you:[/dim]")
        for sf in shared:
            idx = len(choices) + 1
            console.print(f"  {idx}. {sf.name} [dim](by {sf.owner_name})[/dim]")
            choices.append((sf.id, sf.name))

    new_idx = len(choices) + 1
    console.print(f"  {new_idx}. [green]+ Create new folder[/green]\n")

    selection = Prompt.ask(
        "Enter number",
        default="1" if choices else str(new_idx),
    )

    try:
        num = int(selection)
    except ValueError:
        console.print("[red]Invalid selection.[/red]")
        sys.exit(1)

    if num == new_idx:
        name = Prompt.ask("Folder name", default=sync_root.name)
        folder = await client.create_folder(name)
        console.print(f"[green]✓[/green] Created folder '{folder.name}'")
        _init_project_config(sync_root, client, folder.id, folder.name, user_info)
        return folder.id, folder.name

    if 1 <= num <= len(choices):
        folder_id, folder_name = choices[num - 1]
        _init_project_config(sync_root, client, folder_id, folder_name, user_info)
        return folder_id, folder_name

    console.print("[red]Invalid selection.[/red]")
    sys.exit(1)


def _print_sync_summary(actions: list) -> None:
    """Print a summary of the initial sync."""
    if not actions:
        console.print("[green]✓[/green] Everything is up to date.")
        return

    counts: dict[str, int] = {}
    for a in actions:
        label = {
            ActionKind.PUSH_NEW: "pushed (new)",
            ActionKind.PUSH_UPDATE: "pushed (update)",
            ActionKind.PULL_NEW: "pulled (new)",
            ActionKind.PULL_UPDATE: "pulled (update)",
            ActionKind.DELETE_LOCAL: "deleted locally",
            ActionKind.DELETE_REMOTE: "deleted remotely",
            ActionKind.CONFLICT: "conflicts",
        }.get(a.kind, str(a.kind))
        counts[label] = counts.get(label, 0) + 1

    parts = [f"{v} {k}" for k, v in counts.items()]
    console.print(f"[green]✓[/green] Sync complete: {', '.join(parts)}")


async def _watch_loop(
    client: CollabMarkClient,
    sync_root: Path,
    folder_id: str,
    state,
    project_dir: Path,
    interval: float,
    api_key: str | None = None,
) -> None:
    """Run periodic sync cycles + file watching until interrupted."""
    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()

    def _signal_handler(sig, frame):
        stop_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    def on_file_change():
        asyncio.run_coroutine_threadsafe(
            _sync_once(client, sync_root, folder_id, state, project_dir, api_key),
            loop,
        )

    watcher = DebouncedWatcher(sync_root, on_change=on_file_change)
    watcher.start()

    try:
        while not stop_event.is_set():
            await _sync_once(client, sync_root, folder_id, state, project_dir, api_key)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
    finally:
        watcher.stop()
        console.print("[dim]Final sync...[/dim]")
        await _sync_once(client, sync_root, folder_id, state, project_dir, api_key)
        console.print("[green]✓[/green] Stopped.")


async def _sync_once(client, sync_root, folder_id, state, project_dir, api_key=None):
    """Run a single sync cycle, catching and logging errors."""
    try:
        actions = await run_sync_cycle(client, sync_root, folder_id, state, project_dir, api_key)
        update_heartbeat(str(sync_root), len(actions))
        tracked = len(state.files)
        logger.debug("Sync cycle: %d actions (%d files tracked)", len(actions), tracked)
    except Exception as exc:
        update_heartbeat(str(sync_root), 0, error=str(exc))
        console.print(f"[yellow]⚠[/yellow] Sync error: {exc}")
