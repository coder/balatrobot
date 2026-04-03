-- src/lua/endpoints/play.lua

---@type BB_LOGGER
local BB_LOGGER = assert(SMODS.load_file("src/lua/utils/logger.lua"))()

-- Win overlay state is now tracked in BB_GAMESTATE (shared with love.update)

-- ==========================================================================
-- Play Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Play.Params
---@field cards integer[] 0-based indices of cards to play

-- ==========================================================================
-- Play Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "play",

  description = "Play a card from the hand",

  schema = {
    cards = {
      type = "array",
      required = true,
      items = "integer",
      description = "0-based indices of cards to play",
    },
  },

  requires_state = { G.STATES.SELECTING_HAND },

  ---@param args Request.Endpoint.Play.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init play()", "BB.ENDPOINTS")
    if #args.cards == 0 then
      send_response({
        message = "Must provide at least one card to play",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    if #args.cards > G.hand.config.highlighted_limit then
      send_response({
        message = "You can only play " .. G.hand.config.highlighted_limit .. " cards",
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

    -- Log the cards being played
    local card_str = BB_LOGGER.format_playing_cards(G.hand.cards, args.cards)
    sendDebugMessage(string.format("Playing %d cards: %s", #args.cards, card_str), "BB.ENDPOINTS")

    ---@diagnostic disable-next-line: undefined-field
    local play_button = UIBox:get_UIE_by_ID("play_button", G.buttons.UIRoot)
    assert(play_button ~= nil, "play() play button not found")
    G.FUNCS.play_cards_from_highlighted(play_button)

    local hand_played = false
    local draw_to_hand = false

    -- NOTE: GAME_OVER detection cannot happen inside this event function
    -- because when G.STATE becomes GAME_OVER, the game sets G.SETTINGS.paused = true,
    -- which stops all event processing. This callback is set so that love.update
    -- (which runs even when paused) can detect GAME_OVER immediately.
    BB_GAMESTATE.on_game_over = send_response

    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        -- State progression:
        -- Loss: HAND_PLAYED -> NEW_ROUND -> (game paused) -> GAME_OVER
        -- Win round: HAND_PLAYED -> NEW_ROUND -> ROUND_EVAL
        -- Win game: HAND_PLAYED -> NEW_ROUND -> ROUND_EVAL (with G.GAME.won = true)
        -- Keep playing current round: HAND_PLAYED -> DRAW_TO_HAND -> SELECTING_HAND

        -- Track state transitions
        if G.STATE == G.STATES.HAND_PLAYED then
          hand_played = true
        end

        if G.STATE == G.STATES.DRAW_TO_HAND then
          draw_to_hand = true
        end

        -- if G.STATE == G.STATES.GAME_OVER then
        --   -- NOTE: GAME_OVER is detected by gamestate.on_game_over callback in love.update
        --   return true
        -- end

        if G.STATE == G.STATES.ROUND_EVAL then
          -- Early exit if basic conditions not met
          if not G.round_eval or not G.STATE_COMPLETE or G.CONTROLLER.locked then
            return false
          end

          -- Game is won — love.update auto-dismisses the overlay.
          -- Wait here until that's done before looking for cash_out button.
          if G.GAME.won and not BB_GAMESTATE.win_overlay_dismissed then
            return false
          end

          -- Wait for first scoring row (blind1) to be added to the UI
          -- This ensures the main scoring events have started processing
          local has_blind1 = G.round_eval:get_UIE_by_ID("dollar_blind1") ~= nil

          -- Wait for cash_out_button to ensure the last scoring row (bottom) has been processed
          local has_cash_out_button = false
          for _, b in ipairs(G.I.UIBOX) do
            if b:get_UIE_by_ID("cash_out_button") then
              has_cash_out_button = true
              break
            end
          end

          -- Both first and last scoring rows must be present
          if has_blind1 and has_cash_out_button then
            local state_data = BB_GAMESTATE.get_gamestate()
            sendDebugMessage("Return play() - cash out", "BB.ENDPOINTS")
            send_response(state_data)
            return true
          end
        end

        if draw_to_hand and hand_played and G.buttons and G.STATE == G.STATES.SELECTING_HAND then
          sendDebugMessage("Return play() - same round", "BB.ENDPOINTS")
          local state_data = BB_GAMESTATE.get_gamestate()
          send_response(state_data)
          return true
        end

        return false
      end,
    }))
  end,
}
