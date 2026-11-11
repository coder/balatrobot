"""CPU-only checks of visible joker targets from Lua RPC through compact traces."""

import ast
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_rpc_reads_targets_without_advancing_randomness():
    lua = shutil.which("luajit")
    if not lua:
        pytest.skip("LuaJIT is needed for the RPC serializer test")
    script = r'''
local gs = dofile("src/lua/utils/gamestate.lua")
function pseudorandom() error("A state read must not roll RNG") end
function pseudoseed() error("A state read must not roll RNG") end
function card(key, extra)
  return {config={center_key=key}, ability={set="Joker",extra=extra},
    generate_UIBox_ability_table=function() return {main={}} end}
end
G = {STATE=1,STATES={SELECTING_HAND=1},GAME={current_round={
  idol_card={rank="King",suit="Hearts",id=13,private_seed="not exported"},
  ancient_card={suit="Clubs"},mail_card={rank="Ace",id=14},
  castle_card={suit="Diamonds"},unrelated_rng=999}},
  jokers={config={card_count=5,card_limit=5},cards={
    card("j_idol"),card("j_ancient"),card("j_mail"),
    card("j_castle",{chips=27,chip_mod=3}),card("j_joker")}}}
local first=gs.get_gamestate().jokers.cards
assert(first[1].scoring_state.target.rank=="K")
assert(first[1].scoring_state.target.rank_id==13)
assert(first[1].scoring_state.target.suit=="H")
assert(first[1].scoring_state.target.private_seed==nil)
assert(first[2].scoring_state.target.suit=="C")
assert(first[3].scoring_state.target.rank=="A")
assert(first[4].scoring_state.target.suit=="D")
assert(first[4].scoring_state.chips==27 and first[4].scoring_state.chip_gain==3)
assert(first[5].scoring_state==nil)
G.GAME.current_round.idol_card={rank="10",suit="Spades",id=10}
local second=gs.get_gamestate().jokers.cards
assert(second[1].scoring_state.target.rank=="T")
assert(second[1].scoring_state.target.suit=="S")
assert(first[1].scoring_state.target.rank=="K", "snapshot must not alias live tables")
G.GAME.current_round=nil
assert(gs.get_gamestate().jokers.cards[1].scoring_state==nil)
print("ok")
'''
    result = subprocess.run([lua, "-"], input=script, text=True, cwd=ROOT, capture_output=True, check=True)
    assert result.stdout.strip() == "ok"


@pytest.mark.parametrize("limit", [6000, 1])
def test_compact_trace_preserves_targets_even_when_deck_is_omitted(limit):
    tree = ast.parse((ROOT / "batro_modal_rl.py").read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_compact_state")
    namespace = {"Any": Any, "json": json}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "batro_modal_rl.py", "exec"), namespace)
    target = {"target": {"rank": "K", "rank_id": 13, "suit": "H"}}
    state = {"state": "SELECTING_HAND", "jokers": {"count": 1, "limit": 5, "cards": [{"key": "j_idol", "value": {"effect": "X2 Mult on the current target"}, "scoring_state": target}]}}
    before = json.dumps(state)
    compact = json.loads(namespace["_compact_state"](state, limit))
    assert compact["jokers"]["items"][0]["scoring_state"] == target
    assert json.dumps(state) == before


def test_rpc_schema_describes_optional_scoring_state():
    schema = json.loads((ROOT / "src/lua/utils/openrpc.json").read_text())
    card = schema["components"]["schemas"]["Card"]
    assert "scoring_state" in card["properties"]
    assert "scoring_state" not in card["required"]
