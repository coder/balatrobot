"""Integration tests for BalatroClient."""

import httpx
import pytest

from balatrobot.cli.client import APIError, BalatroClient


class TestBalatroClient:
    """Test BalatroClient.call() against real Balatro server."""

    def test_health_call_returns_result(self, balatro_client: BalatroClient):
        """Health endpoint returns result dict."""
        result = balatro_client.call("health")
        assert result["status"] == "ok"

    def test_gamestate_call_returns_state(self, balatro_client: BalatroClient):
        """Gamestate returns current state."""
        # Reset to menu first
        balatro_client.call("menu")
        result = balatro_client.call("gamestate")
        assert "state" in result

    def test_api_error_raised_on_invalid_state(self, balatro_client: BalatroClient):
        """APIError raised when action invalid for current state."""
        balatro_client.call("menu")  # Ensure MENU state
        with pytest.raises(APIError) as exc_info:
            balatro_client.call("play", {"cards": [0]})
        assert exc_info.value.name == "INVALID_STATE"
        assert exc_info.value.code == -32002

    def test_api_error_raised_on_bad_params(self, balatro_client: BalatroClient):
        """APIError raised on schema validation failure."""
        with pytest.raises(APIError) as exc_info:
            balatro_client.call("start", {"invalid_param": "value"})
        assert exc_info.value.name == "BAD_REQUEST"

    def test_request_id_increments(self, balatro_client: BalatroClient):
        """Request ID increments with each call."""
        assert balatro_client._request_id == 0
        balatro_client.call("health")
        assert balatro_client._request_id == 1
        balatro_client.call("health")
        assert balatro_client._request_id == 2

    def test_url_property(self):
        """URL property formats correctly."""
        client = BalatroClient(host="example.com", port=9999)
        assert client.url == "http://example.com:9999"

    def test_connection_error_on_bad_port(self):
        """httpx.ConnectError raised when server not available."""
        client = BalatroClient(host="127.0.0.1", port=1, timeout=1.0)
        with pytest.raises(httpx.ConnectError):
            client.call("health")

    def test_http_client_built_once(self, monkeypatch):
        """Every call reuses one httpx.Client."""
        from balatrobot.cli import client as client_module

        built = []
        real_client = httpx.Client

        def counting_client(**kwargs):
            built.append(kwargs)
            transport = httpx.MockTransport(
                lambda request: httpx.Response(200, json={"jsonrpc": "2.0", "result": {"status": "ok"}, "id": 1})
            )
            return real_client(transport=transport, **kwargs)

        monkeypatch.setattr(client_module.httpx, "Client", counting_client)
        client = BalatroClient()
        for _ in range(3):
            assert client.call("health") == {"status": "ok"}
        assert len(built) == 1
        client.close()
        assert client._http is None
