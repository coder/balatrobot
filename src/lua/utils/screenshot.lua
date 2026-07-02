--[[
  Screenshot logging — writes a PNG of the post-action game state after a
  successful API response. Opt-in via BB_SETTINGS.screenshots.
]]

local nativefs = require("nativefs")

--- Set during capture to suppress hover (stale-cursor artifact).
local suppress_hover = false

--- Deadman timeout; should never fire.
local TIMEOUT = 15

--- Previous-frame VT signatures, keyed by object ID. Lets us detect moveables
--- whose VT never reaches T but is frozen (e.g. the GAME_OVER Jimbo character,
--- positioned off-screen with a permanent T!=VT offset). Such objects are
--- visually settled even though they never converge.
local _prev_vt = {}

--- A moveable is settled when position/rotation are at target (converged), OR
--- when its VT did not change since the last poll (frozen). Scale is skipped:
--- the hover-scale term keeps it perpetually off-target.
local function is_settled(m)
  if m.juice then
    return false
  end
  local t, vt = m.T, m.VT
  if not t or not vt then
    return true
  end
  local dx, dy, dr = math.abs(t.x - vt.x), math.abs(t.y - vt.y), math.abs(t.r - vt.r)
  local converged = dx <= 0.01 and dy <= 0.01 and dr <= 0.001
  if converged then
    _prev_vt[m.ID] = nil
    return true
  end
  -- Frozen? Compare against the VT recorded on the previous poll.
  local prev = _prev_vt[m.ID]
  local cur_x, cur_y, cur_r = vt.x, vt.y, vt.r
  _prev_vt[m.ID] = { cur_x, cur_y, cur_r }
  if
    prev
    and math.abs(cur_x - prev[1]) < 0.001
    and math.abs(cur_y - prev[2]) < 0.001
    and math.abs(cur_r - prev[3]) < 0.0001
  then
    return true
  end
  return false
end

local function is_quiescent()
  for _, m in pairs(G.MOVEABLES) do
    if not is_settled(m) then
      return false
    end
  end
  return true
end

--- Encode the current framebuffer to <id>.png (arms ondemand render first).
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

  if BB_SETTINGS.render == "ondemand" then
    BB_RENDER = true
  end
  suppress_hover = true

  love.graphics.captureScreenshot(function(imagedata)
    suppress_hover = false
    local png = imagedata:encode("png"):getString()
    if not nativefs.write(path, png) then
      sendErrorMessage("Failed to write screenshot: " .. path, "BB.SCREENSHOT")
    end
  end)
end

---@type Screenshot
BB_SCREENSHOT = {
  --- Wait until the screen is quiescent, capture it, then call `after`.
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

  --- Clear hover artifacts for the captured frame. Called from BB_SERVER.update,
  --- the only slot after G.CONTROLLER:update (which sets hover) and before
  --- love.draw (which renders+captures). Clears tint (hover.is), card popups
  --- (h_popup), and tag/blind popups (alert/info).
  clear_hover_for_capture = function()
    if not suppress_hover then
      return
    end
    for _, v in ipairs(G.DRAW_HASH) do
      if v.states and v.states.hover and v.states.hover.is then
        v.states.hover.is = false
      end
      if v.children then
        if v.children.h_popup then
          v:stop_hover()
        end
        if v.children.alert then
          v.children.alert:remove()
          v.children.alert = nil
        end
        if v.children.info then
          v.children.info:remove()
          v.children.info = nil
        end
      end
    end
  end,
}

return BB_SCREENSHOT
