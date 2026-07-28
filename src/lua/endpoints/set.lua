-- src/lua/endpoints/set.lua

-- ==========================================================================
-- Set Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Set.Params
---@field money integer? New money amount
---@field chips integer? New chips amount
---@field ante integer? New ante number
---@field round integer? New round number
---@field hands integer? New number of hands left number
---@field discards integer? New number of discards left number
---@field shop boolean? Re-stock shop with new items
---@field boss string? Override which Boss Blind appears

-- ==========================================================================
-- Set Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "set",

  description = "Set a in-game value",

  schema = {
    money = {
      type = "integer",
      required = false,
      description = "New money amount",
    },
    chips = {
      type = "integer",
      required = false,
      description = "New chips amount",
    },
    ante = {
      type = "integer",
      required = false,
      description = "New ante number",
    },
    round = {
      type = "integer",
      required = false,
      description = "New round number",
    },
    hands = {
      type = "integer",
      required = false,
      description = "New number of hands left number",
    },
    discards = {
      type = "integer",
      required = false,
      description = "New number of discards left number",
    },
    shop = {
      type = "boolean",
      required = false,
      description = "Re-stock shop with new items",
    },
    boss = {
      type = "string",
      required = false,
      description = "Override which Boss Blind appears",
    },
  },

  requires_state = nil,

  ---@param args Request.Endpoint.Set.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("set()", "BB.ENDPOINTS")

    -- Build fields string for logging
    local fields = {}
    if args.money ~= nil then
      table.insert(fields, "money=" .. args.money)
    end
    if args.chips ~= nil then
      table.insert(fields, "chips=" .. args.chips)
    end
    if args.ante ~= nil then
      table.insert(fields, "ante=" .. args.ante)
    end
    if args.round ~= nil then
      table.insert(fields, "round=" .. args.round)
    end
    if args.hands ~= nil then
      table.insert(fields, "hands=" .. args.hands)
    end
    if args.discards ~= nil then
      table.insert(fields, "discards=" .. args.discards)
    end
    if args.shop ~= nil then
      table.insert(fields, "shop")
    end
    if args.boss ~= nil then
      table.insert(fields, "boss=" .. tostring(args.boss))
    end
    sendInfoMessage("Setting " .. table.concat(fields, ", "), "BB.ENDPOINTS")

    -- Validate we're in a run
    if G.STAGE and G.STAGE ~= G.STAGES.RUN then
      send_response({
        message = "Can only set during an active run",
        name = BB_ERROR_NAMES.INVALID_STATE,
      })
      return
    end

    -- Check for at least one field
    if
      args.money == nil
      and args.ante == nil
      and args.chips == nil
      and args.round == nil
      and args.hands == nil
      and args.discards == nil
      and args.shop == nil
      and args.boss == nil
    then
      send_response({
        message = "Must provide at least one field to set",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Boss + shop mutual exclusion
    if args.boss and args.shop then
      send_response({
        message = "Cannot set boss and shop at the same time",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Boss validation
    if args.boss then
      if G.STATE ~= G.STATES.BLIND_SELECT then
        send_response({
          message = "Can only set boss blind during blind selection (BLIND_SELECT state)",
          name = BB_ERROR_NAMES.INVALID_STATE,
        })
        return
      end

      local boss_state = G.GAME.round_resets.blind_states.Boss
      if boss_state ~= "Upcoming" then
        send_response({
          message = "Boss blind is not selectable (current state: " .. tostring(boss_state) .. ")",
          name = BB_ERROR_NAMES.INVALID_STATE,
        })
        return
      end

      if not G.P_BLINDS[args.boss] then
        send_response({
          message = "Unknown boss blind key: " .. args.boss,
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end

      if not G.P_BLINDS[args.boss].boss then
        send_response({
          message = "Not a boss blind: " .. args.boss,
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
    end

    -- Set money
    if args.money then
      if args.money < 0 then
        send_response({
          message = "Money must be a positive integer",
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
      G.GAME.dollars = args.money
    end

    -- Set chips
    if args.chips then
      if args.chips < 0 then
        send_response({
          message = "Chips must be a positive integer",
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
      G.GAME.chips = args.chips
    end

    -- Set ante
    if args.ante then
      if args.ante < 0 then
        send_response({
          message = "Ante must be a positive integer",
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
      G.GAME.round_resets.ante = args.ante
    end

    -- Set round
    if args.round then
      if args.round < 0 then
        send_response({
          message = "Round must be a positive integer",
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
      G.GAME.round = args.round
    end

    -- Set hands
    if args.hands then
      if args.hands < 0 then
        send_response({
          message = "Hands must be a positive integer",
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
      G.GAME.current_round.hands_left = args.hands
    end

    -- Set discards
    if args.discards then
      if args.discards < 0 then
        send_response({
          message = "Discards must be a positive integer",
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
      G.GAME.current_round.discards_left = args.discards
    end

    if args.shop then
      if G.STATE ~= G.STATES.SHOP then
        send_response({
          message = "Can re-stock shop only in SHOP state",
          name = BB_ERROR_NAMES.NOT_ALLOWED,
        })
        return
      end
      if G.shop then
        G.shop:remove()
        G.shop = nil
      end
      if G.SHOP_SIGN then
        G.SHOP_SIGN:remove()
        G.SHOP_SIGN = nil
      end
      G.GAME.current_round.used_packs = nil
      G.STATE_COMPLETE = false
      G:update_shop()
    end

    -- Boss execution: inject desired boss via perscribed_bosses and reroll
    if args.boss then
      G.GAME.perscribed_bosses = G.GAME.perscribed_bosses or {}
      G.GAME.perscribed_bosses[G.GAME.round_resets.ante] = args.boss
      G.from_boss_tag = true
      G.FUNCS.reroll_boss()
    end

    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        if args.shop then
          local done_vouchers = G.shop_vouchers and G.shop_vouchers.config and G.shop_vouchers.config.card_count > 0
          local done_packs = G.shop_booster and G.shop_booster.config and G.shop_booster.config.card_count > 0
          local done_jokers = G.shop_jokers and G.shop_jokers.config and G.shop_jokers.config.card_count > 0
          if done_vouchers or done_packs or done_jokers then
            sendDebugMessage("set() → ok", "BB.ENDPOINTS")
            local state_data = BB_GAMESTATE.get_gamestate()
            send_response(state_data)
            return true
          end
          return false
        elseif args.boss then
          -- Wait for boss reroll to complete (controller lock releases after 0.5s)
          if G.CONTROLLER.locks.boss_reroll == nil then
            G.GAME.round_resets.boss_rerolled = false
            sendDebugMessage("set() → ok (boss)", "BB.ENDPOINTS")
            local state_data = BB_GAMESTATE.get_gamestate()
            send_response(state_data)
            return true
          end
          return false
        else
          sendDebugMessage("set() → ok", "BB.ENDPOINTS")
          local state_data = BB_GAMESTATE.get_gamestate()
          send_response(state_data)
          return true
        end
      end,
    }))
  end,
}
