-- src/lua/endpoints/sort.lua

-- ==========================================================================
-- Sort Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Sort.Params
---@field by string Sort mode: "rank" or "suit"

-- ==========================================================================
-- Sort Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "sort",

  description = "Sort the hand by rank or suit (mirrors the in-game Sort buttons)",

  schema = {
    by = {
      type = "string",
      required = true,
      description = 'Sort mode: "rank" or "suit"',
    },
  },

  requires_state = { G.STATES.SELECTING_HAND },

  ---@param args Request.Endpoint.Sort.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("sort()", "BB.ENDPOINTS")

    -- Gate: manual enum check (the validator has no enum support)
    if args.by ~= "rank" and args.by ~= "suit" then
      send_response({
        message = 'Sort \'by\' must be "rank" or "suit", got "' .. args.by .. '"',
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    if args.by == "rank" then
      G.FUNCS.sort_hand_value({})
    else
      G.FUNCS.sort_hand_suit({})
    end

    sendInfoMessage("Sorting hand by " .. args.by, "BB.ENDPOINTS")

    -- Wait for the hand to be sorted (predicate α)
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        local done = G.STATE == G.STATES.SELECTING_HAND and G.hand ~= nil
        if done then
          sendDebugMessage("sort() → ok", "BB.ENDPOINTS")
          send_response(BB_GAMESTATE.get_gamestate())
        end
        return done
      end,
    }))
  end,
}
