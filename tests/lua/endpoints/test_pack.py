"""Tests for src/lua/endpoints/pack.lua"""

import httpx

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


class TestPackEndpoint:
    """Test basic pack endpoint functionality."""

    def test_pack_no_args(self, client: httpx.Client) -> None:
        """Test pack endpoint with no arguments."""
        # Buy a pack first to open it
        load_fixture(client, "pack", "state-SHOP")
        result = api(client, "buy", {"pack": 0})
        assert_gamestate_response(result)

        assert_error_response(
            api(client, "pack", {}),
            "BAD_REQUEST",
            "Invalid arguments. You must provide one of: card, skip",
        )

    def test_pack_both_args(self, client: httpx.Client) -> None:
        """Test pack endpoint with both card and skip."""
        # Buy a pack first to open it
        load_fixture(client, "pack", "state-SHOP")
        result = api(client, "buy", {"pack": 0})
        assert_gamestate_response(result)

        assert_error_response(
            api(client, "pack", {"card": 0, "skip": True}),
            "BAD_REQUEST",
            "Invalid arguments. Cannot provide both card and skip",
        )

    def test_pack_no_pack_open(self, client: httpx.Client) -> None:
        """Test pack endpoint when no pack is open."""
        load_fixture(client, "pack", "state-SHOP")

        # The dispatcher checks required state before the endpoint runs
        assert_error_response(
            api(client, "pack", {"card": 0}),
            "INVALID_STATE",
            "requires one of these states: SMODS_BOOSTER_OPENED",
        )

    def test_pack_invalid_card_index(self, client: httpx.Client) -> None:
        """Test pack endpoint with invalid card index."""
        # Buy a pack first to open it
        gamestate = load_fixture(client, "pack", "state-SHOP")
        result = api(client, "buy", {"pack": 0})
        gamestate = assert_gamestate_response(result)

        pack_count = gamestate.get("pack", {}).get("count", 0)
        assert pack_count > 0

        assert_error_response(
            api(client, "pack", {"card": 999}),
            "BAD_REQUEST",
            f"Card index out of range. Index: 999, Available cards: {pack_count}",
        )

    def test_pack_skip(self, client: httpx.Client) -> None:
        """Test skipping pack selection."""
        # Buy a pack first to open it
        gamestate = load_fixture(client, "pack", "state-SHOP")
        result = api(client, "buy", {"pack": 0})
        assert_gamestate_response(result)

        # Skip the pack
        result = api(client, "pack", {"skip": True})
        gamestate = assert_gamestate_response(result, state="SHOP")

        # Pack should be closed
        assert "pack" not in gamestate or gamestate.get("pack") is None

    def test_pack_joker_from_buffoon_pack(self, client: httpx.Client) -> None:
        """Test selecting a joker from a buffoon pack."""
        # Set up state with a buffoon pack
        gamestate = load_fixture(
            client, "pack", "state-SHOP--packs.cards[0].key-p_buffoon_normal_1"
        )
        initial_joker_count = gamestate["jokers"]["count"]

        # Buy the buffoon pack
        result = api(client, "buy", {"pack": 0})
        gamestate = assert_gamestate_response(result)

        # Verify pack is open
        assert "pack" in gamestate
        assert gamestate["pack"]["count"] > 0

        # Select first card from pack
        result = api(client, "pack", {"card": 0})
        gamestate = assert_gamestate_response(result)

        # Verify joker was added
        assert gamestate["jokers"]["count"] == initial_joker_count + 1

    def test_pack_tarot_from_arcana_pack(self, client: httpx.Client) -> None:
        """Test selecting and using a tarot from arcana pack."""
        # Start a fresh game with the seed that has arcana pack at position 1
        api(client, "menu", {})
        api(client, "start", {"deck": "RED", "stake": "WHITE", "seed": "QKNXF682"})

        # Select starting blind
        result = api(client, "select", {})
        assert_gamestate_response(result)

        # Set chips to 1000 to easily beat the blind
        api(client, "set", {"chips": 1000})

        # Play one card to complete the blind
        api(client, "play", {"cards": [0]})

        # Cash out to get to shop
        result = api(client, "cash_out", {})
        gamestate = assert_gamestate_response(result, state="SHOP")

        # Verify we have an arcana pack at position 1
        assert gamestate["packs"]["count"] >= 2

        # Buy the arcana pack (position 1)
        result = api(client, "buy", {"pack": 1})
        gamestate = assert_gamestate_response(result)

        # Verify pack is open
        assert "pack" in gamestate
        assert gamestate["pack"]["count"] > 0

        # Select first card from pack (Hierophant) with 2 card targets
        result = api(client, "pack", {"card": 0, "targets": [0, 1]})
        gamestate = assert_gamestate_response(result, state="SHOP")

        # Pack should be closed
        assert "pack" not in gamestate or gamestate.get("pack") is None

    def test_pack_planet_from_celestial_pack(self, client: httpx.Client) -> None:
        """Test selecting and using a planet from celestial pack."""
        # Set up state with a celestial pack
        gamestate = load_fixture(
            client, "pack", "state-SHOP--packs.cards[1].key-p_celestial_normal_2"
        )

        # Buy the celestial pack
        result = api(client, "buy", {"pack": 1})
        gamestate = assert_gamestate_response(result)

        # Verify pack is open
        assert "pack" in gamestate
        assert gamestate["pack"]["count"] > 0

        # Select first card from pack (planet will be used immediately)
        result = api(client, "pack", {"card": 0})
        gamestate = assert_gamestate_response(result, state="SMODS_BOOSTER_OPENED")

        # Pack should still be open with 1 less choice
        assert "pack" in gamestate
        assert gamestate["pack"]["count"] == 4

        # Select second card to close the Mega pack
        result = api(client, "pack", {"card": 0})
        gamestate = assert_gamestate_response(result, state="SHOP")

        # Pack should be closed
        assert "pack" not in gamestate or gamestate.get("pack") is None

    def test_pack_spectral_from_spectral_pack(self, client: httpx.Client) -> None:
        """Test selecting and using a spectral from spectral pack."""
        # Set up state with a spectral pack
        gamestate = load_fixture(
            client, "pack", "state-SHOP--packs.cards[1].key-p_spectral_normal_1"
        )

        # Buy a joker first (needed for Ankh card which copies a random joker)
        # Add money to afford both joker and pack
        api(client, "set", {"money": 50})
        initial_joker_count = gamestate["jokers"]["count"]
        result = api(client, "buy", {"card": 0})
        gamestate = assert_gamestate_response(result)
        assert gamestate["jokers"]["count"] == initial_joker_count + 1

        # Buy the spectral pack
        result = api(client, "buy", {"pack": 1})
        gamestate = assert_gamestate_response(result)

        # Verify pack is open
        assert "pack" in gamestate
        assert gamestate["pack"]["count"] > 0

        # Select first card from pack (spectral will be used immediately)
        result = api(client, "pack", {"card": 0})
        gamestate = assert_gamestate_response(result, state="SHOP")

        # Pack should be closed
        assert "pack" not in gamestate or gamestate.get("pack") is None

    def test_pack_playing_card_from_standard_pack(self, client: httpx.Client) -> None:
        """Test selecting a playing card from standard pack (Mega pack - 2 selections)."""
        # Set up state with a Mega standard pack
        gamestate = load_fixture(
            client, "pack", "state-SHOP--packs.cards[1].key-p_standard_normal_2"
        )

        # Buy the standard pack
        result = api(client, "buy", {"pack": 1})
        gamestate = assert_gamestate_response(result)

        # Verify pack is open
        assert "pack" in gamestate
        assert gamestate["pack"]["count"] > 0

        # Select first card from pack (Mega pack allows 2 selections)
        result = api(client, "pack", {"card": 0})
        gamestate = assert_gamestate_response(result, state="SMODS_BOOSTER_OPENED")

        # Pack should still be open
        assert "pack" in gamestate
        assert gamestate["pack"]["count"] > 0

        # Select second card from pack
        result = api(client, "pack", {"card": 0})
        gamestate = assert_gamestate_response(result, state="SHOP")

        # Pack should be closed
        assert "pack" not in gamestate or gamestate.get("pack") is None

    def test_pack_joker_slots_full(self, client: httpx.Client) -> None:
        """Test selecting joker when slots are full."""
        # Set up state with full joker slots and buffoon pack
        load_fixture(
            client, "buy", "state-SHOP--jokers.count-5--shop.cards[0].set-JOKER"
        )

        # Buy the buffoon pack
        result = api(client, "buy", {"pack": 0})
        assert_gamestate_response(result)

        # Try to select a joker
        assert_error_response(
            api(client, "pack", {"card": 0}),
            "NOT_ALLOWED",
            "Cannot select joker, joker slots are full. Current: 5, Limit: 5",
        )

    def test_pack_missing_required_targets(self, client: httpx.Client) -> None:
        """Test that selecting a card requiring targets without providing them fails."""
        # Start a fresh game with a seed that has arcana pack at position 1
        api(client, "menu", {})
        api(client, "start", {"deck": "RED", "stake": "WHITE", "seed": "QKNXF682"})

        # Select starting blind
        result = api(client, "select", {})
        assert_gamestate_response(result)

        # Set chips to 1000 to easily beat the blind
        api(client, "set", {"chips": 1000})

        # Play one card to complete the blind
        api(client, "play", {"cards": [0]})

        # Cash out to get to shop
        result = api(client, "cash_out", {})
        gamestate = assert_gamestate_response(result, state="SHOP")

        # Verify we have an arcana pack at position 1
        assert gamestate["packs"]["count"] >= 2

        # Buy the arcana pack (position 1)
        result = api(client, "buy", {"pack": 1})
        gamestate = assert_gamestate_response(result)

        # Verify pack is open
        assert "pack" in gamestate
        assert gamestate["pack"]["count"] > 0

        # Try to select Hierophant without providing required targets
        assert_error_response(
            api(client, "pack", {"card": 0}),
            "BAD_REQUEST",
            "Card 'c_heirophant' requires 1-2 target card(s). Provided: 0",
        )
