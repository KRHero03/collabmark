"""``collabmark status`` — show the current sync state."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from collabmark.lib.config import find_project_root, load_sync_config, load_sync_state
from collabmark.lib.daemon import is_process_alive, read_pid

console = Console()


@click.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    default=None,
    help="Directory to check (defaults to current directory).",
)
def status(path: str | None) -> None:
    """Show the current sync state for this directory.

    \b
    Displays:
      - Which cloud folder is linked
      - How many files and folders are synced
      - Whether the background daemon is running
    """
    start_dir = Path(path) if path else Path.cwd()
    project_root = find_project_root(start_dir)

    if not project_root:
        console.print("[yellow]No active sync found.[/yellow] Run [bold]collabmark start[/bold] to begin.")
        return

    project_dir = project_root / ".collabmark"
    config = load_sync_config(project_dir)
    state = load_sync_state(project_dir)
    pid = read_pid()
    is_running = pid is not None and is_process_alive(pid)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()

    if config:
        table.add_row("Folder:", config.folder_name)
        table.add_row("User:", config.user_email)
        table.add_row("Server:", config.server_url)

    table.add_row("Local:", str(project_root))
    table.add_row("Files:", f"{len(state.files)} synced")
    table.add_row("Folders:", f"{len(state.folders)} tracked")

    if is_running:
        table.add_row("Status:", f"[green]Running[/green] (PID {pid})")
    else:
        table.add_row("Status:", "[dim]Stopped[/dim]")

    console.print()
    console.print("[bold]CollabMark Sync Status[/bold]")
    console.print(table)
    console.print()
