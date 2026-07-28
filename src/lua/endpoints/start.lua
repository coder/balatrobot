-- src/lua/endpoints/start.lua

-- ==========================================================================
-- Start Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Start.Params
---@field deck Deck? Deck key from G.P_CENTERS (e.g., "b_red", "b_blue"). Required unless `challenge` is given.
---@field stake Stake? Stake key from G.P_STAKES (e.g., "stake_white", "stake_red", "stake_black"). Required unless `challenge` is given.
---@field seed string? Optional seed for the run
---@field challenge Challenge? Optional challenge id from G.CHALLENGES (e.g., "c_omelette_1"). Mutually exclusive with `deck`/`stake`; composes freely with `seed`.

-- ==========================================================================
-- Start Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "start",

  description = "Start a new game run with specified deck and stake, or a challenge run",

  schema = {
    deck = {
      type = "string",
      required = false,
      description = "Deck key from G.P_CENTERS (e.g., 'b_red', 'b_blue'). Required unless 'challenge' is given.",
    },
    stake = {
      type = "string",
      required = false,
      description = "Stake key from G.P_STAKES (e.g., 'stake_white', 'stake_red', 'stake_black'). Required unless 'challenge' is given.",
    },
    seed = {
      type = "string",
      required = false,
      description = "Optional seed for the run",
    },
    challenge = {
      type = "string",
      required = false,
      description = "Optional challenge id from G.CHALLENGES (e.g., 'c_omelette_1'). Mutually exclusive with 'deck'/'stake'; composes freely with 'seed'.",
    },
  },

  requires_state = { G.STATES.MENU },

  ---@param args Request.Endpoint.Start.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("start()", "BB.ENDPOINTS")

    -- Exclusivity: challenge cannot be combined with deck or stake. Checked
    -- first (independent of value validity) so a bad challenge id combined
    -- with a deck still reports the conflict, not the unknown id.
    if args.challenge and (args.deck or args.stake) then
      sendWarnMessage("challenge combined with deck/stake: " .. tostring(args.challenge), "BB.ENDPOINTS")
      send_response({
        message = "Param 'challenge' cannot be combined with 'deck' or 'stake'",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- ========================================================================
    -- Challenge branch
    -- ========================================================================
    if args.challenge then
      -- Resolve the id against the live G.CHALLENGES table (mirrors
      -- SMODS.Challenge.get_obj, game_object.lua:2854). Runtime lookup (not a
      -- static enum) so SMODS-injected challenges are reachable.
      local challenge_entry
      for _, v in ipairs(G.CHALLENGES) do
        if v.id == args.challenge then
          challenge_entry = v
          break
        end
      end
      if not challenge_entry then
        sendWarnMessage("Invalid challenge id: " .. tostring(args.challenge), "BB.ENDPOINTS")
        send_response({
          message = "Expected a c_* challenge id from G.CHALLENGES (e.g. c_omelette_1). Got: "
            .. tostring(args.challenge),
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end

      -- Mirror G.FUNCS.start_challenge_run (button_callbacks.lua:1847).
      -- deck/stake resolution and change_to are intentionally SKIPPED:
      --   * G:start_run forces selected_back from args.challenge.deck.type
      --     at game.lua:2037, overriding any selected_back/viewed_back, so
      --     change_to would be a pure no-op.
      --   * The canonical path hardcodes stake = 1 (button_callbacks.lua:1849).
      -- setup_run is also omitted on purpose: G.FUNCS.start_run / G:start_run
      --   read none of the state it mutates (current_setup, run_setup_seed,
      --   setup_seed are UI-button-only at button_callbacks.lua:1826-1842;
      --   viewed_back is short-circuited above; G.SETTINGS.paused is re-set by
      --   start_run itself). Not a regression — traced during design.
      if G.OVERLAY_MENU then
        G.FUNCS.exit_overlay_menu()
      end

      local run_params = { stake = 1, challenge = challenge_entry }
      if args.seed then
        run_params.seed = args.seed
      end

      sendInfoMessage(
        "Starting challenge run: " .. args.challenge .. ", seed=" .. tostring(args.seed or "none"),
        "BB.ENDPOINTS"
      )
      G.FUNCS.start_run(nil, run_params)

      -- Completion predicate is unchanged: challenges alter starting
      -- conditions, not the run flow — still lands in BLIND_SELECT.
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
            sendDebugMessage("start() → BLIND_SELECT (challenge)", "BB.ENDPOINTS")
            send_response(BB_GAMESTATE.get_gamestate())
          end
          return done
        end,
      }))
      return
    end

    -- ========================================================================
    -- Normal branch (deck + stake)
    -- ========================================================================

    -- deck/stake are schema-optional now (challenge is an alternative), so
    -- enforce presence here. The shared validator rejects missing required
    -- fields before execute runs, which is why they had to drop to optional.
    if args.deck == nil then
      send_response({
        message = "Missing required field 'deck'",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end
    if args.stake == nil then
      send_response({
        message = "Missing required field 'stake'",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

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
