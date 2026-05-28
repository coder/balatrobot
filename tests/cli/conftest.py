"""Shared test fixtures for CLI tests."""

import asyncio
import os
import random
from unittest.mock import AsyncMock, MagicMock

import pytest

from balatrobot.cli.client import BalatroClient
from balatrobot.config import ENV_MAP, Config
from balatrobot.instance import BalatroInstance

# ============================================================================
# Constants
# ============================================================================

HOST = "127.0.0.1"


# ============================================================================
# Pytest Hooks for Balatro Instance Management
# ============================================================================


def pytest_configure(config):
    """Start Balatro instances for integration tests (master only)."""
    # Skip if xdist worker (master handles startup)
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return

    # Determine parallelism
    numprocesses = getattr(config.option, "numprocesses", None)
    parallel = numprocesses if numprocesses and numprocesses > 0 else 1

    # Allocate random ports
    ports = random.sample(range(20000, 30000), parallel)
    os.environ["BALATROBOT_CLI_PORTS"] = ",".join(str(p) for p in ports)

    config._cli_balatro_ports = ports
    config._cli_balatro_parallel = parallel

    # Start instances
    base_config = Config.from_env()
    instances: list[BalatroInstance] = []

    async def start_all():
        for port in ports:
            instances.append(BalatroInstance(base_config, port=port))
        await asyncio.gather(*[inst.start() for inst in instances])
        print(f"CLI tests: {parallel} Balatro instance(s) started on ports: {ports}")

    try:
        asyncio.run(start_all())
        config._cli_balatro_instances = instances
    except Exception as e:
        # Cleanup on failure
        async def cleanup():
            for instance in instances:
                await instance.stop()

        asyncio.run(cleanup())
        raise pytest.UsageError(f"Could not start Balatro instances: {e}") from e


def pytest_unconfigure(config):
    """Stop Balatro instances after tests complete."""
    instances = getattr(config, "_cli_balatro_instances", None)
    if instances is None:
        return

    async def stop_all():
        for instance in instances:
            await instance.stop()

    try:
        asyncio.run(stop_all())
    except Exception as e:
        print(f"Error stopping Balatro instances: {e}")


# ============================================================================
# Session-scoped Fixtures for Integration Tests
# ============================================================================


@pytest.fixture(scope="session")
def cli_port(worker_id) -> int:
    """Get assigned port for this worker from env var."""
    ports_str = os.environ.get("BALATROBOT_CLI_PORTS", "12346")
    ports = [int(p) for p in ports_str.split(",")]

    if worker_id == "master":
        return ports[0]

    worker_num = int(worker_id.replace("gw", ""))
    return ports[worker_num]


@pytest.fixture
def balatro_client(cli_port: int) -> BalatroClient:
    """Create BalatroClient connected to test server."""
    return BalatroClient(host=HOST, port=cli_port)


# ============================================================================
# Existing Fixtures (Mocks)
# ============================================================================


@pytest.fixture
def clean_env(monkeypatch):
    """Clear all BALATROBOT_* env vars for clean tests."""
    for env_var in ENV_MAP.values():
        monkeypatch.delenv(env_var, raising=False)
    yield


@pytest.fixture
def mock_popen(monkeypatch):
    """Mock subprocess.Popen for lifecycle tests."""
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.terminate = MagicMock()
    mock_process.kill = MagicMock()
    mock_process.wait = MagicMock(return_value=0)

    mock_popen_cls = MagicMock(return_value=mock_process)
    monkeypatch.setattr("subprocess.Popen", mock_popen_cls)

    return mock_process


@pytest.fixture
def mock_httpx_success(monkeypatch):
    """Mock httpx.AsyncClient returning successful health response."""

    async def mock_post(*args, **kwargs):
        response = MagicMock()
        response.json.return_value = {"result": {"status": "ok"}}
        return response

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = mock_post

    mock_async_client = MagicMock(return_value=mock_client)
    monkeypatch.setattr("httpx.AsyncClient", mock_async_client)

    return mock_client


@pytest.fixture
def mock_httpx_fail(monkeypatch):
    """Mock httpx.AsyncClient always raising ConnectionError."""
    import httpx

    async def mock_post(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = mock_post

    mock_async_client = MagicMock(return_value=mock_client)
    monkeypatch.setattr("httpx.AsyncClient", mock_async_client)

    return mock_client
