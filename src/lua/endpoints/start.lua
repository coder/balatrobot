-- src/lua/endpoints/start.lua

-- ==========================================================================
-- Start Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Start.Params
---@field deck Deck Deck key from G.P_CENTERS (e.g., "b_red", "b_blue")
---@field stake Stake key from G.P_STAKES (e.g., "stake_white", "stake_red", "stake_black")
---@field seed string? optional seed for the run

-- ==========================================================================
-- Start Endpoint
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
      description = "Deck key from G.P_CENTERS (e.g., 'b_red', 'b_blue')",
    },
    stake = {
      type = "string",
      required = true,
      description = "Stake key from G.P_STAKES (e.g., 'stake_white', 'stake_red', 'stake_black')",
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
    sendDebugMessage("start()", "BB.ENDPOINTS")

    -- Validate and map stake key
    local stake_data = G.P_STAKES[args.stake]
    if not stake_data then
      sendWarnMessage("Invalid stake key: " .. tostring(args.stake), "BB.ENDPOINTS")
      send_response({
        message = "Expected a stake_* key from G.P_STAKES (e.g. stake_white, stake_red). Got: " .. tostring(args.stake),
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end
    local stake_number = stake_data.order or stake_data.stake_level

    -- Validate deck key against G.P_CENTERS
    local deck_center = G.P_CENTERS and G.P_CENTERS[args.deck]
    if not deck_center or deck_center.set ~= "Back" then
      sendWarnMessage("Invalid deck key: " .. tostring(args.deck), "BB.ENDPOINTS")
      send_response({
        message = "Expected a b_* deck key from G.P_CENTERS (e.g. b_red, b_blue). Got: " .. tostring(args.deck),
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Reset the game (setup_run and exit_overlay_menu)
    G.FUNCS.setup_run({ config = {} })
    G.FUNCS.exit_overlay_menu()

    -- Find and set the deck using the deck key
    local deck_found = false
    if G.P_CENTER_POOLS and G.P_CENTER_POOLS.Back then
      for _, deck_data in pairs(G.P_CENTER_POOLS.Back) do
        if deck_data.key == args.deck then
          G.GAME.selected_back:change_to(deck_data)
          G.GAME.viewed_back:change_to(deck_data)
          deck_found = true
          break
        end
      end
    end

    if not deck_found then
      sendWarnMessage("Deck not found in G.P_CENTER_POOLS.Back: " .. args.deck, "BB.ENDPOINTS")
      send_response({
        message = "Deck not found in game data: " .. args.deck,
        name = BB_ERROR_NAMES.INTERNAL_ERROR,
      })
      return
    end

    -- Start the run with stake number and optional seed
    local run_params = { stake = stake_number }
    if args.seed then
      run_params.seed = args.seed
    end

    sendInfoMessage(
      "Starting run: "
        .. args.deck
        .. ", stake="
        .. tostring(stake_number)
        .. " ("
        .. args.stake
        .. "), seed="
        .. tostring(args.seed or "none"),
      "BB.ENDPOINTS"
    )
    G.FUNCS.start_run(nil, run_params)

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
          sendDebugMessage("start() → BLIND_SELECT", "BB.ENDPOINTS")
          local state_data = BB_GAMESTATE.get_gamestate()
          send_response(state_data)
        end

        return done
      end,
    }))
  end,
}
