"""``collabmark start`` — begin syncing a folder with CollabMark cloud."""

import click
from rich.console import Console

console = Console()


@click.command()
@click.argument("link", required=False, default=None)
@click.option("--daemon", "-d", is_flag=True, help="Run as a background service.")
def start(link: str | None, daemon: bool) -> None:
    """Start syncing markdown files with CollabMark.

    Optionally pass a LINK (share URL) to join a specific cloud folder.
    Without a link, you'll be prompted to choose a folder interactively.
    """
    console.print("[bold green]collabmark start[/] — not yet implemented")
    if link:
        console.print(f"  link: {link}")
    if daemon:
        console.print("  mode: daemon (background)")
