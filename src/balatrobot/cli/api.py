"""API command for interacting with running BalatroBot server."""

import json
from enum import StrEnum
from typing import Annotated

import httpx
import typer

from balatrobot.cli.client import APIError, BalatroClient
from balatrobot.state import StateFile


class Method(StrEnum):
    """Valid API methods."""

    ADD = "add"
    BUY = "buy"
    CASH_OUT = "cash_out"
    DISCARD = "discard"
    GAMESTATE = "gamestate"
    HEALTH = "health"
    LOAD = "load"
    MENU = "menu"
    NEXT_ROUND = "next_round"
    PACK = "pack"
    PLAY = "play"
    REARRANGE = "rearrange"
    REROLL = "reroll"
    SAVE = "save"
    SCREENSHOT = "screenshot"
    SELECT = "select"
    SELL = "sell"
    SET = "set"
    SKIP = "skip"
    START = "start"
    USE = "use"


def api(
    method: Annotated[Method, typer.Argument(help="API method to call")],
    params: Annotated[str, typer.Argument(help="JSON params object")] = "{}",
    host: Annotated[str | None, typer.Option(help="Server hostname")] = None,
    port: Annotated[int | None, typer.Option(help="Server port")] = None,
    index: Annotated[
        int | None, typer.Option("--index", "-i", help="Instance index (default: 0)")
    ] = None,
) -> None:
    """Call API endpoint on a running BalatroBot server."""
    # Validate JSON params
    try:
        params_dict = json.loads(params)
    except json.JSONDecodeError as e:
        typer.echo(f"Error: Invalid JSON params - {e}", err=True)
        raise typer.Exit(code=1)

    # Validate: --host and --port must be provided together or not at all
    if (host is None) != (port is None):
        typer.echo("Error: --host and --port must be provided together.", err=True)
        raise typer.Exit(code=1)

    # Resolve instance: explicit host+port, or discover from state file
    if host is not None and port is not None:
        target_host = host
        target_port = port
    else:
        try:
            info = StateFile.resolve(host=host, port=port, index=index)
            target_host = info.host
            target_port = info.port
        except Exception as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(code=1)

    # Make API call
    client = BalatroClient(host=target_host, port=target_port)
    try:
        result = client.call(method.value, params_dict)
        typer.echo(json.dumps(result, indent=2))
    except APIError as e:
        typer.echo(f"Error: {e.name} - {e.message}", err=True)
        raise typer.Exit(code=1)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        typer.echo(f"Error: Connection failed - {e}", err=True)
        raise typer.Exit(code=1)
