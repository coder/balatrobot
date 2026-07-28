"""CLI entry point for BalatroBot."""

import typer

from balatrobot.cli.api import api
from balatrobot.cli.list import list_cmd
from balatrobot.cli.serve import serve
from balatrobot.cli.stop import stop

app = typer.Typer(
    name="balatrobot",
    help="BalatroBot - Balatro bot development framework",
    no_args_is_help=True,
)

# Register commands
app.command()(serve)
app.command()(api)
app.command(name="list")(list_cmd)
app.command()(stop)


def main() -> None:
    """Entry point for balatrobot CLI."""
    app()
