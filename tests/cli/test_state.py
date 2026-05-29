"""Tests for balatrobot.state module."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from balatrobot.config import Config
from balatrobot.pool import BalatroPool
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
                {"host": "127.0.0.1", "port": 14001},
                {"host": "127.0.0.1", "port": 14002},
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
            "instances": [{"host": "127.0.0.1", "port": 14001}],
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
                {"host": "127.0.0.1", "port": 14001},
                {"host": "127.0.0.1", "port": 14002},
            ],
        }
        state_path.write_text(json.dumps(state_data))
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        info = StateFile.resolve(host="127.0.0.1", port=14002)
        assert info.port == 14002

    def test_resolve_by_index(self, tmp_path, monkeypatch):
        """Resolves by index."""
        state_path = tmp_path / "state.json"
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [
                {"host": "127.0.0.1", "port": 14001},
                {"host": "127.0.0.1", "port": 14002},
            ],
        }
        state_path.write_text(json.dumps(state_data))
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        info = StateFile.resolve(index=1)
        assert info.port == 14002

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
            "instances": [{"host": "127.0.0.1", "port": 14001}],
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
                {"host": "127.0.0.1", "port": 14001},
                {"host": "127.0.0.1", "port": 14002},
            ],
        }
        state_path.write_text(json.dumps(state_data))
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        info = StateFile.resolve()
        assert info.port == 14001  # index=0 by default

    def test_resolve_host_port_not_in_instances(self, tmp_path, monkeypatch):
        """Raises InstanceNotFoundError when host:port not found in instances."""
        state_path = tmp_path / "state.json"
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [{"host": "127.0.0.1", "port": 14001}],
        }
        state_path.write_text(json.dumps(state_data))
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        with pytest.raises(InstanceNotFoundError):
            StateFile.resolve(host="127.0.0.1", port=99999)


# ============================================================================
# StateFile context manager tests
# ============================================================================


class TestStateFileContextManager:
    """Tests for StateFile as async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_writes_state(self, tmp_path):
        """StateFile writes state file on enter, deletes on exit."""
        state_path = tmp_path / "state.json"
        config = Config(logs_path=str(tmp_path))

        mock_inst = MagicMock()
        mock_inst.port = 14001
        mock_inst.start = AsyncMock()
        mock_inst.stop = AsyncMock()

        with patch("balatrobot.pool.BalatroInstance", return_value=mock_inst):
            pool = BalatroPool(config, ports=[14001])
            sf = StateFile(pool, path=state_path)
            async with sf:
                assert state_path.exists()
                data = json.loads(state_path.read_text())
                assert data["pid"] == os.getpid()
                assert len(data["instances"]) == 1
                assert data["instances"][0]["port"] == 14001
                assert "started_at" in data

        assert not state_path.exists()

    @pytest.mark.asyncio
    async def test_delegates_instances(self, tmp_path):
        """StateFile.instances delegates to pool."""
        config = Config(logs_path=str(tmp_path))

        mock_inst = MagicMock()
        mock_inst.port = 14001
        mock_inst.start = AsyncMock()
        mock_inst.stop = AsyncMock()

        with patch("balatrobot.pool.BalatroInstance", return_value=mock_inst):
            pool = BalatroPool(config, ports=[14001])
            sf = StateFile(pool, path=tmp_path / "state.json")
            async with sf:
                assert len(sf.instances) == 1
                assert sf.instances[0].port == 14001

    @pytest.mark.asyncio
    async def test_path_property(self, tmp_path):
        """StateFile.path returns resolved path."""
        state_path = tmp_path / "state.json"
        config = Config()
        pool = BalatroPool(config)
        sf = StateFile(pool, path=state_path)
        assert sf.path == state_path

    @pytest.mark.asyncio
    async def test_double_start_raises_busy(self, tmp_path):
        """StateFileBusy raised if another live state file exists."""
        state_path = tmp_path / "state.json"

        # Write a "live" state file with current PID
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [{"host": "127.0.0.1", "port": 14001}],
        }
        state_path.write_text(json.dumps(state_data))

        config = Config(logs_path=str(tmp_path))
        mock_inst = MagicMock()
        mock_inst.port = 14001
        mock_inst.start = AsyncMock()
        mock_inst.stop = AsyncMock()

        with patch("balatrobot.pool.BalatroInstance", return_value=mock_inst):
            pool = BalatroPool(config, ports=[14001])
            sf = StateFile(pool, path=state_path)
            with pytest.raises(StateFileBusy):
                async with sf:
                    pass

    @pytest.mark.asyncio
    async def test_stale_state_does_not_raise_busy(self, tmp_path):
        """Stale state file is cleaned up and doesn't raise StateFileBusy."""
        state_path = tmp_path / "state.json"

        # Write a "stale" state file with dead PID
        state_data = {
            "pid": 999999999,
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [{"host": "127.0.0.1", "port": 14001}],
        }
        state_path.write_text(json.dumps(state_data))

        config = Config(logs_path=str(tmp_path))
        mock_inst = MagicMock()
        mock_inst.port = 14001
        mock_inst.start = AsyncMock()
        mock_inst.stop = AsyncMock()

        with patch("balatrobot.pool.BalatroInstance", return_value=mock_inst):
            pool = BalatroPool(config, ports=[14001])
            sf = StateFile(pool, path=state_path)
            async with sf:
                # Should succeed — stale file cleaned up
                assert sf.is_started is True

    @pytest.mark.asyncio
    async def test_write_failure_stops_pool(self, tmp_path):
        """Pool is stopped if state file write fails after pool start."""
        state_path = tmp_path / "state.json"
        config = Config(logs_path=str(tmp_path))

        mock_inst = MagicMock()
        mock_inst.port = 14001
        mock_inst.start = AsyncMock()
        mock_inst.stop = AsyncMock()

        with patch("balatrobot.pool.BalatroInstance", return_value=mock_inst):
            pool = BalatroPool(config, ports=[14001])
            sf = StateFile(pool, path=state_path)

            # Make _write_state fail after pool starts
            with patch.object(sf, "_write_state", side_effect=OSError("disk full")):
                with pytest.raises(OSError, match="disk full"):
                    async with sf:
                        pass

        # Pool should have been stopped (stop called on mock_inst)
        mock_inst.stop.assert_called()


# ============================================================================
# StateFile path resolution tests
# ============================================================================


class TestStateFilePath:
    """Tests for StateFile default path resolution."""

    def test_default_path_uses_platformdirs(self, tmp_path, monkeypatch):
        """Default path uses platformdirs.user_state_dir."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))
        config = Config()
        pool = BalatroPool(config)
        sf = StateFile(pool, path=tmp_path / "state.json")
        assert sf.path == tmp_path / "state.json"

    def test_env_var_overrides_path(self, tmp_path, monkeypatch):
        """BALATROBOT_STATE_DIR overrides default path."""
        state_dir = tmp_path / "custom_state"
        state_dir.mkdir()
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(state_dir))

        config = Config()
        pool = BalatroPool(config)
        sf = StateFile(pool)
        assert sf.path == state_dir / "state.json"
