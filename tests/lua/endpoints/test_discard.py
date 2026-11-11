"""Tests for src/lua/endpoints/discard.lua"""

import httpx

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


class TestDiscardEndpoint:
    """Test basic discard endpoint functionality."""

    def test_discard_zero_cards(self, client: httpx.Client) -> None:
        """Test discard endpoint with empty cards array."""
        gamestate = load_fixture(client, "discard", "state-SELECTING_HAND")
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "discard", {"cards": []}),
            "BAD_REQUEST",
            "Must provide at least one card to discard",
        )

    def test_discard_too_many_cards(self, client: httpx.Client) -> None:
        """Test discard endpoint with more cards than limit."""
        gamestate = load_fixture(client, "discard", "state-SELECTING_HAND")
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "discard", {"cards": [0, 1, 2, 3, 4, 5]}),
            "BAD_REQUEST",
            "You can only discard 5 cards",
        )

    def test_discard_out_of_range_cards(self, client: httpx.Client) -> None:
        """Test discard endpoint with invalid card index."""
        gamestate = load_fixture(client, "discard", "state-SELECTING_HAND")
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "discard", {"cards": [999]}),
            "BAD_REQUEST",
            "Invalid card index: 999",
        )

    def test_discard_no_discards_left(self, client: httpx.Client) -> None:
        """Test discard endpoint when no discards remain."""
        gamestate = load_fixture(
            client, "discard", "state-SELECTING_HAND--round.discards_left-0"
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["round"]["discards_left"] == 0
        assert_error_response(
            api(client, "discard", {"cards": [0]}),
            "BAD_REQUEST",
            "No discards left",
        )

    def test_discard_valid_single_card(self, client: httpx.Client) -> None:
        """Test discard endpoint with valid single card."""
        before = load_fixture(client, "discard", "state-SELECTING_HAND")
        assert before["state"] == "SELECTING_HAND"
        response = api(client, "discard", {"cards": [0]})
        after = assert_gamestate_response(response, state="SELECTING_HAND")
        assert after["round"]["discards_left"] == before["round"]["discards_left"] - 1

    def test_discard_valid_multiple_cards(self, client: httpx.Client) -> None:
        """Test discard endpoint with valid multiple cards."""
        before = load_fixture(client, "discard", "state-SELECTING_HAND")
        assert before["state"] == "SELECTING_HAND"
        response = api(client, "discard", {"cards": [1, 2, 3]})
        after = assert_gamestate_response(response, state="SELECTING_HAND")
        assert after["round"]["discards_left"] == before["round"]["discards_left"] - 1


class TestDiscardEndpointValidation:
    """Test discard endpoint parameter validation."""

    def test_missing_cards_parameter(self, client: httpx.Client):
        """Test that discard fails when cards parameter is missing."""
        gamestate = load_fixture(client, "discard", "state-SELECTING_HAND")
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "discard", {}),
            "BAD_REQUEST",
            "Missing required field 'cards'",
        )

    def test_invalid_cards_type(self, client: httpx.Client):
        """Test that discard fails when cards parameter is not an array."""
        gamestate = load_fixture(client, "discard", "state-SELECTING_HAND")
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "discard", {"cards": "INVALID_CARDS"}),
            "BAD_REQUEST",
            "Field 'cards' must be an array",
        )

    def test_cerulean_bell_forced_card_not_included_in_discard(
        self, client: httpx.Client
    ) -> None:
        """Discard a single non-forced card; the forced card must NOT be silently included."""

        prev_gs = load_fixture(
            client, "discard", "state-SELECTING_HAND--blinds.boss.key-bl_final_bell"
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

        # Select another card to discard, this should raise an error in the API.
        response = api(client, "discard", {"cards": [1 if h_idx == 0 else 0]})
        assert_error_response(
            response,
            "BAD_REQUEST",
            "forced-selected by the boss blind",
        )


class TestDiscardEndpointStateRequirements:
    """Test discard endpoint state requirements."""

    def test_discard_from_BLIND_SELECT(self, client: httpx.Client):
        """Test that discard fails when not in SELECTING_HAND state."""
        gamestate = load_fixture(client, "discard", "state-BLIND_SELECT")
        assert gamestate["state"] == "BLIND_SELECT"
        assert_error_response(
            api(client, "discard", {"cards": [0]}),
            "INVALID_STATE",
            "Method 'discard' requires one of these states: SELECTING_HAND",
        )
