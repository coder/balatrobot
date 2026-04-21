-- src/lua/endpoints/highlight.lua

-- ==========================================================================
-- Highlight Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Highlight.Params
---@field card integer 0-based index of card to toggle highlight

-- ==========================================================================
-- Highlight Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "highlight",

  description = "Toggle highlight on a single card in the hand",

  schema = {
    card = {
      type = "integer",
      required = true,
      description = "0-based index of the card to toggle highlight",
    },
  },

  requires_state = { G.STATES.SELECTING_HAND },

  ---@param args Request.Endpoint.Highlight.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init highlight()", "BB.ENDPOINTS")

    if not G.hand.cards[args.card + 1] then
      send_response({
        message = "Invalid card index: " .. args.card,
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    G.hand.cards[args.card + 1]:click()

    sendDebugMessage("Return highlight() - toggled card " .. args.card, "BB.ENDPOINTS")
    local state_data = BB_GAMESTATE.get_gamestate()
    send_response(state_data)
  end,
}
