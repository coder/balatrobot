"""Tests for src/lua/endpoints/reroll_boss.lua"""

import httpx

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


class TestRerollBossEndpoint:
    """Test basic reroll_boss endpoint functionality."""

    def test_reroll_boss_with_directors_cut(self, client: httpx.Client) -> None:
        """Test rerolling the Boss blind with Director's Cut."""
        before = load_fixture(
            client, "reroll_boss", "state-BLIND_SELECT--used_vouchers.v_directors_cut"
        )
        assert before["state"] == "BLIND_SELECT"
        assert "v_directors_cut" in before["used_vouchers"]
        assert before["round"]["boss_rerolled"] is False
        response = api(client, "reroll_boss", {})
        after = assert_gamestate_response(response, state="BLIND_SELECT")
        assert after["money"] == before["money"] - 10
        assert after["round"]["boss_rerolled"] is True
        assert after["blinds"]["boss"]["type"] == "BOSS"
        assert after["blinds"]["boss"]["status"] == "UPCOMING"

    def test_reroll_boss_directors_cut_once_per_ante(
        self, client: httpx.Client
    ) -> None:
        """Test that Director's Cut allows only one Boss reroll per ante."""
        load_fixture(
            client, "reroll_boss", "state-BLIND_SELECT--used_vouchers.v_directors_cut"
        )
        assert_gamestate_response(api(client, "reroll_boss", {}))
        assert_error_response(
            api(client, "reroll_boss", {}),
            "NOT_ALLOWED",
            "Boss blind already rerolled this ante",
        )

    def test_reroll_boss_with_retcon(self, client: httpx.Client) -> None:
        """Test that Retcon allows unlimited Boss rerolls."""
        before = load_fixture(
            client, "reroll_boss", "state-BLIND_SELECT--used_vouchers.v_retcon"
        )
        assert "v_retcon" in before["used_vouchers"]
        money = before["money"]
        for _ in range(3):
            response = api(client, "reroll_boss", {})
            after = assert_gamestate_response(response, state="BLIND_SELECT")
            money -= 10
            assert after["money"] == money
            assert after["round"]["boss_rerolled"] is True

    def test_reroll_boss_without_voucher(self, client: httpx.Client) -> None:
        """Test reroll_boss without Director's Cut or Retcon."""
        gamestate = load_fixture(client, "reroll_boss", "state-BLIND_SELECT")
        assert gamestate["state"] == "BLIND_SELECT"
        assert "v_directors_cut" not in gamestate["used_vouchers"]
        assert_error_response(
            api(client, "reroll_boss", {}),
            "NOT_ALLOWED",
            "Cannot reroll Boss blind without Director's Cut or Retcon voucher",
        )

    def test_reroll_boss_insufficient_funds(self, client: httpx.Client) -> None:
        """Test reroll_boss when player has insufficient funds."""
        gamestate = load_fixture(
            client,
            "reroll_boss",
            "state-BLIND_SELECT--used_vouchers.v_directors_cut--money-0",
        )
        assert gamestate["money"] == 0
        assert_error_response(
            api(client, "reroll_boss", {}),
            "NOT_ALLOWED",
            "Not enough dollars to reroll Boss blind",
        )

    def test_reroll_boss_with_credit_card_joker(self, client: httpx.Client) -> None:
        """Test reroll_boss with Credit Card joker (can go negative)."""
        gamestate = load_fixture(
            client, "reroll_boss", "state-SHOP--used_vouchers.v_directors_cut"
        )
        assert gamestate["state"] == "SHOP"
        assert_gamestate_response(api(client, "add", {"key": "j_credit_card"}))
        assert_gamestate_response(api(client, "set", {"money": 0}))
        assert_gamestate_response(api(client, "next_round", {}), state="BLIND_SELECT")
        response = api(client, "reroll_boss", {})
        after = assert_gamestate_response(response, state="BLIND_SELECT")
        assert after["money"] == -10

    def test_reroll_boss_resets_next_ante(self, client: httpx.Client) -> None:
        """Test that the Director's Cut reroll is available again next ante."""
        load_fixture(
            client, "reroll_boss", "state-BLIND_SELECT--used_vouchers.v_directors_cut"
        )
        gamestate = assert_gamestate_response(api(client, "reroll_boss", {}))
        assert gamestate["round"]["boss_rerolled"] is True
        ante = gamestate["ante_num"]
        # Beat the Big and Boss blinds (the fixture already beat the Small one)
        for _ in range(2):
            assert_gamestate_response(api(client, "select", {}))
            assert_gamestate_response(api(client, "set", {"chips": 1000000}))
            assert_gamestate_response(api(client, "play", {"cards": [0]}))
            assert_gamestate_response(api(client, "cash_out", {}))
            assert_gamestate_response(api(client, "set", {"money": 50}))
            gamestate = assert_gamestate_response(api(client, "next_round", {}))
        assert gamestate["state"] == "BLIND_SELECT"
        assert gamestate["ante_num"] == ante + 1
        assert gamestate["round"]["boss_rerolled"] is False
        response = api(client, "reroll_boss", {})
        after = assert_gamestate_response(response, state="BLIND_SELECT")
        assert after["round"]["boss_rerolled"] is True


class TestRerollBossEndpointStateRequirements:
    """Test reroll_boss endpoint state requirements."""

    def test_reroll_boss_from_SHOP(self, client: httpx.Client):
        """Test that reroll_boss fails when not in BLIND_SELECT state."""
        gamestate = load_fixture(
            client, "reroll_boss", "state-SHOP--used_vouchers.v_directors_cut"
        )
        assert gamestate["state"] == "SHOP"
        assert_error_response(
            api(client, "reroll_boss", {}),
            "INVALID_STATE",
            "Method 'reroll_boss' requires one of these states: BLIND_SELECT",
        )
