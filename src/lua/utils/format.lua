--[[
  Format utilities for BalatroBot
  Provides helpers for serializing values, params, and cards
]]

---@class BB_FORMAT
local BB_FORMAT = {}

--- Serialize a value for logging (handles tables, strings, etc.)
---@param value any
---@param max_len? integer Maximum string length before truncation (default 50)
---@return string
local function serialize_value(value, max_len)
  max_len = max_len or 50
  if value == nil then
    return "nil"
  elseif type(value) == "table" then
    -- For arrays, show contents; for objects, show count
    if #value > 0 then
      local items = {}
      for i, v in ipairs(value) do
        if i > 5 then
          table.insert(items, "...")
          break
        end
        table.insert(items, tostring(v))
      end
      return "[" .. table.concat(items, ",") .. "]"
    elseif next(value) then
      local count = 0
      for _ in pairs(value) do
        count = count + 1
      end
      return "{" .. count .. " keys}"
    else
      return "{}"
    end
  elseif type(value) == "string" then
    if #value > max_len then
      return '"' .. value:sub(1, max_len - 3) .. '..."'
    end
    return '"' .. value .. '"'
  elseif type(value) == "boolean" then
    return value and "true" or "false"
  else
    return tostring(value)
  end
end

--- Serialize params table to readable string for logging
--- Examples: "({cards=[0,2,4], deck="RED"})" or "()"
---@param params table|nil
---@return string
function BB_FORMAT.serialize_params(params)
  if params == nil or next(params) == nil then
    return "()"
  end
  local parts = {}
  for k, v in pairs(params) do
    table.insert(parts, k .. "=" .. serialize_value(v))
  end
  -- Sort for consistent output
  table.sort(parts)
  return "({" .. table.concat(parts, ", ") .. "})"
end

--- Format a playing card as "R♠" style (e.g., "A♠", "K♥", "10♦")
---@param card table The card object with card.base.value and card.base.suit
---@return string
function BB_FORMAT.format_playing_card(card)
  if not card or not card.base then
    return "?"
  end
  local suit_icons = { Spades = "♠", Hearts = "♥", Diamonds = "♦", Clubs = "♣" }
  local rank = card.base.value or "?"
  -- Shorten face card names: "Jack" -> "J", "Queen" -> "Q", "King" -> "K", "Ace" -> "A"
  if rank == "10" then
    rank = "10"
  elseif rank and #rank > 1 then
    rank = rank:sub(1, 1)
  end
  local suit = suit_icons[card.base.suit] or "?"
  return rank .. suit
end

--- Format array of playing cards by indices (0-based API indices)
---@param cards table[] Array of card objects (1-based Lua array)
---@param indices integer[] Array of 0-based indices
---@return string Comma-separated card strings like "A♠, K♥, Q♦"
function BB_FORMAT.format_playing_cards(cards, indices)
  local parts = {}
  for _, idx in ipairs(indices) do
    local card = cards[idx + 1] -- 0-based to 1-based
    table.insert(parts, BB_FORMAT.format_playing_card(card))
  end
  return table.concat(parts, ", ")
end

return BB_FORMAT
