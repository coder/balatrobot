-- src/lua/endpoints/menu.lua

-- ==========================================================================
-- Menu Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Menu.Params

-- ==========================================================================
-- Menu Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "menu",

  description = "Return to the main menu from any game state",

  schema = {},

  requires_state = nil,

  ---@param _ Request.Endpoint.Menu.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(_, send_response)
    sendDebugMessage("menu()", "BB.ENDPOINTS")
    if G.STATE ~= G.STATES.MENU then
      G.FUNCS.go_to_menu({})
    end

    -- Wait for menu state using Balatro's Event Manager
    G.E_MANAGER:add_event(Event({
      no_delete = true,
      trigger = "condition",
      blocking = true,
      func = function()
        local done = G.STATE == G.STATES.MENU and G.MAIN_MENU_UI

        if done then
          sendDebugMessage("menu() → MENU", "BB.ENDPOINTS")
          local state_data = BB_GAMESTATE.get_gamestate()
          send_response(state_data)
        end

        return done
      end,
    }))
  end,
}
