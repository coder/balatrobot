"""List command — show running BalatroBot instances."""

import json
from typing import Annotated

import typer

from balatrobot.state import StateFile


def list_cmd(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List running BalatroBot instances."""
    data = StateFile.read()

    if data is None or not data.get("instances"):
        if json_output:
            typer.echo(json.dumps({"instances": []}))
        else:
            typer.echo("No running instances.")
        return

    if json_output:
        typer.echo(json.dumps(data, indent=2))
        return

    instances = data["instances"]
    started_at = data.get("started_at", "unknown")
    typer.echo(f"Started: {started_at}")
    typer.echo(f"Instances ({len(instances)}):")
    for i, inst in enumerate(instances):
        typer.echo(f"  [{i}] http://{inst['host']}:{inst['port']}")
