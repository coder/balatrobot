"""Tests for src/lua/endpoints/pack.lua"""

import httpx
import pytest

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)

# =============================================================================
# Pack Constants
# =============================================================================

NORMAL_PACKS = (
    "p_arcana_normal_1",
    "p_celestial_normal_1",
    "p_spectral_normal_1",
    "p_standard_normal_1",
    "p_buffoon_normal_1",
)
JUMBO_PACKS = (
    "p_arcana_jumbo_1",
    "p_celestial_jumbo_1",
    "p_spectral_jumbo_1",
    "p_standard_jumbo_1",
    "p_buffoon_jumbo_1",
)
MEGA_PACKS = (
    "p_arcana_mega_1",
    "p_celestial_mega_1",
    "p_spectral_mega_1",
    "p_standard_mega_1",
    "p_buffoon_mega_1",
)

ARCANA_PACKS = ("p_arcana_normal_1", "p_arcana_jumbo_1", "p_arcana_mega_1")
CELESTIAL_PACKS = ("p_celestial_normal_1", "p_celestial_jumbo_1", "p_celestial_mega_1")
SPECTRAL_PACKS = ("p_spectral_normal_1", "p_spectral_jumbo_1", "p_spectral_mega_1")
STANDARD_PACKS = ("p_standard_normal_1", "p_standard_jumbo_1", "p_standard_mega_1")
BUFFOON_PACKS = ("p_buffoon_normal_1", "p_buffoon_jumbo_1", "p_buffoon_mega_1")

PACKS = NORMAL_PACKS + JUMBO_PACKS + MEGA_PACKS


# =============================================================================
# Argument Validation Tests
# =============================================================================


class TestPackEndpointArguments:
    """Tests for argument validation (pack.lua lines 85-108)."""

    def test_pack_no_args(self, client: httpx.Client) -> None:
        """Test pack endpoint with no arguments."""
        load_fixture(client, "pack", "state-SHOP--packs.count-0")
        api(client, "add", {"key": "p_arcana_normal_1"})
        result = api(client, "buy", {"pack": 0})
        assert_gamestate_response(result)

        assert_error_response(
            api(client, "pack", {}),
            "BAD_REQUEST",
            "Invalid arguments. You must provide one of: card, skip",
        )

    def test_pack_both_args(self, client: httpx.Client) -> None:
        """Test pack endpoint with both card and skip."""
        load_fixture(client, "pack", "state-SHOP--packs.count-0")
        api(client, "add", {"key": "p_arcana_normal_1"})
        result = api(client, "buy", {"pack": 0})
        assert_gamestate_response(result)

        assert_error_response(
            api(client, "pack", {"card": 0, "skip": True}),
            "BAD_REQUEST",
            "Invalid arguments. Cannot provide both card and skip",
        )


# =============================================================================
# Card Index Validation Tests
# =============================================================================


class TestPackEndpointCardIndex:
    """Tests for card index validation (pack.lua lines 123-131)."""

    def test_pack_invalid_card_index_high(self, client: httpx.Client) -> None:
        """Test pack endpoint with card index too high."""
        load_fixture(client, "pack", "state-SHOP--packs.count-0")
        api(client, "add", {"key": "p_arcana_normal_1"})
        result = api(client, "buy", {"pack": 0})
        gamestate = assert_gamestate_response(result)
        pack_count = gamestate["pack"]["count"]
        assert pack_count > 0

        assert_error_response(
            api(client, "pack", {"card": 999}),
            "BAD_REQUEST",
            f"Card index out of range. Index: 999, Available cards: {pack_count}",
        )

    def test_pack_negative_card_index(self, client: httpx.Client) -> None:
        """Test pack endpoint with negative card index."""
        load_fixture(client, "pack", "state-SHOP--packs.count-0")
        api(client, "add", {"key": "p_arcana_normal_1"})
        result = api(client, "buy", {"pack": 0})
        gamestate = assert_gamestate_response(result)
        pack_count = gamestate["pack"]["count"]
        assert pack_count > 0

        # Negative index should fail validation
        assert_error_response(
            api(client, "pack", {"card": -1}),
            "BAD_REQUEST",
            f"Card index out of range. Index: -1, Available cards: {pack_count}",
        )

    def test_pack_last_valid_index(self, client: httpx.Client) -> None:
        """Test selecting the last card in a pack succeeds."""
        load_fixture(client, "pack", "state-SHOP--packs.count-0")
        # Use standard normal pack - playing cards don't require targets
        api(client, "add", {"key": "p_standard_normal_1"})
        result = api(client, "buy", {"pack": 0})
        before = assert_gamestate_response(result)
        pack_count = before["pack"]["count"]
        assert pack_count > 0

        # Select the last card (0-indexed, so pack_count - 1)
        last_index = pack_count - 1
        result = api(client, "pack", {"card": last_index})
        # Verify selection succeeded by checking deck gained a card
        after = assert_gamestate_response(result)
        assert after["cards"]["count"] == before["cards"]["count"] + 1


# =============================================================================
# Joker Slot Validation Tests
# =============================================================================


class TestPackEndpointJokerSlots:
    """Tests for joker slot validation (pack.lua lines 136-150)."""

    @pytest.mark.dev
    @pytest.mark.skip(reason="Requires fixture: buffoon pack open with 5 jokers")
    def test_pack_joker_slots_full(self, client: httpx.Client) -> None:
        """Test selecting joker when slots are full fails."""
        # Expected fixture: state-SMODS_BOOSTER_OPENED--pack.type-buffoon--jokers.count-5
        # Test implementation:
        # load_fixture(client, "pack", "state-SMODS_BOOSTER_OPENED--pack.type-buffoon--jokers.count-5")
        # assert_error_response(
        #     api(client, "pack", {"card": 0}),
        #     "NOT_ALLOWED",
        #     "Cannot select joker, joker slots are full. Current: 5, Limit: 5",
        # )
        pass

    @pytest.mark.dev
    @pytest.mark.skip(reason="Requires fixture: buffoon pack open with 4 jokers")
    def test_pack_joker_slots_available(self, client: httpx.Client) -> None:
        """Test selecting joker when slots available succeeds."""
        # Expected fixture: state-SMODS_BOOSTER_OPENED--pack.type-buffoon--jokers.count-4
        # Test implementation:
        # load_fixture(client, "pack", "state-SMODS_BOOSTER_OPENED--pack.type-buffoon--jokers.count-4")
        # before = api(client, "gamestate", {})
        # result = api(client, "pack", {"card": 0})
        # after = assert_gamestate_response(result, state="SHOP")
        # assert after["jokers"]["count"] == before["result"]["jokers"]["count"] + 1
        pass


# =============================================================================
# Target Validation Tests
# =============================================================================


class TestPackEndpointTargets:
    """Tests for consumable target validation (pack.lua lines 152-217)."""

    # -------------------------------------------------------------------------
    # Tarot cards with target requirements (min/max highlighted)
    # -------------------------------------------------------------------------

    def test_pack_tarot_with_valid_targets(self, client: httpx.Client) -> None:
        """Test selecting tarot card with valid target count."""
        load_fixture(client, "pack", "state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_heirophant")
        print("Loaded fixture for tarot card with targets")
        result = api(client, "pack", {"card": 0, "targets": [0, 1]})
        assert_gamestate_response(result, state="SHOP")

    def test_pack_tarot_missing_targets(self, client: httpx.Client) -> None:
        """Test selecting tarot card without required targets fails."""
        load_fixture(client, "pack", "state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_heirophant")
        assert_error_response(
            api(client, "pack", {"card": 0}),
            "BAD_REQUEST",
            "Card 'c_heirophant' requires 1-2 target card(s). Provided: 0",
        )

    @pytest.mark.dev
    @pytest.mark.skip(
        reason="Requires fixture: arcana pack with tarot requiring max 2 targets"
    )
    def test_pack_tarot_too_many_targets(self, client: httpx.Client) -> None:
        """Test selecting tarot card with too many targets fails."""
        # Expected fixture: state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_heirophant
        # Test implementation:
        # load_fixture(client, "pack", "state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_heirophant")
        # assert_error_response(
        #     api(client, "pack", {"card": 0, "targets": [0, 1, 2, 3]}),
        #     "BAD_REQUEST",
        #     "Card 'c_heirophant' requires 1-2 target card(s). Provided: 4",
        # )
        pass

    @pytest.mark.dev
    @pytest.mark.skip(
        reason="Requires fixture: arcana pack with any tarot requiring targets"
    )
    def test_pack_target_index_out_of_range(self, client: httpx.Client) -> None:
        """Test selecting tarot with target index out of range fails."""
        # Expected fixture: state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_heirophant
        # Test implementation:
        # load_fixture(client, "pack", "state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_heirophant")
        # assert_error_response(
        #     api(client, "pack", {"card": 0, "targets": [99]}),
        #     "BAD_REQUEST",
        #     "Target card index out of range. Index: 99, Hand size: 8",
        # )
        pass

    # -------------------------------------------------------------------------
    # Aura special case (exactly 1 target)
    # -------------------------------------------------------------------------

    @pytest.mark.dev
    @pytest.mark.skip(reason="Requires fixture: spectral pack with c_aura")
    def test_pack_aura_no_targets(self, client: httpx.Client) -> None:
        """Test selecting Aura without targets fails."""
        # Expected fixture: state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_aura
        # Test implementation:
        # load_fixture(client, "pack", "state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_aura")
        # assert_error_response(
        #     api(client, "pack", {"card": 0}),
        #     "BAD_REQUEST",
        #     "Card 'c_aura' requires exactly 1 target card(s). Provided: 0",
        # )
        pass

    @pytest.mark.dev
    @pytest.mark.skip(reason="Requires fixture: spectral pack with c_aura")
    def test_pack_aura_one_target(self, client: httpx.Client) -> None:
        """Test selecting Aura with exactly 1 target succeeds."""
        # Expected fixture: state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_aura
        # Test implementation:
        # load_fixture(client, "pack", "state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_aura")
        # result = api(client, "pack", {"card": 0, "targets": [0]})
        # assert_gamestate_response(result, state="SHOP")
        pass

    @pytest.mark.dev
    @pytest.mark.skip(reason="Requires fixture: spectral pack with c_aura")
    def test_pack_aura_two_targets(self, client: httpx.Client) -> None:
        """Test selecting Aura with 2 targets fails."""
        # Expected fixture: state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_aura
        # Test implementation:
        # load_fixture(client, "pack", "state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_aura")
        # assert_error_response(
        #     api(client, "pack", {"card": 0, "targets": [0, 1]}),
        #     "BAD_REQUEST",
        #     "Card 'c_aura' requires exactly 1 target card(s). Provided: 2",
        # )
        pass

    # -------------------------------------------------------------------------
    # Ankh special case (requires joker)
    # -------------------------------------------------------------------------

    @pytest.mark.dev
    @pytest.mark.skip(reason="Requires fixture: spectral pack with c_ankh and 0 jokers")
    def test_pack_ankh_no_jokers(self, client: httpx.Client) -> None:
        """Test selecting Ankh without jokers fails."""
        # Expected fixture: state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_ankh--jokers.count-0
        # Test implementation:
        # load_fixture(client, "pack", "state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_ankh--jokers.count-0")
        # assert_error_response(
        #     api(client, "pack", {"card": 0}),
        #     "NOT_ALLOWED",
        #     "Card 'c_ankh' requires at least 1 joker. Current: 0",
        # )
        pass

    @pytest.mark.dev
    @pytest.mark.skip(reason="Requires fixture: spectral pack with c_ankh and 1 joker")
    def test_pack_ankh_with_joker(self, client: httpx.Client) -> None:
        """Test selecting Ankh with joker succeeds."""
        # Expected fixture: state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_ankh--jokers.count-1
        # Test implementation:
        # load_fixture(client, "pack", "state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_ankh--jokers.count-1")
        # result = api(client, "pack", {"card": 0})
        # gamestate = assert_gamestate_response(result, state="SHOP")
        # assert gamestate["jokers"]["count"] == 2  # Original + copy
        pass


# =============================================================================
# Card Selection Tests (by pack type)
# =============================================================================


class TestPackEndpointSelection:
    """Tests for successful card selection by pack type."""

    @pytest.mark.parametrize("pack_key", ARCANA_PACKS)
    def test_pack_arcana_pack(self, client: httpx.Client, pack_key: str) -> None:
        """Test selecting one card from an arcana pack.

        Note: Card 0 in the pack is always Hermit so we check for +$20.
        """
        load_fixture(client, "pack", "state-SHOP--packs.count-0")
        assert_gamestate_response(api(client, "add", {"key": pack_key}))
        result = api(client, "buy", {"pack": 0})
        before = assert_gamestate_response(result)

        result = api(client, "pack", {"card": 0})
        after = assert_gamestate_response(result)
        assert before["money"] + 20 == after["money"]

    @pytest.mark.parametrize("pack_key", CELESTIAL_PACKS)
    def test_pack_planet_pack(self, client: httpx.Client, pack_key: str) -> None:
        """Test selecting one card from a celestial pack.

        Note: Card 0 in the pack is always Saturn so we check for +1 level for Straight.
        """
        load_fixture(client, "pack", "state-SHOP--packs.count-0")
        assert_gamestate_response(api(client, "add", {"key": pack_key}))
        result = api(client, "buy", {"pack": 0})
        before = assert_gamestate_response(result)

        result = api(client, "pack", {"card": 0})
        after = assert_gamestate_response(result)
        assert (
            before["hands"]["Straight"]["level"] + 1
            == after["hands"]["Straight"]["level"]
        )

    @pytest.mark.parametrize("pack_key", SPECTRAL_PACKS)
    def test_pack_spectral_pack(self, client: httpx.Client, pack_key: str) -> None:
        """Test selecting one card from a spectral pack.

        Note: Card 0 in the pack is always Immolate so we check for +$20 and -5 deck cards.
        """
        load_fixture(client, "pack", "state-SHOP--packs.count-0")
        assert_gamestate_response(api(client, "add", {"key": pack_key}))
        result = api(client, "buy", {"pack": 0})
        before = assert_gamestate_response(result)

        result = api(client, "pack", {"card": 0})
        after = assert_gamestate_response(result)
        assert before["money"] + 20 == after["money"]
        assert before["hand"]["count"] - 5 == after["hand"]["count"]

    @pytest.mark.parametrize("pack_key", STANDARD_PACKS)
    def test_pack_standard_pack(self, client: httpx.Client, pack_key: str) -> None:
        """Test selecting one card from a standard pack.

        Note: We just check that one card is added to the deck.
        """
        load_fixture(client, "pack", "state-SHOP--packs.count-0")
        assert_gamestate_response(api(client, "add", {"key": pack_key}))
        result = api(client, "buy", {"pack": 0})
        before = assert_gamestate_response(result)

        result = api(client, "pack", {"card": 0})
        after = assert_gamestate_response(result)
        assert before["cards"]["count"] + 1 == after["cards"]["count"]

    @pytest.mark.parametrize("pack_key", BUFFOON_PACKS)
    def test_pack_buffoon_pack(self, client: httpx.Client, pack_key: str) -> None:
        """Test selecting one card from a buffoon pack.

        Note: We just check that joker count is increased by 1.
        """
        load_fixture(client, "pack", "state-SHOP--packs.count-0")
        assert_gamestate_response(api(client, "add", {"key": pack_key}))
        result = api(client, "buy", {"pack": 0})
        before = assert_gamestate_response(result)

        result = api(client, "pack", {"card": 0})
        after = assert_gamestate_response(result)
        assert before["jokers"]["count"] + 1 == after["jokers"]["count"]


# =============================================================================
# Mega Pack Multi-Selection Tests
# =============================================================================


class TestPackEndpointMegaPack:
    """Tests for mega pack multi-selection behavior (pack.lua lines 233-256)."""

    @pytest.mark.dev
    @pytest.mark.skip(reason="Requires fixture: mega pack already opened")
    def test_mega_pack_first_selection_keeps_open(self, client: httpx.Client) -> None:
        """Test that first selection in mega pack keeps pack open."""
        # Expected fixture: state-SMODS_BOOSTER_OPENED--pack.key-p_celestial_mega_1
        # Test implementation:
        # load_fixture(client, "pack", "state-SMODS_BOOSTER_OPENED--pack.key-p_celestial_mega_1")
        # result = api(client, "pack", {"card": 0})
        # gamestate = assert_gamestate_response(result, state="SMODS_BOOSTER_OPENED")
        # assert "pack" in gamestate
        # assert gamestate["pack"]["count"] > 0
        pass

    @pytest.mark.dev
    @pytest.mark.skip(reason="Requires fixture: mega pack already opened")
    def test_mega_pack_second_selection_closes(self, client: httpx.Client) -> None:
        """Test that second selection in mega pack closes pack."""
        # Expected fixture: state-SMODS_BOOSTER_OPENED--pack.key-p_celestial_mega_1
        # Test implementation:
        # load_fixture(client, "pack", "state-SMODS_BOOSTER_OPENED--pack.key-p_celestial_mega_1")
        # api(client, "pack", {"card": 0})  # First selection
        # result = api(client, "pack", {"card": 0})  # Second selection
        # gamestate = assert_gamestate_response(result, state="SHOP")
        # assert "pack" not in gamestate
        pass


# =============================================================================
# Skip Tests
# =============================================================================


class TestPackEndpointSkip:
    """Tests for skip functionality (pack.lua lines 264-286)."""

    @pytest.mark.parametrize("pack_key", PACKS)
    def test_pack_skip(self, client: httpx.Client, pack_key: str) -> None:
        """Test skipping pack selection."""
        load_fixture(client, "pack", "state-SHOP--packs.count-0")
        api(client, "add", {"key": pack_key})
        result = api(client, "buy", {"pack": 0})
        assert_gamestate_response(result)

        result = api(client, "pack", {"skip": True})
        gamestate = assert_gamestate_response(result, state="SHOP")
        assert "pack" not in gamestate


# =============================================================================
# Schema Validation Tests
# =============================================================================


class TestPackEndpointValidation:
    """Tests for JSON schema validation."""

    def test_invalid_card_type_string(self, client: httpx.Client) -> None:
        """Test that pack fails when card parameter is a string."""
        load_fixture(client, "pack", "state-SHOP")
        api(client, "buy", {"pack": 0})

        assert_error_response(
            api(client, "pack", {"card": "INVALID_STRING"}),
            "BAD_REQUEST",
            "Field 'card' must be an integer",
        )

    def test_invalid_skip_type_string(self, client: httpx.Client) -> None:
        """Test that pack fails when skip parameter is a string."""
        load_fixture(client, "pack", "state-SHOP")
        api(client, "buy", {"pack": 0})

        assert_error_response(
            api(client, "pack", {"skip": "INVALID_STRING"}),
            "BAD_REQUEST",
            "Field 'skip' must be of type boolean",
        )

    def test_invalid_targets_type_string(self, client: httpx.Client) -> None:
        """Test that pack fails when targets parameter is a string."""
        load_fixture(client, "pack", "state-SHOP")
        api(client, "buy", {"pack": 0})

        assert_error_response(
            api(client, "pack", {"card": 0, "targets": "INVALID_STRING"}),
            "BAD_REQUEST",
            "Field 'targets' must be an array",
        )

    def test_invalid_targets_items_string(self, client: httpx.Client) -> None:
        """Test that pack fails when targets array contains strings."""
        load_fixture(client, "pack", "state-SHOP")
        api(client, "buy", {"pack": 0})

        assert_error_response(
            api(client, "pack", {"card": 0, "targets": ["zero", "one"]}),
            "BAD_REQUEST",
            "Field 'targets' array item at index 0 must be of type integer",
        )


# =============================================================================
# State Requirement Tests
# =============================================================================


class TestPackEndpointStateRequirements:
    """Tests for game state requirements."""

    def test_pack_from_MENU(self, client: httpx.Client) -> None:
        """Test that pack fails from MENU state."""
        api(client, "menu", {})

        assert_error_response(
            api(client, "pack", {"card": 0}),
            "INVALID_STATE",
            "Method 'pack' requires one of these states: SMODS_BOOSTER_OPENED",
        )

    def test_pack_from_SHOP(self, client: httpx.Client) -> None:
        """Test that pack fails from SHOP state."""
        load_fixture(client, "pack", "state-SHOP")

        assert_error_response(
            api(client, "pack", {"card": 0}),
            "INVALID_STATE",
            "Method 'pack' requires one of these states: SMODS_BOOSTER_OPENED",
        )

    def test_pack_from_SELECTING_HAND(self, client: httpx.Client) -> None:
        """Test that pack fails from SELECTING_HAND state."""
        api(client, "menu", {})
        api(client, "start", {"deck": "RED", "stake": "WHITE", "seed": "TEST123"})
        api(client, "select", {})

        assert_error_response(
            api(client, "pack", {"card": 0}),
            "INVALID_STATE",
            "Method 'pack' requires one of these states: SMODS_BOOSTER_OPENED",
        )
