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


class TestStartChallenge:
    """Tests for the challenge-run branch of the start endpoint.

    Challenges are Balatro's 20 fixed-preset runs. The `challenge` param is
    mutually exclusive with `deck`/`stake` but composes freely with `seed`.
    """

    @pytest.mark.parametrize(
        "challenge_id",
        [
            "c_omelette_1",
            "c_jokerless_1",
            "c_mad_world_1",
        ],
    )
    def test_start_challenge_happy_path(self, client: httpx.Client, challenge_id: str):
        """A challenge run lands in BLIND_SELECT under the b_challenge deck."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(client, "start", {"challenge": challenge_id})
        assert_gamestate_response(
            response,
            state="BLIND_SELECT",
            challenge=challenge_id,
            deck="b_challenge",
            stake="stake_white",
        )

    def test_start_challenge_with_seed(self, client: httpx.Client):
        """challenge composes freely with seed."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(
            client, "start", {"challenge": "c_omelette_1", "seed": "TEST123"}
        )
        assert_gamestate_response(
            response,
            state="BLIND_SELECT",
            challenge="c_omelette_1",
            seed="TEST123",
        )

    def test_start_challenge_effect_applied(self, client: httpx.Client):
        """Deep check: The Omelette starts with 5 Eggs — proves the challenge
        actually took effect, not just the challenge flag."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(client, "start", {"challenge": "c_omelette_1"})
        gamestate = assert_gamestate_response(response, state="BLIND_SELECT")
        assert gamestate["jokers"]["count"] == 5
        assert {c["key"] for c in gamestate["jokers"]["cards"]} == {"j_egg"}

    def test_start_challenge_conflict_with_deck(self, client: httpx.Client):
        """challenge cannot be combined with deck."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(
            client,
            "start",
            {"challenge": "c_omelette_1", "deck": "b_red"},
        )
        assert_error_response(response, "BAD_REQUEST", "cannot be combined")

    def test_start_challenge_conflict_with_stake(self, client: httpx.Client):
        """challenge cannot be combined with stake."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(
            client,
            "start",
            {"challenge": "c_omelette_1", "stake": "stake_white"},
        )
        assert_error_response(response, "BAD_REQUEST", "cannot be combined")

    def test_start_challenge_conflict_with_both(self, client: httpx.Client):
        """challenge cannot be combined with deck and stake together."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(
            client,
            "start",
            {
                "challenge": "c_omelette_1",
                "deck": "b_red",
                "stake": "stake_white",
            },
        )
        assert_error_response(response, "BAD_REQUEST", "cannot be combined")

    def test_start_challenge_invalid_id(self, client: httpx.Client):
        """An unknown challenge id is rejected against live G.CHALLENGES."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(client, "start", {"challenge": "c_nope_1"})
        assert_error_response(response, "BAD_REQUEST", "Expected a c_* challenge id")

    def test_start_challenge_wrong_type(self, client: httpx.Client):
        """challenge must be a string (schema-level type check)."""
        response = api(client, "menu", {})
        assert_gamestate_response(response, state="MENU")
        response = api(client, "start", {"challenge": 123})
        assert_error_response(response, "BAD_REQUEST", "must be of type string")
