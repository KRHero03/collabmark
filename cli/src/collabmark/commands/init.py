"""``collabmark init`` — initialize a directory for syncing."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console

from collabmark.lib.api import CollabMarkClient
from collabmark.lib.auth import AuthError, ensure_authenticated
from collabmark.lib.config import find_project_root

console = Console()


@click.command()
@click.argument("link", required=False, default=None)
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    default=None,
    help="Directory to initialise (defaults to current directory).",
)
def init(link: str | None, path: str | None) -> None:
    """Set up the current directory for CollabMark sync.

    This creates a .collabmark/ folder and links it to a cloud folder.
    After running init, use `collabmark start` to begin syncing.

    \b
    Examples:
      collabmark init                  Interactive folder picker
      collabmark init <share-link>     Join a shared folder by link
    """
    asyncio.run(_init_async(link, path))


async def _init_async(link: str | None, path_str: str | None) -> None:
    target = Path(path_str) if path_str else Path.cwd()

    existing = find_project_root(target)
    if existing == target:
        console.print(
            "[yellow]This directory is already set up for sync.[/yellow]\n"
            "Run [bold]collabmark start[/bold] to begin syncing, or "
            "[bold]collabmark status[/bold] to see current state."
        )
        return

    try:
        api_key, user_info = await ensure_authenticated()
    except AuthError as exc:
        console.print(f"[red]Not logged in:[/red] {exc}")
        console.print("Run [bold]collabmark login[/bold] first.")
        sys.exit(1)

    console.print(f"[green]✓[/green] Authenticated as {user_info.name} ({user_info.email})")

    from collabmark.commands.start import (
        _extract_folder_id_from_link,
        _init_project_config,
        _interactive_folder_picker,
    )

    async with CollabMarkClient(api_key) as client:
        if link:
            folder_id = _extract_folder_id_from_link(link)
            if folder_id:
                folder = await client.get_folder(folder_id)
                _init_project_config(target, client, folder.id, folder.name)
                console.print(f"[green]✓[/green] Linked to cloud folder [bold]{folder.name}[/bold]")
            else:
                console.print("[red]Could not parse folder link.[/red]")
                sys.exit(1)
        else:
            folder_id, folder_name = await _interactive_folder_picker(client, target)
            console.print(f"[green]✓[/green] Linked to cloud folder [bold]{folder_name}[/bold]")

    console.print(f"\nReady! Run [bold]collabmark start[/bold] in [dim]{target}[/dim] to begin syncing.")
