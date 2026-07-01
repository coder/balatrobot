-- src/lua/endpoints/sell.lua

-- ==========================================================================
-- Sell Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Sell.Params
---@field joker integer? 0-based index of joker to sell
---@field consumable integer? 0-based index of consumable to sell

-- ==========================================================================
-- Sell Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "sell",

  description = "Sell a joker or consumable from player inventory",

  schema = {
    joker = {
      type = "integer",
      required = false,
      description = "0-based index of joker to sell",
    },
    consumable = {
      type = "integer",
      required = false,
      description = "0-based index of consumable to sell",
    },
  },

  requires_state = {
    G.STATES.SELECTING_HAND,
    G.STATES.SHOP,
    G.STATES.SMODS_BOOSTER_OPENED,
    G.STATES.ROUND_EVAL,
    G.STATES.BLIND_SELECT,
  },

  ---@param args Request.Endpoint.Sell.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("sell()", "BB.ENDPOINTS")

    -- Validate exactly one parameter is provided
    local param_count = (args.joker and 1 or 0) + (args.consumable and 1 or 0)
    if param_count == 0 then
      send_response({
        message = "Must provide exactly one of: joker or consumable",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    elseif param_count > 1 then
      send_response({
        message = "Can only sell one item at a time",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Determine which type to sell and validate existence
    local source_array, pos, sell_type

    if args.joker then
      -- Validate G.jokers exists and has cards
      if not G.jokers or not G.jokers.config or G.jokers.config.card_count == 0 then
        send_response({
          message = "No jokers available to sell",
          name = BB_ERROR_NAMES.NOT_ALLOWED,
        })
        return
      end
      source_array = G.jokers.cards
      pos = args.joker + 1 -- Convert to 1-based
      sell_type = "joker"
    else -- args.consumable
      -- Validate G.consumeables exists and has cards
      if not G.consumeables or not G.consumeables.config or G.consumeables.config.card_count == 0 then
        send_response({
          message = "No consumables available to sell",
          name = BB_ERROR_NAMES.NOT_ALLOWED,
        })
        return
      end
      source_array = G.consumeables.cards
      pos = args.consumable + 1 -- Convert to 1-based
      sell_type = "consumable"
    end

    -- Validate card exists at index
    if not source_array[pos] then
      send_response({
        message = "Index out of range for " .. sell_type .. ": " .. (pos - 1),
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    local card = source_array[pos]

    -- Track initial state for completion verification
    local initial_money = G.GAME.dollars
    local expected_money = initial_money + card.sell_cost

    -- Log what we're selling
    local item_name = card.ability and card.ability.name or "Unknown"
    sendInfoMessage(string.format("Selling %s '%s' for $%d", sell_type, item_name, card.sell_cost), "BB.ENDPOINTS")

    -- Create mock UI element for G.FUNCS.sell_card
    local mock_element = {
      config = {
        ref_table = card,
      },
    }

    -- Call the game function to trigger sell
    G.FUNCS.sell_card(mock_element)

    -- Wait for sell completion with verification
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        -- 1. Card was removed
        local card_removed = card.removed == true

        -- 2. Money increased by sell_cost
        local money_increased = (G.GAME.dollars == expected_money)

        -- 3. State stability
        local state_stable = G.STATE_COMPLETE == true

        -- 4. Still in valid state
        local valid_state = (
          G.STATE == G.STATES.SHOP
          or G.STATE == G.STATES.SELECTING_HAND
          or G.STATE == G.STATES.SMODS_BOOSTER_OPENED
          or G.STATE == G.STATES.ROUND_EVAL
          or G.STATE == G.STATES.BLIND_SELECT
        )

        if card_removed and money_increased and state_stable and valid_state then
          sendDebugMessage("sell() → ok", "BB.ENDPOINTS")
          send_response(BB_GAMESTATE.get_gamestate())
          return true
        end

        return false
      end,
    }))
  end,
}
