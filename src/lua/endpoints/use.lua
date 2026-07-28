-- src/lua/endpoints/use.lua

---@type BB_FORMAT
local BB_FORMAT = assert(SMODS.load_file("src/lua/utils/format.lua"))()

-- ==========================================================================
-- Use Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Use.Params
---@field consumable integer 0-based index of consumable to use
---@field cards integer[]? 0-based indices of cards to target

-- ==========================================================================
-- Reveal Snapshot (transient `revealed` field support)
-- ==========================================================================

---Compute the set of currently-hidden cards a conversion consumable will flip
---face-up during its flip→modify→flip animation, so the `use` response can stamp
---the transient `revealed` flag on them. Mirrors the use_consumeable branches in
---card.lua:1110-1159 (mod_conv/suit_conv operate on G.hand.highlighted) and
---card.lua:1235-1266 (Sigil/Ouija operate on the whole G.hand.cards).
---
---Must run BEFORE G.FUNCS.use_card, which clears G.hand.highlighted mid-op.
---@param consumable_card table The consumable about to be used
---@return table[] snapshot Array of hidden (facing == "back") game card objects
local function get_reveal_snapshot(consumable_card)
  local ability = consumable_card.ability or {}
  local consumeable = ability.consumeable or {}

  local affected
  if consumeable.mod_conv or consumeable.suit_conv then
    affected = G.hand.highlighted
  elseif ability.name == "Sigil" or ability.name == "Ouija" then
    affected = G.hand.cards
  else
    return {}
  end

  local snapshot = {}
  for _, card in ipairs(affected) do
    if card.facing == "back" then
      snapshot[#snapshot + 1] = card
    end
  end
  return snapshot
end

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

  requires_state = {
    G.STATES.SELECTING_HAND,
    G.STATES.SHOP,
    G.STATES.SMODS_BOOSTER_OPENED,
    G.STATES.ROUND_EVAL,
    G.STATES.BLIND_SELECT,
  },

  ---@param args Request.Endpoint.Use.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("use()", "BB.ENDPOINTS")

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
    if requires_cards and G.STATE ~= G.STATES.SELECTING_HAND and G.STATE ~= G.STATES.SMODS_BOOSTER_OPENED then
      send_response({
        message = "Consumable '"
          .. consumable_card.ability.name
          .. "' requires card selection and can only be used in SELECTING_HAND or SMODS_BOOSTER_OPENED state.",
        name = BB_ERROR_NAMES.INVALID_STATE,
      })
      return
    end

    -- Step 4: Cards Parameter Validation
    if requires_cards then
      if not args.cards or #args.cards == 0 then
        send_response({
          message = "Consumable '"
            .. consumable_card.ability.name
            .. "' requires card selection. Provide target cards via the `cards` parameter.",
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
            "Consumable '%s' requires exactly %d card%s (provided: %d). Provide the correct number of cards via the `cards` parameter.",
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
            "Consumable '%s' requires at least %d card%s (provided: %d). Provide more cards via the `cards` parameter.",
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
            "Consumable '%s' requires at most %d card%s (provided: %d). Provide fewer cards via the `cards` parameter.",
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
      local targets = BB_FORMAT.format_playing_cards(G.hand.cards, args.cards)
      sendInfoMessage(string.format("Using '%s' on: %s", cons_name, targets), "BB.ENDPOINTS")
    else
      sendInfoMessage(string.format("Using '%s'", cons_name), "BB.ENDPOINTS")
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
        message = "Cannot use consumable '"
          .. consumable_card.ability.name
          .. "': insufficient space. Use `sell` or `use` to free up space.",
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

    -- Snapshot the hidden cards a conversion consumable will momentarily expose
    -- during its flip→modify→flip animation. Captured BEFORE use_card because
    -- use_card clears G.hand.highlighted mid-operation. Drives the transient
    -- `revealed` flag stamped on the response.
    local reveal_snapshot = get_reveal_snapshot(consumable_card)

    -- Call game's use_card function
    G.FUNCS.use_card(mock_element, true, true)

    -- Completion Detection
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        -- Condition 1: State restored
        local state_restored = G.STATE == G.STATES.SELECTING_HAND
          or G.STATE == G.STATES.SHOP
          or G.STATE == G.STATES.SMODS_BOOSTER_OPENED
          or G.STATE == G.STATES.ROUND_EVAL
          or G.STATE == G.STATES.BLIND_SELECT

        -- Condition 2: Controller unlocked
        local controller_unlocked = not G.CONTROLLER.locks.use

        -- Condition 3: no stop use
        local no_stop_use = not (G.GAME.STOP_USE and G.GAME.STOP_USE > 0)

        if state_restored and controller_unlocked and no_stop_use then
          sendDebugMessage("use() → ok", "BB.ENDPOINTS")
          -- Stamp the transient `revealed` flag onto the response gamestate for
          -- the cards the consumable momentarily exposed, then clear the
          -- registry so `revealed` never leaks into later (non-use) snapshots.
          BB_GAMESTATE.set_revealed(reveal_snapshot)
          send_response(BB_GAMESTATE.get_gamestate())
          BB_GAMESTATE.clear_revealed()
          return true
        end

        return false
      end,
    }))
  end,
}
