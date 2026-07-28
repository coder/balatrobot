"""Windows platform launcher."""

import os
from pathlib import Path

from balatrobot.config import Config
from balatrobot.platforms.base import BaseLauncher


class WindowsLauncher(BaseLauncher):
    """Windows-specific Balatro launcher via Steam."""

    def validate_paths(self, config: Config) -> None:
        """Validate paths, apply Windows defaults if None."""
        if config.path_love is None:
            config.path_love = (
                r"C:\Program Files (x86)\Steam\steamapps\common\Balatro\Balatro.exe"
            )
        if config.path_lovely is None:
            config.path_lovely = (
                r"C:\Program Files (x86)\Steam\steamapps\common\Balatro\version.dll"
            )

        love = Path(config.path_love)
        lovely = Path(config.path_lovely)

        if not love.exists():
            raise RuntimeError(f"Balatro executable not found: {love}")
        if not lovely.exists():
            raise RuntimeError(f"version.dll not found: {lovely}")

    def build_env(self, config: Config) -> dict[str, str]:
        """Build environment."""
        env = os.environ.copy()
        env.update(config.to_env())
        return env

    def build_cmd(self, config: Config) -> list[str]:
        """Build Windows launch command."""
        assert config.path_love is not None
        return [config.path_love]
