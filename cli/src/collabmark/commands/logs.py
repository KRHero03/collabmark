"""``collabmark logs`` — view sync log output."""

import click
from rich.console import Console

console = Console()


@click.command()
@click.option("--follow", "-f", is_flag=True, help="Follow log output in real time.")
@click.option("--lines", "-n", default=50, help="Number of lines to show.")
def logs(follow: bool, lines: int) -> None:
    """View the sync daemon log output."""
    console.print("[bold magenta]collabmark logs[/] — not yet implemented")
