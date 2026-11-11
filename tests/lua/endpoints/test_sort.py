"""Tests for src/lua/endpoints/sort.lua"""

import httpx

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)

# ---------------------------------------------------------------------------
# Sort comparator helpers
# ---------------------------------------------------------------------------

RANK = {
    "2": 0,
    "3": 1,
    "4": 2,
    "5": 3,
    "6": 4,
    "7": 5,
    "8": 6,
    "9": 7,
    "T": 8,
    "J": 9,
    "Q": 10,
    "K": 11,
    "A": 12,
}
SUIT = {"D": 0, "C": 1, "H": 2, "S": 3}  # Diamonds < Clubs < Hearts < Spades


def _key_rank(card: dict) -> tuple[int, int]:
    """Sort-by-rank key: (rank, suit) — primary rank desc, tiebreak suit desc."""
    return (RANK[card["value"]["rank"]], SUIT[card["value"]["suit"]])


def _key_suit(card: dict) -> tuple[int, int]:
    """Sort-by-suit key: (suit, rank) — primary suit desc, tiebreak rank desc."""
    return (SUIT[card["value"]["suit"]], RANK[card["value"]["rank"]])


def _is_descending_by(cards: list[dict], key) -> bool:
    """True if `cards` is strictly descending by `key`."""
    ks = [key(c) for c in cards]
    return all(ks[i] > ks[i + 1] for i in range(len(ks) - 1))


class TestSortEndpoint:
    """Test sort endpoint functionality."""

    def test_sort_by_rank(self, client: httpx.Client) -> None:
        """Sort by rank reorders hand descending A>K>...>2, suit Spades>...>Diamonds."""
        before = load_fixture(client, "sort", "state-SELECTING_HAND--hand.count-8")
        assert before["state"] == "SELECTING_HAND"
        assert before["hand"]["count"] == 8
        before_ids = {card["id"] for card in before["hand"]["cards"]}

        response = api(client, "sort", {"by": "rank"})
        after = assert_gamestate_response(response, state="SELECTING_HAND")

        after_cards = after["hand"]["cards"]
        after_ids = {card["id"] for card in after_cards}
        # Permutation contract: no cards lost or created
        assert after_ids == before_ids
        # Sort contract: descending by (rank, suit)
        assert _is_descending_by(after_cards, _key_rank)

    def test_sort_by_suit(self, client: httpx.Client) -> None:
        """Sort by suit groups Spades>Hearts>Clubs>Diamonds, rank desc within suit."""
        before = load_fixture(client, "sort", "state-SELECTING_HAND--hand.count-8")
        assert before["state"] == "SELECTING_HAND"
        assert before["hand"]["count"] == 8
        before_ids = {card["id"] for card in before["hand"]["cards"]}

        response = api(client, "sort", {"by": "suit"})
        after = assert_gamestate_response(response, state="SELECTING_HAND")

        after_cards = after["hand"]["cards"]
        after_ids = {card["id"] for card in after_cards}
        # Permutation contract: no cards lost or created
        assert after_ids == before_ids
        # Sort contract: descending by (suit, rank)
        assert _is_descending_by(after_cards, _key_suit)

    def test_sort_wrong_state(self, client: httpx.Client) -> None:
        """sort requires SELECTING_HAND state."""
        gamestate = load_fixture(client, "sort", "state-SHOP")
        assert gamestate["state"] == "SHOP"
        assert_error_response(
            api(client, "sort", {"by": "rank"}),
            "INVALID_STATE",
            "requires one of these states: SELECTING_HAND",
        )

    def test_sort_missing_by(self, client: httpx.Client) -> None:
        """Missing 'by' param is rejected by the schema validator."""
        load_fixture(client, "sort", "state-SELECTING_HAND--hand.count-8")
        assert_error_response(
            api(client, "sort", {}),
            "BAD_REQUEST",
            "Missing required field 'by'",
        )

    def test_sort_by_wrong_type(self, client: httpx.Client) -> None:
        """Non-string 'by' param is rejected by the schema validator."""
        load_fixture(client, "sort", "state-SELECTING_HAND--hand.count-8")
        assert_error_response(
            api(client, "sort", {"by": 5}),
            "BAD_REQUEST",
            "Field 'by' must be of type string",
        )

    def test_sort_by_invalid_enum(self, client: httpx.Client) -> None:
        """'by' must be exactly 'rank' or 'suit' (manual enum check)."""
        load_fixture(client, "sort", "state-SELECTING_HAND--hand.count-8")
        assert_error_response(
            api(client, "sort", {"by": "value"}),
            "BAD_REQUEST",
            'must be "rank" or "suit"',
        )
