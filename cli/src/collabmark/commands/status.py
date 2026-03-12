"""``collabmark status`` — show the current sync state."""

import click
from rich.console import Console

console = Console()


@click.command()
def status() -> None:
    """Show the current sync state for this directory."""
    console.print("[bold cyan]collabmark status[/] — not yet implemented")
