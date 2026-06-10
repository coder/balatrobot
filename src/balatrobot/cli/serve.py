"""Serve command — start Balatro with BalatroBot mod loaded."""

import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Annotated

import typer

from balatrobot.config import RENDER_CHOICES, Config
from balatrobot.instance import InstanceDiedError
from balatrobot.pool import BalatroPool
from balatrobot.state import StateFile, StateFileBusy, default_state_path

# Platform choices for validation
PLATFORM_CHOICES = ["darwin", "linux", "windows", "native"]


class Server:
    """Owns the full serve lifecycle: pool start/stop, state file write/delete,
    and a supervision loop that watches for SIGTERM or child-death.

    Usage::

        async with Server(config, n=2) as server:
            await server.run()
    """

    def __init__(
        self,
        config: Config,
        n: int,
        state_path: Path | None = None,
    ) -> None:
        self._config = config
        self._n = n
        self._state_path = state_path or default_state_path()
        self._pool: BalatroPool | None = None
        self._shutdown = asyncio.Event()

    @property
    def pool(self) -> BalatroPool | None:
        return self._pool

    async def __aenter__(self) -> "Server":
        # 1. Check for existing live state file
        existing = StateFile.read(self._state_path)
        if existing is not None:
            raise StateFileBusy(path=self._state_path, pid=existing["pid"])

        # 2. Start pool
        self._pool = BalatroPool(self._config, n=self._n)
        try:
            await self._pool.start()
            # 3. Write state file
            StateFile.write(self._state_path, os.getpid(), self._pool.instances)
        except BaseException:
            await self._pool.stop()
            raise

        return self

    async def __aexit__(self, *args: object) -> None:
        if self._pool is not None:
            await self._pool.stop()
        StateFile.delete(self._state_path)

    async def run(self) -> None:
        """Block until SIGTERM or child death.

        Raises InstanceDiedError on child death.
        """
        assert self._pool is not None  # set by __aenter__
        loop = asyncio.get_running_loop()

        if sys.platform != "win32":
            loop.add_signal_handler(signal.SIGTERM, self._shutdown.set)

        try:
            while not self._shutdown.is_set():
                self._pool.check_alive()
                try:
                    await asyncio.wait_for(self._shutdown.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass
        finally:
            if sys.platform != "win32":
                loop.remove_signal_handler(signal.SIGTERM)


def serve(
    # fmt: off
    num: Annotated[
        int, typer.Option("--num", help="Number of instances to start (default: 1)")
    ] = 1,
    settings: Annotated[
        str | None,
        typer.Option("--settings", help="Path to balatrosettings profile directory"),
    ] = None,
    render: Annotated[
        str | None,
        typer.Option("--render", help="Render mode: headfull|headless|ondemand"),
    ] = None,
    debug: Annotated[
        bool | None, typer.Option("--debug", help="Enable debug endpoints")
    ] = None,
    host: Annotated[str | None, typer.Option("--host", help="Server hostname")] = None,
    port: Annotated[int | None, typer.Option("--port", help="Server port")] = None,
    path_balatro: Annotated[
        str | None, typer.Option("--path-balatro", help="Path to Balatro directory")
    ] = None,
    path_lovely: Annotated[
        str | None, typer.Option("--path-lovely", help="Path to lovely library")
    ] = None,
    path_love: Annotated[
        str | None, typer.Option("--path-love", help="Path to LOVE executable")
    ] = None,
    platform: Annotated[
        str | None,
        typer.Option("--platform", help="Platform (darwin, linux, windows, native)"),
    ] = None,
    path_logs: Annotated[
        str | None, typer.Option("--path-logs", help="Log directory")
    ] = None,
    # fmt: on
) -> None:
    """Start Balatro with BalatroBot mod loaded."""
    # Validate platform choice
    if platform is not None and platform not in PLATFORM_CHOICES:
        typer.echo(
            f"Error: Invalid platform '{platform}'. "
            f"Choose from: {', '.join(PLATFORM_CHOICES)}",
            err=True,
        )
        raise typer.Exit(code=1)

    if render is not None and render not in RENDER_CHOICES:
        typer.echo(
            f"Error: Invalid render mode '{render}'. "
            f"Choose from: {', '.join(sorted(RENDER_CHOICES))}",
            err=True,
        )
        raise typer.Exit(code=1)

    if num < 1:
        typer.echo(f"Error: --num must be >= 1, got {num}.", err=True)
        raise typer.Exit(code=1)

    # Build config from kwargs with env var fallback
    config = Config.from_kwargs(
        settings=settings,
        render=render,
        debug=debug,
        host=host,
        port=port,
        path_balatro=path_balatro,
        path_lovely=path_lovely,
        path_love=path_love,
        platform=platform,
        path_logs=path_logs,
    )

    try:
        asyncio.run(_serve(config, num))
    except KeyboardInterrupt:
        typer.echo("\nShutting down server...")
    except InstanceDiedError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)
    except StateFileBusy as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)


async def _serve(config: Config, n: int) -> None:
    async with Server(config, n) as server:
        pool = server.pool
        assert pool is not None
        for i, info in enumerate(pool.instances):
            typer.echo(f"Instance [{i}]: {info.url}")
        typer.echo(
            f"Session: {pool.session_name} | Logs: {config.path_logs}/{pool.session_name}/"
        )
        typer.echo("Press Ctrl+C to stop.")
        await server.run()
