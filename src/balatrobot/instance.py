"""Context manager for a Balatro instance."""

import asyncio
import subprocess
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import httpx

from balatrobot.config import Config
from balatrobot.platforms import get_launcher
from balatrobot.platforms.base import BaseLauncher


@dataclass(frozen=True)
class InstanceInfo:
    """Immutable metadata for a running Balatro instance."""

    host: str
    port: int
    log_path: Path | None = None

    @property
    def url(self) -> str:
        """Full HTTP URL for this instance."""
        return f"http://{self.host}:{self.port}"


HEALTH_TIMEOUT = 30.0


class InstanceDiedError(Exception):
    """Raised when a Balatro subprocess has exited unexpectedly."""

    def __init__(self, port: int, log_path: str | None = None) -> None:
        self.port = port
        self.log_path = log_path
        msg = f"Instance on port {port} died unexpectedly."
        if log_path is not None:
            msg += f"\nLog: {log_path}"
        super().__init__(msg)


class BalatroInstance:
    """Context manager for a single Balatro instance."""

    def __init__(
        self, config: Config | None = None, session_name: str | None = None, **overrides
    ) -> None:
        """Initialize a Balatro instance.

        Args:
            config: Base configuration. If None, uses Config from environment.
            session_name: Session directory name (timestamp). If None, generated at start().
            **overrides: Override specific config fields (e.g., port=12347).
        """
        base = config or Config.from_env()
        self._config = replace(base, **overrides) if overrides else base
        self._process: subprocess.Popen | None = None
        self._log_path: Path | None = None
        self._session_name = session_name
        self._launcher: BaseLauncher | None = None

    @property
    def port(self) -> int:
        """Get the port this instance is running on."""
        return self._config.port

    @property
    def process(self) -> subprocess.Popen:
        """Get the subprocess. Raises if not started."""
        if self._process is None:
            raise RuntimeError("Instance not started")
        return self._process

    @property
    def log_path(self) -> Path | None:
        """Get the log file path, if available."""
        return self._log_path

    async def _wait_for_health(self, timeout: float = HEALTH_TIMEOUT) -> None:
        """Wait for health endpoint to respond."""
        url = f"http://{self._config.host}:{self._config.port}"
        payload = {"jsonrpc": "2.0", "method": "health", "params": {}, "id": 1}
        start = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start < timeout:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.post(url, json=payload)
                    data = response.json()
                    if "result" in data and data["result"].get("status") == "ok":
                        return
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            await asyncio.sleep(0.5)

        raise RuntimeError(
            f"Health check failed after {timeout}s on "
            f"{self._config.host}:{self._config.port}"
        )

    async def start(self) -> None:
        """Start the Balatro instance and wait for health."""
        if self._process is not None:
            raise RuntimeError("Instance already started")

        # Create session directory (use provided session_name or generate one)
        session_name = self._session_name or datetime.now().strftime(
            "%Y-%m-%dT%H-%M-%S"
        )
        session_dir = Path(self._config.logs_path) / session_name
        session_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = session_dir / f"{self._config.port}.log"

        # Get launcher and start process
        self._launcher = get_launcher(self._config.platform)
        print(f"Starting Balatro on port {self._config.port}...")

        self._process = await self._launcher.start(self._config, session_dir)

        # Wait for health
        print(f"Waiting for health check on {self._config.host}:{self._config.port}...")
        try:
            await self._wait_for_health()
        except RuntimeError as e:
            await self.stop()
            raise RuntimeError(f"{e}. Check log file: {self._log_path}") from e

        print(f"Balatro started (PID: {self._process.pid})")

    async def stop(self) -> None:
        """Stop the Balatro instance."""
        if self._process is None:
            return

        process = self._process
        self._process = None

        print(f"Stopping instance on port {self._config.port}...")

        # Platform-specific cleanup (e.g. wineserver -k on Linux/Proton)
        if self._launcher is not None:
            self._launcher.cleanup(self._config)

        # Try graceful termination first
        process.terminate()

        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, process.wait),
                timeout=5,
            )
        except asyncio.TimeoutError:
            print(f"Force killing instance on port {self._config.port}...")
            process.kill()
            await loop.run_in_executor(None, process.wait)

    def check_alive(self) -> None:
        """Check if the subprocess is still running.

        Raises InstanceDiedError if the process has exited.
        Silently returns if the instance hasn't been started or is already stopped.
        """
        if self._process is None:
            return
        if self._process.poll() is not None:
            raise InstanceDiedError(
                port=self._config.port,
                log_path=str(self._log_path) if self._log_path is not None else None,
            )

    async def __aenter__(self) -> "BalatroInstance":
        """Start instance on context entry."""
        await self.start()
        return self

    async def __aexit__(self, *args) -> None:
        """Stop instance on context exit."""
        await self.stop()
