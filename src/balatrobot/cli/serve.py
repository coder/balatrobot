"""Serve command - Start Balatro with BalatroBot mod loaded."""

import asyncio
from typing import Annotated

import typer

from balatrobot.config import Config
from balatrobot.manager import BalatroInstance

# Platform choices for validation
PLATFORM_CHOICES = ["darwin", "proton", "windows", "native"]


def serve(
    # fmt: off
    attach: Annotated[
        bool,
        typer.Option(
            help="Attach to a game already launched externally (e.g. snap/Flatpak Steam). "
            "Skips launching the game and waits up to 5 minutes for it to come up."
        ),
    ] = False,
    host: Annotated[
        str | None, typer.Option(help="Server hostname (default: 127.0.0.1)")
    ] = None,
    port: Annotated[
        int | None, typer.Option(help="Server port (default: 12346)")
    ] = None,
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
        str | None, typer.Option(help="Platform (darwin, proton, windows, native)")
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

    # Build config from kwargs with env var fallback
    config = Config.from_kwargs(
        host=host,
        port=port,
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
        asyncio.run(_serve(config, attach=attach))
    except KeyboardInterrupt:
        typer.echo("\nShutting down server...")


async def _serve(config: Config, attach: bool = False) -> None:
    """Async serve implementation."""
    if attach:
        instance = BalatroInstance(config)
        await instance.attach()
        typer.echo(f"Balatro running on port {instance.port}. Press Ctrl+C to stop.")
        try:
            while True:
                await asyncio.sleep(5)
        finally:
            pass
    else:
        async with BalatroInstance(config) as instance:
            typer.echo(
                f"Balatro running on port {instance.port}. Press Ctrl+C to stop."
            )
            while True:
                await asyncio.sleep(5)
