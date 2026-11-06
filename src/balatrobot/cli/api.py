"""API command for interacting with running BalatroBot server."""

import json
from enum import StrEnum
from typing import Annotated

import httpx
import typer

from balatrobot.cli.client import APIError, BalatroClient


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
    REROLL_BOSS = "reroll_boss"
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
    host: Annotated[str, typer.Option(help="Server hostname")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Server port")] = 12346,
) -> None:
    """Call API endpoint on a running BalatroBot server."""
    # Validate JSON params
    try:
        params_dict = json.loads(params)
    except json.JSONDecodeError as e:
        typer.echo(f"Error: Invalid JSON params - {e}", err=True)
        raise typer.Exit(code=1)

    # Make API call
    client = BalatroClient(host=host, port=port)
    try:
        result = client.call(method.value, params_dict)
        typer.echo(json.dumps(result, indent=2))
    except APIError as e:
        typer.echo(f"Error: {e.name} - {e.message}", err=True)
        raise typer.Exit(code=1)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        typer.echo(f"Error: Connection failed - {e}", err=True)
        raise typer.Exit(code=1)
