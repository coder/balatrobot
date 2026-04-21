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
---@field blind string? Boss blind key (e.g. "bl_flint") — sets the upcoming boss blind
---@field debuff boolean? Re-apply blind debuffs to all hand cards (useful after add())

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
    blind = {
      type = "string",
      required = false,
      description = "Boss blind key (e.g. 'bl_flint') — sets the upcoming boss blind",
    },
    debuff = {
      type = "boolean",
      required = false,
      description = "Re-apply blind debuffs to all hand cards (call after add() during a boss blind)",
    },
  },

  requires_state = nil,

  ---@param args Request.Endpoint.Set.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init set()", "BB.ENDPOINTS")

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
      and args.blind == nil
      and args.debuff == nil
    then
      send_response({
        message = "Must provide at least one field to set",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
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

    -- Set boss blind
    if args.blind then
      if not G.P_BLINDS[args.blind] then
        send_response({
          message = "Unknown blind key: " .. tostring(args.blind),
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
      G.GAME.round_resets.blind_choices.Boss = args.blind
      G.RESET_BLIND_STATES = true

      -- Rebuild the boss blind UIBox so select_blind picks up the new blind.
      -- Mirrors the logic in G.FUNCS.reroll_boss (button_callbacks.lua).
      if G.blind_select_opts and G.blind_select_opts.boss then
        local par = G.blind_select_opts.boss.parent
        G.blind_select_opts.boss:remove()
        G.blind_select_opts.boss = UIBox{
          T = {par.T.x, 0, 0, 0},
          definition =
            {n=G.UIT.ROOT, config={align = "cm", colour = G.C.CLEAR}, nodes={
              UIBox_dyn_container(
                {create_UIBox_blind_choice('Boss')},
                false,
                get_blind_main_colour('Boss'),
                mix_colours(G.C.BLACK, get_blind_main_colour('Boss'), 0.8)
              )
            }},
          config = {align="bmi",
                    offset = {x=0, y=G.ROOM.T.y + 9},
                    major = par,
                    xy_bond = 'Weak'
                  }
        }
        par.config.object = G.blind_select_opts.boss
        par.config.object:recalculate()
        G.blind_select_opts.boss.parent = par
        G.blind_select_opts.boss.alignment.offset.y = 0
      end
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

    -- Re-apply blind debuffs to hand cards
    if args.debuff then
      if G.STATE ~= G.STATES.SELECTING_HAND then
        send_response({
          message = "Can only apply debuffs in SELECTING_HAND state",
          name = BB_ERROR_NAMES.NOT_ALLOWED,
        })
        return
      end
      if G.GAME.blind and G.GAME.blind.debuff_card then
        for _, card in ipairs(G.hand.cards) do
          G.GAME.blind:debuff_card(card)
        end
        sendDebugMessage("Re-applied blind debuffs to " .. #G.hand.cards .. " hand cards", "BB.ENDPOINTS")
      end
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
            sendDebugMessage("Return set()", "BB.ENDPOINTS")
            local state_data = BB_GAMESTATE.get_gamestate()
            send_response(state_data)
            return true
          end
          return false
        else
          sendDebugMessage("Return set()", "BB.ENDPOINTS")
          local state_data = BB_GAMESTATE.get_gamestate()
          send_response(state_data)
          return true
        end
      end,
    }))
  end,
}
