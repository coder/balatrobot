"""Stop command — stop a running BalatroBot server."""

import os
import signal
import time
from typing import Annotated

import typer

from balatrobot.state import StateFile


def stop() -> None:
    """Stop a running BalatroBot server."""
    data = StateFile.read()

    if data is None:
        typer.echo("No running instances.")
        return

    pid = data.get("pid")
    if pid is None:
        typer.echo("No running instances.")
        return

    # Send SIGTERM
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        # Already dead — treat as success
        typer.echo(f"Server stopped (PID {pid}).")
        return
    except PermissionError:
        typer.echo(
            f"Permission denied: PID {pid} is owned by another user.", err=True
        )
        raise typer.Exit(code=1)
    except OSError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    # Poll for process to die (100ms intervals, up to 5s)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError, OSError):
            # Process is gone
            typer.echo(f"Server stopped (PID {pid}).")
            return
        time.sleep(0.1)

    typer.echo(f"Timed out waiting for PID {pid} to stop.", err=True)
    raise typer.Exit(code=1)
