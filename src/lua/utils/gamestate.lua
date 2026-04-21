---Simplified game state extraction utilities
---This module provides a clean, simplified interface for extracting game state
---according to the new gamestate specification

---@class GameStateModule
---@field on_game_over (fun(state: GameState))?
---@field check_game_over fun()
---@field get_blinds_info fun(): table<string, Blind>
---@field get_gamestate fun(): GameState
local gamestate = {}

-- ==========================================================================
-- State Name Mapping
-- ==========================================================================

---Converts numeric state ID to string state name
---@param state_num number The numeric state value from G.STATE
---@return string state_name The string name of the state (e.g., "SELECTING_HAND")
local function get_state_name(state_num)
  if not G or not G.STATES then
    return "UNKNOWN"
  end

  for name, value in pairs(G.STATES) do
    if value == state_num then
      return name
    end
  end

  return "UNKNOWN"
end

-- ==========================================================================
-- Deck Name Mapping
-- ==========================================================================

local DECK_KEY_TO_NAME = {
  b_red = "RED",
  b_blue = "BLUE",
  b_yellow = "YELLOW",
  b_green = "GREEN",
  b_black = "BLACK",
  b_magic = "MAGIC",
  b_nebula = "NEBULA",
  b_ghost = "GHOST",
  b_abandoned = "ABANDONED",
  b_checkered = "CHECKERED",
  b_zodiac = "ZODIAC",
  b_painted = "PAINTED",
  b_anaglyph = "ANAGLYPH",
  b_plasma = "PLASMA",
  b_erratic = "ERRATIC",
}

---Converts deck key to string deck name
---@param deck_key string The key from G.P_CENTERS (e.g., "b_red")
---@return string? deck_name The string name of the deck (e.g., "RED"), or nil if not found
local function get_deck_name(deck_key)
  return DECK_KEY_TO_NAME[deck_key]
end

-- ==========================================================================
-- Stake Name Mapping
-- ==========================================================================

local STAKE_LEVEL_TO_NAME = {
  [1] = "WHITE",
  [2] = "RED",
  [3] = "GREEN",
  [4] = "BLACK",
  [5] = "BLUE",
  [6] = "PURPLE",
  [7] = "ORANGE",
  [8] = "GOLD",
}

---Converts numeric stake level to string stake name
---@param stake_num number The numeric stake value from G.GAME.stake (1-8)
---@return string? stake_name The string name of the stake (e.g., "WHITE"), or nil if not found
local function get_stake_name(stake_num)
  return STAKE_LEVEL_TO_NAME[stake_num]
end

-- ==========================================================================
-- Card UI Description
-- ==========================================================================

---Recursively removes DynaText and other Moveable objects from UI node tree
---to prevent memory leaks from objects registering in G.I.MOVEABLE
---@param nodes table|nil UI node tree (array or single node)
local function cleanup_ui_nodes(nodes)
  if type(nodes) ~= "table" then
    return
  end

  -- Handle single node with object (DynaText, etc.)
  local config = nodes.config
  if config and config.object then
    local obj = config.object
    if obj and obj.remove then
      obj:remove() -- Removes from G.I.MOVEABLE and other tracking arrays
    end
    config.object = nil
  end

  -- Recurse into children/nodes
  if nodes.nodes then
    cleanup_ui_nodes(nodes.nodes)
  end
  if nodes.children then
    cleanup_ui_nodes(nodes.children)
  end

  -- Traverse arrays and maps to avoid missing nodes with holes
  for key, node in pairs(nodes) do
    if key ~= "nodes" and key ~= "children" and key ~= "config" and type(node) == "table" then
      cleanup_ui_nodes(node)
    end
  end
end

---Gets the description text for a card by reading from its UI elements
---Uses generate_UIBox_ability_table() directly to avoid hover() side effects
---(sound, animation, h_popup creation)
---@param card table The card object
---@return string description The description text from UI
local function get_card_ui_description(card)
  -- Generate UI structure directly (no hover side effects)
  local ui_table = card:generate_UIBox_ability_table()
  if not ui_table then
    return ""
  end

  -- Extract all text nodes from the UI tree
  local texts = {}

  -- The UI table has main/info/type sections
  if ui_table.main then
    for _, line in ipairs(ui_table.main) do
      local line_texts = {}
      for _, section in ipairs(line) do
        if section.config and section.config.text then
          -- normal text and colored text
          line_texts[#line_texts + 1] = section.config.text
        elseif section.nodes then
          for _, node in ipairs(section.nodes) do
            if node.config and node.config.text then
              -- highlighted text
              line_texts[#line_texts + 1] = node.config.text
            end
          end
        end
      end
      texts[#texts + 1] = table.concat(line_texts, "")
    end
  end

  -- Cleanup DynaText and other objects to prevent memory leak
  -- These objects register in G.I.MOVEABLE when created
  cleanup_ui_nodes(ui_table.main)
  cleanup_ui_nodes(ui_table.info)
  if ui_table.name and type(ui_table.name) == "table" then
    cleanup_ui_nodes(ui_table.name)
  end

  -- Join text lines with spaces (in the game these are separated by newlines)
  return table.concat(texts, " ")
end

-- ==========================================================================
-- Card Value Converters
-- ==========================================================================

---Converts Balatro suit name to enum format
---@param suit_name string The suit name from card.config.card.suit
---@return Card.Value.Suit? suit_enum The single-letter suit enum ("H", "D", "C", "S")
local function convert_suit_to_enum(suit_name)
  if suit_name == "Hearts" then
    return "H"
  elseif suit_name == "Diamonds" then
    return "D"
  elseif suit_name == "Clubs" then
    return "C"
  elseif suit_name == "Spades" then
    return "S"
  end
  return nil
end

---Converts Balatro rank value to enum format
---@param rank_value string The rank value from card.config.card.value
---@return Card.Value.Rank? rank_enum The single-character rank enum
local function convert_rank_to_enum(rank_value)
  -- Numbers 2-9 stay the same
  if
    rank_value == "2"
    or rank_value == "3"
    or rank_value == "4"
    or rank_value == "5"
    or rank_value == "6"
    or rank_value == "7"
    or rank_value == "8"
    or rank_value == "9"
  then
    return rank_value
  elseif rank_value == "10" then
    return "T"
  elseif rank_value == "Jack" then
    return "J"
  elseif rank_value == "Queen" then
    return "Q"
  elseif rank_value == "King" then
    return "K"
  elseif rank_value == "Ace" then
    return "A"
  end
  return nil
end

-- ==========================================================================
-- Card Component Extractors
-- ==========================================================================

---Extracts modifier information from a card
---@param card table The card object
---@return Card.Modifier modifier The Card.Modifier object
local function extract_card_modifier(card)
  local modifier = {}

  -- Seal (direct property)
  if card.seal then
    modifier.seal = string.upper(card.seal)
  end

  -- Edition: use the card's own scoring methods for reliable detection.
  -- card:get_chip_mult() returns the holo mult, get_chip_bonus() includes foil chips,
  -- get_chip_x_mult() returns polychrome xmult. These work regardless of how
  -- the edition table is structured internally.
  if card.edition then
    -- Type string for identification
    if card.edition.type then
      modifier.edition = string.upper(card.edition.type)
    elseif card.edition.holo then
      modifier.edition = "HOLO"
    elseif card.edition.foil then
      modifier.edition = "FOIL"
    elseif card.edition.polychrome then
      modifier.edition = "POLYCHROME"
    elseif card.edition.negative then
      modifier.edition = "NEGATIVE"
    elseif card.edition.key then
      -- SMODS: edition.key = "e_holo" / "e_foil" / "e_polychrome" / "e_negative"
      local etype = card.edition.key:gsub("^e_", "")
      modifier.edition = string.upper(etype)
    end

    -- Numeric scoring values
    if card.edition.mult and card.edition.mult ~= 0 then
      modifier.edition_mult = card.edition.mult
    end
    if card.edition.chips and card.edition.chips ~= 0 then
      modifier.edition_chips = card.edition.chips
    end
    -- Use get_edition() for x_mult: the raw card.edition.x_mult can be
    -- contaminated by enhancement values (Glass x2 overwrites Polychrome x1.5).
    -- get_edition() returns the correct edition-only value.
    if card.get_edition then
      local ok, ed = pcall(function() return card:get_edition() end)
      if ok and ed and ed.x_mult_mod and ed.x_mult_mod ~= 0 then
        modifier.edition_x_mult = ed.x_mult_mod
      end
    elseif card.edition.x_mult and card.edition.x_mult ~= 0 then
      modifier.edition_x_mult = card.edition.x_mult
    end
  end
  -- Fallback: use card scoring methods directly (catches editions not in card.edition table)
  -- Skip if the card has a MULT or LUCKY enhancement — get_chip_mult() includes
  -- enhancement mult, which would create a phantom HOLO edition.
  local has_mult_enhancement = card.ability and card.ability.effect
    and (card.ability.effect == "Mult Card" or card.ability.effect == "Lucky Card")
  if not modifier.edition and card.get_chip_mult and not has_mult_enhancement then
    local ok, emult = pcall(function() return card:get_chip_mult() end)
    if ok and emult and emult > 0 then
      modifier.edition = "HOLO"
      modifier.edition_mult = emult
    end
  end
  -- Note: removed get_chip_x_mult() fallback here — it returns the enhancement
  -- x_mult (Glass 2.0), not the edition x_mult (Polychrome 1.5). Edition detection
  -- via get_edition() above is now the primary path.
  if not modifier.edition_chips and card.get_chip_bonus then
    -- get_chip_bonus includes base nominal + ability.bonus + perma_bonus + edition chips
    -- We already handle perma_bonus separately, so only check for foil-level chips
    local ok, echips = pcall(function() return card:get_chip_bonus() end)
    if ok and echips then
      local base_nominal = (card.base and card.base.nominal) or 0
      local ability_bonus = (card.ability and card.ability.bonus) or 0
      local perma = (card.ability and card.ability.perma_bonus) or 0
      local edition_chips = echips - base_nominal - ability_bonus - perma
      if edition_chips > 0 then
        modifier.edition = modifier.edition or "FOIL"
        modifier.edition_chips = edition_chips
      end
    end
  end

  -- Enhancement (from ability.name for enhanced cards)
  if card.ability and card.ability.effect and card.ability.effect ~= "Base" then
    modifier.enhancement = string.upper(card.ability.effect:gsub(" Card", ""))
    -- Expose enhancement x_mult separately (Glass = 2.0)
    if card.ability.x_mult and card.ability.x_mult ~= 1 then
      modifier.enhancement_x_mult = card.ability.x_mult
    end
  end

  -- Eternal (boolean from ability)
  if card.ability and card.ability.eternal then
    modifier.eternal = true
  end

  -- Perishable (from perish_tally - only include if > 0)
  if card.ability and card.ability.perish_tally and card.ability.perish_tally > 0 then
    modifier.perishable = card.ability.perish_tally
  end

  -- Rental (boolean from ability)
  if card.ability and card.ability.rental then
    modifier.rental = true
  end

  return modifier
end

---Extracts value information from a card
---@param card table The card object
---@return Card.Value value The Card.Value object
local function extract_card_value(card)
  local value = {}

  -- Suit and rank (for playing cards)
  if card.config and card.config.card then
    if card.config.card.suit then
      value.suit = convert_suit_to_enum(card.config.card.suit)
    end
    if card.config.card.value then
      value.rank = convert_rank_to_enum(card.config.card.value)
    end
  end

  -- Effect description (for all cards)
  value.effect = get_card_ui_description(card)

  -- Permanent chip bonus (from Hiker etc.) — only for playing cards
  if card.ability then
    if card.ability.perma_bonus and card.ability.perma_bonus ~= 0 then
      value.perma_bonus = card.ability.perma_bonus
    end
  end

  -- Joker rarity (1=Common, 2=Uncommon, 3=Rare, 4=Legendary)
  if card.config and card.config.center and card.config.center.rarity then
    value.rarity = card.config.center.rarity
  end

  -- Joker ability data: expose actual scoring values instead of requiring
  -- text parsing. Includes accumulated values for scaling jokers.
  if card.ability then
    local ab = {}
    -- extra: varies by joker — can be number or table with chips/mult/Xmult/etc.
    if card.ability.extra ~= nil then
      if type(card.ability.extra) == "table" then
        -- Shallow copy the table
        for k, v in pairs(card.ability.extra) do
          if type(v) ~= "table" and type(v) ~= "function" then
            ab[k] = v
          end
        end
      else
        ab.extra = card.ability.extra
      end
    end
    -- Config-level scoring fields (hand-type jokers like Jolly, Sly, etc.)
    if card.ability.t_mult and card.ability.t_mult ~= 0 then ab.t_mult = card.ability.t_mult end
    if card.ability.t_chips and card.ability.t_chips ~= 0 then ab.t_chips = card.ability.t_chips end
    if card.ability.mult and card.ability.mult ~= 0 then ab.mult = card.ability.mult end
    if card.ability.x_mult and card.ability.x_mult ~= 0 then ab.x_mult = card.ability.x_mult end
    -- Driver's License enhanced card count
    if card.ability.driver_tally then ab.driver_tally = card.ability.driver_tally end
    -- Loyalty Card: remaining hands until trigger
    if card.ability.loyalty_remaining ~= nil then ab.loyalty_remaining = card.ability.loyalty_remaining end
    -- Only include if non-empty
    if next(ab) ~= nil then
      value.ability = ab
    end
  end

  return value
end

---Extracts state information from a card
---@param card table The card object
---@return Card.State state The Card.State object
local function extract_card_state(card)
  local state = {}

  -- Debuff
  if card.debuff then
    state.debuff = true
  end

  -- Hidden (facing == "back")
  if card.facing and card.facing == "back" then
    state.hidden = true
  end

  -- Highlighted
  if card.highlighted then
    state.highlight = true
  end

  return state
end

---Extracts cost information from a card
---@param card table The card object
---@return Card.Cost cost The Card.Cost object
local function extract_card_cost(card)
  return {
    sell = card.sell_cost or 0,
    buy = card.cost or 0,
  }
end

-- ==========================================================================
-- Card Extractor
-- ==========================================================================

---Extracts a complete Card object from a game card
---@param card table The game card object
---@return Card card The Card object
local function extract_card(card)
  -- Determine set
  local set = "DEFAULT"
  if card.ability and card.ability.set then
    local ability_set = card.ability.set
    if ability_set == "Joker" then
      set = "JOKER"
    elseif ability_set == "Tarot" then
      set = "TAROT"
    elseif ability_set == "Planet" then
      set = "PLANET"
    elseif ability_set == "Spectral" then
      set = "SPECTRAL"
    elseif ability_set == "Voucher" then
      set = "VOUCHER"
    elseif ability_set == "Booster" then
      set = "BOOSTER"
    elseif ability_set == "Edition" then
      set = "EDITION"
    elseif card.ability.effect and card.ability.effect ~= "Base" then
      set = "ENHANCED"
    end
  end

  -- Extract key (prefer card_key for playing cards, fallback to center_key)
  local key = ""
  if card.config then
    if card.config.card_key then
      key = card.config.card_key
    elseif card.config.center_key then
      key = card.config.center_key
    end
  end

  return {
    id = card.sort_id or 0,
    key = key,
    set = set,
    label = card.label or "",
    value = extract_card_value(card),
    modifier = extract_card_modifier(card),
    state = extract_card_state(card),
    cost = extract_card_cost(card),
  }
end

-- ==========================================================================
-- Area Extractor
-- ==========================================================================

---Extracts an Area object from a game area (like G.jokers, G.hand, etc.)
---@param area table The game area object
---@return Area? area_data The Area object
local function extract_area(area)
  if not area then
    return nil
  end

  local cards = {}
  if area.cards then
    for i, card in pairs(area.cards) do
      cards[i] = extract_card(card)
    end
  end

  local area_data = {
    count = (area.config and area.config.card_count) or 0,
    limit = (area.config and area.config.card_limit) or 0,
    cards = cards,
  }

  -- Add highlighted_limit if available (for hand area)
  if area.config and area.config.highlighted_limit then
    area_data.highlighted_limit = area.config.highlighted_limit
  end

  return area_data
end

-- ==========================================================================
-- Poker Hands Extractor
-- ==========================================================================

---Extracts poker hands information
---@param hands table The G.GAME.hands table
---@return table<string, Hand> hands_data The hands information
local function extract_hand_info(hands)
  if not hands then
    return {}
  end

  local hands_data = {}
  for name, hand in pairs(hands) do
    hands_data[name] = {
      order = hand.order or 0,
      level = hand.level or 1,
      chips = hand.chips or 0,
      mult = hand.mult or 0,
      played = hand.played or 0,
      played_this_round = hand.played_this_round or 0,
      example = hand.example or {},
    }
  end

  return hands_data
end

-- ==========================================================================
-- Round Info Extractor
-- ==========================================================================

---Extracts round state information
---@return Round round The Round object
local function extract_round_info()
  if not G or not G.GAME or not G.GAME.current_round then
    return {}
  end

  local round = {}

  if G.GAME.current_round.hands_left then
    round.hands_left = G.GAME.current_round.hands_left
  end

  if G.GAME.current_round.hands_played then
    round.hands_played = G.GAME.current_round.hands_played
  end

  if G.GAME.current_round.discards_left then
    round.discards_left = G.GAME.current_round.discards_left
  end

  if G.GAME.current_round.discards_used then
    round.discards_used = G.GAME.current_round.discards_used
  end

  if G.GAME.current_round.reroll_cost then
    round.reroll_cost = G.GAME.current_round.reroll_cost
  end

  -- Chips is stored in G.GAME not G.GAME.current_round
  if G.GAME.chips then
    round.chips = G.GAME.chips
  end

  -- The Ox: which hand type triggers money loss
  if G.GAME.current_round.most_played_poker_hand then
    round.most_played_poker_hand = G.GAME.current_round.most_played_poker_hand
  end

  -- Ancient Joker's current rotating suit
  if G.GAME.current_round.ancient_card and G.GAME.current_round.ancient_card.suit then
    local suit = G.GAME.current_round.ancient_card.suit
    local suit_map = {Spades = "S", Hearts = "H", Clubs = "C", Diamonds = "D"}
    round.ancient_suit = suit_map[suit] or suit
  end

  -- The Idol: target rank+suit that grants X2 Mult, rerolled each round
  if G.GAME.current_round.idol_card
    and G.GAME.current_round.idol_card.rank
    and G.GAME.current_round.idol_card.suit
  then
    local suit_map = { Spades = "S", Hearts = "H", Clubs = "C", Diamonds = "D" }
    round.idol_card = {
      rank = convert_rank_to_enum(G.GAME.current_round.idol_card.rank) or G.GAME.current_round.idol_card.rank,
      suit = suit_map[G.GAME.current_round.idol_card.suit] or G.GAME.current_round.idol_card.suit,
    }
  end

  return round
end

-- ==========================================================================
-- Blind Information
-- ==========================================================================

---Gets blind effect description from localization data
---@param blind_config table The blind configuration from G.P_BLINDS
---@return string effect The effect description
local function get_blind_effect_from_ui(blind_config)
  if not blind_config or not blind_config.key then
    return ""
  end

  -- Small and Big blinds have no effect
  if blind_config.key == "bl_small" or blind_config.key == "bl_big" then
    return ""
  end

  -- Access localization data directly (more reliable than using localize function)
  -- Path: G.localization.descriptions.Blind[blind_key].text
  if not G or not G.localization then ---@diagnostic disable-line: undefined-global
    return ""
  end

  local loc_data = G.localization.descriptions ---@diagnostic disable-line: undefined-global
  if not loc_data or not loc_data.Blind or not loc_data.Blind[blind_config.key] then
    return ""
  end

  local blind_data = loc_data.Blind[blind_config.key]
  if not blind_data.text or type(blind_data.text) ~= "table" then
    return ""
  end

  -- Concatenate all description lines
  local effect_parts = {}
  for _, line in ipairs(blind_data.text) do
    if line and line ~= "" then
      effect_parts[#effect_parts + 1] = line
    end
  end

  return table.concat(effect_parts, " ")
end

---Gets tag information using localize function (same approach as Tag:set_text)
---@param tag_key string The tag key from G.P_TAGS
---@return table tag_info {name: string, effect: string}
local function get_tag_info(tag_key)
  local result = { name = "", effect = "" }

  if not tag_key or not G.P_TAGS or not G.P_TAGS[tag_key] then
    return result
  end

  if not localize then ---@diagnostic disable-line: undefined-global
    return result
  end

  local tag_data = G.P_TAGS[tag_key]
  result.name = tag_data.name or ""

  -- Build loc_vars based on tag name (same logic as Tag:get_uibox_table in tag.lua:545-561)
  local loc_vars = {}
  local name = tag_data.name
  if name == "Investment Tag" then
    loc_vars = { tag_data.config and tag_data.config.dollars or 0 }
  elseif name == "Handy Tag" then
    local dollars_per_hand = tag_data.config and tag_data.config.dollars_per_hand or 0
    local hands_played = (G.GAME and G.GAME.hands_played) or 0
    loc_vars = { dollars_per_hand, dollars_per_hand * hands_played }
  elseif name == "Garbage Tag" then
    local dollars_per_discard = tag_data.config and tag_data.config.dollars_per_discard or 0
    local unused_discards = (G.GAME and G.GAME.unused_discards) or 0
    loc_vars = { dollars_per_discard, dollars_per_discard * unused_discards }
  elseif name == "Juggle Tag" then
    loc_vars = { tag_data.config and tag_data.config.h_size or 0 }
  elseif name == "Top-up Tag" then
    loc_vars = { tag_data.config and tag_data.config.spawn_jokers or 0 }
  elseif name == "Skip Tag" then
    local skip_bonus = tag_data.config and tag_data.config.skip_bonus or 0
    local skips = (G.GAME and G.GAME.skips) or 0
    loc_vars = { skip_bonus, skip_bonus * (skips + 1) }
  elseif name == "Orbital Tag" then
    local orbital_hand = "Poker Hand" -- Default placeholder
    local levels = tag_data.config and tag_data.config.levels or 0
    loc_vars = { orbital_hand, levels }
  elseif name == "Economy Tag" then
    loc_vars = { tag_data.config and tag_data.config.max or 0 }
  end

  -- Use localize with raw_descriptions type (matches Balatro's internal approach)
  local text_lines = localize({ type = "raw_descriptions", key = tag_key, set = "Tag", vars = loc_vars }) ---@diagnostic disable-line: undefined-global
  if text_lines and type(text_lines) == "table" then
    result.effect = table.concat(text_lines, " ")
  end

  return result
end

---Converts game blind status to uppercase enum
---@param status string Game status (e.g., "Defeated", "Current", "Select")
---@return string uppercase_status Uppercase status enum (e.g., "DEFEATED", "CURRENT", "SELECT")
local function convert_status_to_enum(status)
  if status == "Defeated" then
    return "DEFEATED"
  elseif status == "Skipped" then
    return "SKIPPED"
  elseif status == "Current" then
    return "CURRENT"
  elseif status == "Select" then
    return "SELECT"
  elseif status == "Upcoming" then
    return "UPCOMING"
  else
    return "UPCOMING" -- Default fallback
  end
end

---Gets comprehensive blind information for the current ante
---@return table<string, Blind> blinds Information about small, big, and boss blinds
function gamestate.get_blinds_info()
  -- Initialize with default structure matching the Blind type
  local blinds = {
    small = {
      type = "SMALL",
      status = "UPCOMING",
      name = "",
      effect = "",
      score = 0,
      tag_name = "",
      tag_effect = "",
    },
    big = {
      type = "BIG",
      status = "UPCOMING",
      name = "",
      effect = "",
      score = 0,
      tag_name = "",
      tag_effect = "",
    },
    boss = {
      type = "BOSS",
      status = "UPCOMING",
      name = "",
      effect = "",
      score = 0,
      tag_name = "",
      tag_effect = "",
    },
  }

  if not G.GAME or not G.GAME.round_resets then
    return blinds
  end

  -- Get base blind amount for current ante
  local ante = G.GAME.round_resets.ante or 1
  local base_amount = get_blind_amount(ante) ---@diagnostic disable-line: undefined-global

  -- Apply ante scaling with null check
  local ante_scaling = (G.GAME.starting_params and G.GAME.starting_params.ante_scaling) or 1

  -- Get blind choices
  local blind_choices = G.GAME.round_resets.blind_choices or {}
  local blind_states = G.GAME.round_resets.blind_states or {}

  -- ====================
  -- Small Blind
  -- ====================
  local small_choice = blind_choices.Small or "bl_small"
  if G.P_BLINDS and G.P_BLINDS[small_choice] then
    local small_blind = G.P_BLINDS[small_choice]
    blinds.small.name = small_blind.name or "Small Blind"
    blinds.small.score = math.floor(base_amount * (small_blind.mult or 1) * ante_scaling)
    blinds.small.effect = get_blind_effect_from_ui(small_blind)

    -- Set status
    if blind_states.Small then
      blinds.small.status = convert_status_to_enum(blind_states.Small)
    end

    -- Get tag information
    local small_tag_key = G.GAME.round_resets.blind_tags and G.GAME.round_resets.blind_tags.Small
    if small_tag_key then
      local tag_info = get_tag_info(small_tag_key)
      blinds.small.tag_name = tag_info.name
      blinds.small.tag_effect = tag_info.effect
    end
  end

  -- ====================
  -- Big Blind
  -- ====================
  local big_choice = blind_choices.Big or "bl_big"
  if G.P_BLINDS and G.P_BLINDS[big_choice] then
    local big_blind = G.P_BLINDS[big_choice]
    blinds.big.name = big_blind.name or "Big Blind"
    blinds.big.score = math.floor(base_amount * (big_blind.mult or 1.5) * ante_scaling)
    blinds.big.effect = get_blind_effect_from_ui(big_blind)

    -- Set status
    if blind_states.Big then
      blinds.big.status = convert_status_to_enum(blind_states.Big)
    end

    -- Get tag information
    local big_tag_key = G.GAME.round_resets.blind_tags and G.GAME.round_resets.blind_tags.Big
    if big_tag_key then
      local tag_info = get_tag_info(big_tag_key)
      blinds.big.tag_name = tag_info.name
      blinds.big.tag_effect = tag_info.effect
    end
  end

  -- ====================
  -- Boss Blind
  -- ====================
  local boss_choice = blind_choices.Boss
  if boss_choice and G.P_BLINDS and G.P_BLINDS[boss_choice] then
    local boss_blind = G.P_BLINDS[boss_choice]
    blinds.boss.name = boss_blind.name or "Boss Blind"
    blinds.boss.score = math.floor(base_amount * (boss_blind.mult or 2) * ante_scaling)
    blinds.boss.effect = get_blind_effect_from_ui(boss_blind)

    -- Set status
    if blind_states.Boss then
      blinds.boss.status = convert_status_to_enum(blind_states.Boss)
    end
  else
    -- Fallback if boss blind not yet determined
    blinds.boss.name = "Boss Blind"
    blinds.boss.score = math.floor(base_amount * 2 * ante_scaling)
  end

  -- Boss blind has no tags (tag_name and tag_effect remain empty strings)

  return blinds
end

-- ==========================================================================
-- Main Gamestate Extractor
-- ==========================================================================

---Extracts the simplified game state according to the new specification
---@return GameState gamestate The complete simplified game state
function gamestate.get_gamestate()
  if not G then
    return {
      state = "UNKNOWN",
      round_num = 0,
      ante_num = 0,
      money = 0,
    }
  end

  local state_data = {
    state = get_state_name(G.STATE),
  }

  -- Basic game info
  if G.GAME then
    state_data.round_num = G.GAME.round or 0
    state_data.ante_num = (G.GAME.round_resets and G.GAME.round_resets.ante) or 0
    state_data.money = G.GAME.dollars or 0
    state_data.won = G.GAME.won

    -- Deck (optional)
    if G.GAME.selected_back and G.GAME.selected_back.effect and G.GAME.selected_back.effect.center then
      local deck_key = G.GAME.selected_back.effect.center.key
      state_data.deck = get_deck_name(deck_key)
    end

    -- Stake (optional)
    if G.GAME.stake then
      state_data.stake = get_stake_name(G.GAME.stake)
    end

    -- Seed (optional)
    if G.GAME.pseudorandom and G.GAME.pseudorandom.seed then
      state_data.seed = G.GAME.pseudorandom.seed
    end

    -- Used vouchers (table<string, string>)
    if G.GAME.used_vouchers then
      local used_vouchers = {}
      for voucher_name, voucher_data in pairs(G.GAME.used_vouchers) do
        if type(voucher_data) == "table" and voucher_data.description then
          used_vouchers[voucher_name] = voucher_data.description
        else
          used_vouchers[voucher_name] = ""
        end
      end
      state_data.used_vouchers = used_vouchers
    end

    -- Poker hands
    if G.GAME.hands then
      state_data.hands = extract_hand_info(G.GAME.hands)
    end

    -- Round info
    state_data.round = extract_round_info()

    -- Blinds info
    state_data.blinds = gamestate.get_blinds_info()

    -- JackPotts earnings tracker (per-game money attribution)
    if G.GAME.jackpotts_earnings and G.GAME.jackpotts_earnings.entries then
      state_data.earnings = G.GAME.jackpotts_earnings.entries
    end

    -- Currently held tags (Investment, Handy, Top-up, Speed, Garbage, etc.).
    -- Each entry: {key, name, ante (acquired)}.
    if G.GAME.tags and #G.GAME.tags > 0 then
      local tags_out = {}
      for _, tag in ipairs(G.GAME.tags) do
        local t_key = tag.key or ""
        local t_info = (G.P_TAGS and G.P_TAGS[t_key]) or {}
        table.insert(tags_out, {
          key = t_key,
          name = t_info.name or t_key,
          ante = tag.ante,
        })
      end
      state_data.tags = tags_out
    end
  end

  -- Always available areas
  state_data.jokers = extract_area(G.jokers)
  state_data.consumables = extract_area(G.consumeables) -- Note: typo in game code

  -- Cards remaining in deck
  if G.deck then
    state_data.cards = extract_area(G.deck)
  end

  -- Hand (count is 0 during not playing phase)
  if G.hand then
    state_data.hand = extract_area(G.hand)
  end

  -- Shop areas (available during shop phase)
  if G.shop_jokers then
    state_data.shop = extract_area(G.shop_jokers)
  end

  if G.shop_vouchers then
    state_data.vouchers = extract_area(G.shop_vouchers)
  end

  if G.shop_booster then
    state_data.packs = extract_area(G.shop_booster)
  end

  -- Pack cards area (available during pack opening phases)
  if G.pack_cards and not G.pack_cards.REMOVED then
    state_data.pack = extract_area(G.pack_cards)
  end

  return state_data
end

-- ==========================================================================
-- GAME_OVER Callback Support
-- ==========================================================================

-- Callback set by endpoints that need immediate GAME_OVER notification
-- This is necessary because when G.STATE becomes GAME_OVER, the game pauses
-- (G.SETTINGS.paused = true) which stops event processing, preventing
-- normal event-based detection from working.
gamestate.on_game_over = nil

-- Tracks whether we've already dismissed the win overlay for endless mode.
-- The dismissal happens in love.update (check_win_overlay) because the
-- overlay sets G.SETTINGS.paused=true which blocks event processing.
-- Two-phase: dismiss first, then confirm removal on a later frame so the
-- game has time to fully process the overlay removal before the bot resumes.
gamestate.win_overlay_dismissed = false
gamestate.win_overlay_dismissing = false

---Check and trigger GAME_OVER callback if state is GAME_OVER
---Called from love.update before game logic runs
function gamestate.check_game_over()
  if gamestate.on_game_over and G.STATE == G.STATES.GAME_OVER then
    gamestate.on_game_over(gamestate.get_gamestate())
    gamestate.on_game_over = nil
  end
end

---Auto-dismiss the "YOU WIN" overlay to continue into endless mode.
---Called from love.update so it works even when the game is paused.
---Two-phase: dismiss first, then confirm removal on a later frame so the
---game has time to fully process the overlay removal before the bot resumes.
function gamestate.check_win_overlay()
  if gamestate.win_overlay_dismissed then return end
  if not G.GAME or not G.GAME.won then return end

  -- Phase 2: overlay was dismissed on a previous frame, confirm it's gone
  if gamestate.win_overlay_dismissing then
    if not G.OVERLAY_MENU then
      sendDebugMessage("check_win_overlay() - overlay confirmed gone, resuming", "BB.GAMESTATE")
      gamestate.win_overlay_dismissed = true
    end
    return
  end

  -- Phase 1: overlay is visible, dismiss it now
  if not G.OVERLAY_MENU then return end  -- not visible yet
  sendDebugMessage("check_win_overlay() - dismissing win overlay for endless mode", "BB.GAMESTATE")
  G.FUNCS.exit_overlay_menu()
  gamestate.on_game_over = nil  -- prevent GAME_OVER callback from firing
  gamestate.win_overlay_dismissing = true
end

return gamestate
