"""Lua API test-specific configuration and fixtures."""

import asyncio
import json
import os
import random
import tempfile
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Generator

import httpx
import pytest

from balatrobot.config import Config
from balatrobot.instance import BalatroInstance
from balatrobot.pool import InstanceInfo

# ============================================================================
# Constants
# ============================================================================

HOST: str = "127.0.0.1"  # Default host for Balatro server
CONNECTION_TIMEOUT: float = 60.0  # Connection timeout in seconds
REQUEST_TIMEOUT: float = 30.0  # Default per-request timeout in seconds

# JSON-RPC 2.0 request ID counter
_request_id_counter: int = 0

# Default cache behavior for load_fixture
_USE_CACHE_DEFAULT: bool = True


def _check_health(host: str, port: int, timeout: float = 2.0) -> bool:
    """Sync health check for test fixtures."""
    url = f"http://{host}:{port}"
    payload = {"jsonrpc": "2.0", "method": "health", "params": {}, "id": 1}
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=payload)
            data = response.json()
            return "result" in data and data["result"].get("status") == "ok"
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def pytest_addoption(parser):
    """Add command line options."""
    parser.addoption(
        "--no-caches",
        action="store_true",
        default=False,
        help="Disable fixture caching and force regeneration.",
    )


def pytest_configure(config):
    """Configure pytest and start Balatro instances."""
    global _USE_CACHE_DEFAULT
    if config.getoption("--no-caches", default=False):
        _USE_CACHE_DEFAULT = False

    # Skip if running as xdist worker (master handles startup)
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    if worker_id is not None:
        return

    # Determine parallelism
    numprocesses = getattr(config.option, "numprocesses", None)
    parallel = numprocesses if numprocesses and numprocesses > 0 else 1

    # Allocate random ports
    port_range_start = 12346
    port_range_end = 23456
    ports = random.sample(range(port_range_start, port_range_end), parallel)

    os.environ["BALATROBOT_PORTS"] = ",".join(str(p) for p in ports)

    config._balatro_ports = ports
    config._balatro_parallel = parallel

    # Start instances
    base_config = Config.from_env()
    instances: list[BalatroInstance] = []

    async def start_all():
        for port in ports:
            instances.append(BalatroInstance(base_config, port=port))
        await asyncio.gather(*[inst.start() for inst in instances])
        print(f"All {parallel} Balatro instance(s) started on ports: {ports}")

    try:
        asyncio.run(start_all())
        config._balatro_instances = instances
    except Exception as e:

        async def cleanup():
            for instance in instances:
                await instance.stop()

        asyncio.run(cleanup())
        raise pytest.UsageError(f"Could not start Balatro instances: {e}") from e


def pytest_unconfigure(config):
    """Stop Balatro instances after tests complete."""
    instances = getattr(config, "_balatro_instances", None)
    if instances is None:
        return

    async def stop_all():
        for instance in instances:
            await instance.stop()

    try:
        asyncio.run(stop_all())
    except Exception as e:
        print(f"Error stopping Balatro instances: {e}")


def pytest_collection_modifyitems(items):
    """No-op placeholder. Kept for pytest hook consistency."""


@pytest.fixture(scope="session")
def instance(worker_id) -> InstanceInfo:
    """Return InstanceInfo for this worker's assigned instance."""
    ports_str = os.environ.get("BALATROBOT_PORTS", "12346")
    ports = [int(p) for p in ports_str.split(",")]

    if worker_id == "master":
        port = ports[0]
    else:
        worker_num = int(worker_id.replace("gw", ""))
        port = ports[worker_num]

    return InstanceInfo(host=HOST, port=port)


@pytest.fixture(scope="session")
async def balatro_server(instance: InstanceInfo) -> AsyncGenerator[None, None]:
    """Wait for pre-started Balatro instance to be healthy."""
    timeout = 10.0
    elapsed = 0.0
    while elapsed < timeout:
        if _check_health(instance.host, instance.port):
            print(f"[worker] Connected to Balatro on port {instance.port}")
            yield None
            return
        await asyncio.sleep(0.5)
        elapsed += 0.5

    pytest.fail(f"Balatro instance on port {instance.port} not responding")


@pytest.fixture
def client(
    instance: InstanceInfo, balatro_server
) -> Generator[httpx.Client, None, None]:
    """Create an HTTP client connected to Balatro game instance.

    Args:
        instance: The InstanceInfo for the assigned instance.
        balatro_server: Ensures the server is healthy.

    Yields:
        An httpx.Client for communicating with the game.
    """
    with httpx.Client(
        base_url=instance.url,
        timeout=httpx.Timeout(CONNECTION_TIMEOUT, read=REQUEST_TIMEOUT),
    ) as http_client:
        yield http_client


# ============================================================================
# Helper Functions
# ============================================================================


def api(
    client: httpx.Client,
    method: str,
    params: dict = {},
    timeout: float = REQUEST_TIMEOUT,
) -> dict[str, Any]:
    """Send a JSON-RPC 2.0 API call to the Balatro game and get the response.

    Args:
        client: The HTTP client connected to the game.
        method: The name of the API method to call.
        params: Dictionary of parameters to pass to the API method (default: {}).
        timeout: Request timeout in seconds (default: 5.0).

    Returns:
        The raw JSON-RPC 2.0 response with either 'result' or 'error' field.
    """
    global _request_id_counter
    _request_id_counter += 1

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": _request_id_counter,
    }

    response = client.post("/", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def send_request(
    client: httpx.Client,
    method: str,
    params: dict[str, Any],
    request_id: int | str | None = None,
    timeout: float = REQUEST_TIMEOUT,
) -> httpx.Response:
    """Send a JSON-RPC 2.0 request to the server.

    Args:
        client: The HTTP client connected to the game.
        method: The name of the method to call.
        params: Dictionary of parameters to pass to the method.
        request_id: Optional request ID (auto-increments if not provided).
        timeout: Request timeout in seconds (default: 5.0).

    Returns:
        The HTTP response object.
    """
    global _request_id_counter
    if request_id is None:
        _request_id_counter += 1
        request_id = _request_id_counter

    request = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id,
    }

    return client.post("/", json=request, timeout=timeout)


def get_fixture_path(endpoint: str, fixture_name: str) -> Path:
    """Get path to a test fixture file.

    Args:
        endpoint: The endpoint directory (e.g., "save", "load").
        fixture_name: Name of the fixture file (e.g., "start.jkr").

    Returns:
        Path to the fixture file in tests/fixtures/<endpoint>/.
    """
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    return fixtures_dir / endpoint / f"{fixture_name}.jkr"


def create_temp_save_path() -> Path:
    """Create a temporary path for save files.

    Returns:
        Path to a temporary .jkr file in the system temp directory.
    """
    temp_dir = Path(tempfile.gettempdir())
    return temp_dir / f"balatrobot_test_{uuid.uuid4().hex[:8]}.jkr"


def load_fixture(
    client: httpx.Client,
    endpoint: str,
    fixture_name: str,
    cache: bool | None = None,
) -> dict[str, Any]:
    """Load a fixture file and return the resulting gamestate.

    This helper function consolidates the common pattern of:
    1. Loading a fixture file (or generating it if missing)
    2. Asserting the load succeeded
    3. Getting the current gamestate

    If the fixture file doesn't exist or cache=False, it will be automatically
    generated using the setup steps defined in fixtures.json.
    """
    global _USE_CACHE_DEFAULT
    if cache is None:
        cache = _USE_CACHE_DEFAULT

    fixture_path = get_fixture_path(endpoint, fixture_name)

    # Generate fixture if it doesn't exist or cache=False
    if not fixture_path.exists() or not cache:
        fixtures_json_path = Path(__file__).parent.parent / "fixtures" / "fixtures.json"
        with open(fixtures_json_path) as f:
            fixtures_data = json.load(f)

        if endpoint not in fixtures_data:
            raise KeyError(f"Endpoint '{endpoint}' not found in fixtures.json")
        if fixture_name not in fixtures_data[endpoint]:
            raise KeyError(
                f"Fixture key '{fixture_name}' not found in fixtures.json['{endpoint}']"
            )

        setup_steps = fixtures_data[endpoint][fixture_name]

        # Execute each setup step
        for step in setup_steps:
            step_method = step["method"]
            step_params = step.get("params", {})
            response = api(client, step_method, step_params)

            # Check for errors during generation
            if "error" in response:
                error_msg = response["error"]["message"]
                raise AssertionError(
                    f"Fixture generation failed at step {step_method}: {error_msg}"
                )

        # Save the fixture
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        save_response = api(client, "save", {"path": str(fixture_path)})
        assert_path_response(save_response)

    # Load the fixture
    load_response = api(client, "load", {"path": str(fixture_path)})
    assert_path_response(load_response)
    gamestate_response = api(client, "gamestate", {})
    return gamestate_response["result"]


# ============================================================================
# Assertion Helpers
# ============================================================================


def assert_health_response(response: dict[str, Any]) -> None:
    """Assert response is a Response.Endpoint.Health.

    Used by: health endpoint.

    Args:
        response: The raw JSON-RPC 2.0 response.

    Raises:
        AssertionError: If response is not a valid HealthResponse.
    """
    assert "result" in response, f"Expected 'result' in response, got: {response}"
    assert "error" not in response, f"Unexpected error: {response.get('error')}"
    result = response["result"]
    assert "status" in result, f"HealthResponse missing 'status': {result}"
    assert result["status"] == "ok", f"HealthResponse status not 'ok': {result}"


def assert_path_response(
    response: dict[str, Any],
    expected_path: str | None = None,
) -> str:
    """Assert response is a Response.Endpoint.Path and return the path.

    Used by: save, load endpoints.

    Args:
        response: The raw JSON-RPC 2.0 response.
        expected_path: Optional expected path to verify.

    Returns:
        The path from the response.

    Raises:
        AssertionError: If response is not a valid PathResponse.
    """
    assert "result" in response, f"Expected 'result' in response, got: {response}"
    assert "error" not in response, f"Unexpected error: {response.get('error')}"
    result = response["result"]
    assert "success" in result, f"PathResponse missing 'success': {result}"
    assert result["success"] is True, f"PathResponse success is not True: {result}"
    assert "path" in result, f"PathResponse missing 'path': {result}"
    assert isinstance(result["path"], str), (
        f"PathResponse 'path' not a string: {result}"
    )

    if expected_path is not None:
        assert result["path"] == expected_path, (
            f"Expected path '{expected_path}', got '{result['path']}'"
        )

    return result["path"]


def assert_gamestate_response(
    response: dict[str, Any],
    **expected_fields: Any,
) -> dict[str, Any]:
    """Assert response is a Response.Endpoint.GameState and return the gamestate.

    Used by: gamestate, menu, start, set, buy, sell, play, discard, select, etc.

    Args:
        response: The raw JSON-RPC 2.0 response.
        **expected_fields: Optional field values to verify (e.g., state="SHOP", money=100).

    Returns:
        The gamestate from the response.

    Raises:
        AssertionError: If response is not a valid GameStateResponse.
    """
    assert "result" in response, f"Expected 'result' in response, got: {response}"
    assert "error" not in response, f"Unexpected error: {response.get('error')}"
    result = response["result"]

    # Verify required GameState field
    assert "state" in result, f"GameStateResponse missing 'state': {result}"
    assert isinstance(result["state"], str), (
        f"GameStateResponse 'state' not a string: {result}"
    )

    # Verify any expected fields
    for field, expected_value in expected_fields.items():
        assert field in result, f"GameStateResponse missing '{field}': {result}"
        assert result[field] == expected_value, (
            f"GameStateResponse '{field}': expected {expected_value!r}, got {result[field]!r}"
        )

    return result


def assert_test_response(
    response: dict[str, Any],
    expected_received_args: dict[str, Any] | None = None,
    expected_state_validated: bool | None = None,
) -> dict[str, Any]:
    """Assert response is a Response.Endpoint.Test and return the result.

    Used by: test_validation, test_endpoint, test_state, test_echo endpoints.

    Args:
        response: The raw JSON-RPC 2.0 response.
        expected_received_args: Optional expected received_args to verify.
        expected_state_validated: Optional expected state_validated to verify.

    Returns:
        The test result from the response.

    Raises:
        AssertionError: If response is not a valid TestResponse.
    """
    assert "result" in response, f"Expected 'result' in response, got: {response}"
    assert "error" not in response, f"Unexpected error: {response.get('error')}"
    result = response["result"]
    assert "success" in result, f"TestResponse missing 'success': {result}"
    assert result["success"] is True, f"TestResponse success is not True: {result}"

    if expected_received_args is not None:
        assert "received_args" in result, (
            f"TestResponse missing 'received_args': {result}"
        )
        assert result["received_args"] == expected_received_args, (
            f"TestResponse received_args: expected {expected_received_args}, got {result['received_args']}"
        )

    if expected_state_validated is not None:
        assert "state_validated" in result, (
            f"TestResponse missing 'state_validated': {result}"
        )
        assert result["state_validated"] == expected_state_validated, (
            f"TestResponse state_validated: expected {expected_state_validated}, got {result['state_validated']}"
        )

    return result


def assert_error_response(
    response: dict[str, Any],
    expected_error_name: str | None = None,
    expected_message_contains: str | None = None,
) -> dict[str, Any]:
    """Assert response is a Response.Server.Error and return the error data.

    Args:
        response: The raw JSON-RPC 2.0 response.
        expected_error_name: Optional expected error name (BAD_REQUEST, INVALID_STATE, etc.).
        expected_message_contains: Optional substring to check in error message (case-insensitive).

    Returns:
        The error data dict with 'name' field.

    Raises:
        AssertionError: If response is not a valid ErrorResponse.
    """
    assert "error" in response, f"Expected 'error' in response, got: {response}"
    assert "result" not in response, (
        f"Unexpected 'result' in error response: {response}"
    )

    error = response["error"]
    assert "message" in error, f"ErrorResponse missing 'message': {error}"
    assert "data" in error, f"ErrorResponse missing 'data': {error}"
    assert "name" in error["data"], f"ErrorResponse data missing 'name': {error}"
    assert isinstance(error["message"], str), (
        f"ErrorResponse 'message' not a string: {error}"
    )
    assert isinstance(error["data"]["name"], str), (
        f"ErrorResponse 'name' not a string: {error}"
    )

    if expected_error_name is not None:
        actual_name = error["data"]["name"]
        assert actual_name == expected_error_name, (
            f"Expected error name '{expected_error_name}', got '{actual_name}'"
        )

    if expected_message_contains is not None:
        actual_message = error["message"]
        assert expected_message_contains.lower() in actual_message.lower(), (
            f"Expected message to contain '{expected_message_contains}', got '{actual_message}'"
        )

    return error["data"]
