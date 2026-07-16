"""Base launcher class for all platforms."""

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from balatrobot.config import Config


class BaseLauncher(ABC):
    """Abstract base class for platform-specific launchers."""

    @abstractmethod
    def validate_paths(self, config: Config) -> None:
        """Validate paths exist, apply platform defaults if None.

        Mutates config in-place with platform-specific defaults.

        Raises:
            RuntimeError: If required paths are missing or invalid.
        """
        ...

    @abstractmethod
    def build_env(self, config: Config) -> dict[str, str]:
        """Build environment dict for subprocess.

        Returns:
            Environment dict including os.environ and platform-specific vars.
        """
        ...

    @abstractmethod
    def build_cmd(self, config: Config) -> list[str]:
        """Build command list for subprocess.

        Returns:
            Command list suitable for subprocess.Popen.
        """
        ...

    async def start(self, config: Config, instance_dir: Path) -> subprocess.Popen:
        """Start Balatro with the given configuration.

        Args:
            config: Launcher configuration (mutated with defaults).
            instance_dir: Per-instance directory for log files. Exposed to the
                Lua mod as BALATROBOT_LOG_DIR.

        Returns:
            The subprocess.Popen object.

        Raises:
            RuntimeError: If startup fails.
        """
        self.validate_paths(config)
        env = self.build_env(config)
        env["BALATROBOT_LOG_DIR"] = str(instance_dir.resolve())
        # Expose instance dir so docker can bind-mount it.
        self.instance_dir = instance_dir.resolve()
        cmd = self.build_cmd(config)

        log_path = instance_dir / "balatro.log"

        with open(log_path, "w") as log:
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )

        return process

    def cleanup(self, config: Config) -> None:
        """Platform-specific cleanup before terminating the process.

        Called by the manager before process.terminate().
        Override in platform launchers that need special shutdown
        (e.g. wineserver -k for Proton on Linux).
        """
        pass
