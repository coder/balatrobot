"""Tests for src/lua/endpoints/gamestate.lua"""

import re

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

    class TestGamestateAreasJokers:
        """Test gamestate jokers area extraction."""

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

    class TestGamestateAreasConsumables:
        """Test gamestate consumables area extraction."""

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

    class TestGamestateAreasCards:
        """Test gamestate cards area extraction."""

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

    class TestGamestateAreasHand:
        """Test gamestate hand area extraction."""

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

    class TestGamestateAreasPack:
        """Test gamestate pack area extraction."""

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

    class TestGamestateAreasShop:
        """Test gamestate shop area extraction."""

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

    class TestGamestateAreasVouchers:
        """Test gamestate vouchers area extraction."""

        def test_vouchers_area_absent_in_BLIND_SELECT(
            self, client: httpx.Client
        ) -> None:
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

    class TestGamestateAreasPacks:
        """Test gamestate packs area extraction."""

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


class TestGamestateCards:
    """Test gamestate cards."""

    class TestGamestateCardId:
        """Test gamestate card id."""

        def test_card_ids_in_hand(self, client: httpx.Client) -> None:
            """Test card ids in hand."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            cards = gamestate["hand"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

        def test_card_ids_in_jokers(self, client: httpx.Client) -> None:
            """Test card ids in jokers."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            gamestate = assert_gamestate_response(response)
            cards = gamestate["jokers"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

        def test_card_ids_in_cards(self, client: httpx.Client) -> None:
            """Test card ids in cards."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            cards = gamestate["cards"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

        def test_card_ids_in_consumables(self, client: httpx.Client) -> None:
            """Test card ids in consumables."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_fool"})
            gamestate = assert_gamestate_response(response)
            cards = gamestate["consumables"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

        def test_card_ids_in_pack(self, client: httpx.Client) -> None:
            """Test card ids in pack."""
            fixture_name = "state-SMODS_BOOSTER_OPENED"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            cards = gamestate["pack"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

        def test_card_ids_in_shop(self, client: httpx.Client) -> None:
            """Test card ids in shop."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            cards = gamestate["shop"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

        def test_card_ids_in_vouchers(self, client: httpx.Client) -> None:
            """Test card ids in vouchers."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            cards = gamestate["vouchers"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

        def test_card_ids_in_packs(self, client: httpx.Client) -> None:
            """Test card ids in packs."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            cards = gamestate["packs"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

    class TestGamestateCardKey:
        """Test gamestate card key."""

        def test_card_key_joker_format(self, client: httpx.Client) -> None:
            """Test joker card key format matches pattern ^j_[a-z_]+$."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            joker = response["result"]["jokers"]["cards"][0]
            assert re.match(r"^j_[a-z_]+$", joker["key"])

        def test_card_key_tarot_format(self, client: httpx.Client) -> None:
            """Test tarot card key format matches pattern ^c_[a-z_]+$."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_fool"})
            tarot = response["result"]["consumables"]["cards"][0]
            assert re.match(r"^c_[a-z_]+$", tarot["key"])

        def test_card_key_planet_format(self, client: httpx.Client) -> None:
            """Test planet card key format matches pattern ^c_[a-z_]+$."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_pluto"})
            planet = response["result"]["consumables"]["cards"][0]
            assert re.match(r"^c_[a-z_]+$", planet["key"])

        def test_card_key_spectral_format(self, client: httpx.Client) -> None:
            """Test spectral card key format matches pattern ^c_[a-z_]+$."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_familiar"})
            spectral = response["result"]["consumables"]["cards"][0]
            assert re.match(r"^c_[a-z_]+$", spectral["key"])

        def test_card_key_voucher_format(self, client: httpx.Client) -> None:
            """Test voucher card key format matches pattern ^v_[a-z_]+$."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            vouchers = gamestate["vouchers"]["cards"]
            for voucher in vouchers:
                assert re.match(r"^v_[a-z_]+$", voucher["key"])

        def test_card_key_booster_format(self, client: httpx.Client) -> None:
            """Test booster pack key format matches pattern ^p_[a-z_0-9]+$."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            packs = gamestate["packs"]["cards"]
            for pack in packs:
                assert re.match(r"^p_[a-z_0-9]+$", pack["key"])

        def test_card_key_playing_card_format(self, client: httpx.Client) -> None:
            """Test playing card key format matches pattern ^[HDCS]_[2-9TJQKA]$."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            hand_cards = gamestate["hand"]["cards"]
            for card in hand_cards:
                assert re.match(r"^[HDCS]_[2-9TJQKA]$", card["key"])

    class TestGamestateCardSet:
        """Test gamestate card set."""

        def test_card_set_default(self, client: httpx.Client) -> None:
            """Test default playing cards have DEFAULT set."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            card = gamestate["hand"]["cards"][0]
            assert card["set"] == "DEFAULT"

        def test_card_set_enhanced(self, client: httpx.Client) -> None:
            """Test enhanced playing cards have ENHANCED set."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "H_A", "enhancement": "BONUS"})
            # Find the enhanced card (last card in hand)
            cards = response["result"]["hand"]["cards"]
            card = cards[-1]
            assert card["set"] == "ENHANCED"

        def test_card_set_joker(self, client: httpx.Client) -> None:
            """Test joker cards have JOKER set."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            joker = response["result"]["jokers"]["cards"][0]
            assert joker["set"] == "JOKER"

        def test_card_set_tarot(self, client: httpx.Client) -> None:
            """Test tarot cards have TAROT set."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_fool"})
            tarot = response["result"]["consumables"]["cards"][0]
            assert tarot["set"] == "TAROT"

        def test_card_set_planet(self, client: httpx.Client) -> None:
            """Test planet cards have PLANET set."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_pluto"})
            planet = response["result"]["consumables"]["cards"][0]
            assert planet["set"] == "PLANET"

        def test_card_set_spectral(self, client: httpx.Client) -> None:
            """Test spectral cards have SPECTRAL set."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_familiar"})
            spectral = response["result"]["consumables"]["cards"][0]
            assert spectral["set"] == "SPECTRAL"

        def test_card_set_voucher(self, client: httpx.Client) -> None:
            """Test voucher cards have VOUCHER set."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            voucher = gamestate["vouchers"]["cards"][0]
            assert voucher["set"] == "VOUCHER"

        def test_card_set_booster(self, client: httpx.Client) -> None:
            """Test booster packs have BOOSTER set."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            pack = gamestate["packs"]["cards"][0]
            assert pack["set"] == "BOOSTER"

    class TestGamestateCardLabel:
        """Test gamestate card label."""

        def test_card_label_is_string(self, client: httpx.Client) -> None:
            """Test card labels are non-empty strings."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            hand_cards = gamestate["hand"]["cards"]

            # Verify multiple cards have valid string labels
            for card in hand_cards[:3]:
                assert "label" in card
                assert isinstance(card["label"], str)
                assert len(card["label"]) > 0

        def test_card_label_joker(self, client: httpx.Client) -> None:
            """Test joker card has human-readable label."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            joker = response["result"]["jokers"]["cards"][0]

            assert "label" in joker
            assert joker["label"] == "Joker"

        def test_card_label_playing_card(self, client: httpx.Client) -> None:
            """Test playing cards have descriptive labels (Base Card or enhancement)."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            hand_cards = gamestate["hand"]["cards"]

            # Verify first card has a valid card type label
            card = hand_cards[0]

            assert "label" in card
            label = card["label"]

            # Validate label is one of the valid playing card types
            # fmt: off
            valid_labels = [
                "Base Card", "Steel Card", "Glass Card", "Gold Card", "Stone Card",
                "Lucky Card", "Bonus Card", "Mult Card", "Wild Card",
            ]
            # fmt: on
            assert label in valid_labels

    class TestGamestateCardValue:
        """Test gamestate card value."""

        def test_card_value_suit_valid_enum(self, client: httpx.Client) -> None:
            """Test playing cards have valid suit enum (H, D, C, S)."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            valid_suits = ["H", "D", "C", "S"]
            for card in gamestate["hand"]["cards"]:
                assert card["value"]["suit"] in valid_suits

        def test_card_value_suit_present_for_playing_cards(
            self, client: httpx.Client
        ) -> None:
            """Test all playing cards have suit field in value."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            for card in gamestate["hand"]["cards"]:
                assert "suit" in card["value"]
                assert card["value"]["suit"] is not None

        def test_card_value_suit_absent_for_jokers(self, client: httpx.Client) -> None:
            """Test jokers don't have suit field."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            joker = response["result"]["jokers"]["cards"][0]
            assert joker["value"].get("suit") is None

        def test_card_value_rank_valid_enum(self, client: httpx.Client) -> None:
            """Test playing cards have valid rank enum."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            # fmt: off
            valid_ranks = [
                "2", "3", "4", "5", "6", "7", "8",
                "9", "T", "J", "Q", "K", "A",
            ]
            # fmt: on
            for card in gamestate["hand"]["cards"]:
                assert card["value"]["rank"] in valid_ranks

        def test_card_value_rank_present_for_playing_cards(
            self, client: httpx.Client
        ) -> None:
            """Test all playing cards have rank field in value."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            for card in gamestate["hand"]["cards"]:
                assert "rank" in card["value"]
                assert card["value"]["rank"] is not None

        def test_card_value_rank_absent_for_consumables(
            self, client: httpx.Client
        ) -> None:
            """Test consumables don't have rank field."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_fool"})
            tarot = response["result"]["consumables"]["cards"][0]
            assert tarot["value"].get("rank") is None

        def test_card_value_effect_is_string(self, client: httpx.Client) -> None:
            """Test effect field is always a string."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            for card in gamestate["hand"]["cards"]:
                assert isinstance(card["value"]["effect"], str)

        def test_card_value_effect_joker(self, client: httpx.Client) -> None:
            """Test joker effect description."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            joker = response["result"]["jokers"]["cards"][0]
            assert joker["value"]["effect"] == "+4 Mult"

        def test_card_value_effect_tarot(self, client: httpx.Client) -> None:
            """Test tarot effect description."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_fool"})
            tarot = response["result"]["consumables"]["cards"][0]
            expected = (
                "Creates the last Tarot or Planet card "
                "used during this run The Fool excluded "
            )
            assert tarot["value"]["effect"] == expected

        def test_card_value_effect_planet(self, client: httpx.Client) -> None:
            """Test planet effect description."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_pluto"})
            planet = response["result"]["consumables"]["cards"][0]
            assert (
                planet["value"]["effect"]
                == "(lvl.1) Level up High Card +1 Mult and +10 chips"
            )

    class TestGamestateCardModifier:
        """Test gamestate card modifier."""

        def test_modifier_structure_exists(self, client: httpx.Client) -> None:
            """Test card has modifier field."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            card = gamestate["hand"]["cards"][0]
            assert "modifier" in card

        def test_modifier_absent_fields(self, client: httpx.Client) -> None:
            """Test unmodified card has empty modifier (fields omitted when not set)."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            card = gamestate["hand"]["cards"][0]
            assert card["modifier"] == []

    class TestGamestateCardState:
        """Test gamestate card state."""

        # TODO: add later

    class TestGamestateCardCost:
        """Test gamestate card cost."""

        def test_cost_buy_in_shop(self, client: httpx.Client) -> None:
            """Test shop card has cost['buy'] > 0."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            shop_cards = gamestate["shop"]["cards"]

            assert len(shop_cards) > 0, "Shop should have at least one card"
            card = shop_cards[0]
            assert isinstance(card["cost"]["buy"], int)
            assert card["cost"]["buy"] > 0

        def test_cost_sell_owned_joker(self, client: httpx.Client) -> None:
            """Test added joker has cost['sell'] > 0."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            joker = response["result"]["jokers"]["cards"][0]

            assert isinstance(joker["cost"]["sell"], int)
            assert joker["cost"]["sell"] > 0


class TestGamestateCardModifiers:
    """Test gamestate card modifiers."""

    class TestGamestateCardModifierSeal:
        """Test gamestate card modifier seal."""

        # TODO: add later

    class TestGamestateCardModifierEdition:
        """Test gamestate card modifier edition."""

        # TODO: add later

    class TestGamestateCardModifierEnhancement:
        """Test gamestate card modifier enhancement."""

        # TODO: add later

    class TestGamestateCardModifierEternal:
        """Test gamestate card modifier eternal."""

        # TODO: add later

    class TestGamestateCardModifierPerishable:
        """Test gamestate card modifier perishable."""

        # TODO: add later

    class TestGamestateCardModifierRental:
        """Test gamestate card modifier rental."""

        # TODO: add later


class TestGamestateCardStates:
    """Test gamestate card states."""

    class TestGamestateCardStateDebuff:
        """Test gamestate card state debuff."""

        # TODO: add later

    class TestGamestateCardStateHidden:
        """Test gamestate card state hidden."""

        # TODO: add later

    class TestGamestateCardStateHighlight:
        """Test gamestate card state highlight."""

        # TODO: add later


class TestGamestateCardCosts:
    """Test gamestate card costs."""

    class TestGamestateCardCostSell:
        """Test gamestate card cost sell."""

        # TODO: add later

    class TestGamestateCardCostBuy:
        """Test gamestate card cost buy."""

        # TODO: add later
