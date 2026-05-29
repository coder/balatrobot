"""Tests for balatrobot.state module."""

import json
import os
from pathlib import Path

import pytest

from balatrobot.state import (
    InstanceNotFoundError,
    StateFile,
    StateFileBusy,
    StateFileError,
    StateFileNotFound,
    allocate_ports,
)

# ============================================================================
# allocate_ports tests
# ============================================================================


class TestAllocatePorts:
    """Tests for allocate_ports helper."""

    def test_allocate_one_port(self):
        """Allocates one port."""
        ports = allocate_ports(1)
        assert len(ports) == 1
        assert isinstance(ports[0], int)

    def test_allocate_multiple_ports(self):
        """Allocates multiple distinct ports."""
        ports = allocate_ports(3)
        assert len(ports) == 3
        assert len(set(ports)) == 3  # All unique

    def test_allocate_zero_ports(self):
        """Allocates zero ports."""
        ports = allocate_ports(0)
        assert ports == []

    def test_ports_in_valid_range(self):
        """Allocated ports are in valid ephemeral range."""
        ports = allocate_ports(5)
        for port in ports:
            assert 1024 <= port <= 65535


# ============================================================================
# Exception hierarchy tests
# ============================================================================


class TestExceptions:
    """Tests for state exception hierarchy."""

    def test_state_file_error_base(self):
        """StateFileError is the base exception."""
        err = StateFileError("test")
        assert isinstance(err, Exception)
        assert str(err) == "test"

    def test_state_file_busy(self):
        """StateFileBusy is a StateFileError."""
        err = StateFileBusy(path="/tmp/state.json", pid=1234)
        assert isinstance(err, StateFileError)
        assert err.path == "/tmp/state.json"
        assert err.pid == 1234

    def test_state_file_not_found(self):
        """StateFileNotFound is a StateFileError."""
        err = StateFileNotFound(path="/tmp/state.json")
        assert isinstance(err, StateFileError)
        assert err.path == "/tmp/state.json"

    def test_instance_not_found_error(self):
        """InstanceNotFoundError is a StateFileError."""
        err = InstanceNotFoundError(index=5, total=3)
        assert isinstance(err, StateFileError)
        assert err.index == 5
        assert err.total == 3


# ============================================================================
# StateFile.read tests
# ============================================================================


class TestStateFileRead:
    """Tests for StateFile.read static method."""

    def test_read_valid_state(self, tmp_path):
        """Reads a valid state file."""
        state_path = tmp_path / "state.json"
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [
                {
                    "host": "127.0.0.1",
                    "port": 14001,
                    "log_path": "/tmp/logs/s/14001.log",
                },
                {
                    "host": "127.0.0.1",
                    "port": 14002,
                    "log_path": "/tmp/logs/s/14002.log",
                },
            ],
        }
        state_path.write_text(json.dumps(state_data))

        result = StateFile.read(state_path)
        assert result is not None
        assert result["pid"] == os.getpid()
        assert len(result["instances"]) == 2

    def test_read_missing_file(self, tmp_path):
        """Returns None for missing file."""
        result = StateFile.read(tmp_path / "nonexistent.json")
        assert result is None

    def test_read_stale_state_auto_deletes(self, tmp_path):
        """Auto-deletes state file if PID is no longer alive."""
        state_path = tmp_path / "state.json"
        state_data = {
            "pid": 999999999,  # Non-existent PID
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [
                {
                    "host": "127.0.0.1",
                    "port": 14001,
                    "log_path": "/tmp/logs/s/14001.log",
                }
            ],
        }
        state_path.write_text(json.dumps(state_data))

        result = StateFile.read(state_path)
        assert result is None
        assert not state_path.exists()

    def test_read_invalid_json(self, tmp_path):
        """Returns None for invalid JSON."""
        state_path = tmp_path / "state.json"
        state_path.write_text("not json")

        result = StateFile.read(state_path)
        assert result is None

    def test_read_default_path(self, tmp_path, monkeypatch):
        """Reads from default path when no path given."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))
        result = StateFile.read()
        assert result is None  # No file exists yet


# ============================================================================
# StateFile.resolve tests
# ============================================================================


class TestStateFileResolve:
    """Tests for StateFile.resolve static method."""

    def test_resolve_by_host_port(self, tmp_path, monkeypatch):
        """Resolves by explicit host and port."""
        state_path = tmp_path / "state.json"
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [
                {
                    "host": "127.0.0.1",
                    "port": 14001,
                    "log_path": "/tmp/logs/s/14001.log",
                },
                {
                    "host": "127.0.0.1",
                    "port": 14002,
                    "log_path": "/tmp/logs/s/14002.log",
                },
            ],
        }
        state_path.write_text(json.dumps(state_data))
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        info = StateFile.resolve(host="127.0.0.1", port=14002)
        assert info.port == 14002
        assert info.log_path == Path("/tmp/logs/s/14002.log")

    def test_resolve_by_index(self, tmp_path, monkeypatch):
        """Resolves by index."""
        state_path = tmp_path / "state.json"
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [
                {
                    "host": "127.0.0.1",
                    "port": 14001,
                    "log_path": "/tmp/logs/s/14001.log",
                },
                {
                    "host": "127.0.0.1",
                    "port": 14002,
                    "log_path": "/tmp/logs/s/14002.log",
                },
            ],
        }
        state_path.write_text(json.dumps(state_data))
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        info = StateFile.resolve(index=1)
        assert info.port == 14002
        assert info.log_path == Path("/tmp/logs/s/14002.log")

    def test_resolve_no_state_file(self, tmp_path, monkeypatch):
        """Raises StateFileNotFound when no state file."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))
        with pytest.raises(StateFileNotFound):
            StateFile.resolve()

    def test_resolve_empty_instances(self, tmp_path, monkeypatch):
        """Raises StateFileNotFound when instances list is empty."""
        state_path = tmp_path / "state.json"
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [],
        }
        state_path.write_text(json.dumps(state_data))
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        with pytest.raises(StateFileNotFound):
            StateFile.resolve()

    def test_resolve_index_out_of_range(self, tmp_path, monkeypatch):
        """Raises InstanceNotFoundError for invalid index."""
        state_path = tmp_path / "state.json"
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [
                {
                    "host": "127.0.0.1",
                    "port": 14001,
                    "log_path": "/tmp/logs/s/14001.log",
                }
            ],
        }
        state_path.write_text(json.dumps(state_data))
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        with pytest.raises(InstanceNotFoundError) as exc_info:
            StateFile.resolve(index=5)
        assert exc_info.value.index == 5
        assert exc_info.value.total == 1

    def test_resolve_default_index_zero(self, tmp_path, monkeypatch):
        """Default index is 0."""
        state_path = tmp_path / "state.json"
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [
                {
                    "host": "127.0.0.1",
                    "port": 14001,
                    "log_path": "/tmp/logs/s/14001.log",
                },
                {
                    "host": "127.0.0.1",
                    "port": 14002,
                    "log_path": "/tmp/logs/s/14002.log",
                },
            ],
        }
        state_path.write_text(json.dumps(state_data))
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        info = StateFile.resolve()
        assert info.port == 14001  # index=0 by default
        assert info.log_path == Path("/tmp/logs/s/14001.log")

    def test_resolve_host_port_not_in_instances(self, tmp_path, monkeypatch):
        """Raises InstanceNotFoundError when host:port not found in instances."""
        state_path = tmp_path / "state.json"
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [
                {
                    "host": "127.0.0.1",
                    "port": 14001,
                    "log_path": "/tmp/logs/s/14001.log",
                }
            ],
        }
        state_path.write_text(json.dumps(state_data))
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        with pytest.raises(InstanceNotFoundError):
            StateFile.resolve(host="127.0.0.1", port=99999)


# ============================================================================
# StateFile.write / delete tests
# ============================================================================


class TestStateFileWriteDelete:
    """Tests for StateFile.write and StateFile.delete static methods."""

    def test_write_creates_state_file(self, tmp_path):
        """write() creates a valid state file."""
        from balatrobot.instance import InstanceInfo

        state_path = tmp_path / "state.json"
        instances = [
            InstanceInfo(host="127.0.0.1", port=14001, log_path=Path("/tmp/a.log")),
            InstanceInfo(host="127.0.0.1", port=14002, log_path=None),
        ]
        StateFile.write(state_path, pid=12345, instances=instances)

        assert state_path.exists()
        data = json.loads(state_path.read_text())
        assert data["pid"] == 12345
        assert "started_at" in data
        assert len(data["instances"]) == 2
        assert data["instances"][0]["host"] == "127.0.0.1"
        assert data["instances"][0]["port"] == 14001
        assert data["instances"][0]["log_path"] == "/tmp/a.log"
        assert data["instances"][1]["log_path"] is None

    def test_write_atomic(self, tmp_path):
        """write() succeeds (smoke test for atomicity)."""
        from balatrobot.instance import InstanceInfo

        state_path = tmp_path / "state.json"
        instances = [InstanceInfo(host="127.0.0.1", port=14001)]
        StateFile.write(state_path, pid=os.getpid(), instances=instances)
        assert state_path.exists()

    def test_write_creates_parent_dir(self, tmp_path):
        """write() creates parent directories if they don't exist."""
        from balatrobot.instance import InstanceInfo

        state_path = tmp_path / "nested" / "dir" / "state.json"
        instances = [InstanceInfo(host="127.0.0.1", port=14001)]
        StateFile.write(state_path, pid=os.getpid(), instances=instances)
        assert state_path.exists()

    def test_delete_removes_file(self, tmp_path):
        """delete() removes an existing state file."""
        from balatrobot.instance import InstanceInfo

        state_path = tmp_path / "state.json"
        instances = [InstanceInfo(host="127.0.0.1", port=14001)]
        StateFile.write(state_path, pid=os.getpid(), instances=instances)
        assert state_path.exists()

        StateFile.delete(state_path)
        assert not state_path.exists()

    def test_delete_silent_on_missing(self, tmp_path):
        """delete() doesn't raise for non-existent path."""
        state_path = tmp_path / "nonexistent.json"
        StateFile.delete(state_path)  # Should not raise
        assert not state_path.exists()


# ============================================================================
# StateFile path resolution tests
# ============================================================================


class TestStateFilePath:
    """Tests for StateFile default path resolution."""

    def test_default_path_uses_env_var(self, tmp_path, monkeypatch):
        """BALATROBOT_STATE_DIR overrides default path."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))
        from balatrobot.state import default_state_path

        assert default_state_path() == tmp_path / "state.json"
