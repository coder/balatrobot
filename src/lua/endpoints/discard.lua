-- src/lua/endpoints/discard.lua

---@type BB_LOGGER
local BB_LOGGER = assert(SMODS.load_file("src/lua/utils/logger.lua"))()

-- ==========================================================================
-- Discard Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Discard.Params
---@field cards integer[] 0-based indices of cards to discard

-- ==========================================================================
-- Discard Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "discard",

  description = "Discard cards from the hand",

  schema = {
    cards = {
      type = "array",
      required = true,
      items = "integer",
      description = "0-based indices of cards to discard",
    },
  },

  requires_state = { G.STATES.SELECTING_HAND },

  ---@param args Request.Endpoint.Discard.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init discard()", "BB.ENDPOINTS")
    if #args.cards == 0 then
      send_response({
        message = "Must provide at least one card to discard",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    if G.GAME.current_round.discards_left <= 0 then
      send_response({
        message = "No discards left",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    if #args.cards > G.hand.config.highlighted_limit then
      send_response({
        message = "You can only discard " .. G.hand.config.highlighted_limit .. " cards",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    for _, card_index in ipairs(args.cards) do
      if not G.hand.cards[card_index + 1] then
        send_response({
          message = "Invalid card index: " .. card_index,
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
    end

    -- Intelligently match selection to args.cards
    -- We DON'T use unhighlight_all() because it cheats Boss Blinds (Cerulean Bell).
    -- Instead, we toggle cards that should be selected but aren't,
    -- and we don't touch cards that are already selected (even if forced).
    
    local target_indices = {}
    for _, idx in ipairs(args.cards) do
        target_indices[idx + 1] = true
    end

    for i, card in ipairs(G.hand.cards) do
        local is_selected = false
        for _, highlighted_card in ipairs(G.hand.highlighted) do
            if highlighted_card == card then
                is_selected = true
                break
            end
        end

        local should_be_selected = target_indices[i]
        if should_be_selected and not is_selected then
            card:click()
        end
        -- Note: We don't UNSELECT cards that the AI didn't ask for,
        -- because if they are selected, they might be forced by a Boss.
    end

    -- Log the cards being discarded
    local card_str = BB_LOGGER.format_playing_cards(G.hand.cards, args.cards)
    local remaining = G.GAME.current_round.discards_left - 1
    sendDebugMessage(
      string.format("Discarding %d cards: %s (%d discards left)", #args.cards, card_str, remaining),
      "BB.ENDPOINTS"
    )

    ---@diagnostic disable-next-line: undefined-field
    local discard_button = UIBox:get_UIE_by_ID("discard_button", G.buttons.UIRoot)
    assert(discard_button ~= nil, "discard() discard button not found")
    G.FUNCS.discard_cards_from_highlighted(discard_button)

    local left_selecting = false

    G.E_MANAGER:add_event(Event({
      trigger = "immediate",
      blocking = false,
      blockable = false,
      created_on_pause = true,
      func = function()
        -- State progression for discard:
        -- SELECTING_HAND -> HAND_PLAYED -> DRAW_TO_HAND -> SELECTING_HAND
        -- Track that we left SELECTING_HAND (animation started) to avoid
        -- returning before the discard animation even begins.
        if G.STATE ~= G.STATES.SELECTING_HAND then
          left_selecting = true
        end

        if left_selecting and G.buttons and G.STATE == G.STATES.SELECTING_HAND then
          sendDebugMessage("Return discard()", "BB.ENDPOINTS")
          local state_data = BB_GAMESTATE.get_gamestate()
          send_response(state_data)
          return true
        end

        return false
      end,
    }))
  end,
}
