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


class TestUseRevealed:
    """Test the transient `revealed` field emitted by the `use` endpoint.

    Under a flip blind (The House, bl_house) the whole hand is dealt face-down.
    Using a conversion consumable (Magician: mod_conv; Sigil/Ouija: whole-hand)
    on a hidden card triggers the game's flip→modify→flip animation: the card is
    momentarily shown face-up to a human, then flipped back face-down. The
    transient `revealed: true` flag tells a fair-play consumer "you may now know
    this card." It co-occurs with `hidden: true` (the card ends face-down) and
    is present ONLY on the `use` response.
    """

    def test_use_magician_reveals_targeted_hidden_cards_under_the_house(
        self, client: httpx.Client
    ) -> None:
        """Using Magician on hidden cards marks exactly those cards `revealed`."""
        before = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--blinds.boss.key-bl_house--consumables.cards[0].key-c_magician",
        )
        # Preconditions: The House active, round just started, c_magician ready,
        # and the ENTIRE hand is face-down (hidden) — the glitch precondition.
        assert before["state"] == "SELECTING_HAND"
        assert before["blinds"]["boss"]["key"] == "bl_house"
        assert before["consumables"]["cards"][0]["key"] == "c_magician"
        assert before["round"]["hands_played"] == 0
        assert before["round"]["discards_used"] == 0
        assert all(c["state"].get("hidden") for c in before["hand"]["cards"])

        # Use Magician (mod_conv=m_lucky) on hidden cards [0, 1].
        response = api(client, "use", {"consumable": 0, "cards": [0, 1]})
        after = assert_gamestate_response(response, state="SELECTING_HAND")

        # The two targeted cards were momentarily exposed: revealed AND hidden.
        for i in (0, 1):
            card = after["hand"]["cards"][i]
            assert card["state"].get("hidden") is True, (
                f"card[{i}] should still be hidden under The House, got {card['state']}"
            )
            assert card["state"].get("revealed") is True, (
                f"card[{i}] should be transiently revealed, got {card['state']}"
            )
        assert after["hand"]["cards"][0]["modifier"]["enhancement"] == "m_lucky"
        assert after["hand"]["cards"][1]["modifier"]["enhancement"] == "m_lucky"

        # A hidden card NOT targeted by the consumable is revealed for no one.
        untargeted = after["hand"]["cards"][2]
        assert untargeted["state"].get("hidden") is True
        assert untargeted["state"].get("revealed") is not True, (
            f"untargeted card[2] must not be revealed, got {untargeted['state']}"
        )

    def test_revealed_is_transient_and_absent_from_plain_gamestate(
        self, client: httpx.Client
    ) -> None:
        """`revealed` is transient: a plain `gamestate` call after `use` has none.

        Regression guard for the transient contract — a fair-play consumer must
        capture `revealed` on the `use` response; it never appears elsewhere.
        """
        load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--blinds.boss.key-bl_house--consumables.cards[0].key-c_magician",
        )
        use_resp = api(client, "use", {"consumable": 0, "cards": [0, 1]})
        assert _cards_with_revealed(use_resp["result"]) == [
            "hand.cards[0]",
            "hand.cards[1]",
        ]

        # A subsequent gamestate snapshot must carry NO revealed card anywhere.
        gs_resp = api(client, "gamestate", {})
        gs = assert_gamestate_response(gs_resp, state="SELECTING_HAND")
        assert _cards_with_revealed(gs) == []

    def test_use_sigil_reveals_whole_hidden_hand_under_the_house(
        self, client: httpx.Client
    ) -> None:
        """Sigil (whole-hand conversion) reveals every previously-hidden card.

        Drives the `ability.name == 'Sigil'` branch which snapshots the entire
        G.hand.cards rather than G.hand.highlighted.
        """
        before = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--blinds.boss.key-bl_house--consumables.cards[0].key-c_sigil",
        )
        assert before["blinds"]["boss"]["key"] == "bl_house"
        assert before["consumables"]["cards"][0]["key"] == "c_sigil"
        hand_count = before["hand"]["count"]
        assert all(c["state"].get("hidden") for c in before["hand"]["cards"])

        # Sigil needs no card selection (operates on the whole hand).
        response = api(client, "use", {"consumable": 0})
        after = assert_gamestate_response(response, state="SELECTING_HAND")

        # Every hand card was flipped up → converted → flipped back: all hidden
        # AND all revealed.
        assert len(after["hand"]["cards"]) == hand_count
        for i, card in enumerate(after["hand"]["cards"]):
            assert card["state"].get("hidden") is True, (
                f"card[{i}] should remain hidden under The House, got {card['state']}"
            )
            assert card["state"].get("revealed") is True, (
                f"card[{i}] should be revealed by Sigil, got {card['state']}"
            )

    def test_use_on_face_up_cards_never_emits_revealed(
        self, client: httpx.Client
    ) -> None:
        """A normal (non-flip-blind) use must not stamp `revealed` anywhere.

        Regression guard against over-stamping: cards are face-up here, so the
        reveal snapshot is empty and `revealed` must be absent from the response.
        """
        before = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert before["state"] == "SELECTING_HAND"
        # No flip blind → no hidden cards in hand. (state may serialize as []
        # for flag-less cards, so guard with isinstance.)
        assert not any(
            isinstance(c.get("state"), dict) and c["state"].get("hidden")
            for c in before["hand"]["cards"]
        )

        response = api(client, "use", {"consumable": 1, "cards": [0, 1]})
        after = assert_gamestate_response(response, state="SELECTING_HAND")
        assert after["hand"]["cards"][0]["modifier"]["enhancement"] == "m_lucky"

        assert _cards_with_revealed(after) == []


def _cards_with_revealed(gamestate: dict) -> list[str]:
    """Return location labels (e.g. "hand.cards[0]") for every card whose
    `state.revealed` is True across all card-bearing areas.

    Robust to the Lua→JSON quirk where a card with no state flags serializes its
    empty `state` table as `[]` (array) rather than `{}`.
    """
    found: list[str] = []
    for area in (
        "jokers",
        "consumables",
        "hand",
        "cards",
        "shop",
        "vouchers",
        "packs",
        "pack",
    ):
        area_data = gamestate.get(area)
        if not isinstance(area_data, dict):
            continue
        for i, card in enumerate(area_data.get("cards", [])):
            state = card.get("state")
            if isinstance(state, dict) and state.get("revealed"):
                found.append(f"{area}.cards[{i}]")
    return found
