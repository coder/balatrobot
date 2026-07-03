"""API command for interacting with running BalatroBot server."""

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import httpx
import typer

from balatrobot.cli.client import APIError, BalatroClient
from balatrobot.state import StateFile


class Method(StrEnum):
    """Valid API methods."""

    ADD = "add"
    BUY = "buy"
    BUY_AND_USE = "buy_and_use"
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


# ---------------------------------------------------------------------------
# Replay helpers
# ---------------------------------------------------------------------------


def _load_requests(path: Path) -> list[dict]:
    """Load and validate a JSONL requests file.

    Returns list of parsed JSON-RPC request dicts.
    Raises typer.Exit on validation failure.
    """
    lines = path.read_text().splitlines()
    if not lines:
        typer.echo("Error: requests file is empty", err=True)
        raise typer.Exit(code=1)

    requests: list[dict] = []
    for i, line in enumerate(lines, 1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            typer.echo(f"Error: invalid JSON on line {i}: {e}", err=True)
            raise typer.Exit(code=1)
        if not isinstance(obj, dict) or "method" not in obj:
            typer.echo(f"Error: line {i} is not a valid JSON-RPC request", err=True)
            raise typer.Exit(code=1)
        requests.append(obj)
    return requests


def _load_responses(path: Path) -> list[dict]:
    """Load a JSONL responses file.

    Returns list of parsed JSON-RPC response dicts.
    Raises typer.Exit on validation failure.
    """
    lines = path.read_text().splitlines()
    responses: list[dict] = []
    for i, line in enumerate(lines, 1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            typer.echo(f"Error: invalid JSON in responses on line {i}: {e}", err=True)
            raise typer.Exit(code=1)
        responses.append(obj)
    return responses


def _replay(
    requests: list[dict],
    responses: list[dict] | None,
    client: BalatroClient,
) -> None:
    """Replay requests against a live server, optionally verifying responses.

    Raises typer.Exit on first error or divergence.
    """
    try:
        from tqdm import tqdm as _tqdm

        iterator = _tqdm(requests, desc="Replaying", unit="req")
    except ImportError:
        iterator = requests

    for i, req in enumerate(iterator):
        method = req["method"]
        params = req.get("params", {})

        try:
            result = client.call(method, params)
        except APIError as e:
            typer.echo(
                f"\nError: API error on request {i + 1}: {e.name} - {e.message}",
                err=True,
            )
            raise typer.Exit(code=1)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            typer.echo(f"\nError: connection failed on request {i + 1}: {e}", err=True)
            raise typer.Exit(code=1)

        if responses is not None:
            expected = responses[i]
            expected_result = expected.get("result")
            if result != expected_result:
                typer.echo(f"\nDivergence at request {i + 1}:", err=True)
                typer.echo(f"  expected: {json.dumps(expected, indent=2)}", err=True)
                typer.echo(
                    f"  actual:   {json.dumps({'jsonrpc': '2.0', 'result': result, 'id': req.get('id')}, indent=2)}",
                    err=True,
                )
                raise typer.Exit(code=1)

    typer.echo(f"Replayed {len(requests)} requests successfully.")


# ---------------------------------------------------------------------------
# Resolve host/port (shared between single-call and replay)
# ---------------------------------------------------------------------------


def _resolve_target(
    host: str | None,
    port: int | None,
    index: int | None,
) -> tuple[str, int]:
    """Resolve host and port from explicit values or state file."""
    if (host is None) != (port is None):
        typer.echo("Error: --host and --port must be provided together.", err=True)
        raise typer.Exit(code=1)

    if host is not None and port is not None:
        return host, port

    try:
        info = StateFile.resolve(index=index)
        return info.host, info.port
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


def api(
    method: Annotated[
        Method | None,
        typer.Argument(help="API method to call"),
    ] = None,
    params: Annotated[
        str,
        typer.Argument(help="JSON params object"),
    ] = "{}",
    host: Annotated[str | None, typer.Option(help="Server hostname")] = None,
    port: Annotated[int | None, typer.Option(help="Server port")] = None,
    index: Annotated[
        int | None, typer.Option("--index", "-i", help="Instance index (default: 0)")
    ] = None,
    requests_path: Annotated[
        Path | None,
        typer.Option("--requests", help="JSONL file of requests to replay"),
    ] = None,
    responses_path: Annotated[
        Path | None,
        typer.Option("--responses", help="JSONL file of responses to verify against"),
    ] = None,
) -> None:
    """Call API endpoint on a running BalatroBot server.

    Use --requests to replay a JSONL trace file. Mutually exclusive with
    positional METHOD and PARAMS arguments.
    """
    # --requests is mutually exclusive with positional method/params
    if requests_path is not None:
        if method is not None:
            typer.echo(
                "Error: --requests is mutually exclusive with positional METHOD.",
                err=True,
            )
            raise typer.Exit(code=1)

        if not requests_path.exists():
            typer.echo(f"Error: requests file not found: {requests_path}", err=True)
            raise typer.Exit(code=1)

        reqs = _load_requests(requests_path)

        resps: list[dict] | None = None
        if responses_path is not None:
            if not responses_path.exists():
                typer.echo(
                    f"Error: responses file not found: {responses_path}", err=True
                )
                raise typer.Exit(code=1)
            resps = _load_responses(responses_path)
            if len(resps) != len(reqs):
                typer.echo(
                    f"Error: line count mismatch — {len(reqs)} requests vs "
                    f"{len(resps)} responses",
                    err=True,
                )
                raise typer.Exit(code=1)

        target_host, target_port = _resolve_target(host, port, index)
        client = BalatroClient(host=target_host, port=target_port)
        _replay(reqs, resps, client)
        return

    # Single-call mode
    if method is None:
        typer.echo("Error: METHOD is required when not using --requests.", err=True)
        raise typer.Exit(code=1)

    # Validate JSON params
    try:
        params_dict = json.loads(params)
    except json.JSONDecodeError as e:
        typer.echo(f"Error: Invalid JSON params - {e}", err=True)
        raise typer.Exit(code=1)

    target_host, target_port = _resolve_target(host, port, index)
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
