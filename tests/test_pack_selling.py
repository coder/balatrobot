"""Pack replacement regressions: grammar, legal hints, and Lua sale/selection."""

import ast
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def harness():
    tree = ast.parse((ROOT / "batro_modal_rl.py").read_text())
    functions = {
        "_compact_state", "_area_items", "_slot_usage", "_sellable_indices",
        "_purchasable_indices", "_consumable_target_bounds", "_consumable_requires_joker", "_consumable_available",
        "_target_action_help", "_action_help", "_action_is_locally_legal", "_action_regex",
    }
    constants = {"_INDEX", "_INDEX_LIST", "_INDEX_LIST_5", "_ALLOWED_METHODS", "_ACTION_REGEX_BY_STATE",
                 "_CONSUMABLE_TARGET_BOUNDS", "_CONSUMABLE_REQUIRES_JOKER"}
    nodes = [node for node in tree.body if (
        isinstance(node, ast.FunctionDef) and node.name in functions
        or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets)
    )]
    ns = {"Any": Any, "json": json, "ToolCall": SimpleNamespace, "_CONSUMABLE_TARGET_BOUNDS": {}, "_CONSUMABLE_REQUIRES_JOKER": set()}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "batro_modal_rl.py", "exec"), ns)
    return ns


def pack_state():
    return {
        "state": "SMODS_BOOSTER_OPENED",
        "jokers": {"count": 5, "limit": 5, "cards": [
            {"key": "j_joker", "cost": {"sell": 1}, "modifier": {"eternal": i == 0}}
            for i in range(5)
        ]},
        "consumables": {"count": 1, "limit": 2, "cards": [{"key": "c_fool", "cost": {"sell": 1}}]},
        "pack": {"count": 1, "cards": [{"key": "j_blueprint"}]},
    }


def test_pack_exposes_sale_then_unlocks_selection(harness):
    state = pack_state()
    sell = SimpleNamespace(name="sell", arguments={"joker": 1})
    pick = SimpleNamespace(name="pack", arguments={"card": 0})
    assert "sell" in harness["_ALLOWED_METHODS"][state["state"]]
    for kind in ("joker", "consumable"):
        assert re.fullmatch(harness["_action_regex"](state["state"]), f'{{"method":"sell","params":{{"{kind}":1}}}}')
    help_text = harness["_action_help"](state)
    assert "sell joker=one of [1, 2, 3, 4]" in help_text
    assert "sell consumable=one of [0]" in help_text
    assert "keeps pack open" in help_text
    assert "pack card=" not in help_text
    assert harness["_action_is_locally_legal"](sell, state)
    assert not harness["_action_is_locally_legal"](pick, state)
    after = copy.deepcopy(state)
    after["jokers"]["cards"].pop(1)
    after["jokers"]["count"] = 4
    assert "pack card=0" in harness["_action_help"](after)
    assert harness["_action_is_locally_legal"](pick, after)
    assert after["pack"] == state["pack"]


@pytest.mark.parametrize("index", [0, -1, 5, True, "1"])
def test_pack_sale_rejects_eternal_or_invalid_index(harness, index):
    assert not harness["_action_is_locally_legal"](
        SimpleNamespace(name="sell", arguments={"joker": index}), pack_state(),
    )


@pytest.mark.parametrize("phase", ["SHOP", "SELECTING_HAND", "BLIND_SELECT"])
def test_existing_sale_phases(harness, phase):
    state = {**pack_state(), "state": phase}
    assert harness["_action_is_locally_legal"](
        SimpleNamespace(name="sell", arguments={"joker": 1}), state,
    ) is (phase != "BLIND_SELECT")


@pytest.mark.parametrize("case", json.loads((ROOT / "tests/fixtures/consumable_capacity_failures.json").read_text()))
def test_recorded_engine_rejections_are_never_advertised_or_accepted(harness, case):
    state = case["state"]
    action = SimpleNamespace(name=case["action"]["method"], arguments=case["action"]["params"])
    parameter = "consumable" if action.name == "use" else "card"
    hint = f"{action.name} {parameter}={action.arguments[parameter]}"
    assert hint not in harness["_action_help"](state)
    assert not harness["_action_is_locally_legal"](action, state)
    # Selling a joker restores both the hint and the actual legal action.
    after = copy.deepcopy(state)
    after["jokers"]["cards"].pop()
    after["jokers"]["count"] -= 1
    assert hint in harness["_action_help"](after)
    assert harness["_action_is_locally_legal"](action, after)


@pytest.mark.parametrize("phase", ["SHOP", "SELECTING_HAND"])
def test_owned_consumable_gate_preserves_legal_uses_and_eternal_sales(harness, phase):
    state = {**pack_state(), "state": phase,
             "round": {"hands_left": 4, "discards_left": 3},
             "hand": {"cards": [{"key": "S_A"}]},
             "consumables": {"cards": [{"key": "c_wraith"}, {"key": "c_mercury"}]}}
    hint = harness["_action_help"](state)
    assert "use consumable=0" not in hint
    assert "use consumable=1" in hint
    assert "sell joker=one of [1, 2, 3, 4]" in hint
    assert harness["_action_is_locally_legal"](SimpleNamespace(name="use", arguments={"consumable": 1}), state)
    assert not harness["_action_is_locally_legal"](SimpleNamespace(name="use", arguments={"consumable": True}), state)


def test_lua_sale_preserves_pack_and_allows_replacement():
    lua = shutil.which("luajit")
    if not lua:
        pytest.skip("LuaJIT required")
    script = r'''
package.preload.socket=function() return {gettime=function() return 0 end} end
SMODS={load_file=function() return function() return {} end end}
function sendDebugMessage() end
function Event(e) return e end
BB_ERROR_NAMES={NOT_ALLOWED="NOT_ALLOWED",BAD_REQUEST="BAD_REQUEST"}
G={STATES={SMODS_BOOSTER_OPENED=1,SHOP=2,SELECTING_HAND=3,BLIND_SELECT=4},
  STATE=1,STATE_COMPLETE=true,GAME={dollars=5,pack_choices=2},P_CENTERS={}}
local function card(id,eternal)
  return {sort_id=id,sell_cost=2,ability={name="Joker",set="Joker",eternal=eternal},
    can_sell_card=function(self) return not self.ability.eternal end}
end
G.jokers={cards={card(1,true),card(2),card(3),card(4),card(5)},config={card_count=5,card_limit=5}}
G.consumeables={cards={card(6)},config={card_count=1,card_limit=2}}
G.pack_cards={cards={card(7),card(8)},config={card_count=2}}
local original_pack=G.pack_cards
local events={}
G.E_MANAGER={add_event=function(self,e) table.insert(events,e) end}
G.FUNCS={sell_card=function(e)
  for _,area in ipairs({G.jokers,G.consumeables}) do
    for i,c in ipairs(area.cards) do
      if c==e.config.ref_table then
        table.remove(area.cards,i);area.config.card_count=#area.cards
        G.GAME.dollars=G.GAME.dollars+c.sell_cost
        return
      end
    end
  end
end,use_card=function(e)
  assert(#G.jokers.cards<G.jokers.config.card_limit)
  table.insert(G.jokers.cards,e.config.ref_table);G.jokers.config.card_count=#G.jokers.cards
  table.remove(G.pack_cards.cards,1);G.GAME.pack_choices=G.GAME.pack_choices-1
end}
BB_GAMESTATE={get_gamestate=function() return {ok=true} end}
local sell=dofile("src/lua/endpoints/sell.lua")
local pack=dofile("src/lua/endpoints/pack.lua")
local allowed=false
for _,s in ipairs(sell.requires_state) do if s==1 then allowed=true end end
assert(allowed)
local function call(endpoint,args)
  local responses={}
  endpoint.execute(args,function(r) table.insert(responses,r) end)
  for _=1,3 do
    local pending=events;events={}
    for _,e in ipairs(pending) do if not e.func() then table.insert(events,e) end end
  end
  assert(#responses==1,"exactly one response required")
  assert(#events==0,"sale must not hang waiting for SHOP")
  return responses[1]
end
assert(call(pack,{card=0}).name=="NOT_ALLOWED")
assert(call(sell,{joker=0}).name=="NOT_ALLOWED")
assert(G.GAME.dollars==5 and #G.jokers.cards==5)
assert(call(sell,{joker=1}).ok)
assert(G.STATE==1 and G.pack_cards==original_pack and #G.pack_cards.cards==2)
assert(G.GAME.pack_choices==2 and #G.jokers.cards==4 and G.GAME.dollars==7)
assert(call(pack,{card=0}).ok)
assert(G.STATE==1 and #G.jokers.cards==5 and G.jokers.cards[5].sort_id==7)
assert(G.GAME.pack_choices==1 and #G.pack_cards.cards==1)
assert(call(sell,{consumable=0}).ok)
assert(G.GAME.pack_choices==1 and G.pack_cards==original_pack and G.GAME.dollars==9)
-- Existing shop/hand sales must still complete.
for _,phase in ipairs({2,3}) do
  G.STATE=phase
  assert(call(sell,{joker=1}).ok)
end
print("ok")
'''
    result = subprocess.run([lua, "-"], input=script, text=True, cwd=ROOT, capture_output=True, check=True)
    assert result.stdout.strip() == "ok"
