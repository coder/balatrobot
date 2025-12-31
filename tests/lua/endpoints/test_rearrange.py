"""Tests for src/lua/endpoints/rearrange.lua"""

import httpx
import pytest

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


class TestRearrangeHandInSelectingHandState:
    """Test rearranging hand in SELECTING_HAND state."""

    def test_rearrange_hand(self, client: httpx.Client) -> None:
        """Test rearranging hand in selecting hand state."""
        before = load_fixture(client, "rearrange", "state-SELECTING_HAND--hand.count-8")
        assert before["state"] == "SELECTING_HAND"
        assert before["hand"]["count"] == 8
        prev_ids = [card["id"] for card in before["hand"]["cards"]]
        permutation = [1, 2, 0, 3, 4, 5, 7, 6]
        response = api(
            client,
            "rearrange",
            {"hand": permutation},
        )
        after = assert_gamestate_response(response)
        ids = [card["id"] for card in after["hand"]["cards"]]
        assert ids == [prev_ids[i] for i in permutation]


class TestRearrangeInShopState:
    """Test rearranging cards in SHOP state."""

    def test_rearrange_jokers(self, client: httpx.Client) -> None:
        """Test rearranging jokers in shop."""
        before = load_fixture(
            client, "rearrange", "state-SHOP--jokers.count-4--consumables.count-2"
        )
        assert before["state"] == "SHOP"
        assert before["jokers"]["count"] == 4
        prev_ids = [card["id"] for card in before["jokers"]["cards"]]
        permutation = [2, 0, 1, 3]
        response = api(
            client,
            "rearrange",
            {"jokers": permutation},
        )
        after = assert_gamestate_response(response)
        ids = [card["id"] for card in after["jokers"]["cards"]]
        assert ids == [prev_ids[i] for i in permutation]

    def test_rearrange_consumables(self, client: httpx.Client) -> None:
        """Test rearranging consumables in shop."""
        before = load_fixture(
            client, "rearrange", "state-SHOP--jokers.count-4--consumables.count-2"
        )
        assert before["state"] == "SHOP"
        assert before["consumables"]["count"] == 2
        prev_ids = [card["id"] for card in before["consumables"]["cards"]]
        permutation = [1, 0]
        response = api(
            client,
            "rearrange",
            {"consumables": permutation},
        )
        after = assert_gamestate_response(response)
        ids = [card["id"] for card in after["consumables"]["cards"]]
        assert ids == [prev_ids[i] for i in permutation]

    def test_rearrange_hand_from_shop_fails(self, client: httpx.Client) -> None:
        """Test that rearranging hand fails in SHOP state."""
        gamestate = load_fixture(
            client, "rearrange", "state-SHOP--jokers.count-4--consumables.count-2"
        )
        assert gamestate["state"] == "SHOP"
        assert_error_response(
            api(client, "rearrange", {"hand": [0, 1, 2, 3, 4, 5, 6, 7]}),
            "INVALID_STATE",
            "Can only rearrange hand during hand selection",
        )


class TestRearrangeHandInPackState:
    """Test rearranging cards while in SMODS_BOOSTER_OPENED state."""

    @pytest.mark.parametrize(
        "pack_key",
        ("p_arcana_normal_1", "p_spectral_normal_1"),
    )
    def test_rearrange_hand_in_arcana_or_spectral_pack(
        self, client: httpx.Client, pack_key: str
    ) -> None:
        """Test rearranging hand in Arcana/Spectral pack (which shows hand)."""
        load_fixture(client, "rearrange", "state-SHOP--packs.count-0")
        api(client, "add", {"key": pack_key})
        response = api(client, "buy", {"pack": 0})
        before = assert_gamestate_response(response)
        assert before["state"] == "SMODS_BOOSTER_OPENED"
        assert before["hand"]["count"] >= 0

        prev_ids = [card["id"] for card in before["hand"]["cards"]]
        permutation = list(range(before["hand"]["count"]))
        permutation[0], permutation[1] = permutation[1], permutation[0]

        response = api(client, "rearrange", {"hand": permutation})
        after = assert_gamestate_response(response)
        assert after["state"] == "SMODS_BOOSTER_OPENED"
        ids = [card["id"] for card in after["hand"]["cards"]]
        assert ids == [prev_ids[i] for i in permutation]

    @pytest.mark.parametrize(
        "pack_key",
        ("p_buffoon_normal_1", "p_celestial_normal_1", "p_standard_normal_1"),
    )
    def test_rearrange_hand_in_non_arcana_or_non_spectral_pack_fails(
        self, client: httpx.Client, pack_key: str
    ) -> None:
        """Test rearranging hand fails in Buffoon pack (no hand visible)."""
        load_fixture(client, "rearrange", "state-SHOP--packs.count-0")
        api(client, "add", {"key": pack_key})
        response = api(client, "buy", {"pack": 0})
        before = assert_gamestate_response(response)
        assert before["state"] == "SMODS_BOOSTER_OPENED"

        response = api(client, "rearrange", {"hand": [0, 1, 2, 3, 4, 5, 6, 7]})
        assert_error_response(
            response,
            "NOT_ALLOWED",
            "No cards to rearrange. You can only rearrange hand in Arcana and Spectral packs.",
        )

    def test_rearrange_jokers_in_pack_state(self, client: httpx.Client) -> None:
        """Test rearranging jokers while a booster pack is open."""
        load_fixture(client, "rearrange", "state-SHOP--packs.count-0")
        api(client, "add", {"key": "j_joker"})
        api(client, "add", {"key": "j_greedy_joker"})
        api(client, "add", {"key": "p_arcana_normal_1"})

        response = api(client, "buy", {"pack": 0})
        before = assert_gamestate_response(response)
        assert before["state"] == "SMODS_BOOSTER_OPENED"
        assert before["jokers"]["count"] == 2

        prev_ids = [card["id"] for card in before["jokers"]["cards"]]
        response = api(client, "rearrange", {"jokers": [1, 0]})
        after = assert_gamestate_response(response)
        assert after["state"] == "SMODS_BOOSTER_OPENED"
        ids = [card["id"] for card in after["jokers"]["cards"]]
        assert ids == [prev_ids[1], prev_ids[0]]

    def test_rearrange_consumables_in_pack_state(self, client: httpx.Client) -> None:
        """Test rearranging consumables while a booster pack is open."""
        load_fixture(client, "rearrange", "state-SHOP--packs.count-0")
        api(client, "add", {"key": "c_fool"})
        api(client, "add", {"key": "c_magician"})
        api(client, "add", {"key": "p_arcana_normal_1"})

        response = api(client, "buy", {"pack": 0})
        before = assert_gamestate_response(response)
        assert before["state"] == "SMODS_BOOSTER_OPENED"
        assert before["consumables"]["count"] == 2

        prev_ids = [card["id"] for card in before["consumables"]["cards"]]
        response = api(client, "rearrange", {"consumables": [1, 0]})
        after = assert_gamestate_response(response)
        assert after["state"] == "SMODS_BOOSTER_OPENED"
        ids = [card["id"] for card in after["consumables"]["cards"]]
        assert ids == [prev_ids[1], prev_ids[0]]


class TestRearrangeEndpointValidation:
    """Test rearrange endpoint parameter validation."""

    def test_no_parameters_provided(self, client: httpx.Client) -> None:
        """Test error when no rearrange type specified."""
        gamestate = load_fixture(
            client, "rearrange", "state-SELECTING_HAND--hand.count-8"
        )
        assert gamestate["state"] == "SELECTING_HAND"
        response = api(client, "rearrange", {})
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Must provide exactly one of: hand, jokers, or consumables",
        )

    def test_multiple_parameters_provided(self, client: httpx.Client) -> None:
        """Test error when multiple rearrange types specified."""
        gamestate = load_fixture(
            client, "rearrange", "state-SELECTING_HAND--hand.count-8"
        )
        assert gamestate["state"] == "SELECTING_HAND"
        response = api(
            client, "rearrange", {"hand": [], "jokers": [], "consumables": []}
        )
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Can only rearrange one type at a time",
        )

    def test_wrong_array_length_hand(self, client: httpx.Client) -> None:
        """Test error when hand array wrong length."""
        gamestate = load_fixture(
            client, "rearrange", "state-SELECTING_HAND--hand.count-8"
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["hand"]["count"] == 8
        response = api(
            client,
            "rearrange",
            {"hand": [0, 1, 2, 3]},
        )
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Must provide exactly 8 indices for hand",
        )

    def test_wrong_array_length_jokers(self, client: httpx.Client) -> None:
        """Test error when jokers array wrong length."""
        gamestate = load_fixture(
            client, "rearrange", "state-SHOP--jokers.count-4--consumables.count-2"
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["jokers"]["count"] == 4
        response = api(
            client,
            "rearrange",
            {"jokers": [0, 1, 2]},
        )
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Must provide exactly 4 indices for jokers",
        )

    def test_wrong_array_length_consumables(self, client: httpx.Client) -> None:
        """Test error when consumables array wrong length."""
        gamestate = load_fixture(
            client, "rearrange", "state-SHOP--jokers.count-4--consumables.count-2"
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["consumables"]["count"] == 2
        response = api(
            client,
            "rearrange",
            {"consumables": [0, 1, 2]},
        )
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Must provide exactly 2 indices for consumables",
        )

    def test_invalid_card_index(self, client: httpx.Client) -> None:
        """Test error when card index out of range."""
        gamestate = load_fixture(
            client, "rearrange", "state-SELECTING_HAND--hand.count-8"
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["hand"]["count"] == 8
        response = api(
            client,
            "rearrange",
            {"hand": [-1, 1, 2, 3, 4, 5, 6, 7]},
        )
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Index out of range for hand: -1",
        )

    def test_duplicate_indices(self, client: httpx.Client) -> None:
        """Test error when indices contain duplicates."""
        gamestate = load_fixture(
            client, "rearrange", "state-SELECTING_HAND--hand.count-8"
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["hand"]["count"] == 8
        response = api(
            client,
            "rearrange",
            {"hand": [1, 1, 2, 3, 4, 5, 6, 7]},
        )
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Duplicate index in hand: 1",
        )


class TestRearrangeEndpointStateRequirements:
    """Test rearrange endpoint state requirements."""

    def test_rearrange_hand_from_wrong_state(self, client: httpx.Client) -> None:
        """Test that rearranging hand fails from wrong state."""
        gamestate = load_fixture(client, "rearrange", "state-BLIND_SELECT")
        assert gamestate["state"] == "BLIND_SELECT"
        assert_error_response(
            api(client, "rearrange", {"hand": [0, 1, 2, 3, 4, 5, 6, 7]}),
            "INVALID_STATE",
            "Method 'rearrange' requires one of these states: SELECTING_HAND, SHOP",
        )

    def test_rearrange_jokers_from_wrong_state(self, client: httpx.Client) -> None:
        """Test that rearranging jokers fails from wrong state."""
        gamestate = load_fixture(client, "rearrange", "state-BLIND_SELECT")
        assert gamestate["state"] == "BLIND_SELECT"
        assert_error_response(
            api(client, "rearrange", {"jokers": [0, 1, 2, 3, 4]}),
            "INVALID_STATE",
            "Method 'rearrange' requires one of these states: SELECTING_HAND, SHOP",
        )

    def test_rearrange_consumables_from_wrong_state(self, client: httpx.Client) -> None:
        """Test that rearranging consumables fails from wrong state."""
        gamestate = load_fixture(client, "rearrange", "state-BLIND_SELECT")
        assert gamestate["state"] == "BLIND_SELECT"
        assert_error_response(
            api(client, "rearrange", {"jokers": [0, 1]}),
            "INVALID_STATE",
            "Method 'rearrange' requires one of these states: SELECTING_HAND, SHOP",
        )
