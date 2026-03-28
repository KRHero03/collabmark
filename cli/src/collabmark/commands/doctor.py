"""Health check command for diagnosing sync issues."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import click
from rich.console import Console

from collabmark.lib.auth import load_api_key, load_metadata
from collabmark.lib.config import COLLABMARK_HOME
from collabmark.lib.registry import load_registry

console = Console()


def _check_mark(ok: bool) -> str:
    return "[green]✓[/green]" if ok else "[red]✗[/red]"


def _check_config_dir() -> bool:
    ok = COLLABMARK_HOME.is_dir()
    console.print(f"  {_check_mark(ok)} Config directory ({COLLABMARK_HOME})")
    return ok


def _check_credentials() -> tuple[bool, str | None]:
    meta = load_metadata()
    api_key = load_api_key()
    if not meta or not api_key:
        console.print(f"  {_check_mark(False)} Credentials (not logged in)")
        return False, None
    console.print(f"  {_check_mark(True)} Credentials (logged in as {meta.get('email', '?')})")
    return True, api_key


async def _check_server(api_key: str) -> bool:
    from collabmark.lib.api import CollabMarkClient

    try:
        async with CollabMarkClient(api_key) as client:
            await client.get_current_user()
        console.print(f"  {_check_mark(True)} Server reachable and auth valid")
        return True
    except Exception as exc:
        console.print(f"  {_check_mark(False)} Server ({exc})")
        return False


async def _check_websocket(api_key: str) -> bool:
    from collabmark.lib.config import get_api_url
    from collabmark.lib.crdt_sync import _build_ws_url

    try:
        from websockets.asyncio.client import connect

        ws_url = _build_ws_url("__health_check__", api_key, get_api_url())
        async with asyncio.timeout(5):
            async with connect(ws_url, close_timeout=2):
                pass
        console.print(f"  {_check_mark(True)} WebSocket connectivity")
        return True
    except Exception as exc:
        short = str(exc)[:60]
        console.print(f"  {_check_mark(False)} WebSocket ({short})")
        return False


def _check_active_syncs() -> bool:
    reg = load_registry()
    running = [e for e in reg.syncs if e.status == "running"]
    if not running:
        console.print(f"  {_check_mark(True)} No active syncs (nothing to check)")
        return True

    all_ok = True
    for entry in running:
        pid = entry.pid
        pid_alive = False
        if pid:
            try:
                os.kill(pid, 0)
                pid_alive = True
            except (OSError, ProcessLookupError):
                pass

        label = f"Sync {Path(entry.local_path).name}" if entry.local_path else f"Sync {entry.folder_id}"
        if pid_alive:
            console.print(f"  {_check_mark(True)} {label} (PID {pid} alive)")
        else:
            msg = f"PID {pid} dead — run `collabmark stop` then `collabmark start`"
            console.print(f"  {_check_mark(False)} {label} ({msg})")
            all_ok = False

        if entry.last_error:
            console.print(f"    [yellow]Last error: {entry.last_error}[/yellow]")

    return all_ok


def _check_keyring() -> bool:
    try:
        import keyring

        keyring.get_keyring()
        console.print(f"  {_check_mark(True)} Keyring backend available ({type(keyring.get_keyring()).__name__})")
        return True
    except Exception as exc:
        console.print(f"  {_check_mark(False)} Keyring ({exc})")
        return False


async def _run_checks() -> int:
    failures = 0
    console.print("\n[bold]CollabMark Doctor[/bold]\n")

    console.print("[bold]Environment[/bold]")
    if not _check_config_dir():
        failures += 1
    if not _check_keyring():
        failures += 1

    console.print("\n[bold]Authentication[/bold]")
    ok, api_key = _check_credentials()
    if not ok:
        failures += 1

    if api_key:
        console.print("\n[bold]Connectivity[/bold]")
        if not await _check_server(api_key):
            failures += 1
        if not await _check_websocket(api_key):
            failures += 1

    console.print("\n[bold]Active Syncs[/bold]")
    if not _check_active_syncs():
        failures += 1

    console.print()
    if failures == 0:
        console.print("[green bold]All checks passed.[/green bold]\n")
    else:
        console.print(f"[red bold]{failures} check(s) failed.[/red bold]\n")
    return failures


@click.command()
def doctor() -> None:
    """Run health checks on your CollabMark setup.

    Verifies config directory, credentials, server reachability,
    WebSocket connectivity, keyring access, and active sync health.
    """
    failures = asyncio.run(_run_checks())
    raise SystemExit(1 if failures else 0)
