-- src/lua/endpoints/buy_and_use.lua

-- ==========================================================================
-- Buy and Use Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.BuyAndUse.Params
---@field card integer? 0-based index of shop consumable to buy and use

-- ==========================================================================
-- Buy and Use Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "buy_and_use",

  description = "Buy and use a consumable card from the shop in one step",

  schema = {
    card = {
      type = "integer",
      required = false,
      description = "0-based index of shop consumable to buy and use",
    },
  },

  requires_state = { G.STATES.SHOP },

  ---@param args Request.Endpoint.BuyAndUse.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("buy_and_use()", "BB.ENDPOINTS")
    local gamestate = BB_GAMESTATE.get_gamestate()

    -- 1. Validate card param is provided
    if not args.card then
      send_response({
        message = "Invalid arguments. You must provide: card",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    local area = gamestate.shop
    local pos = args.card + 1

    -- 2. Validate shop has cards
    if #area.cards == 0 then
      send_response({
        message = "No consumables in the shop. Use `reroll` to restock the shop.",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- 3. Validate card index is in range
    if not area.cards[pos] then
      send_response({
        message = "Card index out of range. Index: " .. args.card .. ", Available cards: " .. area.count,
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    local card = area.cards[pos]
    local live_card = G.shop_jokers.cards[pos]

    -- 4. Affordability check (mirrors can_buy_and_use; handles Credit Card joker)
    local available_money = G.GAME.dollars - G.GAME.bankrupt_at
    if card.cost.buy > 0 and card.cost.buy > available_money then
      send_response({
        message = "Card is not affordable. Cost: " .. card.cost.buy .. ", Available money: " .. available_money,
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- 5. Feasibility gate. Mirrors G.FUNCS.can_buy_and_use, which the game only
    --    ever attaches to consumable shop cards. Card:can_use_consumeable()
    --    indexes ability.consumeable, so guard non-consumables (jokers/playing
    --    cards) for which the Buy-and-Use button never exists. (Per §2.3 we do
    --    NOT pre-call check_use here — the game calls it inside use_card.)
    local is_consumable = live_card.ability and live_card.ability.consumeable ~= nil
    if not is_consumable or not live_card:can_use_consumeable() then
      send_response({
        message = "Consumable '"
          .. (live_card.ability.name or card.label or "Unknown")
          .. "' cannot be buy-and-used at this time.",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    -- Capture initial state for completion detection
    local initial_shop_count = (G.shop_jokers and G.shop_jokers.config and G.shop_jokers.config.card_count or 0)
    local initial_money = gamestate.money

    -- Log what we're buy-and-using
    local item_name = live_card.ability.name or card.label or "Unknown"
    sendInfoMessage(string.format("Buy-and-using '%s' for $%d", item_name, card.cost.buy), "BB.ENDPOINTS")

    -- Programmatic mock-button invocation (ephemeral inline table; routes to
    -- the buy_and_use branch inside G.FUNCS.buy_from_shop via config.id).
    G.FUNCS.buy_from_shop({
      config = {
        id = "buy_and_use",
        ref_table = live_card,
      },
    })

    -- Completion detection: union of the buy-phase and use-phase terminal
    -- conditions. Race-free: during use the state is PLAY_TAROT (predicate
    -- waits); the Ankh-noop never leaves SHOP and never acquires the lock.
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        local shop_count = (G.shop_jokers and G.shop_jokers.config and G.shop_jokers.config.card_count or 0)
        local shop_decreased = (shop_count == initial_shop_count - 1)
        local money_deducted = (G.GAME.dollars == initial_money - card.cost.buy)
        if shop_decreased and money_deducted and G.STATE == G.STATES.SHOP and not G.CONTROLLER.locks.use then
          sendDebugMessage("buy_and_use() → ok", "BB.ENDPOINTS")
          send_response(BB_GAMESTATE.get_gamestate())
          return true
        end
        return false
      end,
    }))
  end,
}
