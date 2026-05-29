"""Tests for balatrobot.manager module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from balatrobot.config import Config
from balatrobot.instance import BalatroInstance, InstanceDiedError


class TestBalatroInstanceInit:
    """Tests for BalatroInstance initialization."""

    def test_init_with_default_config(self):
        """Creates instance with default config when none provided."""
        instance = BalatroInstance()
        assert instance.port == 12346

    def test_init_with_config(self):
        """Uses provided config."""
        config = Config(port=9999)
        instance = BalatroInstance(config)
        assert instance.port == 9999

    def test_init_with_overrides(self):
        """Overrides apply to base config."""
        config = Config(port=8888, fast=False)
        instance = BalatroInstance(config, port=9999, fast=True)
        assert instance.port == 9999

    def test_init_overrides_without_config(self):
        """Overrides work without explicit config."""
        instance = BalatroInstance(port=9999)
        assert instance.port == 9999


class TestBalatroInstanceProperties:
    """Tests for BalatroInstance properties."""

    def test_port_property(self):
        """port property returns config port."""
        instance = BalatroInstance(port=9999)
        assert instance.port == 9999

    def test_process_not_started(self):
        """process property raises when not started."""
        instance = BalatroInstance()
        with pytest.raises(RuntimeError, match="Instance not started"):
            _ = instance.process

    def test_log_path_not_started(self):
        """log_path is None before start."""
        instance = BalatroInstance()
        assert instance.log_path is None


class TestBalatroInstanceStart:
    """Tests for BalatroInstance.start() method."""

    @pytest.mark.asyncio
    async def test_start_already_started(self):
        """Raises RuntimeError when already started."""
        instance = BalatroInstance()
        instance._process = MagicMock()  # Simulate started state

        with pytest.raises(RuntimeError, match="Instance already started"):
            await instance.start()


class TestBalatroInstanceStop:
    """Tests for BalatroInstance.stop() method."""

    @pytest.mark.asyncio
    async def test_stop_not_started(self):
        """Stop does nothing when not started."""
        instance = BalatroInstance()
        await instance.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_stop_graceful(self):
        """Stop terminates process gracefully."""
        instance = BalatroInstance()
        mock_process = MagicMock()
        mock_process.terminate = MagicMock()
        mock_process.wait = MagicMock(return_value=0)
        instance._process = mock_process

        await instance.stop()

        mock_process.terminate.assert_called_once()
        assert instance._process is None

    @pytest.mark.asyncio
    async def test_stop_force_kill(self, monkeypatch):
        """Stop force kills when graceful termination times out."""
        instance = BalatroInstance()
        mock_process = MagicMock()
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = MagicMock(return_value=0)
        instance._process = mock_process

        # Make the first wait_for timeout, but second succeed
        call_count = 0
        original_wait_for = asyncio.wait_for

        async def mock_wait_for(coro, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call (graceful wait) times out
                await coro  # Consume the coroutine to avoid warning
                raise asyncio.TimeoutError()
            # Second call (after kill) succeeds
            return await original_wait_for(coro, timeout)

        monkeypatch.setattr("asyncio.wait_for", mock_wait_for)

        await instance.stop()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()


class TestBalatroInstanceHealthCheck:
    """Tests for BalatroInstance._wait_for_health() method."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_httpx_success):
        """Health check succeeds with OK response."""
        instance = BalatroInstance()

        # Should not raise
        await instance._wait_for_health(timeout=1.0)

    @pytest.mark.asyncio
    async def test_health_check_timeout(self, mock_httpx_fail):
        """Health check raises after timeout."""
        instance = BalatroInstance()

        with pytest.raises(RuntimeError, match="Health check failed"):
            await instance._wait_for_health(timeout=1.0)


class TestBalatroInstanceContextManager:
    """Tests for BalatroInstance context manager protocol."""

    @pytest.mark.asyncio
    async def test_context_manager_calls_start_stop(self, tmp_path, monkeypatch):
        """Context manager calls start on enter and stop on exit."""
        # Mock the launcher and health check
        mock_launcher = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 12345

        async def mock_start(config, session_dir):
            return mock_process

        mock_launcher.start = mock_start
        mock_launcher.validate_paths = MagicMock()
        mock_launcher.build_env = MagicMock(return_value={})
        mock_launcher.build_cmd = MagicMock(return_value=["echo"])

        monkeypatch.setattr("balatrobot.instance.get_launcher", lambda x: mock_launcher)

        instance = BalatroInstance(logs_path=str(tmp_path))

        # Mock health check to succeed immediately
        instance._wait_for_health = AsyncMock()  # ty: ignore[invalid-assignment]

        async with instance:
            assert instance._process is mock_process

        # After exit, process should be cleared
        assert instance._process is None


class TestBalatroInstanceCheckAlive:
    """Tests for BalatroInstance.check_alive() method."""

    def test_check_alive_healthy(self):
        """No exception when process is running (poll returns None)."""
        instance = BalatroInstance(port=14001)
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        instance._process = mock_process

        instance.check_alive()  # Should not raise

    def test_check_alive_dead(self):
        """Raises InstanceDiedError when process has exited."""
        instance = BalatroInstance(port=14001)
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Exit code 1
        instance._process = mock_process
        instance._log_path = MagicMock()
        instance._log_path.__str__ = lambda self: "/tmp/test/14001.log"

        with pytest.raises(InstanceDiedError) as exc_info:
            instance.check_alive()
        assert exc_info.value.port == 14001
        assert "14001" in str(exc_info.value)

    def test_check_alive_dead_with_log_path(self):
        """InstanceDiedError includes log_path in message."""
        from pathlib import Path

        instance = BalatroInstance(port=14002)
        mock_process = MagicMock()
        mock_process.poll.return_value = 0
        instance._process = mock_process
        instance._log_path = Path("/tmp/logs/session/14002.log")

        with pytest.raises(InstanceDiedError) as exc_info:
            instance.check_alive()
        assert exc_info.value.port == 14002
        assert exc_info.value.log_path == "/tmp/logs/session/14002.log"
        assert "/tmp/logs/session/14002.log" in str(exc_info.value)

    def test_check_alive_not_started(self):
        """No exception when _process is None (not started)."""
        instance = BalatroInstance(port=14001)
        assert instance._process is None
        instance.check_alive()  # Should not raise
