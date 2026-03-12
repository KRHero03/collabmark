"""Root CLI group and top-level commands."""

import click

from collabmark import __version__
from collabmark.commands.login import login
from collabmark.commands.logout import logout
from collabmark.commands.logs import logs
from collabmark.commands.start import start
from collabmark.commands.status import status
from collabmark.commands.stop import stop

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=__version__, prog_name="collabmark")
def cli() -> None:
    """CollabMark — keep local markdown files in sync with your team's cloud workspace."""


cli.add_command(login)
cli.add_command(logout)
cli.add_command(start)
cli.add_command(status)
cli.add_command(stop)
cli.add_command(logs)
