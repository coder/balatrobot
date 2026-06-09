-- src/lua/endpoints/reroll.lua

-- ==========================================================================
-- Reroll Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Reroll.Params

-- ==========================================================================
-- Reroll Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "reroll",

  description = "Reroll to update the cards in the shop area",

  schema = {},

  requires_state = { G.STATES.SHOP },

  ---@param _ Request.Endpoint.Reroll.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(_, send_response)
    sendDebugMessage("reroll()", "BB.ENDPOINTS")

    -- Check affordability (accounting for Credit Card joker via bankrupt_at)
    local reroll_cost = G.GAME.current_round and G.GAME.current_round.reroll_cost or 0
    local available_money = G.GAME.dollars - G.GAME.bankrupt_at

    if reroll_cost > 0 and available_money < reroll_cost then
      send_response({
        message = "Not enough dollars to reroll. Available: " .. available_money .. ", Required: " .. reroll_cost,
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    -- Log reroll with cost and money
    sendInfoMessage(string.format("Rerolling shop ($%d, money=$%d)", reroll_cost, G.GAME.dollars), "BB.ENDPOINTS")
    G.FUNCS.reroll_shop(nil)

    -- Wait for shop state to confirm reroll completed
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        local done = G.STATE == G.STATES.SHOP
        if done then
          sendDebugMessage("reroll() → ok", "BB.ENDPOINTS")
          send_response(BB_GAMESTATE.get_gamestate())
        end
        return done
      end,
    }))
  end,
}
