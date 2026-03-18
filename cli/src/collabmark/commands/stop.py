"""``collabmark stop`` — stop sync daemons."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Prompt

from collabmark.lib.config import get_project_dir, load_sync_config
from collabmark.lib.registry import find_entry_by_path, get_running_syncs, stop_sync_process

console = Console()


def _stop_one(entry) -> bool:
    """Send SIGTERM to a single sync process with Rich output."""
    pid = entry.pid
    ok = stop_sync_process(entry)
    if ok:
        console.print(
            f"[green]✓[/green] Stopped [bold]{entry.folder_name}[/bold]  [dim]{entry.local_path}[/dim]  (PID {pid})"
        )
    else:
        console.print(f"[yellow]Sync '{entry.folder_name}' was not running.[/yellow]")
    return ok


@click.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    default=None,
    help="Stop the sync for a specific directory.",
)
@click.option("--all", "stop_all", is_flag=True, help="Stop all running syncs.")
def stop(path: str | None, stop_all: bool) -> None:
    """Stop a running sync.

    \b
    Examples:
      collabmark stop              Stop sync for current directory (or pick)
      collabmark stop --all        Stop all running syncs
      collabmark stop -p ~/notes   Stop sync for ~/notes
    """
    if stop_all:
        _stop_all_syncs()
        return

    if path:
        _stop_by_path(Path(path))
        return

    entry = find_entry_by_path(Path.cwd())
    if entry:
        _stop_by_path(Path(entry.local_path))
        return

    running = get_running_syncs()
    if not running:
        console.print("[yellow]No syncs are currently running.[/yellow]")
        return

    if len(running) == 1:
        _stop_one(running[0])
        return

    _interactive_stop(running)


def _stop_all_syncs() -> None:
    """Stop every running sync."""
    running = get_running_syncs()
    if not running:
        console.print("[yellow]No syncs are currently running.[/yellow]")
        return

    stopped = 0
    for entry in running:
        if _stop_one(entry):
            stopped += 1

    console.print(f"\n[dim]{stopped}/{len(running)} syncs stopped.[/dim]")


def _stop_by_path(target: Path) -> None:
    """Stop the sync for a specific directory."""
    abs_path = str(target.resolve())

    running = get_running_syncs()
    match = next((s for s in running if s.local_path == abs_path), None)

    if match:
        _stop_one(match)
        return

    entry = find_entry_by_path(target)
    if entry:
        project_dir = get_project_dir(entry.folder_id)
        config = load_sync_config(project_dir)
        name = config.folder_name if config else entry.folder_name
        console.print(f"[yellow]Sync for '{name}' is not running.[/yellow]")
    else:
        console.print("[yellow]No sync found for this directory.[/yellow]")


def _interactive_stop(running: list) -> None:
    """Show a numbered list of running syncs and let the user pick."""
    console.print("\n[bold]Multiple syncs are running. Choose which to stop:[/bold]\n")

    for i, s in enumerate(running, 1):
        console.print(f"  {i}. [bold]{s.folder_name}[/bold]  [dim]{s.local_path}[/dim]  (PID {s.pid})")

    all_idx = len(running) + 1
    console.print(f"  {all_idx}. [red]Stop all[/red]\n")

    selection = Prompt.ask("Enter number", default="1")
    try:
        num = int(selection)
    except ValueError:
        console.print("[red]Invalid selection.[/red]")
        return

    if num == all_idx:
        _stop_all_syncs()
    elif 1 <= num <= len(running):
        _stop_one(running[num - 1])
    else:
        console.print("[red]Invalid selection.[/red]")
