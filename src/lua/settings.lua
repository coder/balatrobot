--[[
BalatroBot configure settings in Balatro using the following environment variables:

  - BALATROBOT_HOST: the hostname when the TCP server is running.
      Type string (default: 127.0.0.1)

  - BALATROBOT_PORT: the port when the TCP server is running.
      Type string (default: 12346)

  - BALATROBOT_HEADLESS: whether to run in headless mode.
      1 for actiavate the headeless mode, 0 for running headed (default: 0)

  - BALATROBOT_FAST: whether to run in fast mode.
      1 for actiavate the fast mode, 0 for running slow (default: 0)

  - BALATROBOT_RENDER_ON_API: whether to render frames only on API calls.
      1 for actiavate the render on API mode, 0 for normal rendering (default: 0)

  - BALATROBOT_AUDIO: whether to play audio.
      1 for actiavate the audio mode, 0 for no audio (default: 0)

  - BALATROBOT_DEBUG: whether enable debug mode. It requires DebugPlus mod to be running.
      1 for actiavate the debug mode, 0 for no debug (default: 0)

  - BALATROBOT_NO_SHADERS: whether to disable all shaders for better performance.
      1 for disable shaders, 0 for enable shaders (default: 0)

  - BALATROBOT_FPS_CAP: the maximum FPS cap for the game.
      Type number (default: 60)

  - BALATROBOT_GAMESPEED: the game speed multiplier.
      Type number (default: 4)

  - BALATROBOT_ANIMATION_FPS: the animation FPS.
      Type number (default: 10)

  - BALATROBOT_NO_REDUCED_MOTION: whether to disable reduced motion.
      1 for disable reduced motion, 0 for enable reduced motion (default: 0)

  - BALATROBOT_PIXEL_ART_SMOOTHING: whether to enable pixel art smoothing.
      1 for enable pixel art smoothing, 0 for disable (default: 0)
]]

---@diagnostic disable: duplicate-set-field

---@type Settings
BB_SETTINGS = {
  host = os.getenv("BALATROBOT_HOST") or "127.0.0.1",
  port = tonumber(os.getenv("BALATROBOT_PORT")) or 12346,
  headless = os.getenv("BALATROBOT_HEADLESS") == "1" or false,
  fast = os.getenv("BALATROBOT_FAST") == "1" or false,
  render_on_api = os.getenv("BALATROBOT_RENDER_ON_API") == "1" or false,
  audio = os.getenv("BALATROBOT_AUDIO") == "1" or false,
  debug = os.getenv("BALATROBOT_DEBUG") == "1" or false,
  no_shaders = os.getenv("BALATROBOT_NO_SHADERS") == "1" or false,
  fps_cap = tonumber(os.getenv("BALATROBOT_FPS_CAP")) or 60,
  gamespeed = tonumber(os.getenv("BALATROBOT_GAMESPEED")) or 4,
  animation_fps = tonumber(os.getenv("BALATROBOT_ANIMATION_FPS")) or 10,
  no_reduced_motion = os.getenv("BALATROBOT_NO_REDUCED_MOTION") == "1" or false,
  pixel_art_smoothing = os.getenv("BALATROBOT_PIXEL_ART_SMOOTHING") == "1" or false,
}

---@type boolean?
BB_RENDER = nil

--- Patches love.update to use a fixed delta time based on headless mode
--- Headless mode uses 4.99/60 for faster simulation, normal mode uses 1/60
---@return nil
local function configure_love_update()
  local love_update = love.update
  local dt = BB_SETTINGS.headless and (4.99 / 60.0) or (1.0 / 60.0)
  love.update = function(_)
    love_update(dt)
  end
  sendDebugMessage("Patched love.update with dt=" .. dt, "BB.SETTINGS")
end

--- Configures base game settings for optimal bot performance
--- Disables audio, sets high game speed, reduces visual effects, and disables tutorials
---@return nil
local function configure_settings()
  -- disable audio
  G.SETTINGS.SOUND.volume = 0
  G.SETTINGS.SOUND.music_volume = 0
  G.SETTINGS.SOUND.game_sounds_volume = 0
  G.F_SOUND_THREAD = false
  G.F_MUTE = true

  -- performance
  G.FPS_CAP = BB_SETTINGS.fps_cap
  G.SETTINGS.GAMESPEED = BB_SETTINGS.gamespeed
  G.ANIMATION_FPS = BB_SETTINGS.animation_fps

  -- features
  G.F_SKIP_TUTORIAL = true
  G.VIBRATION = 0
  G.F_VERBOSE = true
  G.F_RUMBLE = nil

  -- graphics
  G.SETTINGS.GRAPHICS = G.SETTINGS.GRAPHICS or {}
  G.SETTINGS.GRAPHICS.shadows = "Off" -- Always disable shadows
  G.SETTINGS.GRAPHICS.bloom = 0 -- Always disable CRT bloom
  G.SETTINGS.GRAPHICS.crt = 0 -- Always disable CRT
  G.SETTINGS.GRAPHICS.texture_scaling = BB_SETTINGS.pixel_art_smoothing and 2 or 1

  -- visuals
  G.SETTINGS.skip_splash = "Yes" -- Skip intro animation
  G.SETTINGS.reduced_motion = not BB_SETTINGS.no_reduced_motion
  G.SETTINGS.screenshake = false
  G.SETTINGS.rumble = nil

  -- Window
  love.window.setVSync(0)
  G.SETTINGS.WINDOW = G.SETTINGS.WINDOW or {}
  G.SETTINGS.WINDOW.vsync = 0
end

--- Configures headless mode by minimizing and hiding the window
--- Disables all rendering operations, graphics, and window updates
---@return nil
local function configure_headless()
  if love.window and love.window.isOpen() then
    if love.window.minimize then
      love.window.minimize()
      sendDebugMessage("Minimized window", "BB.SETTINGS")
    end

    love.window.setMode(1, 1)
    love.window.setPosition(-1000, -1000)
    sendDebugMessage("Set window to 1x1 and moved to (-1000, -1000)", "BB.SETTINGS")
  end

  -- Disable all rendering operations
  love.graphics.isActive = function()
    return false
  end

  -- Disable drawing operations
  love.draw = function()
    -- Do nothing in headless mode
  end

  -- Disable graphics present/swap buffers
  love.graphics.present = function()
    -- Do nothing in headless mode
  end

  -- Disable window creation/updates for future calls
  if love.window then
    love.window.setMode = function()
      return false
    end

    love.window.isOpen = function()
      return false
    end

    love.window.setPosition = function()
      -- Do nothing
    end

    love.window.minimize = function()
      -- Do nothing
    end

    love.window.maximize = function()
      -- Do nothing
    end

    love.window.restore = function()
      -- Do nothing
    end

    love.window.requestAttention = function()
      -- Do nothing
    end

    love.window.setFullscreen = function()
      return false
    end

    love.graphics.isCreated = function()
      return false
    end
  end

  sendInfoMessage("Headless mode enabled", "BB.SETTINGS")
end

--- Configures render-on-API mode where frames are only rendered when BB_RENDER is true
--- Patches love.draw and love.graphics.present to conditionally render based on BB_RENDER flag
---@return nil
local function configure_render_on_api()
  BB_RENDER = false

  -- Original render function
  local love_draw = love.draw
  local love_graphics_present = love.graphics.present

  local did_render_this_frame = false

  love.draw = function()
    if BB_RENDER then
      love_draw()
      did_render_this_frame = true
      BB_RENDER = false
    else
      did_render_this_frame = false
    end
  end

  love.graphics.present = function()
    if did_render_this_frame then
      love_graphics_present()
      did_render_this_frame = false
    end
  end

  sendInfoMessage("Render on API mode enabled", "BB.SETTINGS")
end

--- Configures fast mode with unlimited FPS, 10x game speed, and 60 FPS animations
---@return nil
local function configure_fast()
  -- performance
  G.FPS_CAP = nil -- Unlimited FPS
  G.SETTINGS.GAMESPEED = 10 -- 10x game speed
  G.ANIMATION_FPS = 60 -- 6x faster animations
  G.F_VERBOSE = false
end

--- Disables all shaders by overriding love.graphics.setShader to always pass nil
--- This improves performance by bypassing shader compilation and rendering
--- Disabling shaders cause visual glitches. Use at your own risk.
---@return nil
local function configure_no_shaders()
  local love_graphics_setShader = love.graphics.setShader
  love.graphics.setShader = function()
    return love_graphics_setShader()
  end
  sendInfoMessage("Disabled all shaders", "BB.SETTINGS")
end

--- Enables audio by setting volume levels and enabling sound thread
---@return nil
local function configure_audio()
  G.SETTINGS.SOUND = G.SETTINGS.SOUND or {}
  G.SETTINGS.SOUND.volume = 50
  G.SETTINGS.SOUND.music_volume = 100
  G.SETTINGS.SOUND.game_sounds_volume = 100
  G.F_MUTE = false
  G.F_SOUND_THREAD = true
end

--- Initializes and applies all BalatroBot settings based on environment variables
--- Orchestrates configuration of love.update, game settings, and optional features
--- (headless, render-on-api, fast mode, audio)
---@return nil
BB_SETTINGS.setup = function()
  configure_love_update()
  configure_settings()

  if BB_SETTINGS.headless and BB_SETTINGS.render_on_api then
    sendWarnMessage("Headless mode and render on API mode are mutually exclusive. Disabling headless", "BB.SETTINGS")
    BB_SETTINGS.headless = false
  end

  if BB_SETTINGS.headless then
    configure_headless()
  end

  if BB_SETTINGS.render_on_api then
    configure_render_on_api()
  end

  if BB_SETTINGS.fast then
    configure_fast()
  end

  if BB_SETTINGS.no_shaders then
    configure_no_shaders()
  end

  if BB_SETTINGS.audio then
    configure_audio()
  end
end
