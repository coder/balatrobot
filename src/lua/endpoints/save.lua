-- src/lua/endpoints/save.lua

-- ==========================================================================
-- Save Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Save.Params
---@field path string File path for the save file

-- ==========================================================================
-- Save Endpoint Utils
-- ==========================================================================

local nativefs = require("nativefs")

-- ==========================================================================
-- Save Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "save",

  description = "Save the current run state to a file",

  schema = {
    path = {
      type = "string",
      required = true,
      description = "File path for the save file",
    },
  },

  requires_state = {
    G.STATES.SELECTING_HAND,
    G.STATES.HAND_PLAYED,
    G.STATES.DRAW_TO_HAND,
    G.STATES.GAME_OVER,
    G.STATES.SHOP,
    G.STATES.PLAY_TAROT,
    G.STATES.BLIND_SELECT,
    G.STATES.ROUND_EVAL,
    G.STATES.TAROT_PACK,
    G.STATES.PLANET_PACK,
    G.STATES.SPECTRAL_PACK,
    G.STATES.STANDARD_PACK,
    G.STATES.BUFFOON_PACK,
    G.STATES.NEW_ROUND,
    G.STATES.SMODS_BOOSTER_OPENED,
  },

  ---@param args Request.Endpoint.Save.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("Init save()", "BB.ENDPOINTS")
    local path = args.path

    -- Validate we're in a run
    if not G.STAGE or G.STAGE ~= G.STAGES.RUN then
      send_response({
        message = "Can only save during an active run",
        name = BB_ERROR_NAMES.INVALID_STATE,
      })
      return
    end

    -- Call save_run() and use compress_and_save
    save_run() ---@diagnostic disable-line: undefined-global

    local temp_filename = "balatrobot_temp_save_" .. BB_SETTINGS.port .. ".jkr"
    compress_and_save(temp_filename, G.ARGS.save_run) ---@diagnostic disable-line: undefined-global

    -- Read from temp and write to target path using nativefs
    local save_dir = love.filesystem.getSaveDirectory()
    local temp_path = save_dir .. "/" .. temp_filename
    local compressed_data = nativefs.read(temp_path)
    ---@cast compressed_data string

    if not compressed_data then
      send_response({
        message = "Failed to save game state",
        name = BB_ERROR_NAMES.INTERNAL_ERROR,
      })
      return
    end

    local write_success = nativefs.write(path, compressed_data)
    if not write_success then
      send_response({
        message = "Failed to write save file to '" .. path .. "'",
        name = BB_ERROR_NAMES.INTERNAL_ERROR,
      })
      return
    end

    -- Clean up
    love.filesystem.remove(temp_filename)

    sendDebugMessage("Return save() - saved to " .. path, "BB.ENDPOINTS")
    send_response({
      success = true,
      path = path,
    })
  end,
}
