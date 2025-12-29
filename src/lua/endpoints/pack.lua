-- src/lua/endpoints/pack.lua

-- ==========================================================================
-- Pack Select Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.PackSelect.Params
---@field card integer? 0-based index of card to select from pack
---@field targets integer[]? 0-based indices of hand cards to target (for consumables requiring targets)
---@field skip boolean? Skip pack selection

-- ==========================================================================
-- Consumable Target Requirements
-- ==========================================================================

-- Cards requiring specific number of highlighted targets
local CONSUMABLE_TARGET_REQUIREMENTS = {
  -- Tarot Cards
  c_magician = { min = 1, max = 2 }, -- Enhance to Lucky
  c_empress = { min = 1, max = 2 }, -- Enhance to Mult
  c_heirophant = { min = 1, max = 2 }, -- Enhance to Bonus
  c_lovers = { min = 1, max = 1 }, -- Enhance to Wild
  c_chariot = { min = 1, max = 1 }, -- Enhance to Steel
  c_justice = { min = 1, max = 1 }, -- Enhance to Glass
  c_strength = { min = 1, max = 2 }, -- Increase rank
  c_hanged_man = { min = 1, max = 2 }, -- Destroy cards
  c_death = { min = 2, max = 2 }, -- Convert left to right
  c_devil = { min = 1, max = 1 }, -- Enhance to Gold
  c_tower = { min = 1, max = 1 }, -- Enhance to Stone
  c_star = { min = 1, max = 3 }, -- Convert to Diamonds
  c_moon = { min = 1, max = 3 }, -- Convert to Clubs
  c_sun = { min = 1, max = 3 }, -- Convert to Hearts
  c_world = { min = 1, max = 3 }, -- Convert to Spades
  -- Spectral Cards
  c_talisman = { min = 1, max = 1 }, -- Add Gold Seal
  c_deja_vu = { min = 1, max = 1 }, -- Add Red Seal
  c_trance = { min = 1, max = 1 }, -- Add Blue Seal
  c_medium = { min = 1, max = 1 }, -- Add Purple Seal
  c_cryptid = { min = 1, max = 1 }, -- Create copies
  c_aura = { min = 1, max = 1 }, -- Add edition
  c_ankh = { requires_joker = true }, -- Copy random joker (requires at least 1 joker)
}

-- ==========================================================================
-- Pack Select Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "pack",

  description = "Select or skip a card from an opened booster pack",

  schema = {
    card = {
      type = "integer",
      required = false,
      description = "0-based index of card to select from pack",
    },
    targets = {
      type = "array",
      items = { type = "integer" },
      required = false,
      description = "0-based indices of hand cards to target (for consumables requiring targets)",
    },
    skip = {
      type = "boolean",
      required = false,
      description = "Skip pack selection",
    },
  },

  requires_state = { G.STATES.SMODS_BOOSTER_OPENED },

  ---@param args Request.Endpoint.PackSelect.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init pack()", "BB.ENDPOINTS")

    -- Validate that exactly one of card or skip is provided
    local set = 0
    if args.card then
      set = set + 1
    end
    if args.skip then
      set = set + 1
    end

    if set == 0 then
      send_response({
        message = "Invalid arguments. You must provide one of: card, skip",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    if set > 1 then
      send_response({
        message = "Invalid arguments. Cannot provide both card and skip",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Validate pack_cards exists
    if not G.pack_cards or G.pack_cards.REMOVED then
      send_response({
        message = "No pack is currently open",
        name = BB_ERROR_NAMES.INVALID_STATE,
      })
      return
    end

    -- Check if this is a Mega pack (allows 2 selections) from metadata stored during purchase
    local gamestate = BB_GAMESTATE.get_gamestate()
    local is_mega_pack = gamestate.pack and gamestate.pack.is_mega or false

    -- Helper function to perform card selection and handle response
    local function select_card()
      local pos = args.card + 1

      -- Validate card index is in range
      if not G.pack_cards.cards[pos] then
        local pack_count = G.pack_cards.config and G.pack_cards.config.card_count or 0
        send_response({
          message = "Card index out of range. Index: " .. args.card .. ", Available cards: " .. pack_count,
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return true
      end

      local card = G.pack_cards.cards[pos]
      local card_key = card.config and card.config.center and card.config.center.key

      -- Check if card is a Joker and validate that we have room
      if card.ability and card.ability.set == "Joker" then
        local joker_count = G.jokers and G.jokers.config and G.jokers.config.card_count or 0
        local joker_limit = G.jokers and G.jokers.config and G.jokers.config.card_limit or 0
        if joker_count >= joker_limit then
          send_response({
            message = "Cannot select joker, joker slots are full. Current: "
              .. joker_count
              .. ", Limit: "
              .. joker_limit,
            name = BB_ERROR_NAMES.NOT_ALLOWED,
          })
          return true
        end
      end

      -- Validate consumable target requirements
      if card_key and CONSUMABLE_TARGET_REQUIREMENTS[card_key] then
        local req = CONSUMABLE_TARGET_REQUIREMENTS[card_key]

        -- Check joker requirement for cards like Ankh
        if req.requires_joker then
          local joker_count = G.jokers and G.jokers.config and G.jokers.config.card_count or 0
          if joker_count == 0 then
            send_response({
              message = string.format("Card '%s' requires at least 1 joker. Current: %d", card_key, joker_count),
              name = BB_ERROR_NAMES.NOT_ALLOWED,
            })
            return true
          end
        end

        -- Check target card requirements
        local target_count = args.targets and #args.targets or 0
        if req.min and req.max and (target_count < req.min or target_count > req.max) then
          local msg
          if req.min == req.max then
            msg = string.format(
              "Card '%s' requires exactly %d target card(s). Provided: %d",
              card_key,
              req.min,
              target_count
            )
          else
            msg = string.format(
              "Card '%s' requires %d-%d target card(s). Provided: %d",
              card_key,
              req.min,
              req.max,
              target_count
            )
          end
          send_response({
            message = msg,
            name = BB_ERROR_NAMES.BAD_REQUEST,
          })
          return true
        end

        -- Highlight the target cards in hand
        if args.targets and #args.targets > 0 then
          -- Clear existing highlights
          for _, hand_card in ipairs(G.hand.cards) do
            hand_card.highlighted = false
          end

          -- Highlight target cards
          for _, target_idx in ipairs(args.targets) do
            local hand_pos = target_idx + 1 -- Convert 0-based to 1-based
            if not G.hand.cards[hand_pos] then
              send_response({
                message = "Target card index out of range. Index: " .. target_idx .. ", Hand size: " .. #G.hand.cards,
                name = BB_ERROR_NAMES.BAD_REQUEST,
              })
              return true
            end
            G.hand.cards[hand_pos].highlighted = true
            G.hand.highlighted[#G.hand.highlighted + 1] = G.hand.cards[hand_pos]
          end
        end
      end

      -- Select the card by calling use_card
      local btn = {
        config = {
          ref_table = card,
        },
      }

      -- Check pack count BEFORE calling use_card (count decreases after)
      local pack_cards_remaining = G.pack_cards and G.pack_cards.config and G.pack_cards.config.card_count or 0

      G.FUNCS.use_card(btn)

      -- Only wait for pack to close if this is not a Mega pack with more selections
      if is_mega_pack and pack_cards_remaining > 4 then
        -- Return for Mega packs with more selections available
        -- But wait a bit for pack to stabilize first so we don't run into crashes
        local delay_frames = 0
        G.E_MANAGER:add_event(Event({
          trigger = "condition",
          blocking = false,
          func = function()
            delay_frames = delay_frames + 1
            if delay_frames >= 30 then -- Wait ~0.5 seconds
              send_response(BB_GAMESTATE.get_gamestate())
              return true
            end
            return false
          end,
        }))
        return true
      end

      -- Wait for pack to close and return to shop
      G.E_MANAGER:add_event(Event({
        trigger = "condition",
        blocking = false,
        func = function()
          local pack_closed = not G.pack_cards or G.pack_cards.REMOVED
          local back_to_shop = G.STATE == G.STATES.SHOP

          if pack_closed and back_to_shop then
            G.GAME.bb_pack_is_mega = nil -- Clear pack metadata
            sendDebugMessage("Return pack() after selection", "BB.ENDPOINTS")
            send_response(BB_GAMESTATE.get_gamestate())
            return true
          end

          return false
        end,
      }))

      return true
    end

    -- Handle skip
    if args.skip then
      G.FUNCS.skip_booster({})

      -- Wait for pack to close and return to shop
      G.E_MANAGER:add_event(Event({
        trigger = "condition",
        blocking = false,
        func = function()
          local pack_closed = not G.pack_cards or G.pack_cards.REMOVED
          local back_to_shop = G.STATE == G.STATES.SHOP

          if pack_closed and back_to_shop then
            G.GAME.bb_pack_is_mega = nil -- Clear pack metadata
            sendDebugMessage("Return pack() after skip", "BB.ENDPOINTS")
            send_response(BB_GAMESTATE.get_gamestate())
            return true
          end

          return false
        end,
      }))
      return
    end

    -- Wait for hand cards to load for Arcana and Spectral packs
    local pack_key = G.pack_cards
      and G.pack_cards.cards
      and G.pack_cards.cards[1]
      and G.pack_cards.cards[1].ability
      and G.pack_cards.cards[1].ability.set
    local needs_hand = pack_key == "Tarot" or pack_key == "Spectral"

    if needs_hand then
      -- Wait for hand cards to be fully loaded and positioned
      local selection_executed = false -- Flag to ensure we only execute once

      G.E_MANAGER:add_event(Event({
        trigger = "condition",
        blocking = false,
        func = function()
          -- Wait for hand to be fully loaded and positioned
          local hand_ready = G.hand
            and not G.hand.REMOVED
            and G.hand.cards
            and #G.hand.cards > 0
            and G.hand.T -- Table area exists
            and G.hand.T.x -- Positioned

          -- Also check that cards are actually positioned in the hand
          local cards_positioned = hand_ready and G.hand.cards[1] and G.hand.cards[1].T and G.hand.cards[1].T.x

          -- Validate that all target card indices exist in hand
          local all_targets_exist = true
          if args.targets and #args.targets > 0 then
            for _, target_idx in ipairs(args.targets) do
              local hand_pos = target_idx + 1 -- Convert 0-based to 1-based
              if not G.hand.cards[hand_pos] then
                all_targets_exist = false
                break
              end
            end
          end

          if hand_ready and cards_positioned and all_targets_exist and not selection_executed then
            selection_executed = true -- Mark as executed to prevent re-running
            return select_card()
          end

          return false
        end,
      }))
      return
    else
      -- Handle card selection for packs that don't need hand (e.g., Buffoon, Celestial, Standard)
      return select_card()
    end
  end,
}
