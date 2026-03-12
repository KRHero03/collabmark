"""``collabmark stop`` — stop the sync daemon."""

import click
from rich.console import Console

console = Console()


@click.command()
def stop() -> None:
    """Stop the background sync daemon."""
    console.print("[bold yellow]collabmark stop[/] — not yet implemented")
