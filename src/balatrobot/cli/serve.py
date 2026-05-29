"""Serve command — start Balatro with BalatroBot mod loaded."""

import asyncio
import os
import signal
from pathlib import Path
from typing import Annotated

import typer

from balatrobot.config import Config
from balatrobot.instance import InstanceDiedError
from balatrobot.pool import BalatroPool
from balatrobot.state import StateFile, StateFileBusy, _default_state_path

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
        self._state_path = state_path or _default_state_path()
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
        StateFile.delete(self._state_path)
        if self._pool is not None:
            await self._pool.stop()

    async def run(self) -> None:
        """Block until SIGTERM or child death.

        Raises InstanceDiedError on child death.
        """
        assert self._pool is not None  # set by __aenter__
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGTERM, self._shutdown.set)

        while not self._shutdown.is_set():
            self._pool.check_alive()
            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass


def serve(
    # fmt: off
    num_instances: Annotated[
        int,
        typer.Option(
            "-n", "--num-instances", help="Number of instances to start (default: 1)"
        ),
    ] = 1,
    fps_cap: Annotated[
        int | None, typer.Option(help="Maximum FPS cap (default: 60)")
    ] = None,
    gamespeed: Annotated[
        int | None, typer.Option(help="Game speed multiplier (default: 4)")
    ] = None,
    animation_fps: Annotated[
        int | None, typer.Option(help="Animation FPS (default: 10)")
    ] = None,
    logs_path: Annotated[
        str | None, typer.Option(help="Directory for log files (default: logs)")
    ] = None,
    fast: Annotated[
        bool | None, typer.Option(help="Enable fast mode (10x speed)")
    ] = None,
    headless: Annotated[bool | None, typer.Option(help="Enable headless mode")] = None,
    render_on_api: Annotated[
        bool | None, typer.Option(help="Render only on API calls")
    ] = None,
    audio: Annotated[bool | None, typer.Option(help="Enable audio")] = None,
    debug: Annotated[bool | None, typer.Option(help="Enable debug mode")] = None,
    no_shaders: Annotated[bool | None, typer.Option(help="Disable shaders")] = None,
    no_reduced_motion: Annotated[
        bool | None, typer.Option(help="Disable reduced motion")
    ] = None,
    pixel_art_smoothing: Annotated[
        bool | None, typer.Option(help="Enable pixel art smoothing")
    ] = None,
    balatro_path: Annotated[
        str | None, typer.Option(help="Path to Balatro executable")
    ] = None,
    lovely_path: Annotated[
        str | None, typer.Option(help="Path to lovely library")
    ] = None,
    love_path: Annotated[
        str | None, typer.Option(help="Path to game launcher executable")
    ] = None,
    platform: Annotated[
        str | None, typer.Option(help="Platform (darwin, linux, windows, native)")
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

    # Validate num_instances
    if num_instances < 1:
        typer.echo(
            f"Error: --num-instances must be >= 1, got {num_instances}.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Build config from kwargs with env var fallback
    config = Config.from_kwargs(
        fps_cap=fps_cap,
        gamespeed=gamespeed,
        animation_fps=animation_fps,
        logs_path=logs_path,
        fast=fast,
        headless=headless,
        render_on_api=render_on_api,
        audio=audio,
        debug=debug,
        no_shaders=no_shaders,
        no_reduced_motion=no_reduced_motion,
        pixel_art_smoothing=pixel_art_smoothing,
        balatro_path=balatro_path,
        lovely_path=lovely_path,
        love_path=love_path,
        platform=platform,
    )

    try:
        asyncio.run(_serve(config, num_instances))
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
            f"Session: {pool.session_name} | Logs: {config.logs_path}/{pool.session_name}/"
        )
        typer.echo("Press Ctrl+C to stop.")
        await server.run()
