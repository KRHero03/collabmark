"""``collabmark logs`` — view sync log output."""

from __future__ import annotations

import json
import time
from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Prompt

from collabmark.lib.config import get_project_dir, load_sync_config
from collabmark.lib.logger import get_log_file, list_log_files
from collabmark.lib.registry import find_entry_by_path, load_registry

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


def _resolve_log_file(folder: str | None):
    """Determine which log file to show.

    Priority:
    1. Explicit --folder flag
    2. Current project directory's folder_id
    3. Interactive picker if multiple logs exist
    4. Legacy sync.log fallback
    """
    if folder:
        log_file = get_log_file(folder)
        if log_file.is_file():
            return log_file
        console.print(f"[yellow]No log file for folder '{folder}'.[/yellow]")
        return None

    entry = find_entry_by_path(Path.cwd())
    if entry:
        project_dir = get_project_dir(entry.folder_id)
        config = load_sync_config(project_dir)
        if config:
            log_file = get_log_file(config.folder_id)
            if log_file.is_file():
                return log_file

    available = list_log_files()
    if not available:
        legacy = get_log_file()
        return legacy if legacy.is_file() else None

    if len(available) == 1:
        return available[0][1]

    registry = load_registry()
    console.print("\n[bold]Choose a sync to view logs for:[/bold]\n")
    for i, (fid, path) in enumerate(available, 1):
        entry = registry.syncs.get(next((k for k, v in registry.syncs.items() if v.folder_id == fid), ""))
        label = entry.folder_name if entry else fid
        local = entry.local_path if entry else ""
        console.print(f"  {i}. {label}  [dim]{local}[/dim]")

    console.print()
    selection = Prompt.ask("Enter number", default="1")
    try:
        idx = int(selection) - 1
        if 0 <= idx < len(available):
            return available[idx][1]
    except ValueError:
        pass
    console.print("[red]Invalid selection.[/red]")
    return None


@click.command()
@click.option("--follow", "-f", is_flag=True, help="Follow log output in real time.")
@click.option("--lines", "-n", default=50, show_default=True, help="Number of lines to show.")
@click.option("--folder", default=None, help="Show logs for a specific folder ID.")
@click.option("--all-syncs", "show_all", is_flag=True, help="Show interleaved logs from all syncs.")
def logs(follow: bool, lines: int, folder: str | None, show_all: bool) -> None:
    """View the sync daemon log output.

    \b
    Examples:
      collabmark logs              Show logs for current project
      collabmark logs -n 100       Show last 100 entries
      collabmark logs -f           Follow logs in real time (like tail -f)
      collabmark logs --all-syncs  Show logs from all syncs, interleaved
    """
    if show_all:
        _show_all_logs(lines, follow)
        return

    log_file = _resolve_log_file(folder)
    if not log_file or not log_file.is_file():
        console.print("[yellow]No log file found.[/yellow] Start syncing first with [bold]collabmark start[/bold].")
        return

    _tail_log(log_file, lines, follow)


def _tail_log(log_file, lines: int, follow: bool) -> None:
    """Display the tail of a single log file, optionally following."""
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


def _show_all_logs(lines: int, follow: bool) -> None:
    """Interleave log lines from all per-project log files, sorted by timestamp."""
    available = list_log_files()
    if not available:
        legacy = get_log_file()
        if legacy.is_file():
            _tail_log(legacy, lines, follow)
            return
        console.print("[yellow]No log files found.[/yellow]")
        return

    all_entries: list[tuple[str, str]] = []
    for _fid, path in available:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
                ts = entry.get("ts", "")
                all_entries.append((ts, line))
            except (json.JSONDecodeError, ValueError):
                all_entries.append(("", line))

    all_entries.sort(key=lambda x: x[0])
    tail = all_entries[-lines:] if len(all_entries) > lines else all_entries

    for _ts, raw in tail:
        formatted = _format_log_line(raw)
        if formatted:
            console.print(formatted)

    if follow:
        console.print("[dim]--all-syncs follow not supported. Use --folder or run from a project dir.[/dim]")
