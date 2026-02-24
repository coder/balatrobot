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
        message = "No discards left. Play cards using `play` instead.",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    if #args.cards > G.hand.config.highlighted_limit then
      send_response({
        message = "You can only discard " .. G.hand.config.highlighted_limit .. " cards. Provide fewer card indices.",
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

    -- NOTE: Clear any existing highlights before selecting new cards
    -- prevent state pollution. This is a bit of a hack but could interfere
    -- with Boss Blind like Cerulean Bell.
    G.hand:unhighlight_all()

    for _, card_index in ipairs(args.cards) do
      G.hand.cards[card_index + 1]:click()
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

    local draw_to_hand = false

    G.E_MANAGER:add_event(Event({
      trigger = "immediate",
      blocking = false,
      blockable = false,
      created_on_pause = true,
      func = function()
        -- State progression for discard:
        -- Discard always continues current round: HAND_PLAYED -> DRAW_TO_HAND -> SELECTING_HAND
        if G.STATE == G.STATES.DRAW_TO_HAND then
          draw_to_hand = true
        end

        if draw_to_hand and G.buttons and G.STATE == G.STATES.SELECTING_HAND then
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
