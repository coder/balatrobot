"""Tests for src/lua/endpoints/reroll_boss.lua"""

import httpx

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


class TestRerollBossEndpoint:
    """Test reroll_boss endpoint functionality."""

    def test_reroll_boss_happy_path_directors_cut(self, client: httpx.Client) -> None:
        """Director's Cut: reroll succeeds, costs $10, boss key changes at ante 1."""
        before = load_fixture(
            client,
            "reroll_boss",
            "state-BLIND_SELECT--blinds.boss.status-SELECT--used_vouchers.v_directors_cut-1--money-20",
        )
        assert before["state"] == "BLIND_SELECT"
        assert before["money"] == 20
        assert "v_directors_cut" in before["used_vouchers"]
        assert before["blinds"]["boss"]["status"] == "SELECT"
        # Reroll is available before the action
        assert before["blinds"]["boss"]["reroll_available"] is True
        original_boss_key = before["blinds"]["boss"]["key"]

        response = api(client, "reroll_boss", {})
        after = assert_gamestate_response(response, state="BLIND_SELECT")
        # Primary success signal: $10 spent (predicate α only promises lock + charge)
        assert after["money"] == 10
        # Secondary check: boss key differs (safe at ante 1: min-bosses_used
        # filter + deterministic seed guarantees a fresh pick)
        assert after["blinds"]["boss"]["key"] != original_boss_key

    def test_reroll_boss_wrong_state(self, client: httpx.Client) -> None:
        """reroll_boss requires BLIND_SELECT state."""
        gamestate = load_fixture(client, "reroll_boss", "state-SHOP")
        assert gamestate["state"] == "SHOP"
        assert_error_response(
            api(client, "reroll_boss", {}),
            "INVALID_STATE",
            "Method 'reroll_boss' requires one of these states: BLIND_SELECT",
        )

    def test_reroll_boss_no_voucher(self, client: httpx.Client) -> None:
        """reroll_boss without Director's Cut or Retcon voucher is not allowed."""
        gamestate = load_fixture(
            client, "reroll_boss", "state-BLIND_SELECT--blinds.boss.status-SELECT"
        )
        assert gamestate["state"] == "BLIND_SELECT"
        assert gamestate["blinds"]["boss"]["status"] == "SELECT"
        assert gamestate["blinds"]["boss"]["reroll_available"] is False
        assert_error_response(
            api(client, "reroll_boss", {}),
            "NOT_ALLOWED",
            "requires the Director's Cut or Retcon voucher",
        )

    def test_reroll_boss_cannot_afford(self, client: httpx.Client) -> None:
        """reroll_boss with insufficient dollars is not allowed."""
        gamestate = load_fixture(
            client,
            "reroll_boss",
            "state-BLIND_SELECT--blinds.boss.status-SELECT--used_vouchers.v_directors_cut-1--money-5",
        )
        assert gamestate["state"] == "BLIND_SELECT"
        assert gamestate["money"] == 5
        assert gamestate["blinds"]["boss"]["reroll_available"] is False
        assert_error_response(
            api(client, "reroll_boss", {}),
            "NOT_ALLOWED",
            "Not enough dollars to reroll boss",
        )

    def test_reroll_boss_directors_cut_per_ante_limit(
        self, client: httpx.Client
    ) -> None:
        """Director's Cut allows only one reroll per ante."""
        gamestate = load_fixture(
            client,
            "reroll_boss",
            "state-BLIND_SELECT--blinds.boss.status-SELECT--used_vouchers.v_directors_cut-1--money-20",
        )
        assert gamestate["money"] == 20

        # First reroll succeeds: $20 -> $10
        response = api(client, "reroll_boss", {})
        after_first = assert_gamestate_response(response, state="BLIND_SELECT")
        assert after_first["money"] == 10
        # Per-ante limit reached: reroll no longer available
        assert after_first["blinds"]["boss"]["reroll_available"] is False

        # Second reroll same ante is not allowed
        assert_error_response(
            api(client, "reroll_boss", {}),
            "NOT_ALLOWED",
            "one Reroll Boss Blind per ante; already used",
        )

    def test_reroll_boss_retcon_unlimited(self, client: httpx.Client) -> None:
        """Retcon voucher allows unlimited rerolls per ante."""
        gamestate = load_fixture(
            client,
            "reroll_boss",
            "state-BLIND_SELECT--blinds.boss.status-SELECT--used_vouchers.v_retcon-1--money-30",
        )
        assert gamestate["money"] == 30
        assert "v_retcon" in gamestate["used_vouchers"]

        # First reroll succeeds: $30 -> $20
        response = api(client, "reroll_boss", {})
        after_first = assert_gamestate_response(response, state="BLIND_SELECT")
        assert after_first["money"] == 20
        # Retcon has no per-ante limit: still available
        assert after_first["blinds"]["boss"]["reroll_available"] is True

        # Second reroll same ante also succeeds: $20 -> $10
        response = api(client, "reroll_boss", {})
        after_second = assert_gamestate_response(response, state="BLIND_SELECT")
        assert after_second["money"] == 10
