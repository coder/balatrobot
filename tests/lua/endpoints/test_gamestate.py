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
