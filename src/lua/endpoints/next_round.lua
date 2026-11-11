-- src/lua/endpoints/next_round.lua

-- ==========================================================================
-- NextRound Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.NextRound.Params

-- ==========================================================================
-- NextRound Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "next_round",

  description = "Leave the shop and advance to blind selection",

  schema = {},

  requires_state = { G.STATES.SHOP },

  ---@param _ Request.Endpoint.NextRound.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(_, send_response)
    sendDebugMessage("next_round()", "BB.ENDPOINTS")
    G.FUNCS.toggle_shop({})

    -- Wait for BLIND_SELECT state after leaving shop
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        -- Wait for state transition and UI to be fully initialized
        if G.STATE ~= G.STATES.BLIND_SELECT then
          return false
        end
        if not G.blind_select_opts then
          return false
        end

        local blind_key = string.lower(G.GAME.blind_on_deck)
        local blind_pane = G.blind_select_opts[blind_key]
        if not blind_pane then
          return false
        end

        local select_button = blind_pane:get_UIE_by_ID("select_blind_button")
        if not select_button then
          return false
        end

        sendDebugMessage("next_round() → BLIND_SELECT", "BB.ENDPOINTS")
        send_response(BB_GAMESTATE.get_gamestate())
        return true
      end,
    }))
  end,
}
