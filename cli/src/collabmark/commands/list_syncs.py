"""``collabmark list`` — list all registered syncs (alias for global status)."""

from __future__ import annotations

import click

from collabmark.commands.status import _show_global_status


@click.command("list")
def list_syncs() -> None:
    """List all registered CollabMark syncs.

    \b
    Shows a table of every sync project with its cloud folder,
    local path, status, last sync time, and PID.

    This is equivalent to running `collabmark status` outside
    any synced project directory.
    """
    _show_global_status()
