--[[
  Screenshot logging — writes a PNG of the post-action game state after a
  successful API response. Opt-in via BB_SETTINGS.screenshots.

  When enabled, capture is deferred until the screen is quiescent (every
  Moveable stationary) and the API response is held back until then, so a
  rapid-fire client cannot start request N+1 before N's settled frame is
  captured. See docs/adr/0003-screenshot-settling-quiescence.md.

  In ondemand mode a BB_RENDER flip re-arms rendering for the settled frame;
  the dispatch-start flip stays untouched. See docs/adr/0002.
]]

local nativefs = require("nativefs")

--- Seconds to wait for the screen to settle before capturing anyway (deadman).
--- Guards against a future perpetual motion hanging the API; should never fire.
local TIMEOUT = 15

--- True when no Moveable is meaningfully still animating. Position/rotation must
--- be at target; juice (active wiggle) must be done. The hover-scale term in
--- move_scale (states.hover.is and 0.05) is a *static* zoom the easing never
--- converges to STATIONARY against, so scale-only residual is tolerated.
local function is_settled(m)
  if m.juice then
    return false
  end
  local t, vt = m.T, m.VT
  if not t or not vt then
    return true
  end
  if math.abs(t.x - vt.x) > 0.01 or math.abs(t.y - vt.y) > 0.01 then
    return false
  end
  if math.abs(t.r - vt.r) > 0.001 then
    return false
  end
  return true
end

local function is_quiescent()
  for _, m in pairs(G.MOVEABLES) do
    if not is_settled(m) then
      return false
    end
  end
  return true
end

--- Encode the current framebuffer to <id>.png (ondemand render armed first).
---@param id integer|string|nil JSON-RPC request id (filename stem)
local function capture_now(id)
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
end

---@type Screenshot
BB_SCREENSHOT = {
  --- Wait until the screen is quiescent, capture it, then call `after` (which
  --- sends the API response). No-op of the wait when screenshots are off is the
  --- caller's responsibility (server calls this only when screenshots are on).
  ---@param id integer|string|nil JSON-RPC request id (filename stem)
  ---@param after fun() called in the same settled frame, after capture initiates
  capture_when_settled = function(id, after)
    local deadline = G.TIMERS.REAL + TIMEOUT
    G.E_MANAGER:add_event(Event({
      trigger = "condition",
      blocking = false,
      blockable = false,
      pause_force = true,
      func = function()
        if is_quiescent() then
          capture_now(id)
          after()
          return true
        end
        if G.TIMERS.REAL >= deadline then
          sendWarnMessage("Screenshot quiescence deadman hit; capturing anyway", "BB.SCREENSHOT")
          capture_now(id)
          after()
          return true
        end
        return false
      end,
    }))
  end,
}

return BB_SCREENSHOT
