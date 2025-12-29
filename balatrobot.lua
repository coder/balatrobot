-- Load required files
assert(SMODS.load_file("src/lua/settings.lua"))() -- define BB_SETTINGS

-- Configure Balatro with appropriate settings from environment variables
BB_SETTINGS.setup()

-- Endpoints for the BalatroBot API
BB_ENDPOINTS = {
  -- Health endpoint
  "src/lua/endpoints/health.lua",
  -- Gamestate endpoints
  "src/lua/endpoints/gamestate.lua",
  -- Save/load endpoints
  "src/lua/endpoints/save.lua",
  "src/lua/endpoints/load.lua",
  -- Screenshot endpoint
  "src/lua/endpoints/screenshot.lua",
  -- Game control endpoints
  "src/lua/endpoints/set.lua",
  "src/lua/endpoints/add.lua",
  -- Gameplay endpoints
  "src/lua/endpoints/menu.lua",
  "src/lua/endpoints/start.lua",
  -- Blind selection endpoints
  "src/lua/endpoints/skip.lua",
  "src/lua/endpoints/select.lua",
  -- Play/discard endpoints
  "src/lua/endpoints/play.lua",
  "src/lua/endpoints/discard.lua",
  -- Cash out endpoint
  "src/lua/endpoints/cash_out.lua",
  -- Shop endpoints
  "src/lua/endpoints/next_round.lua",
  "src/lua/endpoints/reroll.lua",
  "src/lua/endpoints/buy.lua",
  "src/lua/endpoints/pack_select.lua",
  -- Rearrange endpoint
  "src/lua/endpoints/rearrange.lua",
  -- Sell endpoint
  "src/lua/endpoints/sell.lua",
  -- Use consumable endpoint
  "src/lua/endpoints/use.lua",
  -- If debug mode is enabled, debugger.lua will load test endpoints
}

-- Enable debug mode
if BB_SETTINGS.debug then
  assert(SMODS.load_file("src/lua/utils/debugger.lua"))() -- define BB_DEBUG
  BB_DEBUG.setup()
end

-- Load core modules
assert(SMODS.load_file("src/lua/core/server.lua"))() -- define BB_SERVER
assert(SMODS.load_file("src/lua/core/dispatcher.lua"))() -- define BB_DISPATCHER

-- Load gamestate and errors utilities
BB_GAMESTATE = assert(SMODS.load_file("src/lua/utils/gamestate.lua"))()
assert(SMODS.load_file("src/lua/utils/errors.lua"))()

-- Initialize Server
local server_success = BB_SERVER.init()
if not server_success then
  return
end

local dispatcher_ok = BB_DISPATCHER.init(BB_SERVER, BB_ENDPOINTS)
if not dispatcher_ok then
  return
end

-- Hook into love.update to run server update loop and detect GAME_OVER
local love_update = love.update
love.update = function(dt) ---@diagnostic disable-line: duplicate-set-field
  -- Check for GAME_OVER before game logic runs
  BB_GAMESTATE.check_game_over()
  love_update(dt)
  BB_SERVER.update(BB_DISPATCHER)
end

sendInfoMessage("BalatroBot loaded - version " .. SMODS.current_mod.version, "BB.BALATROBOT")
