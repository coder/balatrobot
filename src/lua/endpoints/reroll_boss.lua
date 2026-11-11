-- src/lua/endpoints/reroll_boss.lua

-- ==========================================================================
-- Reroll Boss Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.RerollBoss.Params

-- ==========================================================================
-- Reroll Boss Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "reroll_boss",

  description = "Reroll the upcoming Boss Blind for $10 (requires Director's Cut or Retcon voucher)",

  schema = {},

  requires_state = { G.STATES.BLIND_SELECT },

  ---@param _ Request.Endpoint.RerollBoss.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(_, send_response)
    sendDebugMessage("reroll_boss()", "BB.ENDPOINTS")

    local has_retcon = G.GAME.used_vouchers["v_retcon"]
    local has_directors_cut = G.GAME.used_vouchers["v_directors_cut"]

    -- Gate 1: requires the Director's Cut or Retcon voucher
    if not has_retcon and not has_directors_cut then
      send_response({
        message = "Reroll Boss Blind requires the Director's Cut or Retcon voucher",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    -- Gate 2: Director's Cut allows one reroll per ante (Retcon is unlimited)
    if not has_retcon and G.GAME.round_resets.boss_rerolled then
      send_response({
        message = "Director's Cut allows one Reroll Boss Blind per ante; already used",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    -- Gate 3: affordability (accounting for Credit Card joker via bankrupt_at)
    local available_money = G.GAME.dollars - G.GAME.bankrupt_at
    if (available_money - 10) < 0 then
      send_response({
        message = "Not enough dollars to reroll boss. Available: " .. available_money .. ", Required: 10",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    sendInfoMessage("Rerolling boss blind ($10)", "BB.ENDPOINTS")
    G.FUNCS.reroll_boss({})

    -- Wait for the boss reroll lock to release (predicate α)
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        local done = G.CONTROLLER.locks.boss_reroll == nil
        if done then
          sendDebugMessage("reroll_boss() → ok", "BB.ENDPOINTS")
          send_response(BB_GAMESTATE.get_gamestate())
        end
        return done
      end,
    }))
  end,
}
