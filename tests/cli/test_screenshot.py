"""Integration test for the screenshot logging feature (requires Balatro)."""

import asyncio
import os
import random
from pathlib import Path

import httpx
import pytest

from balatrobot import BalatroInstance

HEADLESS = os.getenv("BALATROBOT_RENDER") == "headless"


def _random_port() -> int:
    """Get a random port in the test range."""
    return random.randint(20000, 30000)


@pytest.mark.skipif(HEADLESS, reason="Screenshot logging requires rendering")
@pytest.mark.parametrize("render", ["headfull", "ondemand"])
@pytest.mark.asyncio
async def test_screenshot_written_after_success(tmp_path: Path, render: str) -> None:
    """A successful API call writes <port>/<id>.png under the logs dir."""
    async with BalatroInstance(
        port=_random_port(),
        render=render,
        screenshots=True,
        path_logs=str(tmp_path),
    ) as instance:
        url = f"http://127.0.0.1:{instance.port}"
        payload = {"jsonrpc": "2.0", "method": "menu", "params": {}, "id": 1}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
        assert resp.json().get("result", {}).get("state") == "MENU"

        # PNG write happens asynchronously on the next frame; poll for it.
        png = None
        for _ in range(50):
            matches = list(tmp_path.glob(f"*/{instance.port}/*.png"))
            if matches:
                png = matches[0]
                break
            await asyncio.sleep(0.1)

        assert png is not None, f"No screenshot written under {tmp_path}"
        assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
