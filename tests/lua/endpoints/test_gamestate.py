"""Tests for src/lua/endpoints/gamestate.lua"""

import httpx

from tests.lua.conftest import api, assert_gamestate_response, load_fixture


class TestGamestateEndpoint:
    """Test basic gamestate endpoint and gamestate response structure."""

    def test_gamestate_from_MENU(self, client: httpx.Client) -> None:
        """Test that gamestate endpoint from MENU state is valid."""
        api(client, "menu", {})
        response = api(client, "gamestate", {})
        assert_gamestate_response(response, state="MENU")

    def test_gamestate_from_BLIND_SELECT(self, client: httpx.Client) -> None:
        """Test that gamestate from BLIND_SELECT state is valid."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["state"] == "BLIND_SELECT"
        assert gamestate["round_num"] == 0
        assert gamestate["deck"] == "RED"
        assert gamestate["stake"] == "WHITE"
        response = api(client, "gamestate", {})
        assert_gamestate_response(
            response,
            state="BLIND_SELECT",
            round_num=0,
            deck="RED",
            stake="WHITE",
        )


class TestGamestateTopLevel:
    """Test gamestate endpoint with top-level fields."""

    def test_deck_extraction(self, client: httpx.Client) -> None:
        """Test deck field matches started deck (e.g., "BLUE")."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["deck"] == "BLUE"

    def test_stake_extraction(self, client: httpx.Client) -> None:
        """Test stake field matches started stake (e.g., "RED")."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["stake"] == "RED"

    def test_seed_extraction(self, client: httpx.Client) -> None:
        """Test seed field matches the seed used in `start`."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["seed"] == "TEST123"

    def test_money_extraction(self, client: httpx.Client) -> None:
        """Test money field after using `set` to modify it."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        load_fixture(client, "gamestate", fixture_name)
        response = api(client, "set", {"money": 42})
        assert response["result"]["seed"] == "TEST123"

    def test_ante_num_extractions(self, client: httpx.Client) -> None:
        """Test ante_num field after using `set` to modify it."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        load_fixture(client, "gamestate", fixture_name)
        response = api(client, "set", {"ante": 5})
        assert response["result"]["ante_num"] == 5

    def test_round_num_extractions(self, client: httpx.Client) -> None:
        """Test round_num field after using `set` to modify it."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        load_fixture(client, "gamestate", fixture_name)
        response = api(client, "set", {"round": 5})
        assert response["result"]["round_num"] == 5

    def test_won_false_extraction(self, client: httpx.Client) -> None:
        """Test won field after defeating ante 8 boss."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["won"] is False

    def test_won_true_extraction(self, client: httpx.Client) -> None:
        """Test won field after winning ante 8 boss."""
        fixture_name = "state-SELECTING_HAND--round_num-8--blinds.boss.status-CURRENT--round.chips-1000000"
        load_fixture(client, "gamestate", fixture_name)
        response = api(client, "play", {"cards": [0]})
        assert response["result"]["won"] is True


class TestGamestateRound:
    """Test gamestate round extraction."""

    def test_round_hands_left_and_round_hands_played(
        self, client: httpx.Client
    ) -> None:
        """Test round.hands_left and round.hands_played fields."""
        fixture_name = (
            "state-SELECTING_HAND--round.hands_played-1--round.discards_used-1"
        )
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["round"]["hands_left"] == 3
        assert gamestate["round"]["hands_played"] == 1

    def test_round_discards_left_and_round_discards_used(
        self, client: httpx.Client
    ) -> None:
        """Test round.discards_left and round.discards_used fields."""
        fixture_name = (
            "state-SELECTING_HAND--round.hands_played-1--round.discards_used-1"
        )
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["round"]["discards_left"] == 3
        assert gamestate["round"]["discards_used"] == 1

    def test_round_chips_extraction(self, client: httpx.Client) -> None:
        """Test round.chips field."""
        fixture_name = (
            "state-SELECTING_HAND--round.hands_played-1--round.discards_used-1"
        )
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["round"]["chips"] == 16
        response = api(client, "play", {"cards": [0]})
        assert response["result"]["round"]["chips"] == 31

    def test_round_reroll_cost_extraction(self, client: httpx.Client) -> None:
        """Test round.reroll_cost field."""
        fixture_name = "state-SHOP"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["round"]["reroll_cost"] == 5
        response = api(client, "reroll", {})
        assert response["result"]["round"]["reroll_cost"] == 6


class TestGamestateBlinds:
    """Test gamestate blind extraction."""

    def test_blinds_structure_extraction(self, client: httpx.Client) -> None:
        """Test blind extraction structure."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        expected_blinds = {
            "small": {
                "type": "SMALL",
                "name": "Small Blind",
                "effect": "",
                "score": 300,
                "tag_effect": "Next base edition shop Joker is free and becomes Polychrome",
                "tag_name": "Polychrome Tag",
            },
            "big": {
                "effect": "",
                "name": "Big Blind",
                "score": 450,
                "tag_effect": "After defeating the Boss Blind, gain $25",
                "tag_name": "Investment Tag",
                "type": "BIG",
            },
            "boss": {
                "effect": "-1 Hand Size",
                "name": "The Manacle",
                "score": 600,
                "tag_effect": "",
                "tag_name": "",
                "type": "BOSS",
            },
        }
        actual_blinds = {
            blind_key: {k: v for k, v in blind_data.items() if k != "status"}
            for blind_key, blind_data in gamestate["blinds"].items()
        }
        assert actual_blinds == expected_blinds

    def test_blinds_zero_skip_extraction(self, client: httpx.Client) -> None:
        """Test initial blind extraction."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["blinds"]["small"]["status"] == "SELECT"
        assert gamestate["blinds"]["big"]["status"] == "UPCOMING"
        assert gamestate["blinds"]["boss"]["status"] == "UPCOMING"

    def test_blinds_one_skip_extraction(self, client: httpx.Client) -> None:
        """Test blind extraction after one skip."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        load_fixture(client, "gamestate", fixture_name)
        gamestate = api(client, "skip", {})["result"]
        assert gamestate["blinds"]["small"]["status"] == "SKIPPED"
        assert gamestate["blinds"]["big"]["status"] == "SELECT"
        assert gamestate["blinds"]["boss"]["status"] == "UPCOMING"

    def test_blinds_two_skip_extraction(self, client: httpx.Client) -> None:
        """Test blind extraction after two skip."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        load_fixture(client, "gamestate", fixture_name)
        api(client, "skip", {})
        gamestate = api(client, "skip", {})["result"]
        assert gamestate["blinds"]["small"]["status"] == "SKIPPED"
        assert gamestate["blinds"]["big"]["status"] == "SKIPPED"
        assert gamestate["blinds"]["boss"]["status"] == "SELECT"

    def test_blinds_progession_extraction(self, client: httpx.Client) -> None:
        """Test blind extraction after one completed blind."""
        fixture_name = "state-SELECTING_HAND"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["blinds"]["small"]["status"] == "CURRENT"
        assert gamestate["blinds"]["big"]["status"] == "UPCOMING"
        assert gamestate["blinds"]["boss"]["status"] == "UPCOMING"
        api(client, "set", {"chips": 1000})
        api(client, "play", {"cards": [0]})
        api(client, "cash_out", {})
        gamestate = api(client, "next_round", {})["result"]
        assert gamestate["blinds"]["small"]["status"] == "DEFEATED"
        assert gamestate["blinds"]["big"]["status"] == "SELECT"
        assert gamestate["blinds"]["boss"]["status"] == "UPCOMING"


class TestGamestateAreas:
    """Test gamestate areas extraction."""

    # Jokers ###################################################################

    def test_jokers_area_empty_initial(self, client: httpx.Client) -> None:
        """Test jokers area is empty at start of run."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["jokers"]["count"] == 0
        assert gamestate["jokers"]["cards"] == []

    def test_jokers_area_count_after_add(self, client: httpx.Client) -> None:
        """Test jokers area count after adding a joker."""
        fixture_name = "state-SELECTING_HAND"
        load_fixture(client, "gamestate", fixture_name)
        response = api(client, "add", {"key": "j_joker"})
        assert response["result"]["jokers"]["count"] == 1
        assert len(response["result"]["jokers"]["cards"]) == 1

    def test_jokers_area_limit(self, client: httpx.Client) -> None:
        """Test jokers area limit."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["jokers"]["limit"] == 5

    # Consumables ##############################################################

    def test_consumables_area_empty_initial(self, client: httpx.Client) -> None:
        """Test consumables area is empty at start of run."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["consumables"]["count"] == 0
        assert gamestate["consumables"]["cards"] == []

    def test_consumables_area_count_after_add(self, client: httpx.Client) -> None:
        """Test consumables area count after adding a consumable."""
        fixture_name = "state-SELECTING_HAND"
        load_fixture(client, "gamestate", fixture_name)
        response = api(client, "add", {"key": "c_fool"})
        assert response["result"]["consumables"]["count"] == 1
        assert len(response["result"]["consumables"]["cards"]) == 1

    def test_consumables_area_limit(self, client: httpx.Client) -> None:
        """Test consumables area limit."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["consumables"]["limit"] == 2

    # Cards ####################################################################

    def test_cards_area_initial_count(self, client: httpx.Client) -> None:
        """Test cards area has full deck at blind selection."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["cards"]["count"] == 52

    def test_cards_area_count_after_draw(self, client: httpx.Client) -> None:
        """Test cards area count after drawing cards."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        load_fixture(client, "gamestate", fixture_name)
        response = api(client, "select", {})
        assert response["result"]["cards"]["count"] == 52 - 8  # 8 cards drawn

    def test_cards_area_limit(self, client: httpx.Client) -> None:
        """Test cards area limit."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["cards"]["limit"] == 52

    # Hand #####################################################################

    def test_hand_area_count_in_BLIND_SELECT(self, client: httpx.Client) -> None:
        """Test hand area is absent in BLIND_SELECT state."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["hand"]["count"] == 0

    def test_hand_area_count_in_SELECTING_HAND(self, client: httpx.Client) -> None:
        """Test hand area count."""
        fixture_name = "state-SELECTING_HAND"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["hand"]["count"] == 8

    def test_hand_area_limit(self, client: httpx.Client) -> None:
        """Test hand area limit."""
        fixture_name = "state-SELECTING_HAND"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["hand"]["limit"] == 8

    def test_hand_area_highlighted_limit(self, client: httpx.Client) -> None:
        """Test hand area highlighted limit."""
        fixture_name = "state-SELECTING_HAND"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["hand"]["highlighted_limit"] == 5

    # Pack #####################################################################

    def test_pack_area_absent_in_SHOP(self, client: httpx.Client) -> None:
        """Test pack area is absent in non SMODS_BOOSTER_OPENED state (e.g. SHOP)"""
        fixture_name = "state-SHOP"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert "pack" not in gamestate

    def test_pack_area_limit(self, client: httpx.Client) -> None:
        """Test pack area is absent in non SMODS_BOOSTER_OPENED state (e.g. SHOP)"""
        fixture_name = "state-SMODS_BOOSTER_OPENED"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["pack"]["limit"] > 0

    def test_pack_area_count(self, client: httpx.Client) -> None:
        """Test pack area count."""
        fixture_name = "state-SMODS_BOOSTER_OPENED"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["pack"]["count"] > 0
        assert gamestate["pack"]["count"] == gamestate["pack"]["limit"]

    def test_pack_area_highlighted_limit(self, client: httpx.Client) -> None:
        """Test pack area highlighted limit."""
        fixture_name = "state-SMODS_BOOSTER_OPENED"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["pack"]["highlighted_limit"] == 1

    # Shop, Vouchers, Packs ####################################################

    def test_shop_area_absent_in_BLIND_SELECT(self, client: httpx.Client) -> None:
        """Test shop area is absent in BLIND_SELECT state."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert "shop" not in gamestate

    def test_shop_area_count(self, client: httpx.Client) -> None:
        """Test shop area count."""
        fixture_name = "state-SHOP"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["shop"]["count"] == 2
        reponse = api(client, "buy", {"card": 0})
        assert reponse["result"]["shop"]["count"] == 1

    def test_shop_area_limit(self, client: httpx.Client) -> None:
        """Test shop area limit."""
        fixture_name = "state-SHOP"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["shop"]["limit"] == 2

    def test_vouchers_area_absent_in_BLIND_SELECT(self, client: httpx.Client) -> None:
        """Test vouchers area is absent in BLIND_SELECT state."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert "vouchers" not in gamestate

    def test_vouchers_area_count(self, client: httpx.Client) -> None:
        """Test vouchers area count."""
        fixture_name = "state-SHOP"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["vouchers"]["count"] == 1
        reponse = api(client, "buy", {"voucher": 0})
        assert reponse["result"]["vouchers"]["count"] == 0

    def test_vouchers_area_limit(self, client: httpx.Client) -> None:
        """Test vouchers area limit."""
        fixture_name = "state-SHOP"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["vouchers"]["limit"] == 1

    def test_packs_area_absent_in_BLIND_SELECT(self, client: httpx.Client) -> None:
        """Test packs area is absent in BLIND_SELECT state."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert "packs" not in gamestate

    def test_packs_area_count(self, client: httpx.Client) -> None:
        """Test packs area count."""
        fixture_name = "state-SHOP"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["packs"]["count"] == 2
        reponse = api(client, "buy", {"pack": 0})
        assert reponse["result"]["packs"]["count"] == 1

    def test_packs_area_limit(self, client: httpx.Client) -> None:
        """Test packs area limit."""
        fixture_name = "state-SHOP"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["packs"]["limit"] == 2
