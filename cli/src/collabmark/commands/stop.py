"""``collabmark stop`` — stop the sync daemon."""

from __future__ import annotations

import click
from rich.console import Console

from collabmark.lib.daemon import is_process_alive, read_pid, remove_pid_file, stop_daemon

console = Console()


@click.command()
def stop() -> None:
    """Stop the background sync daemon.

    Sends a graceful stop signal. The daemon completes any
    in-progress sync before shutting down.
    """
    pid = read_pid()

    if pid is None:
        console.print("[yellow]No daemon is running.[/yellow]")
        return

    if not is_process_alive(pid):
        remove_pid_file()
        console.print("[yellow]Daemon (PID {pid}) is no longer running. Cleaned up PID file.[/yellow]")
        return

    if stop_daemon():
        console.print(f"[green]✓[/green] Sent stop signal to daemon (PID {pid}).")
    else:
        console.print(f"[red]✗[/red] Failed to stop daemon (PID {pid}).")
