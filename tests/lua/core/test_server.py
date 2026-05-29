"""
Integration tests for BB_SERVER HTTP communication (JSON-RPC 2.0).

Test classes are organized by functionality:
- TestHTTPServerInit: Server initialization and port binding
- TestHTTPServerRouting: HTTP routing (POST to "/" only, rpc.discover)
- TestHTTPServerJSONRPC: JSON-RPC 2.0 protocol enforcement
- TestHTTPServerRequestID: Request ID validation
- TestHTTPServerErrors: HTTP error responses
- TestHTTPServerConcurrency: Concurrent request handling
"""

import errno
import json
import socket
import threading

import httpx
import pytest

from balatrobot.instance import InstanceInfo


class TestHTTPServerInit:
    """Tests for HTTP server initialization and port binding."""

    def test_server_binds_to_configured_port(
        self, instance: InstanceInfo, balatro_server
    ) -> None:
        """Test that server is listening on the expected port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            sock.connect(("127.0.0.1", instance.port))
            assert sock.fileno() != -1, f"Should connect to port {instance.port}"

    def test_port_is_exclusively_bound(
        self, instance: InstanceInfo, balatro_server
    ) -> None:
        """Test that server exclusively binds the port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            with pytest.raises(OSError) as exc_info:
                sock.bind(("127.0.0.1", instance.port))
            assert exc_info.value.errno == errno.EADDRINUSE

    def test_server_responds_to_http(self, client: httpx.Client) -> None:
        """Test that server responds to HTTP requests."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": 1,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["status"] == "ok"


class TestHTTPServerRouting:
    """Tests for HTTP request routing."""

    def test_post_endpoint(self, client: httpx.Client) -> None:
        """Test POST accepts JSON-RPC requests."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": 1,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "jsonrpc" in data
        assert data["jsonrpc"] == "2.0"

    def test_rpc_discover_endpoint(self, client: httpx.Client) -> None:
        """Test rpc.discover returns the OpenRPC spec."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "rpc.discover",
                "params": {},
                "id": 1,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        spec = data["result"]
        assert "openrpc" in spec
        assert spec["openrpc"] == "1.3.2"
        assert "info" in spec
        assert "methods" in spec

    def test_get_returns_405(self, client: httpx.Client) -> None:
        """Test that GET returns 405 Method Not Allowed."""
        response = client.get("/")
        assert response.status_code == 405
        data = response.json()
        assert "error" in data
        assert "method not allowed" in data["error"]["message"].lower()

    def test_put_returns_405(self, client: httpx.Client) -> None:
        """Test that PUT returns 405 Method Not Allowed."""
        response = client.put("/", json={})
        assert response.status_code == 405
        data = response.json()
        assert "error" in data
        assert "method not allowed" in data["error"]["message"].lower()

    def test_options_returns_405(self, client: httpx.Client) -> None:
        """Test that OPTIONS returns 405 Method Not Allowed."""
        response = client.options("/")
        assert response.status_code == 405
        data = response.json()
        assert "error" in data
        assert "method not allowed" in data["error"]["message"].lower()

    def test_post_to_non_root_returns_404(self, client: httpx.Client) -> None:
        """Test that POST to paths other than '/' returns 404."""
        response = client.post(
            "/api/health",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": 1,
            },
        )
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "not found" in data["error"]["message"].lower()


class TestHTTPServerJSONRPC:
    """Tests for JSON-RPC 2.0 protocol enforcement over HTTP."""

    def test_invalid_json_body(self, client: httpx.Client) -> None:
        """Test that invalid JSON body returns JSON-RPC error."""
        response = client.post(
            "/",
            content=b"{invalid json}",
            headers={"Content-Type": "application/json"},
        )
        # HTTP 200 OK but JSON-RPC error in body
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["data"]["name"] == "BAD_REQUEST"
        assert "invalid json" in data["error"]["message"].lower()

    def test_missing_jsonrpc_version(self, client: httpx.Client) -> None:
        """Test that missing jsonrpc version returns error."""
        response = client.post(
            "/",
            json={
                "method": "health",
                "params": {},
                "id": 1,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["data"]["name"] == "BAD_REQUEST"

    def test_wrong_jsonrpc_version(self, client: httpx.Client) -> None:
        """Test that wrong jsonrpc version returns error."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "1.0",
                "method": "health",
                "params": {},
                "id": 1,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["data"]["name"] == "BAD_REQUEST"
        assert "2.0" in data["error"]["message"]

    def test_response_includes_request_id(self, client: httpx.Client) -> None:
        """Test that response includes the request ID."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": 42,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 42

    def test_string_request_id(self, client: httpx.Client) -> None:
        """Test that string request IDs are preserved."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": "my-request-id",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "my-request-id"


class TestHTTPServerRequestID:
    """Tests for JSON-RPC 2.0 request ID validation."""

    def test_missing_id_returns_error(self, client: httpx.Client) -> None:
        """Test that missing 'id' field returns error."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["data"]["name"] == "BAD_REQUEST"
        assert "id" in data["error"]["message"].lower()
        # id is null or omitted when request had no id
        assert data.get("id") is None

    def test_null_id_returns_error(self, client: httpx.Client) -> None:
        """Test that explicit null 'id' returns error."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": None,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["data"]["name"] == "BAD_REQUEST"
        assert "id" in data["error"]["message"].lower()

    def test_float_id_returns_error(self, client: httpx.Client) -> None:
        """Test that floating-point 'id' returns error."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": 1.5,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["data"]["name"] == "BAD_REQUEST"
        assert "integer" in data["error"]["message"].lower()

    def test_boolean_id_returns_error(self, client: httpx.Client) -> None:
        """Test that boolean 'id' returns error."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["data"]["name"] == "BAD_REQUEST"

    def test_array_id_returns_error(self, client: httpx.Client) -> None:
        """Test that array 'id' returns error."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": [1, 2, 3],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["data"]["name"] == "BAD_REQUEST"

    def test_object_id_returns_error(self, client: httpx.Client) -> None:
        """Test that object 'id' returns error."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": {"key": "value"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["data"]["name"] == "BAD_REQUEST"

    def test_zero_id_is_valid(self, client: httpx.Client) -> None:
        """Test that zero is a valid integer ID."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": 0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["id"] == 0

    def test_negative_id_is_valid(self, client: httpx.Client) -> None:
        """Test that negative integers are valid IDs."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": -42,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["id"] == -42

    def test_empty_string_id_is_valid(self, client: httpx.Client) -> None:
        """Test that empty string is a valid ID."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": "",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["id"] == ""


class TestHTTPServerErrors:
    """Tests for HTTP error responses."""

    def test_empty_body_returns_error(self, client: httpx.Client) -> None:
        """Test that empty request body returns error."""
        response = client.post(
            "/",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["data"]["name"] == "BAD_REQUEST"

    def test_json_array_rejected(self, client: httpx.Client) -> None:
        """Test that JSON array body is rejected (must be object)."""
        response = client.post(
            "/",
            json=["array", "of", "values"],
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["data"]["name"] == "BAD_REQUEST"

    def test_json_string_rejected(self, client: httpx.Client) -> None:
        """Test that JSON string body is rejected (must be object)."""
        response = client.post(
            "/",
            content=b'"just a string"',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["data"]["name"] == "BAD_REQUEST"

    def test_connection_close_header(self, client: httpx.Client) -> None:
        """Test that responses include Connection: close header."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": 1,
            },
        )
        assert response.status_code == 200
        assert response.headers.get("Connection", "").lower() == "close"

    def test_content_type_is_json(self, client: httpx.Client) -> None:
        """Test that responses have application/json content type."""
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": 1,
            },
        )
        assert response.status_code == 200
        assert "application/json" in response.headers["Content-Type"]


class TestHTTPServerSequentialRequests:
    """Tests for sequential HTTP request handling."""

    def test_multiple_sequential_requests(self, client: httpx.Client) -> None:
        """Test handling multiple sequential requests."""
        for i in range(5):
            response = client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "method": "health",
                    "params": {},
                    "id": i,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert "result" in data
            assert data["id"] == i

    def test_different_endpoints_sequentially(self, client: httpx.Client) -> None:
        """Test accessing different endpoints sequentially."""
        # POST - health
        response1 = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": 1,
            },
        )
        assert response1.status_code == 200

        # POST - rpc.discover
        response2 = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "rpc.discover",
                "params": {},
                "id": 2,
            },
        )
        assert response2.status_code == 200
        assert "result" in response2.json()

        # OPTIONS (now returns 405)
        response3 = client.options("/")
        assert response3.status_code == 405

        # POST again
        response4 = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "method": "health",
                "params": {},
                "id": 3,
            },
        )
        assert response4.status_code == 200


class TestHTTPServerConcurrency:
    """Tests for concurrent request handling."""

    def test_concurrent_requests_do_not_crash(
        self, instance, balatro_server, client: httpx.Client
    ) -> None:
        """Two concurrent requests must not crash the server (#193)."""
        barrier = threading.Barrier(2)
        results: dict[str, bytes] = {}

        def raw_post(method: str, rid: int, key: str) -> None:
            body = json.dumps(
                {"jsonrpc": "2.0", "method": method, "params": {}, "id": rid}
            )
            req = (
                f"POST / HTTP/1.1\r\nHost: {instance.host}:{instance.port}\r\n"
                f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n{body}"
            )
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10)
                try:
                    s.connect((instance.host, instance.port))
                    barrier.wait(timeout=5)
                    s.sendall(req.encode())
                    chunks = b""
                    while True:
                        try:
                            chunk = s.recv(4096)
                        except socket.timeout:
                            break
                        if not chunk:
                            break
                        chunks += chunk
                    results[key] = chunks
                except OSError as e:
                    results[key] = str(e).encode()

        t1 = threading.Thread(target=raw_post, args=("menu", 1, "r1"))
        t2 = threading.Thread(target=raw_post, args=("health", 2, "r2"))
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        # Both must get HTTP responses, not connection errors
        for key, raw in results.items():
            assert raw.startswith(b"HTTP/"), f"{key}: got {raw!r}"

        # Server must still be alive
        resp = client.post(
            "/", json={"jsonrpc": "2.0", "method": "health", "params": {}, "id": 3}
        )
        assert resp.json()["result"]["status"] == "ok"
