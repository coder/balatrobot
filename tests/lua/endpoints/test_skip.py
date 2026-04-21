"""Tests for src/lua/endpoints/skip.lua"""

import httpx

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


class TestSkipEndpoint:
    """Test basic skip endpoint functionality."""

    def test_skip_small_blind(self, client: httpx.Client) -> None:
        """Test skipping Small blind in BLIND_SELECT state."""
        gamestate = load_fixture(
            client, "skip", "state-BLIND_SELECT--blinds.small.status-SELECT"
        )
        assert gamestate["state"] == "BLIND_SELECT"
        assert gamestate["blinds"]["small"]["status"] == "SELECT"
        response = api(client, "skip", {})
        gamestate = assert_gamestate_response(response, state="BLIND_SELECT")
        assert gamestate["blinds"]["small"]["status"] == "SKIPPED"
        assert gamestate["blinds"]["big"]["status"] == "SELECT"

    def test_skip_big_blind(self, client: httpx.Client) -> None:
        """Test skipping Big blind in BLIND_SELECT state."""
        gamestate = load_fixture(
            client, "skip", "state-BLIND_SELECT--blinds.big.status-SELECT"
        )
        assert gamestate["state"] == "BLIND_SELECT"
        assert gamestate["blinds"]["big"]["status"] == "SELECT"
        response = api(client, "skip", {})
        gamestate = assert_gamestate_response(response, state="BLIND_SELECT")
        assert gamestate["blinds"]["big"]["status"] == "SKIPPED"
        assert gamestate["blinds"]["boss"]["status"] == "SELECT"

    def test_skip_big_boss(self, client: httpx.Client) -> None:
        """Test skipping Boss in BLIND_SELECT state."""
        gamestate = load_fixture(
            client, "skip", "state-BLIND_SELECT--blinds.boss.status-SELECT"
        )
        assert gamestate["state"] == "BLIND_SELECT"
        assert gamestate["blinds"]["boss"]["status"] == "SELECT"
        assert_error_response(
            api(client, "skip", {}),
            "NOT_ALLOWED",
            "Cannot skip Boss blind",
        )


class TestSkipEndpointStateRequirements:
    """Test skip endpoint state requirements."""

    def test_skip_from_MENU(self, client: httpx.Client):
        """Test that skip fails when not in BLIND_SELECT state."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        assert_error_response(
            api(client, "skip", {}),
            "INVALID_STATE",
            "Method 'skip' requires one of these states: BLIND_SELECT",
        )
