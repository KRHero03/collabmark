"""``collabmark login`` — authenticate with the CollabMark API."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.panel import Panel

from collabmark.lib.auth import (
    AuthError,
    KeyringUnavailableError,
    LoginMetadata,
    mask_api_key,
    save_api_key,
    save_metadata,
    validate_api_key,
)
from collabmark.lib.browser_auth import browser_login

console = Console()


def _show_success(name: str, email: str, api_key: str, method: str) -> None:
    console.print(
        Panel(
            f"[bold green]Logged in successfully![/bold green]\n\n"
            f"  Name:     {name}\n"
            f"  Email:    {email}\n"
            f"  Key:      {mask_api_key(api_key)}\n"
            f"  Method:   {method}\n"
            f"  Storage:  OS Keychain",
            title="CollabMark",
            border_style="green",
        )
    )


@click.command()
@click.option(
    "--api-key",
    default=None,
    envvar="COLLABMARK_API_KEY",
    help="Use an API key instead of browser login (fallback).",
)
@click.option(
    "--server",
    envvar="COLLABMARK_API_URL",
    default=None,
    help="CollabMark server URL override.",
)
def login(api_key: str | None, server: str | None) -> None:
    """Log in to CollabMark.

    Opens your browser for a one-click Google login. The CLI receives
    the credentials automatically — no copy-pasting needed.

    For environments without a browser, pass --api-key as a fallback.
    Generate an API key from the CollabMark web app (Settings > API Keys).
    """
    if api_key:
        _login_with_api_key(api_key.strip(), server)
    else:
        _login_with_browser(server)


def _login_with_browser(server: str | None) -> None:
    console.print(
        "\n[bold]Opening your browser to log in...[/bold]\n"
        "[dim]Waiting for authentication (you have 2 minutes)...[/dim]\n"
    )

    try:
        raw_key, user_info = asyncio.run(browser_login(api_url=server))
    except KeyringUnavailableError as exc:
        console.print(f"\n[red bold]Cannot store credentials:[/red bold] {exc}")
        raise SystemExit(1) from exc
    except AuthError as exc:
        console.print(f"\n[red bold]Login failed:[/red bold] {exc}")
        console.print(
            "\n[dim]Tip: if you don't have a browser, use "
            "[bold]collabmark login --api-key YOUR_KEY[/bold][/dim]"
        )
        raise SystemExit(1) from exc

    save_metadata(
        LoginMetadata(email=user_info.email, name=user_info.name, server_url=server)
    )
    _show_success(user_info.name, user_info.email, raw_key, "Browser OAuth")


def _login_with_api_key(api_key: str, server: str | None) -> None:
    if not api_key:
        console.print("[red]No API key provided. Aborting.[/red]")
        raise SystemExit(1)

    console.print("\n[dim]Validating API key...[/dim]")

    try:
        user_info = asyncio.run(validate_api_key(api_key, api_url=server))
    except AuthError as exc:
        console.print(f"\n[red bold]Login failed:[/red bold] {exc}")
        raise SystemExit(1) from exc

    try:
        save_api_key(api_key)
    except KeyringUnavailableError as exc:
        console.print(f"\n[red bold]Cannot store credentials:[/red bold] {exc}")
        raise SystemExit(1) from exc

    save_metadata(
        LoginMetadata(email=user_info.email, name=user_info.name, server_url=server)
    )
    _show_success(user_info.name, user_info.email, api_key, "API Key")
