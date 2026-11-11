"""Tests for src/lua/endpoints/screenshot.lua"""

import os
from pathlib import Path

import httpx
import pytest

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    assert_path_response,
    load_fixture,
)

HEADLESS = os.getenv("BALATROBOT_RENDER") == "headless"


@pytest.mark.skipif(
    HEADLESS, reason="Screenshot endpoint does not work in headless mode"
)
class TestScreenshotEndpoint:
    """Test basic screenshot endpoint functionality."""

    def test_screenshot_from_MENU(self, client: httpx.Client, tmp_path: Path) -> None:
        """Test that screenshot succeeds from MENU state."""
        gamestate = api(client, "menu", {})
        assert_gamestate_response(gamestate, state="MENU")
        temp_file = tmp_path / "screenshot.png"
        response = api(client, "screenshot", {"path": str(temp_file)})
        assert_path_response(response)
        assert response["result"]["path"] == str(temp_file)
        assert temp_file.exists()
        assert temp_file.stat().st_size > 0
        assert temp_file.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    def test_screenshot_from_BLIND_SELECT(
        self, client: httpx.Client, tmp_path: Path
    ) -> None:
        """Test that screenshot succeeds from BLIND_SELECT state."""
        gamestate = load_fixture(client, "screenshot", "state-BLIND_SELECT")
        assert gamestate["state"] == "BLIND_SELECT"
        temp_file = tmp_path / "screenshot.png"
        response = api(client, "screenshot", {"path": str(temp_file)})
        assert_path_response(response)
        assert response["result"]["path"] == str(temp_file)
        assert temp_file.exists()
        assert temp_file.stat().st_size > 0
        assert temp_file.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


class TestScreenshotValidation:
    """Test screenshot endpoint parameter validation."""

    def test_missing_path_parameter(self, client: httpx.Client) -> None:
        """Test that screenshot fails when path parameter is missing."""
        response = api(client, "screenshot", {})
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Missing required field 'path'",
        )

    def test_invalid_path_type(self, client: httpx.Client) -> None:
        """Test that screenshot fails when path is not a string."""
        response = api(client, "screenshot", {"path": 123})
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Field 'path' must be of type string",
        )
