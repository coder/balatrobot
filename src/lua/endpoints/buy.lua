-- src/lua/endpoints/buy.lua

-- ==========================================================================
-- Buy Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Buy.Params
---@field card integer? 0-based index of card to buy
---@field voucher integer? 0-based index of voucher to buy
---@field pack integer? 0-based index of pack to buy

-- ==========================================================================
-- Buy Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "buy",

  description = "Buy a card from the shop",

  schema = {
    card = {
      type = "integer",
      required = false,
      description = "0-based index of card to buy",
    },
    voucher = {
      type = "integer",
      required = false,
      description = "0-based index of voucher to buy",
    },
    pack = {
      type = "integer",
      required = false,
      description = "0-based index of pack to buy",
    },
  },

  requires_state = { G.STATES.SHOP },

  ---@param args Request.Endpoint.Buy.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init buy()", "BB.ENDPOINTS")
    local gamestate = BB_GAMESTATE.get_gamestate()
    local area
    local pos
    local set = 0
    if args.card then
      area = gamestate.shop
      pos = args.card + 1
      set = set + 1
    end
    if args.voucher then
      area = gamestate.vouchers
      pos = args.voucher + 1
      set = set + 1
    end
    if args.pack then
      area = gamestate.packs
      pos = args.pack + 1
      set = set + 1
    end

    -- Validate that only one of card, voucher, or pack is provided
    if not area then
      send_response({
        message = "Invalid arguments. You must provide one of: card, voucher, pack",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Validate that only one of card, voucher, or pack is provided
    if set > 1 then
      send_response({
        message = "Invalid arguments. Cannot provide more than one of: card, voucher, or pack",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Validate that the area has cards
    if #area.cards == 0 then
      local msg
      if args.card then
        msg = "No jokers/consumables/cards in the shop. Reroll to restock the shop"
      elseif args.voucher then
        msg = "No vouchers to redeem. Defeat boss blind to restock"
      elseif args.pack then
        msg = "No packs to open"
      end
      send_response({
        message = msg,
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Validate card index is in range
    if not area.cards[pos] then
      send_response({
        message = "Card index out of range. Index: " .. args.card .. ", Available cards: " .. area.count,
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Get the card
    local card = area.cards[pos]

    -- Check if the card can be afforded (accounting for Credit Card joker via bankrupt_at)
    local available_money = G.GAME.dollars - G.GAME.bankrupt_at
    if card.cost.buy > 0 and card.cost.buy > available_money then
      send_response({
        message = "Card is not affordable. Cost: " .. card.cost.buy .. ", Available money: " .. available_money,
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Ensure there is space in joker area
    if card.set == "JOKER" then
      if gamestate.jokers.count >= gamestate.jokers.limit then
        send_response({
          message = "Cannot purchase joker card, joker slots are full. Current: "
            .. gamestate.jokers.count
            .. ", Limit: "
            .. gamestate.jokers.limit,
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
    end

    -- Ensure there is space in consumable area
    if card.set == "PLANET" or card.set == "SPECTRAL" or card.set == "TAROT" then
      if gamestate.consumables.count >= gamestate.consumables.limit then
        send_response({
          message = "Cannot purchase consumable card, consumable slots are full. Current: "
            .. gamestate.consumables.count
            .. ", Limit: "
            .. gamestate.consumables.limit,
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
    end

    local initial_shop_count = 0
    local initial_dest_count = 0
    local initial_money = gamestate.money

    if args.card then
      initial_shop_count = gamestate.shop.count
      initial_dest_count = gamestate.jokers.count
        + gamestate.consumables.count
        + (G.deck and G.deck.config and G.deck.config.card_count or 0)
    elseif args.voucher then
      initial_shop_count = gamestate.vouchers.count
      initial_dest_count = 0
      for _ in pairs(gamestate.used_vouchers) do
        initial_dest_count = initial_dest_count + 1
      end
    end

    -- Get the buy button from the card
    local btn
    if args.card then
      btn = G.shop_jokers.cards[pos].children.buy_button.definition
    elseif args.voucher then
      btn = G.shop_vouchers.cards[pos].children.buy_button.definition
    elseif args.pack then
      btn = G.shop_booster.cards[pos].children.buy_button.definition
    end
    if not btn then
      send_response({
        message = "No buy button found for card",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    -- Use appropriate function: use_card for vouchers, buy_from_shop for others
    if args.voucher or args.pack then
      G.FUNCS.use_card(btn)
    else
      G.FUNCS.buy_from_shop(btn)
    end

    -- Wait for buy completion with comprehensive verification
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        local done = false

        if args.card then
          local shop_count = (G.shop_jokers and G.shop_jokers.config and G.shop_jokers.config.card_count or 0)
          local dest_count = (G.jokers and G.jokers.config and G.jokers.config.card_count or 0)
            + (G.consumeables and G.consumeables.config and G.consumeables.config.card_count or 0)
            + (G.deck and G.deck.config and G.deck.config.card_count or 0)
          local shop_decreased = (shop_count == initial_shop_count - 1)
          local dest_increased = (dest_count == initial_dest_count + 1)
          local money_deducted = (G.GAME.dollars == initial_money - card.cost.buy)
          if shop_decreased and dest_increased and money_deducted and G.STATE == G.STATES.SHOP then
            done = true
          end
        elseif args.voucher then
          local shop_count = (G.shop_vouchers and G.shop_vouchers.config and G.shop_vouchers.config.card_count or 0)
          local dest_count = 0
          if G.GAME.used_vouchers then
            for _ in pairs(G.GAME.used_vouchers) do
              dest_count = dest_count + 1
            end
          end
          local shop_decreased = (shop_count == initial_shop_count - 1)
          local dest_increased = (dest_count == initial_dest_count + 1)
          local money_deducted = (G.GAME.dollars == initial_money - card.cost.buy)

          if shop_decreased and dest_increased and money_deducted and G.STATE == G.STATES.SHOP then
            done = true
          end
        elseif args.pack then
          local money_deducted = (G.GAME.dollars == initial_money - card.cost.buy)
          local pack_ready = (
            G.pack_cards
            and not G.pack_cards.REMOVED
            and G.pack_cards.cards[1]
            and G.STATE_COMPLETE
            and G.STATE == G.STATES.SMODS_BOOSTER_OPENED
          )
          if money_deducted and pack_ready then
            done = true
          end
        end

        if done then
          sendDebugMessage("Return buy()", "BB.ENDPOINTS")
          send_response(BB_GAMESTATE.get_gamestate())
          return true
        end

        return false
      end,
    }))
  end,
}
