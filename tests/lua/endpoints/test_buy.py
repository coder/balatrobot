"""Tests for src/lua/endpoints/buy.lua"""

import httpx
import pytest

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


class TestBuyEndpoint:
    """Test basic buy endpoint functionality."""

    @pytest.mark.flaky(reruns=2)
    def test_buy_no_args(self, client: httpx.Client) -> None:
        """Test buy endpoint with no arguments."""
        gamestate = load_fixture(client, "buy", "state-SHOP--shop.cards[0].set-JOKER")
        assert gamestate["state"] == "SHOP"
        assert gamestate["shop"]["cards"][0]["set"] == "JOKER"
        assert_error_response(
            api(client, "buy", {}),
            "BAD_REQUEST",
            "Invalid arguments. You must provide one of: card, voucher, pack",
        )

    @pytest.mark.flaky(reruns=2)
    def test_buy_multi_args(self, client: httpx.Client) -> None:
        """Test buy endpoint with multiple arguments."""
        gamestate = load_fixture(client, "buy", "state-SHOP--shop.cards[0].set-JOKER")
        assert gamestate["state"] == "SHOP"
        assert gamestate["shop"]["cards"][0]["set"] == "JOKER"
        assert_error_response(
            api(client, "buy", {"card": 0, "voucher": 0}),
            "BAD_REQUEST",
            "Invalid arguments. Cannot provide more than one of: card, voucher, or pack",
        )

    def test_buy_no_card_in_shop_area(self, client: httpx.Client) -> None:
        """Test buy endpoint with no card in shop area."""
        gamestate = load_fixture(client, "buy", "state-SHOP--shop.count-0")
        assert gamestate["state"] == "SHOP"
        assert gamestate["shop"]["count"] == 0
        assert_error_response(
            api(client, "buy", {"card": 0}),
            "BAD_REQUEST",
            "No jokers/consumables/cards in the shop. Reroll to restock the shop",
        )

    def test_buy_invalid_card_index(self, client: httpx.Client) -> None:
        """Test buy endpoint with invalid card index."""
        gamestate = load_fixture(client, "buy", "state-SHOP--shop.cards[0].set-JOKER")
        assert gamestate["state"] == "SHOP"
        assert gamestate["shop"]["cards"][0]["set"] == "JOKER"
        assert_error_response(
            api(client, "buy", {"card": 999}),
            "BAD_REQUEST",
            "Card index out of range. Index: 999, Available cards: 2",
        )

    def test_buy_invalid_voucher_index(self, client: httpx.Client) -> None:
        """Test buy endpoint with invalid voucher index."""
        gamestate = load_fixture(
            client, "buy", "state-SHOP--voucher.cards[0].set-VOUCHER"
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["vouchers"]["cards"][0]["set"] == "VOUCHER"
        assert_error_response(
            api(client, "buy", {"voucher": 999}),
            "BAD_REQUEST",
            "Voucher index out of range. Index: 999, Available: 1",
        )

    def test_buy_invalid_pack_index(self, client: httpx.Client) -> None:
        """Test buy endpoint with invalid pack index."""
        gamestate = load_fixture(
            client,
            "buy",
            "state-SHOP--packs.cards[0].label-Buffoon+Pack--packs.cards[1].label-Standard+Pack",
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["packs"]["cards"][0]["label"] == "Buffoon Pack"
        assert_error_response(
            api(client, "buy", {"pack": 999}),
            "BAD_REQUEST",
            "Pack index out of range. Index: 999, Available: 2",
        )

    def test_buy_insufficient_funds(self, client: httpx.Client) -> None:
        """Test buy endpoint when player has insufficient funds."""
        gamestate = load_fixture(client, "buy", "state-SHOP--money-0")
        assert gamestate["state"] == "SHOP"
        assert gamestate["money"] == 0
        assert_error_response(
            api(client, "buy", {"card": 0}),
            "BAD_REQUEST",
            "Card is not affordable. Cost: 5, Available money: 0",
        )

    def test_buy_joker_slots_full(self, client: httpx.Client) -> None:
        """Test buy endpoint when player has the maximum number of consumables."""
        gamestate = load_fixture(
            client, "buy", "state-SHOP--jokers.count-5--shop.cards[0].set-JOKER"
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["jokers"]["count"] == 5
        assert gamestate["shop"]["cards"][0]["set"] == "JOKER"
        assert_error_response(
            api(client, "buy", {"card": 0}),
            "BAD_REQUEST",
            "Cannot purchase joker card, joker slots are full. Current: 5, Limit: 5",
        )

    def test_buy_consumable_slots_full(self, client: httpx.Client) -> None:
        """Test buy endpoint when player has the maximum number of consumables."""
        gamestate = load_fixture(
            client,
            "buy",
            "state-SHOP--consumables.count-2--shop.cards[1].set-PLANET",
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["consumables"]["count"] == 2
        assert gamestate["shop"]["cards"][1]["set"] == "PLANET"
        assert_error_response(
            api(client, "buy", {"card": 1}),
            "BAD_REQUEST",
            "Cannot purchase consumable card, consumable slots are full. Current: 2, Limit: 2",
        )

    def test_buy_vouchers_slot_empty(self, client: httpx.Client) -> None:
        """Test buy endpoint when player has the maximum number of vouchers."""
        gamestate = load_fixture(client, "buy", "state-SHOP--voucher.count-0")
        assert gamestate["state"] == "SHOP"
        assert gamestate["vouchers"]["count"] == 0
        assert_error_response(
            api(client, "buy", {"voucher": 0}),
            "BAD_REQUEST",
            "No vouchers to redeem. Defeat boss blind to restock",
        )

    def test_buy_packs_slot_empty(self, client: httpx.Client) -> None:
        """Test buy endpoint when player has the maximum number of vouchers."""
        gamestate = load_fixture(client, "buy", "state-SHOP--packs.count-0")
        assert gamestate["state"] == "SHOP"
        assert gamestate["packs"]["count"] == 0
        assert_error_response(
            api(client, "buy", {"pack": 0}),
            "BAD_REQUEST",
            "No packs to open",
        )

    def test_buy_joker_success(self, client: httpx.Client) -> None:
        """Test buying a joker card from shop."""
        gamestate = load_fixture(client, "buy", "state-SHOP--shop.cards[0].set-JOKER")
        assert gamestate["state"] == "SHOP"
        assert gamestate["shop"]["cards"][0]["set"] == "JOKER"
        response = api(client, "buy", {"card": 0})
        gamestate = assert_gamestate_response(response)
        assert gamestate["jokers"]["cards"][0]["set"] == "JOKER"

    def test_buy_consumable_success(self, client: httpx.Client) -> None:
        """Test buying a consumable card (Planet/Tarot/Spectral) from shop."""
        gamestate = load_fixture(client, "buy", "state-SHOP--shop.cards[1].set-PLANET")
        assert gamestate["state"] == "SHOP"
        assert gamestate["shop"]["cards"][1]["set"] == "PLANET"
        response = api(client, "buy", {"card": 1})
        gamestate = assert_gamestate_response(response)
        assert gamestate["consumables"]["cards"][0]["set"] == "PLANET"

    def test_buy_voucher_success(self, client: httpx.Client) -> None:
        """Test buying a voucher from shop."""
        gamestate = load_fixture(
            client, "buy", "state-SHOP--voucher.cards[0].set-VOUCHER"
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["vouchers"]["cards"][0]["set"] == "VOUCHER"
        response = api(client, "buy", {"voucher": 0})
        gamestate = assert_gamestate_response(response)
        assert gamestate["used_vouchers"] is not None
        assert len(gamestate["used_vouchers"]) > 0

    def test_buy_packs_success(self, client: httpx.Client) -> None:
        """Test buying a pack from shop."""
        gamestate = load_fixture(
            client,
            "buy",
            "state-SHOP--packs.cards[0].label-Buffoon+Pack--packs.cards[1].label-Standard+Pack",
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["packs"]["cards"][0]["label"] == "Buffoon Pack"
        assert gamestate["packs"]["cards"][1]["label"] == "Standard Pack"
        response = api(client, "buy", {"pack": 0})
        gamestate = assert_gamestate_response(response)
        assert gamestate["pack"] is not None
        assert len(gamestate["pack"]["cards"]) > 0

    def test_buy_with_credit_card_joker(self, client: httpx.Client) -> None:
        """Test buying when player has Credit Card joker (can go negative)."""
        # Get to shop state with $0
        gamestate = load_fixture(client, "buy", "state-SHOP--money-0")
        assert gamestate["state"] == "SHOP"
        assert gamestate["money"] == 0

        # Add Credit Card joker (gives +$20 credit, can go to -$20)
        response = api(client, "add", {"key": "j_credit_card"})
        gamestate = assert_gamestate_response(response)
        assert any(j["key"] == "j_credit_card" for j in gamestate["jokers"]["cards"])

        # Should be able to buy a card costing <= $20 even with $0 (due to credit)
        card_cost = gamestate["shop"]["cards"][0]["cost"]["buy"]
        assert card_cost <= 20  # Credit Card gives $20 credit

        response = api(client, "buy", {"card": 0})
        gamestate = assert_gamestate_response(response)
        # Money should be negative now
        assert gamestate["money"] < 0


class TestBuyEndpointValidation:
    """Test buy endpoint parameter validation."""

    def test_invalid_card_type_string(self, client: httpx.Client) -> None:
        """Test that buy fails when card parameter is a string instead of integer."""
        gamestate = load_fixture(client, "buy", "state-SHOP--shop.cards[0].set-JOKER")
        assert gamestate["state"] == "SHOP"
        assert gamestate["shop"]["cards"][0]["set"] == "JOKER"
        assert_error_response(
            api(client, "buy", {"card": "INVALID_STRING"}),
            "BAD_REQUEST",
            "Field 'card' must be an integer",
        )

    def test_invalid_voucher_type_string(self, client: httpx.Client) -> None:
        """Test that buy fails when voucher parameter is a string instead of integer."""
        gamestate = load_fixture(client, "buy", "state-SHOP--shop.cards[0].set-JOKER")
        assert gamestate["state"] == "SHOP"
        assert gamestate["shop"]["cards"][0]["set"] == "JOKER"
        assert_error_response(
            api(client, "buy", {"voucher": "INVALID_STRING"}),
            "BAD_REQUEST",
            "Field 'voucher' must be an integer",
        )

    def test_invalid_pack_type_string(self, client: httpx.Client) -> None:
        """Test that buy fails when pack parameter is a string instead of integer."""
        gamestate = load_fixture(client, "buy", "state-SHOP--shop.cards[0].set-JOKER")
        assert gamestate["state"] == "SHOP"
        assert gamestate["shop"]["cards"][0]["set"] == "JOKER"
        assert_error_response(
            api(client, "buy", {"pack": "INVALID_STRING"}),
            "BAD_REQUEST",
            "Field 'pack' must be an integer",
        )


class TestBuyEndpointStateRequirements:
    """Test buy endpoint state requirements."""

    def test_buy_from_BLIND_SELECT(self, client: httpx.Client) -> None:
        """Test that buy fails when not in SHOP state."""
        gamestate = load_fixture(client, "buy", "state-BLIND_SELECT")
        assert gamestate["state"] == "BLIND_SELECT"
        assert_error_response(
            api(client, "buy", {"card": 0}),
            "INVALID_STATE",
            "Method 'buy' requires one of these states: SHOP",
        )
