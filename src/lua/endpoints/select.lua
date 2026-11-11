-- src/lua/endpoints/select.lua

-- ==========================================================================
-- Select Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Select.Params

-- ==========================================================================
-- Select Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "select",

  description = "Select the current blind",

  schema = {},

  requires_state = { G.STATES.BLIND_SELECT },

  ---@param _ Request.Endpoint.Select.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(_, send_response)
    sendDebugMessage("select()", "BB.ENDPOINTS")
    -- Get current blind and its UI element
    local current_blind = G.GAME.blind_on_deck
    assert(current_blind ~= nil, "select() called with no blind on deck")
    local blind_pane = G.blind_select_opts[string.lower(current_blind)]
    assert(blind_pane ~= nil, "select() blind pane not found: " .. current_blind)
    local select_button = blind_pane:get_UIE_by_ID("select_blind_button")
    assert(select_button ~= nil, "select() select button not found: " .. current_blind)

    -- Log which blind we're selecting
    local blind_info = BB_GAMESTATE.get_blinds_info()[string.lower(current_blind)]
    local blind_name = blind_info and blind_info.name or current_blind
    local chips = blind_info and blind_info.chips or "?"
    sendInfoMessage(string.format("Selecting %s blind (%s chips)", current_blind, tostring(chips)), "BB.ENDPOINTS")

    -- Execute blind selection
    G.FUNCS.select_blind(select_button)

    -- Wait for completion: transition to SELECTING_HAND with facing_blind flag set
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        local done = G.STATE == G.STATES.SELECTING_HAND and G.hand ~= nil
        if done then
          sendDebugMessage("select() → SELECTING_HAND", "BB.ENDPOINTS")
          local state_data = BB_GAMESTATE.get_gamestate()
          send_response(state_data)
        end
        return done
      end,
    }))
  end,
}
