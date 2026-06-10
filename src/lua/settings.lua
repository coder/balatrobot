--[[
BalatroBot v2 settings — profile-based configuration.

Environment variables:
  BALATROBOT_HOST          - Server hostname (default: 127.0.0.1)
  BALATROBOT_PORT          - Server port (default: 12346)
  BALATROBOT_RENDER        - Render mode: headfull|headless|ondemand (default: headfull)
  BALATROBOT_DEBUG         - Enable debug endpoints (1/0, default: 0)
  BALATROBOT_SETTINGS      - Path to balatrosettings profile directory
  BALATROBOT_PATH_BALATRO  - Path to Balatro directory
  BALATROBOT_PATH_LOVELY   - Path to lovely library
  BALATROBOT_PATH_LOVE     - Path to LOVE executable
  BALATROBOT_PLATFORM      - Platform override
  BALATROBOT_PATH_LOGS     - Log directory
  BALATROBOT_NUM           - Number of instances
]]

---@diagnostic disable: duplicate-set-field

---@type Settings
BB_SETTINGS = {
  host = os.getenv("BALATROBOT_HOST") or "127.0.0.1",
  port = tonumber(os.getenv("BALATROBOT_PORT")) or 12346,
  render = os.getenv("BALATROBOT_RENDER") or "headfull",
  debug = os.getenv("BALATROBOT_DEBUG") == "1" or false,
  settings_path = os.getenv("BALATROBOT_SETTINGS"),
}

---@type boolean?
BB_RENDER = nil

--- Deep merge source into target table (recursive)
---@param target table
---@param source table
local function deep_merge(target, source)
  for k, v in pairs(source) do
    if type(v) == "table" and type(target[k]) == "table" then
      deep_merge(target[k], v)
    else
      target[k] = v
    end
  end
end

--- Apply balatrosettings profile from directory
---@param path string Absolute path to profile directory
local function apply_profile(path)
  local NFS = require("nativefs")

  -- Deep merge settings.lua into G.SETTINGS
  local settings_src = NFS.read(path .. "/settings.lua")
  assert(settings_src, "Profile not found: " .. path .. "/settings.lua")
  local profile_settings = assert(load(settings_src))()
  assert(type(profile_settings) == "table", "settings.lua must return a table")
  deep_merge(G.SETTINGS, profile_settings)

  -- Deep merge 1/profile.lua into G.PROFILES[n]
  local profile_src = NFS.read(path .. "/1/profile.lua")
  assert(profile_src, "Profile not found: " .. path .. "/1/profile.lua")
  local profile_data = assert(load(profile_src))()
  assert(type(profile_data) == "table", "1/profile.lua must return a table")
  local n = G.SETTINGS.profile or 1
  G.PROFILES[n] = G.PROFILES[n] or {}
  deep_merge(G.PROFILES[n], profile_data)

  sendInfoMessage("Applied profile: " .. path, "BB.SETTINGS")
end

--- Headless mode: disable all rendering and window operations
local function configure_headless()
  if love.window and love.window.isOpen() then
    if love.window.minimize then
      love.window.minimize()
    end
    love.window.setMode(1, 1)
    love.window.setPosition(-1000, -1000)
  end

  love.graphics.isActive = function()
    return false
  end
  love.draw = function() end
  love.graphics.present = function() end

  if love.window then
    love.window.setMode = function()
      return false
    end
    love.window.isOpen = function()
      return false
    end
    love.window.setPosition = function() end
    love.window.minimize = function() end
    love.window.maximize = function() end
    love.window.restore = function() end
    love.window.requestAttention = function() end
    love.window.setFullscreen = function()
      return false
    end
    love.graphics.isCreated = function()
      return false
    end
  end

  sendInfoMessage("Render mode: headless", "BB.SETTINGS")
end

--- On-demand rendering: only render when BB_RENDER is set
local function configure_ondemand()
  BB_RENDER = false

  local love_draw = love.draw
  local love_graphics_present = love.graphics.present
  local did_render = false

  love.draw = function()
    if BB_RENDER then
      love_draw()
      did_render = true
      BB_RENDER = false
    else
      did_render = false
    end
  end

  love.graphics.present = function()
    if did_render then
      love_graphics_present()
      did_render = false
    end
  end

  sendInfoMessage("Render mode: ondemand", "BB.SETTINGS")
end

--- Initialize BalatroBot settings. Returns false if "BalatroBot" profile not selected.
---@return boolean
BB_SETTINGS.setup = function()
  -- Gate: only activate when in-game profile is named "BalatroBot"
  local profile_num = G.SETTINGS.profile or 1
  local profile = G.PROFILES[profile_num]
  if not profile or profile.name ~= "BalatroBot" then
    sendWarnMessage(
      "BalatroBot profile not selected. Create a profile named 'BalatroBot' and select it.",
      "BB.SETTINGS"
    )
    return false
  end

  -- Hardcoded overrides for bot operation
  G.F_SKIP_TUTORIAL = true
  G.PROFILES[profile_num].all_unlocked = true

  -- Apply settings profile if --settings provided
  if BB_SETTINGS.settings_path then
    apply_profile(BB_SETTINGS.settings_path)
  end

  -- Render mode
  if BB_SETTINGS.render == "headless" then
    configure_headless()
  elseif BB_SETTINGS.render == "ondemand" then
    configure_ondemand()
  end

  return true
end
