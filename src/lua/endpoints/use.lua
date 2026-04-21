-- src/lua/endpoints/use.lua

---@type BB_LOGGER
local BB_LOGGER = assert(SMODS.load_file("src/lua/utils/logger.lua"))()

-- ==========================================================================
-- Use Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Use.Params
---@field consumable integer 0-based index of consumable to use
---@field cards integer[]? 0-based indices of cards to target

-- ==========================================================================
-- Use Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "use",

  description = "Use a consumable card with optional target cards",

  schema = {
    consumable = {
      type = "integer",
      required = true,
      description = "0-based index of consumable to use",
    },
    cards = {
      type = "array",
      required = false,
      description = "0-based indices of cards to target (required only if consumable requires cards)",
      items = "integer",
    },
  },

  requires_state = { G.STATES.SELECTING_HAND, G.STATES.SHOP },

  ---@param args Request.Endpoint.Use.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init use()", "BB.ENDPOINTS")

    -- Step 1: Consumable Index Validation
    if args.consumable < 0 or args.consumable >= #G.consumeables.cards then
      send_response({
        message = "Consumable index out of range: " .. args.consumable,
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    local consumable_card = G.consumeables.cards[args.consumable + 1]

    -- Step 2: Determine Card Selection Requirements
    local requires_cards = consumable_card.ability.consumeable.max_highlighted ~= nil

    -- Step 3: State Validation for Card-Selecting Consumables
    if requires_cards and G.STATE ~= G.STATES.SELECTING_HAND then
      send_response({
        message = "Consumable '"
          .. consumable_card.ability.name
          .. "' requires card selection and can only be used in SELECTING_HAND state",
        name = BB_ERROR_NAMES.INVALID_STATE,
      })
      return
    end

    -- Step 4: Cards Parameter Validation
    if requires_cards then
      if not args.cards or #args.cards == 0 then
        send_response({
          message = "Consumable '" .. consumable_card.ability.name .. "' requires card selection",
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end

      -- Validate each card index is in range
      for _, card_idx in ipairs(args.cards) do
        if card_idx < 0 or card_idx >= #G.hand.cards then
          send_response({
            message = "Card index out of range: " .. card_idx,
            name = BB_ERROR_NAMES.BAD_REQUEST,
          })
          return
        end
      end
    end

    -- Step 5: Explicit Min/Max Card Count Validation
    if requires_cards then
      local min_cards = consumable_card.ability.consumeable.min_highlighted or 1
      local max_cards = consumable_card.ability.consumeable.max_highlighted
      local card_count = #args.cards

      -- Check if consumable requires exact number of cards
      if min_cards == max_cards and card_count ~= min_cards then
        send_response({
          message = string.format(
            "Consumable '%s' requires exactly %d card%s (provided: %d)",
            consumable_card.ability.name,
            min_cards,
            min_cards == 1 and "" or "s",
            card_count
          ),
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end

      -- For consumables with range, check min and max separately
      if card_count < min_cards then
        send_response({
          message = string.format(
            "Consumable '%s' requires at least %d card%s (provided: %d)",
            consumable_card.ability.name,
            min_cards,
            min_cards == 1 and "" or "s",
            card_count
          ),
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end

      if card_count > max_cards then
        send_response({
          message = string.format(
            "Consumable '%s' requires at most %d card%s (provided: %d)",
            consumable_card.ability.name,
            max_cards,
            max_cards == 1 and "" or "s",
            card_count
          ),
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
    end

    -- Step 6: Card Selection Setup
    if requires_cards then
      -- Clear existing selection
      for i = #G.hand.highlighted, 1, -1 do
        G.hand:remove_from_highlighted(G.hand.highlighted[i], true)
      end

      -- Add cards using proper method
      for _, card_idx in ipairs(args.cards) do
        local hand_card = G.hand.cards[card_idx + 1] -- Convert 0-based to 1-based
        G.hand:add_to_highlighted(hand_card, true) -- silent=true
      end
    end

    -- Log what we're using with target cards
    local cons_name = consumable_card.ability.name
    if args.cards and #args.cards > 0 then
      local targets = BB_LOGGER.format_playing_cards(G.hand.cards, args.cards)
      sendDebugMessage(string.format("Using '%s' on: %s", cons_name, targets), "BB.ENDPOINTS")
    else
      sendDebugMessage(string.format("Using '%s' (no targets)", cons_name), "BB.ENDPOINTS")
    end

    -- Step 7: Game-Level Validation (e.g. try to use Familiar Spectral when G.hand is not available)
    if not consumable_card:can_use_consumeable() then
      send_response({
        message = "Consumable '" .. consumable_card.ability.name .. "' cannot be used at this time",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    -- Step 8: Space Check (not tested)
    if consumable_card:check_use() then
      send_response({
        message = "Cannot use consumable '" .. consumable_card.ability.name .. "': insufficient space",
        name = BB_ERROR_NAMES.NOT_ALLOWED,
      })
      return
    end

    -- Create mock UI element for game function
    local mock_element = {
      config = {
        ref_table = consumable_card,
      },
    }

    -- Call game's use_card function
    G.FUNCS.use_card(mock_element, true, true)

    -- Completion Detection
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        -- Condition 1: State restored
        local state_restored = G.STATE == G.STATES.SELECTING_HAND or G.STATE == G.STATES.SHOP

        -- Condition 2: Controller unlocked
        local controller_unlocked = not G.CONTROLLER.locks.use

        -- Condition 3: no stop use
        local no_stop_use = not (G.GAME.STOP_USE and G.GAME.STOP_USE > 0)

        if state_restored and controller_unlocked and no_stop_use then
          sendDebugMessage("Return use()", "BB.ENDPOINTS")
          send_response(BB_GAMESTATE.get_gamestate())
          return true
        end

        return false
      end,
    }))
  end,
}
