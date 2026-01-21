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
        fixture_name = (
            "state-SELECTING_HAND--round.hands_played-1--round.discards_used-1"
        )
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
