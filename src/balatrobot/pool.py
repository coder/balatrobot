"""BalatroPool — manages N BalatroInstance instances."""

import asyncio
from dataclasses import dataclass
from datetime import datetime

from balatrobot.config import Config
from balatrobot.instance import BalatroInstance


@dataclass(frozen=True)
class InstanceInfo:
    """Immutable metadata for a running Balatro instance."""

    host: str
    port: int
    log_path: str | None = None

    @property
    def url(self) -> str:
        """Full HTTP URL for this instance."""
        return f"http://{self.host}:{self.port}"


class BalatroPool:
    """Manages N BalatroInstance instances with port allocation.

    The pool creates ``n`` instances from a base config, assigning unique
    ports to each.  Use ``start()``/``stop()`` to manage the lifecycle
    and ``check_alive()`` to detect child-death.

    Fail-fast: if any instance fails to start, all already-started
    instances are stopped and the error is re-raised.
    """

    def __init__(
        self,
        config: Config,
        n: int = 1,
        ports: list[int] | None = None,
    ) -> None:
        self._config = config
        self._ports = ports
        if ports is not None:
            self._n = len(ports)
        else:
            self._n = n
        self._instances: list[BalatroInstance] = []
        self._infos: list[InstanceInfo] = []
        self._started = False
        self._session_name: str | None = None

    @property
    def session_name(self) -> str | None:
        """Session directory name (timestamp), available after start()."""
        return self._session_name

    @property
    def n(self) -> int:
        """Number of instances in the pool."""
        return self._n

    @property
    def is_started(self) -> bool:
        """Whether the pool has been started."""
        return self._started

    @property
    def instances(self) -> list[InstanceInfo]:
        """List of InstanceInfo for started instances."""
        return list(self._infos)

    async def start(self) -> None:
        """Allocate ports, spawn instances, health-check, clean up on failure."""
        if self._started:
            raise RuntimeError("Pool already started")

        # Allocate ports (lazy import to avoid circular dependency)
        if self._ports is not None:
            ports = self._ports
        else:
            from balatrobot.state import allocate_ports

            ports = allocate_ports(self._n)

        # Generate shared session directory name (timestamp)
        self._session_name = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

        # Create and start instances
        self._instances = []
        self._infos = []

        try:
            for port in ports:
                inst = BalatroInstance(
                    self._config,
                    session_name=self._session_name,
                    port=port,
                )
                await inst.start()
                self._instances.append(inst)
                log_path = str(inst.log_path) if inst.log_path is not None else None
                self._infos.append(
                    InstanceInfo(host=self._config.host, port=port, log_path=log_path)
                )
        except Exception:
            # Fail-fast: stop all instances that were started
            await self._stop_all()
            raise

        self._started = True

    async def stop(self) -> None:
        """Stop all instances concurrently."""
        if not self._started:
            return
        await self._stop_all()

    async def _stop_all(self) -> None:
        """Internal: stop all instances concurrently."""
        if not self._instances:
            return
        await asyncio.gather(
            *(inst.stop() for inst in self._instances),
            return_exceptions=True,
        )
        self._instances = []
        self._infos = []
        self._started = False

    def check_alive(self) -> None:
        """Check all instances are still running.

        Raises InstanceDiedError from the first dead instance found.
        """
        for inst in self._instances:
            inst.check_alive()
