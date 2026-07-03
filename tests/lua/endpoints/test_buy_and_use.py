"""Tests for src/lua/endpoints/buy_and_use.lua"""

import httpx

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


class TestBuyAndUseEndpoint:
    """Test buy_and_use endpoint functionality."""

    def test_buy_and_use_wrong_state(self, client: httpx.Client) -> None:
        """buy_and_use requires SHOP state."""
        gamestate = load_fixture(client, "buy_and_use", "state-BLIND_SELECT")
        assert gamestate["state"] == "BLIND_SELECT"
        assert_error_response(
            api(client, "buy_and_use", {"card": 0}),
            "INVALID_STATE",
            "Method 'buy_and_use' requires one of these states: SHOP",
        )

    def test_buy_and_use_no_card(self, client: httpx.Client) -> None:
        """buy_and_use with no card argument."""
        gamestate = load_fixture(
            client, "buy_and_use", "state-SHOP--shop.cards[0].set-JOKER"
        )
        assert gamestate["state"] == "SHOP"
        assert_error_response(
            api(client, "buy_and_use", {}),
            "BAD_REQUEST",
            "Invalid arguments. You must provide: card",
        )

    def test_buy_and_use_empty_shop(self, client: httpx.Client) -> None:
        """buy_and_use with no cards in the shop."""
        gamestate = load_fixture(client, "buy_and_use", "state-SHOP--shop.count-0")
        assert gamestate["state"] == "SHOP"
        assert gamestate["shop"]["count"] == 0
        assert_error_response(
            api(client, "buy_and_use", {"card": 0}),
            "BAD_REQUEST",
            "No consumables in the shop. Use `reroll` to restock the shop.",
        )

    def test_buy_and_use_invalid_card_index(self, client: httpx.Client) -> None:
        """buy_and_use with an out-of-range card index."""
        gamestate = load_fixture(
            client, "buy_and_use", "state-SHOP--shop.cards[0].set-JOKER"
        )
        assert gamestate["state"] == "SHOP"
        assert_error_response(
            api(client, "buy_and_use", {"card": 999}),
            "BAD_REQUEST",
            "Card index out of range. Index: 999, Available cards: 2",
        )

    def test_buy_and_use_insufficient_funds(self, client: httpx.Client) -> None:
        """buy_and_use when the player cannot afford the card."""
        gamestate = load_fixture(client, "buy_and_use", "state-SHOP--money-0")
        assert gamestate["state"] == "SHOP"
        assert gamestate["money"] == 0
        assert_error_response(
            api(client, "buy_and_use", {"card": 1}),
            "BAD_REQUEST",
            "Card is not affordable. Cost: 3, Available money: 0",
        )

    def test_buy_and_use_joker_not_consumable(self, client: httpx.Client) -> None:
        """buy_and_use on a Joker (not a consumable) is rejected.

        The Buy-and-Use button only exists on consumables, so a non-consumable
        is never a valid buy-and-use target. (Caught by the is_consumable guard,
        before can_use_consumeable is ever consulted — the game never calls it on
        a Joker.)
        """
        gamestate = load_fixture(
            client, "buy_and_use", "state-SHOP--shop.cards[0].set-JOKER"
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["shop"]["cards"][0]["set"] == "JOKER"
        assert_error_response(
            api(client, "buy_and_use", {"card": 0}),
            "NOT_ALLOWED",
            "cannot be buy-and-used at this time",
        )

    def test_buy_and_use_tarot_needs_targets(self, client: httpx.Client) -> None:
        """buy_and_use on a consumable whose can_use_consumeable() is false.

        The Magician (Tarot) takes hand targets, so can_use_consumeable only
        returns true in SELECTING_HAND / pack states — not SHOP. The game's
        Buy-and-Use button is invisible here; we mirror that with NOT_ALLOWED.
        This exercises the actual can_use_consumeable gate (error-table row 5),
        distinct from the non-consumable guard above.
        """
        gamestate = load_fixture(
            client, "buy_and_use", "state-SHOP--shop.cards[1].set-TAROT"
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["shop"]["cards"][1]["set"] == "TAROT"
        assert_error_response(
            api(client, "buy_and_use", {"card": 1}),
            "NOT_ALLOWED",
            "cannot be buy-and-used at this time",
        )

    def test_buy_and_use_success(self, client: httpx.Client) -> None:
        """buy_and_use on a no-target consumable (Planet): buys and uses it,
        never occupying a consumable slot.
        """
        before = load_fixture(
            client, "buy_and_use", "state-SHOP--shop.cards[1].set-PLANET"
        )
        assert before["state"] == "SHOP"
        assert before["shop"]["cards"][1]["set"] == "PLANET"

        cost = before["shop"]["cards"][1]["cost"]["buy"]
        cons_before = before["consumables"]["count"]
        shop_before = before["shop"]["count"]
        money_before = before["money"]

        response = api(client, "buy_and_use", {"card": 1})
        after = assert_gamestate_response(response, state="SHOP")

        # The defining behaviour of buy_and_use: the card is used, not stored,
        # so the consumable slot count does not change.
        assert after["consumables"]["count"] == cons_before
        # Card left the shop and was paid for.
        assert after["shop"]["count"] == shop_before - 1
        assert after["money"] == money_before - cost

    def test_buy_and_use_consumables_full(self, client: httpx.Client) -> None:
        """The motivating case for #209: consumable slots are full, so a plain
        `buy` would fail, but `buy_and_use` succeeds (uses the card without
        occupying a slot).
        """
        before = load_fixture(
            client,
            "buy_and_use",
            "state-SHOP--consumables.count-2--shop.cards[1].set-PLANET",
        )
        assert before["state"] == "SHOP"
        assert before["consumables"]["count"] == 2
        assert before["consumables"]["limit"] == 2
        assert before["shop"]["cards"][1]["set"] == "PLANET"

        cost = before["shop"]["cards"][1]["cost"]["buy"]
        money_before = before["money"]

        response = api(client, "buy_and_use", {"card": 1})
        after = assert_gamestate_response(response, state="SHOP")

        # Still full — the consumable was used, not stored.
        assert after["consumables"]["count"] == 2
        assert after["money"] == money_before - cost
        assert after["shop"]["count"] == before["shop"]["count"] - 1

    def test_buy_and_use_ankh_noop(self, client: httpx.Client) -> None:
        """Faithfulness edge case (§2.3 of the design): Ankh at full jokers.

        Ankh's `can_use_consumeable` returns true (it only needs >=1 joker and
        card_limit > 1), so the game's Buy-and-Use button is *visible* — but its
        execution-time `check_use` bails because jokers are full. The net result
        in vanilla is a noop: money spent, no joker created. We replicate this
        exactly and report it as a SUCCESS (we do not pre-call `check_use`, so we
        are never stricter than the game).
        """
        before = load_fixture(
            client,
            "buy_and_use",
            "seed-ANKH0001--jokers.count-5--shop.cards[1].key-c_ankh",
        )
        assert before["state"] == "SHOP"
        assert before["jokers"]["count"] == 5
        assert before["jokers"]["limit"] == 5
        assert before["shop"]["cards"][1]["key"] == "c_ankh"

        cost = before["shop"]["cards"][1]["cost"]["buy"]
        money_before = before["money"]

        response = api(client, "buy_and_use", {"card": 1})
        after = assert_gamestate_response(response, state="SHOP")

        # Money spent (cost deducted)...
        assert after["money"] == money_before - cost
        # ...but no joker created — the noop. Honest success, not an error.
        assert after["jokers"]["count"] == 5


class TestBuyAndUseEndpointValidation:
    """Test buy_and_use endpoint parameter type validation."""

    def test_invalid_card_type_string(self, client: httpx.Client) -> None:
        """card must be an integer."""
        gamestate = load_fixture(
            client, "buy_and_use", "state-SHOP--shop.cards[0].set-JOKER"
        )
        assert gamestate["state"] == "SHOP"
        assert_error_response(
            api(client, "buy_and_use", {"card": "INVALID_STRING"}),
            "BAD_REQUEST",
            "Field 'card' must be an integer",
        )
