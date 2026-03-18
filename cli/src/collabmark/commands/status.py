"""``collabmark status`` — show the current sync state."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from collabmark.lib.config import get_project_dir, load_sync_config, load_sync_state
from collabmark.lib.daemon import is_process_alive, read_pid
from collabmark.lib.registry import find_entry_by_path, list_syncs

console = Console()

_STATUS_STYLE = {
    "running": "[green]Running[/green]",
    "stopped": "[dim]Stopped[/dim]",
    "error": "[red]Error[/red]",
}


def _format_ago(iso_ts: str | None) -> str:
    """Convert an ISO timestamp to a human-readable 'ago' string."""
    if not iso_ts:
        return "[dim]never[/dim]"
    try:
        dt = datetime.fromisoformat(iso_ts)
        delta = datetime.now(UTC) - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except (ValueError, TypeError):
        return "[dim]unknown[/dim]"


def _truncate_path(p: str, max_len: int = 40) -> str:
    """Shorten a path for table display, keeping the tail."""
    if len(p) <= max_len:
        return p
    return "..." + p[-(max_len - 3) :]


@click.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    default=None,
    help="Directory to check (defaults to current directory).",
)
def status(path: str | None) -> None:
    """Show the current sync state.

    \b
    Without --path: shows a global overview of all registered syncs.
    With --path:    shows detailed status for that specific project.

    \b
    Examples:
      collabmark status              Global overview of all syncs
      collabmark status -p ~/notes   Detailed status for ~/notes
    """
    if path:
        _show_project_status(Path(path))
    else:
        entry = find_entry_by_path(Path.cwd())
        if entry:
            _show_project_status_from_entry(entry)
        else:
            _show_global_status()


def _show_global_status() -> None:
    """Display a table of all registered syncs."""
    syncs = list_syncs()
    if not syncs:
        console.print("[yellow]No syncs registered.[/yellow] Run [bold]collabmark start[/bold] to begin.")
        return

    console.print()
    console.print("[bold]CollabMark Syncs[/bold]")
    console.print()

    table = Table(show_lines=False, padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("Cloud Folder", style="bold")
    table.add_column("Local Path")
    table.add_column("Status")
    table.add_column("Last Sync")
    table.add_column("Actions", justify="right")
    table.add_column("PID", justify="right", style="dim")

    for i, s in enumerate(syncs, 1):
        status_str = _STATUS_STYLE.get(s.status, s.status)
        if s.status == "error" and s.last_error:
            status_str += f" [dim]({s.last_error[:30]})[/dim]"

        table.add_row(
            str(i),
            s.folder_name,
            _truncate_path(s.local_path),
            status_str,
            _format_ago(s.last_synced_at),
            str(s.last_sync_actions),
            str(s.pid) if s.pid else "-",
        )

    console.print(table)
    console.print()

    running = sum(1 for s in syncs if s.status == "running")
    console.print(f"[dim]{running} running, {len(syncs)} total[/dim]")
    console.print()


def _show_project_status(start_dir: Path) -> None:
    """Display detailed status for a project by directory path."""
    entry = find_entry_by_path(start_dir)
    if not entry:
        console.print("[yellow]No active sync found.[/yellow] Run [bold]collabmark start[/bold] to begin.")
        return
    _show_project_status_from_entry(entry)


def _show_project_status_from_entry(entry) -> None:
    """Display detailed status for a single project from a registry entry."""
    project_dir = get_project_dir(entry.folder_id)
    config = load_sync_config(project_dir)
    state = load_sync_state(project_dir)

    pid = read_pid(entry.folder_id)
    is_running = pid is not None and is_process_alive(pid)

    if not is_running and entry.status == "running" and entry.pid:
        if is_process_alive(entry.pid):
            is_running = True
            pid = entry.pid

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()

    if config:
        table.add_row("Folder:", config.folder_name)
        table.add_row("User:", config.user_email)
        table.add_row("Server:", config.server_url)

    table.add_row("Local:", entry.local_path)
    table.add_row("Files:", f"{len(state.files)} synced")
    table.add_row("Folders:", f"{len(state.folders)} tracked")

    if is_running:
        table.add_row("Status:", f"[green]Running[/green] (PID {pid})")
    elif entry.status == "error":
        table.add_row("Status:", f"[red]Error[/red] [dim]({entry.last_error or ''})[/dim]")
    else:
        table.add_row("Status:", "[dim]Stopped[/dim]")

    if entry.last_synced_at:
        table.add_row("Last Sync:", _format_ago(entry.last_synced_at))

    console.print()
    console.print("[bold]CollabMark Sync Status[/bold]")
    console.print(table)
    console.print()
