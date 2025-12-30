-- src/lua/utils/debugger.lua
-- DebugPlus Integration
--
-- Attempts to load and configure DebugPlus API for enhanced debugging
-- Provides logger instance when DebugPlus mod is available

-- Load test endpoints if debug mode is enabled
table.insert(BB_ENDPOINTS, "src/lua/endpoints/tests/echo.lua")
table.insert(BB_ENDPOINTS, "src/lua/endpoints/tests/state.lua")
table.insert(BB_ENDPOINTS, "src/lua/endpoints/tests/error.lua")
table.insert(BB_ENDPOINTS, "src/lua/endpoints/tests/validation.lua")
sendDebugMessage("Loading test endpoints", "BB.BALATROBOT")

-- Helper function to format response as pretty-printed table
local function format_response(response, depth, indent)
  depth = depth or 5
  indent = indent or ""

  if depth == 0 then
    return tostring(response)
  end

  if type(response) ~= "table" then
    return tostring(response)
  end

  -- Check for custom tostring
  if (getmetatable(response) or {}).__tostring then
    return tostring(response)
  end

  local result = "{\n"
  local count = 0
  local max_items = 50 -- Limit items per level to prevent huge output

  for k, v in pairs(response) do
    -- Skip "hands" key as it clutters the output
    if k ~= "hands" then
      count = count + 1
      if count > max_items then
        result = result .. indent .. "  ... (" .. (count - max_items) .. " more items)\n"
        break
      end

      local key_str = tostring(k)
      local value_str

      if type(v) == "table" then
        value_str = format_response(v, depth - 1, indent .. "  ")
      else
        value_str = tostring(v)
      end

      result = result .. indent .. "  " .. key_str .. ": " .. value_str .. "\n"
    end
  end

  result = result .. indent .. "}"
  return result
end

-- Define BB_API global namespace for calling endpoints via /eval
-- Usage: /eval BB_API.gamestate({})
-- Usage: /eval BB_API.start({deck="RED", stake="WHITE"})
BB_API = setmetatable({}, {
  __index = function(t, endpoint_name)
    return function(args)
      args = args or {}

      -- Check if dispatcher is initialized
      if not BB_DISPATCHER or not BB_DISPATCHER.endpoints then
        error("BB_DISPATCHER not initialized")
      end

      -- Check if endpoint exists
      if not BB_DISPATCHER.endpoints[endpoint_name] then
        error("Unknown endpoint: " .. endpoint_name)
      end

      -- Create request
      local request = {
        method = endpoint_name,
        params = args,
      }

      -- Override send_response to capture and log
      local original_send_response = BB_DISPATCHER.Server.send_response

      BB_DISPATCHER.Server.send_response = function(response)
        -- Restore immediately to prevent race conditions
        BB_DISPATCHER.Server.send_response = original_send_response

        -- Log the response if in debug mode
        if BB_DEBUG and BB_DEBUG.log then
          local formatted = format_response(response)
          local level = response.error and "error" or "info"
          BB_DEBUG.log[level]("API[" .. endpoint_name .. "] Response:\n" .. formatted)
        end

        -- Still send to TCP client if connected
        original_send_response(response)
      end

      -- Dispatch the request
      BB_DISPATCHER.dispatch(request)

      return "Dispatched: " .. endpoint_name .. "()"
    end
  end,
})

---@type Debug
BB_DEBUG = {
  log = nil,
}
--- Initializes DebugPlus integration if available
--- Registers BalatroBot with DebugPlus and creates logger instance
---@return nil
BB_DEBUG.setup = function()
  local success, dpAPI = pcall(require, "debugplus.api")
  if not success or not dpAPI then
    sendDebugMessage("DebugPlus API not found", "BB.DEBUGGER")
    return
  end
  if not dpAPI.isVersionCompatible(1) then
    sendDebugMessage("DebugPlus API version is not compatible", "BB.DEBUGGER")
    return
  end
  local dp = dpAPI.registerID("BalatroBot")
  if not dp then
    sendDebugMessage("Failed to register with DebugPlus", "BB.DEBUGGER")
    return
  end

  -- Create a logger
  BB_DEBUG.log = dp.logger
  BB_DEBUG.log.debug("DebugPlus API available")
  BB_DEBUG.log.info("Use /eval BB_API.endpoint_name({args}) to call API endpoints")
end
