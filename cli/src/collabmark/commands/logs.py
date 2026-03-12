"""``collabmark logs`` — view sync log output."""

from __future__ import annotations

import json
import time

import click
from rich.console import Console

from collabmark.lib.logger import get_log_file

console = Console()

_LEVEL_STYLES = {
    "DEBUG": "dim",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold red",
}


def _format_log_line(line: str) -> str | None:
    """Parse a JSON log line and format it for display."""
    try:
        entry = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return line.strip() if line.strip() else None

    ts = entry.get("ts", "")
    level = entry.get("level", "INFO")
    message = entry.get("message", "")

    if ts and "T" in ts:
        ts = ts.split("T")[1][:8]

    style = _LEVEL_STYLES.get(level, "")
    return f"[dim]{ts}[/dim]  [{style}]{level:<7}[/{style}]  {message}"


@click.command()
@click.option("--follow", "-f", is_flag=True, help="Follow log output in real time.")
@click.option("--lines", "-n", default=50, show_default=True, help="Number of lines to show.")
def logs(follow: bool, lines: int) -> None:
    """View the sync daemon log output.

    \b
    Examples:
      collabmark logs              Show last 50 log entries
      collabmark logs -n 100       Show last 100 entries
      collabmark logs -f           Follow logs in real time (like tail -f)
    """
    log_file = get_log_file()

    if not log_file.is_file():
        console.print("[yellow]No log file found.[/yellow] Start syncing first with [bold]collabmark start[/bold].")
        return

    all_lines = log_file.read_text(encoding="utf-8").splitlines()
    tail = all_lines[-lines:] if len(all_lines) > lines else all_lines

    for raw in tail:
        formatted = _format_log_line(raw)
        if formatted:
            console.print(formatted)

    if not follow:
        return

    console.print("[dim]--- following (Ctrl+C to stop) ---[/dim]")
    try:
        with open(log_file, encoding="utf-8") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    formatted = _format_log_line(line)
                    if formatted:
                        console.print(formatted)
                else:
                    time.sleep(0.5)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped following logs.[/dim]")
