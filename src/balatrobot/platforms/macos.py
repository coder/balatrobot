"""macOS platform launcher."""

import os
from pathlib import Path

from balatrobot.config import Config
from balatrobot.platforms.base import BaseLauncher


class MacOSLauncher(BaseLauncher):
    """macOS-specific Balatro launcher."""

    def validate_paths(self, config: Config) -> None:
        """Validate paths, apply macOS defaults if None."""
        if config.path_love is None:
            config.path_love = str(
                Path.home()
                / "Library/Application Support/Steam/steamapps/common/Balatro"
                / "Balatro.app/Contents/MacOS/love"
            )
        if config.path_lovely is None:
            config.path_lovely = str(
                Path.home()
                / "Library/Application Support/Steam/steamapps/common/Balatro"
                / "liblovely.dylib"
            )

        love = Path(config.path_love)
        lovely = Path(config.path_lovely)

        if not love.exists():
            raise RuntimeError(f"LOVE executable not found: {love}")
        if not lovely.exists():
            raise RuntimeError(f"liblovely.dylib not found: {lovely}")

    def build_env(self, config: Config) -> dict[str, str]:
        """Build environment with DYLD_INSERT_LIBRARIES."""
        assert config.path_lovely is not None
        env = os.environ.copy()
        env["DYLD_INSERT_LIBRARIES"] = config.path_lovely
        env.update(config.to_env())
        return env

    def build_cmd(self, config: Config) -> list[str]:
        """Build macOS launch command."""
        assert config.path_love is not None
        return [config.path_love]
