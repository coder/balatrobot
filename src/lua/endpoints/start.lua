-- src/lua/endpoints/start.lua

-- ==========================================================================
-- Start Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Start.Params
---@field deck Deck deck enum value (e.g., "RED", "BLUE", "YELLOW")
---@field stake Stake stake enum value (e.g., "WHITE", "RED", "GREEN", "BLACK", "BLUE", "PURPLE", "ORANGE", "GOLD")
---@field seed string? optional seed for the run

-- ==========================================================================
-- Start Endpoint Utils
-- ==========================================================================

local DECK_ENUM_TO_NAME = {
  RED = "Red Deck",
  BLUE = "Blue Deck",
  YELLOW = "Yellow Deck",
  GREEN = "Green Deck",
  BLACK = "Black Deck",
  MAGIC = "Magic Deck",
  NEBULA = "Nebula Deck",
  GHOST = "Ghost Deck",
  ABANDONED = "Abandoned Deck",
  CHECKERED = "Checkered Deck",
  ZODIAC = "Zodiac Deck",
  PAINTED = "Painted Deck",
  ANAGLYPH = "Anaglyph Deck",
  PLASMA = "Plasma Deck",
  ERRATIC = "Erratic Deck",
}

local STAKE_ENUM_TO_NUMBER = {
  WHITE = 1,
  RED = 2,
  GREEN = 3,
  BLACK = 4,
  BLUE = 5,
  PURPLE = 6,
  ORANGE = 7,
  GOLD = 8,
}

-- ==========================================================================
-- Start Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "start",

  description = "Start a new game run with specified deck and stake",

  schema = {
    deck = {
      type = "string",
      required = true,
      description = "Deck enum value (e.g., 'RED', 'BLUE', 'YELLOW')",
    },
    stake = {
      type = "string",
      required = true,
      description = "Stake enum value (e.g., 'WHITE', 'RED', 'GREEN', 'BLACK', 'BLUE', 'PURPLE', 'ORANGE', 'GOLD')",
    },
    seed = {
      type = "string",
      required = false,
      description = "Optional seed for the run",
    },
  },

  requires_state = { G.STATES.MENU },

  ---@param args Request.Endpoint.Start.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init start()", "BB.ENDPOINTS")

    -- Validate and map stake enum
    local stake_number = STAKE_ENUM_TO_NUMBER[args.stake]
    if not stake_number then
      sendDebugMessage("start() called with invalid stake enum: " .. tostring(args.stake), "BB.ENDPOINTS")
      send_response({
        message = "Invalid stake enum. Must be one of: WHITE, RED, GREEN, BLACK, BLUE, PURPLE, ORANGE, GOLD. Got: "
          .. tostring(args.stake),
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Validate and map deck enum
    local deck_name = DECK_ENUM_TO_NAME[args.deck]
    if not deck_name then
      sendDebugMessage("start() called with invalid deck enum: " .. tostring(args.deck), "BB.ENDPOINTS")
      send_response({
        message = "Invalid deck enum. Must be one of: RED, BLUE, YELLOW, GREEN, BLACK, MAGIC, NEBULA, GHOST, ABANDONED, CHECKERED, ZODIAC, PAINTED, ANAGLYPH, PLASMA, ERRATIC. Got: "
          .. tostring(args.deck),
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Reset win overlay flags from previous run
    BB_GAMESTATE.win_overlay_dismissed = false
    BB_GAMESTATE.win_overlay_dismissing = false

    -- Reset the game (setup_run and exit_overlay_menu)
    -- Use pcall to handle cases where the overlay isn't fully ready
    pcall(function()
      G.FUNCS.setup_run({ config = {} })
      G.FUNCS.exit_overlay_menu()
    end)

    -- Find and set the deck using the mapped deck name
    local deck_found = false
    if G.P_CENTER_POOLS and G.P_CENTER_POOLS.Back then
      for _, deck_data in pairs(G.P_CENTER_POOLS.Back) do
        if deck_data.name == deck_name then
          sendDebugMessage("Setting deck to: " .. deck_data.name .. " (from enum: " .. args.deck .. ")", "BB.ENDPOINTS")
          G.GAME.selected_back:change_to(deck_data)
          G.GAME.viewed_back:change_to(deck_data)
          deck_found = true
          break
        end
      end
    end

    if not deck_found then
      sendDebugMessage("start() deck not found in game data: " .. deck_name, "BB.ENDPOINTS")
      send_response({
        message = "Deck not found in game data: " .. deck_name,
        name = BB_ERROR_NAMES.INTERNAL_ERROR,
      })
      return
    end

    -- Start the run with stake number and optional seed
    local run_params = { stake = stake_number }
    if args.seed then
      run_params.seed = args.seed
    end

    sendDebugMessage(
      "Starting run with stake="
        .. tostring(stake_number)
        .. " ("
        .. args.stake
        .. "), seed="
        .. tostring(args.seed or "none"),
      "BB.ENDPOINTS"
    )
    local ok, err = pcall(G.FUNCS.start_run, nil, run_params)
    if not ok then
      sendDebugMessage("start_run failed: " .. tostring(err) .. " — retrying after delete_run", "BB.ENDPOINTS")
      -- Clean up stale state and retry
      pcall(function() G:delete_run() end)
      local ok2, err2 = pcall(G.FUNCS.start_run, nil, run_params)
      if not ok2 then
        sendDebugMessage("start_run retry also failed: " .. tostring(err2), "BB.ENDPOINTS")
        send_response({
          message = "Failed to start run: " .. tostring(err2),
          name = BB_ERROR_NAMES.INTERNAL_ERROR,
        })
        return
      end
    end

    -- Wait for run to start using Balatro's Event Manager
    G.E_MANAGER:add_event(Event({
      no_delete = true,
      trigger = "condition",
      blocking = false,
      func = function()
        local done = (
          G.GAME.blind_on_deck ~= nil
          and G.blind_select_opts ~= nil
          and G.blind_select_opts["small"]:get_UIE_by_ID("tag_Small") ~= nil
        )
        if done then
          sendDebugMessage("Return start()", "BB.ENDPOINTS")
          local state_data = BB_GAMESTATE.get_gamestate()
          send_response(state_data)
        end

        return done
      end,
    }))
  end,
}
