-- src/lua/endpoints/reroll_boss.lua

-- ==========================================================================
-- RerollBoss Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.RerollBoss.Params

-- ==========================================================================
-- RerollBoss Endpoint
-- ==========================================================================

-- Hard-coded in the game (G.FUNCS.reroll_boss_button / G.FUNCS.reroll_boss)
local BOSS_REROLL_COST = 10

---@type Endpoint
return {

  name = "reroll_boss",

  description = "Reroll the Boss blind (requires Director's Cut or Retcon voucher)",

  schema = {},

  requires_state = { G.STATES.BLIND_SELECT },

  ---@param _ Request.Endpoint.RerollBoss.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(_, send_response)
    sendDebugMessage("Init reroll_boss()", "BB.ENDPOINTS")

    -- Same checks as G.FUNCS.reroll_boss_button (the in-game button)
    local used_vouchers = G.GAME.used_vouchers or {}
    local has_retcon = used_vouchers["v_retcon"] and true or false
    local has_directors_cut = used_vouchers["v_directors_cut"] and true or false

    if not has_retcon and not has_directors_cut then
      send_response({
        message = "Cannot reroll Boss blind without Director's Cut or Retcon voucher",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    if not has_retcon and G.GAME.round_resets.boss_rerolled then
      send_response({
        message = "Boss blind already rerolled this ante (Director's Cut allows one reroll per ante)",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    -- Check affordability (accounting for Credit Card joker via bankrupt_at)
    local available_money = G.GAME.dollars - G.GAME.bankrupt_at
    if available_money < BOSS_REROLL_COST then
      send_response({
        message = "Not enough dollars to reroll Boss blind. Available: "
          .. available_money
          .. ", Required: "
          .. BOSS_REROLL_COST,
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    if not (G.blind_select_opts and G.blind_select_opts.boss) or G.CONTROLLER.locks.boss_reroll then
      send_response({
        message = "Boss blind cannot be rerolled right now",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    sendDebugMessage(
      string.format("Rerolling boss %s (money=$%d)", G.GAME.round_resets.blind_choices.Boss, G.GAME.dollars),
      "BB.ENDPOINTS"
    )
    G.FUNCS.reroll_boss(nil)

    -- Wait for the reroll to complete
    -- The game sets G.CONTROLLER.locks.boss_reroll and clears it in an event
    -- queued after the new boss pane is built. Non-blocking, otherwise this
    -- event would block the queue in front of the event that clears the lock.
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        local done = (
          G.STATE == G.STATES.BLIND_SELECT
          and G.CONTROLLER.locks.boss_reroll == nil
          and G.blind_select_opts ~= nil
          and G.blind_select_opts.boss ~= nil
        )
        if done then
          sendDebugMessage(
            string.format(
              "Return reroll_boss() boss=%s money=$%d",
              G.GAME.round_resets.blind_choices.Boss,
              G.GAME.dollars
            ),
            "BB.ENDPOINTS"
          )
          send_response(BB_GAMESTATE.get_gamestate())
        end
        return done
      end,
    }))
  end,
}
