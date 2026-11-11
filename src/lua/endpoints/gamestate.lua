-- src/lua/endpoints/gamestate.lua

-- ==========================================================================
-- Gamestate Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Gamestate.Params

-- ==========================================================================
-- Gamestate Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "gamestate",

  description = "Get current game state",

  schema = {},

  requires_state = nil,

  ---@param _ Request.Endpoint.Gamestate.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(_, send_response)
    sendDebugMessage("gamestate()", "BB.ENDPOINTS")
    local state_data = BB_GAMESTATE.get_gamestate()
    sendDebugMessage("gamestate() → ok", "BB.ENDPOINTS")
    send_response(state_data)
  end,
}
