"""Integration test for the screenshot logging feature (requires Balatro)."""

import asyncio
import os
import random
import time
from pathlib import Path

import httpx
import pytest

from balatrobot import BalatroInstance

HEADLESS = os.getenv("BALATROBOT_RENDER") == "headless"

# Above the 15 s quiescence deadman so a hung call still returns (and fails the
# timing assertion below) rather than raising httpx.TimeoutException.
REQUEST_TIMEOUT = 20.0
# A passing call must settle well under the deadman; this catches the regression
# where quiescence never resolves and the call deadmans at 15 s.
MAX_SETTLE_SECONDS = 6.0


def _random_port() -> int:
    """Get a random port in the test range."""
    return random.randint(20000, 30000)


@pytest.mark.skipif(HEADLESS, reason="Screenshot logging requires rendering")
@pytest.mark.parametrize("render", ["headfull", "ondemand"])
@pytest.mark.asyncio
async def test_screenshot_written_after_success(tmp_path: Path, render: str) -> None:
    """A successful API call waits for the frame to settle, then writes a PNG.

    The response is delayed until the screen is quiescent (ADR 0003), so a
    passing call completes well under the deadman — proving settling works.
    """
    async with BalatroInstance(
        port=_random_port(),
        render=render,
        screenshots=True,
        logs=str(tmp_path),
    ) as instance:
        url = f"http://127.0.0.1:{instance.port}"
        payload = {"jsonrpc": "2.0", "method": "menu", "params": {}, "id": 1}

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            start = time.monotonic()
            resp = await client.post(url, json=payload)
            elapsed = time.monotonic() - start
        assert resp.json().get("result", {}).get("state") == "MENU"
        assert elapsed < MAX_SETTLE_SECONDS, (
            f"Response took {elapsed:.1f}s — quiescence likely deadmanned"
        )

        # PNG write happens asynchronously on the next frame; poll for it.
        png = None
        for _ in range(50):
            matches = list(tmp_path.glob(f"*/{instance.port}/screenshots/*.png"))
            if matches:
                png = matches[0]
                break
            await asyncio.sleep(0.1)

        assert png is not None, f"No screenshot written under {tmp_path}"
        assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
