"""Tests for src/lua/endpoints/use.lua"""

import httpx

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


class TestUseEndpoint:
    """Test basic use endpoint functionality."""

    def test_use_hermit_no_cards(self, client: httpx.Client) -> None:
        """Test using The Hermit (no card selection) in SHOP state."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SHOP--money-12--consumables.cards[0]-key-c_hermit",
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["money"] == 12
        assert gamestate["consumables"]["cards"][0]["key"] == "c_hermit"
        response = api(client, "use", {"consumable": 0})
        assert_gamestate_response(response, money=24)

    def test_use_hermit_in_selecting_hand(self, client: httpx.Client) -> None:
        """Test using The Hermit in SELECTING_HAND state."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--money-12--consumables.cards[0]-key-c_hermit",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["money"] == 12
        assert gamestate["consumables"]["cards"][0]["key"] == "c_hermit"
        response = api(client, "use", {"consumable": 0})
        assert_gamestate_response(response, money=24)

    def test_use_temperance_no_cards(self, client: httpx.Client) -> None:
        """Test using Temperance (no card selection)."""
        before = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0]-key-c_temperance--jokers.count-0",
        )
        assert before["state"] == "SELECTING_HAND"
        assert before["jokers"]["count"] == 0  # no jokers => no money increase
        assert before["consumables"]["cards"][0]["key"] == "c_temperance"
        response = api(client, "use", {"consumable": 0})
        assert_gamestate_response(response, money=before["money"])

    def test_use_hermit_in_buffoon_pack(self, client: httpx.Client) -> None:
        """Test using The Hermit while a Buffoon pack is open."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SMODS_BOOSTER_OPENED--pack.type-buffoon--consumables.cards[0].key-c_hermit",
        )
        assert gamestate["state"] == "SMODS_BOOSTER_OPENED"
        assert gamestate["consumables"]["cards"][0]["key"] == "c_hermit"
        assert gamestate["pack"]["cards"][0]["set"] == "JOKER"
        response = api(client, "use", {"consumable": 0})
        assert_gamestate_response(response, money=1019)

    def test_use_hermit_in_round_eval(self, client: httpx.Client) -> None:
        """Test using The Hermit during ROUND_EVAL state."""
        before = load_fixture(
            client,
            "use",
            "state-ROUND_EVAL--consumables.cards[0]-key-c_hermit",
        )
        assert before["state"] == "ROUND_EVAL"
        assert before["consumables"]["cards"][0]["key"] == "c_hermit"

        response = api(client, "use", {"consumable": 0})
        after = assert_gamestate_response(response)
        assert after["consumables"]["count"] == 0

    def test_use_hermit_in_blind_select(self, client: httpx.Client) -> None:
        """Test using The Hermit during BLIND_SELECT state."""
        before = load_fixture(
            client,
            "use",
            "state-BLIND_SELECT--consumables.cards[0]-key-c_hermit",
        )
        assert before["state"] == "BLIND_SELECT"
        assert before["consumables"]["cards"][0]["key"] == "c_hermit"

        response = api(client, "use", {"consumable": 0})
        after = assert_gamestate_response(response)
        assert after["consumables"]["count"] == 0

    def test_use_magician_in_arcana_pack(self, client: httpx.Client) -> None:
        """Test using The Magician (card selection) while an Arcana pack is open."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SMODS_BOOSTER_OPENED--pack.type-arcana--consumables.cards[0].key-c_magician",
        )
        assert gamestate["state"] == "SMODS_BOOSTER_OPENED"
        assert gamestate["consumables"]["cards"][0]["key"] == "c_magician"
        assert gamestate["pack"]["cards"][0]["set"] == "TAROT"
        assert gamestate["hand"]["count"] > 0

        response = api(client, "use", {"consumable": 0, "cards": [0, 1]})
        after = assert_gamestate_response(response)
        assert after["hand"]["cards"][0]["modifier"]["enhancement"] == "m_lucky"
        assert after["hand"]["cards"][1]["modifier"]["enhancement"] == "m_lucky"

    def test_use_planet_no_cards(self, client: httpx.Client) -> None:
        """Test using a Planet card (no card selection)."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["hands"]["High Card"]["level"] == 1
        response = api(client, "use", {"consumable": 0})
        after = assert_gamestate_response(response)
        assert after["hands"]["High Card"]["level"] == 2

    def test_use_magician_with_one_card(self, client: httpx.Client) -> None:
        """Test using The Magician with 1 card (min=1, max=2)."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        response = api(client, "use", {"consumable": 1, "cards": [0]})
        after = assert_gamestate_response(response)
        assert after["hand"]["cards"][0]["modifier"]["enhancement"] == "m_lucky"

    def test_use_magician_with_two_cards(self, client: httpx.Client) -> None:
        """Test using The Magician with 2 cards."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        response = api(client, "use", {"consumable": 1, "cards": [7, 5]})
        after = assert_gamestate_response(response)
        assert after["hand"]["cards"][5]["modifier"]["enhancement"] == "m_lucky"
        assert after["hand"]["cards"][7]["modifier"]["enhancement"] == "m_lucky"

    def test_use_familiar_all_hand(self, client: httpx.Client) -> None:
        """Test using Familiar (destroys cards, #G.hand.cards > 1)."""
        before = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0]-key-c_familiar",
        )
        assert before["state"] == "SELECTING_HAND"
        response = api(client, "use", {"consumable": 0})
        after = assert_gamestate_response(response)
        assert after["hand"]["count"] == before["hand"]["count"] - 1 + 3
        assert after["hand"]["cards"][7]["set"] == "ENHANCED"
        assert after["hand"]["cards"][8]["set"] == "ENHANCED"
        assert after["hand"]["cards"][9]["set"] == "ENHANCED"


class TestUseEndpointValidation:
    """Test use endpoint parameter validation."""

    def test_use_no_consumable_provided(self, client: httpx.Client) -> None:
        """Test that use fails when consumable parameter is missing."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {}),
            "BAD_REQUEST",
            "Missing required field 'consumable'",
        )

    def test_use_invalid_consumable_type(self, client: httpx.Client) -> None:
        """Test that use fails when consumable is not an integer."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {"consumable": "NOT_AN_INTEGER"}),
            "BAD_REQUEST",
            "Field 'consumable' must be an integer",
        )

    def test_use_invalid_consumable_index_negative(self, client: httpx.Client) -> None:
        """Test that use fails when consumable index is negative."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {"consumable": -1}),
            "BAD_REQUEST",
            "Consumable index out of range: -1",
        )

    def test_use_invalid_consumable_index_too_high(self, client: httpx.Client) -> None:
        """Test that use fails when consumable index >= count."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {"consumable": 999}),
            "BAD_REQUEST",
            "Consumable index out of range: 999",
        )

    def test_use_invalid_cards_type(self, client: httpx.Client) -> None:
        """Test that use fails when cards is not an array."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {"consumable": 1, "cards": "NOT_AN_ARRAY_OF_INTEGERS"}),
            "BAD_REQUEST",
            "Field 'cards' must be an array",
        )

    def test_use_invalid_cards_item_type(self, client: httpx.Client) -> None:
        """Test that use fails when cards array contains non-integer."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {"consumable": 1, "cards": ["NOT_INT_1", "NOT_INT_2"]}),
            "BAD_REQUEST",
            "Field 'cards' array item at index 0 must be of type integer",
        )

    def test_use_invalid_card_index_negative(self, client: httpx.Client) -> None:
        """Test that use fails when a card index is negative."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {"consumable": 1, "cards": [-1]}),
            "BAD_REQUEST",
            "Card index out of range: -1",
        )

    def test_use_invalid_card_index_too_high(self, client: httpx.Client) -> None:
        """Test that use fails when a card index >= hand count."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {"consumable": 1, "cards": [999]}),
            "BAD_REQUEST",
            "Card index out of range: 999",
        )

    def test_use_magician_without_cards(self, client: httpx.Client) -> None:
        """Test that using The Magician without cards parameter fails."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["consumables"]["cards"][1]["key"] == "c_magician"
        assert_error_response(
            api(client, "use", {"consumable": 1}),
            "BAD_REQUEST",
            "Consumable 'The Magician' requires card selection",
        )

    def test_use_magician_with_empty_cards(self, client: httpx.Client) -> None:
        """Test that using The Magician with empty cards array fails."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["consumables"]["cards"][1]["key"] == "c_magician"
        assert_error_response(
            api(client, "use", {"consumable": 1, "cards": []}),
            "BAD_REQUEST",
            "Consumable 'The Magician' requires card selection",
        )

    def test_use_magician_too_many_cards(self, client: httpx.Client) -> None:
        """Test that using The Magician with 3 cards fails (max=2)."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["consumables"]["cards"][1]["key"] == "c_magician"
        assert_error_response(
            api(client, "use", {"consumable": 1, "cards": [0, 1, 2]}),
            "BAD_REQUEST",
            "Consumable 'The Magician' requires at most 2 cards (provided: 3)",
        )

    def test_use_death_too_few_cards(self, client: httpx.Client) -> None:
        """Test that using Death with 1 card fails (requires exactly 2)."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_death",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["consumables"]["cards"][0]["key"] == "c_death"
        assert_error_response(
            api(client, "use", {"consumable": 0, "cards": [0]}),
            "BAD_REQUEST",
            "Consumable 'Death' requires exactly 2 cards (provided: 1)",
        )

    def test_use_death_too_many_cards(self, client: httpx.Client) -> None:
        """Test that using Death with 3 cards fails (requires exactly 2)."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_death",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["consumables"]["cards"][0]["key"] == "c_death"
        assert_error_response(
            api(client, "use", {"consumable": 0, "cards": [0, 1, 2]}),
            "BAD_REQUEST",
            "Consumable 'Death' requires exactly 2 cards (provided: 3)",
        )


class TestUseEndpointStateRequirements:
    """Test use endpoint state requirements."""

    def test_use_magician_from_SHOP(self, client: httpx.Client) -> None:
        """Test that using The Magician fails from SHOP (needs a hand)."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SHOP--consumables.cards[0].key-c_magician",
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["consumables"]["cards"][0]["key"] == "c_magician"
        assert_error_response(
            api(client, "use", {"consumable": 0, "cards": [0]}),
            "INVALID_STATE",
            "Consumable 'The Magician' requires card selection and can only be used in SELECTING_HAND or SMODS_BOOSTER_OPENED state",
        )

    def test_use_familiar_from_SHOP(self, client: httpx.Client) -> None:
        """Test that using The Magician fails from SHOP (needs SELECTING_HAND)."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SHOP--consumables.cards[0]-key-c_familiar",
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["consumables"]["cards"][0]["key"] == "c_familiar"
        assert_error_response(
            api(client, "use", {"consumable": 0}),
            "NOT_ALLOWED",
            "Consumable 'Familiar' cannot be used at this time",
        )
