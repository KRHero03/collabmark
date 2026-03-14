"""``collabmark clean`` — remove stale entries from the sync registry."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Prompt

from collabmark.lib.daemon import remove_pid_file
from collabmark.lib.registry import list_syncs, unregister_sync

console = Console()


@click.command()
@click.option("--all", "clean_all", is_flag=True, help="Remove all stopped syncs without prompting.")
@click.option("--force", is_flag=True, help="Also remove running syncs (does NOT stop them).")
def clean(clean_all: bool, force: bool) -> None:
    """Remove stale entries from the sync registry.

    \b
    Removes stopped syncs whose local directories no longer exist,
    or lets you interactively pick entries to remove.

    \b
    Examples:
      collabmark clean              Interactive picker
      collabmark clean --all        Remove all stopped entries
      collabmark clean --force      Remove all entries (including running)
    """
    syncs = list_syncs()
    if not syncs:
        console.print("[yellow]No syncs registered.[/yellow]")
        return

    if clean_all or force:
        _clean_batch(syncs, include_running=force)
        return

    stale = [s for s in syncs if s.status == "stopped"]
    if not stale:
        console.print("[green]No stale entries to clean.[/green] All syncs are running.")
        return

    if len(stale) == 1:
        entry = stale[0]
        _remove_entry(entry)
        return

    _interactive_clean(stale)


def _remove_entry(entry) -> None:
    """Remove a single registry entry and its associated files."""
    removed = unregister_sync(entry.local_path)
    if removed:
        if entry.folder_id:
            remove_pid_file(entry.folder_id)
        console.print(f"[green]✓[/green] Removed [bold]{entry.folder_name}[/bold]  [dim]{entry.local_path}[/dim]")
    else:
        console.print(f"[yellow]Entry not found: {entry.local_path}[/yellow]")


def _clean_batch(syncs: list, include_running: bool) -> None:
    """Remove matching entries in batch."""
    targets = syncs if include_running else [s for s in syncs if s.status == "stopped"]

    if not targets:
        console.print("[green]Nothing to clean.[/green]")
        return

    for entry in targets:
        _remove_entry(entry)

    console.print(f"\n[dim]{len(targets)} entries removed.[/dim]")


def _interactive_clean(stale: list) -> None:
    """Show a numbered list and let the user pick entries to remove."""
    console.print("\n[bold]Stale entries (stopped syncs):[/bold]\n")

    for i, s in enumerate(stale, 1):
        local_exists = Path(s.local_path).is_dir()
        exists_tag = "" if local_exists else "  [red](dir missing)[/red]"
        console.print(f"  {i}. [bold]{s.folder_name}[/bold]  [dim]{s.local_path}[/dim]{exists_tag}")

    all_idx = len(stale) + 1
    console.print(f"  {all_idx}. [red]Remove all[/red]\n")

    selection = Prompt.ask("Enter number", default="1")
    try:
        num = int(selection)
    except ValueError:
        console.print("[red]Invalid selection.[/red]")
        return

    if num == all_idx:
        for entry in stale:
            _remove_entry(entry)
        console.print(f"\n[dim]{len(stale)} entries removed.[/dim]")
    elif 1 <= num <= len(stale):
        _remove_entry(stale[num - 1])
    else:
        console.print("[red]Invalid selection.[/red]")
