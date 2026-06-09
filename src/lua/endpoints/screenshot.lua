-- src/lua/endpoints/screenshot.lua

-- ==========================================================================
-- Screenshot Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Screenshot.Params
---@field path string File path for the screenshot file

-- ==========================================================================
-- Screenshot Endpoint Utils
-- ==========================================================================

local nativefs = require("nativefs")

-- ==========================================================================
-- Screenshot Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "screenshot",

  description = "Take a screenshot of the current game state",

  schema = {
    path = {
      type = "string",
      required = true,
      description = "File path for the screenshot file",
    },
  },

  requires_state = nil,

  ---@param args Request.Endpoint.Screenshot.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(args, send_response)
    sendDebugMessage("screenshot()", "BB.ENDPOINTS")
    local path = args.path

    love.graphics.captureScreenshot(function(imagedata)
      -- Encode ImageData to PNG format
      local filedata = imagedata:encode("png")

      if not filedata then
        send_response({
          message = "Failed to encode screenshot",
          name = BB_ERROR_NAMES.INTERNAL_ERROR,
        })
        return
      end

      -- Get PNG data as string
      local png_data = filedata:getString()

      -- Write to target path using nativefs
      sendInfoMessage("Screenshot → " .. path, "BB.ENDPOINTS")
      local write_success = nativefs.write(path, png_data)
      if not write_success then
        send_response({
          message = "Failed to write screenshot file to '" .. path .. "'",
          name = BB_ERROR_NAMES.INTERNAL_ERROR,
        })
        return
      end

      sendDebugMessage("screenshot() → ok", "BB.ENDPOINTS")
      send_response({
        success = true,
        path = path,
      })
    end)
  end,
}
