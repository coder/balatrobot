"""Tests for src/lua/endpoints/play.lua"""

import httpx

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


class TestPlayEndpoint:
    """Test basic play endpoint functionality."""

    def test_play_zero_cards(self, client: httpx.Client) -> None:
        """Test play endpoint from BLIND_SELECT state."""
        gamestate = load_fixture(client, "play", "state-SELECTING_HAND")
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "play", {"cards": []}),
            "BAD_REQUEST",
            "Must provide at least one card to play",
        )

    def test_play_six_cards(self, client: httpx.Client) -> None:
        """Test play endpoint from BLIND_SELECT state."""
        gamestate = load_fixture(client, "play", "state-SELECTING_HAND")
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "play", {"cards": [0, 1, 2, 3, 4, 5]}),
            "BAD_REQUEST",
            "You can only play 5 cards",
        )

    def test_play_out_of_range_cards(self, client: httpx.Client) -> None:
        """Test play endpoint from BLIND_SELECT state."""
        gamestate = load_fixture(client, "play", "state-SELECTING_HAND")
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "play", {"cards": [999]}),
            "BAD_REQUEST",
            "Invalid card index: 999",
        )

    def test_play_valid_cards_and_round_active(self, client: httpx.Client) -> None:
        """Test play endpoint from BLIND_SELECT state."""
        gamestate = load_fixture(client, "play", "state-SELECTING_HAND")
        assert gamestate["state"] == "SELECTING_HAND"
        response = api(client, "play", {"cards": [0, 3, 4, 5, 6]})
        gamestate = assert_gamestate_response(response, state="SELECTING_HAND")
        assert gamestate["hands"]["Flush"]["played_this_round"] == 1
        assert gamestate["round"]["chips"] == 260

    def test_play_valid_cards_and_round_won(self, client: httpx.Client) -> None:
        """Test play endpoint from BLIND_SELECT state."""
        gamestate = load_fixture(
            client, "play", "state-SELECTING_HAND--round.chips-200"
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["round"]["chips"] == 200
        response = api(client, "play", {"cards": [0, 3, 4, 5, 6]})
        assert_gamestate_response(response, state="ROUND_EVAL")

    def test_play_valid_cards_and_game_won(self, client: httpx.Client) -> None:
        """Test play endpoint from BLIND_SELECT state."""
        gamestate = load_fixture(
            client,
            "play",
            "state-SELECTING_HAND--ante_num-8--blinds.boss.status-CURRENT--round.chips-1000000",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["ante_num"] == 8
        assert gamestate["blinds"]["boss"]["status"] == "CURRENT"
        assert gamestate["round"]["chips"] == 1000000
        response = api(client, "play", {"cards": [0, 3, 4, 5, 6]})
        assert_gamestate_response(response, won=True)

    def test_play_valid_cards_and_game_over(self, client: httpx.Client) -> None:
        """Test play endpoint from BLIND_SELECT state."""
        gamestate = load_fixture(
            client, "play", "state-SELECTING_HAND--round.hands_left-1"
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["round"]["hands_left"] == 1
        response = api(client, "play", {"cards": [0]}, timeout=5)
        assert_gamestate_response(response, state="GAME_OVER")


class TestPlayEndpointValidation:
    """Test play endpoint parameter validation."""

    def test_missing_cards_parameter(self, client: httpx.Client):
        """Test that play fails when cards parameter is missing."""
        gamestate = load_fixture(client, "play", "state-SELECTING_HAND")
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "play", {}),
            "BAD_REQUEST",
            "Missing required field 'cards'",
        )

    def test_invalid_cards_type(self, client: httpx.Client):
        """Test that play fails when cards parameter is not an array."""
        gamestate = load_fixture(client, "play", "state-SELECTING_HAND")
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "play", {"cards": "INVALID_CARDS"}),
            "BAD_REQUEST",
            "Field 'cards' must be an array",
        )

    def test_cerulean_bell_forced_card_not_included_in_play(
        self, client: httpx.Client
    ) -> None:
        """Play a single non-forced card; the forced card must NOT be included."""

        prev_gs = load_fixture(
            client, "play", "state-SELECTING_HAND--blinds.boss.key-bl_final_bell"
        )
        assert prev_gs["blinds"]["boss"]["key"] == "bl_final_bell"

        # Find the forced card (highlighted by The Bell)
        h_idx, h_card = None, None
        for i, c in enumerate(prev_gs["hand"]["cards"]):
            if isinstance(c["state"], dict) and c["state"]["highlight"]:
                h_idx = i
                h_card = c
                break
        assert h_card is not None, "The Bell should force exactly one card"
        assert h_idx is not None, "The Bell should force exactly one card"

        # Select another card to play, this should raise an error in the API.
        response = api(client, "play", {"cards": [1 if h_idx == 0 else 0]})
        assert_error_response(
            response,
            "BAD_REQUEST",
            "forced-selected by the boss blind",
        )


class TestPlayEndpointStateRequirements:
    """Test play endpoint state requirements."""

    def test_play_from_BLIND_SELECT(self, client: httpx.Client):
        """Test that play fails when not in SELECTING_HAND state."""
        gamestate = load_fixture(client, "play", "state-BLIND_SELECT")
        assert gamestate["state"] == "BLIND_SELECT"
        assert_error_response(
            api(client, "play", {"cards": [0]}),
            "INVALID_STATE",
            "Method 'play' requires one of these states: SELECTING_HAND",
        )
