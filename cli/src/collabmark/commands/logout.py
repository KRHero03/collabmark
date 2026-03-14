"""``collabmark logout`` — clear stored credentials and stop running syncs."""

from __future__ import annotations

import click
from rich.console import Console

from collabmark.lib.auth import clear_credentials
from collabmark.lib.registry import clear_stopped_entries, stop_all_syncs

console = Console()


@click.command()
def logout() -> None:
    """Log out by removing stored credentials from the OS keychain.

    Stops all running syncs first (they cannot continue without
    credentials), then clears stale registry entries.
    """
    stopped, total = stop_all_syncs()
    if total:
        console.print(f"[dim]Stopped {stopped}/{total} running sync(s).[/dim]")

    removed = clear_credentials()
    if removed:
        console.print("[green]Credentials removed from OS keychain.[/green]")
    else:
        console.print("[yellow]No stored credentials found.[/yellow]")

    cleaned = clear_stopped_entries()
    if cleaned:
        console.print(f"[dim]Cleaned {cleaned} stale registry entry/entries.[/dim]")

    console.print("[green]You are logged out.[/green]")
