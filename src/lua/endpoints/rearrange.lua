-- src/lua/endpoints/rearrange.lua

-- ==========================================================================
-- Rearrange Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Rearrange.Params
---@field hand integer[]? 0-based indices representing new order of cards in hand
---@field jokers integer[]? 0-based indices representing new order of jokers
---@field consumables integer[]? 0-based indices representing new order of consumables

-- ==========================================================================
-- Rearrange Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "rearrange",

  description = "Rearrange cards in hand, jokers, or consumables",

  schema = {
    hand = {
      type = "array",
      required = false,
      items = "integer",
      description = "0-based indices representing new order of cards in hand",
    },
    jokers = {
      type = "array",
      required = false,
      items = "integer",
      description = "0-based indices representing new order of jokers",
    },
    consumables = {
      type = "array",
      required = false,
      items = "integer",
      description = "0-based indices representing new order of consumables",
    },
  },

  requires_state = { G.STATES.SELECTING_HAND, G.STATES.SHOP, G.STATES.SMODS_BOOSTER_OPENED },

  ---@param args Request.Endpoint.Rearrange.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init rearrange()", "BB.ENDPOINTS")
    -- Validate exactly one parameter is provided
    local param_count = (args.hand and 1 or 0) + (args.jokers and 1 or 0) + (args.consumables and 1 or 0)
    if param_count == 0 then
      send_response({
        message = "Must provide exactly one of: hand, jokers, or consumables",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    elseif param_count > 1 then
      send_response({
        message = "Can only rearrange one type at a time",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Determine which type to rearrange and validate state-specific requirements
    local rearrange_type, source_array, indices, type_name

    if args.hand then
      -- Cards can only be rearranged during SELECTING_HAND
      if G.STATE ~= G.STATES.SELECTING_HAND and G.STATE ~= G.STATES.SMODS_BOOSTER_OPENED then
        send_response({
          message = "Can only rearrange hand during hand selection",
          name = BB_ERROR_NAMES.INVALID_STATE,
        })
        return
      end

      -- Validate G.hand exists (not tested)
      if not G.hand or not G.hand.cards then
        send_response({
          message = "No hand available to rearrange",
          name = BB_ERROR_NAMES.NOT_ALLOWED,
        })
        return
      end

      -- In SMODS_BOOSTER_OPENED, hand is only available in Arcana/Spectral packs
      if G.STATE == G.STATES.SMODS_BOOSTER_OPENED and #G.hand.cards == 0 then
        send_response({
          message = "No cards to rearrange. You can only rearrange hand in Arcana and Spectral packs.",
          name = BB_ERROR_NAMES.NOT_ALLOWED,
        })
        return
      end

      rearrange_type = "hand"
      source_array = G.hand.cards
      indices = args.hand
      type_name = "hand"
    elseif args.jokers then
      -- Validate G.jokers exists (not tested)
      if not G.jokers or not G.jokers.cards then
        send_response({
          message = "No jokers available to rearrange",
          name = BB_ERROR_NAMES.NOT_ALLOWED,
        })
        return
      end

      rearrange_type = "jokers"
      source_array = G.jokers.cards
      indices = args.jokers
      type_name = "jokers"
    else -- args.consumables
      -- Validate G.consumeables exists (not tested)
      if not G.consumeables or not G.consumeables.cards then
        send_response({
          message = "No consumables available to rearrange",
          name = BB_ERROR_NAMES.NOT_ALLOWED,
        })
        return
      end

      rearrange_type = "consumables"
      source_array = G.consumeables.cards
      indices = args.consumables
      type_name = "consumables"
    end

    assert(type(indices) == "table", "indices must be a table")

    -- Validate permutation: correct length, no duplicates, all indices present
    -- Check length matches
    if #indices ~= #source_array then
      send_response({
        message = "Must provide exactly " .. #source_array .. " indices for " .. type_name,
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Check for duplicates and range
    local seen = {}
    for _, idx in ipairs(indices) do
      -- Check range [0, N-1]
      if idx < 0 or idx >= #source_array then
        send_response({
          message = "Index out of range for " .. type_name .. ": " .. idx,
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end

      -- Check for duplicates
      if seen[idx] then
        send_response({
          message = "Duplicate index in " .. type_name .. ": " .. idx,
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
      seen[idx] = true
    end

    -- Create new array from indices (convert 0-based to 1-based)
    local new_array = {}
    for _, old_index in ipairs(indices) do
      table.insert(new_array, source_array[old_index + 1])
    end

    -- Replace the array in game state
    if rearrange_type == "hand" then
      G.hand.cards = new_array
    elseif rearrange_type == "jokers" then
      G.jokers.cards = new_array
    else -- consumables
      G.consumeables.cards = new_array
    end

    -- Update order fields on each card
    for i, card in ipairs(new_array) do
      if rearrange_type == "hand" then
        card.config.card.order = i
        if card.config.center then
          card.config.center.order = i
        end
      else -- jokers or consumables
        if card.ability then
          card.ability.order = i
        end
        if card.config and card.config.center then
          card.config.center.order = i
        end
      end
    end

    -- Wait for completion: state should remain stable after rearranging
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        -- Check that we're still in a valid state and arrays exist
        local done = false
        if args.hand then
          done = (G.STATE == G.STATES.SELECTING_HAND or G.STATE == G.STATES.SMODS_BOOSTER_OPENED) and G.hand ~= nil
        elseif args.jokers then
          done = (
            G.STATE == G.STATES.SHOP
            or G.STATE == G.STATES.SELECTING_HAND
            or G.STATE == G.STATES.SMODS_BOOSTER_OPENED
          ) and G.jokers ~= nil
        else -- consumables
          done = (
            G.STATE == G.STATES.SHOP
            or G.STATE == G.STATES.SELECTING_HAND
            or G.STATE == G.STATES.SMODS_BOOSTER_OPENED
          ) and G.consumeables ~= nil
        end

        if done then
          sendDebugMessage("Return rearrange()", "BB.ENDPOINTS")
          local state_data = BB_GAMESTATE.get_gamestate()
          send_response(state_data)
        end
        return done
      end,
    }))
  end,
}
