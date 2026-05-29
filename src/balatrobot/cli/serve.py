"""Serve command — start Balatro with BalatroBot mod loaded."""

import asyncio
from typing import Annotated

import typer

from balatrobot.config import Config
from balatrobot.pool import BalatroPool
from balatrobot.state import StateFile

# Platform choices for validation
PLATFORM_CHOICES = ["darwin", "linux", "windows", "native"]


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


async def _serve(config: Config, n: int) -> None:
    """Async serve implementation using StateFile + BalatroPool."""
    pool = BalatroPool(config, n=n)
    async with StateFile(pool) as sf:
        instances = sf.instances
        for i, info in enumerate(instances):
            typer.echo(f"Instance [{i}]: {info.url}")
        session_name = pool.session_name
        logs_dir = f"{config.logs_path}/{session_name}/"
        typer.echo(f"Session: {session_name} | Logs: {logs_dir}")
        typer.echo("Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(5)
