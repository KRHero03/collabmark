"""List and manage unresolved sync conflict files."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from collabmark.lib.registry import load_registry

console = Console()

_CONFLICT_GLOB = "*.conflict.*.*"


def _find_conflict_files(directory: Path) -> list[Path]:
    """Find all .conflict.<timestamp>.md files recursively."""
    return sorted(directory.rglob(_CONFLICT_GLOB))


@click.command()
@click.argument("path", required=False, type=click.Path(exists=True))
def conflicts(path: str | None) -> None:
    """List unresolved sync conflict files.

    Shows all .conflict files in the given PATH or across all active syncs.
    """
    if path:
        targets = [Path(path)]
    else:
        reg = load_registry()
        targets = [Path(e.local_path) for e in reg.syncs if e.local_path]
        if not targets:
            targets = [Path.cwd()]

    all_conflicts: list[tuple[Path, Path]] = []
    for target in targets:
        target = target.resolve()
        if target.is_dir():
            for cf in _find_conflict_files(target):
                all_conflicts.append((target, cf))

    if not all_conflicts:
        console.print("[green]No conflict files found.[/green]")
        return

    table = Table(title="Unresolved Conflicts", show_lines=False)
    table.add_column("Sync Root", style="dim")
    table.add_column("Conflict File", style="yellow")
    table.add_column("Size", justify="right")

    for root, cf in all_conflicts:
        rel = cf.relative_to(root) if cf.is_relative_to(root) else cf
        size = cf.stat().st_size
        table.add_row(root.name, str(rel), f"{size:,} B")

    console.print(table)
    console.print(
        f"\n[dim]Found {len(all_conflicts)} conflict(s). "
        "Compare with the original file and delete the .conflict file when resolved.[/dim]"
    )
