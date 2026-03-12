"""``collabmark logout`` — clear stored credentials."""

from __future__ import annotations

import click
from rich.console import Console

from collabmark.lib.auth import clear_credentials

console = Console()


@click.command()
def logout() -> None:
    """Log out by removing stored credentials from the OS keychain."""
    removed = clear_credentials()
    if removed:
        console.print("[green]Credentials removed from OS keychain. You are logged out.[/green]")
    else:
        console.print("[yellow]No stored credentials found.[/yellow]")
