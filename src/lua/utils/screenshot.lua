--[[
  Screenshot logging — writes a PNG of the post-action game state after a
  successful API response. Opt-in via BB_SETTINGS.screenshots.

  See docs/adr/0002-screenshot-logging-ondemand-render.md: in ondemand mode a
  second BB_RENDER flip is required here so the settled post-action frame is
  captured (the dispatch-start flip has already been consumed).
]]

local nativefs = require("nativefs")

---@type Screenshot
BB_SCREENSHOT = {
  ---@param id integer|string|nil JSON-RPC request id (used as the filename stem)
  capture = function(id)
    if not BB_SETTINGS.screenshots then
      return
    end

    local logs = os.getenv("BALATROBOT_PATH_LOGS")
    if not logs or logs == "" then
      return
    end

    local safe_id = tostring(id):gsub("[^A-Za-z0-9._-]", "_")
    local dir = logs .. "/" .. BB_SETTINGS.port
    if not nativefs.createDirectory(dir) then
      sendErrorMessage("Cannot create screenshot dir: " .. dir, "BB.SCREENSHOT")
      return
    end
    local path = dir .. "/" .. safe_id .. ".png"

    -- Re-arm ondemand rendering so the next love.draw renders the settled frame.
    if BB_SETTINGS.render == "ondemand" then
      BB_RENDER = true
    end

    love.graphics.captureScreenshot(function(imagedata)
      local png = imagedata:encode("png"):getString()
      if not nativefs.write(path, png) then
        sendErrorMessage("Failed to write screenshot: " .. path, "BB.SCREENSHOT")
      end
    end)
  end,
}

return BB_SCREENSHOT
