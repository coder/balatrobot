-- src/lua/endpoints/load.lua

-- ==========================================================================
-- Load Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Load.Params
---@field path string File path to the save file

-- ==========================================================================
-- Load Endpoint Utils
-- ==========================================================================

local nativefs = require("nativefs")

-- ==========================================================================
-- Load Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "load",

  description = "Load a saved run state from a file",

  schema = {
    path = {
      type = "string",
      required = true,
      description = "File path to the save file",
    },
  },

  requires_state = nil,

  ---@param args Request.Endpoint.Load.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init load()", "BB.ENDPOINTS")
    local path = args.path

    -- Check if file exists
    local file_info = nativefs.getInfo(path)
    if not file_info or file_info.type ~= "file" then
      send_response({
        message = "File not found: '" .. path .. "'",
        name = BB_ERROR_NAMES.INTERNAL_ERROR,
      })
      return
    end

    -- Read file using nativefs
    local compressed_data = nativefs.read(path)
    ---@cast compressed_data string
    if not compressed_data then
      send_response({
        message = "Failed to read save file",
        name = BB_ERROR_NAMES.INTERNAL_ERROR,
      })
      return
    end

    -- Write to temp location for get_compressed to read
    local temp_filename = "balatrobot_temp_load_" .. BB_SETTINGS.port .. ".jkr"
    local save_dir = love.filesystem.getSaveDirectory()
    local temp_path = save_dir .. "/" .. temp_filename

    local write_success = nativefs.write(temp_path, compressed_data)
    if not write_success then
      send_response({
        message = "Failed to prepare save file for loading",
        name = BB_ERROR_NAMES.INTERNAL_ERROR,
      })
      return
    end

    -- Load using game's built-in functions
    G:delete_run()
    G.SAVED_GAME = get_compressed(temp_filename) ---@diagnostic disable-line: undefined-global

    if G.SAVED_GAME == nil then
      send_response({
        message = "Invalid save file format",
        name = BB_ERROR_NAMES.INTERNAL_ERROR,
      })
      love.filesystem.remove(temp_filename)
      return
    end

    G.SAVED_GAME = STR_UNPACK(G.SAVED_GAME)

    -- Temporarily suppress "Card area not instantiated" warnings during load
    -- These are expected when loading a save from shop state (shop CardAreas
    -- are created later when the shop UI renders, and the game handles this)
    local original_print = print
    print = function(msg)
      if type(msg) == "string" and msg:find("ERROR LOADING GAME: Card area") then
        return -- suppress expected warning
      end
      original_print(msg)
    end

    G:start_run({ savetext = G.SAVED_GAME })

    -- Restore original print
    print = original_print

    -- Clean up
    love.filesystem.remove(temp_filename)

    local num_items = function(area)
      local count = 0
      if area and area.cards then
        for _, v in ipairs(area.cards) do
          if v.children.buy_button and v.children.buy_button.definition then
            count = count + 1
          end
        end
      end
      return count
    end

    G.E_MANAGER:add_event(Event({
      no_delete = true,
      trigger = "condition",
      blocking = false,
      func = function()
        local done = false

        if not G.STATE_COMPLETE or G.CONTROLLER.locked then
          return false
        end

        if G.STATE == G.STATES.BLIND_SELECT then
          done = G.GAME.blind_on_deck ~= nil
            and G.blind_select_opts ~= nil
            and G.blind_select_opts["small"]:get_UIE_by_ID("tag_Small") ~= nil
        end

        if G.STATE == G.STATES.SELECTING_HAND then
          done = G.hand ~= nil
        end

        if G.STATE == G.STATES.ROUND_EVAL and G.round_eval then
          for _, b in ipairs(G.I.UIBOX) do
            if b:get_UIE_by_ID("cash_out_button") then
              done = true
            end
          end
        end

        if G.STATE == G.STATES.SHOP then
          done = num_items(G.shop_booster) > 0 or num_items(G.shop_jokers) > 0 or num_items(G.shop_vouchers) > 0
        end

        if G.STATE == G.STATES.SMODS_BOOSTER_OPENED then
          done = G.pack_cards and G.pack_cards.cards and #G.pack_cards.cards > 0
        end

        if done then
          sendDebugMessage("Return load() - loaded from " .. path, "BB.ENDPOINTS")
          send_response({
            success = true,
            path = path,
          })
        end
        return done
      end,
    }))
  end,
}
