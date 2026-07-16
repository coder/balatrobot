"""Tests for balatrobot.pool module."""

from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from balatrobot.config import Config
from balatrobot.instance import BalatroInstance, InstanceDiedError, InstanceInfo
from balatrobot.pool import BalatroPool

# ============================================================================
# InstanceInfo tests
# ============================================================================


class TestInstanceInfo:
    """Tests for InstanceInfo frozen dataclass."""

    def test_create_with_host_port(self):
        """InstanceInfo stores host and port."""
        info = InstanceInfo(host="127.0.0.1", port=12346)
        assert info.host == "127.0.0.1"
        assert info.port == 12346
        assert info.log_path is None

    def test_create_with_log_path(self):
        """InstanceInfo stores log_path."""
        info = InstanceInfo(
            host="127.0.0.1", port=12346, log_path=Path("/tmp/test.log")
        )
        assert info.log_path == Path("/tmp/test.log")

    def test_url_property(self):
        """url property returns formatted URL."""
        info = InstanceInfo(host="0.0.0.0", port=9999)
        assert info.url == "http://0.0.0.0:9999"

    def test_frozen(self):
        """InstanceInfo is immutable."""
        info = InstanceInfo(host="127.0.0.1", port=12346)
        with pytest.raises(FrozenInstanceError):
            setattr(info, "port", 9999)

    def test_equality(self):
        """Two InstanceInfo with same values are equal."""
        a = InstanceInfo(host="127.0.0.1", port=12346)
        b = InstanceInfo(host="127.0.0.1", port=12346)
        assert a == b

    def test_inequality(self):
        """Different port means different InstanceInfo."""
        a = InstanceInfo(host="127.0.0.1", port=12346)
        b = InstanceInfo(host="127.0.0.1", port=9999)
        assert a != b

    def test_stream_port_default_none(self):
        """stream_port defaults to None."""
        info = InstanceInfo(host="127.0.0.1", port=12346)
        assert info.stream_port is None

    def test_stream_port_set(self):
        """stream_port is stored."""
        info = InstanceInfo(host="127.0.0.1", port=12346, stream_port=8080)
        assert info.stream_port == 8080

    def test_stream_url_none_when_no_stream_port(self):
        """stream_url is None when stream_port is unset."""
        info = InstanceInfo(host="127.0.0.1", port=12346)
        assert info.stream_url is None

    def test_stream_url_built_from_host_and_stream_port(self):
        """stream_url is the HLS endpoint when stream_port is set."""
        info = InstanceInfo(host="127.0.0.1", port=12346, stream_port=8080)
        assert info.stream_url == "http://127.0.0.1:8080/index.m3u8"


# ============================================================================
# BalatroPool tests
# ============================================================================


class TestBalatroPoolInit:
    """Tests for BalatroPool initialization."""

    def test_init_defaults(self):
        """Pool defaults to n=1, no ports."""
        config = Config()
        pool = BalatroPool(config)
        assert pool.n == 1
        assert pool.is_started is False
        assert pool.instances == []

    def test_init_with_n(self):
        """Pool accepts n parameter."""
        config = Config()
        pool = BalatroPool(config, n=3)
        assert pool.n == 3

    def test_init_with_ports(self):
        """Pool accepts explicit ports list."""
        config = Config()
        pool = BalatroPool(config, ports=[10000, 10001, 10002])
        assert pool.n == 3

    def test_init_ports_override_n(self):
        """Ports length overrides n."""
        config = Config()
        pool = BalatroPool(config, n=5, ports=[10000, 10001])
        assert pool.n == 2


class TestBalatroPoolStartStop:
    """Tests for BalatroPool start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_instances(self, tmp_path, monkeypatch):
        """start() creates n instances and populates instances list."""
        config = Config(logs=str(tmp_path))

        # Mock BalatroInstance
        mock_inst = AsyncMock(spec=BalatroInstance)
        mock_inst.port = 12346
        mock_inst._config = config
        mock_inst.start = AsyncMock()

        created_instances = []

        def mock_instance_factory(config_arg, **kwargs):
            inst = MagicMock(spec=BalatroInstance)
            port = kwargs.get("port", 12346)
            inst.port = port
            inst.log_path = Path(f"/tmp/test-logs/{port}.log")
            inst.start = AsyncMock()
            inst.stop = AsyncMock()
            created_instances.append(inst)
            return inst

        with patch(
            "balatrobot.pool.BalatroInstance", side_effect=mock_instance_factory
        ):
            pool = BalatroPool(config, ports=[14001, 14002])
            await pool.start()

        assert pool.is_started is True
        assert len(pool.instances) == 2
        assert pool.instances[0].port == 14001
        assert pool.instances[1].port == 14002

        await pool.stop()

    @pytest.mark.asyncio
    async def test_stop_concurrent(self, tmp_path):
        """stop() stops all instances concurrently."""
        config = Config(logs=str(tmp_path))

        mock_instances = []
        for port in [14001, 14002]:
            inst = MagicMock(spec=BalatroInstance)
            inst.port = port
            inst.log_path = Path(f"/tmp/test-logs/{port}.log")
            inst.start = AsyncMock()
            inst.stop = AsyncMock()
            mock_instances.append(inst)

        with patch("balatrobot.pool.BalatroInstance", side_effect=mock_instances):
            pool = BalatroPool(config, ports=[14001, 14002])
            await pool.start()
            await pool.stop()

        assert pool.is_started is False
        for inst in mock_instances:
            inst.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_fail_cleans_up(self, tmp_path):
        """If one instance fails to start, all are stopped."""
        config = Config(logs=str(tmp_path))

        started_inst = MagicMock(spec=BalatroInstance)
        started_inst.port = 14001
        started_inst.log_path = Path("/tmp/test-logs/14001.log")
        started_inst.start = AsyncMock()
        started_inst.stop = AsyncMock()

        failed_inst = MagicMock(spec=BalatroInstance)
        failed_inst.port = 14002
        failed_inst.log_path = Path("/tmp/test-logs/14002.log")
        failed_inst.start = AsyncMock(side_effect=RuntimeError("start failed"))
        failed_inst.stop = AsyncMock()

        with patch(
            "balatrobot.pool.BalatroInstance", side_effect=[started_inst, failed_inst]
        ):
            pool = BalatroPool(config, ports=[14001, 14002])
            with pytest.raises(RuntimeError, match="start failed"):
                await pool.start()

        # Started instance should have been stopped
        started_inst.stop.assert_called_once()
        assert pool.is_started is False
        assert pool.instances == []

    @pytest.mark.asyncio
    async def test_stop_idempotent(self, tmp_path):
        """stop() is safe to call when not started."""
        config = Config(logs=str(tmp_path))
        pool = BalatroPool(config)
        await pool.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_start_already_started(self, tmp_path):
        """start() raises if already started."""
        config = Config(logs=str(tmp_path))
        pool = BalatroPool(config)

        mock_inst = MagicMock(spec=BalatroInstance)
        mock_inst.port = 14001
        mock_inst.log_path = Path("/tmp/test-logs/14001.log")
        mock_inst.start = AsyncMock()
        mock_inst.stop = AsyncMock()

        with patch("balatrobot.pool.BalatroInstance", return_value=mock_inst):
            await pool.start()
            with pytest.raises(RuntimeError, match="already started"):
                await pool.start()
            await pool.stop()

    @pytest.mark.asyncio
    async def test_instances_populated_after_start(self, tmp_path):
        """instances returns InstanceInfo list after start."""
        config = Config(logs=str(tmp_path))

        mock_instances = []
        for port in [14001, 14002]:
            inst = MagicMock(spec=BalatroInstance)
            inst.port = port
            inst.log_path = Path(f"/tmp/test-logs/{port}.log")
            inst.start = AsyncMock()
            inst.stop = AsyncMock()
            mock_instances.append(inst)

        with patch("balatrobot.pool.BalatroInstance", side_effect=mock_instances):
            pool = BalatroPool(config, ports=[14001, 14002])
            await pool.start()

        infos = pool.instances
        assert len(infos) == 2
        assert all(isinstance(i, InstanceInfo) for i in infos)
        assert infos[0].port == 14001
        assert infos[1].port == 14002
        assert infos[0].host == config.host
        assert infos[0].log_path == Path("/tmp/test-logs/14001.log")
        assert infos[1].log_path == Path("/tmp/test-logs/14002.log")

        await pool.stop()


class TestBalatroPoolCheckAlive:
    """Tests for BalatroPool.check_alive() method."""

    def test_check_alive_all_healthy(self):
        """No exception when all instances are alive."""
        config = Config()
        pool = BalatroPool(config, ports=[14001, 14002])

        mock_inst1 = MagicMock(spec=BalatroInstance)
        mock_inst1.check_alive = MagicMock()
        mock_inst2 = MagicMock(spec=BalatroInstance)
        mock_inst2.check_alive = MagicMock()

        pool._instances = [mock_inst1, mock_inst2]
        pool.check_alive()  # Should not raise

        mock_inst1.check_alive.assert_called_once()
        mock_inst2.check_alive.assert_called_once()

    def test_check_alive_one_dead(self):
        """Raises InstanceDiedError from first dead instance."""
        config = Config()
        pool = BalatroPool(config, ports=[14001, 14002])

        mock_inst1 = MagicMock(spec=BalatroInstance)
        mock_inst1.check_alive = MagicMock()
        mock_inst2 = MagicMock(spec=BalatroInstance)
        mock_inst2.check_alive = MagicMock(
            side_effect=InstanceDiedError(port=14002, log_path="/tmp/14002.log")
        )

        pool._instances = [mock_inst1, mock_inst2]
        with pytest.raises(InstanceDiedError) as exc_info:
            pool.check_alive()
        assert exc_info.value.port == 14002

    def test_check_alive_empty_pool(self):
        """No exception when pool has no instances."""
        config = Config()
        pool = BalatroPool(config)
        pool._instances = []
        pool.check_alive()  # Should not raise


class TestBalatroPoolPortAllocation:
    """Tests for automatic port allocation."""

    @pytest.mark.asyncio
    async def test_auto_allocate_ports(self, tmp_path):
        """Pool allocates ports automatically when none specified."""
        config = Config(logs=str(tmp_path))
        pool = BalatroPool(config, n=2)

        captured_ports = []

        def mock_instance_factory(config_arg, **kwargs):
            port = kwargs.get("port")
            captured_ports.append(port)
            inst = MagicMock(spec=BalatroInstance)
            inst.port = port
            inst.log_path = Path(f"/tmp/test-logs/{port}.log")
            inst.start = AsyncMock()
            inst.stop = AsyncMock()
            return inst

        with patch(
            "balatrobot.pool.BalatroInstance", side_effect=mock_instance_factory
        ):
            await pool.start()

        assert len(captured_ports) == 2
        assert captured_ports[0] != captured_ports[1]
        assert all(isinstance(p, int) for p in captured_ports)

        await pool.stop()


class TestBalatroPoolConfigDerivation:
    """Tests for pool config derivation."""

    @pytest.mark.asyncio
    async def test_derives_config_per_instance(self, tmp_path):
        """Pool derives configs from base config, each with unique port."""
        config = Config(host="0.0.0.0", logs=str(tmp_path))

        captured_configs = []
        captured_overrides = []

        def mock_instance_factory(config_arg, **kwargs):
            captured_configs.append(config_arg)
            captured_overrides.append(kwargs)
            inst = MagicMock(spec=BalatroInstance)
            inst.port = kwargs.get("port", 12346)
            inst.log_path = Path(f"/tmp/test-logs/{kwargs.get('port', 12346)}.log")
            inst.start = AsyncMock()
            inst.stop = AsyncMock()
            return inst

        with patch(
            "balatrobot.pool.BalatroInstance", side_effect=mock_instance_factory
        ):
            pool = BalatroPool(config, ports=[14001, 14002])
            await pool.start()

        # All configs should share host/logs
        assert all(c.host == "0.0.0.0" for c in captured_configs)
        # Each gets a different port
        assert captured_overrides[0]["port"] == 14001
        assert captured_overrides[1]["port"] == 14002

        await pool.stop()

    @pytest.mark.asyncio
    async def test_shared_session_name(self, tmp_path):
        """Pool generates a shared session name for all instances."""
        config = Config(logs=str(tmp_path))

        captured_session_names = []

        def mock_instance_factory(config_arg, **kwargs):
            session_name = kwargs.get("session_name")
            captured_session_names.append(session_name)
            inst = MagicMock(spec=BalatroInstance)
            inst.port = kwargs.get("port", 12346)
            inst.log_path = Path(f"/tmp/test-logs/{kwargs.get('port', 12346)}.log")
            inst.start = AsyncMock()
            inst.stop = AsyncMock()
            return inst

        with patch(
            "balatrobot.pool.BalatroInstance", side_effect=mock_instance_factory
        ):
            pool = BalatroPool(config, ports=[14001, 14002])
            await pool.start()

        # All instances share the same session name
        assert len(set(captured_session_names)) == 1
        assert captured_session_names[0] is not None

        await pool.stop()


class TestBalatroPoolStreamPorts:
    """Tests for BALATROBOX_STREAM-driven stream-port allocation."""

    @pytest.mark.asyncio
    async def test_no_stream_ports_when_env_unset(self, tmp_path, monkeypatch):
        """stream_port override is not passed when BALATROBOX_STREAM is unset."""
        monkeypatch.delenv("BALATROBOX_STREAM", raising=False)
        config = Config(logs=str(tmp_path))

        captured = []

        def factory(config_arg, **kwargs):
            captured.append(kwargs)
            inst = MagicMock(spec=BalatroInstance)
            inst.port = kwargs.get("port")
            inst.log_path = Path(f"/tmp/test-logs/{kwargs.get('port')}.log")
            inst.start = AsyncMock()
            inst.stop = AsyncMock()
            return inst

        with patch("balatrobot.pool.BalatroInstance", side_effect=factory):
            pool = BalatroPool(config, ports=[14001, 14002])
            await pool.start()

        for kw in captured:
            assert "stream_port" not in kw
        for info in pool.instances:
            assert info.stream_port is None

        await pool.stop()

    @pytest.mark.asyncio
    async def test_allocates_stream_ports_when_env_set(self, tmp_path, monkeypatch):
        """BALATROBOX_STREAM=1 allocates one stream port per instance."""
        monkeypatch.setenv("BALATROBOX_STREAM", "1")
        config = Config(logs=str(tmp_path))

        captured = []

        def factory(config_arg, **kwargs):
            captured.append(kwargs)
            inst = MagicMock(spec=BalatroInstance)
            inst.port = kwargs.get("port")
            inst.log_path = Path(f"/tmp/test-logs/{kwargs.get('port')}.log")
            inst.start = AsyncMock()
            inst.stop = AsyncMock()
            return inst

        with patch("balatrobot.pool.BalatroInstance", side_effect=factory):
            pool = BalatroPool(config, ports=[14001, 14002])
            await pool.start()

        # One stream_port override per instance, all distinct.
        stream_ports = [kw.get("stream_port") for kw in captured]
        assert len(stream_ports) == 2
        assert len(set(stream_ports)) == 2
        # InstanceInfo carries the same stream ports.
        infos = pool.instances
        assert {i.stream_port for i in infos} == set(stream_ports)
        assert all(i.stream_url is not None for i in infos)

        await pool.stop()
