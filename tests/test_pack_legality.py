"""CPU-only regression of the real pack endpoint's game-level legality gate."""

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("real_game_rules", [False, True])
def test_pack_checks_consumable_legality_before_using_card(real_game_rules):
    lua = shutil.which("luajit")
    if not lua:
        pytest.skip("LuaJIT is needed for the endpoint regression")
    rules = ""
    if real_game_rules:
        archive = Path.home() / "Library/Application Support/Steam/steamapps/common/Balatro/Balatro.app/Contents/Resources/Balatro.love"
        if not archive.exists():
            pytest.skip("Optional check against the installed game's own legality predicate")
        with zipfile.ZipFile(archive) as game:
            source = game.read("card.lua").decode()
        # Exercise the installed game's actual rule without copying proprietary
        # game code into the repository. UI/animation dependencies stay stubbed.
        predicate = source.split("function Card:can_use_consumeable", 1)[1].split("function Card:check_use", 1)[0]
        rules = "Card = {}\nfunction Card:can_use_consumeable" + predicate
    script = rules + r'''
package.preload.socket = function() return {gettime=function() return 0 end} end
SMODS = {load_file=function() return function()
  return {format_playing_cards=function() return "targets" end}
end end}
function sendDebugMessage() end
function Event(event) return event end
BB_ERROR_NAMES = {NOT_ALLOWED="NOT_ALLOWED", BAD_REQUEST="BAD_REQUEST"}
BB_GAMESTATE = {get_gamestate=function() return {ok=true} end}
G = {STATES={SMODS_BOOSTER_OPENED=1,SHOP=2,BLIND_SELECT=3}}
local endpoint = dofile("src/lua/endpoints/pack.lua")
local function run(set, count, usable, space_blocked, targets)
  local used, checked, responses, events = 0, 0, {}, {}
  local card = {ability={set=set,name="Judgement",consumeable=set~="Joker" and set~="Default" and {}},
    config={center={key="c_judgement"}},
    can_use_consumeable=function(self)
      checked=checked+1
      if targets then assert(#G.hand.highlighted == #targets) end
      if usable~=nil then return usable end
      if Card then return Card.can_use_consumeable(self) end
      return G.jokers.config.card_count < G.jokers.config.card_limit
    end,
    check_use=function() return space_blocked end}
  G.STATE=1; G.STATE_COMPLETE=true; G.GAME={pack_choices=1}
  G.P_CENTERS={c_judgement={config=targets and {max_highlighted=1} or {}}}
  G.CONTROLLER={locked=false}
  G.jokers={cards={},config={card_count=count,card_limit=5}}
  for i=1,count do G.jokers.cards[i]={} end
  G.pack_cards={cards={card},config={card_count=1}}
  G.deck={config={card_count=1}}
  G.hand={cards={{T={x=1}}},highlighted={},config={card_limit=1},T={x=1},
    add_to_highlighted=function(self,c) table.insert(self.highlighted,c) end,
    remove_from_highlighted=function(self,c) table.remove(self.highlighted) end}
  G.E_MANAGER={add_event=function(self,e) table.insert(events,e) end}
  G.FUNCS={use_card=function()
    used=used+1; G.jokers.config.card_count=count+1
    G.STATE=2; G.pack_cards=nil
  end}
  endpoint.execute({card=0,targets=targets},function(r) table.insert(responses,r) end)
  for _=1,3 do
    local pending=events; events={}
    for _,e in ipairs(pending) do if not e.func() then table.insert(events,e) end end
  end
  assert(#responses==1, "must respond exactly once")
  return used,checked,responses[1]
end
local used,checked,response=run("Tarot",5)
assert(used==0 and checked==1 and response.name=="NOT_ALLOWED")
assert(G.jokers.config.card_count==5 and G.GAME.pack_choices==1 and G.pack_cards~=nil)
used,checked,response=run("Tarot",4)
assert(used==1 and checked==1 and response.ok)
-- Spectral restrictions and space checks must not be bypassed either.
used,checked,response=run("Spectral",4,false)
assert(used==0 and response.name=="NOT_ALLOWED")
used,checked,response=run("Planet",4,true,true)
assert(used==0 and response.name=="NOT_ALLOWED")
-- Non-joker-generating consumables stay legal at full joker capacity.
used,checked,response=run("Tarot",5,true,false,{0})
assert(used==1 and checked==1 and response.ok)
for _,set in ipairs({"Joker","Default"}) do
  used,checked,response=run(set,4)
  assert(used==1 and checked==0 and response.ok)
end
print("ok")
'''
    result = subprocess.run([lua, "-"], input=script, text=True, cwd=ROOT, capture_output=True, check=True)
    assert result.stdout.strip() == "ok"
