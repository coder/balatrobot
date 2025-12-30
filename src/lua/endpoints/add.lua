-- src/lua/endpoints/add.lua

-- ==========================================================================
-- Add Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Add.Params
---@field key Card.Key The card key to add (j_* for jokers, c_* for consumables, v_* for vouchers, SUIT_RANK for playing cards)
---@field seal Card.Modifier.Seal? The card seal to apply (only for playing cards)
---@field edition Card.Modifier.Edition? The card edition to apply (jokers, playing cards and NEGATIVE consumables)
---@field enhancement Card.Modifier.Enhancement? The card enhancement to apply (playing cards)
---@field eternal boolean? If true, the card will be eternal (jokers only)
---@field perishable integer? The card will be perishable for this many rounds (jokers only, must be >= 1)
---@field rental boolean? If true, the card will be rental (jokers only)

-- ==========================================================================
-- Add Endpoint Utils
-- ==========================================================================

-- Suit conversion table for playing cards
local SUIT_MAP = {
  H = "Hearts",
  D = "Diamonds",
  C = "Clubs",
  S = "Spades",
}

-- Rank conversion table for playing cards
local RANK_MAP = {
  ["2"] = "2",
  ["3"] = "3",
  ["4"] = "4",
  ["5"] = "5",
  ["6"] = "6",
  ["7"] = "7",
  ["8"] = "8",
  ["9"] = "9",
  T = "10",
  J = "Jack",
  Q = "Queen",
  K = "King",
  A = "Ace",
}

-- Seal conversion table
local SEAL_MAP = {
  RED = "Red",
  BLUE = "Blue",
  GOLD = "Gold",
  PURPLE = "Purple",
}

-- Edition conversion table
local EDITION_MAP = {
  HOLO = "e_holo",
  FOIL = "e_foil",
  POLYCHROME = "e_polychrome",
  NEGATIVE = "e_negative",
}

-- Enhancement conversion table
local ENHANCEMENT_MAP = {
  BONUS = "m_bonus",
  MULT = "m_mult",
  WILD = "m_wild",
  GLASS = "m_glass",
  STEEL = "m_steel",
  STONE = "m_stone",
  GOLD = "m_gold",
  LUCKY = "m_lucky",
}

---Detect card type based on key prefix or pattern
---@param key string The card key
---@return string|nil card_type The detected card type or nil if invalid
local function detect_card_type(key)
  local prefix = key:sub(1, 2)

  if prefix == "j_" then
    return "joker"
  elseif prefix == "c_" then
    return "consumable"
  elseif prefix == "v_" then
    return "voucher"
  elseif prefix == "p_" then
    return "pack"
  else
    -- Check if it's a playing card format (SUIT_RANK like H_A)
    if key:match("^[HDCS]_[2-9TJQKA]$") then
      return "playing_card"
    else
      return nil
    end
  end
end

---Parse playing card key into rank and suit
---@param key string The playing card key (e.g., "H_A")
---@return string|nil rank The rank (e.g., "Ace", "10")
---@return string|nil suit The suit (e.g., "Hearts", "Spades")
local function parse_playing_card_key(key)
  local suit_char = key:sub(1, 1)
  local rank_char = key:sub(3, 3)

  local suit = SUIT_MAP[suit_char]
  local rank = RANK_MAP[rank_char]

  if not suit or not rank then
    return nil, nil
  end

  return rank, suit
end

-- ==========================================================================
-- Add Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "add",

  description = "Add a new card to the game (joker, consumable, voucher, or playing card)",

  schema = {
    key = {
      type = "string",
      required = true,
      description = "Card key (j_* for jokers, c_* for consumables, v_* for vouchers, SUIT_RANK for playing cards like H_A)",
    },
    seal = {
      type = "string",
      required = false,
      description = "Seal type (RED, BLUE, GOLD, PURPLE) - only valid for playing cards",
    },
    edition = {
      type = "string",
      required = false,
      description = "Edition type (HOLO, FOIL, POLYCHROME, NEGATIVE) - valid for jokers, playing cards, and consumables (consumables: NEGATIVE only)",
    },
    enhancement = {
      type = "string",
      required = false,
      description = "Enhancement type (BONUS, MULT, WILD, GLASS, STEEL, STONE, GOLD, LUCKY) - only valid for playing cards",
    },
    eternal = {
      type = "boolean",
      required = false,
      description = "If true, the card will be eternal (cannot be sold or destroyed) - only valid for jokers",
    },
    perishable = {
      type = "integer",
      required = false,
      description = "Number of rounds before card perishes (must be positive integer >= 1) - only valid for jokers",
    },
    rental = {
      type = "boolean",
      required = false,
      description = "If true, the card will be rental (costs $1 per round) - only valid for jokers",
    },
  },

  requires_state = { G.STATES.SELECTING_HAND, G.STATES.SHOP, G.STATES.ROUND_EVAL },

  ---@param args Request.Endpoint.Add.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init add()", "BB.ENDPOINTS")

    -- Detect card type
    local card_type = detect_card_type(args.key)

    if not card_type then
      send_response({
        message = "Invalid card key format. Expected: joker (j_*), consumable (c_*), voucher (v_*), or playing card (SUIT_RANK)",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Special validation for playing cards - can only be added in SELECTING_HAND state
    if card_type == "playing_card" and G.STATE ~= G.STATES.SELECTING_HAND then
      send_response({
        message = "Playing cards can only be added in SELECTING_HAND state",
        name = BB_ERROR_NAMES.INVALID_STATE,
      })
      return
    end

    -- Special validation for vouchers - can only be added in SHOP state
    if card_type == "voucher" and G.STATE ~= G.STATES.SHOP then
      send_response({
        message = "Vouchers can only be added in SHOP state",
        name = BB_ERROR_NAMES.INVALID_STATE,
      })
      return
    end

    -- Special validation for packs - can only be added in SHOP state
    if card_type == "pack" and G.STATE ~= G.STATES.SHOP then
      send_response({
        message = "Packs can only be added in SHOP state",
        name = BB_ERROR_NAMES.INVALID_STATE,
      })
      return
    end

    -- Special validation for packs - check shop booster area capacity
    if card_type == "pack" then
      if not G.shop_booster or not G.shop_booster.config then
        send_response({
          message = "Shop booster area not available",
          name = BB_ERROR_NAMES.INVALID_STATE,
        })
        return
      end

      local current_count = G.shop_booster.config.card_count or 0
      local card_limit = G.shop_booster.config.card_limit or 0

      if current_count >= card_limit then
        send_response({
          message = "Cannot add pack, shop booster slots are full",
          name = BB_ERROR_NAMES.NOT_ALLOWED,
        })
        return
      end
    end

    -- Special validation for packs - validate pack key exists
    if card_type == "pack" then
      if not G.P_CENTERS[args.key] then
        send_response({
          message = "Pack key not found: " .. args.key,
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
    end

    -- Validate seal parameter is only for playing cards
    if args.seal and card_type ~= "playing_card" then
      send_response({
        message = "Seal can only be applied to playing cards",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Validate and convert seal value
    local seal_value = nil
    if args.seal then
      seal_value = SEAL_MAP[args.seal]
      if not seal_value then
        send_response({
          message = "Invalid seal value. Expected: RED, BLUE, GOLD, or PURPLE",
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
    end

    -- Validate edition parameter is only for jokers, playing cards, or consumables
    if args.edition and (card_type == "voucher" or card_type == "pack") then
      send_response({
        message = "Edition cannot be applied to " .. card_type .. "s",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Special validation: consumables can only have NEGATIVE edition
    if args.edition and card_type == "consumable" and args.edition ~= "NEGATIVE" then
      send_response({
        message = "Consumables can only have NEGATIVE edition",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Validate and convert edition value
    local edition_value = nil
    if args.edition then
      edition_value = EDITION_MAP[args.edition]
      if not edition_value then
        send_response({
          message = "Invalid edition value. Expected: HOLO, FOIL, POLYCHROME, or NEGATIVE",
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
    end

    -- Validate enhancement parameter is only for playing cards
    if args.enhancement and card_type ~= "playing_card" then
      send_response({
        message = "Enhancement can only be applied to playing cards",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Validate and convert enhancement value
    local enhancement_value = nil
    if args.enhancement then
      enhancement_value = ENHANCEMENT_MAP[args.enhancement]
      if not enhancement_value then
        send_response({
          message = "Invalid enhancement value. Expected: BONUS, MULT, WILD, GLASS, STEEL, STONE, GOLD, or LUCKY",
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
    end

    -- Validate eternal parameter is only for jokers
    if args.eternal and card_type ~= "joker" then
      send_response({
        message = "Eternal can only be applied to jokers",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Validate perishable parameter is only for jokers
    if args.perishable and card_type ~= "joker" then
      send_response({
        message = "Perishable can only be applied to jokers",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Validate perishable value is a positive integer
    if args.perishable then
      if type(args.perishable) ~= "number" or args.perishable ~= math.floor(args.perishable) or args.perishable < 1 then
        send_response({
          message = "Perishable must be a positive integer (>= 1)",
          name = BB_ERROR_NAMES.BAD_REQUEST,
        })
        return
      end
    end

    -- Validate rental parameter is only for jokers
    if args.rental and card_type ~= "joker" then
      send_response({
        message = "Rental can only be applied to jokers",
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Build SMODS.add_card parameters based on card type
    local params

    if card_type == "playing_card" then
      -- Parse the playing card key
      local rank, suit = parse_playing_card_key(args.key)
      params = {
        rank = rank,
        suit = suit,
        skip_materialize = true,
      }

      -- Add seal if provided
      if seal_value then
        params.seal = seal_value
      end

      -- Add edition if provided
      if edition_value then
        params.edition = edition_value
      end

      -- Add enhancement if provided
      if enhancement_value then
        params.enhancement = enhancement_value
      end
    elseif card_type == "voucher" then
      params = {
        key = args.key,
        area = G.shop_vouchers,
        skip_materialize = true,
      }
    else
      -- For jokers and consumables - just pass the key
      params = {
        key = args.key,
        skip_materialize = true,
        stickers = {},
        force_stickers = true,
      }

      -- Add edition if provided
      if edition_value then
        params.edition = edition_value
      end

      -- Add eternal if provided (jokers only - validation already done)
      if args.eternal then
        params.stickers[#params.stickers + 1] = "eternal"
      end

      -- Add perishable if provided (jokers only - validation already done)
      if args.perishable then
        params.stickers[#params.stickers + 1] = "perishable"
      end

      -- Add rental if provided (jokers only - validation already done)
      if args.rental then
        params.stickers[#params.stickers + 1] = "rental"
      end
    end

    -- Track initial state for verification
    local initial_joker_count = G.jokers and G.jokers.config and G.jokers.config.card_count or 0
    local initial_consumable_count = G.consumeables and G.consumeables.config and G.consumeables.config.card_count or 0
    local initial_voucher_count = G.shop_vouchers and G.shop_vouchers.config and G.shop_vouchers.config.card_count or 0
    local initial_hand_count = G.hand and G.hand.config and G.hand.config.card_count or 0
    local initial_pack_count = G.shop_booster and G.shop_booster.config and G.shop_booster.config.card_count or 0

    sendDebugMessage("Initial voucher count: " .. initial_voucher_count, "BB.ENDPOINTS")

    -- Call SMODS function with error handling
    local success, result

    if card_type == "pack" then
      -- Packs use dedicated SMODS function
      success, result = pcall(SMODS.add_booster_to_shop, args.key)
    else
      -- Other cards use SMODS.add_card
      success, result = pcall(SMODS.add_card, params)
    end

    if not success then
      send_response({
        message = "Failed to add card: " .. args.key,
        name = BB_ERROR_NAMES.BAD_REQUEST,
      })
      return
    end

    -- Set custom perish_tally if perishable was provided
    if args.perishable and result and result.ability then
      result.ability.perish_tally = args.perishable
    end

    sendDebugMessage("SMODS.add_card called for: " .. args.key .. " (" .. card_type .. ")", "BB.ENDPOINTS")

    -- Wait for card addition to complete with event-based verification
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      func = function()
        -- Verify card was added based on card type
        local added = false

        if card_type == "joker" then
          added = G.jokers and G.jokers.config and G.jokers.config.card_count == initial_joker_count + 1
        elseif card_type == "consumable" then
          added = G.consumeables
            and G.consumeables.config
            and G.consumeables.config.card_count == initial_consumable_count + 1
        elseif card_type == "voucher" then
          added = G.shop_vouchers
            and G.shop_vouchers.config
            and G.shop_vouchers.config.card_count == initial_voucher_count + 1
        elseif card_type == "pack" then
          added = G.shop_booster
            and G.shop_booster.config
            and G.shop_booster.config.card_count == initial_pack_count + 1
        elseif card_type == "playing_card" then
          added = G.hand and G.hand.config and G.hand.config.card_count == initial_hand_count + 1
        end

        -- Check state stability
        local state_stable = G.STATE_COMPLETE == true and not G.CONTROLLER.locked

        -- Check valid state (still in one of the allowed states)
        local valid_state = (
          G.STATE == G.STATES.SHOP
          or G.STATE == G.STATES.SELECTING_HAND
          or G.STATE == G.STATES.ROUND_EVAL
        )

        -- All conditions must be met
        if added and state_stable and valid_state then
          sendDebugMessage("Card added successfully: " .. args.key, "BB.ENDPOINTS")
          send_response(BB_GAMESTATE.get_gamestate())
          return true
        end

        return false
      end,
    }))
  end,
}
