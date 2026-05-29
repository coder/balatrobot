"""Tests for balatrobot.cli.serve.Server class."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from balatrobot.cli.serve import Server
from balatrobot.config import Config
from balatrobot.instance import InstanceDiedError
from balatrobot.pool import BalatroPool
from balatrobot.state import StateFileBusy


class TestServerContextManager:
    """Tests for Server async context manager lifecycle."""

    @pytest.mark.asyncio
    async def test_enter_writes_state_exit_deletes(self, tmp_path):
        """State file exists inside with block, gone after exit."""
        state_path = tmp_path / "state.json"
        config = Config(logs_path=str(tmp_path))

        mock_inst = MagicMock()
        mock_inst.port = 14001
        mock_inst.log_path = "/tmp/test-logs/14001.log"
        mock_inst.start = AsyncMock()
        mock_inst.stop = AsyncMock()
        mock_inst.check_alive = MagicMock()

        with patch("balatrobot.pool.BalatroInstance", return_value=mock_inst), \
             patch("balatrobot.state.allocate_ports", return_value=[14001]):
            async with Server(config, n=1, state_path=state_path) as _server:
                assert state_path.exists()
                data = json.loads(state_path.read_text())
                assert data["pid"] == os.getpid()
                assert len(data["instances"]) == 1
                assert data["instances"][0]["port"] == 14001

        assert not state_path.exists()

    @pytest.mark.asyncio
    async def test_enter_double_start_raises_busy(self, tmp_path):
        """StateFileBusy raised if another live state file exists."""
        state_path = tmp_path / "state.json"

        # Write a "live" state file with current PID
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

        config = Config(logs_path=str(tmp_path))
        server = Server(config, n=1, state_path=state_path)

        with pytest.raises(StateFileBusy):
            await server.__aenter__()

    @pytest.mark.asyncio
    async def test_enter_pool_failure_cleans_up(self, tmp_path):
        """No state file left if pool.start() fails."""
        state_path = tmp_path / "state.json"
        config = Config(logs_path=str(tmp_path))

        mock_inst = MagicMock()
        mock_inst.port = 14001
        mock_inst.log_path = "/tmp/test-logs/14001.log"
        mock_inst.start = AsyncMock(side_effect=RuntimeError("start failed"))
        mock_inst.stop = AsyncMock()

        with patch("balatrobot.pool.BalatroInstance", return_value=mock_inst), \
             patch("balatrobot.state.allocate_ports", return_value=[14001]):
            server = Server(config, n=1, state_path=state_path)
            with pytest.raises(RuntimeError, match="start failed"):
                await server.__aenter__()

        # State file should not exist
        assert not state_path.exists()

    @pytest.mark.asyncio
    async def test_pool_property(self, tmp_path):
        """Server.pool returns the pool after enter."""
        state_path = tmp_path / "state.json"
        config = Config(logs_path=str(tmp_path))

        mock_inst = MagicMock()
        mock_inst.port = 14001
        mock_inst.log_path = "/tmp/test-logs/14001.log"
        mock_inst.start = AsyncMock()
        mock_inst.stop = AsyncMock()

        with patch("balatrobot.pool.BalatroInstance", return_value=mock_inst), \
             patch("balatrobot.state.allocate_ports", return_value=[14001]):
            async with Server(config, n=1, state_path=state_path) as server:
                assert server.pool is not None
                assert isinstance(server.pool, BalatroPool)
                assert server.pool.is_started is True


class TestServerRun:
    """Tests for Server.run() supervision loop."""

    @pytest.mark.asyncio
    async def test_run_sigterm_exits_cleanly(self, tmp_path):
        """run() returns normally when shutdown event is set."""
        state_path = tmp_path / "state.json"
        config = Config(logs_path=str(tmp_path))

        mock_inst = MagicMock()
        mock_inst.port = 14001
        mock_inst.log_path = "/tmp/test-logs/14001.log"
        mock_inst.start = AsyncMock()
        mock_inst.stop = AsyncMock()
        mock_inst.check_alive = MagicMock()

        with patch("balatrobot.pool.BalatroInstance", return_value=mock_inst), \
             patch("balatrobot.state.allocate_ports", return_value=[14001]):
            async with Server(config, n=1, state_path=state_path) as server:
                # Pre-set the shutdown event so run() exits immediately
                server._shutdown.set()
                await server.run()  # Should return without error

    @pytest.mark.asyncio
    async def test_run_child_death_raises(self, tmp_path):
        """run() raises InstanceDiedError when child dies, state file cleaned up."""
        state_path = tmp_path / "state.json"
        config = Config(logs_path=str(tmp_path))

        mock_inst = MagicMock()
        mock_inst.port = 14001
        mock_inst.log_path = "/tmp/test-logs/14001.log"
        mock_inst.start = AsyncMock()
        mock_inst.stop = AsyncMock()

        with patch("balatrobot.pool.BalatroInstance", return_value=mock_inst), \
             patch("balatrobot.state.allocate_ports", return_value=[14001]):
            async with Server(config, n=1, state_path=state_path) as server:
                # Mock check_alive to raise InstanceDiedError
                assert server._pool is not None
                server._pool.check_alive = MagicMock(  # ty: ignore[invalid-assignment]
                    side_effect=InstanceDiedError(
                        port=14001, log_path="/tmp/test-logs/14001.log"
                    )
                )
                with pytest.raises(InstanceDiedError) as exc_info:
                    await server.run()
                assert exc_info.value.port == 14001

        # State file should be cleaned up by __aexit__
        assert not state_path.exists()

    @pytest.mark.asyncio
    async def test_run_skips_signal_handler_on_windows(self, tmp_path):
        """run() does not register signal handlers on Windows."""
        state_path = tmp_path / "state.json"
        config = Config(logs_path=str(tmp_path))

        mock_inst = MagicMock()
        mock_inst.port = 14001
        mock_inst.log_path = "/tmp/test-logs/14001.log"
        mock_inst.start = AsyncMock()
        mock_inst.stop = AsyncMock()
        mock_inst.check_alive = MagicMock()

        with patch("balatrobot.pool.BalatroInstance", return_value=mock_inst), \
             patch("balatrobot.state.allocate_ports", return_value=[14001]), \
             patch("balatrobot.cli.serve.sys") as mock_sys, \
             patch("balatrobot.cli.serve.asyncio.get_running_loop") as mock_get_loop:
            mock_sys.platform = "win32"
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop

            async with Server(config, n=1, state_path=state_path) as server:
                server._shutdown.set()
                await server.run()

            # add_signal_handler should never be called on Windows
            mock_loop.add_signal_handler.assert_not_called()
            mock_loop.remove_signal_handler.assert_not_called()
