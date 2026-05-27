"""Integration tests for balatrobot (requires actual Balatro game)."""

import random

import httpx
import pytest

from balatrobot import BalatroInstance


def _random_port() -> int:
    """Get a random port in the test range."""
    return random.randint(20000, 30000)


class TestBalatroIntegration:
    """Integration tests that require a running Balatro instance."""

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self, tmp_path):
        """Context manager starts and stops Balatro properly."""
        async with BalatroInstance(
            port=_random_port(), fast=True, headless=True, logs_path=str(tmp_path)
        ) as instance:
            # Instance should be running
            assert instance.process is not None
            assert instance.process.pid > 0

            # Health check should work
            url = f"http://127.0.0.1:{instance.port}"
            payload = {"jsonrpc": "2.0", "method": "health", "params": {}, "id": 1}

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=payload)
                data = response.json()

            assert data["result"]["status"] == "ok"

        # After exit, process should be terminated
        # (instance._process is None, but we can't check returncode easily)

    @pytest.mark.asyncio
    async def test_health_endpoint_responds(self, tmp_path):
        """Health endpoint returns valid JSON-RPC response."""
        async with BalatroInstance(
            port=_random_port(), fast=True, headless=True, logs_path=str(tmp_path)
        ) as instance:
            url = f"http://127.0.0.1:{instance.port}"
            payload = {"jsonrpc": "2.0", "method": "health", "params": {}, "id": 42}

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=payload)

            assert response.status_code == 200

            data = response.json()
            assert "result" in data
            assert data["result"]["status"] == "ok"
