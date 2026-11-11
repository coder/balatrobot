--[[
BalatroBot settings — profile-based configuration.

Environment variables read by the Lua mod:
  BALATROBOT_HOST          - Server hostname (default: 127.0.0.1)
  BALATROBOT_PORT          - Server port (set internally by launcher, default: 12346)
  BALATROBOT_RENDER        - Render mode: headfull|headless|ondemand (default: headfull)
  BALATROBOT_DEBUG         - Enable debug endpoints (1/0, default: 0)
  BALATROBOT_SCREENSHOTS   - Enable screenshot logging after each API response (1/0, default: 0)
  BALATROBOT_SETTINGS      - Settings profile name (bare name, e.g. "fast", "turbo", "light")
]]

---@diagnostic disable: duplicate-set-field

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

--- Apply settings profile by name
---@param name string Profile name (e.g. "default", "fast", "turbo", "light")
local function apply_profile(name)
  assert(name:match("^[a-zA-Z0-9][a-zA-Z0-9_-]*$"), "Invalid profile name: " .. name)
  local NFS = require("nativefs")

  local profile_dir = SMODS.current_mod.path .. "src/lua/profiles/" .. name .. "/"

  -- Deep merge settings.lua into G.SETTINGS (required)
  local settings_src = NFS.read(profile_dir .. "settings.lua")
  if not settings_src then
    -- List available profiles for error message
    local items = NFS.getDirectoryItems(SMODS.current_mod.path .. "src/lua/profiles/")
    local available = {}
    for _, item in ipairs(items) do
      table.insert(available, item)
    end
    sendErrorMessage(
      "Settings profile not found: '" .. name .. "'. Available: " .. table.concat(available, ", "),
      "BB.SETTINGS"
    )
    error("Settings profile not found: '" .. name .. "'")
  end
  local profile_settings = assert(load(settings_src))()
  assert(type(profile_settings) == "table", "settings.lua must return a table")
  deep_merge(G.SETTINGS, profile_settings)

  -- Deep merge profile.lua into G.PROFILES[n] (optional)
  local profile_src = NFS.read(profile_dir .. "profile.lua")
  if profile_src then
    local profile_data = assert(load(profile_src))()
    assert(type(profile_data) == "table", "profile.lua must return a table")
    local n = G.SETTINGS.profile or 1
    G.PROFILES[n] = G.PROFILES[n] or {}
    deep_merge(G.PROFILES[n], profile_data)
  end

  sendInfoMessage("Applied profile: " .. name, "BB.SETTINGS")
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
local function setup()
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
  G.F_ENGLISH_ONLY = true
  G.F_NO_ACHIEVEMENTS = true
  G.F_VERBOSE = BB_SETTINGS.debug
  G.PROFILES[profile_num].all_unlocked = true

  -- all_unlocked bypasses locks but not G.P_CENTERS[*].discovered; mirror
  -- G.FUNCS.unlock_all so fixtures stay portable across hosts (issue #220).
  local function bb_force_unlock()
    for _, centers in ipairs({ G.P_CENTERS, G.P_BLINDS, G.P_TAGS }) do
      for _, v in pairs(centers) do
        if not v.demo and not v.wip then
          v.alerted = true
          v.discovered = true
          v.unlocked = true
        end
      end
    end
  end

  -- Prototypes load before setup(), so force-discover now.
  if G.P_CENTERS and next(G.P_CENTERS) then
    bb_force_unlock()
    sendInfoMessage("Forced all centers discovered/unlocked", "BB.SETTINGS")
  end

  -- Re-apply on profile reload; the inner name check keeps other profiles safe.
  local _init_item_prototypes = Game.init_item_prototypes
  ---@diagnostic disable-next-line: duplicate-set-field
  Game.init_item_prototypes = function(self)
    _init_item_prototypes(self)
    local p = G.PROFILES and G.SETTINGS and G.SETTINGS.profile and G.PROFILES[G.SETTINGS.profile]
    if p and p.name == "BalatroBot" then
      bb_force_unlock()
    end
  end

  -- Apply settings profile (default if none specified)
  BB_SETTINGS.settings = BB_SETTINGS.settings or "default"
  apply_profile(BB_SETTINGS.settings)

  -- Render mode
  if BB_SETTINGS.render == "headfull" then
    -- default, no special configuration needed
  elseif BB_SETTINGS.render == "headless" then
    configure_headless()
  elseif BB_SETTINGS.render == "ondemand" then
    configure_ondemand()
  else
    sendErrorMessage(
      "Invalid render mode '" .. BB_SETTINGS.render .. "'. Must be headfull, headless, or ondemand. Aborting.",
      "BB.SETTINGS"
    )
    return false
  end

  -- Screenshots require rendering; warn and disable in headless mode
  if BB_SETTINGS.screenshots and BB_SETTINGS.render == "headless" then
    sendWarnMessage("Screenshots requested but render mode is headless; disabling screenshots", "BB.SETTINGS")
    BB_SETTINGS.screenshots = false
  end

  return true
end

---@type Settings
BB_SETTINGS = {
  host = os.getenv("BALATROBOT_HOST") or "127.0.0.1",
  port = tonumber(os.getenv("BALATROBOT_PORT")) or 12346,
  render = os.getenv("BALATROBOT_RENDER") or "headfull",
  debug = os.getenv("BALATROBOT_DEBUG") == "1" or false,
  screenshots = os.getenv("BALATROBOT_SCREENSHOTS") == "1" or false,
  settings = os.getenv("BALATROBOT_SETTINGS"),
  setup = setup,
}

---@type boolean?
BB_RENDER = nil
