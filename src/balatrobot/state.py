"""StateFile — static utilities for BalatroPool state-file discovery.

Provides read / write / delete / resolve helpers for the JSON state file
that enables discovery of running BalatroPool instances by CLI tools and
test fixtures.
"""

import json
import os
import socket
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platformdirs import user_state_dir

from balatrobot.pool import InstanceInfo

# ---------------------------------------------------------------------------
# Port allocation
# ---------------------------------------------------------------------------


def _allocate_port() -> int:
    """Allocate a single free port via bind(0)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def allocate_ports(n: int) -> list[int]:
    """Allocate n free ports.

    Uses bind(0) to find available ports. There is a small TOCTOU window
    between allocation and actual use, but this is acceptable for the
    pool use case.
    """
    return [_allocate_port() for _ in range(n)]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class StateFileError(Exception):
    """Base exception for state file operations."""


class StateFileBusy(StateFileError):
    """A live state file already exists (another pool is running)."""

    def __init__(self, path: str | Path, pid: int) -> None:
        self.path = str(path)
        self.pid = pid
        super().__init__(f"State file {path!s} is locked by PID {pid}")


class StateFileNotFound(StateFileError):
    """No state file found."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = str(path) if path is not None else None
        super().__init__(
            f"No state file found at {path!s}" if path else "No state file found"
        )


class InstanceNotFoundError(StateFileError):
    """Requested instance index or host:port not in state file."""

    def __init__(self, index: int | None = None, total: int | None = None) -> None:
        self.index = index
        self.total = total
        msg_parts = []
        if index is not None:
            msg_parts.append(f"index={index}")
        if total is not None:
            msg_parts.append(f"total={total}")
        super().__init__(f"Instance not found ({', '.join(msg_parts)})")


# ---------------------------------------------------------------------------
# StateFile
# ---------------------------------------------------------------------------

_DEFAULT_FILENAME = "state.json"
_ENV_STATE_DIR = "BALATROBOT_STATE_DIR"


def _default_state_path() -> Path:
    """Resolve the default state file path.

    Uses ``BALATROBOT_STATE_DIR`` env var if set, otherwise falls back
    to ``platformdirs.user_state_dir("balatrobot")``.
    """
    env_dir = os.environ.get(_ENV_STATE_DIR)
    if env_dir:
        base = Path(env_dir)
    else:
        base = Path(user_state_dir("balatrobot"))
    return base / _DEFAULT_FILENAME


def _is_pid_alive(pid: int) -> bool:
    """Check whether *pid* is a running process."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


class StateFile:
    """Static utilities for reading, writing, and resolving state files.

    All methods are static.  The state file is a JSON document that enables
    discovery of running BalatroPool instances by CLI tools and test fixtures.
    """

    # -- Static helpers -----------------------------------------------------

    @staticmethod
    def read(path: Path | None = None) -> dict[str, Any] | None:
        """Read and validate a state file.

        Returns ``None`` if the file doesn't exist, contains invalid JSON,
        or references a dead PID (in which case the orphan file is deleted).

        Args:
            path: Path to read. Defaults to the platform-default path.
        """
        state_path = path or _default_state_path()

        if not state_path.exists():
            return None

        try:
            data = json.loads(state_path.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        pid = data.get("pid")
        if pid is not None and not _is_pid_alive(pid):
            # Orphan — auto-delete
            try:
                state_path.unlink()
            except OSError:
                pass
            return None

        return data

    @staticmethod
    def resolve(
        host: str | None = None,
        port: int | None = None,
        index: int | None = None,
        path: Path | None = None,
    ) -> InstanceInfo:
        """Discover an instance from the state file.

        Resolution order:
        1. If both *host* and *port* are given, find matching instance.
        2. If *index* is given (or defaults to 0), return that instance.
        3. Raises on missing state file, empty instances, or not found.

        Args:
            host: Filter by host.
            port: Filter by port.
            index: Instance index (0-based). Defaults to 0.
            path: State file path override.

        Raises:
            StateFileNotFound: No state file or empty instances.
            InstanceNotFoundError: No matching instance.
        """
        data = StateFile.read(path)
        if data is None:
            raise StateFileNotFound(path or _default_state_path())

        instances = data.get("instances", [])
        if not instances:
            raise StateFileNotFound(path or _default_state_path())

        # Explicit host+port lookup
        if host is not None and port is not None:
            for inst in instances:
                if inst["host"] == host and inst["port"] == port:
                    return InstanceInfo(
                        host=inst["host"],
                        port=inst["port"],
                        log_path=inst["log_path"],
                    )
            raise InstanceNotFoundError(index=None, total=len(instances))

        # Index-based lookup (default to 0)
        idx = index if index is not None else 0
        if idx < 0 or idx >= len(instances):
            raise InstanceNotFoundError(index=idx, total=len(instances))

        inst = instances[idx]
        return InstanceInfo(
            host=inst["host"], port=inst["port"], log_path=inst["log_path"]
        )

    # -- Write / Delete ----------------------------------------------------

    @staticmethod
    def write(
        path: Path,
        pid: int,
        instances: list[InstanceInfo],
    ) -> None:
        """Write a state file atomically.

        Creates parent directories if needed. Uses temp file + ``os.replace``
        for atomicity.

        Args:
            path: Destination file path.
            pid: Process ID of the server.
            instances: List of InstanceInfo to record.
        """
        data = {
            "pid": pid,
            "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "instances": [
                {"host": info.host, "port": info.port, "log_path": info.log_path}
                for info in instances
            ],
        }
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=".state-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f)
            os.replace(tmp_path, str(path))
        except BaseException:
            # Clean up temp file on error
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def delete(path: Path) -> None:
        """Delete a state file. Silent if the file doesn't exist."""
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
