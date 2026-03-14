"""Root CLI group and top-level commands."""

import click
from rich.console import Console
from rich.panel import Panel

from collabmark import __version__
from collabmark.commands.clean import clean
from collabmark.commands.init import init
from collabmark.commands.list_syncs import list_syncs
from collabmark.commands.login import login
from collabmark.commands.logout import logout
from collabmark.commands.logs import logs
from collabmark.commands.start import start
from collabmark.commands.status import status
from collabmark.commands.stop import stop

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

_WELCOME = """\
[bold]CollabMark[/bold] keeps your local markdown files in sync with your
team's cloud workspace — bidirectionally and in real time.

[bold cyan]Quick start:[/bold cyan]

  [green]1.[/green] Log in               [dim]collabmark login[/dim]
  [green]2.[/green] Start syncing         [dim]collabmark start[/dim]
  [green]3.[/green] Check sync status     [dim]collabmark status[/dim]
  [green]4.[/green] View logs             [dim]collabmark logs -f[/dim]

[dim]Run[/dim] [bold]collabmark <command> -h[/bold] [dim]for detailed help on any command.[/dim]"""


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.version_option(version=__version__, prog_name="collabmark")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """CollabMark — keep local markdown files in sync with your team's cloud workspace.

    \b
    Quick start:
      1. collabmark login          Log in via your browser
      2. collabmark start           Start syncing the current directory
      3. collabmark status          Check what's being synced
      4. collabmark logs -f         Follow the sync log in real time

    Run `collabmark <command> -h` for detailed help on any command.
    """
    if ctx.invoked_subcommand is None:
        console = Console()
        console.print()
        console.print(
            Panel(
                _WELCOME,
                title=f"CollabMark CLI v{__version__}",
                border_style="cyan",
                padding=(1, 2),
            )
        )
        console.print()


cli.add_command(init)
cli.add_command(login)
cli.add_command(logout)
cli.add_command(start)
cli.add_command(status)
cli.add_command(stop)
cli.add_command(logs)
cli.add_command(list_syncs, name="list")
cli.add_command(clean)
