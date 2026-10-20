"""Regressions from actual losses; helpers must use only visible card faces."""

import ast
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def compact():
    tree = ast.parse((ROOT / "batro_modal_rl.py").read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_compact_state")
    ns = {"json": json, "Any": Any}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "compact", "exec"), ns)
    def render(cards):
        return json.loads(ns["_compact_state"]({
            "state": "SELECTING_HAND", "hand": {"cards": cards},
            "round": {}, "blinds": {},
        }))
    return render


@pytest.mark.parametrize("case", json.loads((ROOT / "tests/fixtures/broad_layover_decisions.json").read_text()))
def test_recorded_winning_combination_is_explicit(compact, case):
    state = compact([{"key": key} for key in case["hand"]])
    groups = state["hand_groups"]["same_rank"]
    assert sorted(i for indices in groups.values() for i in indices) == case["winning_cards"]
    assert case["winning_score"] >= case["blind"]["score"][1] - case["blind"]["score"][0]


def test_groups_reindex_when_hand_changes(compact):
    before = compact([{"key": k} for k in ["H_A", "H_K", "C_K", "D_K"]])
    after = compact([{"key": k} for k in ["D_K", "H_A", "C_K", "H_K"]])
    assert before["hand_groups"]["same_rank"]["K"] == [1, 2, 3]
    assert after["hand_groups"]["same_rank"]["K"] == [0, 2, 3]


def test_hidden_cards_and_stone_cards_do_not_supply_ranks(compact):
    state = compact([
        {"key": "H_K"},
        {"key": "C_K", "state": {"hidden": True}},
        {"key": "D_K", "modifier": {"enhancement": "STONE"}},
    ])
    assert not state.get("hand_groups", {}).get("same_rank")


def test_straight_examples_and_suit_groups_use_current_visible_indices(compact):
    state = compact([{"key": k} for k in ["H_A", "H_K", "S_Q", "H_J", "D_J", "H_T", "S_8", "C_2"]])
    assert state["hand_groups"]["straight_examples"] == [[5, 3, 2, 1, 0]]
    assert state["hand_groups"]["same_suit"] == {"H": [0, 1, 3, 5]}


def test_wheel_and_duplicate_ranks(compact):
    state = compact([{"key": k} for k in ["S_A", "H_2", "C_3", "D_4", "S_5", "C_5"]])
    assert state["hand_groups"]["straight_examples"] == [[0, 1, 2, 3, 4]]
    assert state["hand_groups"]["same_rank"] == {"5": [4, 5]}
