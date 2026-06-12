"""Tests for the start endpoint."""

from typing import Any

import httpx
import pytest

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


class TestStartEndpoint:
    """Parametrized tests for the start endpoint."""

    @pytest.mark.parametrize(
        "arguments,expected",
        [
            # Test basic start with b_red deck and stake_white stake
            (
                {"deck": "b_red", "stake": "stake_white"},
                {
                    "state": "BLIND_SELECT",
                    "deck": "b_red",
                    "stake": "stake_white",
                    "ante_num": 1,
                    "round_num": 0,
                },
            ),
            # Test with b_blue deck
            (
                {"deck": "b_blue", "stake": "stake_white"},
                {
                    "state": "BLIND_SELECT",
                    "deck": "b_blue",
                    "stake": "stake_white",
                    "ante_num": 1,
                    "round_num": 0,
                },
            ),
            # Test with higher stake (stake_black)
            (
                {"deck": "b_red", "stake": "stake_black"},
                {
                    "state": "BLIND_SELECT",
                    "deck": "b_red",
                    "stake": "stake_black",
                    "ante_num": 1,
                    "round_num": 0,
                },
            ),
            # Test with seed
            (
                {"deck": "b_red", "stake": "stake_white", "seed": "TEST123"},
                {
                    "state": "BLIND_SELECT",
                    "deck": "b_red",
                    "stake": "stake_white",
                    "ante_num": 1,
                    "round_num": 0,
                    "seed": "TEST123",
                },
            ),
        ],
    )
    def test_start_from_MENU(
        self,
        client: httpx.Client,
        arguments: dict[str, Any],
        expected: dict[str, Any],
    ):
        """Test start endpoint with various valid parameters."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(client, "start", arguments)
        assert_gamestate_response(response, **expected)


class TestStartEndpointValidation:
    """Test start endpoint parameter validation."""

    def test_missing_deck_parameter(self, client: httpx.Client):
        """Test that start fails when deck parameter is missing."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(client, "start", {"stake": "stake_white"})
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Missing required field 'deck'",
        )

    def test_missing_stake_parameter(self, client: httpx.Client):
        """Test that start fails when stake parameter is missing."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(client, "start", {"deck": "b_red"})
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Missing required field 'stake'",
        )

    def test_invalid_deck_value(self, client: httpx.Client):
        """Test that start fails with invalid deck key."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(
            client, "start", {"deck": "INVALID_DECK", "stake": "stake_white"}
        )
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Expected a b_* deck key from G.P_CENTERS",
        )

    def test_invalid_stake_value(self, client: httpx.Client):
        """Test that start fails when invalid stake enum is provided."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(client, "start", {"deck": "b_red", "stake": "INVALID_STAKE"})
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Expected a stake_* key from G.P_STAKES",
        )

    def test_invalid_deck_type(self, client: httpx.Client):
        """Test that start fails when deck is not a string."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(client, "start", {"deck": 123, "stake": "stake_white"})
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Field 'deck' must be of type string",
        )

    def test_invalid_stake_type(self, client: httpx.Client):
        """Test that start fails when stake is not a string."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(client, "start", {"deck": "b_red", "stake": 1})
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Field 'stake' must be of type string",
        )


class TestStartEndpointStateRequirements:
    """Test start endpoint state requirements."""

    def test_start_from_BLIND_SELECT(self, client: httpx.Client):
        """Test that start fails when not in MENU state."""
        gamestate = load_fixture(client, "start", "state-BLIND_SELECT")
        assert gamestate["state"] == "BLIND_SELECT"
        response = api(client, "start", {"deck": "b_red", "stake": "stake_white"})
        assert_error_response(
            response,
            "INVALID_STATE",
            "Method 'start' requires one of these states: MENU",
        )
